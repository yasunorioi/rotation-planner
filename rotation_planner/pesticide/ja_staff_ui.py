"""
JA職員向け集計画面 UIモジュール

農協職員が管轄する全農家の農薬発注状況を一覧・集計する機能。
"""

import gradio as gr
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

# 同一パッケージからインポート
from .ui import get_all_farmers_orders, get_aggregate_pesticide_orders

# DBアクセス
try:
    from rotation_planner.common.db_access import JAStaffRepository
except ImportError:
    JAStaffRepository = None

# エクスポート
try:
    from rotation_planner.common.export import export_ja_aggregate_pesticide_csv
except ImportError:
    export_ja_aggregate_pesticide_csv = None


def load_farmers_list(user_state) -> pd.DataFrame:
    """担当農家一覧を読み込み"""
    user_info = user_state or {}
    org_id = user_info.get('org_id')

    if not org_id or JAStaffRepository is None:
        return pd.DataFrame(columns=['ID', '農家名', 'ほ場数', '総面積(ha)'])

    try:
        farmers = JAStaffRepository.get_all_farmers(org_id)
        rows = []
        for f in farmers:
            rows.append({
                'ID': f.get('id'),
                '農家名': f.get('display_name', f.get('username', '')),
                'ほ場数': f.get('field_count', 0),
                '総面積(ha)': f"{f.get('total_area_ha', 0):.2f}",
            })
        return pd.DataFrame(rows)
    except Exception as e:
        print(f"load_farmers_list error: {e}")
        return pd.DataFrame(columns=['ID', '農家名', 'ほ場数', '総面積(ha)'])


def load_farmers_orders(user_state, start_date, end_date) -> pd.DataFrame:
    """農家別発注状況を読み込み"""
    user_info = user_state or {}
    org_id = user_info.get('org_id')

    if not org_id:
        return pd.DataFrame(columns=['農家名', '発注日', '農薬名', '数量', '単位', '状態'])

    # 日付フォーマット
    start_str = start_date if start_date else None
    end_str = end_date if end_date else None

    return get_all_farmers_orders(org_id, start_str, end_str)


def load_aggregate_orders(user_state, target_year) -> pd.DataFrame:
    """組織全体の農薬発注集計を読み込み"""
    user_info = user_state or {}
    org_id = user_info.get('org_id')

    if not org_id:
        return pd.DataFrame(columns=['農薬名', '総必要量', '単位', '発注農家数'])

    return get_aggregate_pesticide_orders(org_id, target_year if target_year else None)


def export_aggregate_csv(user_state, aggregate_df):
    """集計データをCSVエクスポート"""
    if aggregate_df is None or aggregate_df.empty:
        return None, "エラー: エクスポートするデータがありません"

    try:
        csv_path = "/tmp/JA農薬集計.csv"
        aggregate_df.to_csv(csv_path, index=False, encoding='utf-8-sig')
        return csv_path, "✅ CSVをエクスポートしました"
    except Exception as e:
        return None, f"エラー: {str(e)}"


def load_org_stats(user_state) -> str:
    """組織の統計情報を取得"""
    user_info = user_state or {}
    org_id = user_info.get('org_id')

    if not org_id or JAStaffRepository is None:
        return "統計情報を取得できません"

    try:
        stats = JAStaffRepository.get_aggregate_stats(org_id)
        return f"""
**担当農家数:** {stats.get('farmer_count', 0)} 名
**総ほ場数:** {stats.get('field_count', 0)} 筆
**総面積:** {stats.get('total_area_ha', 0):.2f} ha
"""
    except Exception as e:
        return f"統計情報の取得エラー: {e}"


