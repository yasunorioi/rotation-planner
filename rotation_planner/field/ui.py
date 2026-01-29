"""
rotation_planner.field.ui - ほ場登録 Gradio UIモジュール

portal.pyに統合するためのUIコンポーネント。
認証はportal.pyで一元管理するため、このモジュールには含まない。

Usage:
    from rotation_planner.field.ui import create_field_register_ui

    # portal.py 内で
    with gr.Tab("ほ場登録"):
        components = create_field_register_ui(user_state)
"""

import gradio as gr
import pandas as pd
from typing import Dict, Any, Tuple

# 同一パッケージのモジュール
from .map import (
    DEFAULT_LAT,
    DEFAULT_LNG,
    DEFAULT_ZOOM,
    generate_map_html,
    search_address,
)
from .fude_polygon import fetch_fude_polygons_in_bbox
from .crud import (
    get_user_id_from_state,
    get_user_fields,
    get_next_field_id,
    fields_to_dataframe,
    get_fields_json_for_map,
    register_field_with_state,
    delete_field_with_state,
    get_field_history_with_state,
    export_csv_with_state,
)


# =============================================================================
# UI操作関数
# =============================================================================

def search_and_move_map(query: str) -> Tuple[str, str, str]:
    """住所検索して地図を移動"""
    lat, lng, message = search_address(query)

    if lat is not None and lng is not None:
        return message, str(lat), str(lng)
    else:
        return message, "", ""


def _get_fude_polygons_for_area(lat: float, lng: float, zoom: int = 16) -> list:
    """指定位置周辺の筆ポリゴンを取得"""
    # ズームレベルに応じた範囲を計算（おおよそ）
    delta = 0.01 if zoom >= 16 else 0.05
    return fetch_fude_polygons_in_bbox(
        lat - delta, lng - delta,
        lat + delta, lng + delta,
        max_results=200
    )


def update_map_with_search(lat_str: str, lng_str: str, user_state: Dict[str, Any]) -> str:
    """検索結果で地図を更新（HTMLを再生成）"""
    try:
        lat = float(lat_str) if lat_str else DEFAULT_LAT
        lng = float(lng_str) if lng_str else DEFAULT_LNG
    except ValueError:
        lat = DEFAULT_LAT
        lng = DEFAULT_LNG

    # ユーザーのほ場を取得
    user_id = get_user_id_from_state(user_state)
    fields = get_user_fields(user_id) if user_id else []

    # 筆ポリゴンを取得
    fude_polygons = _get_fude_polygons_for_area(lat, lng, 16)

    return generate_map_html(lat, lng, 16, fields, fude_polygons)


def refresh_map(user_state: Dict[str, Any]) -> str:
    """地図を更新"""
    user_id = get_user_id_from_state(user_state)
    fields = get_user_fields(user_id) if user_id else []

    # 筆ポリゴンを取得
    fude_polygons = _get_fude_polygons_for_area(DEFAULT_LAT, DEFAULT_LNG, DEFAULT_ZOOM)

    return generate_map_html(DEFAULT_LAT, DEFAULT_LNG, DEFAULT_ZOOM, fields, fude_polygons)


def load_initial_data(user_state: Dict[str, Any]) -> Tuple[pd.DataFrame, str, str, str]:
    """初期データ読み込み"""
    user_id = get_user_id_from_state(user_state)
    if not user_id:
        return pd.DataFrame(), generate_map_html(), "ログインしてください", ""

    display_name = user_state.get("display_name", user_state.get("username", ""))

    fields = get_user_fields(user_id)

    # 筆ポリゴンを取得
    fude_polygons = _get_fude_polygons_for_area(DEFAULT_LAT, DEFAULT_LNG, DEFAULT_ZOOM)

    # 次のほ場IDを生成
    next_field_id = get_next_field_id(user_id)

    return (
        fields_to_dataframe(fields),
        generate_map_html(DEFAULT_LAT, DEFAULT_LNG, DEFAULT_ZOOM, fields, fude_polygons),
        f"ようこそ、{display_name} さん（{len(fields)}件のほ場が登録されています）",
        next_field_id
    )


# =============================================================================
# メインUIコンポーネント
# =============================================================================

