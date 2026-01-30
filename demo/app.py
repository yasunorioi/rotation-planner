"""
輪作計画メーカー - 統合デモアプリ
Hugging Face Spaces用メインファイル

3つの機能をタブで統合:
- 🌾 輪作計画: 過去データから最適な輪作計画を生成
- 💊 農薬発注: 輪作計画から農薬必要量を算出
- 🗺️ ほ場登録: 地図上でほ場を登録・管理

デモ用ログイン:
- 農家: user1 / demo123
- JA職員: admin / admin123
"""

import gradio as gr
import os

os.environ["GRADIO_ANALYTICS_ENABLED"] = "False"

# =============================================================================
# デモ用認証（ハードコード）
# =============================================================================

# デモ用ユーザー（ユーザ作成・パスワード変更は無効化）
DEMO_USERS = {
    "user1": {
        "password": "demo123",
        "role": "farmer",
        "display_name": "デモ農家",
    },
    "admin": {
        "password": "admin123",
        "role": "ja_staff",
        "display_name": "デモJA職員",
    },
}


def demo_authenticate(username: str, password: str) -> bool:
    """
    デモ用認証関数

    ユーザ作成・パスワード変更機能は無効化
    ハードコードされたユーザーのみ認証可能
    """
    user = DEMO_USERS.get(username)
    if user and user.get("password") == password:
        return True
    return False


def get_demo_user_info(username: str) -> dict:
    """デモ用ユーザー情報取得"""
    user = DEMO_USERS.get(username)
    if user:
        return {
            "username": username,
            "role": user.get("role"),
            "display_name": user.get("display_name"),
        }
    return None

# =============================================================================
# デモUIモジュールのインポート（他の足軽が作成）
# =============================================================================

# 輪作計画デモUI
try:
    from rotation_demo import create_rotation_demo_ui
    ROTATION_AVAILABLE = True
except ImportError:
    ROTATION_AVAILABLE = False
    print("Warning: rotation_demo not available")

# 農薬発注デモUI
try:
    from pesticide_demo import create_pesticide_demo_ui
    PESTICIDE_AVAILABLE = True
except ImportError:
    PESTICIDE_AVAILABLE = False
    print("Warning: pesticide_demo not available")

# ほ場登録デモUI
try:
    from field_demo import create_field_demo_ui
    FIELD_AVAILABLE = True
except ImportError:
    FIELD_AVAILABLE = False
    print("Warning: field_demo not available")


# =============================================================================
# プレースホルダーUI（モジュール未完成時の代替）
# =============================================================================

def create_placeholder_ui(title: str, description: str):
    """モジュール未完成時のプレースホルダーUI"""
    gr.Markdown(f"""
    # {title}

    {description}

    ---

    ## 🚧 現在準備中

    このデモは現在準備中です。しばらくお待ちください。

    ### 予定機能
    - デモデータによる動作確認
    - 主要機能の体験
    - 結果のダウンロード
    """)


# =============================================================================
# メインアプリケーション
# =============================================================================

