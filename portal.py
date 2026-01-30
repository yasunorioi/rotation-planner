"""
農業管理アプリ 統合ポータル - Gradio Application（複数農家対応版）
全機能を1つのアプリに統合し、認証を一元管理
"""

import gradio as gr
import os
from typing import Optional, Dict, Any

os.environ["GRADIO_ANALYTICS_ENABLED"] = "False"

# 認証・DBアクセス
from rotation_planner.common import (
    authenticate, get_user_info, is_admin_role,
    ROLE_ADMIN, ROLE_JA_STAFF, ROLE_FARMER,
    FieldRepository, PlanRepository, JAStaffRepository, UserRepository,
)

# UIモジュール
from rotation_planner.app import create_rotation_planner_ui
from rotation_planner.pesticide import create_pesticide_order_ui
from rotation_planner.field import create_field_register_ui, create_crop_settings_ui

# =============================================================================
# 定数
# =============================================================================

# ロール表示名
ROLE_DISPLAY = {
    "admin": "管理者",
    "ja_staff": "JA職員",
    "farmer": "農家",
}

# =============================================================================
# UI生成ヘルパー
# =============================================================================

def create_user_header(username: str) -> str:
    """ユーザー情報ヘッダーを生成"""
    user = get_user_info(username)
    if not user:
        return ""

    display_name = user.get("display_name", username)
    role = user.get("role", "farmer")
    role_display = ROLE_DISPLAY.get(role, role)

    # ロールに応じた色
    role_color = {
        "admin": "#dc3545",
        "ja_staff": "#28a745",
        "farmer": "#007bff",
    }.get(role, "#6c757d")

    return f"""
    <div style="
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 15px 20px;
        border-radius: 8px;
        margin-bottom: 20px;
        display: flex;
        justify-content: space-between;
        align-items: center;
    ">
        <div>
            <span style="font-size: 1.2em;">👤 ようこそ <strong>{display_name}</strong> 様</span>
        </div>
        <div style="display: flex; align-items: center; gap: 15px;">
            <span style="
                background: {role_color};
                padding: 5px 12px;
                border-radius: 20px;
                font-size: 0.9em;
            ">{role_display}</span>
            <a href="/logout" style="
                background: #dc3545;
                color: white;
                padding: 5px 12px;
                border-radius: 5px;
                text-decoration: none;
                font-size: 0.9em;
            ">ログアウト</a>
        </div>
    </div>
    """


def create_stats_card(username: str) -> str:
    """統計情報カードを生成"""
    user = get_user_info(username)
    if not user:
        return ""

    role = user.get("role", "farmer")

    try:
        if role in ["admin", "ja_staff"]:
            # JA職員・管理者: 組織全体の統計
            stats = JAStaffRepository.get_aggregate_stats(org_id=1)
            return f"""
            <div style="
                background: #f8f9fa;
                padding: 15px;
                border-radius: 8px;
                margin: 10px 0;
            ">
                <h4 style="margin-top: 0;">📊 組織統計</h4>
                <div style="display: flex; gap: 20px; flex-wrap: wrap;">
                    <div><strong>農家数:</strong> {stats.get('farmer_count', 0)}</div>
                    <div><strong>ほ場数:</strong> {stats.get('field_count', 0)}</div>
                    <div><strong>総面積:</strong> {stats.get('total_area_ha', 0):.1f} ha</div>
                </div>
            </div>
            """
        else:
            # 農家: 自分のデータ
            farmer_id = user.get("farmer_id")
            if farmer_id:
                try:
                    user_id = int(farmer_id)
                    fields = FieldRepository.get_fields(user_id)
                    plans = PlanRepository.get_plans(user_id)
                    total_area = sum(f.get('area_ha', 0) for f in fields)
                    return f"""
                    <div style="
                        background: #f8f9fa;
                        padding: 15px;
                        border-radius: 8px;
                        margin: 10px 0;
                    ">
                        <h4 style="margin-top: 0;">📊 マイデータ</h4>
                        <div style="display: flex; gap: 20px; flex-wrap: wrap;">
                            <div><strong>ほ場数:</strong> {len(fields)}</div>
                            <div><strong>総面積:</strong> {total_area:.1f} ha</div>
                            <div><strong>輪作計画:</strong> {len(plans)} 件</div>
                        </div>
                    </div>
                    """
                except (ValueError, TypeError):
                    pass
    except Exception as e:
        pass

    return ""


