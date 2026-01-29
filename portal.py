"""
農業管理アプリ ポータル - Gradio Application（複数農家対応版）
3つのアプリへのランチャー画面 + 認証・ロールベースアクセス制御
"""

import gradio as gr
import os
from typing import Optional, Dict, Any

os.environ["GRADIO_ANALYTICS_ENABLED"] = "False"

# 認証・DBアクセス
from auth import authenticate, get_user_info, is_admin_role, ROLE_ADMIN, ROLE_JA_STAFF, ROLE_FARMER
from db_access import FieldRepository, PlanRepository, JAStaffRepository, UserRepository

# =============================================================================
# 定数
# =============================================================================

APPS = [
    {
        "name": "輪作計画メーカー",
        "port": 7860,
        "file": "app.py",
        "icon": "🌾",
        "description": "過去の作付データ（CSV）から将来の輪作計画を自動生成します。OR-Toolsによる最適化で、連作禁止や面積制約を考慮した計画を立案。",
        "features": [
            "CSV読み込みによる過去作付データ入力",
            "OR-Tools CP-SATソルバーによる最適化",
            "制約設定（面積上限/下限、間隔年数）",
            "ボトルネック分析（感度分析）機能",
        ],
        "roles": ["farmer", "ja_staff", "admin"],  # アクセス可能ロール
    },
    {
        "name": "農薬発注アプリ",
        "port": 7861,
        "file": "pesticide_order.py",
        "icon": "💊",
        "description": "輪作計画CSVから年間の農薬必要量を算出します。防除マスタに基づいて作物ごとの農薬使用量を計算。",
        "features": [
            "輪作計画CSVからの自動読み込み",
            "防除マスタによるカスタマイズ",
            "在庫差し引きによる発注量計算",
            "月別詳細スケジュール表示",
        ],
        "roles": ["farmer", "ja_staff", "admin"],
    },
    {
        "name": "ほ場登録アプリ",
        "port": 7862,
        "file": "field_register.py",
        "icon": "🗺️",
        "description": "地図上でポリゴンを描画してほ場を登録します。正確な面積計算とCSV出力で輪作計画メーカーと連携。",
        "features": [
            "OpenStreetMap + Leaflet.jsによる地図表示",
            "ポリゴン描画によるほ場登録",
            "WGS84楕円体による正確な面積計算",
            "住所・地名検索機能",
        ],
        "roles": ["farmer", "ja_staff", "admin"],
    },
]

# ロール表示名
ROLE_DISPLAY = {
    "admin": "管理者",
    "ja_staff": "JA職員",
    "farmer": "農家",
}

# =============================================================================
# UI生成
# =============================================================================

def create_app_card(app: dict, user_role: str = None) -> str:
    """アプリカードのHTMLを生成"""
    # ロールチェック
    allowed_roles = app.get("roles", ["farmer", "ja_staff", "admin"])
    if user_role and user_role not in allowed_roles:
        return ""  # アクセス不可の場合は表示しない

    features_html = "".join(f"<li>{f}</li>" for f in app["features"])

    return f"""
    <div style="
        border: 1px solid #ddd;
        border-radius: 12px;
        padding: 20px;
        margin: 10px 0;
        background: linear-gradient(135deg, #f8f9fa 0%, #ffffff 100%);
        box-shadow: 0 2px 8px rgba(0,0,0,0.1);
    ">
        <h3 style="margin-top: 0; color: #333;">
            {app["icon"]} {app["name"]}
        </h3>
        <p style="color: #666; line-height: 1.6;">
            {app["description"]}
        </p>
        <details style="margin: 10px 0;">
            <summary style="cursor: pointer; color: #007bff;">機能一覧</summary>
            <ul style="color: #555; margin-top: 10px;">
                {features_html}
            </ul>
        </details>
        <div style="margin-top: 15px;">
            <a href="http://127.0.0.1:{app["port"]}" target="_blank"
               style="
                   display: inline-block;
                   padding: 10px 20px;
                   background: #007bff;
                   color: white;
                   text-decoration: none;
                   border-radius: 6px;
                   font-weight: bold;
               ">
                アプリを開く →
            </a>
            <span style="margin-left: 15px; color: #888; font-size: 0.9em;">
                ポート: {app["port"]} | ファイル: {app["file"]}
            </span>
        </div>
    </div>
    """


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
        <div>
            <span style="
                background: {role_color};
                padding: 5px 12px;
                border-radius: 20px;
                font-size: 0.9em;
            ">{role_display}</span>
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
                # user_idを取得（farmer_idとuser.idの紐付けが必要）
                # 簡易版: farmer_idをintに変換してuser_idとして使用
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


