"""
輪作計画メーカー - Gradio Application（複数農家対応版）
"""

import gradio as gr
import pandas as pd
import numpy as np
import random
import re
import os
os.environ["GRADIO_ANALYTICS_ENABLED"] = "False"  # Gradio 6.x アナリティクス無効化
from typing import Dict, List, Tuple, Optional, Set
from dataclasses import dataclass, field
from copy import deepcopy
from ortools.sat.python import cp_model

# 認証・DBアクセス
from auth import authenticate, get_user_info, is_admin_role
from db_access import FieldRepository, PlanRepository, CropHistoryRepository, UserRepository

# =============================================================================
# 定数・デフォルト値
# =============================================================================

DEFAULT_CROPS = [
    "春小麦", "秋小麦", "大豆", "てんさい", "馬鈴薯"
]

# デフォルト制約
DEFAULT_CONSTRAINTS = {
    "春小麦":     {"min_ha": None, "cap_ha": 10, "min_gap_years": 0, "min_fields": 0, "max_fields": None},
    "秋小麦":     {"min_ha": None, "cap_ha": 10, "min_gap_years": 0, "min_fields": 0, "max_fields": None},
    "大豆":       {"min_ha": None, "cap_ha": 12, "min_gap_years": 0, "min_fields": 0, "max_fields": None},
    "てんさい":   {"min_ha": None, "cap_ha": None, "min_gap_years": 4, "min_fields": 0, "max_fields": 2},
    "馬鈴薯":     {"min_ha": None, "cap_ha": None, "min_gap_years": 4, "min_fields": 0, "max_fields": None},
}

# 固定の禁止遷移
FIXED_FORBIDDEN_TRANSITIONS = [
    ("てんさい", "秋小麦"),  # 作期重複
    ("春小麦", "秋小麦"),    # 病害対策
]

# デフォルトの優先遷移
DEFAULT_PREFERRED_TRANSITIONS = "てんさい->大豆:10, てんさい->春小麦:5"

# 主作物（面積変動を抑えたい）
DEFAULT_MAIN_CROPS = "春小麦, 秋小麦, 大豆"

UNKNOWN_MARKER = "UNKNOWN"

# =============================================================================
# データクラス
# =============================================================================

@dataclass
class Field:
    """ほ場データ"""
    field_id: str
    district: str
    name: str
    area_ha: float
    history: Dict[str, str] = field(default_factory=dict)  # year -> crop
    has_unknown: bool = False
    beet_forbidden: bool = False  # 馬鈴薯・てんさい禁止

@dataclass
class Constraints:
    """制約設定"""
    crop_mins: Dict[str, Optional[float]] = field(default_factory=dict)  # min_ha
    crop_caps: Dict[str, Optional[float]] = field(default_factory=dict)  # cap_ha
    min_gap_years: Dict[str, int] = field(default_factory=dict)
    min_fields: Dict[str, int] = field(default_factory=dict)
    max_fields: Dict[str, Optional[int]] = field(default_factory=dict)
    forbidden_transitions: Set[Tuple[str, str]] = field(default_factory=set)
    preferred_transitions: Dict[Tuple[str, str], float] = field(default_factory=dict)
    main_crops: List[str] = field(default_factory=list)
    unknown_mode: str = "ignore"  # "ignore" or "safe"

# =============================================================================
# ユーティリティ関数
# =============================================================================

def parse_year_columns(columns: List[str]) -> List[str]:
    """R数字 形式の年列を抽出"""
    year_pattern = re.compile(r'^R\d+$')
    return [c for c in columns if year_pattern.match(c)]

def generate_future_years(past_years: List[str], n_years: int) -> List[str]:
    """将来の年列を生成"""
    if not past_years:
        return [f"R{i}" for i in range(9, 9 + n_years)]
    
    # 最後の年から続きを生成
    last_year = max(int(y[1:]) for y in past_years)
    return [f"R{last_year + i + 1}" for i in range(n_years)]

# 列名マッピング（期待列名: 代替列名リスト）
COLUMN_ALIASES = {
    'ほ場ID': ['field', 'ほ場名', 'field_id', 'id'],
    '地区': ['region', 'district', '地域'],
    'ほ場名': ['field', 'name', '名前', '名称'],
    'area': ['面積', 'area_ha', '面積(ha)', '面積(a)'],
    'beet_forbidden': ['禁止', 'てんさい禁止'],
}

def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """列名を正規化する"""
    renamed = {}
    for expected, aliases in COLUMN_ALIASES.items():
        if expected not in df.columns:
            for alias in aliases:
                if alias in df.columns:
                    renamed[alias] = expected
                    break
    if renamed:
        df = df.rename(columns=renamed)
    return df

def infer_crop_for_year(field: 'Field', year: str, crops: List[str],
                        forbidden_transitions: Set[Tuple[str, str]]) -> Optional[str]:
    """その年の作物を推論"""
    excluded = set()
    years = sorted(field.history.keys(), key=lambda y: int(y[1:]))
    if year not in years:
        return None
    year_idx = years.index(year)

    # 1. 連作禁止から逆算（前後の作物と同じものは除外）
    if year_idx > 0:
        prev_crop = field.history.get(years[year_idx - 1], "").replace("*", "")
        if prev_crop and prev_crop != UNKNOWN_MARKER:
            excluded.add(prev_crop)
    if year_idx < len(years) - 1:
        next_crop = field.history.get(years[year_idx + 1], "").replace("*", "")
        if next_crop and next_crop != UNKNOWN_MARKER:
            excluded.add(next_crop)

    # 2. 禁止遷移から逆算
    #    翌年が秋小麦なら、その年はてんさい・春小麦ではない
    if year_idx < len(years) - 1:
        next_crop = field.history.get(years[year_idx + 1], "").replace("*", "")
        if next_crop and next_crop != UNKNOWN_MARKER:
            for from_c, to_c in forbidden_transitions:
                if to_c == next_crop:
                    excluded.add(from_c)
    #    前年からの禁止遷移
    if year_idx > 0:
        prev_crop = field.history.get(years[year_idx - 1], "").replace("*", "")
        if prev_crop and prev_crop != UNKNOWN_MARKER:
            for from_c, to_c in forbidden_transitions:
                if from_c == prev_crop:
                    excluded.add(to_c)

    # 3. 間隔制約から推測（前後4年以内にてんさい・馬鈴薯があれば除外）
    for i, y in enumerate(years):
        if abs(i - year_idx) <= 4 and i != year_idx:
            c = field.history.get(y, "").replace("*", "")
            if c == "てんさい":
                excluded.add("てんさい")
            if c == "馬鈴薯":
                excluded.add("馬鈴薯")

    # 4. beet_forbidden の場合
    if field.beet_forbidden:
        excluded.add("てんさい")
        excluded.add("馬鈴薯")

    # 5. 候補を決定
    candidates = [c for c in crops if c not in excluded]
    if not candidates:
        return None

    # 6. 最も使用頻度の低い作物を選択（面積バランス考慮）
    return candidates[0]

def infer_unknown_crops(fields: List['Field'], crops: List[str],
                        forbidden_transitions: Set[Tuple[str, str]]) -> List['Field']:
    """空欄を推論で埋める"""
    for field in fields:
        for year, crop in list(field.history.items()):
            if crop == UNKNOWN_MARKER:
                inferred = infer_crop_for_year(field, year, crops, forbidden_transitions)
                if inferred:
                    field.history[year] = inferred + "*"  # 推論マーク
                    field.has_unknown = False  # 推論で埋まったのでフラグ更新
    return fields

