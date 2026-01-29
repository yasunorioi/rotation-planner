"""
防除マスタ管理UI - JA職員向け
防除スケジュール（農薬マスタ）の登録・編集・削除機能
"""

import gradio as gr
import pandas as pd
import os
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

# =============================================================================
# 定数
# =============================================================================

MASTER_FILE = Path(__file__).parent / "pesticide_master.csv"

# CSVカラム定義
COLUMNS = [
    "crop",           # 作物
    "month",          # 月
    "period",         # 時期
    "target",         # 対象（病害虫・除草）
    "pesticide_name", # 農薬名
    "dilution_rate",  # 希釈倍率
    "amount_per_10a", # 10aあたり使用量
    "unit",           # 単位
    "days_before_harvest",  # 収穫前日数
    "notes"           # 備考
]

COLUMN_LABELS = {
    "crop": "作物",
    "month": "月",
    "period": "時期",
    "target": "対象",
    "pesticide_name": "農薬名",
    "dilution_rate": "希釈倍率",
    "amount_per_10a": "10a使用量",
    "unit": "単位",
    "days_before_harvest": "収穫前日数",
    "notes": "備考"
}

# 作物リスト
CROPS = ["てんさい", "大豆", "春小麦", "秋小麦", "馬鈴薯", "その他"]

# 対象リスト
TARGETS = ["除草", "殺虫", "殺菌", "病害", "害虫", "その他"]

# 単位リスト
UNITS = ["mL", "g", "L", "kg", "倍"]


# =============================================================================
# データ操作
# =============================================================================

def load_master() -> pd.DataFrame:
    """防除マスタを読み込み"""
    if not MASTER_FILE.exists():
        return pd.DataFrame(columns=COLUMNS)

    try:
        df = pd.read_csv(MASTER_FILE, encoding="utf-8")
        return df
    except Exception as e:
        print(f"マスタ読み込みエラー: {e}")
        return pd.DataFrame(columns=COLUMNS)


def save_master(df: pd.DataFrame) -> bool:
    """防除マスタを保存"""
    try:
        df.to_csv(MASTER_FILE, index=False, encoding="utf-8")
        return True
    except Exception as e:
        print(f"マスタ保存エラー: {e}")
        return False


def get_master_for_display() -> List[List[Any]]:
    """表示用にマスタデータを取得"""
    df = load_master()
    if df.empty:
        return []

    # 表示用に整形
    display_data = []
    for idx, row in df.iterrows():
        display_data.append([
            idx,  # 行番号（編集・削除用）
            row.get("crop", ""),
            row.get("month", ""),
            row.get("period", ""),
            row.get("target", ""),
            row.get("pesticide_name", ""),
            row.get("dilution_rate", ""),
            row.get("amount_per_10a", ""),
            row.get("unit", ""),
            row.get("days_before_harvest", ""),
            row.get("notes", "")
        ])

    return display_data


def filter_master(crop: str, month: str) -> List[List[Any]]:
    """作物・月でフィルタリング"""
    df = load_master()

    if crop and crop != "すべて":
        df = df[df["crop"] == crop]

    if month and month != "すべて":
        df = df[df["month"].astype(str) == str(month)]

    if df.empty:
        return []

    display_data = []
    for idx, row in df.iterrows():
        display_data.append([
            idx,
            row.get("crop", ""),
            row.get("month", ""),
            row.get("period", ""),
            row.get("target", ""),
            row.get("pesticide_name", ""),
            row.get("dilution_rate", ""),
            row.get("amount_per_10a", ""),
            row.get("unit", ""),
            row.get("days_before_harvest", ""),
            row.get("notes", "")
        ])

    return display_data


def add_record(crop, month, period, target, pesticide_name,
               dilution_rate, amount_per_10a, unit, days_before_harvest, notes) -> Tuple[str, List]:
    """レコードを追加"""
    if not crop or not pesticide_name:
        return "エラー: 作物と農薬名は必須です", get_master_for_display()

    df = load_master()

    new_row = {
        "crop": crop,
        "month": month,
        "period": period,
        "target": target,
        "pesticide_name": pesticide_name,
        "dilution_rate": dilution_rate if dilution_rate else "",
        "amount_per_10a": amount_per_10a if amount_per_10a else "",
        "unit": unit,
        "days_before_harvest": days_before_harvest,
        "notes": notes
    }

    df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)

    if save_master(df):
        return f"追加完了: {crop} - {pesticide_name}", get_master_for_display()
    else:
        return "エラー: 保存に失敗しました", get_master_for_display()


