"""
管理機能UI - 管理者向け
ユーザー管理・組織設定・システム情報
"""

import gradio as gr
import json
import os
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional
from datetime import datetime

from rotation_planner.common import (
    load_users, hash_password, add_user as auth_add_user,
    update_password as auth_update_password,
    update_user_role as auth_update_user_role,
    delete_user as auth_delete_user,
    get_admin_count,
    ROLE_ADMIN, ROLE_JA_STAFF, ROLE_FARMER,
)

# =============================================================================
# 定数
# =============================================================================

DB_FILE = Path(__file__).parent / "data" / "rotation_planner.db"
FUDE_CACHE_DIR = Path(__file__).parent / "data" / "fude_cache"
SETTINGS_FILE = Path(__file__).parent / "data" / "settings.json"

ROLES = [
    ("admin", "管理者"),
    ("ja_staff", "JA職員"),
    ("farmer", "農家"),
]

ROLE_CHOICES = [r[0] for r in ROLES]
ROLE_DISPLAY = {r[0]: r[1] for r in ROLES}


# =============================================================================
# ユーザー管理
# =============================================================================

def get_users_for_display() -> List[List[Any]]:
    """ユーザー一覧を表示用に取得（DB版）"""
    users = load_users()
    display_data = []

    for i, user in enumerate(users):
        display_data.append([
            i,
            user.get("username", ""),
            ROLE_DISPLAY.get(user.get("role", ""), user.get("role", "")),
            user.get("display_name", ""),
            str(user.get("id", "")),  # ユーザーID
            "●●●●●●"  # パスワードは非表示
        ])

    return display_data


def _get_username_by_row(row_index: int) -> Optional[str]:
    """行番号からユーザー名を取得"""
    users = load_users()
    if row_index < 0 or row_index >= len(users):
        return None
    return users[row_index].get("username")


def _get_user_role_by_row(row_index: int) -> Optional[str]:
    """行番号からロールを取得"""
    users = load_users()
    if row_index < 0 or row_index >= len(users):
        return None
    return users[row_index].get("role")


def add_user(username: str, password: str, role: str, display_name: str) -> Tuple[str, List]:
    """ユーザーを追加（DB版）"""
    if not username:
        return "エラー: ユーザー名は必須です", get_users_for_display()

    if not password:
        return "エラー: パスワードは必須です", get_users_for_display()

    if len(password) < 4:
        return "エラー: パスワードは4文字以上必要です", get_users_for_display()

    # auth モジュールの add_user を使用
    success = auth_add_user(
        username=username,
        password=password,
        role=role,
        display_name=display_name or username
    )

    if not success:
        return f"エラー: ユーザー名 '{username}' は既に存在します", get_users_for_display()

    return f"ユーザー追加完了: {username} ({ROLE_DISPLAY.get(role, role)})", get_users_for_display()


def delete_user(row_index: int, current_username: str) -> Tuple[str, List]:
    """ユーザーを削除（DB版・論理削除）"""
    if row_index is None or row_index < 0:
        return "エラー: 削除するユーザーを選択してください", get_users_for_display()

    target_username = _get_username_by_row(row_index)
    if not target_username:
        return "エラー: 無効な行番号です", get_users_for_display()

    # 自分自身は削除不可
    if target_username == current_username:
        return "エラー: 自分自身は削除できません", get_users_for_display()

    # 最後の管理者は削除不可
    target_role = _get_user_role_by_row(row_index)
    if target_role == "admin" and get_admin_count() <= 1:
        return "エラー: 最後の管理者は削除できません", get_users_for_display()

    success = auth_delete_user(target_username)
    if not success:
        return f"エラー: ユーザー '{target_username}' の削除に失敗しました", get_users_for_display()

    return f"ユーザー削除完了: {target_username}", get_users_for_display()


