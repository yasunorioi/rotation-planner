#!/usr/bin/env python3
"""
輪作計画メーカー デモ版
認証なし・モックデータで動作する軽量デモ
"""

import gradio as gr
import pandas as pd
import numpy as np
import random
from typing import Dict, List, Tuple, Set
from dataclasses import dataclass, field
from copy import deepcopy
import os

os.environ["GRADIO_ANALYTICS_ENABLED"] = "False"


# =============================================================================
# 定数
# =============================================================================

DEMO_CROPS = ["てんさい", "大豆", "春小麦", "秋小麦"]

FIXED_FORBIDDEN_TRANSITIONS = [
    ("てんさい", "秋小麦"),  # 作期重複
    ("春小麦", "秋小麦"),    # 病害対策
]

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
    history: Dict[str, str] = field(default_factory=dict)
    beet_forbidden: bool = False


@dataclass
class Constraints:
    """制約設定"""
    crop_caps: Dict[str, float] = field(default_factory=dict)
    min_gap_years: Dict[str, int] = field(default_factory=dict)
    max_fields: Dict[str, int] = field(default_factory=dict)
    forbidden_transitions: Set[Tuple[str, str]] = field(default_factory=set)


# =============================================================================
# モックデータ
# =============================================================================

def create_mock_fields() -> Tuple[List[Field], List[str]]:
    """デモ用モックデータを生成"""
    past_years = ["R1", "R2", "R3", "R4", "R5"]

    fields = [
        Field(
            field_id="F001",
            district="A地区",
            name="北側ほ場",
            area_ha=2.5,
            history={
                "R1": "大豆",
                "R2": "春小麦",
                "R3": "てんさい",
                "R4": "秋小麦",
                "R5": "大豆",
            }
        ),
        Field(
            field_id="F002",
            district="A地区",
            name="南側ほ場",
            area_ha=1.8,
            history={
                "R1": "春小麦",
                "R2": "てんさい",
                "R3": "大豆",
                "R4": "春小麦",
                "R5": "秋小麦",
            }
        ),
        Field(
            field_id="F003",
            district="B地区",
            name="東側ほ場",
            area_ha=3.0,
            history={
                "R1": "秋小麦",
                "R2": "大豆",
                "R3": "春小麦",
                "R4": "てんさい",
                "R5": "春小麦",
            }
        ),
        Field(
            field_id="F004",
            district="B地区",
            name="西側ほ場",
            area_ha=2.2,
            history={
                "R1": "てんさい",
                "R2": "秋小麦",
                "R3": "大豆",
                "R4": "春小麦",
                "R5": "大豆",
            }
        ),
    ]

    return fields, past_years


# =============================================================================
# ヒューリスティック最適化（軽量版）
# =============================================================================