def create_ja_staff_summary_ui(user_state: gr.State) -> Dict[str, Any]:
    """
    JA職員向け集計画面を作成

    Args:
        user_state: ユーザー情報を保持するgr.State

    Returns:
        UIコンポーネントの辞書
    """

    gr.Markdown("# 📊 JA職員向け 発注集計画面")
    gr.Markdown("管轄する農家の農薬発注状況を一覧・集計できます。")

    # =================================================================
    # 組織統計
    # =================================================================
    with gr.Row():
        with gr.Column(scale=1):
            org_stats = gr.Markdown("*統計を読み込み中...*")
            refresh_stats_btn = gr.Button("🔄 統計更新", size="sm")

    # =================================================================
    # 担当農家一覧
    # =================================================================
    gr.Markdown("## 👥 担当農家一覧")
    farmers_table = gr.Dataframe(
        headers=['ID', '農家名', 'ほ場数', '総面積(ha)'],
        label="農家一覧",
        interactive=False
    )
    refresh_farmers_btn = gr.Button("🔄 農家一覧を更新", size="sm")

    # =================================================================
    # 期間選択・発注状況
    # =================================================================
    gr.Markdown("---")
    gr.Markdown("## 📋 農家別発注状況")

    with gr.Row():
        # デフォルト: 過去30日
        default_start = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        default_end = datetime.now().strftime("%Y-%m-%d")

        start_date_input = gr.Textbox(
            label="開始日",
            value=default_start,
            placeholder="YYYY-MM-DD"
        )
        end_date_input = gr.Textbox(
            label="終了日",
            value=default_end,
            placeholder="YYYY-MM-DD"
        )
        search_orders_btn = gr.Button("🔍 検索", variant="primary")

    orders_table = gr.Dataframe(
        headers=['農家名', '発注日', '農薬名', '数量', '単位', '状態'],
        label="発注状況",
        interactive=False,
        wrap=True
    )

    # =================================================================
    # 組織全体の農薬発注集計
    # =================================================================
    gr.Markdown("---")
    gr.Markdown("## 📊 組織全体の農薬発注集計")

    with gr.Row():
        # 年度選択
        current_year = datetime.now().year
        year_choices = [str(y) for y in range(current_year - 2, current_year + 3)]
        target_year_input = gr.Dropdown(
            label="対象年",
            choices=year_choices,
            value=str(current_year)
        )
        calc_aggregate_btn = gr.Button("📊 集計", variant="primary")

    aggregate_table = gr.Dataframe(
        headers=['農薬名', '総必要量', '単位', '発注農家数'],
        label="農薬別集計",
        interactive=False
    )

    # =================================================================
    # エクスポート
    # =================================================================
    gr.Markdown("---")
    gr.Markdown("## 📥 エクスポート")

    with gr.Row():
        export_csv_btn = gr.Button("📄 CSV出力", variant="secondary")
        csv_output = gr.File(label="CSVダウンロード")

    export_message = gr.Textbox(label="エクスポート結果", interactive=False)

    # =================================================================
    # イベントハンドラ
    # =================================================================

    # 統計更新
    refresh_stats_btn.click(
        fn=load_org_stats,
        inputs=[user_state],
        outputs=[org_stats]
    )

    # 農家一覧更新
    refresh_farmers_btn.click(
        fn=load_farmers_list,
        inputs=[user_state],
        outputs=[farmers_table]
    )

    # 発注検索
    search_orders_btn.click(
        fn=load_farmers_orders,
        inputs=[user_state, start_date_input, end_date_input],
        outputs=[orders_table]
    )

    # 集計
    calc_aggregate_btn.click(
        fn=load_aggregate_orders,
        inputs=[user_state, target_year_input],
        outputs=[aggregate_table]
    )

    # CSVエクスポート
    export_csv_btn.click(
        fn=export_aggregate_csv,
        inputs=[user_state, aggregate_table],
        outputs=[csv_output, export_message]
    )

    # 初期ロード: user_state 変更時
    user_state.change(
        fn=load_org_stats,
        inputs=[user_state],
        outputs=[org_stats]
    )
    user_state.change(
        fn=load_farmers_list,
        inputs=[user_state],
        outputs=[farmers_table]
    )

    return {
        "org_stats": org_stats,
        "farmers_table": farmers_table,
        "orders_table": orders_table,
        "aggregate_table": aggregate_table,
        "start_date_input": start_date_input,
        "end_date_input": end_date_input,
        "target_year_input": target_year_input,
        "csv_output": csv_output,
        "export_message": export_message,
    }