def reset_password(row_index: int, new_password: str) -> Tuple[str, List]:
    """パスワードをリセット（DB版）"""
    if row_index is None or row_index < 0:
        return "エラー: ユーザーを選択してください", get_users_for_display()

    if not new_password:
        return "エラー: 新しいパスワードを入力してください", get_users_for_display()

    if len(new_password) < 4:
        return "エラー: パスワードは4文字以上必要です", get_users_for_display()

    target_username = _get_username_by_row(row_index)
    if not target_username:
        return "エラー: 無効な行番号です", get_users_for_display()

    success = auth_update_password(target_username, new_password)
    if not success:
        return f"エラー: パスワードリセットに失敗しました", get_users_for_display()

    return f"パスワードリセット完了: {target_username}", get_users_for_display()


def update_user_role(row_index: int, new_role: str, current_username: str) -> Tuple[str, List]:
    """ユーザーロールを変更（DB版）"""
    if row_index is None or row_index < 0:
        return "エラー: ユーザーを選択してください", get_users_for_display()

    target_username = _get_username_by_row(row_index)
    if not target_username:
        return "エラー: 無効な行番号です", get_users_for_display()

    old_role = _get_user_role_by_row(row_index)

    # 自分自身のロールは変更不可（admin降格防止）
    if target_username == current_username:
        return "エラー: 自分自身のロールは変更できません", get_users_for_display()

    # 最後の管理者のロール変更は不可
    if old_role == "admin" and new_role != "admin" and get_admin_count() <= 1:
        return "エラー: 最後の管理者のロールは変更できません", get_users_for_display()

    success = auth_update_user_role(target_username, new_role)
    if not success:
        return f"エラー: ロール変更に失敗しました", get_users_for_display()

    return f"ロール変更完了: {target_username} ({ROLE_DISPLAY.get(old_role)} → {ROLE_DISPLAY.get(new_role)})", get_users_for_display()


# =============================================================================
# システム情報
# =============================================================================

