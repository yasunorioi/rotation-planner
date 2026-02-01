"""
農薬発注アプリ UIモジュール

Gradio UIコンポーネントを提供。
portal.pyへの統合、および単独起動の両方に対応。
"""

import gradio as gr
import pandas as pd
from typing import Dict, Any

# 同一パッケージからインポート
from .calculator import calculate_pesticide_requirements
from .master import (
    load_pesticide_master_from_db,
    load_pesticide_master_csv,
)
from .rotation import (
    load_rotation_plan_from_db,
    get_user_plans_for_dropdown,
    has_saved_plans,
)
from .pdf_export import generate_pesticide_order_pdf, check_pdf_support

# DBアクセス
try:
    from rotation_planner.common import UserRepository
    from rotation_planner.common.db_access import PesticideOrderRepository
except ImportError:
    UserRepository = None
    PesticideOrderRepository = None

# 年度ユーティリティ
try:
    from rotation_planner.common.year_utils import (
        get_default_target_year,
        generate_year_choices,
    )
except ImportError:
    get_default_target_year = None
    generate_year_choices = None


# =============================================================================
# JA職員向け集計機能
# =============================================================================

# JAStaffRepository インポート
try:
    from rotation_planner.common.db_access import JAStaffRepository
except ImportError:
    JAStaffRepository = None


def get_all_farmers_orders(org_id: int, start_date: str = None, end_date: str = None) -> pd.DataFrame:
    """
    全農家の発注状況を取得（JA職員用）

    Args:
        org_id: 組織ID
        start_date: 開始日（任意）
        end_date: 終了日（任意）

    Returns:
        発注状況のDataFrame
    """
    if JAStaffRepository is None:
        return pd.DataFrame(columns=['農家名', '発注日', '農薬名', '数量', '単位', '状態'])

    try:
        orders = JAStaffRepository.get_orders_by_org(org_id, start_date, end_date)
        if not orders:
            return pd.DataFrame(columns=['農家名', '発注日', '農薬名', '数量', '単位', '状態'])

        rows = []
        for order in orders:
            farmer_name = order.get('farmer_name', order.get('username', '不明'))
            created_at = str(order.get('created_at', ''))[:10]
            order_data = order.get('order_data', {})
            status = order.get('status', 'draft')

            # サマリから農薬情報を展開
            summary = order_data.get('summary', [])
            if summary:
                for item in summary:
                    rows.append({
                        '農家名': farmer_name,
                        '発注日': created_at,
                        '農薬名': item.get('pesticide_name') or item.get('農薬名', ''),
                        '数量': item.get('amount') or item.get('必要量', 0),
                        '単位': item.get('unit') or item.get('単位', ''),
                        '状態': status,
                    })
            else:
                # サマリがない場合も1行表示
                rows.append({
                    '農家名': farmer_name,
                    '発注日': created_at,
                    '農薬名': order.get('order_name', ''),
                    '数量': '-',
                    '単位': '-',
                    '状態': status,
                })

        return pd.DataFrame(rows)

    except Exception as e:
        print(f"get_all_farmers_orders error: {e}")
        return pd.DataFrame(columns=['農家名', '発注日', '農薬名', '数量', '単位', '状態'])


def get_aggregate_pesticide_orders(org_id: int, target_year: str = None) -> pd.DataFrame:
    """
    組織全体の農薬発注集計（JA職員用）

    Args:
        org_id: 組織ID
        target_year: 対象年（任意）

    Returns:
        農薬別集計のDataFrame
    """
    if JAStaffRepository is None:
        return pd.DataFrame(columns=['農薬名', '総必要量', '単位', '発注農家数'])

    try:
        aggregates = JAStaffRepository.get_aggregate_orders_by_org(org_id, target_year)
        if not aggregates:
            return pd.DataFrame(columns=['農薬名', '総必要量', '単位', '発注農家数'])

        rows = []
        for item in aggregates:
            rows.append({
                '農薬名': item.get('pesticide_name', ''),
                '総必要量': item.get('total_quantity', 0),
                '単位': item.get('unit', ''),
                '発注農家数': item.get('farmer_count', 0),
            })

        return pd.DataFrame(rows)

    except Exception as e:
        print(f"get_aggregate_pesticide_orders error: {e}")
        return pd.DataFrame(columns=['農薬名', '総必要量', '単位', '発注農家数'])


# =============================================================================
# 処理関数
# =============================================================================

