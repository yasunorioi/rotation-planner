"""
データベース接続モジュール - SQLite接続管理

使用方法:
    from rotation_planner.common.db import get_db, row_to_dict, rows_to_list

    with get_db() as conn:
        cursor = conn.execute("SELECT * FROM fields WHERE user_id = ?", (user_id,))
        fields = rows_to_list(cursor.fetchall())
"""

import sqlite3
from pathlib import Path
from typing import List, Dict, Any, Optional
from contextlib import contextmanager

# =============================================================================
# 設定
# =============================================================================

# DBファイルパス（rotation_planner_ui/data/rotation_planner.db）
DB_DIR = Path(__file__).parent.parent.parent / "data"
DB_PATH = DB_DIR / "rotation_planner.db"


# =============================================================================
# 接続管理
# =============================================================================

def get_connection() -> sqlite3.Connection:
    """
    DB接続を取得

    Returns:
        sqlite3.Connection: データベース接続
    """
    # ディレクトリが存在しない場合は作成
    DB_DIR.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row  # 辞書形式でアクセス可能
    conn.execute("PRAGMA foreign_keys = ON")  # 外部キー制約有効化
    return conn


@contextmanager
def get_db():
    """
    コンテキストマネージャでDB接続を管理

    Usage:
        with get_db() as conn:
            cursor = conn.execute(...)
            # 自動コミット・ロールバック
    """
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


# =============================================================================
# ユーティリティ関数
# =============================================================================

def row_to_dict(row: Optional[sqlite3.Row]) -> Optional[Dict[str, Any]]:
    """
    sqlite3.Rowを辞書に変換

    Args:
        row: SQLiteの行データ

    Returns:
        辞書形式のデータ（rowがNoneの場合はNone）
    """
    return dict(row) if row else None


def rows_to_list(rows: List[sqlite3.Row]) -> List[Dict[str, Any]]:
    """
    sqlite3.Rowのリストを辞書のリストに変換

    Args:
        rows: SQLiteの行データのリスト

    Returns:
        辞書のリスト
    """
    return [dict(row) for row in rows]


# =============================================================================
# データベース初期化
# =============================================================================

def init_db(schema_path: Optional[Path] = None) -> None:
    """
    データベースを初期化（スキーマを適用）

    Args:
        schema_path: スキーマファイルのパス（省略時はデフォルト）
    """
    if schema_path is None:
        schema_path = Path(__file__).parent.parent.parent / "db_schema.sql"

    if not schema_path.exists():
        raise FileNotFoundError(f"Schema file not found: {schema_path}")

    with open(schema_path, "r", encoding="utf-8") as f:
        schema_sql = f.read()

    with get_db() as conn:
        conn.executescript(schema_sql)


def check_db_exists() -> bool:
    """
    データベースファイルが存在するかチェック

    Returns:
        存在すればTrue
    """
    return DB_PATH.exists()


def get_db_info() -> Dict[str, Any]:
    """
    データベース情報を取得

    Returns:
        データベース情報の辞書
    """
    info = {
        "path": str(DB_PATH),
        "exists": DB_PATH.exists(),
        "size_bytes": DB_PATH.stat().st_size if DB_PATH.exists() else 0,
    }

    if DB_PATH.exists():
        with get_db() as conn:
            # テーブル一覧
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            )
            info["tables"] = [row["name"] for row in cursor.fetchall()]

    return info
