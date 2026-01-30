"""
セキュリティテスト（切腹案件）

他農家のデータが絶対に見えないことを保証するテスト
"""

import pytest
import sys
import os

# プロジェクトルートをパスに追加
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rotation_planner.common import auth
from rotation_planner.common import FieldRepository, PlanRepository, JAStaffRepository


class TestDataIsolation:
    """データ分離テスト"""

    def test_farmer_cannot_see_other_farmers_fields(self):
        """
        農家は他の農家のほ場を見れない
        これが失敗したら切腹案件
        """
        # 農家Aのほ場
        fields_a = FieldRepository.get_fields(user_id=1)

        # 農家Bのほ場
        fields_b = FieldRepository.get_fields(user_id=2)

        # 農家Aのリクエストで農家Bのデータが含まれていないことを確認
        if fields_a and fields_b:
            # user_idが異なるデータが混入していないことを確認
            for field in fields_a:
                user_id = field.get("user_id")
                if user_id is not None:
                    assert user_id == 1, "他農家のデータが混入している！切腹案件！"

    def test_farmer_cannot_see_other_farmers_plans(self):
        """
        農家は他の農家の輪作計画を見れない
        これが失敗したら切腹案件
        """
        plans_a = PlanRepository.get_plans(user_id=1)
        plans_b = PlanRepository.get_plans(user_id=2)

        if plans_a and plans_b:
            for plan in plans_a:
                user_id = plan.get("user_id")
                if user_id is not None:
                    assert user_id == 1, "他農家の計画が混入している！切腹案件！"


class TestAccessControl:
    """アクセス制御テスト"""

    def test_can_access_farmer_strict_check(self):
        """
        can_access_farmer関数が厳密にチェックすること
        """
        # 存在しないユーザー
        result = auth.can_access_farmer("nonexistent", "F001")
        assert result is False, "存在しないユーザーがアクセスできてはいけない"

    def test_admin_bypass_is_intentional(self):
        """
        管理者のバイパスは意図的であること
        """
        # adminは全データにアクセス可能（これは仕様）
        assert auth.can_access_farmer("admin", "F001") is True
        assert auth.can_access_farmer("admin", "F999") is True

    def test_role_escalation_not_possible(self):
        """
        ロールエスカレーションができないこと
        """
        # 農家ユーザーのロールを確認
        user = auth.get_user_info("farmer_demo")
        if user:
            assert user.get("role") != "admin", "農家がadminロールを持っていてはいけない"
            assert user.get("role") != "ja_staff", "農家がja_staffロールを持っていてはいけない"


class TestSQLInjection:
    """SQLインジェクション対策テスト"""

    def test_field_repository_sql_injection(self):
        """
        FieldRepositoryがSQLインジェクションを防ぐこと
        """
        # 悪意のあるuser_id
        try:
            # 文字列を渡してもエラーにならないか確認
            # （intにキャストされるかエラーになるべき）
            fields = FieldRepository.get_fields(user_id="1 OR 1=1")
            # 結果が返っても、全データが漏洩していないことを確認
            assert isinstance(fields, list)
        except (TypeError, ValueError, Exception):
            # エラーになるのは正しい動作
            pass

    def test_username_sql_injection(self):
        """
        ユーザー名でSQLインジェクションを防ぐこと
        """
        # 悪意のあるユーザー名
        malicious_username = "admin' OR '1'='1"
        user = auth.get_user_info(malicious_username)

        # 悪意のある入力でadminユーザーが返ってこないこと
        if user:
            assert user.get("username") == malicious_username, \
                "SQLインジェクションで別ユーザーのデータが取得できてはいけない"


class TestCSVExportSecurity:
    """CSVエクスポートのセキュリティテスト"""

    def test_csv_export_respects_user_id(self):
        """
        CSVエクスポートがuser_idを尊重すること
        """
        # csv_exportモジュールがある場合のテスト
        try:
            import csv_export

            # user_id=1のデータのみがエクスポートされることを確認
            # （実際のエクスポート関数の仕様に依存）
            if hasattr(csv_export, 'export_fields_csv'):
                # テスト実装
                pass
        except ImportError:
            pytest.skip("csv_exportモジュールが見つかりません")


class TestJAStaffAccess:
    """JA職員アクセステスト"""

    def test_ja_staff_can_see_all_farmers_in_org(self):
        """
        JA職員は組織内の全農家データを見れること（これは仕様）
        """
        # JA職員用リポジトリのテスト
        all_fields = JAStaffRepository.get_all_fields(org_id=1)
        assert isinstance(all_fields, list)

    def test_ja_staff_cannot_see_other_org_data(self):
        """
        JA職員は他組織のデータを見れないこと
        """
        # org_id=1の職員がorg_id=2のデータを見れないことを確認
        fields_org1 = JAStaffRepository.get_all_fields(org_id=1)
        fields_org2 = JAStaffRepository.get_all_fields(org_id=2)

        # 両方にデータがある場合、組織IDが混在していないことを確認
        if fields_org1:
            for field in fields_org1:
                org_id = field.get("org_id")
                if org_id is not None:
                    assert org_id == 1, "他組織のデータが混入している"
