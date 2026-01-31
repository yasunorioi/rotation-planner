"""
rotation_planner.pesticide_record.ui - 防除記録 Gradio UIモジュール

写真アップロードによる農薬名自動認識、防除履歴のCRUD機能を提供。

Usage:
    from rotation_planner.pesticide_record import create_pesticide_record_ui

    with gr.Tab("🧪 防除記録"):
        components = create_pesticide_record_ui(user_state)
"""

import os
import shutil
import gradio as gr
import pandas as pd
from datetime import datetime, date
from typing import Dict, Any, List, Tuple, Optional

from rotation_planner.common import (
    FieldRepository,
    PesticideRecordRepository,
    PesticideRegistryRepository,
    PesticideUsageRepository,
    format_success,
    format_error,
    format_warning,
    format_info,
)
from rotation_planner.pesticide_record.image_analyzer import analyze_image


# =============================================================================
# 定数
# =============================================================================

SPRAY_UNITS = ["L", "mL", "kg", "g"]

# 画像保存ディレクトリ
UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "uploads", "pesticide_records")


# =============================================================================
# ヘルパー関数
# =============================================================================

def ensure_upload_dir():
    """アップロードディレクトリを確保"""
    if not os.path.exists(UPLOAD_DIR):
        os.makedirs(UPLOAD_DIR, exist_ok=True)


def get_field_choices(user_id: int) -> List[Tuple[str, int]]:
    """
    ユーザーのほ場選択肢を取得

    Returns:
        [(表示名, field_id), ...]
    """
    fields = FieldRepository.get_fields(user_id)
    choices = []
    for f in fields:
        field_code = f.get("field_code", "")
        field_name = f.get("name", "")
        display_name = f"{field_code} {field_name}".strip() if field_name else field_code
        choices.append((display_name, f.get("id")))
    return choices


def get_dilution_choices(pesticide_name: str, crop: str = None) -> List[str]:
    """
    農薬名から希釈倍率の選択肢を取得

    Args:
        pesticide_name: 農薬名
        crop: 作物名（オプション）

    Returns:
        希釈倍率リスト
    """
    if not pesticide_name:
        return []

    # 農薬名でレジストリを検索
    pesticide = PesticideRegistryRepository.get_by_name(pesticide_name)
    if not pesticide:
        # 部分一致で検索
        results = PesticideRegistryRepository.search(pesticide_name, limit=1)
        if results:
            pesticide = results[0]

    if not pesticide:
        return []

    # 適用情報を取得
    usages = PesticideUsageRepository.get_by_pesticide_id(pesticide["id"])

    # 作物でフィルタリング（指定があれば）
    if crop:
        usages = [u for u in usages if crop in str(u.get("crop", ""))]

    # 希釈倍率を抽出（重複排除）
    dilution_rates = set()
    for u in usages:
        rate = u.get("dilution_rate", "")
        if rate:
            dilution_rates.add(rate)

    return sorted(list(dilution_rates))


def get_current_crop_for_field(field_id: int, user_id: int) -> Optional[str]:
    """ほ場の現在の作付作物を取得"""
    from rotation_planner.common import CropHistoryRepository

    # 現在の年度を取得
    current_year = datetime.now().year
    # 令和に変換（2019年が令和1年）
    reiwa_year = current_year - 2018
    year_str = f"R{reiwa_year}"

    # 履歴から取得
    history = CropHistoryRepository.get_history(field_id, year_str)
    if history:
        return history.get("crop")

    return None


# =============================================================================
# UI操作関数
# =============================================================================

