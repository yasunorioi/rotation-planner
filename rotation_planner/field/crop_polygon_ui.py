"""
rotation_planner.field.crop_polygon_ui - 作付けポリゴン管理 Gradio UIモジュール

portal.pyに統合するためのUIコンポーネント。

Usage:
    from rotation_planner.field.crop_polygon_ui import create_crop_polygon_ui

    # portal.py 内で
    with gr.Tab("作付けポリゴン"):
        components = create_crop_polygon_ui(user_state)
"""

import gradio as gr
import pandas as pd
from datetime import date
from typing import Dict, Any, Tuple

from .crop_polygon_crud import (
    get_crop_polygons_df,
    register_crop_polygon,
    delete_crop_polygon,
    import_crop_from_kml,
    copy_previous_year,
)
from .crud import get_user_id_from_state
from rotation_planner.common import (
    format_error,
    format_warning,
)

# デフォルト作物リスト（将来的に動的取得に変更可能）
DEFAULT_CROP_CHOICES = [
    "だいず", "てんさい", "小麦", "ばれいしょ",
    "スイートコーン", "にんじん", "たまねぎ", "かぼちゃ",
]


# =============================================================================
# UI操作関数
# =============================================================================

def load_crop_polygon_data(
    field_id: int,
    year: int,
    state: Dict[str, Any]
) -> Tuple[pd.DataFrame, str]:
    """ほ場・年度を指定してポリゴン一覧を表示"""
    user_id = get_user_id_from_state(state)
    if not user_id:
        return pd.DataFrame(), format_error("ログインしてください")

    fid = int(field_id) if field_id else None
    yr = int(year) if year else None

    df = get_crop_polygons_df(state, field_id=fid, year=yr)
    count = len(df)
    msg = f"{count}件の作付けポリゴンを表示しています"
    if fid:
        msg += f"（ほ場ID: {fid}）"
    if yr:
        msg += f"（{yr}年度）"

    return df, msg


def _register_handler(
    field_id: int,
    year: int,
    crop_name: str,
    geometry_text: str,
    notes: str,
    state: Dict[str, Any]
) -> Tuple[pd.DataFrame, str]:
    """新規登録ハンドラ"""
    if not field_id:
        return get_crop_polygons_df(state), format_warning("ほ場IDを選択してください")
    if not year:
        return get_crop_polygons_df(state), format_warning("年度を入力してください")

    return register_crop_polygon(
        state=state,
        field_id=int(field_id),
        year=int(year),
        crop_name=crop_name,
        geometry_text=geometry_text,
        notes=notes,
    )


def _import_kml_handler(
    crop_name: str,
    kml_file,
    field_id: int,
    year: int,
    state: Dict[str, Any]
) -> Tuple[pd.DataFrame, str]:
    """KMLインポートハンドラ"""
    if not kml_file:
        return get_crop_polygons_df(state), format_warning("KMLファイルを選択してください")
    if not field_id:
        return get_crop_polygons_df(state), format_warning("ほ場IDを選択してください")

    return import_crop_from_kml(
        state=state,
        file=kml_file,
        field_id=int(field_id),
        year=int(year),
        crop_name=crop_name,
    )


def _copy_year_handler(
    from_year: int,
    to_year: int,
    state: Dict[str, Any]
) -> Tuple[pd.DataFrame, str]:
    """前年コピーハンドラ"""
    if not from_year or not to_year:
        return get_crop_polygons_df(state), format_warning("コピー元・先の年度を指定してください")

    return copy_previous_year(
        state=state,
        from_year=int(from_year),
        to_year=int(to_year),
    )


def _delete_handler(
    polygon_id: int,
    state: Dict[str, Any]
) -> Tuple[pd.DataFrame, str]:
    """削除ハンドラ"""
    if not polygon_id:
        return get_crop_polygons_df(state), format_warning("削除するポリゴンIDを入力してください")

    return delete_crop_polygon(
        state=state,
        polygon_id=int(polygon_id),
    )


def _get_field_choices(state: Dict[str, Any]):
    """ユーザーのほ場一覧をDropdown選択肢として取得"""
    from rotation_planner.common import FieldRepository
    user_id = get_user_id_from_state(state)
    if not user_id:
        return gr.Dropdown(choices=[], value=None)

    try:
        fields = FieldRepository.get_fields(user_id)
        choices = [(f"{f['field_code']} - {f['name']}", f["id"]) for f in fields]
        return gr.Dropdown(choices=choices)
    except Exception:
        return gr.Dropdown(choices=[], value=None)


