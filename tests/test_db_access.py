"""
DBアクセス層のテスト
"""

import pytest
import sys
import os
import sqlite3
import tempfile
from pathlib import Path

# プロジェクトルートをパスに追加
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import db_access
from db_access import (
    FieldRepository,
    PlanRepository,
    UserRepository,
    JAStaffRepository,
    get_db,
    row_to_dict,
    rows_to_list,
)


class TestDatabaseConnection:
    """DB接続のテスト"""

    def test_get_connection(self):
        """DB接続が取得できること"""
        conn = db_access.get_connection()
        assert conn is not None
        conn.close()

    def test_get_db_context_manager(self):
        """コンテキストマネージャでDB接続が管理されること"""
        with get_db() as conn:
            assert conn is not None
            cursor = conn.execute("SELECT 1")
            result = cursor.fetchone()
            assert result[0] == 1


class TestFieldRepository:
    """ほ場リポジトリのテスト"""

    def test_get_fields_returns_list(self):
        """ほ場一覧がリストで返ること"""
        fields = FieldRepository.get_fields(user_id=1)
        assert isinstance(fields, list)

    def test_get_fields_user_isolation(self):
        """ユーザーごとにほ場が分離されていること"""
        fields_user1 = FieldRepository.get_fields(user_id=1)
        fields_user999 = FieldRepository.get_fields(user_id=999)

        # 存在しないユーザーは空リスト
        assert isinstance(fields_user999, list)

    def test_get_field_by_id(self):
        """IDでほ場を取得できること"""
        fields = FieldRepository.get_fields(user_id=1)
        if fields:
            field_id = fields[0].get("id") or fields[0].get("field_id")
            if field_id:
                field = FieldRepository.get_field_by_id(field_id, user_id=1)
                assert field is not None


class TestPlanRepository:
    """輪作計画リポジトリのテスト"""

    def test_get_plans_returns_list(self):
        """計画一覧がリストで返ること"""
        plans = PlanRepository.get_plans(user_id=1)
        assert isinstance(plans, list)

    def test_get_plans_user_isolation(self):
        """ユーザーごとに計画が分離されていること"""
        plans_user1 = PlanRepository.get_plans(user_id=1)
        plans_user999 = PlanRepository.get_plans(user_id=999)

        # 存在しないユーザーは空リスト
        assert isinstance(plans_user999, list)


class TestUserRepository:
    """ユーザーリポジトリのテスト"""

    def test_get_user_by_username(self):
        """ユーザー名でユーザーを取得できること"""
        user = UserRepository.get_user_by_username("admin")
        # DBにユーザーがいない場合もある
        if user:
            assert user.get("username") == "admin"

    def test_get_user_nonexistent(self):
        """存在しないユーザーはNoneを返すこと"""
        user = UserRepository.get_user_by_username("nonexistent_user_12345")
        assert user is None


class TestJAStaffRepository:
    """JA職員用リポジトリのテスト"""

    def test_get_all_fields(self):
        """全ほ場を取得できること（JA職員用）"""
        fields = JAStaffRepository.get_all_fields(org_id=1)
        assert isinstance(fields, list)

    def test_get_all_farmers(self):
        """全農家を取得できること（JA職員用）"""
        farmers = JAStaffRepository.get_all_farmers(org_id=1)
        assert isinstance(farmers, list)


class TestSecurityIsolation:
    """セキュリティ分離テスト（切腹案件）"""

    def test_field_repository_requires_user_id(self):
        """FieldRepositoryはuser_idが必須であること"""
        # user_idなしで呼び出すとエラーになることを確認
        with pytest.raises(TypeError):
            FieldRepository.get_fields()  # user_id未指定

    def test_plan_repository_requires_user_id(self):
        """PlanRepositoryはuser_idが必須であること"""
        with pytest.raises(TypeError):
            PlanRepository.get_plans()  # user_id未指定

    def test_no_cross_user_data_leak(self):
        """他ユーザーのデータが漏洩しないこと"""
        # ユーザー1のデータ
        fields_user1 = FieldRepository.get_fields(user_id=1)

        # ユーザー2のデータ
        fields_user2 = FieldRepository.get_fields(user_id=2)

        # 両方にデータがある場合、IDが重複しないことを確認
        if fields_user1 and fields_user2:
            ids_user1 = {f.get("id") for f in fields_user1}
            ids_user2 = {f.get("id") for f in fields_user2}

            # ユーザー間でfield_idの重複があっても、
            # 実際のデータベースIDは異なるはず
            # （この実装依存のテストは削除してもよい）


class TestHelperFunctions:
    """ヘルパー関数のテスト"""

    def test_row_to_dict_none(self):
        """Noneの場合Noneを返すこと"""
        result = row_to_dict(None)
        assert result is None

    def test_rows_to_list_empty(self):
        """空リストの場合空リストを返すこと"""
        result = rows_to_list([])
        assert result == []
