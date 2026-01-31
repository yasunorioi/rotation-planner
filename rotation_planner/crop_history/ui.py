"""
rotation_planner.crop_history.ui - 作付履歴 Gradio UIモジュール

ほ場×年度のマトリックス形式で作付履歴を表示・編集するUI。

Usage:
    from rotation_planner.crop_history import create_crop_history_ui

    with gr.Tab("📜 作付履歴"):
        components = create_crop_history_ui(user_state)
"""

import gradio as gr
import pandas as pd
from typing import Dict, Any, List, Tuple, Optional
import csv
import io

from rotation_planner.common import (
    CropHistoryRepository,
    FieldRepository,
    UserCropRepository,
    format_success,
    format_error,
    format_warning,
    format_info,
)
from rotation_planner.app.constraints import DEFAULT_CONSTRAINTS


# =============================================================================
# 定数
# =============================================================================

# 年度選択肢（R1〜R20）
YEAR_CHOICES = [f"R{i}" for i in range(1, 21)]

# デフォルト年度範囲
DEFAULT_START_YEAR = "R4"
DEFAULT_END_YEAR = "R10"


# =============================================================================
# ヘルパー関数
# =============================================================================

def get_rotation_gap_crops(user_id: int) -> Dict[str, int]:
    """
    連作障害作物とその必要間隔年数を取得

    Returns:
        {作物名: 間隔年数} の辞書（min_gap_years >= 1 のもののみ）
    """
    rotation_gaps = {}

    # ユーザーの作物リストを取得
    user_crops = UserCropRepository.get_user_crops(user_id)

    for crop_info in user_crops:
        crop_name = crop_info.get("name", "")
        parent_name = crop_info.get("parent_name", crop_name)

        # DEFAULT_CONSTRAINTSからmin_gap_yearsを取得
        if parent_name in DEFAULT_CONSTRAINTS:
            gap = DEFAULT_CONSTRAINTS[parent_name].get("min_gap_years", 0)
            if gap >= 1:
                rotation_gaps[crop_name] = gap

    return rotation_gaps


def year_to_int(year_str: str) -> int:
    """年度文字列を整数に変換（R7 -> 7）"""
    if year_str.startswith("R"):
        return int(year_str[1:])
    return int(year_str)


def check_rotation_warnings(
    df: pd.DataFrame,
    rotation_gaps: Dict[str, int],
    year_columns: List[str]
) -> List[str]:
    """
    連作警告をチェック

    Args:
        df: マトリックスDataFrame（行: ほ場、列: 年度）
        rotation_gaps: {作物名: 必要間隔年数}
        year_columns: 年度カラムのリスト

    Returns:
        警告メッセージのリスト
    """
    warnings = []

    if df is None or df.empty:
        return warnings

    # ほ場名カラム（最初のカラム）
    field_col = df.columns[0]

    for _, row in df.iterrows():
        field_name = str(row[field_col])

        # 年度ごとの作物を取得
        crops_by_year = {}
        for year_col in year_columns:
            crop = str(row.get(year_col, "")).strip()
            if crop and crop != "nan":
                # *マークを除去して比較
                crop_clean = crop.replace("*", "").strip()
                crops_by_year[year_col] = crop_clean

        # 連作障害作物のチェック
        for year_col, crop in crops_by_year.items():
            if crop not in rotation_gaps:
                continue

            required_gap = rotation_gaps[crop]
            current_year = year_to_int(year_col)

            # 過去の履歴をチェック
            for past_year_col, past_crop in crops_by_year.items():
                if past_year_col == year_col:
                    continue

                past_year = year_to_int(past_year_col)

                # 過去の年度で同じ作物が作付けされていたら
                if past_crop == crop and past_year < current_year:
                    actual_gap = current_year - past_year

                    if actual_gap < required_gap:
                        warnings.append(
                            f"⚠️ {field_name}: {crop}({year_col})の前回作付けは{past_year_col}。"
                            f"{required_gap}年間隔が必要です（現在{actual_gap}年）"
                        )
                        break  # 最も近い警告のみ

    return warnings


