"""
rotation_planner.field.crud - ほ場CRUD操作モジュール

DBアクセスを伴うほ場の登録・削除・取得操作を提供。
user_idによるマルチテナント分離を保証。

Usage:
    from rotation_planner.field.crud import (
        get_user_fields,
        register_field,
        delete_field,
        get_field_history,
    )
"""

import json
import pandas as pd
from typing import List, Dict, Optional, Tuple, Any

# DB関連
from rotation_planner.common import (
    FieldRepository,
    CropHistoryRepository,
    UserRepository,
    format_alert,
    format_success,
    format_error,
    format_warning,
)

# 同一パッケージの地図モジュール
from .map import calculate_area_from_coords, m2_to_ha


# =============================================================================
# ヘルパー関数
# =============================================================================

def get_user_id_from_state(user_state: Dict[str, Any]) -> Optional[int]:
    """user_stateからユーザーIDを取得"""
    if user_state:
        return user_state.get('user_id')
    return None


def get_username_from_state(user_state: Dict[str, Any]) -> Optional[str]:
    """user_stateからユーザー名を取得"""
    if user_state:
        return user_state.get('username')
    return None


def get_user_id_from_username(username: str) -> Optional[int]:
    """ユーザー名からユーザーIDを取得"""
    user = UserRepository.get_user_by_username(username)
    if user:
        return user.get('id')
    return None


# =============================================================================
# ほ場ID自動生成
# =============================================================================

def get_next_field_id(user_id: int, prefix: str = "F") -> str:
    """
    次のほ場IDを自動生成

    既存のほ場IDを解析して、次の連番を返す。
    例: F001, F002, ... -> F003

    Args:
        user_id: ユーザーID
        prefix: ほ場IDのプレフィックス（デフォルト: "F"）

    Returns:
        次のほ場ID文字列
    """
    if not user_id:
        return f"{prefix}001"

    fields = get_user_fields(user_id)
    if not fields:
        return f"{prefix}001"

    # 既存のほ場IDから番号を抽出
    max_num = 0
    import re
    pattern = re.compile(rf'^{re.escape(prefix)}(\d+)$', re.IGNORECASE)

    for f in fields:
        field_code = f.get("field_code", "")
        match = pattern.match(field_code)
        if match:
            num = int(match.group(1))
            if num > max_num:
                max_num = num

    # 次の番号を生成（3桁ゼロ埋め）
    next_num = max_num + 1
    return f"{prefix}{next_num:03d}"


# =============================================================================
# ほ場データ取得
# =============================================================================

def get_user_fields(user_id: int) -> List[Dict[str, Any]]:
    """
    ユーザーのほ場一覧をDBから取得

    Args:
        user_id: ユーザーID

    Returns:
        ほ場データの辞書リスト
    """
    if not user_id:
        return []
    return FieldRepository.get_fields(user_id)


def fields_to_dataframe(fields: List[Dict[str, Any]]) -> pd.DataFrame:
    """
    ほ場リストをDataFrameに変換

    Args:
        fields: ほ場データのリスト

    Returns:
        ほ場一覧のDataFrame
    """
    if not fields:
        return pd.DataFrame(columns=["ID", "ほ場ID", "地区", "ほ場名", "面積(ha)", "面積(a)", "禁止"])

    rows = []
    for f in fields:
        area_ha = f.get("area_ha", 0)
        area_a = f.get("area_a", area_ha * 100)
        rows.append({
            "ID": f.get("id", ""),
            "ほ場ID": f.get("field_code", ""),
            "地区": f.get("district", ""),
            "ほ場名": f.get("name", ""),
            "面積(ha)": f"{area_ha:.4f}",
            "面積(a)": f"{area_a:.2f}",
            "禁止": "Yes" if f.get("beet_forbidden") else "No"
        })
    return pd.DataFrame(rows)


def get_fields_json_for_map(fields: List[Dict[str, Any]]) -> str:
    """
    地図表示用JSONを取得

    Args:
        fields: ほ場データのリスト

    Returns:
        JSON文字列
    """
    return json.dumps([
        {
            "field_id": f.get("field_code", f.get("id", "")),
            "name": f.get("name", ""),
            "coordinates": json.loads(f.get("coordinates_json", "[]")) if isinstance(f.get("coordinates_json"), str) else [],
            "area_a": f.get("area_a", f.get("area_ha", 0) * 100)
        }
        for f in fields
        if f.get("coordinates_json")
    ])