def delete_record(row_index: int) -> Tuple[str, List]:
    """レコードを削除"""
    if row_index is None or row_index < 0:
        return "エラー: 削除する行を選択してください", get_master_for_display()

    df = load_master()

    if row_index >= len(df):
        return "エラー: 無効な行番号です", get_master_for_display()

    deleted_row = df.iloc[row_index]
    deleted_info = f"{deleted_row.get('crop', '')} - {deleted_row.get('pesticide_name', '')}"

    df = df.drop(index=row_index).reset_index(drop=True)

    if save_master(df):
        return f"削除完了: {deleted_info}", get_master_for_display()
    else:
        return "エラー: 保存に失敗しました", get_master_for_display()


def import_csv(file) -> Tuple[str, List]:
    """CSVファイルをインポート"""
    if file is None:
        return "エラー: ファイルを選択してください", get_master_for_display()

    try:
        # アップロードされたファイルを読み込み
        import_df = pd.read_csv(file.name, encoding="utf-8")

        # カラム検証
        missing_cols = set(COLUMNS) - set(import_df.columns)
        if missing_cols:
            return f"エラー: 必須カラムがありません: {missing_cols}", get_master_for_display()

        # 既存データに追加（または置換）
        existing_df = load_master()

        # 追加モード
        combined_df = pd.concat([existing_df, import_df[COLUMNS]], ignore_index=True)

        # 重複削除（作物・月・農薬名で判定）
        combined_df = combined_df.drop_duplicates(
            subset=["crop", "month", "period", "pesticide_name"],
            keep="last"
        )

        if save_master(combined_df):
            return f"インポート完了: {len(import_df)}件追加（重複除外後: {len(combined_df)}件）", get_master_for_display()
        else:
            return "エラー: 保存に失敗しました", get_master_for_display()

    except Exception as e:
        return f"エラー: {str(e)}", get_master_for_display()


def get_statistics() -> str:
    """統計情報を取得"""
    df = load_master()

    if df.empty:
        return "データがありません"

    stats = []
    stats.append(f"**総レコード数**: {len(df)}件")
    stats.append("")
    stats.append("**作物別件数**:")

    for crop in df["crop"].unique():
        count = len(df[df["crop"] == crop])
        stats.append(f"- {crop}: {count}件")

    stats.append("")
    stats.append("**月別件数**:")

    for month in sorted(df["month"].dropna().unique()):
        count = len(df[df["month"] == month])
        stats.append(f"- {month}月: {count}件")

    return "\n".join(stats)


# =============================================================================
# UI作成
# =============================================================================

