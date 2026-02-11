"""
BasePage — 全 Page Object の基底クラス
"""

from playwright.sync_api import Page, expect


class BasePage:
    """共通のページ操作を提供する基底クラス。"""

    def __init__(self, page: Page, base_url: str = ""):
        self.page = page
        self.base_url = base_url

    def navigate_to(self, path: str) -> None:
        """指定パスに遷移する。"""
        url = f"{self.base_url}{path}" if self.base_url else path
        self.page.goto(url)

    def wait_for_load(self, timeout: float = 10000) -> None:
        """ページ読み込み完了を待機する。"""
        self.page.wait_for_load_state("networkidle", timeout=timeout)

    def get_title(self) -> str:
        """ページタイトルを取得する。"""
        return self.page.title()

    def screenshot(self, name: str = "screenshot") -> bytes:
        """スクリーンショットを撮影する。"""
        return self.page.screenshot(path=f"tests/e2e/screenshots/{name}.png")

    def get_current_url(self) -> str:
        """現在のURLを取得する。"""
        return self.page.url
