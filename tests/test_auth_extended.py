"""
認証モジュール拡張テスト - CRUD・アクセス制御系
"""

import pytest
import sys
import os

# プロジェクトルートをパスに追加
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rotation_planner.common import auth
from rotation_planner.common.db import get_db


class TestAddUser:
    """add_user関数のテスト"""

    def test_AU_01_add_user_success(self, test_db):
        """AU-01: 正常なユーザー追加"""
        result = auth.add_user(
            username="new_farmer",
            password="password123",
            role="farmer",
            display_name="新規農家",
            org_id=2
        )
        assert result is True

        # 追加されたユーザーが認証できることを確認
        auth_result = auth.authenticate("new_farmer", "password123")
        assert auth_result is True

    def test_AU_02_add_user_duplicate_username(self, test_db):
        """AU-02: 既存ユーザー名でValueErrorを送出"""
        # adminは初期ユーザー
        with pytest.raises(ValueError, match="既に使用されています"):
            auth.add_user(
                username="admin",
                password="newpassword",
                role="admin",
                org_id=1
            )


class TestUpdatePassword:
    """update_password関数のテスト"""

    def test_AU_03_update_password_success(self, test_db):
        """AU-03: パスワード変更成功"""
        # 新規ユーザー追加
        auth.add_user(
            username="test_user_pw",
            password="oldpassword",
            role="farmer",
            org_id=2
        )

        # パスワード変更
        result = auth.update_password("test_user_pw", "newpassword")
        assert result is True

        # 新しいパスワードで認証できることを確認
        auth_result = auth.authenticate("test_user_pw", "newpassword")
        assert auth_result is True

        # 古いパスワードでは認証できないことを確認
        auth_result_old = auth.authenticate("test_user_pw", "oldpassword")
        assert auth_result_old is False

    def test_AU_04_update_password_nonexistent_user(self, test_db):
        """AU-04: 存在しないユーザーでFalseを返す"""
        result = auth.update_password("nonexistent_user_xyz", "newpassword")
        assert result is False


class TestDeleteUser:
    """delete_user関数のテスト"""

    def test_AU_05_delete_user_logical_deletion(self, test_db):
        """AU-05: 論理削除（is_active=0）"""
        # 新規ユーザー追加
        auth.add_user(
            username="test_user_delete",
            password="password123",
            role="farmer",
            org_id=2
        )

        # 削除実行
        result = auth.delete_user("test_user_delete")
        assert result is True

        # DBで is_active=0 になっていることを確認
        with get_db() as conn:
            cursor = conn.execute(
                "SELECT is_active FROM users WHERE username = ?",
                ("test_user_delete",)
            )
            row = cursor.fetchone()
            assert row is not None
            assert row[0] == 0  # is_active=0

    def test_AU_06_delete_user_cannot_authenticate(self, test_db):
        """AU-06: 削除後はログイン不可"""
        # 新規ユーザー追加
        auth.add_user(
            username="test_user_delete2",
            password="password123",
            role="farmer",
            org_id=2
        )

        # 削除前はログイン可能
        auth_before = auth.authenticate("test_user_delete2", "password123")
        assert auth_before is True

        # 削除実行
        auth.delete_user("test_user_delete2")

        # 削除後はログイン不可
        auth_after = auth.authenticate("test_user_delete2", "password123")
        assert auth_after is False


class TestGetAdminCount:
    """get_admin_count関数のテスト"""

    def test_AU_07_get_admin_count(self, test_db):
        """AU-07: 管理者数取得（初期データで最低1名）"""
        count = auth.get_admin_count()
        assert isinstance(count, int)
        assert count >= 1  # 初期データにadminが1名以上


class TestGetUserRole:
    """get_user_role関数のテスト"""

    def test_AU_08_get_user_role_existing_user(self, test_db):
        """AU-08: ロール取得（admin/farmer等）"""
        # adminユーザーのロール
        role_admin = auth.get_user_role("admin")
        assert role_admin == "admin"

        # farmer_demoユーザーのロール
        role_farmer = auth.get_user_role("farmer_demo")
        assert role_farmer == "farmer"

    def test_AU_09_get_user_role_nonexistent_user(self, test_db):
        """AU-09: 存在しないユーザーはNone"""
        role = auth.get_user_role("nonexistent_user_xyz")
        assert role is None


class TestGetAccessibleUserIds:
    """get_accessible_user_ids関数のテスト"""

    def test_AU_10_get_accessible_user_ids_admin(self, test_db, admin_state):
        """AU-10: adminは空リスト（全アクセス）"""
        accessible_ids = auth.get_accessible_user_ids("admin")
        assert isinstance(accessible_ids, list)
        assert accessible_ids == []  # 空=全ユーザーアクセス可能

    def test_AU_11_get_accessible_user_ids_farmer(self, test_db, farmer_state):
        """AU-11: farmerは自分のIDのみ"""
        accessible_ids = auth.get_accessible_user_ids("farmer_demo")
        assert isinstance(accessible_ids, list)
        assert len(accessible_ids) == 1

        # farmer_demoの実際のIDを確認
        user = auth.get_user_info("farmer_demo")
        assert user is not None
        assert accessible_ids[0] == user["id"]


class TestLoadUsers:
    """load_users関数のテスト"""

    def test_AU_12_load_users(self, test_db):
        """AU-12: 全ユーザー取得（List[Dict]）"""
        users = auth.load_users()
        assert isinstance(users, list)
        assert len(users) >= 3  # 初期データ: admin, ja_staff, farmer_demo

        # 各ユーザーが辞書形式
        for user in users:
            assert isinstance(user, dict)
            assert "username" in user
            assert "role" in user
            assert "is_active" in user
            assert user["is_active"] == 1  # load_users()はアクティブユーザーのみ


class TestCanAccessFarmerBackwardCompatibility:
    """can_access_farmer後方互換性テスト"""

    def test_AU_13_can_access_farmer_backward_compatibility(self, test_db):
        """AU-13: can_access_farmerがcan_access_user_dataと同等"""
        # farmer_demoの実際のIDを取得
        user = auth.get_user_info("farmer_demo")
        assert user is not None
        farmer_id = user["id"]

        # can_access_user_dataの結果
        result_new = auth.can_access_user_data("admin", farmer_id)
        # can_access_farmerの結果（文字列IDを渡す）
        result_old = auth.can_access_farmer("admin", str(farmer_id))

        # 両方ともTrueになるはず
        assert result_new is True
        assert result_old is True
        assert result_new == result_old

        # farmerが他ユーザーにアクセスできないことも確認
        admin_user = auth.get_user_info("admin")
        admin_id = admin_user["id"]

        result_new_deny = auth.can_access_user_data("farmer_demo", admin_id)
        result_old_deny = auth.can_access_farmer("farmer_demo", str(admin_id))

        assert result_new_deny is False
        assert result_old_deny is False
        assert result_new_deny == result_old_deny
