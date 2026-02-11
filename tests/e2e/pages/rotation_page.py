"""
RotationPage — 輪作計画ページの Page Object
"""

from playwright.sync_api import Page, expect

from .base_page import BasePage


class RotationPage(BasePage):
    """輪作計画ページの操作を提供する。"""

    PATH = "/rotation"

    def __init__(self, page: Page, base_url: str = ""):
        super().__init__(page, base_url)
        # Locators（画面構造に応じて調整）
        self.save_name_input = page.locator("input[name='saveName'], input[placeholder*='計画名']")
        self.optimize_button = page.get_by_role("button", name="最適化実行")
        self.result_table = page.locator("table.result-table, .rotation-result table")
        self.plan_list = page.locator(".plan-list, .saved-plans")
        self.loading_indicator = page.locator(".spinner, .loading")

    def goto(self) -> "RotationPage":
        """輪作計画画面へ遷移する。"""
        self.navigate_to(self.PATH)
        self.wait_for_load()
        return self

    def navigate_to_rotation(self) -> "RotationPage":
        """輪作計画画面へ遷移する（エイリアス）。"""
        return self.goto()

    def create_plan(self, name: str) -> None:
        """
        新規計画を作成する。

        Args:
            name: 計画名
        """
        self.save_name_input.fill(name)

    def run_optimization(self) -> None:
        """最適化実行ボタンを押下する。"""
        self.optimize_button.click()

    def wait_for_optimization_result(self, timeout: float = 30000) -> None:
        """
        最適化結果の表示を待機する。

        Args:
            timeout: タイムアウト時間（ミリ秒）
        """
        # ローディングインジケーターが消えるのを待つ
        if self.loading_indicator.count() > 0:
            expect(self.loading_indicator).to_be_hidden(timeout=timeout)
        # 結果テーブルが表示されるのを待つ
        expect(self.result_table).to_be_visible(timeout=timeout)

    def get_plan_list(self) -> list[str]:
        """
        計画一覧を取得する。

        Returns:
            計画名のリスト
        """
        if self.plan_list.count() == 0:
            return []
        items = self.plan_list.locator(".plan-item, li, .plan-name")
        return [items.nth(i).text_content() for i in range(items.count())]

    def get_optimization_result(self) -> dict:
        """
        最適化結果テーブルの内容を取得する。

        Returns:
            結果データ（行数、列数等）
        """
        if self.result_table.count() == 0:
            return {"rows": 0, "cols": 0, "data": []}

        rows = self.result_table.locator("tbody tr")
        row_count = rows.count()
        if row_count == 0:
            return {"rows": 0, "cols": 0, "data": []}

        # 最初の行から列数を取得
        first_row = rows.nth(0)
        cols = first_row.locator("td")
        col_count = cols.count()

        # 全データを取得
        data = []
        for i in range(row_count):
            row = rows.nth(i)
            cells = row.locator("td")
            row_data = [cells.nth(j).text_content().strip() for j in range(cells.count())]
            data.append(row_data)

        return {"rows": row_count, "cols": col_count, "data": data}

    def expect_plan_exists(self, name: str) -> None:
        """
        計画が存在することを確認する。

        Args:
            name: 計画名
        """
        plan_item = self.plan_list.locator(f"text={name}")
        expect(plan_item).to_be_visible()

    def expect_result_visible(self) -> None:
        """最適化結果が表示されていることを確認する。"""
        expect(self.result_table).to_be_visible()