def load_csv(file_path: str, area_unit: str) -> Tuple[List[Field], List[str], str]:
    """CSVを読み込んでFieldリストを返す"""
    try:
        df = pd.read_csv(file_path, encoding='utf-8')
    except:
        df = pd.read_csv(file_path, encoding='shift_jis')

    # 列名の正規化（空白除去）
    df.columns = df.columns.str.strip()

    # 列名エイリアスの適用
    df = normalize_columns(df)

    # ほ場IDの自動生成（列がない場合）
    if 'ほ場ID' not in df.columns:
        df['ほ場ID'] = [f'F{i+1:03d}' for i in range(len(df))]

    # 地区・ほ場名のフォールバック
    if '地区' not in df.columns:
        df['地区'] = ''
    if 'ほ場名' not in df.columns:
        df['ほ場名'] = df['ほ場ID']

    # 必須列のチェック（area のみ）
    if 'area' not in df.columns:
        return [], [], "エラー: 必須列 'area' がありません"
    
    # 年列の抽出
    year_cols = parse_year_columns(df.columns.tolist())
    if not year_cols:
        return [], [], "エラー: 年列（R数字形式）が見つかりません"
    
    # ソート
    year_cols = sorted(year_cols, key=lambda x: int(x[1:]))
    
    fields = []
    for _, row in df.iterrows():
        field_id = str(row['ほ場ID']).strip()
        district = str(row.get('地区', '')).strip() if pd.notna(row.get('地区', '')) else ''
        name = str(row.get('ほ場名', '')).strip() if pd.notna(row.get('ほ場名', '')) else ''
        
        # 面積変換
        area = row['area']
        if pd.isna(area) or area == '':
            area_ha = 0.0
        else:
            area_val = float(area)
            area_ha = area_val / 100 if area_unit.startswith('a') else area_val
        
        # 作付履歴
        history = {}
        has_unknown = False
        for y in year_cols:
            crop = row.get(y, '')
            if pd.isna(crop) or str(crop).strip() == '':
                history[y] = UNKNOWN_MARKER
                has_unknown = True
            else:
                history[y] = str(crop).strip()
        
        # beet_forbidden 列を読み込む（列がなければ False）
        beet_forbidden = False
        if 'beet_forbidden' in df.columns:
            val = row.get('beet_forbidden', 0)
            beet_forbidden = bool(int(val)) if pd.notna(val) and str(val).strip() != '' else False

        fields.append(Field(
            field_id=field_id,
            district=district,
            name=name,
            area_ha=area_ha,
            history=history,
            has_unknown=has_unknown,
            beet_forbidden=beet_forbidden
        ))
    
    return fields, year_cols, ""

def load_constraints_csv(file_path: str) -> pd.DataFrame:
    """制約CSVを読み込んでDataFrameに変換"""
    try:
        df = pd.read_csv(file_path, encoding='utf-8-sig')
    except:
        try:
            df = pd.read_csv(file_path, encoding='utf-8')
        except:
            df = pd.read_csv(file_path, encoding='shift_jis')

    # 列名の正規化（空白除去）
    df.columns = df.columns.str.strip()

    # 必要な列が存在するか確認
    required_cols = ['crop']
    for col in required_cols:
        if col not in df.columns:
            return pd.DataFrame()

    # 数値列の空欄をそのまま保持
    return df

def build_constraints_table(crops: List[str]) -> pd.DataFrame:
    """作物リストから制約テーブルを構築"""
    rows = []
    for crop in crops:
        if crop in DEFAULT_CONSTRAINTS:
            c = DEFAULT_CONSTRAINTS[crop]
        else:
            c = {"min_ha": None, "cap_ha": 10, "min_gap_years": 0, "min_fields": 0, "max_fields": None}

        rows.append({
            "crop": crop,
            "min_ha": c.get("min_ha", "") if c.get("min_ha") is not None else "",
            "cap_ha": c["cap_ha"] if c["cap_ha"] is not None else "",
            "min_gap_years": c["min_gap_years"],
            "min_fields": c["min_fields"],
            "max_fields": c["max_fields"] if c["max_fields"] is not None else ""
        })

    return pd.DataFrame(rows)

def parse_constraints_table(df: pd.DataFrame) -> Tuple[Dict, Dict, Dict, Dict, Dict]:
    """制約テーブルをパース"""
    crop_mins = {}  # min_ha
    crop_caps = {}  # cap_ha
    min_gap = {}
    min_f = {}
    max_f = {}

    for _, row in df.iterrows():
        crop = str(row['crop']).strip()
        if not crop:
            continue

        # min_ha
        # min_ha (0または空欄は無制限=下限なし)
        min_ha = row.get('min_ha', '')
        if pd.notna(min_ha) and str(min_ha).strip() != '':
            try:
                val = float(min_ha)
                crop_mins[crop] = val if val > 0 else None  # 0は無制限
            except:
                crop_mins[crop] = None
        else:
            crop_mins[crop] = None

        # cap_ha (0または空欄は無制限)
        cap = row.get('cap_ha', '')
        if pd.notna(cap) and str(cap).strip() != '':
            try:
                val = float(cap)
                crop_caps[crop] = val if val > 0 else None  # 0は無制限
            except:
                crop_caps[crop] = None
        else:
            crop_caps[crop] = None

        # min_gap_years
        gap = row.get('min_gap_years', 0)
        try:
            min_gap[crop] = int(gap) if pd.notna(gap) and str(gap).strip() != '' else 0
        except:
            min_gap[crop] = 0

        # min_fields
        minf = row.get('min_fields', 0)
        try:
            min_f[crop] = int(minf) if pd.notna(minf) and str(minf).strip() != '' else 0
        except:
            min_f[crop] = 0

        # max_fields (0は無制限として扱う)
        maxf = row.get('max_fields', '')
        if pd.notna(maxf) and str(maxf).strip() != '':
            try:
                val = int(maxf)
                max_f[crop] = val if val > 0 else None  # 0は無制限
            except:
                max_f[crop] = None
        else:
            max_f[crop] = None

    return crop_mins, crop_caps, min_gap, min_f, max_f

def parse_forbidden_transitions(text: str) -> Set[Tuple[str, str]]:
    """追加禁止遷移をパース (例: "秋小麦->春小麦, 大豆->てんさい")"""
    transitions = set()
    if not text.strip():
        return transitions
    
    for item in text.split(','):
        item = item.strip()
        if '->' in item:
            parts = item.split('->')
            if len(parts) == 2:
                from_crop = parts[0].strip()
                to_crop = parts[1].strip()
                if from_crop and to_crop:
                    transitions.add((from_crop, to_crop))
    
    return transitions

def parse_preferred_transitions(text: str) -> Dict[Tuple[str, str], float]:
    """優先遷移をパース (例: "てんさい->大豆:10, デントコーン->秋小麦:8")"""
    transitions = {}
    if not text.strip():
        return transitions
    
    for item in text.split(','):
        item = item.strip()
        if '->' in item and ':' in item:
            try:
                trans_part, weight_part = item.rsplit(':', 1)
                parts = trans_part.split('->')
                if len(parts) == 2:
                    from_crop = parts[0].strip()
                    to_crop = parts[1].strip()
                    weight = float(weight_part.strip())
                    if from_crop and to_crop:
                        transitions[(from_crop, to_crop)] = weight
            except:
                continue
    
    return transitions

# =============================================================================
# 最適化アルゴリズム
# =============================================================================