class DemoRotationPlanner:
    """デモ用軽量最適化クラス"""

    def __init__(self, fields: List[Field], past_years: List[str],
                 future_years: List[str], crops: List[str], constraints: Constraints):
        self.fields = fields
        self.past_years = past_years
        self.future_years = future_years
        self.all_years = past_years + future_years
        self.crops = crops
        self.constraints = constraints

    def get_last_crop(self, field_idx: int, year: str, plan: Dict) -> str:
        """前年の作物を取得"""
        year_idx = self.all_years.index(year)
        if year_idx == 0:
            return None
        prev_year = self.all_years[year_idx - 1]
        if prev_year in self.past_years:
            return self.fields[field_idx].history.get(prev_year)
        return plan.get((field_idx, prev_year))

    def check_gap_constraint(self, field_idx: int, year: str, crop: str, plan: Dict) -> bool:
        """間隔制約をチェック"""
        min_gap = self.constraints.min_gap_years.get(crop, 0)
        if min_gap <= 0:
            return True

        year_idx = self.all_years.index(year)
        for i in range(1, min_gap + 1):
            if year_idx - i < 0:
                break
            prev_year = self.all_years[year_idx - i]
            if prev_year in self.past_years:
                prev_crop = self.fields[field_idx].history.get(prev_year)
            else:
                prev_crop = plan.get((field_idx, prev_year))
            if prev_crop == crop:
                return False
        return True

    def check_transition(self, field_idx: int, year: str, crop: str, plan: Dict) -> bool:
        """遷移制約をチェック"""
        prev_crop = self.get_last_crop(field_idx, year, plan)
        if prev_crop is None:
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
                if self.check_transition(field_idx, year, crop, plan):
                    valid.append(crop)
        return valid

    def calculate_year_stats(self, year: str, plan: Dict) -> Dict[str, float]:
        """年の作物面積を計算"""
        stats = {c: 0.0 for c in self.crops}
        for i, f in enumerate(self.fields):
            if year in self.past_years:
                crop = f.history.get(year)
            else:
                crop = plan.get((i, year))
            if crop and crop in stats:
                stats[crop] += f.area_ha
        return stats

    def solve(self) -> Tuple[Dict, float, List[str]]:
        """最適化を実行"""
        plan = {}
        errors = []

        for year in self.future_years:
            field_indices = list(range(len(self.fields)))
            random.shuffle(field_indices)

            for field_idx in field_indices:
                valid_crops = self.get_valid_crops(field_idx, year, plan)

                if not valid_crops:
                    valid_crops = self.crops.copy()
                    errors.append(f"警告: {self.fields[field_idx].field_id}の{year}で制約緩和")

                # 面積バランスを考慮して選択
                year_stats = self.calculate_year_stats(year, plan)
                best_crop = min(valid_crops, key=lambda c: year_stats.get(c, 0))

                plan[(field_idx, year)] = best_crop

        # スコア計算（面積変動の逆数）
        total_variance = 0
        for crop in self.crops:
            areas = []
            for year in self.future_years:
                stats = self.calculate_year_stats(year, plan)
                areas.append(stats.get(crop, 0))
            if areas:
                total_variance += np.var(areas)

        score = -total_variance * 100

        return plan, score, errors


# =============================================================================
# 結果生成
# =============================================================================

def generate_result_tables(fields: List[Field], past_years: List[str],
                          future_years: List[str], plan: Dict, crops: List[str]):
    """結果テーブルを生成"""
    all_years = past_years + future_years
    current_year = future_years[0] if future_years else None

    def year_col_name(year):
        if year == current_year:
            return f"📍{year}"
        return year

    # ほ場×年の表
    rows = []
    for i, f in enumerate(fields):
        row = {
            "ほ場ID": f.field_id,
            "地区": f.district,
            "ほ場名": f.name,
            "面積(ha)": f"{f.area_ha:.2f}",
        }
        for year in all_years:
            col_name = year_col_name(year)
            if year in past_years:
                row[col_name] = f.history.get(year, "")
            else:
                row[col_name] = plan.get((i, year), "")
        rows.append(row)

    field_df = pd.DataFrame(rows)

    # 年別面積合計表
    summary_rows = []
    for year in all_years:
        row = {"年": year_col_name(year)}
        for crop in crops:
            total_ha = 0.0
            for i, f in enumerate(fields):
                if year in past_years:
                    c = f.history.get(year)
                else:
                    c = plan.get((i, year))
                if c == crop:
                    total_ha += f.area_ha
            row[crop] = f"{total_ha:.2f}" if total_ha > 0 else ""
        summary_rows.append(row)

    summary_df = pd.DataFrame(summary_rows)

    return field_df, summary_df


# =============================================================================
# デモ最適化実行
# =============================================================================

def run_demo_optimization(n_years: int, beet_gap: int, wheat_cap: float):
    """デモ用最適化を実行"""

    # モックデータ取得
    fields, past_years = create_mock_fields()

    # 将来年生成
    last_year = max(int(y[1:]) for y in past_years)
    future_years = [f"R{last_year + i + 1}" for i in range(n_years)]

    # 制約設定
    constraints = Constraints(
        crop_caps={
            "春小麦": wheat_cap,
            "秋小麦": wheat_cap,
        },
        min_gap_years={
            "てんさい": beet_gap,
        },
        max_fields={
            "てんさい": 2,
        },
        forbidden_transitions=set(FIXED_FORBIDDEN_TRANSITIONS)
    )

    # 最適化実行
    planner = DemoRotationPlanner(fields, past_years, future_years, DEMO_CROPS, constraints)
    plan, score, errors = planner.solve()

    # 結果生成
    field_df, summary_df = generate_result_tables(fields, past_years, future_years, plan, DEMO_CROPS)

    # メッセージ
    message = f"✅ デモ計画生成完了\n"
    message += f"・過去{len(past_years)}年 + 将来{len(future_years)}年の計画\n"
    message += f"・ほ場数: {len(fields)}\n"
    message += f"・総面積: {sum(f.area_ha for f in fields):.2f} ha\n"

    if errors:
        message += "\n⚠️ 警告:\n"
        for e in errors:
            message += f"  - {e}\n"

    return field_df, summary_df, message