def process_order_db(plan_id, target_year, area_unit, user_state):
    """発注処理を実行（DB専用）

    Args:
        plan_id: 計画ID
        target_year: 対象年
        area_unit: 面積単位
        user_state: ユーザー状態
    """

    user_info = user_state or {}
    org_id = user_info.get('org_id')

    # 輪作計画読み込み（DBから）
    if plan_id is None:
        return None, None, None, "エラー: 輪作計画を選択してください"
    rotation_df, year_cols, error = load_rotation_plan_from_db(plan_id)
    if error:
        return None, None, None, error

    # マスタ読み込み（DBから）
    master_df = load_pesticide_master_from_db(org_id)

    if master_df.empty:
        # フォールバック: CSVから読み込み
        master_df = load_pesticide_master_csv()

    if master_df.empty:
        return None, None, None, "エラー: 防除マスタが見つかりません。「防除マスタ」タブで登録してください。"

    # 計算実行
    summary_df, detail_df, message = calculate_pesticide_requirements(
        rotation_df, year_cols, target_year, master_df, area_unit, None
    )

    if summary_df is None:
        return None, None, None, message

    # CSV出力
    csv_path = "/tmp/農薬発注.csv"
    summary_df.to_csv(csv_path, index=False, encoding='utf-8-sig')

    return summary_df, detail_df, csv_path, message


def generate_pdf_from_results(summary_df, detail_df, order_name, target_year):
    """計算結果からPDFを生成

    Args:
        summary_df: サマリーDataFrame
        detail_df: 詳細DataFrame
        order_name: 発注名
        target_year: 対象年

    Returns:
        (pdf_path, message)
    """
    if summary_df is None or (hasattr(summary_df, 'empty') and summary_df.empty):
        return None, "エラー: 先に「発注リスト作成」を実行してください"

    # 発注名のデフォルト
    if not order_name or order_name.strip() == "":
        order_name = "農薬発注"

    # 対象年のデフォルト
    if not target_year:
        target_year = "不明"

    try:
        pdf_path = "/tmp/農薬発注リスト.pdf"
        result = generate_pesticide_order_pdf(
            summary_df, detail_df, order_name, target_year, pdf_path
        )
        if result:
            return result, f"✅ PDFを生成しました: {order_name}"
        else:
            return None, "エラー: PDF生成に失敗しました"
    except Exception as e:
        return None, f"エラー: {str(e)}"


def get_available_years_from_db(plan_id):
    """DBの輪作計画から選択可能な年を取得

    デフォルト選択ロジック:
    - 3月まで: 当年度（例: 2026年3月 → R7）
    - 4月から: 翌年度（例: 2026年4月 → R8）
    """
    if plan_id is None:
        return gr.update(choices=[], value=None)

    try:
        rotation_df, year_cols, error = load_rotation_plan_from_db(plan_id)
        if error or not year_cols:
            return gr.update(choices=[], value=None)

        # 📍を除去して年リストを作成
        years = [c.replace('📍', '') for c in year_cols]

        # デフォルト年度を決定
        default_year = None
        if get_default_target_year:
            target_year = get_default_target_year()  # 例: "R8"
            if target_year in years:
                default_year = target_year

        # デフォルトがなければ最新年を選択
        if default_year is None and years:
            default_year = years[-1]

        return gr.update(choices=years, value=default_year)
    except:
        return gr.update(choices=[], value=None)


def load_user_plans(user_state):
    """ユーザーの輪作計画一覧を読み込み"""
    user_info = user_state or {}
    user_id = user_info.get('user_id')
    if not user_id:
        return gr.update(choices=[], value=None)

    plans = get_user_plans_for_dropdown(user_id)
    if not plans:
        return gr.update(choices=[], value=None)

    return gr.update(choices=plans, value=plans[0][1] if plans else None)


# =============================================================================
# DB保存・読み込み関数
# =============================================================================

def save_order_to_db(order_name, target_year, plan_id, area_unit, summary_df, detail_df, user_state):
    """発注リストをDBに保存"""
    if PesticideOrderRepository is None:
        return "エラー: DB機能が利用できません"

    user_info = user_state or {}
    user_id = user_info.get('user_id')

    if not user_id:
        return "エラー: ログインしてください"

    if not order_name or order_name.strip() == "":
        return "エラー: 発注名を入力してください"

    if summary_df is None or (hasattr(summary_df, 'empty') and summary_df.empty):
        return "エラー: 先に「発注リスト作成」を実行してください"

    try:
        # DataFrameをdict形式に変換
        summary_data = summary_df.to_dict('records') if hasattr(summary_df, 'to_dict') else []
        detail_data = detail_df.to_dict('records') if detail_df is not None and hasattr(detail_df, 'to_dict') else []

        order_data = {
            'name': order_name.strip(),
            'target_year': target_year,
            'rotation_plan_id': plan_id,
            'area_unit': area_unit,
            'order_data': {
                'summary': summary_data,
                'details': detail_data
            }
        }

        order_id = PesticideOrderRepository.create_order(user_id, order_data)
        return f"✅ 保存完了（ID: {order_id}）"

    except Exception as e:
        return f"エラー: {str(e)}"