class RotationPlannerHeuristic:
    """輪作計画最適化クラス（ヒューリスティック版）"""
    
    def __init__(self, fields: List[Field], past_years: List[str], 
                 future_years: List[str], crops: List[str], constraints: Constraints):
        self.fields = fields
        self.past_years = past_years
        self.future_years = future_years
        self.all_years = past_years + future_years
        self.crops = crops
        self.constraints = constraints
        self.errors = []
    
    def get_last_n_crops(self, field_idx: int, year: str, n: int, plan: Dict) -> List[str]:
        """指定年から過去n年の作付を取得"""
        year_idx = self.all_years.index(year)
        crops_list = []
        for i in range(1, n + 1):
            if year_idx - i >= 0:
                prev_year = self.all_years[year_idx - i]
                if prev_year in self.past_years:
                    crops_list.append(self.fields[field_idx].history.get(prev_year, UNKNOWN_MARKER))
                else:
                    crops_list.append(plan.get((field_idx, prev_year), UNKNOWN_MARKER))
        return crops_list
    
    def check_gap_constraint(self, field_idx: int, year: str, crop: str, plan: Dict) -> bool:
        """間隔制約をチェック"""
        min_gap = self.constraints.min_gap_years.get(crop, 0)
        if min_gap <= 0:
            return True
        
        past_crops = self.get_last_n_crops(field_idx, year, min_gap, plan)
        
        for pc in past_crops:
            if pc == crop:
                return False
            if pc == UNKNOWN_MARKER and self.constraints.unknown_mode == "safe":
                # 安全側: 不明があれば間隔制約のある作物は避ける
                return False
        
        return True
    
    def check_transition_constraint(self, field_idx: int, year: str, crop: str, plan: Dict) -> bool:
        """遷移制約をチェック（連作禁止含む）"""
        prev_crops = self.get_last_n_crops(field_idx, year, 1, plan)
        if not prev_crops:
            return True
        
        prev_crop = prev_crops[0]
        
        if prev_crop == UNKNOWN_MARKER:
            if self.constraints.unknown_mode == "safe":
                # 安全側: 禁止遷移のto側になる作物は避ける
                for (from_c, to_c) in self.constraints.forbidden_transitions:
                    if to_c == crop:
                        return False
            return True
        
        # 連作禁止
        if prev_crop == crop:
            return False
        
        # 禁止遷移
        if (prev_crop, crop) in self.constraints.forbidden_transitions:
            return False
        
        return True
    
    def get_valid_crops(self, field_idx: int, year: str, plan: Dict) -> List[str]:
        """有効な作物リストを取得"""
        valid = []
        for crop in self.crops:
            if self.check_gap_constraint(field_idx, year, crop, plan):
                if self.check_transition_constraint(field_idx, year, crop, plan):
                    valid.append(crop)
        return valid
    
    def calculate_year_stats(self, year: str, plan: Dict) -> Dict[str, Tuple[float, int]]:
        """年の作物統計を計算: {crop: (total_ha, field_count)}"""
        stats = {c: (0.0, 0) for c in self.crops}
        for i, f in enumerate(self.fields):
            if year in self.past_years:
                crop = f.history.get(year, UNKNOWN_MARKER)
            else:
                crop = plan.get((i, year), None)
            
            if crop and crop != UNKNOWN_MARKER and crop in stats:
                ha, cnt = stats[crop]
                stats[crop] = (ha + f.area_ha, cnt + 1)
        
        return stats
    
    def check_cap_constraint(self, year: str, crop: str, plan: Dict,
                             additional_ha: float = 0) -> bool:
        """面積上限をチェック (0は無制限)"""
        cap = self.constraints.crop_caps.get(crop)
        if cap is None or cap == 0:
            return True

        stats = self.calculate_year_stats(year, plan)
        current_ha = stats.get(crop, (0, 0))[0]
        return current_ha + additional_ha <= cap
    
    def check_field_count_constraint(self, year: str, crop: str, plan: Dict,
                                     adding: bool = False) -> Tuple[bool, str]:
        """ほ場数制約をチェック"""
        min_f = self.constraints.min_fields.get(crop, 0)
        max_f = self.constraints.max_fields.get(crop)
        
        stats = self.calculate_year_stats(year, plan)
        current_count = stats.get(crop, (0, 0))[1]
        
        if adding:
            new_count = current_count + 1
        else:
            new_count = current_count
        
        if max_f is not None and new_count > max_f:
            return False, f"{crop}のほ場数が上限({max_f})を超えます"
        
        return True, ""
    
    def calculate_transition_score(self, field_idx: int, year: str, crop: str, plan: Dict) -> float:
        """遷移スコアを計算"""
        prev_crops = self.get_last_n_crops(field_idx, year, 1, plan)
        if not prev_crops or prev_crops[0] == UNKNOWN_MARKER:
            return 0
        
        prev_crop = prev_crops[0]
        return self.constraints.preferred_transitions.get((prev_crop, crop), 0)
    
    def calculate_gap_bonus(self, field_idx: int, year: str, crop: str, plan: Dict) -> float:
        """間隔ボーナス（てんさい/馬鈴薯など）"""
        min_gap = self.constraints.min_gap_years.get(crop, 0)
        if min_gap <= 0:
            return 0
        
        # より長く空けるほどボーナス
        year_idx = self.all_years.index(year)
        actual_gap = 0
        for i in range(1, len(self.all_years)):
            if year_idx - i < 0:
                break
            prev_year = self.all_years[year_idx - i]
            if prev_year in self.past_years:
                prev_crop = self.fields[field_idx].history.get(prev_year, UNKNOWN_MARKER)
            else:
                prev_crop = plan.get((field_idx, prev_year), None)
            
            if prev_crop == crop:
                break
            actual_gap += 1
        
        # 最小間隔を超えた分だけボーナス
        return max(0, actual_gap - min_gap) * 0.5
    
    def evaluate_solution(self, plan: Dict) -> Tuple[float, List[str]]:
        """解の評価"""
        score = 0.0
        violations = []
        
        # 各年の統計
        year_stats = {}
        for year in self.future_years:
            year_stats[year] = self.calculate_year_stats(year, plan)
        
        # 1. 主作物の面積変動を評価
        for crop in self.constraints.main_crops:
            areas = [year_stats[y].get(crop, (0, 0))[0] for y in self.future_years]
            if areas:
                variance = np.var(areas)
                score -= variance * 10  # 変動が大きいほどペナルティ
        
        # 2. 優先遷移スコア
        for i, f in enumerate(self.fields):
            for year in self.future_years:
                crop = plan.get((i, year))
                if crop:
                    score += self.calculate_transition_score(i, year, crop, plan)
                    score += self.calculate_gap_bonus(i, year, crop, plan)
        
        # 3. 制約違反チェック
        for year in self.future_years:
            stats = year_stats[year]
            
            for crop in self.crops:
                # 面積上限 (0は無制限)
                cap = self.constraints.crop_caps.get(crop)
                if cap is not None and cap > 0:
                    ha = stats.get(crop, (0, 0))[0]
                    if ha > cap:
                        violations.append(f"{year}: {crop}の面積({ha:.2f}ha)が上限({cap}ha)を超過")
                        score -= 100
                
                # ほ場数制約
                min_f = self.constraints.min_fields.get(crop, 0)
                max_f = self.constraints.max_fields.get(crop)
                cnt = stats.get(crop, (0, 0))[1]
                
                if cnt < min_f:
                    violations.append(f"{year}: {crop}のほ場数({cnt})が下限({min_f})未満")
                    score -= 50
                
                if max_f is not None and cnt > max_f:
                    violations.append(f"{year}: {crop}のほ場数({cnt})が上限({max_f})超過")
                    score -= 50
        
        return score, violations
    
    def generate_initial_solution(self) -> Dict[Tuple[int, str], str]:
        """初期解を生成"""
        plan = {}
        
        for year in self.future_years:
            # ほ場をシャッフル（ランダム性）
            field_indices = list(range(len(self.fields)))
            random.shuffle(field_indices)
            
            for field_idx in field_indices:
                valid_crops = self.get_valid_crops(field_idx, year, plan)
                
                if not valid_crops:
                    # 有効な作物がない場合、制約を緩和して選択
                    valid_crops = self.crops.copy()
                    self.errors.append(f"警告: ほ場{self.fields[field_idx].field_id}の{year}で制約を満たす作物がありません")
                
                # スコアで評価して選択
                best_crop = None
                best_score = float('-inf')
                
                for crop in valid_crops:
                    # 面積上限チェック
                    if not self.check_cap_constraint(year, crop, plan, self.fields[field_idx].area_ha):
                        continue
                    
                    # ほ場数上限チェック
                    ok, _ = self.check_field_count_constraint(year, crop, plan, adding=True)
                    if not ok:
                        continue
                    
                    score = self.calculate_transition_score(field_idx, year, crop, plan)
                    score += self.calculate_gap_bonus(field_idx, year, crop, plan)
                    score += random.random() * 0.1  # ランダム性を追加
                    
                    if score > best_score:
                        best_score = score
                        best_crop = crop
                
                if best_crop is None:
                    # それでも見つからない場合
                    best_crop = random.choice(valid_crops) if valid_crops else self.crops[0]
                
                plan[(field_idx, year)] = best_crop
        
        return plan
    
    def local_search(self, plan: Dict, max_iterations: int = 1000) -> Dict:
        """局所探索で解を改善"""
        current_plan = deepcopy(plan)
        current_score, _ = self.evaluate_solution(current_plan)
        
        for _ in range(max_iterations):
            # ランダムに変更を試みる
            field_idx = random.randint(0, len(self.fields) - 1)
            year = random.choice(self.future_years)
            
            valid_crops = self.get_valid_crops(field_idx, year, current_plan)
            if not valid_crops:
                continue
            
            old_crop = current_plan.get((field_idx, year))
            new_crop = random.choice(valid_crops)
            
            if new_crop == old_crop:
                continue
            
            # 一時的に変更
            current_plan[(field_idx, year)] = new_crop
            
            # 面積・ほ場数制約チェック
            if not self.check_cap_constraint(year, new_crop, current_plan):
                current_plan[(field_idx, year)] = old_crop
                continue
            
            ok, _ = self.check_field_count_constraint(year, new_crop, current_plan)
            if not ok:
                current_plan[(field_idx, year)] = old_crop
                continue
            
            # スコア評価
            new_score, _ = self.evaluate_solution(current_plan)
            
            if new_score > current_score:
                current_score = new_score
            else:
                # 元に戻す
                current_plan[(field_idx, year)] = old_crop
        
        return current_plan
    
    def ensure_min_fields(self, plan: Dict) -> Dict:
        """最小ほ場数制約を満たすように調整"""
        for year in self.future_years:
            stats = self.calculate_year_stats(year, plan)
            
            for crop in self.crops:
                min_f = self.constraints.min_fields.get(crop, 0)
                if min_f <= 0:
                    continue
                
                current_count = stats.get(crop, (0, 0))[1]
                
                while current_count < min_f:
                    # 変更可能なほ場を探す
                    changed = False
                    for i, f in enumerate(self.fields):
                        current_crop = plan.get((i, year))
                        if current_crop == crop:
                            continue
                        
                        # 制約チェック
                        if not self.check_gap_constraint(i, year, crop, plan):
                            continue
                        if not self.check_transition_constraint(i, year, crop, plan):
                            continue
                        
                        # 変更元の作物のmin_fields違反にならないか
                        if current_crop:
                            other_min = self.constraints.min_fields.get(current_crop, 0)
                            other_stats = self.calculate_year_stats(year, plan)
                            if other_stats.get(current_crop, (0, 0))[1] <= other_min:
                                continue
                        
                        plan[(i, year)] = crop
                        changed = True
                        current_count += 1
                        break
                    
                    if not changed:
                        self.errors.append(f"警告: {year}の{crop}最小ほ場数({min_f})を満たせません")
                        break
        
        return plan
    
    def solve(self) -> Tuple[Dict, float, List[str]]:
        """最適化を実行"""
        self.errors = []
        
        # 初期解生成
        plan = self.generate_initial_solution()
        
        # 局所探索
        plan = self.local_search(plan, max_iterations=2000)
        
        # 最小ほ場数調整
        plan = self.ensure_min_fields(plan)
        
        # 最終評価
        score, violations = self.evaluate_solution(plan)
        
        all_errors = self.errors + violations
        
        return plan, score, all_errors


