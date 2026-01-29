"""
共有データモジュール - アプリ間でデータを永続化・共有する

使用方法:
    from shared_data import FieldStorage, RotationPlanStorage

    # ほ場データの保存・読み込み
    fields = FieldStorage.load()
    FieldStorage.save(fields)

    # 輪作計画の保存・読み込み
    plan = RotationPlanStorage.load("plan_2026")
    RotationPlanStorage.save(plan, "plan_2026")
"""

import json
import os
from pathlib import Path
from typing import List, Dict, Optional, Any
from datetime import datetime


# =============================================================================
# 設定
# =============================================================================

# データディレクトリ（このファイルと同じ階層の data/）
DATA_DIR = Path(__file__).parent / "data"

# ファイル名
FIELDS_FILE = "fields.json"
ROTATION_PLANS_DIR = "rotation_plans"


# =============================================================================
# ユーティリティ
# =============================================================================

def ensure_data_dir() -> Path:
    """データディレクトリを作成し、パスを返す"""
    DATA_DIR.mkdir(exist_ok=True)
    return DATA_DIR


def ensure_plans_dir() -> Path:
    """輪作計画ディレクトリを作成し、パスを返す"""
    plans_dir = DATA_DIR / ROTATION_PLANS_DIR
    plans_dir.mkdir(parents=True, exist_ok=True)
    return plans_dir


# =============================================================================
# ほ場データ管理
# =============================================================================

class FieldStorage:
    """ほ場データの永続化"""

    @staticmethod
    def _get_file_path() -> Path:
        return ensure_data_dir() / FIELDS_FILE

    @staticmethod
    def save(fields: List[Dict[str, Any]]) -> None:
        """
        ほ場データを保存

        Args:
            fields: ほ場データのリスト
                各要素は以下のキーを持つdict:
                - field_id: str (ほ場ID)
                - district: str (地区)
                - name: str (ほ場名)
                - area_ha: float (面積、ヘクタール)
                - area_a: float (面積、アール) ※オプション
                - beet_forbidden: bool (てんさい禁止フラグ)
                - coordinates: List[List[float]] (座標) ※オプション
                - history: Dict[str, str] (作付履歴) ※オプション
        """
        file_path = FieldStorage._get_file_path()
        data = {
            "version": "1.0",
            "updated_at": datetime.now().isoformat(),
            "fields": fields
        }
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    @staticmethod
    def load() -> List[Dict[str, Any]]:
        """
        ほ場データを読み込み

        Returns:
            ほ場データのリスト（ファイルがない場合は空リスト）
        """
        file_path = FieldStorage._get_file_path()
        if not file_path.exists():
            return []

        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        return data.get("fields", [])

    @staticmethod
    def add(field: Dict[str, Any]) -> None:
        """
        ほ場を追加（同じfield_idがあれば上書き）

        Args:
            field: ほ場データ
        """
        fields = FieldStorage.load()

        # 既存のfield_idを検索
        existing_idx = None
        for i, f in enumerate(fields):
            if f.get("field_id") == field.get("field_id"):
                existing_idx = i
                break

        if existing_idx is not None:
            fields[existing_idx] = field
        else:
            fields.append(field)

        FieldStorage.save(fields)

    @staticmethod
    def delete(field_id: str) -> bool:
        """
        ほ場を削除

        Args:
            field_id: 削除するほ場ID

        Returns:
            削除成功ならTrue
        """
        fields = FieldStorage.load()
        original_count = len(fields)
        fields = [f for f in fields if f.get("field_id") != field_id]

        if len(fields) < original_count:
            FieldStorage.save(fields)
            return True
        return False

    @staticmethod
    def get(field_id: str) -> Optional[Dict[str, Any]]:
        """
        ほ場を取得

        Args:
            field_id: 取得するほ場ID

        Returns:
            ほ場データ（見つからない場合はNone）
        """
        fields = FieldStorage.load()
        for f in fields:
            if f.get("field_id") == field_id:
                return f
        return None


# =============================================================================
# 輪作計画データ管理
# =============================================================================

class RotationPlanStorage:
    """輪作計画データの永続化"""

    @staticmethod
    def _get_file_path(plan_name: str) -> Path:
        safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in plan_name)
        return ensure_plans_dir() / f"{safe_name}.json"

    @staticmethod
    def save(plan: Dict[str, Any], plan_name: str) -> None:
        """
        輪作計画を保存

        Args:
            plan: 輪作計画データ
                - fields: List[Dict] (ほ場と作付け履歴・計画)
                - constraints: Dict (制約設定)
                - years: List[str] (対象年度)
                - metadata: Dict (その他メタデータ)
            plan_name: 計画名（ファイル名に使用）
        """
        file_path = RotationPlanStorage._get_file_path(plan_name)
        data = {
            "version": "1.0",
            "name": plan_name,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            **plan
        }

        # 既存ファイルがあれば created_at を保持
        if file_path.exists():
            with open(file_path, "r", encoding="utf-8") as f:
                existing = json.load(f)
                data["created_at"] = existing.get("created_at", data["created_at"])

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    @staticmethod
    def load(plan_name: str) -> Optional[Dict[str, Any]]:
        """
        輪作計画を読み込み

        Args:
            plan_name: 計画名

        Returns:
            輪作計画データ（ファイルがない場合はNone）
        """
        file_path = RotationPlanStorage._get_file_path(plan_name)
        if not file_path.exists():
            return None

        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)

    @staticmethod
    def delete(plan_name: str) -> bool:
        """
        輪作計画を削除

        Args:
            plan_name: 削除する計画名

        Returns:
            削除成功ならTrue
        """
        file_path = RotationPlanStorage._get_file_path(plan_name)
        if file_path.exists():
            file_path.unlink()
            return True
        return False

    @staticmethod
    def list_plans() -> List[Dict[str, str]]:
        """
        保存されている輪作計画の一覧を取得

        Returns:
            計画情報のリスト
                - name: 計画名
                - created_at: 作成日時
                - updated_at: 更新日時
        """
        plans_dir = ensure_plans_dir()
        plans = []

        for file_path in plans_dir.glob("*.json"):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    plans.append({
                        "name": data.get("name", file_path.stem),
                        "created_at": data.get("created_at", ""),
                        "updated_at": data.get("updated_at", "")
                    })
            except (json.JSONDecodeError, IOError):
                continue

        # 更新日時で降順ソート
        plans.sort(key=lambda x: x.get("updated_at", ""), reverse=True)
        return plans


# =============================================================================
# 便利関数（dataclass変換）
# =============================================================================

def field_to_dict(field_obj: Any) -> Dict[str, Any]:
    """
    Field/FieldData dataclassをdictに変換

    Args:
        field_obj: app.py の Field または field_register.py の FieldData

    Returns:
        dict形式のほ場データ
    """
    if hasattr(field_obj, "__dataclass_fields__"):
        from dataclasses import asdict
        return asdict(field_obj)
    elif hasattr(field_obj, "__dict__"):
        return dict(field_obj.__dict__)
    else:
        return dict(field_obj)


def normalize_field_data(field: Dict[str, Any]) -> Dict[str, Any]:
    """
    ほ場データの単位を正規化（ha/a両方持つようにする）

    Args:
        field: ほ場データ

    Returns:
        正規化されたほ場データ
    """
    result = dict(field)

    # ha と a の相互変換
    if "area_ha" in result and "area_a" not in result:
        result["area_a"] = result["area_ha"] * 100
    elif "area_a" in result and "area_ha" not in result:
        result["area_ha"] = result["area_a"] / 100

    return result
