"""
認証モジュールのテスト
"""

import pytest
import sys
import os
import tempfile
import json
from pathlib import Path

# プロジェクトルートをパスに追加
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rotation_planner.common import auth


class TestPasswordHashing:
    """パスワードハッシュ化のテスト"""

    def test_hash_password(self):
        """パスワードがハッシュ化されること"""
        password = "test123"
        hashed = auth.hash_password(password)

        assert hashed != password
        assert len(hashed) == 64  # SHA256は64文字

    def test_hash_password_deterministic(self):
        """同じパスワードは同じハッシュになること"""
        password = "test123"
        hash1 = auth.hash_password(password)
        hash2 = auth.hash_password(password)

        assert hash1 == hash2

    def test_hash_password_different_inputs(self):
        """異なるパスワードは異なるハッシュになること"""
        hash1 = auth.hash_password("password1")
        hash2 = auth.hash_password("password2")

        assert hash1 != hash2


class TestAuthenticate:
    """認証関数のテスト"""

    def test_authenticate_valid_user(self):
        """正しい認証情報でTrueを返すこと"""
        # admin / admin123 は初期データ
        result = auth.authenticate("admin", "admin123")
        assert result is True

    def test_authenticate_invalid_password(self):
        """間違ったパスワードでFalseを返すこと"""
        result = auth.authenticate("admin", "wrongpassword")
        assert result is False

    def test_authenticate_invalid_user(self):
        """存在しないユーザーでFalseを返すこと"""
        result = auth.authenticate("nonexistent_user", "password")
        assert result is False

    def test_authenticate_empty_credentials(self):
        """空の認証情報でFalseを返すこと"""
        result = auth.authenticate("", "")
        assert result is False


class TestGetUserInfo:
    """ユーザー情報取得のテスト"""

    def test_get_user_info_existing_user(self):
        """存在するユーザーの情報を取得できること"""
        user = auth.get_user_info("admin")

        assert user is not None
        assert user["username"] == "admin"
        assert "role" in user

    def test_get_user_info_nonexistent_user(self):
        """存在しないユーザーはNoneを返すこと"""
        user = auth.get_user_info("nonexistent_user_12345")
        assert user is None


class TestCanAccessFarmer:
    """ユーザーデータアクセス権限のテスト"""

    def test_admin_can_access_any_user(self):
        """管理者は全ユーザーのデータにアクセス可能"""
        result = auth.can_access_user_data("admin", 1)
        assert result is True

        result = auth.can_access_user_data("admin", 999)
        assert result is True

    def test_ja_staff_can_access_any_user(self):
        """JA職員は全ユーザーのデータにアクセス可能"""
        user = auth.get_user_info("ja_staff")
        if user:
            result = auth.can_access_user_data("ja_staff", 1)
            assert result is True

    def test_farmer_can_access_own_data(self):
        """農家は自分のデータにのみアクセス可能"""
        user = auth.get_user_info("farmer_demo")
        if user and user.get("id"):
            user_id = user["id"]
            result = auth.can_access_user_data("farmer_demo", user_id)
            assert result is True

    def test_farmer_cannot_access_other_user_data(self):
        """農家は他のユーザーのデータにアクセス不可（切腹案件テスト）"""
        user = auth.get_user_info("farmer_demo")
        if user and user.get("id"):
            # 別のユーザーID
            other_user_id = 9999
            result = auth.can_access_user_data("farmer_demo", other_user_id)
            assert result is False, "他ユーザーのデータにアクセスできてはいけない！"


class TestRoles:
    """ロール関連のテスト"""

    def test_admin_roles_defined(self):
        """管理者ロールが定義されていること"""
        assert auth.ROLE_ADMIN in auth.ADMIN_ROLES
        assert auth.ROLE_JA_STAFF in auth.ADMIN_ROLES

    def test_farmer_not_in_admin_roles(self):
        """農家ロールは管理者ロールに含まれないこと"""
        assert auth.ROLE_FARMER not in auth.ADMIN_ROLES


class TestIsAdminRole:
    """管理者判定のテスト"""

    def test_is_admin_role_true(self):
        """管理者ユーザーはTrueを返すこと"""
        result = auth.is_admin_role("admin")
        assert result is True

    def test_is_admin_role_false_for_farmer(self):
        """農家ユーザーはFalseを返すこと"""
        user = auth.get_user_info("farmer_demo")
        if user:
            result = auth.is_admin_role("farmer_demo")
            assert result is False
