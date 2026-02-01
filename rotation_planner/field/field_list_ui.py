"""
rotation_planner.field.field_list_ui - ほ場一覧UI

ほ場の一覧表示・編集機能を提供。
年度別作物表示、インライン編集、輪作計画結果の微調整が可能。
"""

import gradio as gr
import pandas as pd
import json
from datetime import datetime
from typing import Dict, Any, Tuple, List, Optional

from ..common import (
    format_success, format_error, format_warning,
    FieldRepository,
)
from ..common.year_utils import (
    western_to_reiwa,
    reiwa_to_western,
    get_current_fiscal_year,
    generate_year_choices,
)
from .crud import (
    get_user_id_from_state,
    get_user_fields,
    fields_to_dataframe,
)
from .crop_settings import get_user_crops


# =============================================================================
# データ取得
# =============================================================================

def get_fields_with_yearly_crops(user_id: int, start_reiwa_year: str, end_reiwa_year: str = None) -> pd.DataFrame:
    """
    ほ場一覧に年度別作物を付与して取得

    Args:
        user_id: ユーザーID
        start_reiwa_year: 開始年度（令和形式、例: "R5"）
        end_reiwa_year: 終了年度（令和形式、例: "R9"）。Noneの場合は開始から5年

    Returns:
        年度別作物列を含むDataFrame
    """
    fields = get_user_fields(user_id)
    if not fields:
        return pd.DataFrame()

    # 基本情報のDataFrame
    data = []
    for f in fields:
        row = {
            "id": f["id"],
            "ほ場ID": f["field_code"],
            "ほ場名": f["name"],
            "地区": f["district"] or "",
            "面積(ha)": round(f["area_ha"], 2),
            "禁止": "○" if f["beet_forbidden"] else "",
        }
        data.append(row)

    df = pd.DataFrame(data)

    # 令和年度の数値部分を取得
    start_num = int(start_reiwa_year[1:]) if start_reiwa_year.startswith("R") else int(start_reiwa_year)
    if end_reiwa_year:
        end_num = int(end_reiwa_year[1:]) if end_reiwa_year.startswith("R") else int(end_reiwa_year)
    else:
        end_num = start_num + 4  # デフォルト5年

    # 年度別作物を取得（作付履歴から）
    for year_num in range(start_num, end_num + 1):
        reiwa_year = f"R{year_num}"
        df[reiwa_year] = ""

        for idx, row in df.iterrows():
            field_id = row["id"]
            crop = get_crop_for_field_year(user_id, field_id, reiwa_year)
            df.at[idx, reiwa_year] = crop

    return df


def get_crop_for_field_year(user_id: int, field_db_id: int, reiwa_year: str) -> str:
    """
    特定のほ場・年度の作物を取得（作付履歴から）

    Args:
        user_id: ユーザーID（未使用、互換性のため残す）
        field_db_id: ほ場のDB ID
        reiwa_year: 令和年度（例: "R7"）

    Returns:
        作物名（未登録の場合は空文字）
    """
    from ..common import CropHistoryRepository

    # 作付履歴から取得（令和年度形式で比較）
    history = CropHistoryRepository.get_history(field_db_id)
    for h in history:
        if h["year"] == reiwa_year:
            return h["crop"]

    return ""


def get_year_choices() -> List[str]:
    """年度選択肢を生成（令和形式）"""
    return generate_year_choices(start_offset=-2, end_offset=10)


# =============================================================================
# データ更新
# =============================================================================

def update_field_info(
    field_db_id: int,
    field_code: str,
    name: str,
    district: str,
    area_ha: float,
    beet_forbidden: bool,
    user_state: Dict[str, Any]
) -> Tuple[str, pd.DataFrame]:
    """
    ほ場情報を更新

    Returns:
        (メッセージ, 更新後の一覧DataFrame)
    """
    user_id = get_user_id_from_state(user_state)
    if not user_id:
        return format_error("ログインしてください"), pd.DataFrame()

    try:
        FieldRepository.update_field(field_db_id, {
            "field_code": field_code.strip(),
            "name": name.strip(),
            "district": district.strip(),
            "area_ha": area_ha,
            "beet_forbidden": 1 if beet_forbidden else 0,
        })

        # 更新後の一覧を取得
        current_reiwa = get_current_fiscal_year()
        df = get_fields_with_yearly_crops(user_id, current_reiwa)

        return format_success(f"ほ場 '{field_code}' を更新しました"), df

    except Exception as e:
        return format_error(f"更新エラー: {str(e)}"), pd.DataFrame()


