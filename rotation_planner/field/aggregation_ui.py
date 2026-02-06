"""
rotation_planner.field.aggregation_ui - 面積集計表 Gradio UIモジュール

portal.pyに統合するためのUIコンポーネント。
作物×地目のクロス集計表、CSV出力、畑地化補助金サマリを表示。

Usage:
    from rotation_planner.field.aggregation_ui import create_aggregation_ui

    # portal.py 内で
    with gr.Tab("面積集計"):
        components = create_aggregation_ui(user_state)
"""

import datetime
import os
import tempfile

import gradio as gr
import pandas as pd
from typing import Dict, Any, Tuple, Optional

from .crud import get_user_id_from_state
from .aggregation_service import (
    get_cross_tabulation_for_user,
    export_cross_tabulation_csv,
    get_subsidy_summary,
)
from rotation_planner.common import (
    format_error,
    format_info,
    format_success,
    format_warning,
)


# =============================================================================
# UI操作関数
# =============================================================================

def on_calculate(year, state) -> Tuple[pd.DataFrame, str]:
    """集計ボタン処理"""
    user_id = get_user_id_from_state(state)
    if not user_id:
        return pd.DataFrame(), format_error("ログインしてください")

    try:
        year_int = int(year)
    except (TypeError, ValueError):
        return pd.DataFrame(), format_error("年度を正しく入力してください")

    raw_df, display_df = get_cross_tabulation_for_user(user_id, year_int)

    if display_df.empty:
        return pd.DataFrame(), format_warning("データがありません。作付けポリゴンを登録してください。")

    return display_df, format_success(f"{year_int}年度の集計表を表示しました")


def on_export_csv(year, state) -> Tuple[Optional[str], str]:
    """CSV出力処理"""
    user_id = get_user_id_from_state(state)
    if not user_id:
        return None, format_error("ログインしてください")

    try:
        year_int = int(year)
    except (TypeError, ValueError):
        return None, format_error("年度を正しく入力してください")

    csv_content = export_cross_tabulation_csv(user_id, year_int)

    if not csv_content or csv_content.strip() == '\ufeff':
        return None, format_warning("出力するデータがありません")

    # 一時ファイルに書き出し
    tmpdir = tempfile.gettempdir()
    filepath = os.path.join(tmpdir, f"cross_tabulation_{year_int}.csv")
    with open(filepath, 'w', encoding='utf-8-sig') as f:
        f.write(csv_content)

    return filepath, format_success(f"{year_int}年度の集計表をCSV出力しました")


def on_show_subsidy(state) -> Tuple[pd.DataFrame, str]:
    """補助金サマリ表示処理"""
    user_id = get_user_id_from_state(state)
    if not user_id:
        return pd.DataFrame(), format_error("ログインしてください")

    summary = get_subsidy_summary(user_id)

    if not summary:
        return pd.DataFrame(), format_info("畑地化済みのポリゴンがありません")

    df = pd.DataFrame(summary)
    df.columns = ['ほ場ID', '面積(ha)', '畑地化開始年', '残り年数']

    return df, format_success(f"畑地化補助金サマリ: {len(summary)}件")


def load_aggregation_data(state) -> Tuple[pd.DataFrame, pd.DataFrame, str]:
    """初期データ読み込み（タブ選択時）"""
    user_id = get_user_id_from_state(state)
    if not user_id:
        return pd.DataFrame(), pd.DataFrame(), format_info("ログインしてください")

    current_year = datetime.date.today().year

    raw_df, display_df = get_cross_tabulation_for_user(user_id, current_year)
    summary = get_subsidy_summary(user_id)

    subsidy_df = pd.DataFrame()
    if summary:
        subsidy_df = pd.DataFrame(summary)
        subsidy_df.columns = ['ほ場ID', '面積(ha)', '畑地化開始年', '残り年数']

    if display_df.empty:
        msg = format_info("データがありません。作付けポリゴンを登録してください。")
    else:
        msg = format_success(f"{current_year}年度の集計表を表示しました")

    return display_df, subsidy_df, msg


# =============================================================================
# メインUIコンポーネント
# =============================================================================

def create_aggregation_ui(user_state: gr.State) -> Dict[str, Any]:
    """
    面積集計UIコンポーネントを作成

    Args:
        user_state: ユーザー情報を保持するgr.State

    Returns:
        components: UI操作に必要なコンポーネントの辞書
    """

    gr.Markdown("## 📊 面積集計表")

    # 年度入力 + 集計ボタン
    with gr.Row():
        year_input = gr.Number(
            label="年度",
            value=datetime.date.today().year,
            precision=0,
            scale=1,
        )
        calc_btn = gr.Button("📊 集計", variant="primary", scale=1)

    # クロス集計表
    cross_table_df = gr.Dataframe(
        value=pd.DataFrame(),
        label="作物×地目 クロス集計表",
        interactive=False,
    )

    # CSV出力
    with gr.Row():
        csv_btn = gr.Button("📥 CSV出力", scale=1)

    csv_file_output = gr.File(label="ダウンロード")

    gr.Markdown("---")

    # 補助金サマリ
    gr.Markdown("### 🏦 畑地化補助金サマリ")

    subsidy_df = gr.Dataframe(
        value=pd.DataFrame(),
        label="補助金残り年数一覧",
        interactive=False,
    )

    # メッセージ
    message_box = gr.HTML("")

    # ─── イベントハンドラ ───

    calc_btn.click(
        fn=on_calculate,
        inputs=[year_input, user_state],
        outputs=[cross_table_df, message_box],
    )

    csv_btn.click(
        fn=on_export_csv,
        inputs=[year_input, user_state],
        outputs=[csv_file_output, message_box],
    )

    return {
        "cross_table": cross_table_df,
        "subsidy_table": subsidy_df,
        "message_box": message_box,
        "year_input": year_input,
        "csv_file": csv_file_output,
        "load_fn": load_aggregation_data,
    }


# =============================================================================
# 公開API
# =============================================================================

__all__ = [
    "create_aggregation_ui",
    "load_aggregation_data",
]
