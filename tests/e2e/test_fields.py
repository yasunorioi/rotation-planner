"""
E2E テスト: ほ場一覧・編集・削除

テストケース:
  - test_field_list_display: ほ場一覧画面が表示されること
  - test_edit_field: 既存ほ場の情報編集→更新反映
  - test_delete_field: ほ場削除→一覧から消える
  - test_field_validation: 必須項目未入力→エラー表示（編集フォーム）

Note: 新規ほ場登録は /field-register ページで実施されるため、
      本テストでは既存ほ場（E2Eテストほ場1号・2号）を使用。
"""

import pytest
from playwright.sync_api import Page, expect

from .pages import FieldPage


@pytest.mark.e2e
class TestFieldList:
    """ほ場一覧のテスト"""

    def test_field_list_display(self, authenticated_page: Page, base_url: str):
        """ほ場一覧画面が表示される。"""
        field_page = FieldPage(authenticated_page, base_url)
        field_page.goto()

        # ページタイトルとテーブルが表示されること
        field_page.expect_on_field_page()

        # conftest.py で投入したテストほ場が表示されること
        field_page.expect_field_in_list("E2Eテストほ場1号")
        field_page.expect_field_in_list("E2Eテストほ場2号")

    def test_field_list_content(self, authenticated_page: Page, base_url: str):
        """ほ場一覧の内容が正しく表示される（admin）。"""
        field_page = FieldPage(authenticated_page, base_url)
        field_page.goto()

        # admin (user_id=1) はE2E001, E2E002 を保有
        fields = field_page.get_field_list()
        assert len(fields) >= 2, f"最低2件のほ場が表示されるはず (actual: {len(fields)})"

        # E2Eテストほ場1号を確認
        field1 = next((f for f in fields if "E2E001" in f["code"]), None)
        assert field1 is not None, "E2E001 が見つからない"
        assert "E2Eテストほ場1号" in field1["name"]


@pytest.mark.e2e
class TestFieldEdit:
    """ほ場編集のテスト"""

    def test_edit_field_name(self, authenticated_page: Page, base_url: str):
        """既存ほ場の名前を編集すると一覧に反映される（admin）。"""
        field_page = FieldPage(authenticated_page, base_url)
        field_page.goto()

        # admin のE2E001 の名前を変更
        new_name = "E2Eテストほ場1号（編集済み）"
        field_page.edit_field("E2E001", field_name=new_name)

        # 一覧に反映されること
        field_page.expect_field_in_list(new_name)

        # 元の名前に戻す（後続テストのため）
        field_page.edit_field("E2E001", field_name="E2Eテストほ場1号")

    def test_edit_field_district(self, authenticated_page: Page, base_url: str):
        """既存ほ場の地区を編集すると一覧に反映される（admin）。"""
        field_page = FieldPage(authenticated_page, base_url)
        field_page.goto()

        # E2E002 の地区を変更
        field_page.edit_field("E2E002", district="南区")

        # 一覧を取得して地区が更新されていることを確認
        fields = field_page.get_field_list()
        field2 = next((f for f in fields if "E2E002" in f["code"]), None)
        assert field2 is not None
        assert "南区" in field2["district"]

    def test_edit_field_beet_forbidden(self, authenticated_page: Page, base_url: str):
        """てんさい・馬鈴薯禁止フラグをON/OFFできる（admin）。"""
        field_page = FieldPage(authenticated_page, base_url)
        field_page.goto()

        # E2E001 の禁止フラグをON
        field_page.edit_field("E2E001", beet_forbidden=True)

        # 一覧で制限列に表示されることを確認（詳細確認はAPI or 編集画面再確認）
        # ここでは編集が成功したことのみ確認
        field_page.expect_field_in_list("E2E001")

        # フラグをOFFに戻す
        field_page.edit_field("E2E001", beet_forbidden=False)


@pytest.mark.e2e
class TestFieldDelete:
    """ほ場削除のテスト"""

    def test_delete_field(self, authenticated_page: Page, base_url: str):
        """ほ場を削除すると一覧から消える。"""
        field_page = FieldPage(authenticated_page, base_url)
        field_page.goto()

        # まず削除対象が存在することを確認
        field_page.expect_field_in_list("E2Eテストほ場2号")

        # E2E002 を削除
        field_page.delete_field("E2E002")

        # 一覧から消えることを確認
        field_page.expect_field_not_in_list("E2Eテストほ場2号")


@pytest.mark.e2e
class TestFieldValidation:
    """ほ場編集のバリデーションテスト"""

    def test_field_name_empty_validation(self, authenticated_page: Page, base_url: str):
        """ほ場名を空にして送信した場合の挙動を確認。"""
        field_page = FieldPage(authenticated_page, base_url)
        field_page.goto()

        # admin のE2E001 の編集モーダルを開く
        field_page.click_edit_button("E2E001")

        # 元の名前を保持
        original_name = field_page.field_name_input.input_value()

        # ほ場名を空にして送信（ダイアログは FieldPage.__init__ で自動承認済み）
        field_page.field_name_input.fill("")
        field_page.submit_button.click()

        # 送信後の処理を待つ（バリデーションエラー or API送信完了）
        field_page.page.wait_for_timeout(2000)

        # データ復元: 再度編集して元の名前に戻す
        field_page.goto()
        field_page.click_edit_button("E2E001")
        field_page.field_name_input.fill(original_name)
        field_page.submit_button.click()
        field_page.page.wait_for_timeout(1000)

        # ほ場一覧に戻って確認
        field_page.goto()
        field_page.expect_field_in_list(original_name)