def update_crop_for_year(
    field_db_id: int,
    reiwa_year: str,
    crop: str,
    user_state: Dict[str, Any]
) -> Tuple[str, pd.DataFrame]:
    """
    特定年度の作物を更新（作付履歴に登録/更新）

    Args:
        field_db_id: ほ場のDB ID
        reiwa_year: 令和年度（例: "R7"）
        crop: 作物名
        user_state: ユーザー状態

    Returns:
        (メッセージ, 更新後の一覧DataFrame)
    """
    from ..common import CropHistoryRepository

    user_id = get_user_id_from_state(user_state)
    if not user_id:
        return format_error("ログインしてください"), pd.DataFrame()

    try:
        # add_historyはINSERT OR REPLACEなので追加/更新どちらも対応
        CropHistoryRepository.add_history(field_db_id, reiwa_year, crop)
        msg = f"{reiwa_year}の作物を '{crop}' に設定しました"

        # 更新後の一覧を取得
        current_reiwa = get_current_fiscal_year()
        df = get_fields_with_yearly_crops(user_id, current_reiwa)

        return format_success(msg), df

    except Exception as e:
        return format_error(f"更新エラー: {str(e)}"), pd.DataFrame()


def delete_field_from_list(
    field_db_id: int,
    user_state: Dict[str, Any]
) -> Tuple[str, pd.DataFrame]:
    """
    ほ場を削除

    Returns:
        (メッセージ, 更新後の一覧DataFrame)
    """
    user_id = get_user_id_from_state(user_state)
    if not user_id:
        return format_error("ログインしてください"), pd.DataFrame()

    try:
        # ほ場情報を取得
        field = FieldRepository.get_field_by_id(field_db_id)
        if not field:
            return format_error("ほ場が見つかりません"), pd.DataFrame()

        field_code = field["field_code"]

        # 削除
        FieldRepository.delete_field(field_db_id)

        # 更新後の一覧を取得
        current_reiwa = get_current_fiscal_year()
        df = get_fields_with_yearly_crops(user_id, current_reiwa)

        return format_success(f"ほ場 '{field_code}' を削除しました"), df

    except Exception as e:
        return format_error(f"削除エラー: {str(e)}"), pd.DataFrame()


# =============================================================================
# UI構築
# =============================================================================