def on_image_upload(file_path: str, user_state: Dict[str, Any]) -> Tuple[str, str, str, str, str]:
    """
    画像アップロード時の処理

    Args:
        file_path: アップロードされた画像のパス
        user_state: ユーザー状態

    Returns:
        (spray_date, pesticide_name, analysis_info, dilution_choices_html, message)
    """
    if not file_path:
        return "", "", "", "", format_warning("画像を選択してください")

    if not user_state or not user_state.get("user_id"):
        return "", "", "", "", format_error("ログインが必要です")

    # 画像を解析
    result = analyze_image(file_path)

    # 散布日（EXIFから取得、なければ今日）
    spray_date = result.get("spray_date") or date.today().isoformat()

    # 農薬名
    pesticide_name = result.get("pesticide_name") or ""

    # 解析情報を構築
    info_parts = []

    if result.get("spray_datetime"):
        info_parts.append(f"📅 撮影日時: {result['spray_datetime']}")
    else:
        info_parts.append("📅 撮影日時: 取得できませんでした（今日の日付を設定）")

    if result.get("gps"):
        gps = result["gps"]
        info_parts.append(f"📍 GPS: {gps['lat']:.6f}, {gps['lon']:.6f}")
    else:
        info_parts.append("📍 GPS: 取得できませんでした")

    if result.get("pesticide_name"):
        confidence = result.get("confidence", "")
        confidence_text = {"high": "高", "medium": "中", "low": "低"}.get(confidence, "")
        info_parts.append(f"💊 認識した農薬名: {result['pesticide_name']} (確信度: {confidence_text})")
    else:
        info_parts.append("💊 農薬名: 認識できませんでした（手動で入力してください）")

    if result.get("errors"):
        for err in result["errors"]:
            info_parts.append(f"⚠️ {err}")

    analysis_info = "\n".join(info_parts)

    # 希釈倍率の選択肢を取得
    dilution_html = ""
    if pesticide_name:
        dilutions = get_dilution_choices(pesticide_name)
        if dilutions:
            dilution_html = f"適用基準の希釈倍率: {', '.join(dilutions[:10])}"
            if len(dilutions) > 10:
                dilution_html += f" 他{len(dilutions) - 10}件"

    return spray_date, pesticide_name, analysis_info, dilution_html, format_success("画像を解析しました")


def update_dilution_choices(pesticide_name: str, field_choice: str, user_state: Dict[str, Any]) -> gr.Dropdown:
    """
    農薬名・ほ場変更時に希釈倍率の選択肢を更新

    Args:
        pesticide_name: 農薬名
        field_choice: 選択したほ場（"表示名"形式）
        user_state: ユーザー状態

    Returns:
        更新されたDropdown
    """
    if not pesticide_name:
        return gr.Dropdown(choices=[], value="")

    crop = None

    # ほ場から現在の作物を取得
    if field_choice and user_state and user_state.get("user_id"):
        # field_choiceから field_id を抽出（タプルの場合）
        # Gradioのdropdownは値のみ返す
        try:
            field_id = int(field_choice) if isinstance(field_choice, (int, str)) and str(field_choice).isdigit() else None
            if field_id:
                crop = get_current_crop_for_field(field_id, user_state["user_id"])
        except (ValueError, TypeError):
            pass

    dilutions = get_dilution_choices(pesticide_name, crop)

    return gr.Dropdown(choices=dilutions, value=dilutions[0] if dilutions else "")


def register_record(
    file_path: str,
    spray_date: str,
    pesticide_name: str,
    field_id: int,
    dilution_rate: str,
    spray_amount: float,
    spray_unit: str,
    notes: str,
    user_state: Dict[str, Any]
) -> str:
    """
    防除記録を登録

    Returns:
        結果メッセージ
    """
    if not user_state or not user_state.get("user_id"):
        return format_error("ログインが必要です")

    if not field_id:
        return format_error("ほ場を選択してください")

    if not pesticide_name:
        return format_error("農薬名を入力してください")

    if not spray_date:
        return format_error("散布日を入力してください")

    user_id = user_state.get("user_id")

    # 画像を保存ディレクトリにコピー
    photo_path = None
    if file_path and os.path.exists(file_path):
        ensure_upload_dir()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        ext = os.path.splitext(file_path)[1]
        new_filename = f"{user_id}_{timestamp}{ext}"
        photo_path = os.path.join(UPLOAD_DIR, new_filename)
        shutil.copy2(file_path, photo_path)

    # 農薬IDを取得（あれば）
    pesticide_id = None
    pesticide = PesticideRegistryRepository.get_by_name(pesticide_name)
    if pesticide:
        pesticide_id = pesticide["id"]

    # データを準備
    data = {
        "field_id": field_id,
        "spray_date": spray_date,
        "pesticide_name": pesticide_name,
        "pesticide_id": pesticide_id,
        "dilution_rate": dilution_rate,
        "spray_amount": spray_amount if spray_amount else None,
        "spray_unit": spray_unit if spray_amount else None,
        "photo_path": photo_path,
        "notes": notes,
    }

    # 登録
    try:
        record_id = PesticideRecordRepository.create_record(user_id, data)
        return format_success(f"防除記録を登録しました（ID: {record_id}）")
    except Exception as e:
        return format_error(f"登録エラー: {str(e)}")


