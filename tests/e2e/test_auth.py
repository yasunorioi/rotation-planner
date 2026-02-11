"""
E2E テスト: 認証（ログイン / ログアウト）

テストケース:
  - test_login_success: 正しい credential でログイン → ダッシュボードに遷移
  - test_login_failure: 間違った password でエラーメッセージ表示
  - test_logout: ログイン → ログアウト → ログイン画面に戻る
  - test_protected_route: 未ログインでアクセス → ログイン画面にリダイレクト
"""

import pytest
from playwright.sync_api import Page, expect

from .pages import LoginPage, DashboardPage


@pytest.mark.e2e
class TestLoginSuccess:
    """正常ログインのテスト"""

    def test_admin_login(self, page: Page, base_url: str):
        """管理者でログインするとダッシュボードに遷移する。"""
        login_page = LoginPage(page, base_url)
        login_page.goto()
        login_page.login_as_admin()

        # ダッシュボードへの遷移を待機
        page.wait_for_url(f"{base_url}/", timeout=10000)

        dashboard = DashboardPage(page, base_url)
        dashboard.expect_on_dashboard()
        assert "管理者" in dashboard.get_username_display()

    def test_farmer_login(self, page: Page, base_url: str):
        """デモ農家でログインするとダッシュボードに遷移する。"""
        login_page = LoginPage(page, base_url)
        login_page.goto()
        login_page.login_as_farmer()

        page.wait_for_url(f"{base_url}/", timeout=10000)

        dashboard = DashboardPage(page, base_url)
        dashboard.expect_on_dashboard()
        assert "デモ農家" in dashboard.get_username_display()


@pytest.mark.e2e
class TestLoginFailure:
    """ログイン失敗のテスト"""

    def test_wrong_password(self, page: Page, base_url: str):
        """間違ったパスワードで 401 が返り、ダッシュボードに遷移しない。"""
        login_page = LoginPage(page, base_url)
        login_page.goto()

        # API レスポンスを待機しつつログインを実行
        with page.expect_response("**/api/auth/login") as response_info:
            login_page.login("admin", "wrong_password")
        assert response_info.value.status == 401

        # ページが安定するのを待機（401 インターセプタによるリロードの可能性）
        page.wait_for_load_state("networkidle")

        # ログインページに留まっていること（ダッシュボードに遷移していないこと）
        assert "/login" in page.url
        login_page = LoginPage(page, base_url)
        login_page.expect_on_login_page()

    def test_nonexistent_user(self, page: Page, base_url: str):
        """存在しないユーザーで 401 が返り、ダッシュボードに遷移しない。"""
        login_page = LoginPage(page, base_url)
        login_page.goto()

        with page.expect_response("**/api/auth/login") as response_info:
            login_page.login("nonexistent_user", "password123")
        assert response_info.value.status == 401

        page.wait_for_load_state("networkidle")

        assert "/login" in page.url
        login_page = LoginPage(page, base_url)
        login_page.expect_on_login_page()


@pytest.mark.e2e
class TestLogout:
    """ログアウトのテスト"""

    def test_logout_redirects_to_login(self, page: Page, base_url: str):
        """ログイン → ログアウト → ログイン画面に戻る。"""
        # ログイン
        login_page = LoginPage(page, base_url)
        login_page.goto()
        login_page.login_as_admin()
        page.wait_for_url(f"{base_url}/", timeout=10000)

        # ログアウト
        dashboard = DashboardPage(page, base_url)
        dashboard.logout()

        # ログイン画面に戻ることを確認
        page.wait_for_url(f"**/login", timeout=10000)
        login_page = LoginPage(page, base_url)
        login_page.expect_on_login_page()


@pytest.mark.e2e
class TestProtectedRoute:
    """認証保護されたルートのテスト"""

    def test_unauthenticated_access_redirects(self, page: Page, base_url: str):
        """未ログインでダッシュボードにアクセスするとログイン画面にリダイレクトされる。"""
        # localStorage をクリアして未認証状態にする
        page.goto(f"{base_url}/login")
        page.evaluate("() => { localStorage.removeItem('token'); localStorage.removeItem('user'); }")

        # ダッシュボードに直接アクセス
        page.goto(f"{base_url}/")

        # ログイン画面にリダイレクトされる
        page.wait_for_url(f"**/login", timeout=10000)
        login_page = LoginPage(page, base_url)
        login_page.expect_on_login_page()

    def test_unauthenticated_fields_redirects(self, page: Page, base_url: str):
        """未ログインでほ場一覧にアクセスするとログイン画面にリダイレクトされる。"""
        page.goto(f"{base_url}/login")
        page.evaluate("() => { localStorage.removeItem('token'); localStorage.removeItem('user'); }")

        page.goto(f"{base_url}/fields")

        page.wait_for_url(f"**/login", timeout=10000)
        login_page = LoginPage(page, base_url)
        login_page.expect_on_login_page()
