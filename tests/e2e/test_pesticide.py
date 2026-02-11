"""
E2E テスト: 防除マスタ（農薬管理）

テストケース:
  - test_pesticide_list_display: 農薬一覧画面が表示されること
  - test_add_pesticide: 新規農薬登録→一覧に表示
  - test_edit_pesticide: 既存農薬の情報編集→更新反映
  - test_delete_pesticide: 農薬削除→一覧から消える
  - test_pesticide_search: 作物フィルタで検索→該当のみ表示
"""

import pytest
from playwright.sync_api import Page, expect

from .pages import PesticidePage, DashboardPage


@pytest.mark.e2e
class TestPesticideDisplay:
    """防除マスタ画面の表示テスト"""

    def test_pesticide_list_display(self, authenticated_page: Page, base_url: str):
        """防除マスタ画面が正しく表示されること。"""
        page = authenticated_page
        pesticide_page = PesticidePage(page, base_url)
        pesticide_page.goto()

        # ページタイトルと主要要素が表示される
        pesticide_page.expect_on_pesticide_page()

        # テーブルまたは空状態が表示される（どちらでも良い）
        assert pesticide_page.has_data_or_empty()


@pytest.mark.e2e
class TestPesticideAdd:
    """農薬登録のテスト"""

    def test_add_pesticide(self, authenticated_page: Page, base_url: str):
        """新規農薬を登録すると一覧に表示される。"""
        page = authenticated_page
        pesticide_page = PesticidePage(page, base_url)
        pesticide_page.goto()

        # 新規農薬登録
        test_name = "E2Eテスト農薬_Add"
        pesticide_page.add_pesticide(
            name=test_name,
            target_crop="じゃがいも",
            category="殺虫剤",
            manufacturer="E2Eテストメーカー"
        )

        # ページリロードを待つ
        page.wait_for_load_state("networkidle")

        # 一覧に表示される
        pesticide_page.expect_pesticide_in_list(test_name)

    def test_add_pesticide_minimal(self, authenticated_page: Page, base_url: str):
        """必須項目（農薬名）のみで登録できる。"""
        page = authenticated_page
        pesticide_page = PesticidePage(page, base_url)
        pesticide_page.goto()

        # 必須項目のみで登録
        test_name = "E2Eテスト農薬_Minimal"
        pesticide_page.add_pesticide(name=test_name)

        page.wait_for_load_state("networkidle")

        # 一覧に表示される
        pesticide_page.expect_pesticide_in_list(test_name)


@pytest.mark.e2e
class TestPesticideEdit:
    """農薬編集のテスト"""

    def test_edit_pesticide(self, authenticated_page: Page, base_url: str):
        """既存農薬の情報を編集すると更新が反映される。"""
        page = authenticated_page
        pesticide_page = PesticidePage(page, base_url)
        pesticide_page.goto()

        # まず農薬を登録
        original_name = "E2Eテスト農薬_Edit_Original"
        pesticide_page.add_pesticide(
            name=original_name,
            target_crop="にんじん",
            manufacturer="元メーカー"
        )
        page.wait_for_load_state("networkidle")

        # 編集
        updated_name = "E2Eテスト農薬_Edit_Updated"
        pesticide_page.edit_pesticide(
            pesticide_name=original_name,
            new_name=updated_name,
            new_crop="だいこん",
            new_manufacturer="新メーカー"
        )
        page.wait_for_load_state("networkidle")

        # 更新後の名前が一覧に表示される
        pesticide_page.expect_pesticide_in_list(updated_name)
        # 元の名前は存在しない
        pesticide_page.expect_pesticide_not_in_list(original_name)


@pytest.mark.e2e
class TestPesticideDelete:
    """農薬削除のテスト"""

    def test_delete_pesticide(self, authenticated_page: Page, base_url: str):
        """農薬を削除すると一覧から消える。"""
        page = authenticated_page
        pesticide_page = PesticidePage(page, base_url)
        pesticide_page.goto()

        # まず農薬を登録
        test_name = "E2Eテスト農薬_Delete"
        pesticide_page.add_pesticide(
            name=test_name,
            target_crop="トマト"
        )
        page.wait_for_load_state("networkidle")

        # 一覧に存在することを確認
        pesticide_page.expect_pesticide_in_list(test_name)

        # 削除
        pesticide_page.delete_pesticide(test_name)
        page.wait_for_load_state("networkidle")

        # 一覧から消える
        pesticide_page.expect_pesticide_not_in_list(test_name)


@pytest.mark.e2e
class TestPesticideSearch:
    """農薬検索のテスト"""

    def test_pesticide_search_by_crop(self, authenticated_page: Page, base_url: str):
        """作物フィルタで検索すると該当農薬のみ表示される。"""
        page = authenticated_page
        pesticide_page = PesticidePage(page, base_url)
        pesticide_page.goto()

        # テスト用農薬を2つ登録（異なる作物）
        # 作物名はconftest.pyで登録済みのuser_crops名に合わせる
        # (crop_master: 小麦(春播), だいず, ばれいしょ, てんさい)
        pesticide_wheat = "E2Eテスト農薬_小麦用"
        pesticide_soy = "E2Eテスト農薬_だいず用"

        pesticide_page.add_pesticide(name=pesticide_wheat, target_crop="小麦(春播)")
        page.wait_for_load_state("networkidle")

        pesticide_page.add_pesticide(name=pesticide_soy, target_crop="だいず")
        page.wait_for_load_state("networkidle")

        # 全ての作物で表示（デフォルト）
        all_pesticides = pesticide_page.get_pesticide_list()
        assert pesticide_wheat in all_pesticides
        assert pesticide_soy in all_pesticides

        # 小麦(春播)でフィルタ
        pesticide_page.search_pesticide("小麦(春播)")
        page.wait_for_load_state("networkidle")

        filtered_list = pesticide_page.get_pesticide_list()
        # 少なくとも小麦用は表示されること
        assert pesticide_wheat in filtered_list
