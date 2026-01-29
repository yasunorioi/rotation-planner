"""
農薬発注アプリ UIモジュール

Gradio UIコンポーネントを提供。
portal.pyへの統合、および単独起動の両方に対応。
"""

import gradio as gr
import pandas as pd
import os
from typing import Dict, Any, Tuple, Optional

# 同一パッケージからインポート
from .calculator import (
    calculate_pesticide_requirements,
    load_rotation_plan,
    load_inventory_csv,
)
from .master import (
    load_pesticide_master_from_db,
    load_pesticide_master_csv,
    get_default_master_path,
)

# DBアクセス
try:
    from db_access import UserRepository
except ImportError:
    UserRepository = None


# =============================================================================
# JA職員向け集計機能
# =============================================================================

def get_all_farmers_orders() -> pd.DataFrame:
    """全農家の発注状況を取得（JA職員用）"""
    # 将来の拡張用
    return pd.DataFrame(columns=['農家名', '発注日', '農薬名', '数量', '単位', '状態'])


def get_aggregate_pesticide_orders(org_id: int = None) -> pd.DataFrame:
    """組織全体の農薬発注集計（JA職員用）"""
    # 将来の拡張用
    return pd.DataFrame(columns=['農薬名', '総必要量', '単位', '発注農家数'])


# =============================================================================
# 処理関数
# =============================================================================

def process_order(csv_file, target_year, area_unit, master_file, inventory_file, user_state):
    """発注処理を実行"""

    if csv_file is None:
        return None, None, None, "エラー: 輪作計画CSVをアップロードしてください"

    user_info = user_state or {}
    org_id = user_info.get('org_id')

    # マスタ読み込み（DB優先、なければCSV）
    if master_file is not None:
        master_df = pd.read_csv(master_file.name, encoding='utf-8')
    else:
        master_df = load_pesticide_master_from_db(org_id)

    if master_df.empty:
        # フォールバック: CSVから読み込み
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

    # 在庫警告をメッセージに追加
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

        # 📍を除去して年リストを作成
        years = [c.replace('📍', '') for c in year_cols]
        return gr.update(choices=years, value=years[-1] if years else None)
    except:
        return gr.update(choices=[], value=None)


# =============================================================================
# UIコンポーネント
# =============================================================================

def create_pesticide_order_ui(user_state: gr.State) -> Dict[str, Any]:
    """
    農薬発注UIコンポーネントを作成

    Args:
        user_state: ユーザー情報を保持するgr.State
                    {'user_id': int, 'username': str, 'role': str, 'org_id': int, ...}

    Returns:
        components: UI操作に必要なコンポーネントの辞書
    """

    APP_DIR = os.path.dirname(get_default_master_path())

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
            gr.File(value=template_path, label="防除マスタテンプレート")
        inventory_template_path = os.path.join(APP_DIR, 'inventory_template.csv')
        if os.path.exists(inventory_template_path):
            gr.File(value=inventory_template_path, label="在庫テンプレート")

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
                label="防除マスタCSV（オプション）",
                file_types=[".csv"]
            )

            inventory_input = gr.File(
                label="在庫CSV（オプション）",
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

    gr.Markdown("""
    ---
    ## 📝 注意事項

    - 散布基準: **10a あたり 100L** で計算
    - 希釈倍率の農薬は、散布量から逆算して必要量を算出
    - 対応作物: てんさい、大豆、春小麦、秋小麦（デフォルト）
    """)

    # イベント
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

    return {
        "csv_input": csv_input,
        "target_year": target_year,
        "area_unit": area_unit,
        "master_input": master_input,
        "inventory_input": inventory_input,
        "submit_btn": submit_btn,
        "summary_table": summary_table,
        "detail_table": detail_table,
        "csv_output": csv_output,
        "message_output": message_output,
    }


# =============================================================================
# 単独起動用
# =============================================================================

if __name__ == "__main__":
    # 認証モジュール（単独起動時のみ使用）
    try:
        from auth import authenticate, get_user_info
    except ImportError:
        authenticate = None
        get_user_info = None

    with gr.Blocks(title="農薬発注アプリ（UIモジュールテスト）") as demo:
        gr.Markdown("# 💊 農薬発注アプリ（UIモジュールテスト）")

        # テスト用ユーザー状態
        user_state = gr.State({
            "user_id": 1,
            "username": "test",
            "display_name": "テストユーザー",
            "role": "farmer",
            "org_id": 1
        })

        # UIコンポーネント作成
        components = create_pesticide_order_ui(user_state)

    if authenticate:
        demo.launch(server_port=7861, auth=authenticate)
    else:
        demo.launch(server_port=7861)