def create_field_register_ui(user_state: gr.State) -> Dict[str, Any]:
    """
    ほ場登録UIコンポーネントを作成

    Args:
        user_state: ユーザー情報を保持するgr.State
                    {'user_id': int, 'username': str, 'display_name': str, ...}

    Returns:
        components: UI操作に必要なコンポーネントの辞書
    """

    # ユーザー情報表示
    welcome_msg = gr.Markdown("")

    with gr.Row():
        with gr.Column(scale=2):
            gr.Markdown("## 🗺️ 地図")

            # 住所検索
            with gr.Row():
                search_input = gr.Textbox(
                    label="住所・地名検索",
                    placeholder="例: 札幌市, 十勝, 美瑛町",
                    scale=3
                )
                search_btn = gr.Button("🔍 検索", scale=1)

            search_result = gr.Textbox(label="検索結果", interactive=False)

            # 隠しフィールド（検索結果の座標）
            search_lat = gr.Textbox(visible=False)
            search_lng = gr.Textbox(visible=False)

            # Leaflet地図（HTML）
            map_html = gr.HTML(
                value=generate_map_html(),
                label="地図"
            )

            gr.Markdown("""
            **使い方:**
            1. 右上の多角形ツール（六角形アイコン）をクリック
            2. 地図上をクリックしてポリゴンの頂点を打つ
            3. 最後にダブルクリックまたは最初の点をクリックして完了
            4. 編集は鉛筆アイコン、削除はゴミ箱アイコン

            **筆ポリゴン機能:**
            - 左下の「筆ポリゴン」チェックボックスをONにすると、農水省の農地区画情報を表示
            - オレンジ色の区画をクリックすると、そのほ場を選択できます
            - ※ズームレベル15以上で表示されます
            """)

        with gr.Column(scale=1):
            gr.Markdown("## 📝 ほ場情報")

            field_id_input = gr.Textbox(
                label="ほ場ID（必須）",
                placeholder="例: F001"
            )

            district_input = gr.Textbox(
                label="地区",
                placeholder="例: 北地区"
            )

            name_input = gr.Textbox(
                label="ほ場名",
                placeholder="例: 北1号"
            )

            beet_forbidden_input = gr.Checkbox(
                label="馬鈴薯・てんさい禁止",
                value=False
            )

            # 座標データ（地図から受け取る）
            coords_input = gr.Textbox(
                label="座標データ（地図から自動入力）",
                placeholder="地図上でポリゴンを描画してください",
                interactive=True,
                lines=3,
                elem_id="coords_input"
            )


            register_btn = gr.Button("✅ 登録", variant="primary", size="lg")

            gr.Markdown("---")

            gr.Markdown("## 🗑️ 削除")
            delete_id_input = gr.Textbox(
                label="削除するほ場ID",
                placeholder="削除したいほ場IDを入力"
            )
            delete_btn = gr.Button("🗑️ 削除", variant="stop")

            gr.Markdown("---")

            gr.Markdown("## 📜 作付履歴")
            history_id_input = gr.Textbox(
                label="ほ場ID",
                placeholder="履歴を見たいほ場ID"
            )
            history_btn = gr.Button("📜 履歴表示")
            history_output = gr.Markdown("")

    gr.Markdown("---")
    gr.Markdown("## 📋 登録済みほ場一覧")

    field_table = gr.Dataframe(
        value=pd.DataFrame(columns=["ID", "ほ場ID", "地区", "ほ場名", "面積(ha)", "面積(a)", "禁止"]),
        label="ほ場一覧",
        interactive=False
    )

    # 隠しフィールド（地図更新用）
    fields_json = gr.Textbox(visible=False, value="[]")

    message_box = gr.Textbox(label="メッセージ", interactive=False)

    gr.Markdown("## 📥 CSV出力")

    with gr.Row():
        export_btn = gr.Button("📥 CSVダウンロード", variant="primary")
        csv_file = gr.File(label="ダウンロード")

    export_message = gr.Textbox(label="出力結果", interactive=False)

    # イベントハンドラ
    search_btn.click(
        fn=search_and_move_map,
        inputs=[search_input],
        outputs=[search_result, search_lat, search_lng]
    ).then(
        fn=update_map_with_search,
        inputs=[search_lat, search_lng, user_state],
        outputs=[map_html]
    )

    search_input.submit(
        fn=search_and_move_map,
        inputs=[search_input],
        outputs=[search_result, search_lat, search_lng]
    ).then(
        fn=update_map_with_search,
        inputs=[search_lat, search_lng, user_state],
        outputs=[map_html]
    )

    register_btn.click(
        fn=register_field_with_state,
        inputs=[field_id_input, district_input, name_input, beet_forbidden_input, coords_input, user_state],
        outputs=[field_table, message_box, fields_json, field_id_input]
    ).then(
        fn=refresh_map,
        inputs=[user_state],
        outputs=[map_html]
    )

    delete_btn.click(
        fn=delete_field_with_state,
        inputs=[delete_id_input, user_state],
        outputs=[field_table, message_box, fields_json]
    ).then(
        fn=refresh_map,
        inputs=[user_state],
        outputs=[map_html]
    )

    export_btn.click(
        fn=export_csv_with_state,
        inputs=[user_state],
        outputs=[csv_file, export_message]
    )

    history_btn.click(
        fn=get_field_history_with_state,
        inputs=[history_id_input, user_state],
        outputs=[history_output]
    )

    # コンポーネント辞書を返す（初期化用に使用）
    return {
        "welcome_msg": welcome_msg,
        "map_html": map_html,
        "field_table": field_table,
        "message_box": message_box,
        "field_id_input": field_id_input,
        "load_fn": load_initial_data,
    }


# =============================================================================
# 公開API
# =============================================================================

__all__ = [
    "create_field_register_ui",
    "search_and_move_map",
    "update_map_with_search",
    "refresh_map",
    "load_initial_data",
]
