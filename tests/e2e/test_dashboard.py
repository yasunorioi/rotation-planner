"""
E2E テスト: ダッシュボード

テストケース:
  - test_dashboard_loads: ダッシュボードが表示されること
  - test_dashboard_shows_statistics: 統計情報（ほ場数、作物数等）が表示
  - test_dashboard_after_data_change: データ追加後に統計が更新される
"""

import pytest
from playwright.sync_api import Page, expect

from .pages import DashboardPage


@pytest.mark.e2e
class TestDashboardLoads:
    """ダッシュボード表示のテスト"""

    def test_dashboard_displays(self, authenticated_page: Page, base_url: str):
        """ダッシュボードが正常に表示される。"""
        dashboard = DashboardPage(authenticated_page, base_url)
        dashboard.goto()

        # ダッシュボードページにいることを確認
        dashboard.expect_on_dashboard()

        # ユーザー名が表示されることを確認
        username = dashboard.get_username_display()
        assert username is not None
        assert len(username) > 0

    def test_dashboard_url(self, authenticated_page: Page, base_url: str):
        """ダッシュボードのURLが正しいことを確認する。"""
        dashboard = DashboardPage(authenticated_page, base_url)
        dashboard.goto()

        # URLが / であることを確認
        expect(authenticated_page).to_have_url(f"{base_url}/")

    def test_dashboard_has_workflow_section(self, authenticated_page: Page, base_url: str):
        """ダッシュボードにワークフローセクションが表示される。"""
        dashboard = DashboardPage(authenticated_page, base_url)
        dashboard.goto()

        # ワークフローセクションが存在することを確認
        workflow_section = authenticated_page.locator(".workflow-section")
        expect(workflow_section).to_be_visible()


@pytest.mark.e2e
class TestDashboardStatistics:
    """ダッシュボード統計情報のテスト"""

    def test_statistics_visible(self, authenticated_page: Page, base_url: str):
        """統計情報カードが表示される。"""
        dashboard = DashboardPage(authenticated_page, base_url)
        dashboard.goto()

        # 統計カードが表示されることを確認
        stat_cards = authenticated_page.locator(".stat-card")
        expect(stat_cards.first).to_be_visible()

        # 少なくとも1つ以上の統計カードが存在すること
        assert stat_cards.count() > 0

    def test_field_count_displayed(self, farmer_page: Page, base_url: str):
        """ほ場数が表示される。"""
        dashboard = DashboardPage(farmer_page, base_url)
        dashboard.goto()

        # 統計ロード完了を待機
        dashboard.wait_for_statistics_loaded()

        # ほ場数の統計項目が表示される
        dashboard.expect_stat_visible("登録ほ場数")

        # ほ場数を取得（conftest.py でテスト用ほ場2件が投入済み）
        field_count = dashboard.get_field_count()
        assert field_count is not None
        assert field_count != "-"

    def test_total_area_displayed(self, farmer_page: Page, base_url: str):
        """総面積が表示される。"""
        dashboard = DashboardPage(farmer_page, base_url)
        dashboard.goto()

        # 総面積の統計項目が表示される
        dashboard.expect_stat_visible("総面積")

        # 総面積を取得
        total_area = dashboard.get_total_area()
        assert total_area is not None
        assert "ha" in total_area

    def test_get_all_statistics(self, authenticated_page: Page, base_url: str):
        """全ての統計情報を取得できる。"""
        dashboard = DashboardPage(authenticated_page, base_url)
        dashboard.goto()

        # 全統計情報を取得
        stats = dashboard.get_statistics()

        # 統計情報が辞書として取得できること
        assert isinstance(stats, dict)
        assert len(stats) > 0

        # 主要な統計項目が含まれていること
        assert "登録ほ場数" in stats
        assert "総面積" in stats


@pytest.mark.e2e
class TestDashboardDataChange:
    """データ変更後のダッシュボード更新テスト"""

    def test_statistics_reflect_initial_data(self, farmer_page: Page, base_url: str):
        """
        初期データが統計に反映されていることを確認する。

        conftest.py でテスト用ほ場が投入済み。
        """
        dashboard = DashboardPage(farmer_page, base_url)
        dashboard.goto()

        # 統計ロード完了を待機
        dashboard.wait_for_statistics_loaded()

        # ほ場数を確認
        field_count = dashboard.get_field_count()
        # 少なくとも1件以上のほ場が存在することを確認
        field_count_int = int(field_count)
        assert field_count_int >= 1, f"ほ場が存在しません。実際: {field_count}"

    def test_dashboard_refresh_updates_statistics(self, farmer_page: Page, base_url: str):
        """
        ダッシュボードをリフレッシュすると統計が更新される。

        注: 実際のデータ追加APIは他のテストと干渉する可能性があるため、
        このテストではリフレッシュのみを確認する。
        """
        dashboard = DashboardPage(farmer_page, base_url)
        dashboard.goto()

        # 統計ロード完了を待機
        dashboard.wait_for_statistics_loaded()

        # 初期統計を取得
        initial_stats = dashboard.get_statistics()

        # ページをリフレッシュ
        farmer_page.reload()
        dashboard.wait_for_load()

        # 統計ロード完了を再度待機
        dashboard.wait_for_statistics_loaded()

        # 統計が再表示されることを確認
        refreshed_stats = dashboard.get_statistics()
        assert len(refreshed_stats) > 0

        # 統計項目が一致すること（データ追加していないので値も同じはず）
        assert initial_stats == refreshed_stats