def build_history_matrix(
    user_id: int,
    start_year: str,
    end_year: str,
    selected_fields: List[str] = None
) -> Tuple[pd.DataFrame, List[str]]:
    """
    作付履歴マトリックスを構築

    Args:
        user_id: ユーザーID
        start_year: 開始年度（R4など）
        end_year: 終了年度（R10など）
        selected_fields: 選択されたほ場コードリスト（Noneなら全ほ場）

    Returns:
        (DataFrame, 年度カラムリスト)
    """
    # ほ場一覧を取得
    fields = FieldRepository.get_fields(user_id)
    if not fields:
        return pd.DataFrame(), []

    # 選択されたほ場のフィルタリング
    if selected_fields:
        fields = [f for f in fields if f.get("field_code") in selected_fields]

    # 全履歴を取得
    all_history = CropHistoryRepository.get_all_history_for_user(user_id)

    # 履歴を {field_id: {year: crop}} の形式に変換
    history_map = {}
    inferred_map = {}  # 推論フラグ用
    for h in all_history:
        fid = h.get("field_id")
        year = h.get("year")
        crop = h.get("crop", "")
        is_inferred = h.get("is_inferred", 0)

        if fid not in history_map:
            history_map[fid] = {}
            inferred_map[fid] = {}
        history_map[fid][year] = crop
        inferred_map[fid][year] = is_inferred

    # 年度範囲を計算
    start_num = year_to_int(start_year)
    end_num = year_to_int(end_year)
    year_columns = [f"R{i}" for i in range(start_num, end_num + 1)]

    # マトリックスを構築
    rows = []
    for f in fields:
        field_id = f.get("id")
        field_code = f.get("field_code", "")
        field_name = f.get("name", field_code)
        display_name = f"{field_code} {field_name}" if field_name else field_code

        row = {"ほ場": display_name, "_field_id": field_id, "_field_code": field_code}

        for year_col in year_columns:
            crop = history_map.get(field_id, {}).get(year_col, "")
            is_inferred = inferred_map.get(field_id, {}).get(year_col, 0)

            # 推論フラグがあれば*マーク
            if crop and is_inferred:
                crop = f"{crop}*"

            row[year_col] = crop

        rows.append(row)

    df = pd.DataFrame(rows)

    return df, year_columns


def get_field_choices(user_id: int) -> List[str]:
    """ユーザーのほ場選択肢を取得"""
    fields = FieldRepository.get_fields(user_id)
    return [f.get("field_code", "") for f in fields if f.get("field_code")]


# =============================================================================
# UI操作関数
# =============================================================================

def load_history_matrix(
    user_state: Dict[str, Any],
    start_year: str,
    end_year: str,
    view_mode: str,
    selected_fields: List[str]
) -> Tuple[pd.DataFrame, str]:
    """
    作付履歴マトリックスを読み込む

    Returns:
        (DataFrame, 警告メッセージ)
    """
    if not user_state or not user_state.get("user_id"):
        return pd.DataFrame(), format_error("ログインが必要です")

    user_id = user_state.get("user_id")

    # 全ほ場モードの場合はselected_fieldsをNoneに
    fields_filter = None if view_mode == "全ほ場" else selected_fields

    df, year_columns = build_history_matrix(user_id, start_year, end_year, fields_filter)

    if df.empty:
        return pd.DataFrame(), format_warning("ほ場が登録されていません")

    # 連作警告チェック
    rotation_gaps = get_rotation_gap_crops(user_id)
    warnings = check_rotation_warnings(df, rotation_gaps, year_columns)

    # 表示用に _field_id と _field_code カラムを非表示にする
    display_df = df.drop(columns=["_field_id", "_field_code"], errors="ignore")

    # メッセージ
    if warnings:
        warning_text = "\n".join(warnings[:10])  # 最大10件
        if len(warnings) > 10:
            warning_text += f"\n... 他{len(warnings) - 10}件の警告"
        return display_df, format_warning(warning_text)
    else:
        return display_df, format_success(f"{len(df)}件のほ場を読み込みました")