def get_system_info() -> str:
    """システム情報を取得"""
    info = []

    info.append("## システム情報")
    info.append("")

    # ユーザー統計（DBから取得）
    users = load_users()
    info.append(f"**ユーザー数**: {len(users)}")

    role_counts = {}
    for user in users:
        role = user.get("role", "unknown")
        role_counts[role] = role_counts.get(role, 0) + 1

    for role, count in role_counts.items():
        info.append(f"  - {ROLE_DISPLAY.get(role, role)}: {count}")

    info.append("")

    # ファイル情報
    info.append("**データファイル**:")

    if DB_FILE.exists():
        size = DB_FILE.stat().st_size / 1024  # KB
        mtime = datetime.fromtimestamp(DB_FILE.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
        info.append(f"  - rotation_planner.db: {size:.1f} KB (更新: {mtime})")
    else:
        info.append(f"  - rotation_planner.db: 未作成")

    info.append("")

    # 環境情報
    info.append("**環境**:")
    import sys
    info.append(f"  - Python: {sys.version.split()[0]}")

    try:
        import gradio
        info.append(f"  - Gradio: {gradio.__version__}")
    except:
        pass

    return "\n".join(info)


def get_db_tables_info() -> str:
    """DBテーブル情報を取得"""
    if not DB_FILE.exists():
        return "データベースファイルが存在しません"

    import sqlite3

    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()

        # テーブル一覧
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = cursor.fetchall()

        info = ["## データベーステーブル", ""]

        for (table_name,) in tables:
            cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            count = cursor.fetchone()[0]
            info.append(f"**{table_name}**: {count} レコード")

        conn.close()
        return "\n".join(info)

    except Exception as e:
        return f"エラー: {str(e)}"


# =============================================================================
# システム設定
# =============================================================================

def load_settings() -> Dict[str, Any]:
    """システム設定を読み込む"""
    if SETTINGS_FILE.exists():
        try:
            with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            pass
    return {"debug_mode": False}


def save_settings(settings: Dict[str, Any]) -> None:
    """システム設定を保存"""
    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
        json.dump(settings, f, ensure_ascii=False, indent=2)


def get_debug_mode() -> bool:
    """デバッグモードの状態を取得"""
    settings = load_settings()
    return settings.get("debug_mode", False)


def set_debug_mode(enabled: bool) -> str:
    """デバッグモードを設定"""
    settings = load_settings()
    settings["debug_mode"] = enabled
    save_settings(settings)

    status = "ON" if enabled else "OFF"
    return f"✅ デバッグモードを {status} に変更しました。\n※ 変更を反映するにはアプリの再起動が必要です。"


# =============================================================================
# 筆ポリゴン管理
# =============================================================================

def upload_fude_geojson(files) -> str:
    """筆ポリゴンGeoJSONファイルをアップロード"""
    if not files:
        return "エラー: ファイルを選択してください"

    # キャッシュディレクトリ作成
    FUDE_CACHE_DIR.mkdir(parents=True, exist_ok=True)

    results = []
    for file in files:
        try:
            file_path = Path(file.name) if hasattr(file, 'name') else Path(file)
            file_name = file_path.name

            # GeoJSON検証
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # GeoJSON形式チェック
            if not isinstance(data, dict):
                results.append(f"❌ {file_name}: 無効なJSON形式")
                continue

            if data.get("type") not in ["FeatureCollection", "Feature", "GeometryCollection"]:
                # 筆ポリゴン形式かもしれないのでfeaturesをチェック
                if "features" not in data and "geometry" not in data:
                    results.append(f"❌ {file_name}: GeoJSON形式ではありません")
                    continue

            # 筆数をカウント
            feature_count = 0
            if data.get("type") == "FeatureCollection":
                feature_count = len(data.get("features", []))
            elif data.get("type") == "Feature":
                feature_count = 1

            # 保存
            dest_path = FUDE_CACHE_DIR / file_name
            with open(dest_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False)

            results.append(f"✅ {file_name}: アップロード完了（{feature_count}筆）")

        except json.JSONDecodeError as e:
            results.append(f"❌ {file_name}: JSONパースエラー - {str(e)}")
        except Exception as e:
            results.append(f"❌ {file_name}: エラー - {str(e)}")

    return "\n".join(results)


def get_fude_files_list() -> List[List[Any]]:
    """筆ポリゴンファイル一覧を取得"""
    if not FUDE_CACHE_DIR.exists():
        return []

    files_data = []
    for file_path in sorted(FUDE_CACHE_DIR.glob("*.geojson")):
        try:
            stat = file_path.stat()
            size_kb = stat.st_size / 1024
            mtime = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M")

            # 筆数をカウント
            feature_count = 0
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if data.get("type") == "FeatureCollection":
                        feature_count = len(data.get("features", []))
            except:
                pass

            files_data.append([
                file_path.name,
                f"{size_kb:.1f} KB",
                mtime,
                feature_count
            ])
        except Exception:
            continue

    # .json ファイルも確認
    for file_path in sorted(FUDE_CACHE_DIR.glob("*.json")):
        if file_path.suffix == ".geojson":
            continue
        try:
            stat = file_path.stat()
            size_kb = stat.st_size / 1024
            mtime = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M")

            feature_count = 0
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if data.get("type") == "FeatureCollection":
                        feature_count = len(data.get("features", []))
            except:
                pass

            files_data.append([
                file_path.name,
                f"{size_kb:.1f} KB",
                mtime,
                feature_count
            ])
        except Exception:
            continue

    return files_data


def delete_fude_file(file_name: str) -> Tuple[str, List]:
    """筆ポリゴンファイルを削除"""
    if not file_name.strip():
        return "エラー: ファイル名を入力してください", get_fude_files_list()

    file_path = FUDE_CACHE_DIR / file_name.strip()

    if not file_path.exists():
        return f"エラー: ファイル '{file_name}' が見つかりません", get_fude_files_list()

    # 安全チェック（ディレクトリトラバーサル防止）
    try:
        file_path.resolve().relative_to(FUDE_CACHE_DIR.resolve())
    except ValueError:
        return "エラー: 無効なファイルパスです", get_fude_files_list()

    try:
        file_path.unlink()
        return f"✅ '{file_name}' を削除しました", get_fude_files_list()
    except Exception as e:
        return f"エラー: 削除に失敗しました - {str(e)}", get_fude_files_list()


# =============================================================================
# UI作成
# =============================================================================

def create_admin_ui(current_username: str = "") -> Dict[str, Any]:
    """管理機能UIを作成（ポータル埋め込み用）"""

    components = {}

    gr.Markdown("""
    ## ⚙️ システム管理

    ユーザー管理・システム情報の確認ができます。
    """)

    with gr.Tabs():
        # =================================================================
        # ユーザー管理タブ
        # =================================================================
        with gr.TabItem("👥 ユーザー管理"):
            gr.Markdown("### ユーザー一覧")

            users_table = gr.Dataframe(
                headers=["#", "ユーザー名", "ロール", "表示名", "ユーザーID", "パスワード"],
                datatype=["number", "str", "str", "str", "str", "str"],
                value=get_users_for_display(),
                label="ユーザー一覧",
                interactive=False
            )
            components["users_table"] = users_table

            refresh_btn = gr.Button("🔄 更新")
            result_msg = gr.Textbox(label="結果", interactive=False)
            components["result_msg"] = result_msg

            refresh_btn.click(fn=get_users_for_display, outputs=[users_table])

            gr.Markdown("---")

            # 新規ユーザー追加
            with gr.Accordion("➕ 新規ユーザー追加", open=False):
                with gr.Row():
                    with gr.Column():
                        new_username = gr.Textbox(label="ユーザー名 *", placeholder="例: farmer01")
                        new_password = gr.Textbox(label="パスワード *", type="password", placeholder="4文字以上")
                    with gr.Column():
                        new_role = gr.Dropdown(choices=ROLE_CHOICES, value="farmer", label="ロール")
                        new_display_name = gr.Textbox(label="表示名", placeholder="例: 田中太郎")

                add_btn = gr.Button("➕ ユーザー追加", variant="primary")

                add_btn.click(
                    fn=add_user,
                    inputs=[new_username, new_password, new_role, new_display_name],
                    outputs=[result_msg, users_table]
                )

            # ユーザー操作
            with gr.Accordion("🔧 ユーザー操作", open=False):
                row_index = gr.Number(label="操作対象の行番号（#列の値）", precision=0)

                gr.Markdown("#### パスワードリセット")
                with gr.Row():
                    reset_password_input = gr.Textbox(label="新しいパスワード", type="password")
                    reset_btn = gr.Button("🔑 パスワードリセット")

                reset_btn.click(
                    fn=reset_password,
                    inputs=[row_index, reset_password_input],
                    outputs=[result_msg, users_table]
                )

                gr.Markdown("#### ロール変更")
                with gr.Row():
                    new_role_select = gr.Dropdown(choices=ROLE_CHOICES, label="新しいロール")
                    role_btn = gr.Button("👤 ロール変更")

                # current_username を渡すためのState
                username_state = gr.State(current_username)

                role_btn.click(
                    fn=update_user_role,
                    inputs=[row_index, new_role_select, username_state],
                    outputs=[result_msg, users_table]
                )

                gr.Markdown("#### ユーザー削除")
                delete_btn = gr.Button("🗑️ ユーザー削除", variant="stop")

                delete_btn.click(
                    fn=delete_user,
                    inputs=[row_index, username_state],
                    outputs=[result_msg, users_table]
                )

        # =================================================================
        # システム情報タブ
        # =================================================================
        with gr.TabItem("📊 システム情報"):
            system_info = gr.Markdown(value=get_system_info())

            db_info = gr.Markdown(value=get_db_tables_info())

            info_refresh_btn = gr.Button("🔄 更新")

            def refresh_all_info():
                return get_system_info(), get_db_tables_info()

            info_refresh_btn.click(
                fn=refresh_all_info,
                outputs=[system_info, db_info]
            )

        # =================================================================
        # バックアップタブ
        # =================================================================
        with gr.TabItem("💾 バックアップ"):
            gr.Markdown("""
            ### データバックアップ

            データベースファイルをダウンロードできます。
            ユーザー情報、ほ場データ、輪作計画など全てのデータが含まれます。
            """)

            def get_db_file():
                return str(DB_FILE) if DB_FILE.exists() else None

            gr.DownloadButton("📥 rotation_planner.db ダウンロード", value=get_db_file())

            gr.Markdown("""
            ---

            **バックアップ推奨タイミング**:
            - ユーザー追加・削除後
            - 大きなデータ変更後
            - 定期的（週1回など）
            """)

        # =================================================================
        # システム設定タブ
        # =================================================================
        with gr.TabItem("🔧 システム設定"):
            gr.Markdown("""
            ### システム設定

            アプリケーションの動作モードを変更できます。
            """)

            gr.Markdown("---")
            gr.Markdown("### デバッグモード")

            current_debug = get_debug_mode()
            debug_checkbox = gr.Checkbox(
                label="デバッグモードを有効にする",
                value=current_debug,
                info="有効時: ログイン画面にユーザー切り替えラジオボタンが表示されます"
            )

            debug_result = gr.Textbox(label="結果", interactive=False)

            debug_checkbox.change(
                fn=set_debug_mode,
                inputs=[debug_checkbox],
                outputs=[debug_result]
            )

            gr.Markdown("""
            ---

            **デバッグモードの機能:**
            - ログイン画面にユーザー切り替えラジオボタン表示
            - パスワード入力なしでログイン可能

            ---

            ### ⚠️ セキュリティに関する重要な注意

            **本番環境では必ず以下を実施してください:**

            1. **デバッグモードを OFF にする**
            2. **adminのパスワードを変更する**（初期値: admin123）
            3. **テストユーザーを削除する**（farmer_demo, ja_staff など）

            初期パスワードのまま運用すると、第三者に管理者権限でアクセスされる危険があります。
            """)

        # =================================================================
        # 筆ポリゴンタブ
        # =================================================================
        with gr.TabItem("🗺️ 筆ポリゴン"):
            gr.Markdown("""
            ### 筆ポリゴンデータ管理

            農水省の[筆ポリゴン公開サイト](https://open.fude.maff.go.jp/)からダウンロードした
            GeoJSONファイルをアップロードして、ほ場登録時に利用できます。

            **手順:**
            1. [筆ポリゴン公開サイト](https://open.fude.maff.go.jp/)にアクセス
            2. アンケートに回答後、管轄市町村のデータをダウンロード
            3. 下記からGeoJSONファイルをアップロード
            """)

            fude_upload = gr.File(
                label="GeoJSONファイルをアップロード",
                file_types=[".geojson", ".json"],
                file_count="multiple"
            )

            fude_upload_btn = gr.Button("📤 アップロード", variant="primary")
            fude_upload_result = gr.Textbox(label="結果", interactive=False)

            fude_upload_btn.click(
                fn=upload_fude_geojson,
                inputs=[fude_upload],
                outputs=[fude_upload_result]
            )

            gr.Markdown("---")
            gr.Markdown("### アップロード済みデータ")

            fude_list = gr.Dataframe(
                headers=["ファイル名", "サイズ", "更新日時", "筆数"],
                datatype=["str", "str", "str", "number"],
                value=get_fude_files_list(),
                label="筆ポリゴンファイル一覧",
                interactive=False
            )

            fude_refresh_btn = gr.Button("🔄 更新")
            fude_refresh_btn.click(fn=get_fude_files_list, outputs=[fude_list])

            gr.Markdown("---")

            gr.Markdown("### ファイル削除")
            fude_delete_name = gr.Textbox(label="削除するファイル名", placeholder="例: 01231.geojson")
            fude_delete_btn = gr.Button("🗑️ 削除", variant="stop")
            fude_delete_result = gr.Textbox(label="結果", interactive=False)

            fude_delete_btn.click(
                fn=delete_fude_file,
                inputs=[fude_delete_name],
                outputs=[fude_delete_result, fude_list]
            )

            gr.Markdown("""
            ---

            **データ出典:** 農林水産省「筆ポリゴンデータ」

            利用規約に従い、出典を明記して利用してください。
            """)

    return components


# =============================================================================
# スタンドアロン実行
# =============================================================================

if __name__ == "__main__":
    with gr.Blocks(title="管理機能") as app:
        create_admin_ui("admin")

    app.launch(
        server_name="0.0.0.0",
        server_port=7865,
        share=False
    )