def clear_registration_form():
    """登録フォームをクリア"""
    return None, "", "", "", "", gr.Dropdown(choices=[], value=""), None, "", "", ""


def load_record_history(
    user_state: Dict[str, Any],
    field_filter: int,
    date_from: str,
    date_to: str
) -> Tuple[pd.DataFrame, str]:
    """
    防除記録履歴を読み込む

    Returns:
        (DataFrame, メッセージ)
    """
    if not user_state or not user_state.get("user_id"):
        return pd.DataFrame(), format_error("ログインが必要です")

    user_id = user_state.get("user_id")

    # 記録を取得
    records = PesticideRecordRepository.get_records(user_id, field_id=field_filter if field_filter else None)

    if not records:
        return pd.DataFrame(), format_info("防除記録がありません")

    # 日付でフィルタリング
    if date_from:
        records = [r for r in records if r.get("spray_date", "") >= date_from]
    if date_to:
        records = [r for r in records if r.get("spray_date", "") <= date_to]

    # DataFrameに変換
    rows = []
    for r in records:
        rows.append({
            "ID": r.get("id"),
            "散布日": r.get("spray_date"),
            "ほ場": f"{r.get('field_code', '')} {r.get('field_name', '')}".strip(),
            "農薬名": r.get("pesticide_name"),
            "希釈倍率": r.get("dilution_rate", ""),
            "散布量": f"{r.get('spray_amount', '')} {r.get('spray_unit', '')}".strip() if r.get("spray_amount") else "",
            "備考": r.get("notes", ""),
        })

    df = pd.DataFrame(rows)
    return df, format_success(f"{len(df)}件の記録を読み込みました")


def delete_selected_record(
    records_df: pd.DataFrame,
    selected_index: List[int],
    user_state: Dict[str, Any]
) -> Tuple[pd.DataFrame, str]:
    """
    選択した記録を削除

    Returns:
        (更新後のDataFrame, メッセージ)
    """
    if not user_state or not user_state.get("user_id"):
        return records_df, format_error("ログインが必要です")

    if records_df is None or records_df.empty:
        return records_df, format_error("データがありません")

    if not selected_index:
        return records_df, format_warning("削除する行を選択してください")

    # 選択された行のIDを取得
    try:
        idx = selected_index[0] if isinstance(selected_index, list) else selected_index
        record_id = records_df.iloc[idx]["ID"]
    except (IndexError, KeyError) as e:
        return records_df, format_error(f"行の取得に失敗: {str(e)}")

    # 削除
    if PesticideRecordRepository.delete_record(record_id):
        # 再読み込み
        new_records = PesticideRecordRepository.get_records(user_state["user_id"])
        rows = []
        for r in new_records:
            rows.append({
                "ID": r.get("id"),
                "散布日": r.get("spray_date"),
                "ほ場": f"{r.get('field_code', '')} {r.get('field_name', '')}".strip(),
                "農薬名": r.get("pesticide_name"),
                "希釈倍率": r.get("dilution_rate", ""),
                "散布量": f"{r.get('spray_amount', '')} {r.get('spray_unit', '')}".strip() if r.get("spray_amount") else "",
                "備考": r.get("notes", ""),
            })
        df = pd.DataFrame(rows) if rows else pd.DataFrame()
        return df, format_success(f"記録ID {record_id} を削除しました")
    else:
        return records_df, format_error("削除に失敗しました")