class RotationPlannerORTools:
    """輪作計画最適化クラス（OR-Tools CP-SAT版）"""

    def __init__(self, fields: List[Field], past_years: List[str],
                 future_years: List[str], crops: List[str], constraints: Constraints):
        self.fields = fields
        self.past_years = past_years
        self.future_years = future_years
        self.all_years = past_years + future_years
        self.crops = crops
        self.constraints = constraints
        self.num_fields = len(fields)
        self.num_crops = len(crops)
        self.num_future_years = len(future_years)
        self.crop_to_idx = {c: i for i, c in enumerate(crops)}
        self.idx_to_crop = {i: c for i, c in enumerate(crops)}
        # フォールバック用ヒューリスティック版
        self.heuristic = RotationPlannerHeuristic(fields, past_years, future_years, crops, constraints)

    def get_past_crop_idx(self, field_idx: int, year_offset: int) -> Optional[int]:
        """過去の作付を取得（year_offset: 1=前年, 2=前々年, ...）"""
        if not self.past_years:
            return None
        target_year_idx = len(self.past_years) - year_offset
        if target_year_idx < 0:
            return None
        target_year = self.past_years[target_year_idx]
        crop = self.fields[field_idx].history.get(target_year, UNKNOWN_MARKER)
        if crop == UNKNOWN_MARKER:
            return None
        return self.crop_to_idx.get(crop)

    def solve(self, timeout_seconds: int = 10, high_precision: bool = False,
              district_grouping: bool = True) -> Tuple[Dict, float, List[str]]:
        """OR-Toolsで最適化を実行"""
        model = cp_model.CpModel()

        # 決定変数: x[f, y, c] = 1 ならほ場fの将来年yに作物cを割り当て
        x = {}
        for f in range(self.num_fields):
            for y in range(self.num_future_years):
                for c in range(self.num_crops):
                    x[f, y, c] = model.NewBoolVar(f'x_{f}_{y}_{c}')

        # 制約1: 各ほ場・各年に1作物のみ
        for f in range(self.num_fields):
            for y in range(self.num_future_years):
                model.Add(sum(x[f, y, c] for c in range(self.num_crops)) == 1)

        # 制約2: 連作禁止（将来年同士）
        for f in range(self.num_fields):
            for y in range(self.num_future_years - 1):
                for c in range(self.num_crops):
                    model.Add(x[f, y, c] + x[f, y + 1, c] <= 1)

        # 制約3: 連作禁止（過去→将来1年目）
        for f in range(self.num_fields):
            last_crop_idx = self.get_past_crop_idx(f, 1)
            if last_crop_idx is not None:
                model.Add(x[f, 0, last_crop_idx] == 0)

        # 制約4: 禁止遷移（将来年同士）
        for (from_crop, to_crop) in self.constraints.forbidden_transitions:
            from_idx = self.crop_to_idx.get(from_crop)
            to_idx = self.crop_to_idx.get(to_crop)
            if from_idx is None or to_idx is None:
                continue
            for f in range(self.num_fields):
                for y in range(self.num_future_years - 1):
                    model.Add(x[f, y, from_idx] + x[f, y + 1, to_idx] <= 1)

        # 制約5: 禁止遷移（過去→将来1年目）
        for f in range(self.num_fields):
            last_crop_idx = self.get_past_crop_idx(f, 1)
            if last_crop_idx is not None:
                last_crop = self.idx_to_crop[last_crop_idx]
                for (from_crop, to_crop) in self.constraints.forbidden_transitions:
                    if from_crop == last_crop:
                        to_idx = self.crop_to_idx.get(to_crop)
                        if to_idx is not None:
                            model.Add(x[f, 0, to_idx] == 0)

        # 制約6: 間隔制約（てんさい・馬鈴薯など）
        for c in range(self.num_crops):
            crop_name = self.idx_to_crop[c]
            min_gap = self.constraints.min_gap_years.get(crop_name, 0)
            if min_gap <= 0:
                continue

            for f in range(self.num_fields):
                # 過去履歴をチェック
                for offset in range(1, min_gap + 1):
                    past_idx = self.get_past_crop_idx(f, offset)
                    if past_idx == c:
                        # 過去にこの作物があった場合、将来の最初の数年は禁止
                        for y in range(min(min_gap - offset + 1, self.num_future_years)):
                            model.Add(x[f, y, c] == 0)
                        break

                # 将来年同士の間隔制約
                for y1 in range(self.num_future_years):
                    for y2 in range(y1 + 1, min(y1 + min_gap + 1, self.num_future_years)):
                        model.Add(x[f, y1, c] + x[f, y2, c] <= 1)

        # ソフト制約用の違反変数
        # 面積上限超過（単位: 面積×100）
        cap_over = {}
        max_total_area = int(sum(f.area_ha for f in self.fields) * 100) + 1

        for c in range(self.num_crops):
            crop_name = self.idx_to_crop[c]
            cap = self.constraints.crop_caps.get(crop_name)
            if cap is not None and cap > 0:  # 0は無制限
                cap_int = int(cap * 100)
                for y in range(self.num_future_years):
                    cap_over[c, y] = model.NewIntVar(0, max_total_area, f'cap_over_{c}_{y}')
                    area_sum = sum(int(self.fields[f].area_ha * 100) * x[f, y, c]
                                   for f in range(self.num_fields))
                    # area_sum - cap_int <= cap_over → cap_over >= area_sum - cap_int
                    model.Add(cap_over[c, y] >= area_sum - cap_int)

        # 面積下限不足（単位: 面積×100）
        cap_under = {}
        for c in range(self.num_crops):
            crop_name = self.idx_to_crop[c]
            min_ha = self.constraints.crop_mins.get(crop_name)
            if min_ha is not None and min_ha > 0:
                min_int = int(min_ha * 100)
                for y in range(self.num_future_years):
                    cap_under[c, y] = model.NewIntVar(0, max_total_area, f'cap_under_{c}_{y}')
                    area_sum = sum(int(self.fields[f].area_ha * 100) * x[f, y, c]
                                   for f in range(self.num_fields))
                    # min_int - area_sum <= cap_under → cap_under >= min_int - area_sum
                    model.Add(cap_under[c, y] >= min_int - area_sum)

        # ほ場数超過/不足
        field_over = {}
        field_under = {}

        for c in range(self.num_crops):
            crop_name = self.idx_to_crop[c]
            min_f = self.constraints.min_fields.get(crop_name, 0)
            max_f = self.constraints.max_fields.get(crop_name)

            for y in range(self.num_future_years):
                count = sum(x[f, y, c] for f in range(self.num_fields))

                if min_f > 0:
                    field_under[c, y] = model.NewIntVar(0, self.num_fields, f'field_under_{c}_{y}')
                    # min_f - count <= field_under → field_under >= min_f - count
                    model.Add(field_under[c, y] >= min_f - count)

                if max_f is not None:
                    field_over[c, y] = model.NewIntVar(0, self.num_fields, f'field_over_{c}_{y}')
                    # count - max_f <= field_over → field_over >= count - max_f
                    model.Add(field_over[c, y] >= count - max_f)

        # 制約9: 馬鈴薯・てんさい禁止ほ場制約
        beet_idx = self.crop_to_idx.get("てんさい")
        potato_idx = self.crop_to_idx.get("馬鈴薯")
        for f_idx, fld in enumerate(self.fields):
            if fld.beet_forbidden:
                for y in range(self.num_future_years):
                    if beet_idx is not None:
                        model.Add(x[f_idx, y, beet_idx] == 0)
                    if potato_idx is not None:
                        model.Add(x[f_idx, y, potato_idx] == 0)

        # 目的関数: 各作物の年次面積変動を最小化
        # area_cy[c, y] = 作物cの年yの合計面積（×100の整数）
        area_cy = {}
        for c in range(self.num_crops):
            for y in range(self.num_future_years):
                area_cy[c, y] = sum(int(self.fields[f].area_ha * 100) * x[f, y, c]
                                    for f in range(self.num_fields))

        # 差分の絶対値を表す補助変数
        max_area = int(sum(f.area_ha for f in self.fields) * 100) + 1
        diffs = []
        for c in range(self.num_crops):
            for y in range(self.num_future_years - 1):
                diff = model.NewIntVar(0, max_area, f'diff_{c}_{y}')
                model.Add(diff >= area_cy[c, y + 1] - area_cy[c, y])
                model.Add(diff >= area_cy[c, y] - area_cy[c, y + 1])
                diffs.append(diff)

        # 各作物の面積範囲（max-min）を最小化する追加目的
        range_penalties = []
        for c in range(self.num_crops):
            area_max = model.NewIntVar(0, max_area, f'area_max_{c}')
            area_min = model.NewIntVar(0, max_area, f'area_min_{c}')
            for y in range(self.num_future_years):
                model.Add(area_max >= area_cy[c, y])
                model.Add(area_min <= area_cy[c, y])
            range_penalty = model.NewIntVar(0, max_area, f'range_{c}')
            model.Add(range_penalty == area_max - area_min)
            range_penalties.append(range_penalty)

        # 目的関数: ソフト制約違反ペナルティ + 年次差分 + 範囲ペナルティ
        # ペナルティ重み（ソフト制約違反 >> 最適化目標）
        PENALTY_CAP_OVER = 100000  # 面積超過（×100単位）
        PENALTY_CAP_UNDER = 500000  # 面積下限不足（×100単位）
        PENALTY_FIELD_OVER = 500000  # ほ場数超過
        PENALTY_FIELD_UNDER = 500000  # ほ場数不足

        objective = []

        # ソフト制約違反ペナルティ
        for key, var in cap_over.items():
            objective.append(PENALTY_CAP_OVER * var)
        for key, var in cap_under.items():
            objective.append(PENALTY_CAP_UNDER * var)
        for key, var in field_over.items():
            objective.append(PENALTY_FIELD_OVER * var)
        for key, var in field_under.items():
            objective.append(PENALTY_FIELD_UNDER * var)

        # 最適化目標（重み小）
        for diff in diffs:
            objective.append(diff)
        for rp in range_penalties:
            objective.append(2 * rp)

        # 地区まとめボーナス（district_grouping が True の場合のみ）
        if district_grouping:
            # 地区リストを取得
            districts = list(set(f.district for f in self.fields if f.district))
            if districts:
                district_fields = {d: [i for i, f in enumerate(self.fields) if f.district == d]
                                   for d in districts}

                BONUS_DISTRICT_GROUP = -50  # 負の値（最小化なので）

                for d_idx, district in enumerate(districts):
                    field_indices = district_fields[district]
                    if len(field_indices) < 2:
                        continue  # 1ほ場だけの地区はスキップ

                    for y in range(self.num_future_years):
                        for c in range(self.num_crops):
                            # 地区内で同じ作物を作るほ場数
                            count_var = model.NewIntVar(0, len(field_indices),
                                f'dcc_{d_idx}_{y}_{c}')
                            model.Add(count_var == sum(x[f, y, c] for f in field_indices))

                            # 2ほ場以上ならボーナス
                            is_grouped = model.NewBoolVar(f'grouped_{d_idx}_{y}_{c}')
                            model.Add(count_var >= 2).OnlyEnforceIf(is_grouped)
                            model.Add(count_var < 2).OnlyEnforceIf(is_grouped.Not())
                            objective.append(BONUS_DISTRICT_GROUP * is_grouped)

        model.Minimize(sum(objective))

        # ソルバー実行
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = timeout_seconds
        if high_precision:
            solver.parameters.num_search_workers = 4  # 並列探索
            solver.parameters.linearization_level = 2  # より詳細な線形緩和
        status = solver.Solve(model)

        if status in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
            # 解を取得
            plan = {}
            for f in range(self.num_fields):
                for y in range(self.num_future_years):
                    year_name = self.future_years[y]
                    for c in range(self.num_crops):
                        if solver.Value(x[f, y, c]) == 1:
                            plan[(f, year_name)] = self.idx_to_crop[c]
                            break

            # スコア計算（変動の合計、小さいほど良い）
            total_diff = solver.ObjectiveValue() / 100.0  # 元の単位に戻す
            errors = []
            if status == cp_model.FEASIBLE:
                errors.append("注意: 最適解ではなく実行可能解です")

            # ソフト制約違反の警告を出力
            for (c, y), var in cap_over.items():
                over_val = solver.Value(var)
                if over_val > 0:
                    crop_name = self.idx_to_crop[c]
                    year_name = self.future_years[y]
                    over_ha = over_val / 100.0
                    errors.append(f"⚠️ 警告: {year_name}の{crop_name}が面積上限を{over_ha:.2f}ha超過")

            for (c, y), var in cap_under.items():
                under_val = solver.Value(var)
                if under_val > 0:
                    crop_name = self.idx_to_crop[c]
                    year_name = self.future_years[y]
                    under_ha = under_val / 100.0
                    errors.append(f"⚠️ 警告: {year_name}の{crop_name}が面積下限を{under_ha:.2f}ha不足")

            for (c, y), var in field_over.items():
                over_val = solver.Value(var)
                if over_val > 0:
                    crop_name = self.idx_to_crop[c]
                    year_name = self.future_years[y]
                    errors.append(f"⚠️ 警告: {year_name}の{crop_name}がほ場数上限を{over_val}超過")

            for (c, y), var in field_under.items():
                under_val = solver.Value(var)
                if under_val > 0:
                    crop_name = self.idx_to_crop[c]
                    year_name = self.future_years[y]
                    errors.append(f"⚠️ 警告: {year_name}の{crop_name}がほ場数下限を{under_val}不足")

            return plan, -total_diff, errors  # スコアは負値（大きいほど良い）
        else:
            # フォールバック: ヒューリスティック版を使用
            return self.heuristic.solve()


