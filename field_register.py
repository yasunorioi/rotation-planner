"""
ほ場登録アプリ - Gradio + Leaflet.js（後方互換性用ラッパー）

このファイルは後方互換性のために残されています。
新規コードでは rotation_planner.field を使用してください。

スタンドアロン起動: python field_register.py
ポート: 7862
"""

import gradio as gr
import pandas as pd

# 認証・DBモジュール
from rotation_planner.common import (
    authenticate, get_user_info,
    FieldRepository, CropHistoryRepository, UserRepository,
)

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
    get_user_id_from_username,
    # データ取得
    get_user_fields,
    fields_to_dataframe,
    get_fields_json_for_map,
    # UI
    search_and_move_map,
)


# =============================================================================
# gr.Request版の関数（スタンドアロン起動用）
# =============================================================================

def register_field(
    field_id: str,
    district: str,
    name: str,
    beet_forbidden: bool,
    coords_json: str,
    request: gr.Request
):
    """ほ場を登録（gr.Request版）"""
    import json

    # ユーザー情報取得
    if not request or not request.username:
        return pd.DataFrame(), "エラー: ログインが必要です", "[]"

    user_id = get_user_id_from_username(request.username)
    if not user_id:
        return pd.DataFrame(), "エラー: ユーザー情報が取得できません", "[]"

    # 入力検証
    if not field_id.strip():
        fields = get_user_fields(user_id)
        return fields_to_dataframe(fields), "エラー: ほ場IDを入力してください", get_fields_json_for_map(fields)

    if not coords_json.strip():
        fields = get_user_fields(user_id)
        return fields_to_dataframe(fields), "エラー: 地図上でポリゴンを描画してください", get_fields_json_for_map(fields)

    try:
        coordinates = json.loads(coords_json)
        if len(coordinates) < 3:
            fields = get_user_fields(user_id)
            return fields_to_dataframe(fields), "エラー: 3点以上の頂点が必要です", get_fields_json_for_map(fields)
    except json.JSONDecodeError:
        fields = get_user_fields(user_id)
        return fields_to_dataframe(fields), "エラー: 座標データが不正です", get_fields_json_for_map(fields)

    # 重複チェック
    existing = FieldRepository.get_field_by_code(user_id, field_id.strip())
    if existing:
        fields = get_user_fields(user_id)
        return fields_to_dataframe(fields), f"エラー: ほ場ID '{field_id}' は既に登録されています", get_fields_json_for_map(fields)

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
        new_field_id = FieldRepository.create_field(user_id, field_data)
        message = f"ほ場 '{field_id}' を登録しました（{area_ha:.4f} ha / {area_ha * 100:.2f} a）"
    except Exception as e:
        fields = get_user_fields(user_id)
        return fields_to_dataframe(fields), f"エラー: 登録に失敗しました - {str(e)}", get_fields_json_for_map(fields)

    fields = get_user_fields(user_id)
    return fields_to_dataframe(fields), message, get_fields_json_for_map(fields)


def delete_selected_field(field_id: str, request: gr.Request):
    """選択されたほ場を削除（gr.Request版）"""

    # ユーザー情報取得
    if not request or not request.username:
        return pd.DataFrame(), "エラー: ログインが必要です", "[]"

    user_id = get_user_id_from_username(request.username)
    if not user_id:
        return pd.DataFrame(), "エラー: ユーザー情報が取得できません", "[]"

    if not field_id.strip():
        fields = get_user_fields(user_id)
        return fields_to_dataframe(fields), "エラー: 削除するほ場IDを入力してください", get_fields_json_for_map(fields)

    # ほ場コードで検索
    field = FieldRepository.get_field_by_code(user_id, field_id.strip())
    if not field:
        fields = get_user_fields(user_id)
        return fields_to_dataframe(fields), f"エラー: ほ場 '{field_id}' が見つかりません", get_fields_json_for_map(fields)

    # 削除
    try:
        if FieldRepository.delete_field(field["id"]):
            message = f"ほ場 '{field_id}' を削除しました"
        else:
            message = f"エラー: ほ場 '{field_id}' の削除に失敗しました"
    except Exception as e:
        fields = get_user_fields(user_id)
        return fields_to_dataframe(fields), f"エラー: 削除に失敗しました - {str(e)}", get_fields_json_for_map(fields)

    fields = get_user_fields(user_id)
    return fields_to_dataframe(fields), message, get_fields_json_for_map(fields)