# =============================================================================
# メインUIコンポーネント
# =============================================================================

def create_crop_polygon_ui(user_state: gr.State) -> Dict[str, Any]:
    """
    作付けポリゴン管理UIコンポーネントを作成

    Args:
        user_state: ユーザー情報を保持するgr.State

    Returns:
        components: UI操作に必要なコンポーネントの辞書
    """
    current_year = date.today().year

    gr.Markdown("## 🌾 作付けポリゴン管理")

    # ── 表示セクション ──
    with gr.Row():
        field_dropdown = gr.Dropdown(
            label="ほ場選択",
            choices=[],
            value=None,
            scale=2,
        )
        year_input = gr.Number(
            label="年度",
            value=current_year,
            precision=0,
            scale=1,
        )
        load_btn = gr.Button("📋 表示", scale=1)

    crop_table = gr.Dataframe(
        value=pd.DataFrame(columns=["ID", "ほ場ID", "年度", "作物名", "面積(ha)", "メモ"]),
        label="作付けポリゴン一覧",
        interactive=False,
    )

    # ── 新規登録 ──
    gr.Markdown("---")
    gr.Markdown("### 📝 新規登録")
    with gr.Row():
        reg_crop = gr.Dropdown(
            label="作物名",
            choices=DEFAULT_CROP_CHOICES,
            allow_custom_value=True,
            scale=1,
        )
        reg_geojson = gr.Textbox(
            label="GeoJSONテキスト",
            placeholder='{"type":"Polygon","coordinates":[[[lng,lat],...]]}',
            lines=3,
            scale=2,
        )
    with gr.Row():
        reg_notes = gr.Textbox(
            label="メモ",
            placeholder="任意のメモ",
            scale=2,
        )
        reg_btn = gr.Button("✅ 登録", variant="primary", scale=1)

    # ── KMLインポート ──
    gr.Markdown("---")
    gr.Markdown("### 📥 KMLインポート")
    with gr.Row():
        kml_crop = gr.Dropdown(
            label="作物名",
            choices=DEFAULT_CROP_CHOICES,
            allow_custom_value=True,
            scale=1,
        )
        kml_file = gr.File(
            label="KMLファイル",
            file_types=[".kml", ".kmz"],
            scale=2,
        )
    kml_btn = gr.Button("📂 インポート")

    # ── 前年コピー ──
    gr.Markdown("---")
    gr.Markdown("### 📋 前年コピー")
    with gr.Row():
        copy_from = gr.Number(
            label="コピー元年度",
            value=current_year - 1,
            precision=0,
            scale=1,
        )
        gr.Markdown("→", elem_classes=["center-text"])
        copy_to = gr.Number(
            label="コピー先年度",
            value=current_year,
            precision=0,
            scale=1,
        )
        copy_btn = gr.Button("📋 前年コピー", scale=1)

    # ── 削除 ──
    gr.Markdown("---")
    gr.Markdown("### 🗑️ 削除")
    with gr.Row():
        del_id = gr.Number(
            label="ポリゴンID",
            precision=0,
            scale=1,
        )
        del_btn = gr.Button("🗑️ 削除", variant="stop", scale=1)

    # ── メッセージ ──
    message_box = gr.HTML("")

    # =================================================================
    # イベントハンドラ
    # =================================================================

    load_btn.click(
        fn=load_crop_polygon_data,
        inputs=[field_dropdown, year_input, user_state],
        outputs=[crop_table, message_box],
    )

    reg_btn.click(
        fn=_register_handler,
        inputs=[field_dropdown, year_input, reg_crop, reg_geojson, reg_notes, user_state],
        outputs=[crop_table, message_box],
    )

    kml_btn.click(
        fn=_import_kml_handler,
        inputs=[kml_crop, kml_file, field_dropdown, year_input, user_state],
        outputs=[crop_table, message_box],
    )

    copy_btn.click(
        fn=_copy_year_handler,
        inputs=[copy_from, copy_to, user_state],
        outputs=[crop_table, message_box],
    )

    del_btn.click(
        fn=_delete_handler,
        inputs=[del_id, user_state],
        outputs=[crop_table, message_box],
    )

    return {
        "crop_polygon_table": crop_table,
        "message_box": message_box,
        "field_dropdown": field_dropdown,
        "year_input": year_input,
        "load_fn": load_crop_polygon_data,
    }