# =============================================================================
# 結果生成
# =============================================================================

def generate_result_tables(fields: List[Field], past_years: List[str],
                          future_years: List[str], plan: Dict, crops: List[str]):
    """結果テーブルを生成"""
    all_years = past_years + future_years

    # 今年（将来年の最初）を特定
    current_year = future_years[0] if future_years else None

    # 列名マッピング（今年に📍マーカーを付ける）
    def year_col_name(year):
        if year == current_year:
            return f"📍{year}"
        return year

    # 1. ほ場×年の表
    rows = []
    for i, f in enumerate(fields):
        row = {
            "ほ場ID": f.field_id,
            "地区": f.district,
            "ほ場名": f.name,
            "面積(ha)": f"{f.area_ha:.2f}",
            "禁止": "🚫" if f.beet_forbidden else ""
        }
        for year in all_years:
            col_name = year_col_name(year)
            if year in past_years:
                row[col_name] = f.history.get(year, "")
                if row[col_name] == UNKNOWN_MARKER:
                    row[col_name] = "(不明)"
            else:
                row[col_name] = plan.get((i, year), "")
        rows.append(row)

    field_df = pd.DataFrame(rows)

    # 2. 年別面積合計表
    summary_rows = []
    for year in all_years:
        row_year = year_col_name(year)
        row = {"年": row_year}
        for crop in crops:
            total_ha = 0.0
            for i, f in enumerate(fields):
                if year in past_years:
                    c = f.history.get(year, UNKNOWN_MARKER)
                else:
                    c = plan.get((i, year), "")
                if c == crop:
                    total_ha += f.area_ha
            row[crop] = f"{total_ha:.2f}" if total_ha > 0 else ""
        summary_rows.append(row)

    summary_df = pd.DataFrame(summary_rows)

    return field_df, summary_df

def generate_csv_content(field_df: pd.DataFrame) -> str:
    """CSVコンテンツを生成"""
    return field_df.to_csv(index=False)


# =============================================================================
# 感度分析（ボトルネック特定）
# =============================================================================