def create_field_list_ui(user_state: gr.State) -> Dict[str, Any]:
    """
    ほ場一覧UIを作成

    Args:
        user_state: ユーザー状態

    Returns:
        コンポーネント辞書
    """
    current_reiwa = get_current_fiscal_year()
    year_choices = get_year_choices()

    with gr.Column():
        gr.Markdown("## 🗺️ ほ場一覧・編集")
        gr.Markdown("""
        登録済みほ場の一覧表示と編集ができます。
        - 行をクリックして選択 → 下部で編集
        - 年度別作物も修正可能
        """)

        # デフォルト: 過去2年〜2年後（計5年）
        current_num = int(current_reiwa[1:])
        default_start = f"R{current_num - 2}"
        default_end = f"R{current_num + 2}"

        with gr.Row():
            year_start = gr.Dropdown(
                label="開始年度",
                choices=year_choices,
                value=default_start,
                scale=1
            )
            year_end = gr.Dropdown(
                label="終了年度",
                choices=year_choices,
                value=default_end,
                scale=1
            )
            refresh_btn = gr.Button("🔄 更新", scale=1)

        # ほ場一覧テーブル
        field_list_table = gr.Dataframe(
            value=pd.DataFrame(),
            label="ほ場一覧",
            interactive=False,
            wrap=True,
        )

        # 選択中のほ場ID（隠しフィールド）
        selected_field_id = gr.Textbox(visible=False, value="")

        gr.Markdown("---")
        gr.Markdown("### ✏️ 編集")

        with gr.Row():
            with gr.Column(scale=1):
                edit_field_code = gr.Textbox(label="ほ場ID", interactive=True)
                edit_name = gr.Textbox(label="ほ場名", interactive=True)
                edit_district = gr.Textbox(label="地区", interactive=True)

            with gr.Column(scale=1):
                edit_area = gr.Number(label="面積(ha)", interactive=True)
                edit_beet_forbidden = gr.Checkbox(label="てんさい禁止", interactive=True)

        gr.Markdown("#### 年度別作物")
        with gr.Row():
            edit_year = gr.Dropdown(
                label="年度",
                choices=year_choices,
                value=current_reiwa,
                scale=1
            )
            edit_crop = gr.Dropdown(
                label="作物",
                choices=["（未設定）"],
                value="（未設定）",
                scale=2
            )
            apply_crop_btn = gr.Button("💾 作物を保存", scale=1)

        with gr.Row():
            save_btn = gr.Button("💾 ほ場情報を保存", variant="primary")
            delete_btn = gr.Button("🗑️ 削除", variant="stop")

        message_box = gr.HTML("")

    # ==========================================================================
    # イベントハンドラ
    # ==========================================================================

    def load_field_list(start_year: str, end_year: str, user_state: Dict[str, Any]) -> pd.DataFrame:
        """ほ場一覧を読み込み（令和年度形式）"""
        user_id = get_user_id_from_state(user_state)
        if not user_id:
            return pd.DataFrame()

        df = get_fields_with_yearly_crops(user_id, start_year, end_year)

        return df

    def on_select_row(evt: gr.SelectData, df: pd.DataFrame, user_state: Dict[str, Any]):
        """行選択時の処理"""
        if df is None or df.empty:
            return "", "", "", "", 0, False

        row_idx = evt.index[0]
        if row_idx >= len(df):
            return "", "", "", "", 0, False

        row = df.iloc[row_idx]

        field_db_id = str(row.get("id", ""))
        field_code = row.get("ほ場ID", "")
        name = row.get("ほ場名", "")
        district = row.get("地区", "")
        area = row.get("面積(ha)", 0)
        beet_forbidden = row.get("禁止", "") == "○"

        return field_db_id, field_code, name, district, area, beet_forbidden

    def save_field(
        field_db_id: str,
        field_code: str,
        name: str,
        district: str,
        area: float,
        beet_forbidden: bool,
        start_year: str,
        end_year: str,
        user_state: Dict[str, Any]
    ):
        """ほ場情報を保存"""
        if not field_db_id:
            return format_warning("ほ場を選択してください"), pd.DataFrame()

        msg, df = update_field_info(
            int(field_db_id),
            field_code,
            name,
            district,
            area,
            beet_forbidden,
            user_state
        )

        # 一覧を再取得
        user_id = get_user_id_from_state(user_state)
        df = get_fields_with_yearly_crops(user_id, start_year, end_year)

        return msg, df

    def save_crop(
        field_db_id: str,
        reiwa_year: str,
        crop: str,
        start_year: str,
        end_year: str,
        user_state: Dict[str, Any]
    ):
        """年度別作物を保存"""
        if not field_db_id:
            return format_warning("ほ場を選択してください"), pd.DataFrame()

        if not crop or crop == "（未設定）":
            return format_warning("作物を選択してください"), pd.DataFrame()

        msg, _ = update_crop_for_year(
            int(field_db_id),
            reiwa_year,
            crop,
            user_state
        )

        # 一覧を再取得
        user_id = get_user_id_from_state(user_state)
        df = get_fields_with_yearly_crops(user_id, start_year, end_year)

        return msg, df

    def delete_field(
        field_db_id: str,
        start_year: str,
        end_year: str,
        user_state: Dict[str, Any]
    ):
        """ほ場を削除"""
        if not field_db_id:
            return format_warning("ほ場を選択してください"), pd.DataFrame()

        msg, _ = delete_field_from_list(int(field_db_id), user_state)

        # 一覧を再取得
        user_id = get_user_id_from_state(user_state)
        df = get_fields_with_yearly_crops(user_id, start_year, end_year)

        return msg, df

    def init_crop_choices(user_state: Dict[str, Any]) -> gr.Dropdown:
        """作物ドロップダウンを初期化"""
        user_id = get_user_id_from_state(user_state)
        if not user_id:
            return gr.Dropdown(choices=["（未設定）"], value="（未設定）")

        crops = get_user_crops(user_id)
        crop_names = [c["name"] for c in crops]
        choices = ["（未設定）"] + crop_names

        return gr.Dropdown(choices=choices, value="（未設定）")

    # イベント接続
    refresh_btn.click(
        fn=load_field_list,
        inputs=[year_start, year_end, user_state],
        outputs=[field_list_table]
    )

    year_start.change(
        fn=load_field_list,
        inputs=[year_start, year_end, user_state],
        outputs=[field_list_table]
    )

    year_end.change(
        fn=load_field_list,
        inputs=[year_start, year_end, user_state],
        outputs=[field_list_table]
    )

    field_list_table.select(
        fn=on_select_row,
        inputs=[field_list_table, user_state],
        outputs=[selected_field_id, edit_field_code, edit_name, edit_district, edit_area, edit_beet_forbidden]
    )

    save_btn.click(
        fn=save_field,
        inputs=[selected_field_id, edit_field_code, edit_name, edit_district, edit_area, edit_beet_forbidden, year_start, year_end, user_state],
        outputs=[message_box, field_list_table]
    )

    apply_crop_btn.click(
        fn=save_crop,
        inputs=[selected_field_id, edit_year, edit_crop, year_start, year_end, user_state],
        outputs=[message_box, field_list_table]
    )

    delete_btn.click(
        fn=delete_field,
        inputs=[selected_field_id, year_start, year_end, user_state],
        outputs=[message_box, field_list_table]
    )

    return {
        "field_list_table": field_list_table,
        "year_start": year_start,
        "year_end": year_end,
        "edit_crop": edit_crop,
        "load_fn": load_field_list,
        "init_crop_fn": init_crop_choices,
    }


__all__ = [
    "create_field_list_ui",
    "get_fields_with_yearly_crops",
]