def create_demo_app():
    """統合デモアプリを作成"""

    with gr.Blocks(
        title="輪作計画メーカー デモ",
        theme=gr.themes.Soft(),
        css="""
        .gradio-container {
            max-width: 1200px !important;
        }
        """
    ) as demo:

        # ヘッダー
        gr.Markdown("""
        # 🌾 輪作計画メーカー - デモ版

        北海道畑作農家向けの農業管理アプリ群のデモ版です。
        実際のデータを使わずに機能を体験できます。

        ---

        ## 📋 ワークフロー

        ```
        1. 🗺️ ほ場登録 → 地図上でほ場を登録（デモデータ使用可）
        2. 🌾 輪作計画 → 過去データから最適な輪作計画を生成
        3. 💊 農薬発注 → 輪作計画から農薬必要量を算出
        ```

        ---
        """)

        # タブで3機能を統合
        with gr.Tabs() as tabs:
            # 🌾 輪作計画タブ
            with gr.TabItem("🌾 輪作計画", id="rotation"):
                if ROTATION_AVAILABLE:
                    create_rotation_demo_ui()
                else:
                    create_placeholder_ui(
                        "🌾 輪作計画メーカー",
                        "過去の作付データ（CSV）から、OR-Toolsによる最適化で将来の輪作計画を自動生成します。"
                    )

            # 💊 農薬発注タブ
            with gr.TabItem("💊 農薬発注", id="pesticide"):
                if PESTICIDE_AVAILABLE:
                    create_pesticide_demo_ui()
                else:
                    create_placeholder_ui(
                        "💊 農薬発注アプリ",
                        "輪作計画CSVから年間の農薬必要量を算出します。防除マスタに基づいて作物ごとの農薬使用量を計算。"
                    )

            # 🗺️ ほ場登録タブ
            with gr.TabItem("🗺️ ほ場登録", id="field"):
                gr.Markdown("""
                # 🗺️ ほ場登録アプリ

                地図上でポリゴンを描画してほ場を登録します。
                正確な面積計算とCSV出力で輪作計画メーカーと連携。

                ---

                ## ⚠️ デモ版では利用できません

                ほ場登録機能は地図表示（Leaflet.js）を使用するため、
                **Hugging Face Spaces のセキュリティ制約により、このデモ版では利用できません。**

                ### 製品版の機能
                - 🗺️ OpenStreetMap + Leaflet.jsによる地図表示
                - 📐 ポリゴン描画によるほ場境界の登録
                - 📏 WGS84楕円体による正確な面積計算
                - 🔍 住所・地名検索（Nominatim API）
                - 📄 輪作計画メーカー形式でのCSV出力

                ---

                **ローカル版をご利用ください:**
                ```bash
                git clone https://github.com/yasunorioi/rotation-planner
                cd rotation-planner
                pip install -r requirements.txt
                python portal.py
                ```
                """)

        # フッター
        gr.Markdown("""
        ---

        ## 📝 注意事項

        - **デモ版のため、データは保存されません**
        - 実際の運用には認証付き版をご利用ください
        - サンプルデータをダウンロードして試すことができます

        ---

        ## 🔗 リンク

        - [GitHub リポジトリ](https://github.com/your-repo/rotation-planner)
        - [ドキュメント](https://your-docs-url.com)

        ---

        **Powered by Gradio + OR-Tools + Leaflet.js**
        """)

    return demo


# =============================================================================
# メイン
# =============================================================================

# 認証有効化フラグ（環境変数で切り替え可能）
ENABLE_AUTH = os.environ.get("DEMO_AUTH", "true").lower() == "true"

if __name__ == "__main__":
    demo = create_demo_app()

    # HF Spaces環境判定
    is_hf_spaces = os.environ.get("SPACE_ID") is not None

    if is_hf_spaces:
        # HF Spacesでは認証なしで起動（server_name指定でlocalhost問題回避）
        print("HF Spaces環境で起動します（認証なし）")
        demo.launch(server_name="0.0.0.0", server_port=7860)
    else:
        # ローカル環境
        launch_kwargs = {
            "server_name": "0.0.0.0",
            "server_port": 7860,
            "share": False,
        }

        if ENABLE_AUTH:
            launch_kwargs["auth"] = demo_authenticate
            launch_kwargs["auth_message"] = """
            ## デモ版ログイン

            以下のアカウントでログインできます:

            | ロール | ユーザー名 | パスワード |
            |--------|-----------|-----------|
            | 農家 | user1 | demo123 |
            | JA職員 | admin | admin123 |
            """
            print("認証有効モードで起動します")
            print("デモ用ログイン: user1/demo123（農家）, admin/admin123（JA職員）")
        else:
            print("認証なしモードで起動します")

        demo.launch(**launch_kwargs)
