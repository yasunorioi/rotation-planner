"""
api/error_handlers.py のテスト

各カスタム例外が正しいHTTPステータスコードとJSONレスポンスに変換されることを確認。
"""

import pytest
import sys
import os
from pathlib import Path
from unittest.mock import patch

# プロジェクトルートをパスに追加
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI
from fastapi.testclient import TestClient

from rotation_planner.common.exceptions import (
    RotationPlannerError,
    DatabaseError,
    DatabaseConnectionError,
    DuplicateKeyError,
    ForeignKeyViolationError,
    NotNullViolationError,
    RecordNotFoundError,
    FileOperationError,
    ValidationError,
)
from api.error_handlers import register_exception_handlers, require_found


def _make_app_with_route(exception_to_raise):
    """テスト用FastAPIアプリを作成し、指定の例外を投げるエンドポイントを登録"""
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/test")
    def test_route():
        raise exception_to_raise

    return app


class TestExceptionHandlers:
    """各例外が正しいHTTPステータスコードに変換されること"""

    def test_record_not_found_returns_404(self):
        exc = RecordNotFoundError("Field not found", "ほ場が見つかりません")
        client = TestClient(_make_app_with_route(exc))
        resp = client.get("/test")
        assert resp.status_code == 404
        assert resp.json() == {"detail": "ほ場が見つかりません"}

    def test_duplicate_key_returns_409(self):
        exc = DuplicateKeyError("UNIQUE constraint failed", "このコードは既に使用されています")
        client = TestClient(_make_app_with_route(exc))
        resp = client.get("/test")
        assert resp.status_code == 409
        assert resp.json() == {"detail": "このコードは既に使用されています"}

    def test_foreign_key_violation_returns_400(self):
        exc = ForeignKeyViolationError("FK failed", "参照先が存在しません")
        client = TestClient(_make_app_with_route(exc))
        resp = client.get("/test")
        assert resp.status_code == 400
        assert resp.json() == {"detail": "参照先が存在しません"}

    def test_not_null_violation_returns_400(self):
        exc = NotNullViolationError("NOT NULL failed", "必須項目が未入力です")
        client = TestClient(_make_app_with_route(exc))
        resp = client.get("/test")
        assert resp.status_code == 400
        assert resp.json() == {"detail": "必須項目が未入力です"}

    def test_database_connection_error_returns_503(self):
        exc = DatabaseConnectionError("Connection refused", "接続不可")
        client = TestClient(_make_app_with_route(exc))
        resp = client.get("/test")
        assert resp.status_code == 503
        assert resp.json() == {"detail": "データベースに接続できません"}

    def test_database_error_returns_500(self):
        exc = DatabaseError("Unexpected DB error", "データベースエラーが発生しました")
        client = TestClient(_make_app_with_route(exc))
        resp = client.get("/test")
        assert resp.status_code == 500
        assert resp.json() == {"detail": "データベースエラーが発生しました"}

    def test_validation_error_returns_422(self):
        exc = ValidationError("area_ha", "面積は正の値を指定してください")
        client = TestClient(_make_app_with_route(exc))
        resp = client.get("/test")
        assert resp.status_code == 422
        assert resp.json() == {"detail": "面積は正の値を指定してください"}

    def test_file_operation_error_returns_500(self):
        exc = FileOperationError("CSV read failed")
        client = TestClient(_make_app_with_route(exc))
        resp = client.get("/test")
        assert resp.status_code == 500
        assert resp.json() == {"detail": "CSV read failed"}

    def test_rotation_planner_error_returns_500(self):
        exc = RotationPlannerError("Unknown error", "予期しないエラーが発生しました")
        client = TestClient(_make_app_with_route(exc))
        resp = client.get("/test")
        assert resp.status_code == 500
        assert resp.json() == {"detail": "予期しないエラーが発生しました"}

    def test_user_message_used_in_response(self):
        """user_message（日本語）がレスポンスに使われること"""
        exc = RecordNotFoundError("internal message", "ユーザー向けメッセージ")
        client = TestClient(_make_app_with_route(exc))
        resp = client.get("/test")
        assert resp.json()["detail"] == "ユーザー向けメッセージ"

    def test_database_connection_hides_internal_message(self):
        """DatabaseConnectionErrorは内部メッセージを隠すこと"""
        exc = DatabaseConnectionError("sqlite3.OperationalError: unable to open database", "内部エラー")
        client = TestClient(_make_app_with_route(exc))
        resp = client.get("/test")
        # user_messageではなく固定メッセージが返る
        assert resp.json()["detail"] == "データベースに接続できません"
        assert "sqlite3" not in resp.json()["detail"]


class TestRequireFound:
    """require_found ユーティリティのテスト"""

    def test_returns_value_when_not_none(self):
        result = require_found({"id": 1, "name": "test"}, "テスト")
        assert result == {"id": 1, "name": "test"}

    def test_raises_record_not_found_when_none(self):
        with pytest.raises(RecordNotFoundError) as exc_info:
            require_found(None, "ほ場")
        assert "ほ場" in exc_info.value.user_message

    def test_default_resource_name(self):
        with pytest.raises(RecordNotFoundError) as exc_info:
            require_found(None)
        assert "リソース" in exc_info.value.user_message

    def test_passes_through_falsy_non_none(self):
        """0, empty string, empty list などはNoneではないのでそのまま返す"""
        assert require_found(0, "数値") == 0
        assert require_found("", "文字列") == ""
        assert require_found([], "リスト") == []