def run_sensitivity_analysis(fields: List[Field], past_years: List[str],
                             future_years: List[str], crops: List[str],
                             base_constraints: Constraints, base_score: float,
                             timeout_seconds: int = 1, max_tests: int = 5) -> List[str]:
    """
    各制約を少し緩めて再計算し、スコア改善度を比較。
    ボトルネックとなっている制約を特定する。
    高速化のため、制約がかかっている項目のみテスト。
    """
    results = []

    # 試行する緩和パターン（制約がかかっているもののみ）
    relaxations = []

    # cap_ha を +2ha 緩和（制約があるもののみ）
    for crop in crops:
        cap = base_constraints.crop_caps.get(crop)
        if cap is not None and cap > 0:
            relaxations.append({
                'type': 'cap_ha',
                'crop': crop,
                'original': cap,
                'relaxed': cap + 2,
                'description': f"{crop}のcap_ha: {cap}ha → {cap+2}ha"
            })

    # max_fields を +1 緩和（制約があるもののみ）
    for crop in crops:
        max_f = base_constraints.max_fields.get(crop)
        if max_f is not None and max_f > 0:
            relaxations.append({
                'type': 'max_fields',
                'crop': crop,
                'original': max_f,
                'relaxed': max_f + 1,
                'description': f"{crop}のmax_fields: {max_f} → {max_f+1}"
            })

    # min_gap_years を -1 緩和（制約があるもののみ）
    for crop in crops:
        gap = base_constraints.min_gap_years.get(crop, 0)
        if gap > 1:  # 2年以上のみ
            relaxations.append({
                'type': 'min_gap_years',
                'crop': crop,
                'original': gap,
                'relaxed': gap - 1,
                'description': f"{crop}のmin_gap_years: {gap}年 → {gap-1}年"
            })

    # min_ha を -1ha 緩和（制約があるもののみ）
    for crop in crops:
        min_ha = base_constraints.crop_mins.get(crop)
        if min_ha is not None and min_ha > 0:
            new_val = max(0, min_ha - 1)
            relaxations.append({
                'type': 'min_ha',
                'crop': crop,
                'original': min_ha,
                'relaxed': new_val,
                'description': f"{crop}のmin_ha: {min_ha}ha → {new_val}ha"
            })

    # テスト数を制限
    relaxations = relaxations[:max_tests]

    if not relaxations:
        return ["📊 ボトルネック分析: 緩和可能な制約がありません"]

    improvements = []

    for relax in relaxations:
        # 制約をコピーして緩和
        new_constraints = Constraints(
            crop_mins=dict(base_constraints.crop_mins),
            crop_caps=dict(base_constraints.crop_caps),
            min_gap_years=dict(base_constraints.min_gap_years),
            min_fields=dict(base_constraints.min_fields),
            max_fields=dict(base_constraints.max_fields),
            forbidden_transitions=set(base_constraints.forbidden_transitions),
            preferred_transitions=dict(base_constraints.preferred_transitions),
            main_crops=list(base_constraints.main_crops),
            unknown_mode=base_constraints.unknown_mode
        )

        # 該当制約を緩和
        crop = relax['crop']
        if relax['type'] == 'cap_ha':
            new_constraints.crop_caps[crop] = relax['relaxed']
        elif relax['type'] == 'min_ha':
            new_constraints.crop_mins[crop] = relax['relaxed'] if relax['relaxed'] > 0 else None
        elif relax['type'] == 'max_fields':
            new_constraints.max_fields[crop] = relax['relaxed']
        elif relax['type'] == 'min_fields':
            new_constraints.min_fields[crop] = relax['relaxed']
        elif relax['type'] == 'min_gap_years':
            new_constraints.min_gap_years[crop] = relax['relaxed']

        # 再計算（短いタイムアウトで高速化）
        try:
            planner = RotationPlannerORTools(fields, past_years, future_years, crops, new_constraints)
            _, new_score, _ = planner.solve(timeout_seconds=timeout_seconds, high_precision=False)

            improvement = new_score - base_score
            if improvement > 0.1:  # 0.1以上改善したもののみ
                improvements.append({
                    'description': relax['description'],
                    'improvement': improvement,
                    'new_score': new_score
                })
        except Exception:
            pass  # エラーは無視

    # 改善度順にソート
    improvements.sort(key=lambda x: x['improvement'], reverse=True)

    # 結果メッセージ生成
    if improvements:
        results.append("📊 **ボトルネック分析結果**（制約緩和による改善度）:")
        for i, imp in enumerate(improvements[:5]):  # 上位5件
            pct = (imp['improvement'] / abs(base_score) * 100) if base_score != 0 else 0
            results.append(f"  {i+1}. {imp['description']} → スコア +{imp['improvement']:.1f} ({pct:.1f}%改善)")
    else:
        results.append("📊 ボトルネック分析: 制約緩和による大きな改善は見つかりませんでした")

    return results


# =============================================================================
# Gradio UI
# =============================================================================

def update_constraints_table(crop_text: str, current_table: pd.DataFrame) -> pd.DataFrame:
    """作物マスター変更時に制約テーブルを更新"""
    crops = [c.strip() for c in crop_text.strip().split('\n') if c.strip()]

    if current_table is None or current_table.empty:
        return build_constraints_table(crops)

    # 既存の値を保持
    existing = {}
    for _, row in current_table.iterrows():
        crop = str(row.get('crop', '')).strip()
        if crop:
            existing[crop] = {
                'min_ha': row.get('min_ha', ''),
                'cap_ha': row.get('cap_ha', ''),
                'min_gap_years': row.get('min_gap_years', 0),
                'min_fields': row.get('min_fields', 0),
                'max_fields': row.get('max_fields', '')
            }

    # 新しいテーブルを構築
    rows = []
    for crop in crops:
        if crop in existing:
            rows.append({
                "crop": crop,
                "min_ha": existing[crop]['min_ha'],
                "cap_ha": existing[crop]['cap_ha'],
                "min_gap_years": existing[crop]['min_gap_years'],
                "min_fields": existing[crop]['min_fields'],
                "max_fields": existing[crop]['max_fields']
            })
        elif crop in DEFAULT_CONSTRAINTS:
            c = DEFAULT_CONSTRAINTS[crop]
            rows.append({
                "crop": crop,
                "min_ha": c.get("min_ha", "") if c.get("min_ha") is not None else "",
                "cap_ha": c["cap_ha"] if c["cap_ha"] is not None else "",
                "min_gap_years": c["min_gap_years"],
                "min_fields": c["min_fields"],
                "max_fields": c["max_fields"] if c["max_fields"] is not None else ""
            })
        else:
            rows.append({
                "crop": crop,
                "min_ha": "",
                "cap_ha": 10,
                "min_gap_years": 0,
                "min_fields": 0,
                "max_fields": ""
            })

    return pd.DataFrame(rows)

def update_constraints_from_csv(file) -> pd.DataFrame:
    """制約CSVから制約テーブルを更新"""
    if file is None:
        return gr.update()
    try:
        df = load_constraints_csv(file.name if hasattr(file, 'name') else file)
        if df.empty:
            return gr.update()
        return df
    except Exception as e:
        return gr.update()

