"""
rotation_planner.field.paddy_ui - 水田ポリゴン管理 Gradio UIモジュール

portal.pyに統合するためのUIコンポーネント。
認証はportal.pyで一元管理するため、このモジュールには含まない。

Usage:
    from rotation_planner.field.paddy_ui import create_paddy_polygon_ui

    # portal.py 内で
    with gr.Tab("水田ポリゴン"):
        components = create_paddy_polygon_ui(user_state)
"""

import gradio as gr
import pandas as pd
from typing import Dict, Any, Tuple, Optional

# 同一パッケージのモジュール
from .paddy_crud import (
    get_paddy_polygons_df,
    register_paddy_polygon,
    delete_paddy_polygon,
    import_paddy_from_kml,
)
from .crud import get_user_id_from_state, get_user_fields

# UI utilities
from rotation_planner.common import (
    format_alert,
    format_success,
    format_error,
    format_warning,
    format_info,
)


# =============================================================================
# UI操作関数
# =============================================================================

def load_field_choices(user_state: Dict[str, Any]) -> gr.Dropdown:
    """
    ユーザーのほ場一覧を取得してDropdownの選択肢を更新

    Args:
        user_state: ユーザー状態

    Returns:
        更新されたDropdown（gr.update）
    """
    user_id = get_user_id_from_state(user_state)
    if not user_id:
        return gr.Dropdown(choices=[], value=None)

    fields = get_user_fields(user_id)
    if not fields:
        return gr.Dropdown(choices=[], value=None)

    # label: "F001 - 北圃場", value: field_id (int)
    choices = []
    for f in fields:
        field_code = f.get('field_code', '')
        field_name = f.get('name', '')
        label = f"{field_code} - {field_name}" if field_name else field_code
        # field_idはDB上のid（主キー）
        field_db_id = f.get('id')
        if field_db_id:
            choices.append((label, field_db_id))

    if choices:
        return gr.Dropdown(choices=choices, value=choices[0][1])
    else:
        return gr.Dropdown(choices=[], value=None)


def load_paddy_data_for_field(field_id: Optional[int], user_state: Dict[str, Any]) -> Tuple[pd.DataFrame, str]:
    """
    指定ほ場の水田ポリゴン一覧を読み込む

    Args:
        field_id: ほ場ID（DBの主キー）
        user_state: ユーザー状態

    Returns:
        (DataFrame, メッセージ)
    """
    if field_id is None:
        return pd.DataFrame(columns=['ID', 'ほ場ID', '面積(ha)', '地目', '畑地化開始年', 'ソース']), format_warning("ほ場を選択してください")

    df = get_paddy_polygons_df(user_state, field_id=field_id)
    if df.empty:
        return df, format_info("水田ポリゴンが登録されていません")
    else:
        return df, format_success(f"{len(df)}件の水田ポリゴンを表示しています")


def register_paddy_ui_wrapper(
    field_id: Optional[int],
    geometry_text: str,
    is_converted: bool,
    conversion_start_year: Optional[float],
    source: str,
    notes: str,
    user_state: Dict[str, Any]
) -> Tuple[pd.DataFrame, str]:
    """
    水田ポリゴン登録UIラッパー

    Args:
        field_id: ほ場ID
        geometry_text: GeoJSON文字列
        is_converted: 畑地化フラグ
        conversion_start_year: 畑地化開始年度（Number型なのでfloat or None）
        source: データソース
        notes: 備考
        user_state: ユーザー状態

    Returns:
        (更新後のDataFrame, メッセージ)
    """
    # バリデーション
    if field_id is None:
        return get_paddy_polygons_df(user_state), format_error("ほ場を選択してください")

    if not geometry_text or geometry_text.strip() == "":
        return get_paddy_polygons_df(user_state), format_error("GeoJSONを入力してください")

    # conversion_start_yearをintに変換（Number型はfloatで渡される）
    start_year_int = None
    if conversion_start_year is not None:
        try:
            start_year_int = int(conversion_start_year)
        except (ValueError, TypeError):
            return get_paddy_polygons_df(user_state), format_error("畑地化開始年度は整数で入力してください")

    # CRUD関数呼び出し
    return register_paddy_polygon(
        state=user_state,
        field_id=field_id,
        geometry_text=geometry_text.strip(),
        is_converted=is_converted,
        conversion_start_year=start_year_int,
        source=source,
        notes=notes.strip() if notes else ""
    )


