"""
rotation_planner.data_management.ui - データ管理UI

エクスポート・インポート機能を集約したGradio UIコンポーネント。
portal.pyの「📥 データ管理」タブで使用。

Usage:
    from rotation_planner.data_management import create_data_management_ui

    with gr.Tab("📥 データ管理"):
        create_data_management_ui(user_state)
"""

import os
import gradio as gr
from typing import Dict, Any, Optional, Tuple

# アプリのルートパス
APP_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# =============================================================================
# エクスポート関数（既存モジュールのラッパー）
# =============================================================================

def export_fields(user_state: Dict[str, Any]) -> Tuple[Optional[str], str]:
    """ほ場一覧CSVエクスポート"""
    try:
        from rotation_planner.common.export import export_fields_csv
        return export_fields_csv(user_state)
    except ImportError:
        # フォールバック: field.crudの関数を使用
        from rotation_planner.field.crud import export_csv_with_state
        return export_csv_with_state(user_state)


def export_pesticide_orders(
    summary_data: list,
    detail_data: list = None,
    user_state: Dict[str, Any] = None
) -> Tuple[Optional[str], str]:
    """農薬発注CSVエクスポート"""
    try:
        from rotation_planner.common.export import export_pesticide_order_csv
        return export_pesticide_order_csv(summary_data, detail_data, user_state)
    except ImportError:
        return None, "エラー: エクスポート機能が利用できません"


# =============================================================================
# インポート関数
# =============================================================================

def import_fields_csv(
    csv_file,
    user_state: Dict[str, Any]
) -> Tuple[str, str]:
    """
    ほ場CSVインポート

    Args:
        csv_file: アップロードされたCSVファイル
        user_state: ユーザー状態

    Returns:
        (結果メッセージ, 詳細ログ)
    """
    if not user_state or not user_state.get("user_id"):
        return "エラー: ログインが必要です", ""

    if csv_file is None:
        return "エラー: CSVファイルを選択してください", ""

    try:
        import pandas as pd
        from rotation_planner.common.db_access import FieldRepository

        user_id = user_state.get("user_id")

        # CSVを読み込み
        df = pd.read_csv(csv_file, encoding="utf-8-sig")

        # カラム名を正規化
        column_map = {
            "ほ場ID": "field_code",
            "field_id": "field_code",
            "地区": "district",
            "ほ場名": "name",
            "面積": "area",
            "area": "area",
            "beet_forbidden": "beet_forbidden",
            "禁止": "beet_forbidden",
        }

        df.columns = [column_map.get(col, col) for col in df.columns]

        # 必須カラムチェック
        required = ["field_code"]
        missing = [c for c in required if c not in df.columns]
        if missing:
            return f"エラー: 必須カラムがありません: {missing}", ""

        # インポート処理
        success_count = 0
        error_count = 0
        logs = []

        for _, row in df.iterrows():
            field_code = str(row.get("field_code", "")).strip()
            if not field_code:
                continue

            # 重複チェック
            existing = FieldRepository.get_field_by_code(user_id, field_code)
            if existing:
                logs.append(f"スキップ: {field_code} (既存)")
                error_count += 1
                continue

            # 面積を取得
            area = row.get("area", 0)
            try:
                area = float(area) if pd.notna(area) else 0
            except (ValueError, TypeError):
                area = 0

            # area_haに変換（100a以上ならa、それ以下ならha）
            area_ha = area / 100 if area > 10 else area

            field_data = {
                "field_code": field_code,
                "district": str(row.get("district", "")).strip(),
                "name": str(row.get("name", field_code)).strip(),
                "area_ha": area_ha,
                "beet_forbidden": 1 if row.get("beet_forbidden") in [1, "1", True, "Yes", "yes"] else 0,
                "coordinates_json": "[]"  # 座標なし
            }

            try:
                FieldRepository.create_field(user_id, field_data)
                success_count += 1
                logs.append(f"登録: {field_code}")
            except Exception as e:
                error_count += 1
                logs.append(f"エラー: {field_code} - {str(e)}")

        result_msg = f"インポート完了: {success_count}件登録, {error_count}件スキップ"
        return result_msg, "\n".join(logs)

    except Exception as e:
        return f"エラー: {str(e)}", ""


