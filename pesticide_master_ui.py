"""
防除マスタ管理UI - JA職員向け
防除スケジュール（農薬マスタ）の登録・編集・削除機能

データソース: SQLite DB (pesticide_masters テーブル)
"""

import gradio as gr
import pandas as pd
import os
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

from rotation_planner.common import PesticideMasterRepository

# =============================================================================
# 定数
# =============================================================================

# CSVインポート用のパス
MASTER_CSV_FILE = Path(__file__).parent / "pesticide_master.csv"

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
# データ操作（DB版）
# =============================================================================

def get_master_for_display(org_id: int = None) -> List[List[Any]]:
    """表示用にマスタデータを取得（DBから）"""
    rows = PesticideMasterRepository.get_all(org_id)
    if not rows:
        return []

    display_data = []
    for row in rows:
        display_data.append([
            row.get("id", ""),  # DB ID（編集・削除用）
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


def filter_master(crop: str, month: str, org_id: int = None) -> List[List[Any]]:
    """作物・月でフィルタリング"""
    rows = PesticideMasterRepository.get_all(org_id)

    if crop and crop != "すべて":
        rows = [r for r in rows if r.get("crop") == crop]

    if month and month != "すべて":
        rows = [r for r in rows if str(r.get("month", "")) == str(month)]

    if not rows:
        return []

    display_data = []
    for row in rows:
        display_data.append([
            row.get("id", ""),
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
               dilution_rate, amount_per_10a, unit, days_before_harvest, notes,
               org_id: int = None) -> Tuple[str, List]:
    """レコードを追加（DBに保存）"""
    if not crop or not pesticide_name:
        return "エラー: 作物と農薬名は必須です", get_master_for_display(org_id)

    data = {
        "org_id": org_id,
        "crop": crop,
        "month": month if month else None,
        "period": period,
        "target": target,
        "pesticide_name": pesticide_name,
        "dilution_rate": dilution_rate if dilution_rate else None,
        "amount_per_10a": amount_per_10a if amount_per_10a else None,
        "unit": unit,
        "days_before_harvest": days_before_harvest,
        "notes": notes
    }

    try:
        PesticideMasterRepository.create(data)
        return f"追加完了: {crop} - {pesticide_name}", get_master_for_display(org_id)
    except Exception as e:
        return f"エラー: 保存に失敗しました - {e}", get_master_for_display(org_id)


def delete_record(master_id: int, org_id: int = None) -> Tuple[str, List]:
    """レコードを削除（DBから）"""
    if master_id is None or master_id < 1:
        return "エラー: 削除する行のIDを入力してください", get_master_for_display(org_id)

    # 削除前に情報取得
    record = PesticideMasterRepository.get_by_id(master_id)
    if not record:
        return "エラー: 指定されたレコードが見つかりません", get_master_for_display(org_id)

    deleted_info = f"{record.get('crop', '')} - {record.get('pesticide_name', '')}"

    if PesticideMasterRepository.delete(master_id):
        return f"削除完了: {deleted_info}", get_master_for_display(org_id)
    else:
        return "エラー: 削除に失敗しました", get_master_for_display(org_id)


def import_csv(file, replace_mode: bool = False, org_id: int = None) -> Tuple[str, List]:
    """CSVファイルをインポート（DBに保存）"""
    if file is None:
        return "エラー: ファイルを選択してください", get_master_for_display(org_id)

    try:
        # アップロードされたファイルを読み込み
        try:
            import_df = pd.read_csv(file.name, encoding="utf-8")
        except Exception:
            import_df = pd.read_csv(file.name, encoding="utf-8-sig")

        # 最低限必要なカラム
        required_cols = {"crop", "pesticide_name"}
        missing_cols = required_cols - set(import_df.columns)
        if missing_cols:
            return f"エラー: 必須カラムがありません: {missing_cols}", get_master_for_display(org_id)

        # 置換モードの場合は既存データを削除
        if replace_mode:
            deleted_count = PesticideMasterRepository.delete_all(org_id)

        # レコードを一括インポート
        records = import_df.to_dict('records')
        imported_count = PesticideMasterRepository.bulk_import(records, org_id)

        if replace_mode:
            return f"インポート完了: {imported_count}件（既存{deleted_count}件を置換）", get_master_for_display(org_id)
        else:
            return f"インポート完了: {imported_count}件を追加", get_master_for_display(org_id)

    except Exception as e:
        return f"エラー: {str(e)}", get_master_for_display(org_id)


def get_statistics(org_id: int = None) -> str:
    """統計情報を取得（DBから）"""
    rows = PesticideMasterRepository.get_all(org_id)

    if not rows:
        return "データがありません"

    df = pd.DataFrame(rows)

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
        stats.append(f"- {int(month)}月: {count}件")

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
        with gr.TabItem("📤 インポート/エクスポート"):
            gr.Markdown("""
            ### CSVファイルからインポート

            既存のCSVファイルを読み込んでマスタに追加します。

            **必須カラム**: `crop`, `pesticide_name`

            **オプションカラム**: `month`, `period`, `target`, `dilution_rate`, `amount_per_10a`, `unit`, `days_before_harvest`, `notes`
            """)

            import_file = gr.File(label="CSVファイルを選択", file_types=[".csv"])
            import_replace = gr.Checkbox(label="既存データを置換（チェックしない場合は追加）", value=False)
            import_btn = gr.Button("📤 インポート", variant="primary")
            import_result = gr.Textbox(label="結果", interactive=False)

            import_btn.click(
                fn=import_csv,
                inputs=[import_file, import_replace],
                outputs=[import_result, master_table]
            )

            gr.Markdown("---")
            gr.Markdown("### 現在のマスタをエクスポート")

            def export_master_csv():
                """DBからCSVをエクスポート"""
                rows = PesticideMasterRepository.get_all()
                if not rows:
                    return None
                df = pd.DataFrame(rows)
                # 不要なカラムを除外
                export_cols = [c for c in COLUMNS if c in df.columns]
                export_path = Path(__file__).parent / "data" / "pesticide_master_export.csv"
                export_path.parent.mkdir(parents=True, exist_ok=True)
                df[export_cols].to_csv(export_path, index=False, encoding="utf-8-sig")
                return str(export_path)

            export_btn = gr.Button("📥 CSVエクスポート")
            export_file = gr.File(label="ダウンロード", interactive=False)

            export_btn.click(
                fn=export_master_csv,
                outputs=[export_file]
            )

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
