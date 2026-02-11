"""
DashboardPage — ダッシュボード（ホーム）ページの Page Object
"""

from playwright.sync_api import Page, expect

from .base_page import BasePage


class DashboardPage(BasePage):
    """ダッシュボードページの操作を提供する。"""

    PATH = "/"

    def __init__(self, page: Page, base_url: str = ""):
        super().__init__(page, base_url)
        # Locators
        self.logout_button = page.get_by_role("button", name="ログアウト")
        self.user_name = page.locator(".user-name")
        self.logo = page.locator(".logo")
        self.sidebar_nav = page.locator(".sidebar-nav")

    def goto(self) -> "DashboardPage":
        """ダッシュボードに遷移する。"""
        self.navigate_to(self.PATH)
        return self

    def logout(self) -> None:
        """ログアウトする。"""
        self.logout_button.click()

    def get_username_display(self) -> str:
        """表示されているユーザー名を取得する。"""
        return self.user_name.text_content()

    def expect_on_dashboard(self) -> None:
        """ダッシュボードにいることを検証する。"""
        expect(self.logout_button).to_be_visible()
        expect(self.logo).to_be_visible()

    def navigate_via_sidebar(self, label: str) -> None:
        """サイドバーのナビゲーションリンクをクリックする。"""
        self.sidebar_nav.get_by_text(label).click()

    # ========================================
    # 統計情報関連（Wave2で追加）
    # ========================================

    def get_statistics(self) -> dict[str, str]:
        """
        ダッシュボードの統計情報を取得する。

        Returns:
            統計項目のラベルと値のマップ（例: {"登録ほ場数": "2", "総面積": "4.3 ha"}）
        """
        stats = {}
        stat_cards = self.page.locator(".stat-card")
        for i in range(stat_cards.count()):
            card = stat_cards.nth(i)
            label = card.locator(".stat-label").text_content().strip()
            value = card.locator(".stat-value").text_content().strip()
            stats[label] = value
        return stats

    def expect_stat_visible(self, label: str) -> None:
        """
        特定の統計項目が表示されていることを確認する。

        Args:
            label: 統計項目のラベル（例: "登録ほ場数"）
        """
        stat_card = self.page.locator(".stat-card", has_text=label)
        expect(stat_card).to_be_visible()

    def get_field_count(self) -> str:
        """
        ほ場数の表示値を取得する。

        Returns:
            ほ場数の文字列（例: "2"）
        """
        stat_card = self.page.locator(".stat-card", has_text="登録ほ場数")
        return stat_card.locator(".stat-value").text_content().strip()

    def get_crop_count(self) -> str:
        """
        作物数の表示値を取得する。

        Returns:
            作物数の文字列（例: "5"）
        """
        stat_card = self.page.locator(".stat-card", has_text="作物数")
        if stat_card.count() == 0:
            # 作物数の統計カードが存在しない場合は "-" を返す
            return "-"
        return stat_card.locator(".stat-value").text_content().strip()

    def get_total_area(self) -> str:
        """
        総面積の表示値を取得する。

        Returns:
            総面積の文字列（例: "4.3 ha"）
        """
        stat_card = self.page.locator(".stat-card", has_text="総面積")
        return stat_card.locator(".stat-value").text_content().strip()

    def wait_for_statistics_loaded(self, timeout: float = 10000) -> None:
        """
        統計情報のロード完了を待機する。

        "-" 表示から実際の値に変わるまで待つ。
        """
        # ほ場数が "-" でなくなるまで待機
        stat_card = self.page.locator(".stat-card", has_text="登録ほ場数")
        expect(stat_card.locator(".stat-value")).not_to_have_text("-", timeout=timeout)
