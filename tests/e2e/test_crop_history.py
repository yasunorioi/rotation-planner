"""
E2E テスト: 作付履歴

テストケース:
  - test_crop_history_list: 作付履歴モーダルが表示される
  - test_add_crop_history: 新規作付履歴登録（一括登録機能使用）
  - test_crop_history_display: 登録した作付履歴が表示される

Note: 作付履歴は Fields.jsx 内のモーダル機能として実装されているため、
      FieldPage を使用する。
"""

import pytest
from playwright.sync_api import Page, expect

from .pages import FieldPage


@pytest.mark.e2e
class TestCropHistoryList:
    """作付履歴一覧のテスト"""

    def test_crop_history_modal_opens(self, authenticated_page: Page, base_url: str):
        """作付履歴モーダルが開く（admin）。"""
        field_page = FieldPage(authenticated_page, base_url)
        field_page.goto()

        # admin のE2E001 の作付履歴モーダルを開く
        field_page.show_history("E2E001")

        # モーダルが表示されること
        expect(field_page.history_modal).to_be_visible()
        expect(field_page.history_modal_title).to_contain_text("作付履歴")
        expect(field_page.history_modal_title).to_contain_text("E2Eテストほ場1号")

    def test_crop_history_list_display(self, authenticated_page: Page, base_url: str):
        """作付履歴が一覧表示される（admin）。"""
        field_page = FieldPage(authenticated_page, base_url)
        field_page.goto()

        # E2E001 の作付履歴を開く
        field_page.show_history("E2E001")

        # 履歴テーブルが表示されること（初期状態では空かもしれない）
        expect(field_page.history_table).to_be_visible()


@pytest.mark.e2e
class TestAddCropHistory:
    """作付履歴登録のテスト"""

    def test_add_crop_history_bulk(self, authenticated_page: Page, base_url: str):
        """作付履歴を一括登録できる（admin）。"""
        field_page = FieldPage(authenticated_page, base_url)
        field_page.goto()

        # admin のE2E001 の作付履歴を開く
        field_page.show_history("E2E001")

        # 一括登録で作付履歴を追加
        import datetime
        current_year = datetime.datetime.now().year
        fiscal_year = current_year if datetime.datetime.now().month >= 4 else current_year - 1

        # 4年分の履歴を登録（FAMIC表記準拠）
        history_data = {
            fiscal_year - 3: "だいず",
            fiscal_year - 2: "小麦(春播)",
            fiscal_year - 1: "ばれいしょ",
            fiscal_year: "てんさい",
        }

        field_page.add_bulk_history(history_data)

        # 登録されたことを確認（履歴テーブルを再確認）
        history_list = field_page.get_history_list()
        assert len(history_list) >= 4, "4件以上の履歴が登録されているはず"

        # 各年度の作物が表示されることを確認
        field_page.expect_history_entry(str(fiscal_year - 3), "だいず")
        field_page.expect_history_entry(str(fiscal_year - 2), "小麦(春播)")
        field_page.expect_history_entry(str(fiscal_year - 1), "ばれいしょ")
        field_page.expect_history_entry(str(fiscal_year), "てんさい")

    def test_add_crop_history_updates_existing(self, authenticated_page: Page, base_url: str):
        """既存の年度の作付履歴を上書きできる（admin）。"""
        field_page = FieldPage(authenticated_page, base_url)
        field_page.goto()

        # admin のE2E001 の作付履歴を開く
        field_page.show_history("E2E001")

        # 前回のテストで登録した履歴を上書き
        import datetime
        current_year = datetime.datetime.now().year
        fiscal_year = current_year if datetime.datetime.now().month >= 4 else current_year - 1

        # 最新年度を「小麦(春播)」に変更
        history_data = {
            fiscal_year: "小麦(春播)",
        }

        field_page.add_bulk_history(history_data)

        # 上書きされたことを確認
        field_page.expect_history_entry(str(fiscal_year), "小麦(春播)")


@pytest.mark.e2e
class TestCropHistoryByField:
    """ほ場別の作付履歴テスト"""

    def test_crop_history_different_fields(self, authenticated_page: Page, base_url: str):
        """異なるほ場の作付履歴が独立して管理される（admin）。"""
        field_page = FieldPage(authenticated_page, base_url)
        field_page.goto()

        import datetime
        current_year = datetime.datetime.now().year
        fiscal_year = current_year if datetime.datetime.now().month >= 4 else current_year - 1

        # admin のE2E001 の履歴を登録
        field_page.show_history("E2E001")
        field_page.add_bulk_history({fiscal_year: "だいず"})
        field_page.close_history_modal()

        # E2E002 が存在しない場合はスキップ（削除テストで削除済みの可能性）
        try:
            field_page.expect_field_in_list("E2Eテストほ場2号")
        except AssertionError:
            pytest.skip("E2Eテストほ場2号が削除済みのためスキップ")

        # E2E002 の履歴を登録（別の作物）
        field_page.show_history("E2E002")
        field_page.add_bulk_history({fiscal_year: "小麦(春播)"})
        field_page.close_history_modal()

        # E2E001 の履歴を再確認（E2E002 の影響を受けていないこと）
        field_page.show_history("E2E001")
        field_page.expect_history_entry(str(fiscal_year), "だいず")
        field_page.close_history_modal()

        # E2E002 の履歴を再確認
        field_page.show_history("E2E002")
        field_page.expect_history_entry(str(fiscal_year), "小麦(春播)")
        field_page.close_history_modal()


@pytest.mark.e2e
class TestCropHistoryModalClose:
    """作付履歴モーダルの閉じる操作テスト"""

    def test_close_history_modal(self, authenticated_page: Page, base_url: str):
        """作付履歴モーダルを閉じることができる（admin）。"""
        field_page = FieldPage(authenticated_page, base_url)
        field_page.goto()

        # admin のE2E001 の履歴を開く
        field_page.show_history("E2E001")
        expect(field_page.history_modal).to_be_visible()

        # モーダルを閉じる
        field_page.close_history_modal()

        # モーダルが閉じていること
        expect(field_page.history_modal).not_to_be_visible()