def save_history_matrix(
    user_state: Dict[str, Any],
    df: pd.DataFrame,
    start_year: str,
    end_year: str
) -> str:
    """
    マトリックスの変更を保存

    Returns:
        結果メッセージ
    """
    if not user_state or not user_state.get("user_id"):
        return format_error("ログインが必要です")

    if df is None or df.empty:
        return format_error("保存するデータがありません")

    user_id = user_state.get("user_id")

    # ほ場コードからfield_idを取得するためのマッピング
    fields = FieldRepository.get_fields(user_id)
    field_code_to_id = {}
    for f in fields:
        code = f.get("field_code", "")
        # ほ場カラムは "A-1 北1号" のような形式なので、先頭のコード部分を抽出
        field_code_to_id[code] = f.get("id")

    # 年度カラムを特定
    start_num = year_to_int(start_year)
    end_num = year_to_int(end_year)
    year_columns = [f"R{i}" for i in range(start_num, end_num + 1)]

    # 更新データを構築
    updates = []
    for _, row in df.iterrows():
        field_display = str(row.get("ほ場", ""))
        # ほ場コードを抽出（スペースで分割して最初の部分）
        field_code = field_display.split()[0] if field_display else ""
        field_id = field_code_to_id.get(field_code)

        if not field_id:
            continue

        for year_col in year_columns:
            if year_col not in df.columns:
                continue

            crop = str(row.get(year_col, "")).strip()
            # *マークを除去
            crop = crop.replace("*", "").strip()

            updates.append({
                "field_id": field_id,
                "year": year_col,
                "crop": crop
            })

    if not updates:
        return format_error("保存するデータがありません")

    # 一括更新
    count = CropHistoryRepository.bulk_update_history(updates)

    return format_success(f"{count}件の履歴を保存しました")


def export_history_csv(
    user_state: Dict[str, Any],
    df: pd.DataFrame,
    start_year: str,
    end_year: str
) -> Tuple[Optional[str], str]:
    """
    作付履歴をCSVエクスポート

    Returns:
        (ファイルパス, メッセージ)
    """
    if not user_state or not user_state.get("user_id"):
        return None, format_error("ログインが必要です")

    if df is None or df.empty:
        return None, format_error("エクスポートするデータがありません")

    username = user_state.get("username", "user")

    # CSVを生成
    output_path = f"/tmp/crop_history_{username}.csv"

    # *マークを除去したデータを出力
    export_df = df.copy()
    for col in export_df.columns:
        if col != "ほ場":
            export_df[col] = export_df[col].astype(str).str.replace("*", "", regex=False)

    export_df.to_csv(output_path, index=False, encoding="utf-8-sig")

    return output_path, format_success(f"CSVを出力しました: {output_path}")


def update_field_choices(user_state: Dict[str, Any]) -> gr.Dropdown:
    """ほ場選択肢を更新"""
    if not user_state or not user_state.get("user_id"):
        return gr.Dropdown(choices=[], value=[])

    user_id = user_state.get("user_id")
    choices = get_field_choices(user_id)
    return gr.Dropdown(choices=choices, value=[])


def toggle_field_selector(view_mode: str) -> gr.Dropdown:
    """表示モードに応じてほ場セレクターの表示を切り替え"""
    return gr.Dropdown(visible=(view_mode == "ほ場選択"))


# =============================================================================
# メインUIコンポーネント
# =============================================================================