def export_csv(request: gr.Request):
    """CSVファイルをエクスポート（gr.Request版）"""

    # ユーザー情報取得
    if not request or not request.username:
        return None, "エラー: ログインが必要です"

    user_id = get_user_id_from_username(request.username)
    if not user_id:
        return None, "エラー: ユーザー情報が取得できません"

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


def update_map_with_search(lat_str: str, lng_str: str, request: gr.Request):
    """検索結果で地図を更新（HTMLを再生成）"""
    try:
        lat = float(lat_str) if lat_str else DEFAULT_LAT
        lng = float(lng_str) if lng_str else DEFAULT_LNG
    except ValueError:
        lat = DEFAULT_LAT
        lng = DEFAULT_LNG

    # ユーザーのほ場を取得
    fields = []
    if request and request.username:
        user_id = get_user_id_from_username(request.username)
        if user_id:
            fields = get_user_fields(user_id)

    return generate_map_html(lat, lng, 16, fields)


def refresh_map(request: gr.Request):
    """地図を更新"""
    fields = []
    if request and request.username:
        user_id = get_user_id_from_username(request.username)
        if user_id:
            fields = get_user_fields(user_id)

    return generate_map_html(DEFAULT_LAT, DEFAULT_LNG, DEFAULT_ZOOM, fields)


def load_initial_data(request: gr.Request):
    """初期データ読み込み"""
    if not request or not request.username:
        return pd.DataFrame(), "ログインしてください", "[]"

    user_id = get_user_id_from_username(request.username)
    if not user_id:
        return pd.DataFrame(), "ユーザー情報が取得できません", "[]"

    user_info = get_user_info(request.username)
    display_name = user_info.get("display_name", request.username) if user_info else request.username

    fields = get_user_fields(user_id)

    return (
        fields_to_dataframe(fields),
        generate_map_html(DEFAULT_LAT, DEFAULT_LNG, DEFAULT_ZOOM, fields),
        f"ようこそ、{display_name} さん（{len(fields)}件のほ場が登録されています）"
    )


def get_field_history(field_code: str, request: gr.Request) -> str:
    """ほ場の作付履歴を取得"""
    if not request or not request.username:
        return "ログインが必要です"

    user_id = get_user_id_from_username(request.username)
    if not user_id:
        return "ユーザー情報が取得できません"

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
# Gradio アプリケーション（スタンドアロン起動用）
# =============================================================================

def create_app():
    """Gradioアプリを作成"""

    with gr.Blocks(title="ほ場登録アプリ") as app:
        gr.Markdown("""
        # 🗺️ ほ場登録アプリ

        地図上でポリゴンを描画し、ほ場の位置と面積を登録します。
        登録したデータは「輪作計画メーカー」で使用できるCSV形式で出力できます。
        """)

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
                    lines=3
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

        # 初期ロード時にデータを取得
        app.load(
            fn=load_initial_data,
            outputs=[field_table, map_html, welcome_msg]
        )

        # イベントハンドラ
        search_btn.click(
            fn=search_and_move_map,
            inputs=[search_input],
            outputs=[search_result, search_lat, search_lng]
        ).then(
            fn=update_map_with_search,
            inputs=[search_lat, search_lng],
            outputs=[map_html]
        )

        search_input.submit(
            fn=search_and_move_map,
            inputs=[search_input],
            outputs=[search_result, search_lat, search_lng]
        ).then(
            fn=update_map_with_search,
            inputs=[search_lat, search_lng],
            outputs=[map_html]
        )

        register_btn.click(
            fn=register_field,
            inputs=[field_id_input, district_input, name_input, beet_forbidden_input, coords_input],
            outputs=[field_table, message_box, fields_json]
        ).then(
            fn=refresh_map,
            outputs=[map_html]
        )

        delete_btn.click(
            fn=delete_selected_field,
            inputs=[delete_id_input],
            outputs=[field_table, message_box, fields_json]
        ).then(
            fn=refresh_map,
            outputs=[map_html]
        )

        export_btn.click(
            fn=export_csv,
            outputs=[csv_file, export_message]
        )

        history_btn.click(
            fn=get_field_history,
            inputs=[history_id_input],
            outputs=[history_output]
        )

    return app


# =============================================================================
# メイン
# =============================================================================

if __name__ == "__main__":
    app = create_app()
    app.launch(
        server_name="0.0.0.0",
        server_port=7862,
        share=False,
        auth=authenticate,  # 認証機能追加
        theme=gr.themes.Soft()  # Gradio 6.0: theme は launch() に移動
    )