# =============================================================================
# ほ場登録・削除操作
# =============================================================================

def register_field_with_state(
    field_id: str,
    district: str,
    name: str,
    crop: str,
    beet_forbidden: bool,
    coords_json: str,
    user_state: Dict[str, Any]
) -> Tuple[pd.DataFrame, str, str, str]:
    """
    ほ場を登録（user_state版）

    Args:
        field_id: ほ場ID
        district: 地区名
        name: ほ場名
        crop: 今年の作物（空文字または「（未設定）」の場合は登録しない）
        beet_forbidden: 馬鈴薯・てんさい禁止フラグ
        coords_json: 座標JSON
        user_state: ユーザー情報

    Returns:
        (DataFrame, メッセージ, 地図用JSON, 次のほ場ID) のタプル
    """
    user_id = get_user_id_from_state(user_state)
    if not user_id:
        return pd.DataFrame(), format_error("エラー: ログインが必要です"), "[]", ""

    # 入力検証
    if not field_id.strip():
        fields = get_user_fields(user_id)
        next_id = get_next_field_id(user_id)
        return fields_to_dataframe(fields), format_warning("エラー: ほ場IDを入力してください"), get_fields_json_for_map(fields), next_id

    if not coords_json.strip():
        fields = get_user_fields(user_id)
        next_id = get_next_field_id(user_id)
        return fields_to_dataframe(fields), format_warning("エラー: 地図上でポリゴンを描画してください"), get_fields_json_for_map(fields), next_id

    try:
        coordinates = json.loads(coords_json)
        if len(coordinates) < 3:
            fields = get_user_fields(user_id)
            next_id = get_next_field_id(user_id)
            return fields_to_dataframe(fields), format_warning("エラー: 3点以上の頂点が必要です"), get_fields_json_for_map(fields), next_id
    except json.JSONDecodeError:
        fields = get_user_fields(user_id)
        next_id = get_next_field_id(user_id)
        return fields_to_dataframe(fields), format_error("エラー: 座標データが不正です"), get_fields_json_for_map(fields), next_id

    # 重複チェック
    existing = FieldRepository.get_field_by_code(user_id, field_id.strip())
    if existing:
        fields = get_user_fields(user_id)
        next_id = get_next_field_id(user_id)
        return fields_to_dataframe(fields), format_warning(f"エラー: ほ場ID '{field_id}' は既に登録されています"), get_fields_json_for_map(fields), next_id

    # 面積計算
    area_m2 = calculate_area_from_coords(coordinates)
    area_ha = m2_to_ha(area_m2)

    # ほ場データ作成
    field_data = {
        "field_code": field_id.strip(),
        "district": district.strip(),
        "name": name.strip() or field_id.strip(),
        "area_ha": area_ha,
        "beet_forbidden": 1 if beet_forbidden else 0,
        "coordinates_json": json.dumps(coordinates)
    }

    # DB登録
    try:
        new_field_db_id = FieldRepository.create_field(user_id, field_data)
        message = f"✅ ほ場 '{field_id}' を登録しました（{area_ha:.4f} ha / {area_ha * 100:.2f} a）"

        # 作物が設定されていれば、作付履歴にも登録
        if crop and crop not in ("", "（未設定）"):
            from datetime import datetime
            current_year = str(datetime.now().year)
            try:
                CropHistoryRepository.add_history(
                    field_id=new_field_db_id,
                    year=current_year,
                    crop=crop,
                    is_inferred=False
                )
                message += f"（{current_year}年: {crop}）"
            except Exception as crop_error:
                message += f"（作付履歴の登録に失敗: {crop_error}）"

    except Exception as e:
        fields = get_user_fields(user_id)
        next_id = get_next_field_id(user_id)
        return fields_to_dataframe(fields), format_error(f"エラー: 登録に失敗しました - {str(e)}"), get_fields_json_for_map(fields), next_id

    fields = get_user_fields(user_id)
    next_id = get_next_field_id(user_id)
    return fields_to_dataframe(fields), format_success(message), get_fields_json_for_map(fields), next_id


