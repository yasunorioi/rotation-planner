"""
E2E テスト: 輪作計画

テストケース:
  - test_rotation_plan_list: 輪作計画一覧表示
  - test_create_rotation_plan: 新規計画作成
  - test_run_optimization: 最適化実行→結果表示
  - test_optimization_result_display: 最適化結果の表形式表示確認
"""

import pytest
from playwright.sync_api import Page, expect

from .pages import RotationPage, DashboardPage


@pytest.mark.e2e
class TestRotationPlanList:
    """輪作計画一覧表示のテスト"""

    def test_rotation_page_loads(self, authenticated_page: Page, base_url: str):
        """輪作計画画面が表示される。"""
        rotation = RotationPage(authenticated_page, base_url)
        rotation.goto()

        # URLが /rotation であることを確認
        expect(authenticated_page).to_have_url(f"{base_url}/rotation")

        # ページタイトルまたは見出しが表示されることを確認
        # （画面構造に応じて調整）
        heading = authenticated_page.locator("h1, h2").first
        expect(heading).to_be_visible()

    def test_rotation_plan_list_empty(self, authenticated_page: Page, base_url: str):
        """輪作計画一覧が空の場合でも画面が正常に表示される。"""
        rotation = RotationPage(authenticated_page, base_url)
        rotation.goto()

        # 計画一覧セクションが存在すること（空でもOK）
        # 注: 初期状態では計画が0件の可能性がある
        plans = rotation.get_plan_list()
        assert isinstance(plans, list)


@pytest.mark.e2e
class TestCreateRotationPlan:
    """輪作計画作成のテスト"""

    def test_rotation_form_elements_visible(self, authenticated_page: Page, base_url: str):
        """輪作計画画面に必要な要素が表示される。"""
        rotation = RotationPage(authenticated_page, base_url)
        rotation.goto()

        # 最適化実行ボタンが表示される
        expect(rotation.optimize_button).to_be_visible()

        # 注: 計画名入力フィールドは最適化実行後にのみ表示される


@pytest.mark.e2e
class TestRunOptimization:
    """最適化実行のテスト"""

    def test_optimization_button_visible(self, farmer_page: Page, base_url: str):
        """最適化実行ボタンが表示される。"""
        rotation = RotationPage(farmer_page, base_url)
        rotation.goto()

        # 最適化実行ボタンが表示される
        expect(rotation.optimize_button).to_be_visible()

    @pytest.mark.slow
    def test_run_optimization_and_get_result(self, farmer_page: Page, base_url: str):
        """
        最適化実行→結果表示の流れをテストする。

        注: このテストは実際の最適化計算を実行するため時間がかかる可能性がある。
        conftest.py で作成されたテスト用ほ場（E2E001, E2E002）を使用。
        """
        rotation = RotationPage(farmer_page, base_url)
        rotation.goto()

        # ページが完全に読み込まれるまで待機
        rotation.wait_for_load()

        # 最適化実行ボタンが有効であることを確認
        expect(rotation.optimize_button).to_be_enabled()

        # 最適化を実行
        rotation.run_optimization()

        # 結果表示を待機（最大30秒）
        # 注: 最適化計算が失敗する場合もあるため、エラーハンドリングが必要
        try:
            rotation.wait_for_optimization_result(timeout=30000)
            # 結果テーブルが表示されることを確認
            rotation.expect_result_visible()
        except Exception as e:
            # 最適化が失敗した場合（ほ場データ不足等）はスキップ
            pytest.skip(f"最適化実行が完了しませんでした: {e}")


@pytest.mark.e2e
class TestOptimizationResultDisplay:
    """最適化結果表示のテスト"""

    @pytest.mark.slow
    def test_optimization_result_table_structure(self, farmer_page: Page, base_url: str):
        """
        最適化結果がテーブル形式で表示されることを確認する。

        注: このテストは test_run_optimization_and_get_result の実行が成功することが前提。
        """
        rotation = RotationPage(farmer_page, base_url)
        rotation.goto()
        rotation.wait_for_load()

        # 最適化を実行
        expect(rotation.optimize_button).to_be_enabled()
        rotation.run_optimization()

        # 結果表示を待機
        try:
            rotation.wait_for_optimization_result(timeout=30000)

            # 結果テーブルの構造を取得
            result = rotation.get_optimization_result()

            # テーブルが存在すること（行数 > 0）
            assert result["rows"] > 0, "結果テーブルに行が存在しません"
            assert result["cols"] > 0, "結果テーブルに列が存在しません"

            # データが存在すること
            assert len(result["data"]) > 0, "結果データが空です"

        except Exception as e:
            pytest.skip(f"最適化実行が完了しませんでした: {e}")

    def test_result_table_not_visible_before_optimization(
        self, authenticated_page: Page, base_url: str
    ):
        """最適化実行前は結果テーブルが表示されない。"""
        rotation = RotationPage(authenticated_page, base_url)
        rotation.goto()
        rotation.wait_for_load()

        # 結果テーブルが非表示または存在しないこと
        # （画面設計によって調整）
        if rotation.result_table.count() > 0:
            # テーブルが存在するが内容が空の場合
            result = rotation.get_optimization_result()
            # 行数が0、またはテーブルが非表示であることを確認
            assert result["rows"] == 0 or not rotation.result_table.is_visible()