def import_rotation_plan_csv(
    csv_file,
    plan_name: str,
    user_state: Dict[str, Any]
) -> Tuple[str, str]:
    """
    輪作計画CSVインポート

    Args:
        csv_file: アップロードされたCSVファイル
        plan_name: 計画名
        user_state: ユーザー状態

    Returns:
        (結果メッセージ, 詳細ログ)
    """
    if not user_state or not user_state.get("user_id"):
        return "エラー: ログインが必要です", ""

    if csv_file is None:
        return "エラー: CSVファイルを選択してください", ""

    if not plan_name.strip():
        return "エラー: 計画名を入力してください", ""

    try:
        import pandas as pd
        from rotation_planner.common.db_access import (
            PlanRepository,
            UserCropRepository,
            FieldRepository,
            CropHistoryRepository,
        )
        from rotation_planner.app.constraints import DEFAULT_CONSTRAINTS

        user_id = user_state.get("user_id")

        # CSVを読み込み
        df = pd.read_csv(csv_file, encoding="utf-8-sig")

        # カラム名を正規化
        column_map = {
            "ほ場ID": "field_code",
            "ほ場コード": "field_code",
            "ほ場名": "field_name",
            "地区": "district",
            "年度": "year",
            "年": "year",
            "作物": "crop",
        }

        df.columns = [column_map.get(col, col) for col in df.columns]

        # 必須カラムチェック
        required = ["field_code", "year", "crop"]
        missing = [c for c in required if c not in df.columns]
        if missing:
            return f"エラー: 必須カラムがありません: {missing}", ""

        # ===================================================================
        # バリデーション強化: ユーザー作物設定の取得
        # ===================================================================
        user_crops = UserCropRepository.get_user_crops(user_id)
        user_crop_names = set(c.get("name", "") for c in user_crops if c.get("name"))

        # 連作障害作物の min_gap_years を取得（ユーザー作物 + DEFAULT_CONSTRAINTS）
        rotation_gap_crops = {}
        for crop_info in user_crops:
            crop_name = crop_info.get("name", "")
            parent_name = crop_info.get("parent_name", crop_name)
            if parent_name in DEFAULT_CONSTRAINTS:
                gap = DEFAULT_CONSTRAINTS[parent_name].get("min_gap_years", 0)
                if gap >= 1:
                    rotation_gap_crops[crop_name] = gap

        # ===================================================================
        # バリデーション: 作物の空欄チェック・存在チェック
        # ===================================================================
        errors = []
        warnings = []

        for idx, row in df.iterrows():
            row_num = idx + 2  # ヘッダー行を考慮
            raw_crop = row.get("crop", "")
            crop = "" if pd.isna(raw_crop) else str(raw_crop).strip()

            # 1. 作物が空欄 → エラー
            if not crop:
                errors.append(f"行{row_num}の作物が空欄です")
                continue

            # 2. 作物がユーザーの作物設定に存在しない → エラー
            if user_crop_names and crop not in user_crop_names:
                errors.append(f"作物「{crop}」は作物設定に登録されていません（行{row_num}）")

        # エラーがあればインポート拒否
        if errors:
            error_msg = "バリデーションエラー:\n" + "\n".join(errors[:10])
            if len(errors) > 10:
                error_msg += f"\n... 他{len(errors) - 10}件のエラー"
            return f"エラー: {len(errors)}件のバリデーションエラーがあります", error_msg

        # ===================================================================
        # バリデーション: 連作障害作物の過去履歴チェック（警告のみ）
        # ===================================================================
        # ほ場コード → field_id マッピング
        fields = FieldRepository.get_fields(user_id)
        field_code_to_id = {f["field_code"]: f["id"] for f in fields}

        # 連作障害チェック: CSVの最小年を取得
        years_in_csv = []
        for _, row in df.iterrows():
            year_str = str(row.get("year", "")).strip()
            if year_str.isdigit():
                years_in_csv.append(int(year_str))
        min_year = min(years_in_csv) if years_in_csv else None

        if min_year and rotation_gap_crops:
            # ほ場ごとに連作障害作物の履歴をチェック
            checked_fields = set()
            for _, row in df.iterrows():
                field_code = str(row.get("field_code", "")).strip()
                crop = str(row.get("crop", "")).strip()

                if crop not in rotation_gap_crops:
                    continue
                if field_code in checked_fields:
                    continue

                gap_years = rotation_gap_crops[crop]
                field_id = field_code_to_id.get(field_code)

                if field_id:
                    history = CropHistoryRepository.get_history(field_id)
                    history_years = [int(h["year"]) for h in history if str(h.get("year", "")).isdigit()]

                    # 必要な過去年度（計画開始年の前gap_years年分）
                    required_years = set(range(min_year - gap_years, min_year))
                    existing_years = set(history_years)
                    missing_years = required_years - existing_years

                    if missing_years:
                        warnings.append(
                            f"⚠️ ほ場{field_code}の{crop}に過去{gap_years}年の履歴がありません。"
                            f"連作チェックが不正確になる可能性があります"
                        )
                    checked_fields.add(field_code)

        # 計画詳細を作成
        details = []
        for _, row in df.iterrows():
            field_code = str(row.get("field_code", "")).strip()
            details.append({
                "field_id": field_code_to_id.get(field_code),
                "field_code": field_code,
                "field_name": str(row.get("field_name", "")).strip(),
                "district": str(row.get("district", "")).strip(),
                "year": str(row.get("year", "")).strip(),
                "crop": str(row.get("crop", "")).strip(),
            })

        if not details:
            return "エラー: インポートするデータがありません", ""

        # 計画を保存
        plan_id = PlanRepository.create_plan(
            user_id=user_id,
            data={
                'name': plan_name.strip(),
                'start_year': '',
                'end_year': '',
                'details': details
            }
        )

        # 結果メッセージを作成
        result_msg = f"計画「{plan_name}」を登録しました（{len(details)}行）"
        if warnings:
            result_msg += f"\n⚠️ {len(warnings)}件の警告があります"

        log_lines = [f"計画ID: {plan_id}"]
        if warnings:
            log_lines.append("")
            log_lines.append("=== 警告 ===")
            log_lines.extend(warnings)

        return result_msg, "\n".join(log_lines)

    except Exception as e:
        return f"エラー: {str(e)}", ""


