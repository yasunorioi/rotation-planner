"""
LoginPage — ログインページの Page Object
"""

from playwright.sync_api import Page, expect

from .base_page import BasePage


class LoginPage(BasePage):
    """ログインページの操作を提供する。"""

    PATH = "/login"

    def __init__(self, page: Page, base_url: str = ""):
        super().__init__(page, base_url)
        # Locators
        self.username_input = page.get_by_label("ユーザー名")
        self.password_input = page.get_by_label("パスワード")
        self.login_button = page.get_by_role("button", name="ログイン")
        self.error_message = page.locator(".error-message")
        self.app_title = page.locator("h1")

    def goto(self) -> "LoginPage":
        """ログインページに遷移する。"""
        self.navigate_to(self.PATH)
        return self

    def login(self, username: str, password: str) -> None:
        """ユーザー名とパスワードを入力してログインする。"""
        self.username_input.fill(username)
        self.password_input.fill(password)
        self.login_button.click()

    def login_as_admin(self) -> None:
        """管理者としてログインする。"""
        self.login("admin", "admin123")

    def login_as_farmer(self) -> None:
        """デモ農家としてログインする。"""
        self.login("farmer_demo", "demo123")

    def get_error_text(self) -> str:
        """エラーメッセージのテキストを取得する。"""
        return self.error_message.text_content()

    def expect_error_visible(self) -> None:
        """エラーメッセージが表示されていることを検証する。"""
        expect(self.error_message).to_be_visible()

    def expect_on_login_page(self) -> None:
        """ログインページにいることを検証する。"""
        expect(self.app_title).to_contain_text("農業管理アプリ")
        expect(self.username_input).to_be_visible()
