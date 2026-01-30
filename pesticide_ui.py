"""
農薬発注アプリ UIモジュール

portal.py に統合するためのUIコンポーネント。
認証はportal.pyで一元管理するため、このモジュールには含まない。

使用方法:
    from pesticide_ui import create_pesticide_order_ui

    # portal.py内で
    with gr.Tab("農薬発注"):
        create_pesticide_order_ui(user_state)
"""

import gradio as gr
import pandas as pd
import os
from typing import Dict, Tuple, Optional

# ビジネスロジック（pesticide_order.pyから）
from pesticide_order import (
    load_pesticide_master_from_db,
    load_pesticide_master_csv,
    load_inventory_csv,
    load_rotation_plan,
    calculate_pesticide_requirements,
    get_all_farmers_orders,
    get_aggregate_pesticide_orders,
    APP_DIR
)


def create_pesticide_order_ui(user_state: gr.State) -> None:
    """
    農薬発注アプリのUI部分を作成

    Args:
        user_state: ユーザー情報を保持するgr.State（portal.pyから渡される）

    Note:
        - この関数はgr.Blocks/gr.Tabの中で呼び出すこと
        - 認証はportal.pyで一元管理
    """

    # --- ローカル関数（イベントハンドラ） ---

    def process_order(csv_file, target_year, area_unit, master_file, inventory_file, user_info):
        """発注処理を実行"""
        if csv_file is None:
            return None, None, None, "エラー: 輪作計画CSVをアップロードしてください"

        user_data = user_info or {}
        org_id = user_data.get('org_id')

        # マスタ読み込み（DB優先、なければCSV）
        if master_file is not None:
            master_df = pd.read_csv(master_file.name, encoding='utf-8')
        else:
            master_df = load_pesticide_master_from_db(org_id)

        if master_df.empty:
            master_df = load_pesticide_master_csv()

        if master_df.empty:
            return None, None, None, "エラー: 防除マスタが見つかりません"

        # 在庫CSV読み込み（オプション）
        inventory = None
        inventory_warning = ""
        if inventory_file is not None:
            inventory, inventory_warning = load_inventory_csv(inventory_file.name)

        # 輪作計画読み込み
        rotation_df, year_cols, error = load_rotation_plan(csv_file.name)
        if error:
            return None, None, None, error

        # 計算実行
        summary_df, detail_df, message = calculate_pesticide_requirements(
            rotation_df, year_cols, target_year, master_df, area_unit, inventory
        )

        if summary_df is None:
            return None, None, None, message

        if inventory_warning:
            message += f"\n{inventory_warning}"

        if inventory:
            message += f"\n・在庫データ: {len(inventory)}品目読み込み済み"

        # CSV出力
        csv_path = "/tmp/pesticide_order.csv"
        summary_df.to_csv(csv_path, index=False, encoding='utf-8-sig')

        return summary_df, detail_df, csv_path, message

    def get_available_years(csv_file):
        """CSVから選択可能な年を取得"""
        if csv_file is None:
            return gr.update(choices=[], value=None)

        try:
            rotation_df, year_cols, error = load_rotation_plan(csv_file.name)
            if error or not year_cols:
                return gr.update(choices=[], value=None)

            years = [c.replace('📍', '') for c in year_cols]
            return gr.update(choices=years, value=years[-1] if years else None)
        except:
            return gr.update(choices=[], value=None)

    def refresh_ja_data(user_info):
        """JA集計データを更新"""
        org_id = user_info.get('org_id') if user_info else None
        farmer_orders = get_all_farmers_orders()
        aggregate = get_aggregate_pesticide_orders(org_id)
        return farmer_orders, aggregate

    def load_master_table(user_info):
        """防除マスタをロード"""
        org_id = user_info.get('org_id') if user_info else None
        df = load_pesticide_master_from_db(org_id)
        if df.empty:
            return pd.DataFrame(columns=['crop', 'month', 'target', 'pesticide_name', 'dilution_rate', 'amount_per_10a', 'unit'])
        return df[['crop', 'month', 'target', 'pesticide_name', 'dilution_rate', 'amount_per_10a', 'unit']]

    def check_ja_visibility(user_info):
        """JA職員タブの表示制御"""
        if user_info:
            role = user_info.get('role', 'farmer')
            return role in ['admin', 'ja_staff']
        return False

    # --- UI定義 ---

    gr.Markdown("""
    輪作計画CSVから年間の農薬必要量を算出します。

    ## 使い方
    1. 輪作計画メーカーで作成したCSVをアップロード
    2. 対象年を選択
    3. 「発注リスト作成」ボタンをクリック
    """)

    with gr.Accordion("📥 テンプレートダウンロード", open=False):
        template_path = os.path.join(APP_DIR, 'pesticide_template.csv')
        if os.path.exists(template_path):
            gr.File(value=template_path, label="防除マスタテンプレート（編集して作物・農薬を追加可能）")
        inventory_template_path = os.path.join(APP_DIR, 'inventory_template.csv')
        if os.path.exists(inventory_template_path):
            gr.File(value=inventory_template_path, label="在庫テンプレート")

    # メインコンテンツ
    with gr.Tabs():
        # === 発注計算タブ（全ユーザー共通） ===
        with gr.Tab("📋 発注計算"):
            with gr.Row():
                with gr.Column(scale=1):
                    csv_input = gr.File(
                        label="輪作計画CSV",
                        file_types=[".csv"]
                    )

                    target_year = gr.Dropdown(
                        label="対象年",
                        choices=[],
                        value=None
                    )

                    area_unit = gr.Radio(
                        choices=["ha", "a"],
                        value="ha",
                        label="面積単位（輪作計画CSVの単位）"
                    )

                    master_input = gr.File(
                        label="防除マスタCSV（オプション：カスタムマスタを使用する場合）",
                        file_types=[".csv"]
                    )

                    inventory_input = gr.File(
                        label="在庫CSV（オプション：在庫を差し引いて発注量を算出）",
                        file_types=[".csv"]
                    )

                    gr.Markdown("""
                    **在庫CSV形式:**
                    ```
                    農薬名,在庫量,単位
                    トップジンM水和剤,5,L
                    ゲッター水和剤,2,kg
                    ```
                    """)

                    submit_btn = gr.Button("発注リスト作成", variant="primary")

                with gr.Column(scale=2):
                    message_output = gr.Textbox(
                        label="処理結果",
                        lines=5
                    )

                    csv_output = gr.File(
                        label="発注リストCSVダウンロード"
                    )

            gr.Markdown("## 📋 農薬発注リスト（サマリ）")
            summary_table = gr.Dataframe(
                label="農薬別必要量",
                headers=["農薬名", "必要量", "単位", "対象作物", "対象病害虫"],
                wrap=True
            )

            gr.Markdown("## 📅 月別詳細")
            detail_table = gr.Dataframe(
                label="月別・作物別の農薬使用計画",
                headers=["月", "作物", "対象", "農薬名", "必要量", "面積(ha)"],
                wrap=True
            )

        # === JA職員向けタブ（ロールで表示制御は親で行う想定） ===
        with gr.Tab("🏢 JA集計") as ja_tab:
            gr.Markdown("""
            ## 組織内農家の発注集計

            ※ この機能はJA職員・管理者のみ利用可能です。
            """)

            with gr.Row():
                refresh_btn = gr.Button("集計を更新", variant="secondary")

            gr.Markdown("### 農家別発注状況")
            farmer_orders_table = gr.Dataframe(
                label="農家別発注一覧",
                headers=["農家名", "発注日", "農薬名", "数量", "単位", "状態"],
                wrap=True
            )

            gr.Markdown("### 農薬別集計")
            aggregate_table = gr.Dataframe(
                label="農薬別集計",
                headers=["農薬名", "総必要量", "単位", "発注農家数"],
                wrap=True
            )

            refresh_btn.click(
                fn=refresh_ja_data,
                inputs=[user_state],
                outputs=[farmer_orders_table, aggregate_table]
            )

        # === 防除マスタ管理タブ ===
        with gr.Tab("📚 防除マスタ") as master_tab:
            gr.Markdown("""
            ## 防除マスタ管理

            組織の防除マスタを管理します。
            """)

            master_table = gr.Dataframe(
                label="防除マスタ一覧",
                headers=['作物', '月', '対象', '農薬名', '希釈倍率', '10aあたり使用量', '単位'],
                wrap=True
            )

            load_master_btn = gr.Button("マスタを読み込み")
            load_master_btn.click(
                fn=load_master_table,
                inputs=[user_state],
                outputs=[master_table]
            )

    gr.Markdown("""
    ---
    ## 📝 注意事項

    - 散布基準: **10a あたり 100L** で計算
    - 希釈倍率の農薬は、散布量から逆算して必要量を算出
    - 防除マスタは `pesticide_master.csv` を編集して作物・農薬を追加可能
    - 対応作物: てんさい、大豆、春小麦、秋小麦（デフォルト）
    """)

    # イベント接続
    csv_input.change(
        fn=get_available_years,
        inputs=[csv_input],
        outputs=[target_year]
    )

    submit_btn.click(
        fn=process_order,
        inputs=[csv_input, target_year, area_unit, master_input, inventory_input, user_state],
        outputs=[summary_table, detail_table, csv_output, message_output]
    )


# =============================================================================
# 単独起動用（テスト・デバッグ）
# =============================================================================

if __name__ == "__main__":
    from rotation_planner.common import authenticate, get_user_info

    with gr.Blocks(title="農薬発注アプリ（単独起動）") as demo:
        user_state = gr.State({})

        with gr.Row():
            gr.Markdown("# 💊 農薬発注アプリ")
            user_display = gr.Markdown("")
            logout_btn = gr.Button("🚪 ログアウト", link="/logout", size="sm")

        def on_load(request: gr.Request):
            if request and request.username:
                user_info = get_user_info(request.username)
                if user_info:
                    role = user_info.get('role', 'farmer')
                    display_name = user_info.get('display_name', request.username)
                    role_label = {'admin': '管理者', 'ja_staff': 'JA職員', 'farmer': '農家'}.get(role, role)
                    return user_info, f"👤 {display_name}（{role_label}）"
            return {}, ""

        create_pesticide_order_ui(user_state)

        demo.load(fn=on_load, outputs=[user_state, user_display])

    demo.launch(server_port=7861, auth=authenticate)
