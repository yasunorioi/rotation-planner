"""
E2E テスト共通設定

テスト用DBの初期化、FastAPIサーバーの起動/終了、Playwright fixtures を提供。
FastAPI が frontend/app/dist/ の静的ファイルもサーブするため、
React dev サーバーの別途起動は不要。
"""

import os
import sys
import time
import shutil
import signal
import socket
import subprocess
import tempfile
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent.parent


# ============================================================
# ユーティリティ
# ============================================================

def _find_free_port() -> int:
    """空きTCPポートを取得する。"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait_for_server(host: str, port: int, timeout: float = 30) -> bool:
    """サーバーが接続を受け付けるまで待機する。"""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((host, port), timeout=1):
                return True
        except (ConnectionRefusedError, OSError):
            time.sleep(0.5)
    return False


# ============================================================
# pytest マーカー登録
# ============================================================

def pytest_configure(config):
    config.addinivalue_line("markers", "e2e: End-to-End テスト")


# ============================================================
# DB fixtures
# ============================================================

@pytest.fixture(scope="session")
def test_db_path():
    """テスト用 SQLite DB を作成し、スキーマ + シードデータを投入する。"""
    tmpdir = tempfile.mkdtemp(prefix="rp_e2e_")
    db_path = Path(tmpdir) / "e2e_test.db"

    # プロジェクトルートをパスに追加（init_db を呼ぶため）
    sys.path.insert(0, str(PROJECT_ROOT))

    import rotation_planner.common.db as db_mod
    import rotation_planner.common.db_access as dba_mod

    # DB_PATH を差し替え
    orig_db_path = db_mod.DB_PATH
    orig_db_dir = db_mod.DB_DIR
    orig_dba_path = dba_mod.DB_PATH

    db_mod.DB_PATH = db_path
    db_mod.DB_DIR = db_path.parent
    dba_mod.DB_PATH = db_path

    # スキーマ適用 + 初期ユーザー + 初期組織 + 初期作物
    db_mod.init_db()

    # 追加のシードデータ（テスト用ほ場、作物マスタなど）
    import sqlite3

    conn = sqlite3.connect(str(db_path))

    # init_db() が db_schema.sql のシードデータを投入済み（FAMIC表記）
    # テストで使用する作物のID対応:
    #   1=小麦(春播), 2=小麦(秋播), 3=だいず, 4=てんさい, 5=ばれいしょ
    test_crop_ids = [3, 1, 5, 4]  # だいず, 小麦(春播), ばれいしょ, てんさい

    # admin (user_id=1) の作物を登録
    for crop_id in test_crop_ids:
        conn.execute(
            "INSERT OR IGNORE INTO user_crops (user_id, parent_crop_id, custom_name) "
            "VALUES (1, ?, NULL)",
            (crop_id,)
        )

    # farmer_demo (user_id=3) の作物を登録
    for crop_id in test_crop_ids:
        conn.execute(
            "INSERT OR IGNORE INTO user_crops (user_id, parent_crop_id, custom_name) "
            "VALUES (3, ?, NULL)",
            (crop_id,)
        )

    # admin (user_id=1) のテスト用ほ場
    conn.execute(
        "INSERT OR IGNORE INTO fields (id, user_id, field_code, name, area_ha) "
        "VALUES (1, 1, 'E2E001', 'E2Eテストほ場1号', 2.5)"
    )
    conn.execute(
        "INSERT OR IGNORE INTO fields (id, user_id, field_code, name, area_ha) "
        "VALUES (2, 1, 'E2E002', 'E2Eテストほ場2号', 1.8)"
    )
    # farmer_demo (user_id=3) のテスト用ほ場
    conn.execute(
        "INSERT OR IGNORE INTO fields (id, user_id, field_code, name, area_ha) "
        "VALUES (3, 3, 'E2E003', 'E2Eテストほ場3号', 3.2)"
    )
    conn.commit()
    conn.close()

    # DB_PATH を元に戻す（テストプロセス自体は API サーバーを使うので不要だが念のため）
    db_mod.DB_PATH = orig_db_path
    db_mod.DB_DIR = orig_db_dir
    dba_mod.DB_PATH = orig_dba_path

    yield str(db_path)

    shutil.rmtree(tmpdir, ignore_errors=True)


# ============================================================
# サーバー fixtures
# ============================================================

@pytest.fixture(scope="session")
def api_port():
    """テスト用 API サーバーのポート番号。"""
    return _find_free_port()


@pytest.fixture(scope="session")
def api_server(test_db_path, api_port):
    """
    E2Eテスト用 FastAPI サーバーを起動する（session scope）。

    run_api_server.py 経由で起動し、テスト用 DB を使用する。
    frontend/app/dist/ の静的ファイルもサーブする。
    """
    # フロントエンドビルドが存在するか確認
    dist_dir = PROJECT_ROOT / "frontend" / "app" / "dist"
    if not (dist_dir / "index.html").exists():
        # ビルドを実行
        subprocess.run(
            ["npm", "run", "build"],
            cwd=str(PROJECT_ROOT / "frontend" / "app"),
            check=True,
            capture_output=True,
        )

    env = os.environ.copy()
    env["JWT_SECRET"] = "e2e_test_secret_key_12345"
    env["TEST_DB_PATH"] = test_db_path
    env["API_PORT"] = str(api_port)

    server_script = Path(__file__).parent / "run_api_server.py"
    proc = subprocess.Popen(
        [sys.executable, str(server_script)],
        cwd=str(PROJECT_ROOT),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    if not _wait_for_server("127.0.0.1", api_port, timeout=30):
        proc.kill()
        stdout, stderr = proc.communicate(timeout=5)
        raise RuntimeError(
            f"API server failed to start on port {api_port}\n"
            f"stdout: {stdout.decode()}\n"
            f"stderr: {stderr.decode()}"
        )

    yield proc

    # サーバー停止
    proc.send_signal(signal.SIGTERM)
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=5)


# ============================================================
# Playwright fixtures
# ============================================================

@pytest.fixture(scope="session")
def base_url(api_server, api_port):
    """pytest-playwright が使用する base_url を動的に設定する。"""
    return f"http://127.0.0.1:{api_port}"


# ============================================================
# テストヘルパー fixtures
# ============================================================

@pytest.fixture
def authenticated_page(page, base_url):
    """ログイン済みの Playwright page を提供する。"""
    page.goto(f"{base_url}/login")
    page.get_by_label("ユーザー名").fill("admin")
    page.get_by_label("パスワード").fill("admin123")
    page.get_by_role("button", name="ログイン").click()
    # ダッシュボードへの遷移を待機
    page.wait_for_url(f"{base_url}/", timeout=10000)
    return page


@pytest.fixture
def farmer_page(page, base_url):
    """farmer_demo でログイン済みの Playwright page を提供する。"""
    page.goto(f"{base_url}/login")
    page.get_by_label("ユーザー名").fill("farmer_demo")
    page.get_by_label("パスワード").fill("demo123")
    page.get_by_role("button", name="ログイン").click()
    page.wait_for_url(f"{base_url}/", timeout=10000)
    return page