# =============================================================================
# Gradio UI
# =============================================================================

def create_rotation_demo_ui():
    """
    輪作計画デモUIを作成

    Returns:
        gr.Blocks: Gradioアプリケーション
    """

    with gr.Blocks(title="輪作計画メーカー デモ") as app:

        gr.Markdown("""
        # 🌾 輪作計画メーカー デモ版

        北海道畑作の輪作計画を自動生成するデモです。
        モックデータ（4ほ場・過去5年分）を使用しています。

        ### 📋 対象作物
        - てんさい（4年間隔）
        - 大豆
        - 春小麦
        - 秋小麦

        ### ⛔ 固定の禁止遷移
        - **てんさい→秋小麦**: 作期重複
        - **春小麦→秋小麦**: 病害対策
        - **連作禁止**: 同一作物の連続作付はNG
        """)

        with gr.Row():
            with gr.Column(scale=1):
                gr.Markdown("## ⚙️ パラメータ設定")

                n_years = gr.Slider(
                    minimum=1, maximum=10, value=5, step=1,
                    label="将来年数"
                )

                beet_gap = gr.Slider(
                    minimum=2, maximum=6, value=4, step=1,
                    label="てんさい作付間隔（年）"
                )

                wheat_cap = gr.Slider(
                    minimum=2.0, maximum=10.0, value=5.0, step=0.5,
                    label="小麦類の年間面積上限（ha）"
                )

                run_btn = gr.Button("🚀 計画を生成", variant="primary", size="lg")

            with gr.Column(scale=2):
                gr.Markdown("## 📊 モックデータ（過去5年）")

                # モックデータ表示
                fields, past_years = create_mock_fields()
                mock_rows = []
                for f in fields:
                    row = {"ほ場ID": f.field_id, "地区": f.district, "面積(ha)": f.area_ha}
                    for y in past_years:
                        row[y] = f.history.get(y, "")
                    mock_rows.append(row)
                mock_df = pd.DataFrame(mock_rows)

                gr.Dataframe(value=mock_df, label="入力データ（モック）", interactive=False)

        gr.Markdown("---")
        gr.Markdown("## 📊 計画結果")

        message_box = gr.Textbox(label="実行結果", lines=5, interactive=False)

        with gr.Tabs():
            with gr.TabItem("ほ場×年 計画表"):
                result_table = gr.Dataframe(
                    label="ほ場別計画（📍=今年）",
                    interactive=False,
                    wrap=True
                )

            with gr.TabItem("年別 面積合計"):
                summary_table = gr.Dataframe(
                    label="年別作物面積(ha)",
                    interactive=False,
                    wrap=True
                )

        run_btn.click(
            fn=run_demo_optimization,
            inputs=[n_years, beet_gap, wheat_cap],
            outputs=[result_table, summary_table, message_box]
        )

        gr.Markdown("""
        ---
        ### 📝 注意事項
        - これはデモ版です。実際のデータは使用していません。
        - 認証機能・データ保存機能はありません。
        - 軽量ヒューリスティックアルゴリズムを使用しています。
        """)

    return app


# =============================================================================
# 単独起動
# =============================================================================

if __name__ == "__main__":
    app = create_rotation_demo_ui()
    app.launch(
        server_name="0.0.0.0",
        server_port=7860,  # HF Spaces標準ポート
        share=False,
        ssr_mode=False  # SSR無効化（HF Spaces互換性向上）
    )
