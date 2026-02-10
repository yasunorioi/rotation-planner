"""
テスト共通設定 — Gradio未インストール環境での回避策 + DB一元管理 + フィクスチャ
"""
import os
import sys
import types
import tempfile
import shutil
import sqlite3
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# プロジェクトルートをパスに追加
sys.path.insert(0, str(Path(__file__).parent.parent))

# Gradio およびGradio依存モジュールをモック（未インストール環境対応）
for mod_name in [
    'gradio', 'gradio.themes', 'gradio.components',
    'gradio_folium',
]:
    if mod_name not in sys.modules:
        sys.modules[mod_name] = MagicMock()

# 共通テスト用DBパスを設定（全テストファイルで統一）
_test_db_fd, _shared_test_db_path = tempfile.mkstemp(suffix='_test.db')
os.close(_test_db_fd)

import rotation_planner.common.db_access as _db_mod
_db_mod.DB_PATH = Path(_shared_test_db_path)

# db モジュールの DB_PATH も差し替え＆スキーマ初期化
from rotation_planner.common import db as _db_mod2
_db_mod2.DB_PATH = Path(_shared_test_db_path)
_schema_path = Path(__file__).parent.parent / "db_schema.sql"
if _schema_path.exists():
    _conn = sqlite3.connect(_shared_test_db_path)
    with open(_schema_path, 'r', encoding='utf-8') as _f:
        _conn.executescript(_f.read())
    _conn.close()
    _db_mod2.init_db()
    # テスト用シードデータ: FK参照先として必要な最低限のレコード
    _conn = sqlite3.connect(_shared_test_db_path)
    _conn.execute(
        "INSERT OR IGNORE INTO rotation_plans (id, user_id, name, start_year, end_year) "
        "VALUES (1, 3, 'テスト計画', 'R6', 'R10')"
    )
    _conn.execute(
        "INSERT OR IGNORE INTO fields (id, user_id, field_code, name, area_ha) "
        "VALUES (1, 1, 'TEST001', 'テスト共有ほ場', 2.5)"
    )
    _conn.commit()
    _conn.close()


# ============================================================
# pytest マーカー定義
# ============================================================

def pytest_configure(config):
    """pytest マーカー登録"""
    config.addinivalue_line("markers", "slow: 時間のかかるテスト")
    config.addinivalue_line("markers", "db: データベース操作を含むテスト")
    config.addinivalue_line("markers", "api: API呼び出しを含むテスト")
    config.addinivalue_line("markers", "security: セキュリティ関連のテスト")


# ============================================================
# DB フィクスチャ
# ============================================================

@pytest.fixture(scope="function")
def test_db(monkeypatch):
    """
    各テスト関数で独立したテスト用DB。
    db.DB_PATH と db_access.DB_PATH の両方を差し替える。
    """
    from rotation_planner.common import db
    from rotation_planner.common import db_access

    # 一時DBファイル作成
    tmpdir = tempfile.mkdtemp(prefix="rp_test_")
    temp_db_path = Path(tmpdir) / "test_rotation.db"

    # 両方のDB_PATHをパッチ
    monkeypatch.setattr(db, 'DB_PATH', temp_db_path)
    monkeypatch.setattr(db_access, 'DB_PATH', temp_db_path)

    # スキーマ初期化（db_schema.sqlを使用）
    schema_path = Path(__file__).parent.parent / "db_schema.sql"
    conn = sqlite3.connect(str(temp_db_path))
    with open(schema_path, 'r', encoding='utf-8') as f:
        conn.executescript(f.read())
    conn.close()

    # init_db()で初期ユーザー作成
    db.init_db()

    # テスト用シードデータ: FK参照先として必要な最低限のレコード
    seed_conn = sqlite3.connect(str(temp_db_path))
    seed_conn.execute(
        "INSERT OR IGNORE INTO rotation_plans (id, user_id, name, start_year, end_year) "
        "VALUES (1, 3, 'テスト計画', 'R6', 'R10')"
    )
    seed_conn.commit()
    seed_conn.close()

    yield temp_db_path

    # クリーンアップ
    shutil.rmtree(tmpdir, ignore_errors=True)


# ============================================================
# ユーザー状態フィクスチャ
# ============================================================

@pytest.fixture
def admin_state():
    """管理者ユーザー状態"""
    return {
        "user_id": 1,
        "username": "admin",
        "display_name": "管理者",
        "role": "admin",
        "org_id": 1,
    }


@pytest.fixture
def farmer_state():
    """農家ユーザー状態（farmer_demo）"""
    return {
        "user_id": 3,
        "username": "farmer_demo",
        "display_name": "デモ農家",
        "role": "farmer",
        "org_id": 2,
    }


@pytest.fixture
def ja_staff_state():
    """JA職員ユーザー状態"""
    return {
        "user_id": 2,
        "username": "ja_staff",
        "display_name": "JA職員",
        "role": "ja_staff",
        "org_id": 1,
    }


# ============================================================
# 一時ファイルフィクスチャ
# ============================================================

@pytest.fixture
def temp_dir():
    """一時ディレクトリ"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def temp_csv(temp_dir):
    """一時CSVファイルを作成するファクトリ"""
    def _create(content: str, filename: str = "test.csv") -> str:
        path = os.path.join(temp_dir, filename)
        with open(path, "w", encoding="utf-8-sig") as f:
            f.write(content)
        return path
    return _create


# ============================================================
# テストデータフィクスチャ
# ============================================================

@pytest.fixture
def sample_field_data():
    """サンプルほ場データ"""
    return {
        "field_code": "TEST001",
        "district": "テスト地区",
        "name": "テストほ場1号",
        "area_ha": 2.5,
        "beet_forbidden": False,
        "coordinates_json": None,
        "notes": "テスト用",
    }


@pytest.fixture
def sample_crop_history():
    """サンプル作付履歴"""
    return {
        "R5": "大豆",
        "R6": "てんさい",
        "R7": "春小麦",
    }


@pytest.fixture
def sample_constraints():
    """サンプル制約データ"""
    return {
        "crop_mins": {"てんさい": 0.2, "大豆": 0.1},
        "crop_caps": {"てんさい": 0.4, "大豆": 0.3},
        "min_gap_years": {"てんさい": 4, "大豆": 2},
        "forbidden_transitions": {("てんさい", "てんさい")},
        "preferred_transitions": {("大豆", "てんさい"): 0.8},
    }