def delete_paddy_ui_wrapper(polygon_id: Optional[float], user_state: Dict[str, Any]) -> Tuple[pd.DataFrame, str]:
    """
    水田ポリゴン削除UIラッパー

    Args:
        polygon_id: ポリゴンID（Number型なのでfloat or None）
        user_state: ユーザー状態

    Returns:
        (更新後のDataFrame, メッセージ)
    """
    if polygon_id is None:
        return get_paddy_polygons_df(user_state), format_error("削除するポリゴンIDを入力してください")

    try:
        polygon_id_int = int(polygon_id)
    except (ValueError, TypeError):
        return get_paddy_polygons_df(user_state), format_error("ポリゴンIDは整数で入力してください")

    return delete_paddy_polygon(state=user_state, polygon_id=polygon_id_int)


def import_kml_ui_wrapper(
    file,
    field_id: Optional[int],
    is_converted: bool,
    conversion_start_year: Optional[float],
    user_state: Dict[str, Any]
) -> Tuple[pd.DataFrame, str]:
    """
    KML/KMZインポートUIラッパー

    Args:
        file: Gradioファイルオブジェクト
        field_id: ほ場ID
        is_converted: 畑地化フラグ
        conversion_start_year: 畑地化開始年度（Number型なのでfloat or None）
        user_state: ユーザー状態

    Returns:
        (更新後のDataFrame, メッセージ)
    """
    if file is None:
        return get_paddy_polygons_df(user_state), format_error("KML/KMZファイルを選択してください")

    if field_id is None:
        return get_paddy_polygons_df(user_state), format_error("ほ場を選択してください")

    # conversion_start_yearをintに変換
    start_year_int = None
    if conversion_start_year is not None:
        try:
            start_year_int = int(conversion_start_year)
        except (ValueError, TypeError):
            return get_paddy_polygons_df(user_state), format_error("畑地化開始年度は整数で入力してください")

    return import_paddy_from_kml(
        state=user_state,
        file=file,
        field_id=field_id,
        is_converted=is_converted,
        conversion_start_year=start_year_int
    )


def load_initial_data(user_state: Dict[str, Any]) -> Tuple[gr.Dropdown, pd.DataFrame, str]:
    """
    初期データ読み込み

    Args:
        user_state: ユーザー状態

    Returns:
        (ほ場Dropdown, 空のDataFrame, ウェルカムメッセージ)
    """
    user_id = get_user_id_from_state(user_state)
    if not user_id:
        return (
            gr.Dropdown(choices=[], value=None),
            pd.DataFrame(columns=['ID', 'ほ場ID', '面積(ha)', '地目', '畑地化開始年', 'ソース']),
            format_error("ログインしてください")
        )

    display_name = user_state.get("display_name", user_state.get("username", ""))

    # ほ場一覧を取得
    fields = get_user_fields(user_id)
    field_count = len(fields) if fields else 0

    # Dropdown選択肢を生成
    dropdown_update = load_field_choices(user_state)

    return (
        dropdown_update,
        pd.DataFrame(columns=['ID', 'ほ場ID', '面積(ha)', '地目', '畑地化開始年', 'ソース']),
        format_info(f"ようこそ、{display_name} さん（{field_count}件のほ場が登録されています）")
    )


# =============================================================================
# メインUIコンポーネント
# =============================================================================