def create_pesticide_master_ui() -> Dict[str, Any]:
    """防除マスタ管理UIを作成（ポータル埋め込み用）"""

    components = {}

    gr.Markdown("""
    ## 💊 防除マスタ管理

    農薬の散布スケジュールを登録・管理します。
    JA指導計画（12月発表）に基づいて更新してください。
    """)

    with gr.Tabs():
        # =================================================================
        # 一覧・検索タブ
        # =================================================================
        with gr.TabItem("📋 一覧"):
            with gr.Row():
                filter_crop = gr.Dropdown(
                    choices=["すべて"] + CROPS,
                    value="すべて",
                    label="作物フィルタ"
                )
                filter_month = gr.Dropdown(
                    choices=["すべて"] + [str(i) for i in range(1, 13)],
                    value="すべて",
                    label="月フィルタ"
                )
                filter_btn = gr.Button("🔍 絞り込み")

            master_table = gr.Dataframe(
                headers=["#", "作物", "月", "時期", "対象", "農薬名", "希釈倍率", "10a使用量", "単位", "収穫前日数", "備考"],
                datatype=["number", "str", "str", "str", "str", "str", "str", "str", "str", "str", "str"],
                value=get_master_for_display(),
                label="防除マスタ一覧",
                interactive=False,
                wrap=True
            )
            components["master_table"] = master_table

            with gr.Row():
                refresh_btn = gr.Button("🔄 更新")
                delete_index = gr.Number(label="削除する行番号（#列の値）", precision=0)
                delete_btn = gr.Button("🗑️ 削除", variant="stop")

            result_msg = gr.Textbox(label="結果", interactive=False)
            components["result_msg"] = result_msg

            # イベント
            filter_btn.click(
                fn=filter_master,
                inputs=[filter_crop, filter_month],
                outputs=[master_table]
            )

            refresh_btn.click(
                fn=get_master_for_display,
                outputs=[master_table]
            )

            delete_btn.click(
                fn=delete_record,
                inputs=[delete_index],
                outputs=[result_msg, master_table]
            )

        # =================================================================
        # 新規登録タブ
        # =================================================================
        with gr.TabItem("➕ 新規登録"):
            gr.Markdown("### 防除スケジュールを登録")

            with gr.Row():
                with gr.Column():
                    add_crop = gr.Dropdown(choices=CROPS, label="作物 *", value="てんさい")
                    add_month = gr.Dropdown(
                        choices=[str(i) for i in range(1, 13)],
                        label="月",
                        value="5"
                    )
                    add_period = gr.Textbox(label="時期", placeholder="例: 播種直後、本葉2葉展開後")
                    add_target = gr.Dropdown(choices=TARGETS, label="対象", value="除草")
                    add_pesticide = gr.Textbox(label="農薬名 *", placeholder="例: デュアールゴールド")

                with gr.Column():
                    add_dilution = gr.Textbox(label="希釈倍率", placeholder="例: 2000（倍の場合）")
                    add_amount = gr.Textbox(label="10aあたり使用量", placeholder="例: 100")
                    add_unit = gr.Dropdown(choices=UNITS, label="単位", value="mL")
                    add_days = gr.Textbox(label="収穫前日数", placeholder="例: 90日前")
                    add_notes = gr.Textbox(label="備考", placeholder="例: 臨機防除")

            add_btn = gr.Button("➕ 登録", variant="primary")
            add_result = gr.Textbox(label="結果", interactive=False)

            add_btn.click(
                fn=add_record,
                inputs=[add_crop, add_month, add_period, add_target, add_pesticide,
                       add_dilution, add_amount, add_unit, add_days, add_notes],
                outputs=[add_result, master_table]
            )

        # =================================================================
        # CSVインポートタブ
        # =================================================================
        with gr.TabItem("📤 インポート"):
            gr.Markdown("""
            ### CSVファイルからインポート

            既存のCSVファイルを読み込んでマスタに追加します。

            **必須カラム**:
            ```
            crop, month, period, target, pesticide_name, dilution_rate, amount_per_10a, unit, days_before_harvest, notes
            ```
            """)

            import_file = gr.File(label="CSVファイルを選択", file_types=[".csv"])
            import_btn = gr.Button("📤 インポート", variant="primary")
            import_result = gr.Textbox(label="結果", interactive=False)

            import_btn.click(
                fn=import_csv,
                inputs=[import_file],
                outputs=[import_result, master_table]
            )

            gr.Markdown("---")
            gr.Markdown("### 現在のマスタをダウンロード")

            def get_master_file():
                return str(MASTER_FILE) if MASTER_FILE.exists() else None

            download_btn = gr.DownloadButton("📥 CSVダウンロード", value=get_master_file())

        # =================================================================
        # 統計タブ
        # =================================================================
        with gr.TabItem("📊 統計"):
            stats_display = gr.Markdown(value=get_statistics())
            stats_refresh = gr.Button("🔄 更新")

            stats_refresh.click(
                fn=get_statistics,
                outputs=[stats_display]
            )

    return components


# =============================================================================
# スタンドアロン実行
# =============================================================================

if __name__ == "__main__":
    with gr.Blocks(title="防除マスタ管理") as app:
        create_pesticide_master_ui()

    app.launch(
        server_name="0.0.0.0",
        server_port=7864,
        share=False
    )