def load_record_for_edit(
    records_df: pd.DataFrame,
    selected_index: List[int],
    user_state: Dict[str, Any]
) -> Tuple[int, str, str, str, int, str, float, str, str, str]:
    """
    選択した記録を編集用に読み込む

    Returns:
        (record_id, spray_date, pesticide_name, field_display, field_id, dilution_rate, spray_amount, spray_unit, notes, message)
    """
    if not user_state or not user_state.get("user_id"):
        return None, "", "", "", None, "", None, "", "", format_error("ログインが必要です")

    if records_df is None or records_df.empty:
        return None, "", "", "", None, "", None, "", "", format_error("データがありません")

    if not selected_index:
        return None, "", "", "", None, "", None, "", "", format_warning("編集する行を選択してください")

    try:
        idx = selected_index[0] if isinstance(selected_index, list) else selected_index
        row = records_df.iloc[idx]

        record_id = row["ID"]
        spray_date = row["散布日"]
        pesticide_name = row["農薬名"]
        field_display = row["ほ場"]
        dilution_rate = row["希釈倍率"]

        # 散布量と単位を分割
        spray_amount_str = row["散布量"]
        spray_amount = None
        spray_unit = ""
        if spray_amount_str:
            parts = spray_amount_str.strip().split()
            if parts:
                try:
                    spray_amount = float(parts[0])
                    spray_unit = parts[1] if len(parts) > 1 else ""
                except ValueError:
                    pass

        notes = row["備考"]

        # field_idを取得
        user_id = user_state.get("user_id")
        field_id = None
        if field_display:
            field_code = field_display.split()[0]
            fields = FieldRepository.get_fields(user_id)
            for f in fields:
                if f.get("field_code") == field_code:
                    field_id = f.get("id")
                    break

        return record_id, spray_date, pesticide_name, field_display, field_id, dilution_rate, spray_amount, spray_unit, notes, format_info(f"記録ID {record_id} を編集します")

    except (IndexError, KeyError) as e:
        return None, "", "", "", None, "", None, "", "", format_error(f"読み込みエラー: {str(e)}")


def update_record(
    record_id: int,
    spray_date: str,
    pesticide_name: str,
    field_id: int,
    dilution_rate: str,
    spray_amount: float,
    spray_unit: str,
    notes: str,
    user_state: Dict[str, Any]
) -> Tuple[pd.DataFrame, str]:
    """
    防除記録を更新

    Returns:
        (更新後のDataFrame, メッセージ)
    """
    if not user_state or not user_state.get("user_id"):
        return pd.DataFrame(), format_error("ログインが必要です")

    if not record_id:
        return pd.DataFrame(), format_error("編集対象が選択されていません")

    if not field_id:
        return pd.DataFrame(), format_error("ほ場を選択してください")

    if not pesticide_name:
        return pd.DataFrame(), format_error("農薬名を入力してください")

    # 農薬IDを取得
    pesticide_id = None
    pesticide = PesticideRegistryRepository.get_by_name(pesticide_name)
    if pesticide:
        pesticide_id = pesticide["id"]

    data = {
        "field_id": field_id,
        "spray_date": spray_date,
        "pesticide_name": pesticide_name,
        "pesticide_id": pesticide_id,
        "dilution_rate": dilution_rate,
        "spray_amount": spray_amount if spray_amount else None,
        "spray_unit": spray_unit if spray_amount else None,
        "notes": notes,
    }

    if PesticideRecordRepository.update_record(record_id, data):
        # 再読み込み
        new_records = PesticideRecordRepository.get_records(user_state["user_id"])
        rows = []
        for r in new_records:
            rows.append({
                "ID": r.get("id"),
                "散布日": r.get("spray_date"),
                "ほ場": f"{r.get('field_code', '')} {r.get('field_name', '')}".strip(),
                "農薬名": r.get("pesticide_name"),
                "希釈倍率": r.get("dilution_rate", ""),
                "散布量": f"{r.get('spray_amount', '')} {r.get('spray_unit', '')}".strip() if r.get("spray_amount") else "",
                "備考": r.get("notes", ""),
            })
        df = pd.DataFrame(rows) if rows else pd.DataFrame()
        return df, format_success(f"記録ID {record_id} を更新しました")
    else:
        return pd.DataFrame(), format_error("更新に失敗しました")


# =============================================================================
# メインUIコンポーネント
# =============================================================================