def on_load(request: gr.Request):
    """ページロード時にユーザー情報を取得"""
    if request and hasattr(request, 'username'):
        username = request.username
        user = get_user_info(username)
        if user:
            return (
                create_user_header(username),
                create_stats_card(username),
                user.get("role", "farmer")
            )
    return ("", "", "farmer")


def create_app():
    """Gradioアプリを作成"""

    with gr.Blocks(title="農業管理アプリ ポータル") as app:

        # 状態管理
        user_role = gr.State("farmer")

        # ユーザーヘッダー
        user_header = gr.HTML("")
        stats_card = gr.HTML("")

        gr.Markdown("""
        # 🚜 農業管理アプリ ポータル

        北海道畑作農家向けの農業管理アプリ群です。
        各アプリを事前に起動してから、下のボタンでアクセスしてください。
        """)

        with gr.Tabs() as tabs:
            # アプリ一覧タブ（全ロール共通）
            with gr.TabItem("🖥️ アプリ一覧", id="apps"):
                gr.Markdown("""
                ## 📋 ワークフロー

                ```
                1. ほ場登録アプリ → ほ場をCSV出力
                2. 輪作計画メーカー → CSVを読み込み、輪作計画を生成
                3. 農薬発注アプリ → 輪作計画から農薬必要量を算出
                ```
                """)

                gr.Markdown("## 🖥️ アプリ一覧")

                # アプリカードを表示
                for app_info in APPS:
                    gr.HTML(create_app_card(app_info))

            # JA職員・管理者用タブ
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

                refresh_btn = gr.Button("🔄 更新")
                refresh_btn.click(fn=load_farmers, outputs=[farmers_table])

            # 管理者用タブ
            with gr.TabItem("⚙️ 管理", id="admin", visible=False) as admin_tab:
                gr.Markdown("## ⚙️ システム管理")
                gr.Markdown("*管理者のみ表示*")

                gr.Markdown("""
                ### 機能一覧
                - ユーザー管理
                - 組織設定
                - システム設定
                """)

        gr.Markdown("---")

        gr.Markdown("""
        ## 🚀 起動方法

        各アプリは個別に起動する必要があります。

        ```bash
        cd /home/yasu/multi-agent-shogun/docs/rotation_planner_ui
        source .venv/bin/activate

        # 各アプリを別ターミナルで起動
        python app.py              # 輪作計画メーカー (7860)
        python pesticide_order.py  # 農薬発注アプリ (7861)
        python field_register.py   # ほ場登録アプリ (7862)
        python portal.py           # このポータル (7863)
        ```
        """)

        gr.Markdown("""
        ## 📝 注意事項

        - 各アプリは独立して動作します
        - データはCSVファイルを介して連携します
        - アプリが起動していない場合、リンクをクリックしてもアクセスできません
        """)

        # ロード時の処理
        def update_ui_by_role(request: gr.Request):
            """ロールに応じてUIを更新"""
            header_html, stats_html, role = on_load(request)

            # タブの表示制御
            show_farmers = role in ["admin", "ja_staff"]
            show_admin = role == "admin"

            return (
                header_html,
                stats_html,
                role,
                gr.update(visible=show_farmers),
                gr.update(visible=show_admin)
            )

        app.load(
            fn=update_ui_by_role,
            outputs=[user_header, stats_card, user_role, farmers_tab, admin_tab]
        )

    return app


# =============================================================================
# メイン
# =============================================================================

if __name__ == "__main__":
    app = create_app()
    app.launch(
        server_name="0.0.0.0",
        server_port=7863,
        share=False,
        auth=authenticate  # 認証機能有効化
    )