# =============================================================================
# メインUI関数
# =============================================================================

def create_data_management_ui(user_state: gr.State):
    """
    データ管理UIを作成

    Args:
        user_state: gr.State - ユーザー状態

    Returns:
        dict: UIコンポーネントの辞書
    """
    gr.Markdown("""
    ## 📥 データ管理

    CSV形式でのデータ入出力を行います。
    """)

    # =========================================================================
    # エクスポートセクション
    # =========================================================================
    with gr.Accordion("📤 エクスポート（データ出力）", open=True):
        gr.Markdown("登録済みデータをCSVファイルとしてダウンロードできます。")

        with gr.Row():
            # --- ほ場一覧エクスポート ---
            with gr.Column():
                gr.Markdown("### 🗺️ ほ場一覧")
                export_fields_btn = gr.Button("📥 ほ場一覧をダウンロード", variant="primary")
                export_fields_file = gr.File(label="ダウンロード", interactive=False)
                export_fields_msg = gr.Textbox(label="結果", interactive=False, lines=1)

            # --- 農薬発注エクスポート ---
            with gr.Column():
                gr.Markdown("### 💊 農薬発注")
                gr.Markdown("*農薬発注タブで計算後にダウンロード可能*", elem_classes=["text-muted"])
                # 農薬発注は計算結果が必要なので、ここでは参照のみ

    # =========================================================================
    # インポートセクション
    # =========================================================================
    with gr.Accordion("📥 インポート（データ入力）", open=False):
        gr.Markdown("CSVファイルからデータを一括登録できます。")

        with gr.Tabs():
            # --- ほ場インポート ---
            with gr.TabItem("🗺️ ほ場インポート"):
                with gr.Row():
                    gr.DownloadButton(
                        "📄 サンプルCSV",
                        value=os.path.join(APP_DIR, "サンプルほ場.csv"),
                        size="sm"
                    )
                    gr.DownloadButton(
                        "📄 空テンプレート",
                        value=os.path.join(APP_DIR, "ほ場テンプレート.csv"),
                        size="sm"
                    )

                import_fields_csv_input = gr.File(
                    label="ほ場CSV",
                    file_types=[".csv"]
                )
                import_fields_btn = gr.Button("📤 インポート実行", variant="primary")
                import_fields_msg = gr.Textbox(label="結果", interactive=False, lines=1)
                import_fields_log = gr.Textbox(label="詳細ログ", interactive=False, lines=5)

            # --- 輪作計画インポート ---
            with gr.TabItem("🌾 輪作計画インポート"):
                with gr.Row():
                    gr.DownloadButton(
                        "📄 輪作計画テンプレート",
                        value=os.path.join(APP_DIR, "輪作計画テンプレート.csv"),
                        size="sm"
                    )

                import_plan_name = gr.Textbox(
                    label="計画名",
                    placeholder="例: 2026年度輪作計画",
                    lines=1
                )
                import_plan_csv_input = gr.File(
                    label="輪作計画CSV",
                    file_types=[".csv"]
                )
                import_plan_btn = gr.Button("📤 インポート実行", variant="primary")
                import_plan_msg = gr.Textbox(label="結果", interactive=False, lines=1)
                import_plan_log = gr.Textbox(label="詳細ログ", interactive=False, lines=5)

    # =========================================================================
    # イベントハンドラ
    # =========================================================================

    # エクスポート: ほ場一覧
    export_fields_btn.click(
        fn=export_fields,
        inputs=[user_state],
        outputs=[export_fields_file, export_fields_msg]
    )

    # インポート: ほ場
    import_fields_btn.click(
        fn=import_fields_csv,
        inputs=[import_fields_csv_input, user_state],
        outputs=[import_fields_msg, import_fields_log]
    )

    # インポート: 輪作計画
    import_plan_btn.click(
        fn=import_rotation_plan_csv,
        inputs=[import_plan_csv_input, import_plan_name, user_state],
        outputs=[import_plan_msg, import_plan_log]
    )

    return {
        "export_fields_btn": export_fields_btn,
        "import_fields_btn": import_fields_btn,
        "import_plan_btn": import_plan_btn,
    }