def run_optimization(csv_file, area_unit, n_years, crop_text, constraints_table,
                    forbidden_text, preferred_text, main_crops_text, unknown_mode,
                    tensai_required, precision_mode, infer_unknown, district_grouping):
    """最適化を実行"""

    if csv_file is None:
        return None, None, None, "エラー: CSVファイルをアップロードしてください"

    # CSV読み込み
    fields, past_years, error = load_csv(csv_file.name, area_unit)
    if error:
        return None, None, None, error

    if not fields:
        return None, None, None, "エラー: ほ場データがありません"

    # 作物リスト
    crops = [c.strip() for c in crop_text.strip().split('\n') if c.strip()]
    if not crops:
        return None, None, None, "エラー: 作物マスターが空です"

    # 将来年
    future_years = generate_future_years(past_years, int(n_years))

    # 制約パース
    crop_mins, crop_caps, min_gap, min_f, max_f = parse_constraints_table(constraints_table)

    # てんさい必須チェックボックスがONの場合、min_fieldsを上書き
    if tensai_required:
        min_f["てんさい"] = 1

    # 禁止遷移
    forbidden = set(FIXED_FORBIDDEN_TRANSITIONS)
    forbidden.update(parse_forbidden_transitions(forbidden_text))

    # 空欄を推論で埋める
    if infer_unknown:
        fields = infer_unknown_crops(fields, crops, forbidden)

    # 優先遷移
    preferred = parse_preferred_transitions(preferred_text)

    # 主作物
    main_crops = [c.strip() for c in main_crops_text.split(',') if c.strip()]

    # unknown_mode
    unk_mode = "safe" if "安全側" in unknown_mode else "ignore"

    constraints = Constraints(
        crop_mins=crop_mins,
        crop_caps=crop_caps,
        min_gap_years=min_gap,
        min_fields=min_f,
        max_fields=max_f,
        forbidden_transitions=forbidden,
        preferred_transitions=preferred,
        main_crops=main_crops,
        unknown_mode=unk_mode
    )
    
    # 最適化実行
    # 計算精度モード
    high_precision = "高精度" in precision_mode
    timeout = 60 if high_precision else 10

    planner = RotationPlannerORTools(fields, past_years, future_years, crops, constraints)
    plan, score, errors = planner.solve(timeout_seconds=timeout, high_precision=high_precision,
                                        district_grouping=district_grouping)
    
    # 結果生成
    field_df, summary_df = generate_result_tables(fields, past_years, future_years, plan, crops)
    
    # CSV出力
    csv_content = generate_csv_content(field_df)
    csv_path = "/tmp/rotation_plan.csv"
    with open(csv_path, 'w', encoding='utf-8-sig') as f:
        f.write(csv_content)
    
    # メッセージ
    message = f"✅ 計画生成完了 (スコア: {score:.1f})\n"
    message += f"・過去{len(past_years)}年 + 将来{len(future_years)}年の計画\n"
    message += f"・ほ場数: {len(fields)}\n"

    if errors:
        message += "\n⚠️ 警告/違反:\n"
        for e in errors[:10]:  # 最大10件
            message += f"  - {e}\n"
        if len(errors) > 10:
            message += f"  ... 他{len(errors)-10}件\n"

    # 感度分析（ボトルネック特定）
    message += "\n"
    try:
        sensitivity_results = run_sensitivity_analysis(
            fields, past_years, future_years, crops, constraints, score,
            timeout_seconds=1, max_tests=5
        )
        for line in sensitivity_results:
            message += f"{line}\n"
    except Exception as e:
        message += f"📊 ボトルネック分析: 実行できませんでした ({e})\n"

    return field_df, summary_df, csv_path, message

# アプリのパス
APP_DIR = os.path.dirname(os.path.abspath(__file__))