def load_saved_orders(user_state):
    """保存済み発注一覧を読み込み"""
    if PesticideOrderRepository is None:
        return pd.DataFrame(columns=['ID', '発注名', '対象年', 'ステータス', '作成日'])

    user_info = user_state or {}
    user_id = user_info.get('user_id')

    if not user_id:
        return pd.DataFrame(columns=['ID', '発注名', '対象年', 'ステータス', '作成日'])

    try:
        orders = PesticideOrderRepository.get_orders(user_id)
        if not orders:
            return pd.DataFrame(columns=['ID', '発注名', '対象年', 'ステータス', '作成日'])

        rows = []
        for o in orders:
            rows.append({
                'ID': o['id'],
                '発注名': o['name'],
                '対象年': o['target_year'],
                'ステータス': o['status'],
                '作成日': str(o['created_at'])[:10] if o.get('created_at') else ''
            })
        return pd.DataFrame(rows)

    except Exception:
        return pd.DataFrame(columns=['ID', '発注名', '対象年', 'ステータス', '作成日'])


def load_order_from_db(orders_df, selected_index, user_state):
    """選択した発注をDBから読み込み"""
    if PesticideOrderRepository is None:
        return None, None, "エラー: DB機能が利用できません"

    if orders_df is None or orders_df.empty:
        return None, None, "エラー: 一覧を更新してください"

    if selected_index is None or len(selected_index) == 0:
        return None, None, "エラー: 発注を選択してください"

    try:
        # 選択行のIDを取得
        row_idx = selected_index[0] if isinstance(selected_index, list) else selected_index
        order_id = int(orders_df.iloc[row_idx]['ID'])

        order = PesticideOrderRepository.get_order(order_id)
        if not order:
            return None, None, f"エラー: ID {order_id} の発注が見つかりません"

        order_data = order.get('order_data', {})
        summary_data = order_data.get('summary', [])
        detail_data = order_data.get('details', [])

        summary_df = pd.DataFrame(summary_data) if summary_data else None
        detail_df = pd.DataFrame(detail_data) if detail_data else None

        return summary_df, detail_df, f"✅ 「{order['name']}」を読み込みました"

    except Exception as e:
        return None, None, f"エラー: {str(e)}"


