"""
ほ場登録アプリ UIモジュール（後方互換性用ラッパー）

このファイルは後方互換性のために残されています。
新規コードでは rotation_planner.field を使用してください。

Usage:
    # 旧方式（後方互換性あり）
    from field_ui import create_field_register_ui

    # 新方式（推奨）
    from rotation_planner.field import create_field_register_ui
"""

import warnings

# 新モジュールから全てインポート
from rotation_planner.field import (
    # 定数
    DEFAULT_LAT,
    DEFAULT_LNG,
    DEFAULT_ZOOM,
    NOMINATIM_URL,
    # 面積計算
    calculate_area_from_coords,
    m2_to_a,
    m2_to_ha,
    # 住所検索
    search_address,
    # 地図生成
    generate_map_html,
    # ヘルパー
    get_user_id_from_state,
    get_username_from_state,
    # データ取得
    get_user_fields,
    fields_to_dataframe,
    get_fields_json_for_map,
    # CRUD操作
    register_field_with_state,
    delete_field_with_state,
    # 履歴
    get_field_history_with_state,
    # CSV出力
    export_csv_with_state,
    # UI
    create_field_register_ui,
    search_and_move_map,
    update_map_with_search,
    refresh_map,
    load_initial_data,
)

# 後方互換性のための別名
update_map_with_search_state = update_map_with_search
refresh_map_with_state = refresh_map
load_initial_data_with_state = load_initial_data


# =============================================================================
# 公開API（後方互換性維持）
# =============================================================================

__all__ = [
    # 定数
    "DEFAULT_LAT",
    "DEFAULT_LNG",
    "DEFAULT_ZOOM",
    "NOMINATIM_URL",
    # 面積計算
    "calculate_area_from_coords",
    "m2_to_a",
    "m2_to_ha",
    # 住所検索
    "search_address",
    # 地図生成
    "generate_map_html",
    # ヘルパー
    "get_user_id_from_state",
    "get_username_from_state",
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
    # UI
    "create_field_register_ui",
    "search_and_move_map",
    "update_map_with_search",
    "update_map_with_search_state",  # 後方互換性
    "refresh_map",
    "refresh_map_with_state",  # 後方互換性
    "load_initial_data",
    "load_initial_data_with_state",  # 後方互換性
]


# =============================================================================
# 単独起動用（デバッグ・テスト用）
# =============================================================================

if __name__ == "__main__":
    import gradio as gr
    from rotation_planner.common import authenticate

    with gr.Blocks(title="ほ場登録アプリ（テスト）") as demo:
        gr.Markdown("# 🗺️ ほ場登録アプリ（UIモジュールテスト）")

        # テスト用ユーザー状態
        user_state = gr.State({"user_id": 1, "username": "test", "display_name": "テストユーザー"})

        # UIコンポーネント作成
        components = create_field_register_ui(user_state)

        # 初期データロード
        demo.load(
            fn=components["load_fn"],
            inputs=[user_state],
            outputs=[components["field_table"], components["map_html"], components["welcome_msg"], components["field_id_input"]]
        )

    demo.launch(server_port=7862, auth=authenticate)
