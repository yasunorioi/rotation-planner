"""
FieldPage — ほ場一覧ページの Page Object

Wave2 で足軽2号が拡充。
"""

from playwright.sync_api import Page, expect

from .base_page import BasePage


class FieldPage(BasePage):
    """ほ場一覧ページの操作を提供する。"""

    PATH = "/fields"

    def __init__(self, page: Page, base_url: str = ""):
        super().__init__(page, base_url)
        # ダイアログ（alert/confirm）を自動承認（セッション全体で1回だけ登録）
        page.on("dialog", lambda dialog: dialog.accept())
        # Locators
        self.page_title = page.locator("h1")
        self.data_table = page.locator("table.data-table")
        self.add_field_button = page.get_by_role("button", name="+ ほ場登録")

        # フォームロケータ
        self.modal = page.locator(".modal")
        # フォーム内の input を .form-group から辿る
        self.field_name_input = page.locator(".form-group:has-text('ほ場名') input")
        self.district_input = page.locator(".form-group:has-text('地区') input")
        self.area_input = page.locator(".form-group:has-text('面積') input")
        self.beet_forbidden_checkbox = page.locator(".form-group.checkbox input[type='checkbox']")
        self.submit_button = page.get_by_role("button", name="更新")
        self.cancel_button = page.get_by_role("button", name="キャンセル")

        # 作付履歴モーダルロケータ
        self.history_modal = page.locator(".modal-lg")
        self.history_modal_title = page.locator("h2", has_text="作付履歴")
        # 履歴テーブルは thead に「作物」ヘッダーを持つテーブル（一括登録テーブルと区別）
        self.history_table = self.history_modal.locator("table.data-table:has(thead:has-text('作物'))")
        self.close_history_button = page.get_by_role("button", name="閉じる")

    def goto(self) -> "FieldPage":
        """ほ場一覧ページに遷移する。"""
        self.navigate_to(self.PATH)
        return self

    def expect_on_field_page(self) -> None:
        """ほ場一覧ページにいることを検証する。"""
        expect(self.page_title).to_have_text("🗺️ ほ場一覧")
        expect(self.data_table).to_be_visible()

    def get_field_list(self) -> list[dict]:
        """
        ほ場一覧を取得する（通常表示モード前提）。

        Returns:
            list[dict]: [{"code": "...", "name": "...", "area": "..."}, ...]
        """
        # テーブルが読み込まれるまで待機
        self.page.wait_for_load_state("networkidle")

        rows = self.data_table.locator("tbody tr").all()
        fields = []
        for row in rows:
            cells = row.locator("td").all()
            # 通常表示は7列（checkbox, code, name, district, area, restriction, actions）
            if len(cells) >= 7:
                fields.append({
                    "code": cells[1].inner_text(),
                    "name": cells[2].inner_text(),
                    "district": cells[3].inner_text(),
                    "area": cells[4].inner_text(),
                })
        return fields

    def expect_field_in_list(self, name: str) -> None:
        """ほ場が一覧に存在することを確認する。"""
        expect(self.data_table.locator("tbody")).to_contain_text(name)

    def expect_field_not_in_list(self, name: str) -> None:
        """ほ場が一覧にないことを確認する。"""
        expect(self.data_table.locator("tbody")).not_to_contain_text(name)

    def click_edit_button(self, field_code: str) -> None:
        """指定コードのほ場の編集ボタンをクリックする。"""
        # コードセルを含む行を探し、その行の編集ボタンをクリック
        row = self.data_table.locator(f"tbody tr:has-text('{field_code}')").first
        row.get_by_role("button", name="✏️").click()
        expect(self.modal).to_be_visible()

    def edit_field(self, field_code: str, **kwargs) -> None:
        """
        ほ場を編集する。

        Args:
            field_code: 編集対象のほ場コード
            **kwargs: 編集するフィールド (field_name, district, beet_forbidden)
        """
        self.click_edit_button(field_code)

        if "field_name" in kwargs:
            self.field_name_input.fill(kwargs["field_name"])
        if "district" in kwargs:
            self.district_input.fill(kwargs["district"])
        if "beet_forbidden" in kwargs:
            if kwargs["beet_forbidden"]:
                self.beet_forbidden_checkbox.check()
            else:
                self.beet_forbidden_checkbox.uncheck()

        self.submit_button.click()
        expect(self.modal).not_to_be_visible(timeout=5000)

    def click_delete_button(self, field_code: str) -> None:
        """指定コードのほ場の削除ボタンをクリックする。"""
        row = self.data_table.locator(f"tbody tr:has-text('{field_code}')").first
        row.get_by_role("button", name="🗑️").click()

    def delete_field(self, field_code: str) -> None:
        """ほ場を削除する（confirm自動承認）。"""
        self.click_delete_button(field_code)
        # 削除後は一覧から消えることを待機
        self.page.wait_for_timeout(500)

    def show_history(self, field_code: str) -> None:
        """指定コードのほ場の作付履歴モーダルを開く。"""
        row = self.data_table.locator(f"tbody tr:has-text('{field_code}')").first
        row.get_by_role("button", name="📅").click()
        expect(self.history_modal).to_be_visible()
        expect(self.history_modal_title).to_be_visible()

    def get_history_list(self) -> list[dict]:
        """
        作付履歴モーダル内の履歴一覧を取得する。

        Returns:
            list[dict]: [{"year": "2023年", "crop": "だいず"}, ...]
        """
        rows = self.history_table.locator("tbody tr").all()
        history = []
        for row in rows:
            cells = row.locator("td").all()
            if len(cells) >= 2:
                history.append({
                    "year": cells[0].inner_text(),
                    "crop": cells[1].inner_text(),
                })
        return history

    def add_bulk_history(self, year_crop_map: dict) -> None:
        """
        作付履歴モーダル内の一括登録テーブルから履歴を登録する。

        Args:
            year_crop_map: {2023: "だいず", 2024: "小麦", ...}
        """
        # 一括登録テーブルは history_modal 内の最初のテーブル
        bulk_table = self.history_modal.locator("table.data-table").first

        for year, crop in year_crop_map.items():
            # 年度ヘッダーからインデックスを特定
            th_elements = bulk_table.locator("thead th").all()
            col_index = None
            for i, th in enumerate(th_elements):
                if f"{year}年" in th.inner_text():
                    col_index = i
                    break

            if col_index is not None:
                # 該当列の select 要素に値をセット
                select = bulk_table.locator(f"tbody tr td:nth-child({col_index + 1}) select")
                select.select_option(label=crop)

        # 一括登録ボタンをクリック（ダイアログは __init__ で自動承認済み）
        self.page.get_by_role("button", name="一括登録").click()
        self.page.wait_for_timeout(2000)

    def expect_history_entry(self, year: str, crop: str) -> None:
        """
        作付履歴モーダル内の履歴テーブルに指定エントリが存在することを確認する。

        Args:
            year: 年度（例: "2023年" or "2023"）
            crop: 作物名
        """
        year_str = f"{year}年" if not year.endswith("年") else year
        expect(self.history_table.locator("tbody")).to_contain_text(year_str)
        expect(self.history_table.locator("tbody")).to_contain_text(crop)

    def close_history_modal(self) -> None:
        """作付履歴モーダルを閉じる。"""
        self.close_history_button.click()
        expect(self.history_modal).not_to_be_visible()