def get_user_state_from_request(request: gr.Request) -> Dict[str, Any]:
    """リクエストからユーザー状態を構築"""
    if not request or not hasattr(request, 'username') or not request.username:
        return {}

    username = request.username
    user = get_user_info(username)
    if not user:
        return {}

    # DBからuser_idを取得
    db_user = UserRepository.get_user_by_username(username)
    user_id = db_user.get('id') if db_user else None

    return {
        "user_id": user_id,
        "username": username,
        "display_name": user.get("display_name", username),
        "role": user.get("role", "farmer"),
        "farmer_id": user.get("farmer_id"),
        "org_id": db_user.get("org_id") if db_user else None,
    }


# =============================================================================
# メインアプリケーション
# =============================================================================

def create_app():
    """統合Gradioアプリを作成"""

    with gr.Blocks(title="農業管理アプリ 統合ポータル", theme=gr.themes.Soft()) as app:

        # 状態管理
        user_state = gr.State({})

        # ユーザーヘッダー
        user_header = gr.HTML("")
        stats_card = gr.HTML("")

        gr.Markdown("""
        # 🚜 農業管理アプリ 統合ポータル

        北海道畑作農家向けの農業管理アプリ群です。
        1回のログインで全ての機能をご利用いただけます。
        """)

        with gr.Tabs() as tabs:
            # =================================================================
            # 🏠 ホームタブ（全ロール共通）
            # =================================================================
            with gr.TabItem("🏠 ホーム", id="home"):
                gr.Markdown("""
                ## 📋 ワークフロー

                ```
                1. 🗺️ ほ場登録 → 地図上でほ場を登録
                2. 🌾 輪作計画 → 過去データから最適な輪作計画を生成
                3. 💊 農薬発注 → 輪作計画から農薬必要量を算出
                ```

                ---

                ## 🖥️ 機能一覧

                | タブ | 機能 | 説明 |
                |------|------|------|
                | 🗺️ ほ場登録 | ほ場管理 | 地図上でポリゴン描画、面積自動計算 |
                | 🌾 輪作計画 | 計画生成 | OR-Toolsによる最適化、制約考慮 |
                | 💊 農薬発注 | 発注計算 | 防除マスタに基づく必要量算出 |
                | 📊 農家一覧 | 組織管理 | JA職員・管理者向け |
                | ⚙️ 管理 | システム管理 | 管理者向け |
                """)

                gr.Markdown("---")

                gr.Markdown("""
                ## 📝 今日のタスク

                - [ ] ほ場情報の確認・更新
                - [ ] 輪作計画の生成・確認
                - [ ] 農薬発注リストの作成
                """)

            # =================================================================
            # 🗺️ ほ場登録タブ（farmer, ja_staff, admin）
            # =================================================================
            with gr.TabItem("🗺️ ほ場登録", id="field") as field_tab:
                gr.Markdown("# 🗺️ ほ場登録アプリ")
                gr.Markdown("""
                地図上でポリゴンを描画し、ほ場の位置と面積を登録します。
                登録したデータは「輪作計画メーカー」で使用できます。
                """)
                field_components = create_field_register_ui(user_state)

            # =================================================================
            # 🌱 作物設定タブ（farmer, ja_staff, admin）
            # =================================================================
            with gr.TabItem("🌱 作物設定", id="crop_settings") as crop_settings_tab:
                crop_settings_components = create_crop_settings_ui(user_state)

            # =================================================================
            # 🌾 輪作計画タブ（farmer, ja_staff, admin）
            # =================================================================
            with gr.TabItem("🌾 輪作計画", id="rotation") as rotation_tab:
                gr.Markdown("# 🌾 輪作計画メーカー")
                gr.Markdown("""
                過去の作付データから、将来の輪作計画を自動生成します。

                ## 使い方
                1. **登録済みほ場を使う** または **CSVファイルをアップロード**
                2. 作物・制約を設定
                3. 「計画を生成」ボタンをクリック
                """)

                # 輪作計画UIを埋め込み
                # Note: create_rotation_planner_ui は gr.Blocks を返すが、
                # ここでは内部のUIが構築されることを期待
                from rotation_planner.app import (
                    DEFAULT_CROPS, DEFAULT_PREFERRED_TRANSITIONS, DEFAULT_MAIN_CROPS,
                    APP_DIR, build_constraints_table, update_constraints_table,
                    update_constraints_from_csv, run_optimization
                )

                with gr.Row():
                    gr.DownloadButton("📥 サンプルCSV", value=os.path.join(APP_DIR, "template_example.csv"))
                    gr.DownloadButton("📥 空テンプレート", value=os.path.join(APP_DIR, "template_empty.csv"))

                gr.Markdown("""
                ### ⛔ 固定の禁止遷移
                - **てんさい→秋小麦**: 作期重複
                - **春小麦→秋小麦**: 病害対策
                - **連作禁止**: 同一作物の連続年作付はNG
                """)

                with gr.Row():
                    with gr.Column(scale=1):
                        gr.Markdown("## 📂 入力")

                        # 登録済みほ場を使うボタン
                        with gr.Row():
                            load_registered_fields_btn = gr.Button(
                                "📋 登録済みほ場を読み込む",
                                variant="secondary"
                            )
                            fields_status = gr.Textbox(
                                label="",
                                interactive=False,
                                show_label=False,
                                max_lines=1
                            )

                        csv_file = gr.File(label="CSVファイル（または上のボタンで登録済みほ場を使用）", file_types=[".csv"])

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

                        tensai_required = gr.Checkbox(value=False, label="てんさい必須（毎年1ほ場以上）")
                        infer_unknown = gr.Checkbox(value=True, label="空欄を推論で補完（*マーク付き）")
                        district_grouping = gr.Checkbox(value=True, label="地区まとめを優先")

                        gr.Markdown("## 🌱 作物マスター")
                        crop_text = gr.Textbox(
                            value="\n".join(DEFAULT_CROPS),
                            label="作物リスト（改行区切り）",
                            lines=8
                        )

                    with gr.Column(scale=1):
                        gr.Markdown("## ⚙️ 制約設定")

                        constraints_file = gr.File(
                            label="制約CSV（オプション）",
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

                        forbidden_text = gr.Textbox(value="", label="追加禁止遷移", placeholder="from->to, from->to, ...")
                        preferred_text = gr.Textbox(value=DEFAULT_PREFERRED_TRANSITIONS, label="優先遷移")
                        main_crops_text = gr.Textbox(value=DEFAULT_MAIN_CROPS, label="主作物")

                # 制約テーブル更新イベント
                crop_text.change(fn=update_constraints_table, inputs=[crop_text, constraints_table], outputs=[constraints_table])
                constraints_file.change(fn=update_constraints_from_csv, inputs=[constraints_file], outputs=[constraints_table])

                run_btn = gr.Button("🚀 計画を生成", variant="primary", size="lg")

                gr.Markdown("## 📊 結果")
                message_box_rotation = gr.Textbox(label="実行結果", lines=5, interactive=False)

                with gr.Tabs():
                    with gr.TabItem("ほ場×年 計画表"):
                        result_table = gr.Dataframe(label="ほ場別計画", interactive=False, wrap=True)
                    with gr.TabItem("年別 面積合計"):
                        summary_table = gr.Dataframe(label="年別作物面積(ha)", interactive=False, wrap=True)

                csv_download = gr.File(label="📥 計画CSVダウンロード")

                run_btn.click(
                    fn=run_optimization,
                    inputs=[csv_file, area_unit, n_years, crop_text, constraints_table,
                            forbidden_text, preferred_text, main_crops_text, unknown_mode,
                            tensai_required, precision_mode, infer_unknown, district_grouping],
                    outputs=[result_table, summary_table, csv_download, message_box_rotation]
                )

                # 登録済みほ場を読み込むボタンのイベント
                def load_registered_fields(user_state_dict):
                    """登録済みほ場からCSVを生成して読み込む"""
                    if not user_state_dict or not user_state_dict.get("user_id"):
                        return None, "エラー: ログインが必要です"

                    from rotation_planner.field import export_csv_with_state
                    csv_path, message = export_csv_with_state(user_state_dict)

                    if csv_path:
                        return csv_path, message
                    else:
                        return None, message

                load_registered_fields_btn.click(
                    fn=load_registered_fields,
                    inputs=[user_state],
                    outputs=[csv_file, fields_status]
                )

            # =================================================================
            # 💊 農薬発注タブ（farmer, ja_staff, admin）
            # =================================================================
            with gr.TabItem("💊 農薬発注", id="pesticide") as pesticide_tab:
                gr.Markdown("# 💊 農薬発注アプリ")
                create_pesticide_order_ui(user_state)

            # =================================================================
            # 📊 農家一覧タブ（ja_staff, admin のみ）
            # =================================================================
            with gr.TabItem("📊 農家一覧", id="farmers", visible=False) as farmers_tab:
                gr.Markdown("## 👥 組織内農家一覧")
                gr.Markdown("*JA職員・管理者のみ表示*")

                farmers_table = gr.Dataframe(
                    headers=["ID", "ユーザー名", "表示名", "ほ場数", "総面積(ha)"],
                    label="農家一覧"
                )

                def load_farmers():
                    try:
                        farmers = JAStaffRepository.get_all_farmers(org_id=1)
                        return [[
                            f.get('id'),
                            f.get('username'),
                            f.get('display_name'),
                            f.get('field_count', 0),
                            f"{f.get('total_area_ha', 0):.2f}"
                        ] for f in farmers]
                    except:
                        return []

                refresh_farmers_btn = gr.Button("🔄 更新")
                refresh_farmers_btn.click(fn=load_farmers, outputs=[farmers_table])

            # =================================================================
            # 💊 防除マスタ管理タブ（ja_staff, admin のみ）
            # =================================================================
            with gr.TabItem("💊 防除マスタ", id="pesticide_master", visible=False) as pesticide_master_tab:
                from pesticide_master_ui import create_pesticide_master_ui
                pesticide_master_components = create_pesticide_master_ui()

            # =================================================================
            # ⚙️ 管理タブ（admin のみ）
            # =================================================================
            with gr.TabItem("⚙️ 管理", id="admin", visible=False) as admin_tab:
                from admin_ui import create_admin_ui
                admin_components = create_admin_ui()

        # =================================================================
        # ロード時の処理
        # =================================================================
        def on_app_load(request: gr.Request):
            """アプリロード時の初期化処理"""
            if not request or not hasattr(request, 'username') or not request.username:
                return {}, "", "", gr.update(visible=False), gr.update(visible=False), gr.update(visible=False)

            username = request.username

            # ユーザー状態を構築
            user_state_dict = get_user_state_from_request(request)
            role = user_state_dict.get("role", "farmer")

            # ヘッダー生成
            header_html = create_user_header(username)
            stats_html = create_stats_card(username)

            # タブの表示制御
            show_farmers = role in ["admin", "ja_staff"]
            show_pesticide_master = role in ["admin", "ja_staff"]  # JA職員・管理者のみ
            show_admin = role == "admin"

            return (
                user_state_dict,
                header_html,
                stats_html,
                gr.update(visible=show_farmers),
                gr.update(visible=show_pesticide_master),
                gr.update(visible=show_admin)
            )

        # ほ場登録タブの初期化（user_state更新後に実行）
        def init_field_tab(user_state_dict):
            """ほ場登録タブの初期化"""
            if not user_state_dict or not user_state_dict.get("user_id"):
                return None, None, "", ""

            from rotation_planner.field import load_initial_data
            return load_initial_data(user_state_dict)

        # 作物設定タブの初期化
        def init_crop_settings_tab(user_state_dict):
            """作物設定タブの初期化"""
            if not user_state_dict or not user_state_dict.get("user_id"):
                import pandas as pd
                return [], pd.DataFrame(columns=["ID", "作物名", "親作物"]), ""

            from rotation_planner.field import load_crop_settings
            return load_crop_settings(user_state_dict)

        # ほ場登録の作物プルダウンを初期化
        def init_crop_dropdown(user_state_dict):
            """作物プルダウンの初期化"""
            from rotation_planner.field import get_crop_choices
            return get_crop_choices(user_state_dict)

        app.load(
            fn=on_app_load,
            outputs=[user_state, user_header, stats_card, farmers_tab, pesticide_master_tab, admin_tab]
        ).then(
            fn=init_field_tab,
            inputs=[user_state],
            outputs=[
                field_components["field_table"],
                field_components["map_html"],
                field_components["welcome_msg"],
                field_components["field_id_input"]
            ]
        ).then(
            fn=init_crop_settings_tab,
            inputs=[user_state],
            outputs=[
                crop_settings_components["crop_checkboxes"],
                crop_settings_components["custom_crops_table"],
                crop_settings_components["message"]
            ]
        ).then(
            fn=init_crop_dropdown,
            inputs=[user_state],
            outputs=[field_components["crop_input"]]
        )

        # 作物設定保存後にほ場登録の作物プルダウンを更新
        crop_settings_components["save_master_btn"].click(
            fn=init_crop_dropdown,
            inputs=[user_state],
            outputs=[field_components["crop_input"]]
        )

        crop_settings_components["add_custom_btn"].click(
            fn=init_crop_dropdown,
            inputs=[user_state],
            outputs=[field_components["crop_input"]]
        )

    return app


# =============================================================================
# メイン
# =============================================================================

import os
DEBUG_MODE = os.environ.get('DEBUG', '1') == '1'  # デフォルトON、本番では DEBUG=0 で起動

CUSTOM_HEAD = """
<script>
var DEBUG = """ + ('true' if DEBUG_MODE else 'false') + """;
window.addEventListener('message', function(event) {
    if (event.data && event.data.type === 'polygon_coordinates') {
        if (DEBUG) console.log('[PORTAL] Received polygon coords');
        var textareas = document.querySelectorAll('textarea');
        for (var i = 0; i < textareas.length; i++) {
            var label = textareas[i].closest('.wrap, .gradio-textbox, .block');
            if (label && label.textContent && label.textContent.includes('座標データ')) {
                if (DEBUG) console.log('[PORTAL] Found textarea');
                textareas[i].value = event.data.coordinates;
                textareas[i].dispatchEvent(new Event('input', { bubbles: true }));
                return;
            }
        }
        var el = document.querySelector('#coords_input textarea');
        if (el) {
            if (DEBUG) console.log('[PORTAL] Found by elem_id');
            el.value = event.data.coordinates;
            el.dispatchEvent(new Event('input', { bubbles: true }));
        }
    }
});
if (DEBUG) console.log('[PORTAL] Debug mode ON');
</script>
"""

if __name__ == "__main__":
    app = create_app()
    import os
    # HF Spaces環境では認証なし・SSRなしで起動
    if os.environ.get("SPACE_ID"):
        app.launch(ssr_mode=False)
    else:
        app.launch(
            server_name="0.0.0.0",
            server_port=7863,
            share=False,
            auth=authenticate
        )