def create_crop_history_ui(user_state: gr.State) -> Dict[str, Any]:
    """
    作付履歴UIコンポーネントを作成

    Args:
        user_state: ユーザー情報を保持するgr.State

    Returns:
        components: UI操作に必要なコンポーネントの辞書
    """

    gr.Markdown("""
    ## 📜 作付履歴

    ほ場×年度のマトリックス形式で作付履歴を表示・編集します。
    - **直接編集**: テーブルのセルをクリックして編集できます
    - **推論マーク**: 「*」が付いた値は推論で補完されたものです
    - **連作警告**: 連作障害作物の間隔不足を自動で警告します
    """)

    with gr.Row():
        with gr.Column(scale=1):
            # ほ場選択セクション
            gr.Markdown("### 📋 表示設定")

            view_mode = gr.Radio(
                choices=["全ほ場", "ほ場選択"],
                value="全ほ場",
                label="表示モード"
            )

            field_selector = gr.Dropdown(
                choices=[],
                multiselect=True,
                label="ほ場選択",
                visible=False
            )

        with gr.Column(scale=1):
            # 年度範囲
            gr.Markdown("### 📅 年度範囲")

            with gr.Row():
                start_year = gr.Dropdown(
                    choices=YEAR_CHOICES,
                    value=DEFAULT_START_YEAR,
                    label="開始年"
                )
                end_year = gr.Dropdown(
                    choices=YEAR_CHOICES,
                    value=DEFAULT_END_YEAR,
                    label="終了年"
                )

    # 操作ボタン（読み込みは自動なので削除）
    with gr.Row():
        reload_btn = gr.Button("🔄 再読込", variant="secondary")
        save_btn = gr.Button("💾 保存", variant="primary")
        export_btn = gr.Button("📥 CSVエクスポート", variant="secondary")

    # マトリックス表示
    history_table = gr.Dataframe(
        value=pd.DataFrame(),
        label="作付履歴マトリックス",
        interactive=True,
        wrap=True,
        row_count=(10, "dynamic")
    )

    # 警告表示エリア
    warning_area = gr.HTML("")

    # エクスポートファイル
    export_file = gr.File(label="ダウンロード", visible=False)

    # イベントハンドラ
    view_mode.change(
        fn=toggle_field_selector,
        inputs=[view_mode],
        outputs=[field_selector]
    )

    reload_btn.click(
        fn=load_history_matrix,
        inputs=[user_state, start_year, end_year, view_mode, field_selector],
        outputs=[history_table, warning_area]
    )

    save_btn.click(
        fn=save_history_matrix,
        inputs=[user_state, history_table, start_year, end_year],
        outputs=[warning_area]
    )

    export_btn.click(
        fn=export_history_csv,
        inputs=[user_state, history_table, start_year, end_year],
        outputs=[export_file, warning_area]
    ).then(
        fn=lambda: gr.File(visible=True),
        outputs=[export_file]
    )

    return {
        "view_mode": view_mode,
        "field_selector": field_selector,
        "start_year": start_year,
        "end_year": end_year,
        "reload_btn": reload_btn,
        "save_btn": save_btn,
        "export_btn": export_btn,
        "history_table": history_table,
        "warning_area": warning_area,
        "export_file": export_file,
        "update_field_choices": update_field_choices,
    }


# =============================================================================
# 初期化関数（portal.py から呼び出し）
# =============================================================================

def load_initial_history(user_state: Dict[str, Any]) -> Tuple[gr.Dropdown, pd.DataFrame, str]:
    """
    作付履歴タブの初期化（全ほ場を自動ロード）

    Returns:
        (ほ場選択肢, 履歴テーブル, 警告メッセージ)
    """
    if not user_state or not user_state.get("user_id"):
        return gr.Dropdown(choices=[], value=[]), pd.DataFrame(), ""

    user_id = user_state.get("user_id")
    choices = get_field_choices(user_id)

    # 初期表示は全ほ場
    df, year_columns = build_history_matrix(user_id, DEFAULT_START_YEAR, DEFAULT_END_YEAR, None)

    if df.empty:
        return gr.Dropdown(choices=choices, value=[]), pd.DataFrame(), format_warning("ほ場が登録されていません")

    # 連作警告チェック
    rotation_gaps = get_rotation_gap_crops(user_id)
    warnings = check_rotation_warnings(df, rotation_gaps, year_columns)

    # 表示用に _field_id と _field_code カラムを非表示にする
    display_df = df.drop(columns=["_field_id", "_field_code"], errors="ignore")

    # メッセージ
    if warnings:
        warning_text = "\n".join(warnings[:10])
        if len(warnings) > 10:
            warning_text += f"\n... 他{len(warnings) - 10}件の警告"
        return gr.Dropdown(choices=choices, value=[]), display_df, format_warning(warning_text)
    else:
        return gr.Dropdown(choices=choices, value=[]), display_df, format_success(f"{len(display_df)}件のほ場を読み込みました")


# =============================================================================
# 公開API
# =============================================================================

__all__ = [
    "create_crop_history_ui",
    "load_initial_history",
]