def delete_saved_order(orders_df, selected_index, user_state):
    """選択した発注を削除"""
    if PesticideOrderRepository is None:
        return orders_df, "エラー: DB機能が利用できません"

    if orders_df is None or orders_df.empty:
        return orders_df, "エラー: 一覧を更新してください"

    if selected_index is None or len(selected_index) == 0:
        return orders_df, "エラー: 削除する発注を選択してください"

    try:
        row_idx = selected_index[0] if isinstance(selected_index, list) else selected_index
        order_id = int(orders_df.iloc[row_idx]['ID'])
        order_name = orders_df.iloc[row_idx]['発注名']

        success = PesticideOrderRepository.delete_order(order_id)
        if success:
            # 一覧を再取得
            new_df = load_saved_orders(user_state)
            return new_df, f"✅ 「{order_name}」を削除しました"
        else:
            return orders_df, f"エラー: 削除に失敗しました"

    except Exception as e:
        return orders_df, f"エラー: {str(e)}"


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

    gr.Markdown("""
    輪作計画から年間の農薬必要量を算出します。

    ## 使い方
    1. 登録済みの輪作計画を選択
    2. 対象年を選択
    3. 「発注リスト作成」ボタンをクリック
    """)

    with gr.Row():
        with gr.Column(scale=1):
            # 輪作計画選択
            plan_dropdown = gr.Dropdown(
                label="登録済み輪作計画",
                choices=[],
                value=None,
                interactive=True
            )
            refresh_plans_btn = gr.Button("🔄 計画一覧を更新", size="sm")

            target_year = gr.Dropdown(
                label="対象年",
                choices=[],
                value=None
            )

            area_unit = gr.Radio(
                choices=["ha", "a"],
                value="ha",
                label="面積単位（輪作計画の単位）"
            )

            submit_btn = gr.Button("発注リスト作成", variant="primary")

        with gr.Column(scale=2):
            message_output = gr.Textbox(
                label="処理結果",
                lines=5
            )

            with gr.Row():
                csv_output = gr.File(
                    label="CSVダウンロード"
                )
                pdf_output = gr.File(
                    label="PDFダウンロード"
                )

            pdf_btn = gr.Button("📄 PDFダウンロード", variant="secondary")
            pdf_message = gr.Textbox(label="PDF生成結果", interactive=False, visible=False)

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

    # =================================================================
    # 💾 DBに保存セクション
    # =================================================================
    gr.Markdown("---")
    gr.Markdown("## 💾 発注リストを保存")

    with gr.Row():
        order_name_input = gr.Textbox(
            label="発注名",
            placeholder="例: 2026年度 春季発注",
            scale=3
        )
        save_btn = gr.Button("💾 DBに保存", variant="secondary", scale=1)

    save_result = gr.Textbox(label="保存結果", interactive=False)

    # =================================================================
    # 📋 保存済み発注一覧セクション
    # =================================================================
    with gr.Accordion("📋 保存済み発注一覧", open=False):
        with gr.Row():
            refresh_orders_btn = gr.Button("🔄 一覧更新", size="sm")
            load_order_btn = gr.Button("📂 読み込み", size="sm")
            delete_order_btn = gr.Button("🗑️ 削除", variant="stop", size="sm")

        orders_table = gr.Dataframe(
            label="保存済み発注リスト",
            headers=["ID", "発注名", "対象年", "ステータス", "作成日"],
            interactive=False
        )

        orders_message = gr.Textbox(label="操作結果", interactive=False)

    # イベント: 計画一覧更新
    refresh_plans_btn.click(
        fn=load_user_plans,
        inputs=[user_state],
        outputs=[plan_dropdown]
    )

    # イベント: 計画選択時に年リスト更新
    plan_dropdown.change(
        fn=get_available_years_from_db,
        inputs=[plan_dropdown],
        outputs=[target_year]
    )

    # イベント: 発注処理
    submit_btn.click(
        fn=process_order_db,
        inputs=[plan_dropdown, target_year, area_unit, user_state],
        outputs=[summary_table, detail_table, csv_output, message_output]
    )

    # イベント: PDF生成
    pdf_btn.click(
        fn=generate_pdf_from_results,
        inputs=[summary_table, detail_table, order_name_input, target_year],
        outputs=[pdf_output, pdf_message]
    )

    # 初期ロード: ユーザーの計画一覧を取得
    user_state.change(
        fn=load_user_plans,
        inputs=[user_state],
        outputs=[plan_dropdown]
    )

    # イベント: DBに保存
    save_btn.click(
        fn=save_order_to_db,
        inputs=[order_name_input, target_year, plan_dropdown, area_unit, summary_table, detail_table, user_state],
        outputs=[save_result]
    )

    # イベント: 保存済み一覧更新
    refresh_orders_btn.click(
        fn=load_saved_orders,
        inputs=[user_state],
        outputs=[orders_table]
    )

    # イベント: 発注読み込み
    load_order_btn.click(
        fn=load_order_from_db,
        inputs=[orders_table, orders_table, user_state],
        outputs=[summary_table, detail_table, orders_message]
    )

    # イベント: 発注削除
    delete_order_btn.click(
        fn=delete_saved_order,
        inputs=[orders_table, orders_table, user_state],
        outputs=[orders_table, orders_message]
    )

    return {
        "plan_dropdown": plan_dropdown,
        "target_year": target_year,
        "area_unit": area_unit,
        "submit_btn": submit_btn,
        "summary_table": summary_table,
        "detail_table": detail_table,
        "csv_output": csv_output,
        "pdf_output": pdf_output,
        "pdf_btn": pdf_btn,
        "message_output": message_output,
        # DB保存関連
        "order_name_input": order_name_input,
        "save_btn": save_btn,
        "save_result": save_result,
        # 保存済み一覧関連
        "orders_table": orders_table,
        "refresh_orders_btn": refresh_orders_btn,
        "load_order_btn": load_order_btn,
        "delete_order_btn": delete_order_btn,
        "orders_message": orders_message,
    }


# =============================================================================
# 単独起動用
# =============================================================================

if __name__ == "__main__":
    # 認証モジュール（単独起動時のみ使用）
    try:
        from rotation_planner.common import authenticate, get_user_info
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
