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
from rotation_planner.pesticide_record import create_pesticide_record_ui, load_initial_fields
from rotation_planner.field import create_field_register_ui, create_crop_settings_ui
from rotation_planner.field.crud import get_fields_with_history
from rotation_planner.data_management import create_data_management_ui
from rotation_planner.crop_history import create_crop_history_ui

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
            user_id = user.get("id")
            if user_id:
                try:
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

        # DEBUG時のみユーザー切り替えUI表示
        if DEBUG_MODE:
            with gr.Row():
                with gr.Column(scale=3):
                    debug_user_radio = gr.Radio(
                        choices=["admin", "ja_staff", "farmer_demo"],
                        value="farmer_demo",
                        label="🔧 DEBUG: ユーザー切り替え",
                        interactive=True
                    )
                with gr.Column(scale=1):
                    debug_login_btn = gr.Button("ログイン", variant="primary")

            def debug_switch_user(selected_user):
                """DEBUGモードでユーザーを切り替え"""
                user = get_user_info(selected_user)
                if not user:
                    return {}, "", ""

                db_user = UserRepository.get_user_by_username(selected_user)
                user_id = db_user.get('id') if db_user else None

                new_state = {
                    "user_id": user_id,
                    "username": selected_user,
                    "display_name": user.get("display_name", selected_user),
                    "role": user.get("role", "farmer"),
                    "org_id": db_user.get("org_id") if db_user else None,
                }

                header = create_user_header(selected_user)
                stats = create_stats_card(selected_user)

                return new_state, header, stats

            # DEBUGログイン後の初期化チェーンは app.load() の後で設定
            # (コンポーネント定義後に設定するため、ここでは変数のみ保持)
            _debug_login_btn = debug_login_btn
            _debug_user_radio = debug_user_radio
            _debug_switch_user = debug_switch_user

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
            # 🌱 作物設定タブ（farmer, ja_staff, admin）
            # =================================================================
            with gr.TabItem("🌱 作物設定", id="crop_settings") as crop_settings_tab:
                crop_settings_components = create_crop_settings_ui(user_state)

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
            # 📜 作付履歴タブ（farmer, ja_staff, admin）
            # =================================================================
            with gr.TabItem("📜 作付履歴", id="crop_history") as crop_history_tab:
                crop_history_components = create_crop_history_ui(user_state)

            # =================================================================
            # 🌾 輪作計画タブ（farmer, ja_staff, admin）
            # =================================================================
            with gr.TabItem("🌾 輪作計画", id="rotation") as rotation_tab:
                gr.Markdown("# 🌾 輪作計画メーカー")
                gr.Markdown("""
                過去の作付データから、将来の輪作計画を自動生成します。

                ## 使い方
                1. **「登録済みほ場を読み込む」** ボタンをクリック
                2. 作物・制約を設定
                3. 「計画を生成」ボタンをクリック

                ※ ほ場データは「📥 データ管理」タブでインポートできます
                """)

                # 輪作計画UIを埋め込み
                # Note: create_rotation_planner_ui は gr.Blocks を返すが、
                # ここでは内部のUIが構築されることを期待
                from rotation_planner.app import (
                    DEFAULT_CROPS, DEFAULT_PREFERRED_TRANSITIONS, DEFAULT_MAIN_CROPS,
                    get_default_crops,
                    APP_DIR, build_constraints_table, update_constraints_table,
                    update_constraints_from_csv, run_optimization
                )

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
                                variant="primary"
                            )
                            fields_status = gr.Textbox(
                                label="",
                                interactive=False,
                                show_label=False,
                                max_lines=1
                            )

                        # CSVアップロードは廃止（データ管理タブでインポート）
                        csv_file = gr.State(value=None)

                        # DB直接読み込み用 State（登録済みほ場ボタン用）
                        fields_state = gr.State(value=None)
                        past_years_state = gr.State(value=None)

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
                            value="",  # ログイン後に動的に設定
                            label="作物リスト（改行区切り）",
                            lines=8,
                            placeholder="ログイン後に作物リストが表示されます"
                        )

                    with gr.Column(scale=1):
                        gr.Markdown("## ⚙️ 制約設定")

                        # 制約CSVアップロードは廃止（テーブルを直接編集）
                        constraints_file = gr.State(value=None)

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

                run_btn = gr.Button("🚀 計画を生成", variant="primary", size="lg")

                gr.Markdown("## 📊 結果")
                message_box_rotation = gr.Textbox(label="実行結果", lines=5, interactive=False)

                with gr.Tabs():
                    with gr.TabItem("ほ場×年 計画表"):
                        result_table = gr.Dataframe(label="ほ場別計画", interactive=False, wrap=True)
                    with gr.TabItem("年別 面積合計"):
                        summary_table = gr.Dataframe(label="年別作物面積(ha)", interactive=False, wrap=True)

                with gr.Row():
                    csv_download = gr.File(label="📥 計画CSVダウンロード")
                    with gr.Column():
                        plan_name_input = gr.Textbox(label="計画名", placeholder="例: 2026年度計画")
                        save_to_db_btn = gr.Button("💾 DBに保存", variant="secondary")
                        save_result = gr.Textbox(label="保存結果", interactive=False, max_lines=1)

                # DBに保存する関数
                def save_plan_to_db(result_df, plan_name, user_state_dict):
                    """生成した輪作計画をDBに保存"""
                    if result_df is None or len(result_df) == 0:
                        return "エラー: 先に計画を生成してください"

                    if not plan_name or not plan_name.strip():
                        return "エラー: 計画名を入力してください"

                    if not user_state_dict or not user_state_dict.get("user_id"):
                        return "エラー: ログインが必要です"

                    try:
                        user_id = user_state_dict.get("user_id")

                        # ほ場一覧を取得してfield_code -> field_id のマッピング作成
                        fields = FieldRepository.get_fields(user_id)
                        field_code_to_id = {f.get('field_code'): f.get('id') for f in fields}

                        # DataFrameから計画詳細を抽出
                        # result_tableは「ほ場×年」形式: 列名が年度、行がほ場
                        details = []
                        df = result_df

                        # 非年度カラムを除外
                        non_year_cols = ['ほ場ID', 'ほ場名', '地区', '面積', 'field_code', 'field_id', 'name', 'district', 'area']
                        field_col = df.columns[0]  # 最初の列がほ場情報
                        year_cols = [c for c in df.columns if c not in non_year_cols and (str(c).replace('R', '').replace('*', '').isdigit() or str(c).startswith('R'))]

                        for _, row in df.iterrows():
                            field_code = str(row[field_col])
                            field_id = field_code_to_id.get(field_code)
                            if not field_id:
                                continue  # ほ場が見つからない場合はスキップ

                            for year_col in year_cols:
                                crop = str(row.get(year_col, "")).strip()
                                if crop and crop != "nan":
                                    details.append({
                                        "field_id": field_id,
                                        "year": str(year_col).replace('*', ''),  # *を除去
                                        "crop": crop.replace('*', ''),  # *を除去
                                    })

                        if not details:
                            return "エラー: 保存するデータがありません"

                        # 年の範囲を取得（R7形式やR2026形式に対応）
                        def parse_year(y):
                            y_str = str(y)
                            if y_str.startswith("R"):
                                num = y_str[1:]
                                if len(num) <= 2:  # R7 -> 2025 (令和7年)
                                    return 2018 + int(num)
                                else:  # R2026 -> 2026
                                    return int(num)
                            return int(y_str)

                        try:
                            years = [parse_year(d["year"]) for d in details if d.get("year")]
                            start_year = min(years) if years else 2026
                            end_year = max(years) if years else 2030
                        except (ValueError, TypeError):
                            start_year = 2026
                            end_year = 2030

                        # 保存
                        plan_data = {
                            "name": plan_name.strip(),
                            "start_year": start_year,
                            "end_year": end_year,
                            "details": details
                        }
                        plan_id = PlanRepository.create_plan(user_id=user_id, data=plan_data)

                        return f"✅ 計画「{plan_name}」を保存しました（ID: {plan_id}）"

                    except Exception as e:
                        return f"エラー: {str(e)}"

                save_to_db_btn.click(
                    fn=save_plan_to_db,
                    inputs=[result_table, plan_name_input, user_state],
                    outputs=[save_result]
                )

                run_btn.click(
                    fn=run_optimization,
                    inputs=[csv_file, area_unit, n_years, crop_text, constraints_table,
                            forbidden_text, preferred_text, main_crops_text, unknown_mode,
                            tensai_required, precision_mode, infer_unknown, district_grouping,
                            fields_state, past_years_state],
                    outputs=[result_table, summary_table, csv_download, message_box_rotation]
                )

                # 登録済みほ場を読み込むボタンのイベント
                def load_registered_fields(user_state_dict):
                    """登録済みほ場をDBから直接読み込む（CSV経由を廃止）+ 作物リスト更新"""
                    if not user_state_dict or not user_state_dict.get("user_id"):
                        return None, None, None, "エラー: ログインが必要です", ""

                    user_id = user_state_dict.get("user_id")
                    fields, past_years, error = get_fields_with_history(user_id)

                    if error:
                        return None, None, None, error, ""

                    # ユーザーの作物リストを取得
                    crops = get_default_crops(user_id)
                    crops_text = "\n".join(crops) if crops else ""

                    message = f"✅ {len(fields)}件のほ場を読み込みました（{len(past_years)}年分の履歴）"
                    # csv_file は None にリセット、fields/past_years を State に保存
                    return None, fields, past_years, message, crops_text

                load_registered_fields_btn.click(
                    fn=load_registered_fields,
                    inputs=[user_state],
                    outputs=[csv_file, fields_state, past_years_state, fields_status, crop_text]
                )

            # =================================================================
            # 💊 農薬発注タブ（farmer, ja_staff, admin）
            # =================================================================
            with gr.TabItem("💊 農薬発注", id="pesticide") as pesticide_tab:
                gr.Markdown("# 💊 農薬発注アプリ")
                create_pesticide_order_ui(user_state)

            # =================================================================
            # 🧪 防除記録タブ（farmer, ja_staff, admin）
            # =================================================================
            with gr.TabItem("🧪 防除記録", id="pesticide_record") as pesticide_record_tab:
                pesticide_record_components = create_pesticide_record_ui(user_state)

            # =================================================================
            # 📥 データ管理タブ（farmer, ja_staff, admin）
            # =================================================================
            with gr.TabItem("📥 データ管理", id="data_management") as data_management_tab:
                data_management_ui = create_data_management_ui(user_state)

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

        # 作付履歴タブの初期化
        def init_crop_history_tab(user_state_dict):
            """作付履歴タブの初期化"""
            if not user_state_dict or not user_state_dict.get("user_id"):
                import pandas as pd
                return gr.Dropdown(choices=[], value=[]), pd.DataFrame(), ""

            from rotation_planner.crop_history.ui import load_initial_history
            return load_initial_history(user_state_dict)

        # 防除記録タブの初期化
        def init_pesticide_record_tab(user_state_dict):
            """防除記録タブの初期化（ほ場選択肢を設定）"""
            if not user_state_dict or not user_state_dict.get("user_id"):
                empty = gr.Dropdown(choices=[], value=None)
                return empty, empty, empty

            return load_initial_fields(user_state_dict)

        app.load(
            fn=on_app_load,
            outputs=[user_state, user_header, stats_card, farmers_tab, pesticide_master_tab, admin_tab]
        ).then(
            fn=init_crop_settings_tab,
            inputs=[user_state],
            outputs=[
                crop_settings_components["crop_checkboxes"],
                crop_settings_components["custom_crops_table"],
                crop_settings_components["message"]
            ]
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
            fn=init_crop_dropdown,
            inputs=[user_state],
            outputs=[field_components["crop_input"]]
        ).then(
            fn=init_crop_history_tab,
            inputs=[user_state],
            outputs=[
                crop_history_components["field_selector"],
                crop_history_components["history_table"],
                crop_history_components["warning_area"]
            ]
        ).then(
            fn=init_pesticide_record_tab,
            inputs=[user_state],
            outputs=[
                pesticide_record_components["field_dropdown"],
                pesticide_record_components["history_field_filter"],
                pesticide_record_components["edit_field_dropdown"],
            ]
        )

        # DEBUGログイン後の初期化チェーン
        if DEBUG_MODE:
            _debug_login_btn.click(
                fn=_debug_switch_user,
                inputs=[_debug_user_radio],
                outputs=[user_state, user_header, stats_card]
            ).then(
                fn=init_crop_settings_tab,
                inputs=[user_state],
                outputs=[
                    crop_settings_components["crop_checkboxes"],
                    crop_settings_components["custom_crops_table"],
                    crop_settings_components["message"]
                ]
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
                fn=init_crop_dropdown,
                inputs=[user_state],
                outputs=[field_components["crop_input"]]
            ).then(
                fn=init_crop_history_tab,
                inputs=[user_state],
                outputs=[
                    crop_history_components["field_selector"],
                    crop_history_components["history_table"],
                    crop_history_components["warning_area"]
                ]
            ).then(
                fn=init_pesticide_record_tab,
                inputs=[user_state],
                outputs=[
                    pesticide_record_components["field_dropdown"],
                    pesticide_record_components["history_field_filter"],
                    pesticide_record_components["edit_field_dropdown"],
                ]
            )

        # 作物設定変更時（自動保存後）にほ場登録の作物プルダウンを更新
        crop_settings_components["crop_checkboxes"].change(
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
import json
from pathlib import Path

def _load_debug_mode() -> bool:
    """デバッグモードを設定ファイルまたは環境変数から読み込む"""
    # 1. 環境変数が明示的に設定されていればそれを使用
    env_debug = os.environ.get('DEBUG')
    if env_debug is not None:
        return env_debug == '1'

    # 2. 設定ファイルから読み込み
    settings_file = Path(__file__).parent / "data" / "settings.json"
    if settings_file.exists():
        try:
            with open(settings_file, 'r', encoding='utf-8') as f:
                settings = json.load(f)
                return settings.get("debug_mode", False)
        except:
            pass

    # 3. デフォルトは OFF（本番向け）
    return False

DEBUG_MODE = _load_debug_mode()

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
    # DB初期化（テーブルと初期ユーザー作成）
    from rotation_planner.common import init_db
    init_db()

    app = create_app()
    import os
    # HF Spaces環境では認証なし・SSRなしで起動
    if os.environ.get("SPACE_ID"):
        app.launch(ssr_mode=False)
    elif DEBUG_MODE:
        # DEBUG時は認証スキップ（アプリ内でユーザー切り替え）
        app.launch(
            server_name="0.0.0.0",
            server_port=7863,
            share=False
        )
    else:
        # 本番は通常認証
        app.launch(
            server_name="0.0.0.0",
            server_port=7863,
            share=False,
            auth=authenticate
        )