def create_paddy_polygon_ui(user_state: gr.State) -> Dict[str, Any]:
    """
    水田ポリゴン管理UIコンポーネントを作成

    Args:
        user_state: ユーザー情報を保持するgr.State
                    {'user_id': int, 'username': str, 'display_name': str, ...}

    Returns:
        components: UI操作に必要なコンポーネントの辞書
    """

    gr.Markdown("# 🏞️ 水田ポリゴン管理")
    gr.Markdown("""
    ほ場内の水田ポリゴンを管理します。水田か畑地化済（転換畑）かを記録できます。

    ## 使い方
    1. ほ場を選択して「表示」ボタンをクリック
    2. 新規登録: GeoJSON形式でポリゴンを入力
    3. KMLインポート: Google Earthで作成したKML/KMZファイルから一括登録
    """)

    # ほ場選択
    with gr.Row():
        field_dropdown = gr.Dropdown(
            label="ほ場",
            choices=[],
            value=None,
            interactive=True,
            scale=3
        )
        load_field_btn = gr.Button("表示", variant="primary", scale=1)

    # 水田ポリゴン一覧
    paddy_table = gr.Dataframe(
        value=pd.DataFrame(columns=['ID', 'ほ場ID', '面積(ha)', '地目', '畑地化開始年', 'ソース']),
        label="水田ポリゴン一覧",
        interactive=False,
        wrap=True
    )

    gr.Markdown("---")
    gr.Markdown("## ➕ 新規登録")

    geometry_input = gr.Textbox(
        label="GeoJSON（Polygon形式）",
        placeholder='{"type":"Polygon","coordinates":[[[141.0,43.0],[141.01,43.0],[141.01,43.01],[141.0,43.01],[141.0,43.0]]]}',
        lines=3
    )

    with gr.Row():
        is_converted_input = gr.Checkbox(
            label="畑地化済",
            value=False,
            scale=1
        )
        conversion_start_year_input = gr.Number(
            label="畑地化開始年度",
            precision=0,
            value=None,
            scale=1
        )

    with gr.Row():
        source_dropdown = gr.Dropdown(
            label="ソース",
            choices=["manual", "kml", "maff"],
            value="manual",
            scale=1
        )
        notes_input = gr.Textbox(
            label="メモ",
            placeholder="例: Google Earthから取得",
            lines=1,
            scale=2
        )

    register_btn = gr.Button("✅ 登録", variant="primary")

    gr.Markdown("---")
    gr.Markdown("## 📥 KMLインポート")
    gr.Markdown("Google EarthでKML/KMZファイルを作成してインポートできます。")

    kml_file = gr.File(
        label="KML/KMZファイル",
        file_types=[".kml", ".kmz"],
        type="filepath"
    )

    with gr.Row():
        kml_is_converted = gr.Checkbox(
            label="畑地化済",
            value=False,
            scale=1
        )
        kml_conversion_year = gr.Number(
            label="畑地化開始年度",
            precision=0,
            value=None,
            scale=1
        )

    kml_import_btn = gr.Button("📂 KMLインポート", variant="secondary")

    gr.Markdown("---")
    gr.Markdown("## 🗑️ 削除")

    delete_id = gr.Number(
        label="削除するポリゴンID",
        precision=0,
        placeholder="一覧から削除したいIDを入力"
    )
    delete_btn = gr.Button("🗑️ 削除", variant="stop")

    gr.Markdown("---")

    # メッセージ表示
    message_box = gr.HTML("")

    # =================================================================
    # イベントハンドラ
    # =================================================================

    # ほ場選択 → 水田ポリゴン一覧を表示
    load_field_btn.click(
        fn=load_paddy_data_for_field,
        inputs=[field_dropdown, user_state],
        outputs=[paddy_table, message_box]
    )

    # 新規登録
    register_btn.click(
        fn=register_paddy_ui_wrapper,
        inputs=[
            field_dropdown,
            geometry_input,
            is_converted_input,
            conversion_start_year_input,
            source_dropdown,
            notes_input,
            user_state
        ],
        outputs=[paddy_table, message_box]
    )

    # KMLインポート
    kml_import_btn.click(
        fn=import_kml_ui_wrapper,
        inputs=[
            kml_file,
            field_dropdown,
            kml_is_converted,
            kml_conversion_year,
            user_state
        ],
        outputs=[paddy_table, message_box]
    )

    # 削除
    delete_btn.click(
        fn=delete_paddy_ui_wrapper,
        inputs=[delete_id, user_state],
        outputs=[paddy_table, message_box]
    )

    # コンポーネント辞書を返す（初期化用に使用）
    return {
        "paddy_table": paddy_table,
        "message_box": message_box,
        "field_dropdown": field_dropdown,
        "load_fn": load_initial_data,
    }


# =============================================================================
# 公開API
# =============================================================================

__all__ = [
    "create_paddy_polygon_ui",
    "load_initial_data",
]