def create_app():
    """Gradioアプリを作成（複数農家対応版）"""

    with gr.Blocks(title="輪作計画メーカー") as app:
        # ユーザー情報State
        user_state = gr.State(None)

        # ヘッダー（ユーザー情報表示）
        with gr.Row():
            with gr.Column(scale=4):
                gr.Markdown("""
                # 🌾 輪作計画メーカー

                過去の作付データ（CSV）から、将来の輪作計画を自動生成します。
                """)
            with gr.Column(scale=1):
                user_info_display = gr.Markdown("", elem_id="user_info")
                logout_btn = gr.Button("🚪 ログアウト", link="/logout", size="sm")

        # ログイン時のユーザー情報読み込み
        def on_load(request: gr.Request):
            if request.username:
                user = get_user_info(request.username)
                if user:
                    # DBからuser_idを取得
                    db_user = UserRepository.get_user_by_username(request.username)
                    user_id = db_user.get('id') if db_user else None

                    role_label = {"admin": "管理者", "ja_staff": "JA職員", "farmer": "農家"}.get(user["role"], user["role"])
                    display_text = f"👤 **{user['display_name']}** ({role_label})"

                    # user_stateにuser_idも含める
                    user_data = {
                        **user,
                        'user_id': user_id
                    }
                    return user_data, display_text
            return None, ""

        app.load(on_load, outputs=[user_state, user_info_display])

        # =================================================================
        # DB統合: ほ場データ取得・計画保存機能
        # =================================================================

        def load_fields_from_db(user_info):
            """DBからユーザーのほ場データを取得"""
            if not user_info or not user_info.get('user_id'):
                return pd.DataFrame(), "ログインが必要です"

            user_id = user_info['user_id']
            fields = FieldRepository.get_fields(user_id)

            if not fields:
                return pd.DataFrame(), "ほ場データがありません。ほ場登録から登録してください。"

            # DataFrameに変換
            df = pd.DataFrame(fields)
            return df[['field_code', 'name', 'district', 'area_ha']], f"✅ {len(fields)}件のほ場を読み込みました"

        def load_crop_history_from_db(user_info):
            """DBからほ場の作付履歴を取得してCSV形式で返す"""
            if not user_info or not user_info.get('user_id'):
                return None, "ログインが必要です"

            user_id = user_info['user_id']
            fields = FieldRepository.get_fields(user_id)

            if not fields:
                return None, "ほ場データがありません"

            # 作付履歴を取得
            all_histories = []
            years = set()

            for field in fields:
                history = CropHistoryRepository.get_history(field['id'])
                for h in history:
                    years.add(h['year'])
                    all_histories.append({
                        'field_id': field['id'],
                        'field_code': field['field_code'],
                        'name': field['name'],
                        'district': field.get('district', ''),
                        'area_ha': field['area_ha'],
                        'year': h['year'],
                        'crop': h['crop']
                    })

            if not all_histories:
                # 履歴がない場合はほ場データのみで作成
                rows = []
                for field in fields:
                    rows.append({
                        'ほ場ID': field['field_code'],
                        '地区': field.get('district', ''),
                        'ほ場名': field['name'],
                        '面積(ha)': field['area_ha']
                    })
                df = pd.DataFrame(rows)
                return df, f"✅ {len(fields)}件のほ場（履歴なし）"

            # ピボットテーブル形式に変換
            df = pd.DataFrame(all_histories)
            pivot = df.pivot_table(
                index=['field_code', 'name', 'district', 'area_ha'],
                columns='year',
                values='crop',
                aggfunc='first'
            ).reset_index()

            # 列名を整理
            pivot.columns.name = None
            rename_map = {
                'field_code': 'ほ場ID',
                'name': 'ほ場名',
                'district': '地区',
                'area_ha': '面積(ha)'
            }
            pivot = pivot.rename(columns=rename_map)

            # 年列をR形式に変換
            year_cols = [c for c in pivot.columns if isinstance(c, int)]
            for year in year_cols:
                pivot = pivot.rename(columns={year: f'R{year}'})

            return pivot, f"✅ {len(fields)}件のほ場、{len(years)}年分の履歴"

        def save_plan_to_db(user_info, plan_name, result_df, constraints_data):
            """計画をDBに保存"""
            if not user_info or not user_info.get('user_id'):
                return "エラー: ログインが必要です"

            if result_df is None or len(result_df) == 0:
                return "エラー: 保存する計画がありません"

            user_id = user_info['user_id']

            try:
                # 年列を特定
                year_cols = [c for c in result_df.columns if c.startswith('R') or c.startswith('📍R')]
                if not year_cols:
                    return "エラー: 計画データの形式が不正です"

                # 年の範囲を取得
                years = [int(c.replace('📍', '').replace('R', '')) for c in year_cols]
                start_year = min(years)
                end_year = max(years)

                # 計画詳細を構築
                details = []
                for _, row in result_df.iterrows():
                    field_code = row.get('ほ場ID', row.get('field_id', ''))
                    # ほ場IDからDB上のfield_idを取得
                    field = FieldRepository.get_field_by_code(user_id, field_code)
                    if not field:
                        continue

                    for year_col in year_cols:
                        year = int(year_col.replace('📍', '').replace('R', ''))
                        crop = row.get(year_col, '')
                        if pd.notna(crop) and str(crop).strip():
                            details.append({
                                'field_id': field['id'],
                                'year': year,
                                'crop': str(crop).strip()
                            })

                # 計画を作成
                plan_data = {
                    'name': plan_name or f"計画_{start_year}-{end_year}",
                    'start_year': start_year,
                    'end_year': end_year,
                    'constraints': constraints_data or {},
                    'details': details
                }

                plan_id = PlanRepository.create_plan(user_id, plan_data)
                return f"✅ 計画を保存しました（ID: {plan_id}）"

            except Exception as e:
                return f"エラー: 計画の保存に失敗しました - {str(e)}"

        def load_saved_plans(user_info):
            """保存済み計画一覧を取得"""
            if not user_info or not user_info.get('user_id'):
                return gr.update(choices=[], value=None)

            user_id = user_info['user_id']
            plans = PlanRepository.get_plans(user_id)

            if not plans:
                return gr.update(choices=[], value=None)

            choices = [(f"{p['name']} (R{p['start_year']}-R{p['end_year']})", p['id']) for p in plans]
            return gr.update(choices=choices, value=choices[0][1] if choices else None)

        def load_plan_detail(plan_id, user_info):
            """保存済み計画を読み込み"""
            if not plan_id or not user_info:
                return None, None, "計画を選択してください"

            plan = PlanRepository.get_plan(plan_id)
            if not plan:
                return None, None, "計画が見つかりません"

            # セキュリティ: user_idチェック
            if plan.get('user_id') != user_info.get('user_id'):
                return None, None, "アクセス権限がありません"

            # 計画詳細をDataFrameに変換
            details = plan.get('details', [])
            if not details:
                return None, None, "計画詳細がありません"

            # ピボットテーブル形式に変換
            rows = []
            for d in details:
                rows.append({
                    'field_code': d['field_code'],
                    'field_name': d['field_name'],
                    'district': d.get('district', ''),
                    'year': d['year'],
                    'crop': d['crop']
                })

            df = pd.DataFrame(rows)
            pivot = df.pivot_table(
                index=['field_code', 'field_name', 'district'],
                columns='year',
                values='crop',
                aggfunc='first'
            ).reset_index()

            # 列名を整理
            pivot.columns.name = None
            rename_map = {'field_code': 'ほ場ID', 'field_name': 'ほ場名', 'district': '地区'}
            pivot = pivot.rename(columns=rename_map)

            # 年列をR形式に
            year_cols = [c for c in pivot.columns if isinstance(c, int)]
            for year in year_cols:
                pivot = pivot.rename(columns={year: f'R{year}'})

            return pivot, None, f"✅ 計画「{plan['name']}」を読み込みました"

        with gr.Row():
            gr.DownloadButton("📥 サンプルCSV", value=os.path.join(APP_DIR, "template_example.csv"))
            gr.DownloadButton("📥 空テンプレート", value=os.path.join(APP_DIR, "template_empty.csv"))

        gr.Markdown("""
        ### ⛔ 固定の禁止遷移
        - **てんさい→秋小麦**: 作期重複（ビート5-11月、秋小麦9月播種→翌7月収穫）
        - **春小麦→秋小麦**: 病害対策
        - **連作禁止**: 同一作物の連続年作付はNG
        """)
        
        with gr.Row():
            with gr.Column(scale=1):
                gr.Markdown("## 📂 入力")

                # データソース選択（DBまたはCSV）
                with gr.Accordion("🗄️ DBからほ場データを読み込む", open=False):
                    gr.Markdown("登録済みのほ場・作付履歴を使用して計画を作成します。")
                    load_from_db_btn = gr.Button("📥 DBからほ場・履歴を読み込む", variant="secondary")
                    db_load_status = gr.Textbox(label="読み込み状態", interactive=False)
                    db_fields_table = gr.Dataframe(
                        label="読み込んだほ場",
                        headers=["ほ場ID", "ほ場名", "地区", "面積(ha)"],
                        visible=False
                    )

                with gr.Accordion("📄 CSVファイルからインポート", open=True):
                    gr.Markdown("新規ユーザーまたは一括インポート用")
                    csv_file = gr.File(label="CSVファイル", file_types=[".csv"])
                
                with gr.Row():
                    area_unit = gr.Radio(
                        choices=["a (アール)", "ha (ヘクタール)"],
                        value="a (アール)",
                        label="面積の単位"
                    )
                    n_years = gr.Slider(
                        minimum=1, maximum=10, value=5, step=1,
                        label="将来年数"
                    )
                
                unknown_mode = gr.Radio(
                    choices=["制約をかけない（推奨）", "安全側（不明年を考慮）"],
                    value="制約をかけない（推奨）",
                    label="空欄(UNKNOWN)の扱い"
                )

                precision_mode = gr.Radio(
                    choices=["標準（10秒）", "高精度（60秒）"],
                    value="標準（10秒）",
                    label="計算精度"
                )

                tensai_required = gr.Checkbox(
                    value=False,
                    label="てんさい必須（毎年1ほ場以上）"
                )

                infer_unknown = gr.Checkbox(
                    value=True,
                    label="空欄を推論で補完（*マーク付き）"
                )

                district_grouping = gr.Checkbox(
                    value=True,
                    label="地区まとめを優先（同じ地区に同じ作物）"
                )

                gr.Markdown("## 🌱 作物マスター")
                crop_text = gr.Textbox(
                    value="\n".join(DEFAULT_CROPS),
                    label="作物リスト（改行区切り）",
                    lines=10
                )
                
            with gr.Column(scale=1):
                gr.Markdown("## ⚙️ 制約設定")

                with gr.Row():
                    constraints_sample_btn = gr.DownloadButton(
                        "📥 制約サンプルCSV",
                        value="constraints_example.csv"
                    )
                    constraints_empty_btn = gr.DownloadButton(
                        "📥 制約テンプレート",
                        value="constraints_empty.csv"
                    )

                constraints_file = gr.File(
                    label="制約CSV（オプション: アップロードで上書き）",
                    file_types=[".csv"],
                    type="filepath"
                )

                constraints_table = gr.Dataframe(
                    value=build_constraints_table(DEFAULT_CROPS),
                    label="制約テーブル",
                    headers=["作物", "最小(ha)", "最大(ha)", "間隔(年)", "最小筆数", "最大筆数"],
                    datatype=["str", "number", "number", "number", "number", "number"],
                    interactive=True,
                    row_count=(10, "dynamic")
                )

                gr.Markdown("""
                **列の説明:**
                - `最小(ha)`: 年間面積下限、空欄or0=下限なし
                - `最大(ha)`: 年間面積上限、空欄or0=無制限
                - `間隔(年)`: 最小作付間隔
                - `最小筆数`: 年間最小ほ場数
                - `最大筆数`: 年間最大ほ場数、空欄or0=無制限
                """)
                
                forbidden_text = gr.Textbox(
                    value="",
                    label="追加禁止遷移（例: 秋小麦->春小麦, 大豆->てんさい）",
                    placeholder="from->to, from->to, ..."
                )
                
                preferred_text = gr.Textbox(
                    value=DEFAULT_PREFERRED_TRANSITIONS,
                    label="優先遷移（例: てんさい->大豆:10）",
                    placeholder="from->to:weight, ..."
                )
                
                main_crops_text = gr.Textbox(
                    value=DEFAULT_MAIN_CROPS,
                    label="主作物（面積変動を抑制、カンマ区切り）"
                )
        
        # 作物マスター変更時に制約テーブルを更新
        crop_text.change(
            fn=update_constraints_table,
            inputs=[crop_text, constraints_table],
            outputs=[constraints_table]
        )

        # 制約CSVアップロード時に制約テーブルを更新
        constraints_file.change(
            fn=update_constraints_from_csv,
            inputs=[constraints_file],
            outputs=[constraints_table]
        )

        run_btn = gr.Button("🚀 計画を生成", variant="primary", size="lg")
        
        gr.Markdown("## 📊 結果")
        
        message_box = gr.Textbox(label="実行結果", lines=5, interactive=False)
        
        with gr.Tabs():
            with gr.TabItem("ほ場×年 計画表"):
                result_table = gr.Dataframe(
                    label="ほ場別計画",
                    interactive=False,
                    wrap=True
                )
            
            with gr.TabItem("年別 面積合計"):
                summary_table = gr.Dataframe(
                    label="年別作物面積(ha)",
                    interactive=False,
                    wrap=True
                )
        
        csv_download = gr.File(label="📥 計画CSVダウンロード")

        # DB保存機能
        with gr.Accordion("💾 計画をDBに保存", open=False):
            gr.Markdown("生成した計画をデータベースに保存します。")
            with gr.Row():
                plan_name_input = gr.Textbox(label="計画名", placeholder="例: 2026年度輪作計画")
                save_plan_btn = gr.Button("💾 DBに保存", variant="secondary")
            save_status = gr.Textbox(label="保存状態", interactive=False)

        run_btn.click(
            fn=run_optimization,
            inputs=[
                csv_file, area_unit, n_years, crop_text, constraints_table,
                forbidden_text, preferred_text, main_crops_text, unknown_mode,
                tensai_required, precision_mode, infer_unknown, district_grouping
            ],
            outputs=[result_table, summary_table, csv_download, message_box]
        )

        # DB読み込みボタンのイベント
        load_from_db_btn.click(
            fn=load_crop_history_from_db,
            inputs=[user_state],
            outputs=[db_fields_table, db_load_status]
        ).then(
            fn=lambda: gr.update(visible=True),
            outputs=[db_fields_table]
        )

        # 計画保存ボタンのイベント
        save_plan_btn.click(
            fn=save_plan_to_db,
            inputs=[user_state, plan_name_input, result_table, gr.State({})],
            outputs=[save_status]
        )

    return app

if __name__ == "__main__":
    app = create_app()
    app.launch(
        server_name="0.0.0.0",
        server_port=7860,
        theme=gr.themes.Soft(),
        auth=authenticate,  # 認証機能追加
        auth_message="輪作計画メーカーにログインしてください",
        allowed_paths=[
            os.path.join(os.path.dirname(__file__), "template_example.csv"),
            os.path.join(os.path.dirname(__file__), "template_empty.csv")
        ]
    )