def create_pesticide_record_ui(user_state: gr.State) -> Dict[str, Any]:
    """
    防除記録UIコンポーネントを作成

    Args:
        user_state: ユーザー情報を保持するgr.State

    Returns:
        components: UI操作に必要なコンポーネントの辞書
    """

    gr.Markdown("""
    ## 🧪 防除記録

    写真をアップロードして農薬名を自動認識。防除履歴を簡単に管理できます。
    - **写真アップロード**: 農薬ラベルの写真から自動で農薬名を認識
    - **EXIF解析**: 撮影日時を自動取得（位置情報ONを推奨）
    - **適用基準連携**: FAMICデータから希釈倍率を自動提示
    """)

    with gr.Tabs():
        # =====================================================================
        # 📷 記録登録タブ
        # =====================================================================
        with gr.TabItem("📷 記録登録"):
            with gr.Row():
                with gr.Column(scale=1):
                    gr.Markdown("### 📷 写真アップロード")

                    image_upload = gr.File(
                        label="農薬ラベルの写真",
                        file_types=["image"],
                        type="filepath"
                    )

                    analysis_info = gr.Textbox(
                        label="解析結果",
                        lines=5,
                        interactive=False
                    )

                    dilution_info = gr.Markdown("")

                with gr.Column(scale=1):
                    gr.Markdown("### 📝 記録情報")

                    spray_date_input = gr.Textbox(
                        label="散布日",
                        placeholder="YYYY-MM-DD（自動取得または手入力）"
                    )

                    pesticide_name_input = gr.Textbox(
                        label="農薬名",
                        placeholder="認識結果または手入力"
                    )

                    field_dropdown = gr.Dropdown(
                        label="ほ場",
                        choices=[],
                        interactive=True
                    )

                    dilution_dropdown = gr.Dropdown(
                        label="希釈倍率",
                        choices=[],
                        allow_custom_value=True,
                        interactive=True
                    )

                    with gr.Row():
                        spray_amount_input = gr.Number(
                            label="散布量",
                            precision=2
                        )
                        spray_unit_dropdown = gr.Dropdown(
                            label="単位",
                            choices=SPRAY_UNITS,
                            value="L"
                        )

                    notes_input = gr.Textbox(
                        label="備考",
                        lines=2
                    )

            with gr.Row():
                register_btn = gr.Button("💾 登録", variant="primary")
                clear_btn = gr.Button("🗑️ クリア", variant="secondary")

            register_message = gr.HTML("")

        # =====================================================================
        # 📋 履歴一覧タブ
        # =====================================================================
        with gr.TabItem("📋 履歴一覧"):
            gr.Markdown("### 🔍 フィルタ")

            with gr.Row():
                history_field_filter = gr.Dropdown(
                    label="ほ場",
                    choices=[],
                    value=None,
                    interactive=True
                )
                history_date_from = gr.Textbox(
                    label="開始日",
                    placeholder="YYYY-MM-DD"
                )
                history_date_to = gr.Textbox(
                    label="終了日",
                    placeholder="YYYY-MM-DD"
                )
                refresh_history_btn = gr.Button("🔄 更新", variant="secondary")

            history_table = gr.Dataframe(
                value=pd.DataFrame(columns=["ID", "散布日", "ほ場", "農薬名", "希釈倍率", "散布量", "備考"]),
                label="防除記録一覧",
                interactive=False,
                row_count=(10, "dynamic")
            )

            history_message = gr.HTML("")

            with gr.Accordion("✏️ 編集", open=False):
                edit_record_id = gr.Number(label="記録ID", visible=False)

                with gr.Row():
                    edit_spray_date = gr.Textbox(label="散布日")
                    edit_pesticide_name = gr.Textbox(label="農薬名")

                with gr.Row():
                    edit_field_dropdown = gr.Dropdown(
                        label="ほ場",
                        choices=[],
                        interactive=True
                    )
                    edit_dilution = gr.Textbox(label="希釈倍率")

                with gr.Row():
                    edit_spray_amount = gr.Number(label="散布量", precision=2)
                    edit_spray_unit = gr.Dropdown(
                        label="単位",
                        choices=SPRAY_UNITS,
                        value="L"
                    )

                edit_notes = gr.Textbox(label="備考")

                with gr.Row():
                    load_edit_btn = gr.Button("📥 選択行を読み込み", variant="secondary")
                    update_btn = gr.Button("💾 更新", variant="primary")
                    delete_btn = gr.Button("🗑️ 削除", variant="stop")

                edit_message = gr.HTML("")

    # =========================================================================
    # イベントハンドラ
    # =========================================================================

    # 画像アップロード時
    image_upload.change(
        fn=on_image_upload,
        inputs=[image_upload, user_state],
        outputs=[spray_date_input, pesticide_name_input, analysis_info, dilution_info, register_message]
    )

    # 農薬名変更時に希釈倍率を更新
    pesticide_name_input.change(
        fn=update_dilution_choices,
        inputs=[pesticide_name_input, field_dropdown, user_state],
        outputs=[dilution_dropdown]
    )

    # ほ場変更時に希釈倍率を更新
    field_dropdown.change(
        fn=update_dilution_choices,
        inputs=[pesticide_name_input, field_dropdown, user_state],
        outputs=[dilution_dropdown]
    )

    # 登録ボタン
    register_btn.click(
        fn=register_record,
        inputs=[
            image_upload,
            spray_date_input,
            pesticide_name_input,
            field_dropdown,
            dilution_dropdown,
            spray_amount_input,
            spray_unit_dropdown,
            notes_input,
            user_state
        ],
        outputs=[register_message]
    )

    # クリアボタン
    clear_btn.click(
        fn=clear_registration_form,
        outputs=[
            image_upload,
            spray_date_input,
            pesticide_name_input,
            analysis_info,
            dilution_info,
            dilution_dropdown,
            spray_amount_input,
            spray_unit_dropdown,
            notes_input,
            register_message
        ]
    )

    # 履歴更新ボタン
    refresh_history_btn.click(
        fn=load_record_history,
        inputs=[user_state, history_field_filter, history_date_from, history_date_to],
        outputs=[history_table, history_message]
    )

    # 編集用に読み込み
    load_edit_btn.click(
        fn=load_record_for_edit,
        inputs=[history_table, history_table, user_state],
        outputs=[
            edit_record_id,
            edit_spray_date,
            edit_pesticide_name,
            edit_field_dropdown,
            edit_field_dropdown,
            edit_dilution,
            edit_spray_amount,
            edit_spray_unit,
            edit_notes,
            edit_message
        ]
    )

    # 更新ボタン
    update_btn.click(
        fn=update_record,
        inputs=[
            edit_record_id,
            edit_spray_date,
            edit_pesticide_name,
            edit_field_dropdown,
            edit_dilution,
            edit_spray_amount,
            edit_spray_unit,
            edit_notes,
            user_state
        ],
        outputs=[history_table, edit_message]
    )

    # 削除ボタン
    delete_btn.click(
        fn=delete_selected_record,
        inputs=[history_table, history_table, user_state],
        outputs=[history_table, edit_message]
    )

    return {
        "image_upload": image_upload,
        "spray_date_input": spray_date_input,
        "pesticide_name_input": pesticide_name_input,
        "field_dropdown": field_dropdown,
        "dilution_dropdown": dilution_dropdown,
        "spray_amount_input": spray_amount_input,
        "spray_unit_dropdown": spray_unit_dropdown,
        "notes_input": notes_input,
        "register_btn": register_btn,
        "clear_btn": clear_btn,
        "register_message": register_message,
        "history_field_filter": history_field_filter,
        "history_table": history_table,
        "history_message": history_message,
        "edit_record_id": edit_record_id,
        "edit_field_dropdown": edit_field_dropdown,
        "refresh_history_btn": refresh_history_btn,
    }


# =============================================================================
# 初期化関数（portal.py から呼び出し）
# =============================================================================

def load_initial_fields(user_state: Dict[str, Any]) -> Tuple[gr.Dropdown, gr.Dropdown, gr.Dropdown]:
    """
    防除記録タブの初期化（ほ場選択肢を設定）

    Returns:
        (field_dropdown, history_field_filter, edit_field_dropdown)
    """
    if not user_state or not user_state.get("user_id"):
        empty = gr.Dropdown(choices=[], value=None)
        return empty, empty, empty

    user_id = user_state.get("user_id")
    choices = get_field_choices(user_id)

    # Gradio Dropdownの選択肢形式に変換
    dropdown_choices = [(name, fid) for name, fid in choices]

    # 履歴フィルタには「全て」を追加
    filter_choices = [("全て", None)] + dropdown_choices

    return (
        gr.Dropdown(choices=dropdown_choices, value=None),
        gr.Dropdown(choices=filter_choices, value=None),
        gr.Dropdown(choices=dropdown_choices, value=None),
    )


# =============================================================================
# 公開API
# =============================================================================

__all__ = [
    "create_pesticide_record_ui",
    "load_initial_fields",
]
