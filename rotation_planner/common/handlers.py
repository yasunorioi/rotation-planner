"""
エラーハンドリングモジュール

Gradioイベントハンドラ、DB操作メソッド用のエラーハンドリングデコレータを提供。
"""

import sqlite3
import logging
import traceback
from functools import wraps
from typing import Any, Callable

# Gradioのインポート（テスト環境でない場合）
try:
    import gradio as gr
except ImportError:
    gr = None

# カスタム例外クラス
from rotation_planner.common.exceptions import (
    RotationPlannerError,
    DatabaseError,
    DatabaseConnectionError,
    DuplicateKeyError,
    NotNullViolationError,
    ForeignKeyViolationError,
    CSVReadError,
    CSVWriteError,
    ValidationError,
)

# ロガー設定
logger = logging.getLogger(__name__)


# =============================================================================
# Gradioイベントハンドラ用デコレータ
# =============================================================================

def safe_handler(default_return=None, show_traceback=False):
    """
    Gradioイベントハンドラ用の安全ラッパー。
    例外をキャッチし、ユーザー向けメッセージ表示＋ログ記録。

    Args:
        default_return: 例外発生時のデフォルト戻り値
        show_traceback: Trueの場合、トレースバックをログに出力

    Usage:
        @safe_handler(default_return=None)
        def on_button_click(value):
            # Gradioイベントハンドラ処理
            return result
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            try:
                return func(*args, **kwargs)
            except CSVReadError as e:
                logger.warning(f"CSV読み込みエラー: {e}")
                if gr:
                    raise gr.Error(f"📄 {e.user_message}")
                return default_return
            except CSVWriteError as e:
                logger.warning(f"CSV書き出しエラー: {e}")
                if gr:
                    raise gr.Error(f"📄 {e.user_message}")
                return default_return
            except DatabaseConnectionError as e:
                logger.critical(f"DB接続エラー: {e}")
                if gr:
                    raise gr.Error("🔌 データベースに接続できません。管理者に連絡してください。")
                return default_return
            except DatabaseError as e:
                logger.error(f"DBエラー: {e}")
                if gr:
                    raise gr.Error(f"💾 {e.user_message}")
                return default_return
            except ValidationError as e:
                logger.info(f"バリデーションエラー: {e.field} - {e}")
                if gr:
                    raise gr.Error(f"⚠️ {e.user_message}")
                return default_return
            except PermissionError as e:
                logger.error(f"権限エラー: {e}")
                if gr:
                    raise gr.Error("🔒 アクセス権限がありません。")
                return default_return
            except Exception as e:
                if show_traceback:
                    logger.error(f"予期しないエラー:\n{traceback.format_exc()}")
                else:
                    logger.error(f"予期しないエラー: {e}")
                if gr:
                    raise gr.Error("❌ 予期しないエラーが発生しました。")
                return default_return
        return wrapper
    return decorator


# =============================================================================
# DB操作メソッド用デコレータ
# =============================================================================

def handle_db_error(operation: str = "DB操作"):
    """
    DB操作メソッド用のエラーハンドリングデコレータ。
    sqlite3エラーをカスタム例外に変換する。

    Args:
        operation: 操作名（ログ出力用）

    Usage:
        @handle_db_error(operation="ユーザー登録")
        def add_user(self, username, password):
            # DB操作処理
            pass
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            try:
                return func(*args, **kwargs)
            except sqlite3.IntegrityError as e:
                error_msg = str(e).lower()
                logger.error(f"{operation}中にIntegrityError: {e}")

                # UNIQUE制約違反
                if "unique" in error_msg:
                    raise DuplicateKeyError(
                        message=f"{operation}失敗: 重複するデータが存在します",
                        user_message="このデータは既に登録されています。"
                    )
                # NOT NULL制約違反
                elif "not null" in error_msg:
                    raise NotNullViolationError(
                        message=f"{operation}失敗: 必須項目が未入力です",
                        user_message="必須項目が入力されていません。"
                    )
                # FOREIGN KEY制約違反
                elif "foreign key" in error_msg:
                    raise ForeignKeyViolationError(
                        message=f"{operation}失敗: 参照先のデータが存在しません",
                        user_message="関連するデータが見つかりません。"
                    )
                else:
                    raise DatabaseError(
                        message=f"{operation}失敗: データ整合性エラー",
                        user_message="データの整合性エラーが発生しました。"
                    )
            except sqlite3.OperationalError as e:
                logger.error(f"{operation}中にOperationalError: {e}")
                error_msg = str(e).lower()

                # DB接続エラー
                if "unable to open database" in error_msg or "disk i/o error" in error_msg:
                    raise DatabaseConnectionError(
                        message=f"{operation}失敗: DB接続エラー",
                        user_message="データベースに接続できません。"
                    )
                else:
                    raise DatabaseError(
                        message=f"{operation}失敗: DB操作エラー - {e}",
                        user_message="データベース操作に失敗しました。"
                    )
            except sqlite3.Error as e:
                logger.error(f"{operation}中にsqlite3.Error: {e}")
                raise DatabaseError(
                    message=f"{operation}失敗: {e}",
                    user_message="データベースエラーが発生しました。"
                )
        return wrapper
    return decorator
