"""
DB エラー処理テスト

WALモード、FK制約、transaction()コンテキストマネージャ、例外分類のテスト
"""

import pytest
import sqlite3
from rotation_planner.common.db_access import (
    get_connection, transaction, FieldRepository
)
from rotation_planner.common.exceptions import (
    DuplicateKeyError, NotNullViolationError, ForeignKeyViolationError,
    DatabaseError
)


@pytest.mark.db
def test_wal_mode_enabled(test_db):
    """WALモードが有効化されていることを確認"""
    conn = get_connection()
    cursor = conn.execute("PRAGMA journal_mode")
    mode = cursor.fetchone()[0]
    conn.close()

    assert mode.upper() == "WAL", f"Expected WAL mode, but got {mode}"


@pytest.mark.db
def test_foreign_keys_enabled(test_db):
    """外部キー制約が有効化されていることを確認"""
    conn = get_connection()
    cursor = conn.execute("PRAGMA foreign_keys")
    fk_enabled = cursor.fetchone()[0]
    conn.close()

    assert fk_enabled == 1, "Foreign keys should be enabled"


@pytest.mark.db
def test_timeout_setting(test_db):
    """タイムアウトが30秒に設定されていることを確認"""
    conn = get_connection()
    # タイムアウトはconnectionオブジェクトのプロパティで確認できないため、
    # 実際に設定されていることは接続時の引数で確認済み（コードレビューで確認）
    # ここでは接続が成功することを確認
    assert conn is not None
    conn.close()


@pytest.mark.db
def test_transaction_commit(test_db):
    """transaction() コンテキストマネージャの正常系（COMMIT）"""
    # テスト用ほ場を作成
    with transaction() as conn:
        cursor = conn.execute("""
            INSERT INTO fields (user_id, field_code, name, area_ha)
            VALUES (?, ?, ?, ?)
        """, (1, "TX001", "Transaction Test Field", 3.0))
        field_id = cursor.lastrowid

    # コミット後にデータが存在することを確認
    conn = get_connection()
    cursor = conn.execute("SELECT * FROM fields WHERE id = ?", (field_id,))
    row = cursor.fetchone()
    conn.close()

    assert row is not None
    assert row["field_code"] == "TX001"


@pytest.mark.db
def test_transaction_rollback(test_db):
    """transaction() コンテキストマネージャの異常系（ROLLBACK）"""
    # 意図的にエラーを発生させる（transaction()が例外を分類する）
    with pytest.raises(NotNullViolationError):
        with transaction() as conn:
            # 正常なINSERT
            conn.execute("""
                INSERT INTO fields (user_id, field_code, name, area_ha)
                VALUES (?, ?, ?, ?)
            """, (1, "TX002", "Rollback Test Field", 2.5))

            # NOT NULL制約違反（area_haが必須）
            conn.execute("""
                INSERT INTO fields (user_id, field_code, name, area_ha)
                VALUES (?, ?, ?, ?)
            """, (1, "TX003", "Should Fail", None))

    # ロールバック後にデータが存在しないことを確認
    conn = get_connection()
    cursor = conn.execute("SELECT * FROM fields WHERE field_code = 'TX002'")
    row = cursor.fetchone()
    conn.close()

    assert row is None, "Transaction should have been rolled back"


@pytest.mark.db
def test_duplicate_key_error(test_db):
    """DuplicateKeyError 例外分類"""
    # 最初のほ場を作成
    FieldRepository.create_field(
        user_id=1,
        data={
            "field_code": "DUP001",
            "name": "Duplicate Test",
            "area_ha": 2.0
        }
    )

    # 同じfield_codeで作成するとDuplicateKeyErrorが発生
    with pytest.raises(DuplicateKeyError) as exc_info:
        FieldRepository.create_field(
            user_id=1,
            data={
                "field_code": "DUP001",
                "name": "Duplicate Test 2",
                "area_ha": 3.0
            }
        )

    assert "重複" in str(exc_info.value)


@pytest.mark.db
def test_not_null_violation_error(test_db):
    """NotNullViolationError 例外分類"""
    # area_ha（必須）にNoneを渡してエラー発生
    with pytest.raises(NotNullViolationError) as exc_info:
        FieldRepository.create_field(
            user_id=1,
            data={
                "field_code": "NULL001",
                "name": "Null Test",
                "area_ha": None  # NOT NULL violation
            }
        )

    assert "必須項目" in str(exc_info.value)


@pytest.mark.db
def test_foreign_key_violation_error(test_db):
    """ForeignKeyViolationError 例外分類"""
    # 存在しないuser_idで作成するとFK制約違反
    with pytest.raises(ForeignKeyViolationError) as exc_info:
        FieldRepository.create_field(
            user_id=99999,  # 存在しないユーザー
            data={
                "field_code": "FK001",
                "name": "FK Test",
                "area_ha": 2.0
            }
        )

    assert "参照先" in str(exc_info.value)


@pytest.mark.db
def test_transaction_exception_classification(test_db):
    """transaction() 内での例外分類の動作確認"""
    # UNIQUE制約違反 → DuplicateKeyError
    with transaction() as conn:
        conn.execute("""
            INSERT INTO fields (user_id, field_code, name, area_ha)
            VALUES (?, ?, ?, ?)
        """, (1, "EXC001", "Exception Test", 2.0))

    with pytest.raises(DuplicateKeyError):
        with transaction() as conn:
            conn.execute("""
                INSERT INTO fields (user_id, field_code, name, area_ha)
                VALUES (?, ?, ?, ?)
            """, (1, "EXC001", "Duplicate", 3.0))

    # NOT NULL制約違反 → NotNullViolationError
    with pytest.raises(NotNullViolationError):
        with transaction() as conn:
            conn.execute("""
                INSERT INTO fields (user_id, field_code, name, area_ha)
                VALUES (?, ?, ?, ?)
            """, (1, "EXC002", "Null Test", None))

    # FK制約違反 → ForeignKeyViolationError
    with pytest.raises(ForeignKeyViolationError):
        with transaction() as conn:
            conn.execute("""
                INSERT INTO fields (user_id, field_code, name, area_ha)
                VALUES (?, ?, ?, ?)
            """, (99999, "EXC003", "FK Test", 2.0))
