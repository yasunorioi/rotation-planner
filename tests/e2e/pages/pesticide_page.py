"""
PesticidePage — 防除マスタページの Page Object
"""

from playwright.sync_api import Page, expect

from .base_page import BasePage


class PesticidePage(BasePage):
    """防除マスタページの操作を提供する。"""

    PATH = "/pesticide-masters"

    def __init__(self, page: Page, base_url: str = ""):
        super().__init__(page, base_url)
        # Locators
        self.page_title = page.locator(".page-header h1")
        self.new_pesticide_button = page.get_by_role("button", name="+ 新規農薬")
        self.crop_select = page.locator(".crop-select")
        self.data_table = page.locator(".data-table")
        self.modal = page.locator(".modal-overlay")
        self.modal_title = page.locator(".modal h2")

        # Form buttons (モーダル内)
        self.submit_button = page.locator('.modal button[type="submit"]')
        self.cancel_button = page.locator('.modal button.btn-secondary')

    def goto(self) -> "PesticidePage":
        """防除マスタページに遷移する。"""
        self.navigate_to(self.PATH)
        return self

    def navigate_to_pesticides(self) -> None:
        """防除マスタ画面へ遷移する。"""
        self.goto()
        self.wait_for_load()

    def get_pesticide_list(self) -> list[str]:
        """農薬一覧をテーブルから取得する（農薬名のリスト）。"""
        # テーブルの1列目（農薬名）を取得
        rows = self.data_table.locator("tbody tr")
        count = rows.count()
        if count == 0:
            return []

        names = []
        for i in range(count):
            row = rows.nth(i)
            name = row.locator("td").first.text_content()
            names.append(name)
        return names

    def add_pesticide(
        self,
        name: str,
        target_crop: str = "",
        category: str = "",
        manufacturer: str = ""
    ) -> None:
        """新規農薬を登録する。"""
        # 新規農薬ボタンをクリック
        self.new_pesticide_button.click()

        # モーダルが表示されるのを待つ
        expect(self.modal).to_be_visible()
        expect(self.modal_title).to_have_text("新規農薬")

        # モーダルのアニメーション完了を待つ
        self.page.wait_for_timeout(300)

        # フォーム入力（モーダル内のinputを順序で取得）
        # PesticideMasters.jsx: 農薬名、対象作物、カテゴリ、メーカー、有効成分、使用時期、散布方法の順
        modal_text_inputs = self.modal.locator('input[type="text"]')
        modal_text_inputs.nth(0).fill(name)  # 農薬名
        if target_crop:
            modal_text_inputs.nth(1).fill(target_crop)  # 対象作物
        if category:
            self.modal.locator('select').first.select_option(category)  # カテゴリ
        if manufacturer:
            modal_text_inputs.nth(2).fill(manufacturer)  # メーカー

        # 送信
        self.submit_button.click()

        # API処理とモーダルが閉じるのを待つ（タイムアウト延長）
        expect(self.modal).not_to_be_visible(timeout=10000)

    def edit_pesticide(
        self,
        pesticide_name: str,
        new_name: str = None,
        new_crop: str = None,
        new_category: str = None,
        new_manufacturer: str = None
    ) -> None:
        """既存農薬の情報を編集する。"""
        # テーブルから該当行を探して編集ボタンをクリック
        row = self._find_pesticide_row(pesticide_name)
        if row is None:
            raise ValueError(f"農薬 '{pesticide_name}' が見つかりません")

        edit_button = row.locator('button.btn-icon').first  # ✏️ボタン
        edit_button.click()

        # モーダルが表示されるのを待つ
        expect(self.modal).to_be_visible()
        expect(self.modal_title).to_have_text("農薬編集")

        # モーダルのアニメーション完了を待つ
        self.page.wait_for_timeout(300)

        # フォーム更新（モーダル内のinputを順序で取得）
        modal_text_inputs = self.modal.locator('input[type="text"]')
        if new_name is not None:
            modal_text_inputs.nth(0).fill(new_name)  # 農薬名
        if new_crop is not None:
            modal_text_inputs.nth(1).fill(new_crop)  # 対象作物
        if new_category is not None:
            self.modal.locator('select').first.select_option(new_category)  # カテゴリ
        if new_manufacturer is not None:
            modal_text_inputs.nth(2).fill(new_manufacturer)  # メーカー

        # 送信
        self.submit_button.click()

        # API処理とモーダルが閉じるのを待つ（タイムアウト延長）
        expect(self.modal).not_to_be_visible(timeout=10000)

    def delete_pesticide(self, pesticide_name: str) -> None:
        """農薬を削除する（確認ダイアログ付き）。"""
        # テーブルから該当行を探して削除ボタンをクリック
        row = self._find_pesticide_row(pesticide_name)
        if row is None:
            raise ValueError(f"農薬 '{pesticide_name}' が見つかりません")

        delete_button = row.locator('button.btn-danger')  # 🗑️ボタン

        # confirm ダイアログを自動承認
        self.page.on("dialog", lambda dialog: dialog.accept())
        delete_button.click()

        # 削除が反映されるのを待つ（ページリロード or テーブル更新）
        self.page.wait_for_timeout(500)

    def search_pesticide(self, crop_name: str) -> None:
        """作物名で検索する（作物フィルタを使用）。"""
        self.crop_select.select_option(crop_name)
        # テーブル更新を待つ
        self.page.wait_for_timeout(500)

    def expect_pesticide_in_list(self, name: str) -> None:
        """指定した農薬名が一覧に存在することを検証する。"""
        pesticides = self.get_pesticide_list()
        assert name in pesticides, f"農薬 '{name}' が一覧に見つかりません。一覧: {pesticides}"

    def expect_pesticide_not_in_list(self, name: str) -> None:
        """指定した農薬名が一覧に存在しないことを検証する。"""
        pesticides = self.get_pesticide_list()
        assert name not in pesticides, f"農薬 '{name}' が一覧に残っています。一覧: {pesticides}"

    def expect_on_pesticide_page(self) -> None:
        """防除マスタページにいることを検証する。"""
        expect(self.page_title).to_contain_text("💊 防除マスタ")
        expect(self.new_pesticide_button).to_be_visible()

    def has_data_or_empty(self) -> bool:
        """テーブルまたは空状態が表示されているか確認する。"""
        # テーブルが表示されているか
        if self.data_table.is_visible():
            return True
        # 空状態メッセージが表示されているか
        if self.page.get_by_text("農薬が登録されていません").is_visible():
            return True
        return False

    def _find_pesticide_row(self, pesticide_name: str):
        """テーブルから農薬名に該当する行を探す。"""
        rows = self.data_table.locator("tbody tr")
        count = rows.count()
        for i in range(count):
            row = rows.nth(i)
            name_cell = row.locator("td").first
            if name_cell.text_content() == pesticide_name:
                return row
        return None