def delete_field_with_state(field_id: str, user_state: Dict[str, Any]) -> Tuple[pd.DataFrame, str, str]:
    """
    ほ場を削除（user_state版）

    Args:
        field_id: 削除するほ場ID
        user_state: ユーザー情報

    Returns:
        (DataFrame, メッセージ, 地図用JSON) のタプル
    """
    user_id = get_user_id_from_state(user_state)
    if not user_id:
        return pd.DataFrame(), format_error("エラー: ログインが必要です"), "[]"

    if not field_id.strip():
        fields = get_user_fields(user_id)
        return fields_to_dataframe(fields), format_warning("エラー: 削除するほ場IDを入力してください"), get_fields_json_for_map(fields)

    # ほ場コードで検索
    field = FieldRepository.get_field_by_code(user_id, field_id.strip())
    if not field:
        fields = get_user_fields(user_id)
        return fields_to_dataframe(fields), format_warning(f"エラー: ほ場 '{field_id}' が見つかりません"), get_fields_json_for_map(fields)

    # 削除
    try:
        if FieldRepository.delete_field(field["id"]):
            message = format_success(f"✅ ほ場 '{field_id}' を削除しました")
        else:
            message = format_error(f"エラー: ほ場 '{field_id}' の削除に失敗しました")
    except Exception as e:
        fields = get_user_fields(user_id)
        return fields_to_dataframe(fields), format_error(f"エラー: 削除に失敗しました - {str(e)}"), get_fields_json_for_map(fields)

    fields = get_user_fields(user_id)
    return fields_to_dataframe(fields), message, get_fields_json_for_map(fields)


# =============================================================================
# 作付履歴
# =============================================================================

def get_field_history_with_state(field_code: str, user_state: Dict[str, Any]) -> str:
    """
    ほ場の作付履歴を取得

    Args:
        field_code: ほ場コード
        user_state: ユーザー情報

    Returns:
        Markdown形式の履歴文字列
    """
    user_id = get_user_id_from_state(user_state)
    if not user_id:
        return "ログインが必要です"

    # ほ場を検索
    field = FieldRepository.get_field_by_code(user_id, field_code.strip())
    if not field:
        return f"ほ場 '{field_code}' が見つかりません"

    # 作付履歴を取得
    history = CropHistoryRepository.get_history(field["id"])

    if not history:
        return f"ほ場 '{field_code}' の作付履歴はありません"

    # 履歴を表示
    lines = [f"### ほ場 '{field_code}' の作付履歴\n"]
    for h in history:
        inferred = "（推定）" if h.get("is_inferred") else ""
        lines.append(f"- {h.get('year')}: {h.get('crop')}{inferred}")

    return "\n".join(lines)


# =============================================================================
# CSV出力
# =============================================================================

def export_csv_with_state(user_state: Dict[str, Any]) -> Tuple[Optional[str], str]:
    """
    CSVファイルをエクスポート

    Args:
        user_state: ユーザー情報

    Returns:
        (ファイルパス, メッセージ) のタプル
    """
    user_id = get_user_id_from_state(user_state)
    if not user_id:
        return None, "エラー: ログインが必要です"

    fields = get_user_fields(user_id)

    if not fields:
        return None, "エラー: 登録されたほ場がありません"

    # CSV形式で出力（輪作計画メーカー形式）
    lines = ["ほ場ID,地区,ほ場名,area,beet_forbidden"]
    for f in fields:
        beet = 1 if f.get("beet_forbidden") else 0
        area_a = f.get("area_a", f.get("area_ha", 0) * 100)
        lines.append(f"{f.get('field_code', '')},{f.get('district', '')},{f.get('name', '')},{area_a:.2f},{beet}")

    csv_content = "\n".join(lines)
    csv_path = "/tmp/field_register_export.csv"

    with open(csv_path, 'w', encoding='utf-8-sig') as file:
        file.write(csv_content)

    return csv_path, f"CSVファイルを出力しました（{len(fields)}件）"


# =============================================================================
# 公開API
# =============================================================================

__all__ = [
    # ヘルパー
    "get_user_id_from_state",
    "get_username_from_state",
    "get_user_id_from_username",
    # ほ場ID自動生成
    "get_next_field_id",
    # データ取得
    "get_user_fields",
    "fields_to_dataframe",
    "get_fields_json_for_map",
    # CRUD操作
    "register_field_with_state",
    "delete_field_with_state",
    # 履歴
    "get_field_history_with_state",
    # CSV出力
    "export_csv_with_state",
]
