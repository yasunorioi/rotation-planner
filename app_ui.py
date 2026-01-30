"""
輪作計画メーカー - UIモジュール
portal.py との統合用。認証は portal.py で一元管理。

Note: このファイルは後方互換性のために残されています。
      新しいコードは rotation_planner.app パッケージを使用してください。
"""

import gradio as gr
import os

os.environ["GRADIO_ANALYTICS_ENABLED"] = "False"

# 新しいパッケージから関数・定数をインポート
from rotation_planner.app import (
    # 定数
    DEFAULT_CROPS,
    DEFAULT_PREFERRED_TRANSITIONS,
    DEFAULT_MAIN_CROPS,
    # 関数
    build_constraints_table,
    update_constraints_table,
    update_constraints_from_csv,
    run_optimization,
)

# 認証モジュール（ユーザー情報表示用）
from rotation_planner.common import get_user_info

# アプリのパス
APP_DIR = os.path.dirname(os.path.abspath(__file__))


def create_rotation_planner_ui(user_state: gr.State = None):
    """
    輪作計画メーカーのUIを作成

    Args:
        user_state: 外部から渡されるユーザー状態（portal.py統合時）
                   None の場合は内部で作成

    Returns:
        gr.Blocks: Gradioアプリケーション
    """

    with gr.Blocks(title="輪作計画メーカー") as app:
        # ユーザー情報State（外部から渡されない場合は内部で作成）
        if user_state is None:
            user_state = gr.State(None)

        # ヘッダー（ユーザー情報表示）
        with gr.Row():
            with gr.Column(scale=4):
                gr.Markdown("""
                # 🌾 輪作計画メーカー

                過去の作付データ（CSV）から、将来の輪作計画を自動生成します。
                """)
            with gr.Column(scale=1):
                user_info_display = gr.Markdown("", elem_id="user_info")

        # ログイン時のユーザー情報読み込み
        def on_load(request: gr.Request):
            if request and hasattr(request, 'username') and request.username:
                user = get_user_info(request.username)
                if user:
                    role_label = {
                        "admin": "管理者",
                        "ja_staff": "JA職員",
                        "farmer": "農家"
                    }.get(user["role"], user["role"])
                    display_text = f"👤 **{user['display_name']}** ({role_label})"
                    return user, display_text
            return None, ""

        app.load(on_load, outputs=[user_state, user_info_display])

        with gr.Row():
            gr.DownloadButton("📥 サンプルCSV", value=os.path.join(APP_DIR, "template_example.csv"))
            gr.DownloadButton("📥 空テンプレート", value=os.path.join(APP_DIR, "template_empty.csv"))

        gr.Markdown("""
        ### ⛔ 固定の禁止遷移
        - **てんさい→秋小麦**: 作期重複（ビート5-11月、秋小麦9月播種→翌7月収穫）
        - **春小麦→秋小麦**: 病害対策
        - **連作禁止**: 同一作物の連続年作付はNG
        """)

        with gr.Row():
            with gr.Column(scale=1):
                gr.Markdown("## 📂 入力")

                csv_file = gr.File(label="CSVファイル", file_types=[".csv"])

                with gr.Row():
                    area_unit = gr.Radio(
                        choices=["a (アール)", "ha (ヘクタール)"],
                        value="a (アール)",
                        label="面積の単位"
                    )
                    n_years = gr.Slider(
                        minimum=1, maximum=10, value=5, step=1,
                        label="将来年数"
                    )

                unknown_mode = gr.Radio(
                    choices=["制約をかけない（推奨）", "安全側（不明年を考慮）"],
                    value="制約をかけない（推奨）",
                    label="空欄(UNKNOWN)の扱い"
                )

                precision_mode = gr.Radio(
                    choices=["標準（10秒）", "高精度（60秒）"],
                    value="標準（10秒）",
                    label="計算精度"
                )

                tensai_required = gr.Checkbox(
                    value=False,
                    label="てんさい必須（毎年1ほ場以上）"
                )

                infer_unknown = gr.Checkbox(
                    value=True,
                    label="空欄を推論で補完（*マーク付き）"
                )

                district_grouping = gr.Checkbox(
                    value=True,
                    label="地区まとめを優先（同じ地区に同じ作物）"
                )

                gr.Markdown("## 🌱 作物マスター")
                crop_text = gr.Textbox(
                    value="\n".join(DEFAULT_CROPS),
                    label="作物リスト（改行区切り）",
                    lines=10
                )

            with gr.Column(scale=1):
                gr.Markdown("## ⚙️ 制約設定")

                with gr.Row():
                    constraints_sample_btn = gr.DownloadButton(
                        "📥 制約サンプルCSV",
                        value="constraints_example.csv"
                    )
                    constraints_empty_btn = gr.DownloadButton(
                        "📥 制約テンプレート",
                        value="constraints_empty.csv"
                    )

                constraints_file = gr.File(
                    label="制約CSV（オプション: アップロードで上書き）",
                    file_types=[".csv"],
                    type="filepath"
                )

                constraints_table = gr.Dataframe(
                    value=build_constraints_table(DEFAULT_CROPS),
                    label="制約テーブル",
                    headers=["作物", "最小(ha)", "最大(ha)", "間隔(年)", "最小筆数", "最大筆数"],
                    datatype=["str", "number", "number", "number", "number", "number"],
                    interactive=True,
                    row_count=(10, "dynamic")
                )

                gr.Markdown("""
                **列の説明:**
                - `min_ha`: 年間面積下限(ha)、空欄or0=下限なし
                - `cap_ha`: 年間面積上限(ha)、空欄or0=無制限
                - `min_gap_years`: 最小作付間隔(年)
                - `min_fields`: 最小ほ場数
                - `max_fields`: 最大ほ場数、空欄or0=無制限
                """)

                forbidden_text = gr.Textbox(
                    value="",
                    label="追加禁止遷移（例: 秋小麦->春小麦, 大豆->てんさい）",
                    placeholder="from->to, from->to, ..."
                )

                preferred_text = gr.Textbox(
                    value=DEFAULT_PREFERRED_TRANSITIONS,
                    label="優先遷移（例: てんさい->大豆:10）",
                    placeholder="from->to:weight, ..."
                )

                main_crops_text = gr.Textbox(
                    value=DEFAULT_MAIN_CROPS,
                    label="主作物（面積変動を抑制、カンマ区切り）"
                )

        # 作物マスター変更時に制約テーブルを更新
        crop_text.change(
            fn=update_constraints_table,
            inputs=[crop_text, constraints_table],
            outputs=[constraints_table]
        )

        # 制約CSVアップロード時に制約テーブルを更新
        constraints_file.change(
            fn=update_constraints_from_csv,
            inputs=[constraints_file],
            outputs=[constraints_table]
        )

        run_btn = gr.Button("🚀 計画を生成", variant="primary", size="lg")

        gr.Markdown("## 📊 結果")

        message_box = gr.Textbox(label="実行結果", lines=5, interactive=False)

        with gr.Tabs():
            with gr.TabItem("ほ場×年 計画表"):
                result_table = gr.Dataframe(
                    label="ほ場別計画",
                    interactive=False,
                    wrap=True
                )

            with gr.TabItem("年別 面積合計"):
                summary_table = gr.Dataframe(
                    label="年別作物面積(ha)",
                    interactive=False,
                    wrap=True
                )

        csv_download = gr.File(label="📥 計画CSVダウンロード")

        run_btn.click(
            fn=run_optimization,
            inputs=[
                csv_file, area_unit, n_years, crop_text, constraints_table,
                forbidden_text, preferred_text, main_crops_text, unknown_mode,
                tensai_required, precision_mode, infer_unknown, district_grouping
            ],
            outputs=[result_table, summary_table, csv_download, message_box]
        )

    return app


# =============================================================================
# 単独起動用（認証なし）
# =============================================================================

if __name__ == "__main__":
    app = create_rotation_planner_ui()
    app.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False,
        allowed_paths=[
            os.path.join(APP_DIR, "template_example.csv"),
            os.path.join(APP_DIR, "template_empty.csv")
        ]
    )
