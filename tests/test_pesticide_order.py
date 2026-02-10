"""
農薬発注機能のテスト

テスト項目:
1. 発注リスト作成後、DB保存が動作するか
2. PDFダウンロードでPDFが生成されるか
3. 保存済み発注一覧で読み込み/削除が動作するか
"""

import pytest
import sys
import os
import tempfile
from pathlib import Path
import pandas as pd

# プロジェクトルートをパスに追加
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rotation_planner.common.db_access import (
    PesticideOrderRepository,
    PlanRepository,
    FieldRepository,
)
from rotation_planner.pesticide.ui import (
    save_order_to_db,
    load_saved_orders,
    load_order_from_db,
    delete_saved_order,
    process_order_db,
    generate_pdf_from_results,
)
from rotation_planner.pesticide.pdf_export import (
    generate_pesticide_order_pdf,
    check_pdf_support,
    REPORTLAB_AVAILABLE,
)
from rotation_planner.pesticide.calculator import calculate_pesticide_requirements


# =============================================================================
# テストデータ
# =============================================================================

# farmer_demo (user_id=3) のテスト用ユーザー状態
TEST_USER_STATE = {
    "user_id": 3,
    "username": "farmer_demo",
    "display_name": "デモ農家",
    "role": "farmer",
    "org_id": 1,
}

# サンプルの発注サマリーデータ
SAMPLE_SUMMARY_DF = pd.DataFrame({
    "農薬名": ["トップジンM水和剤", "スミチオン乳剤", "ダコニール1000"],
    "必要量": ["5.00", "3.50", "2.00"],
    "単位": ["L", "L", "L"],
    "対象作物": ["てんさい", "大豆", "春小麦"],
    "対象病害虫": ["苗立枯病", "アブラムシ", "赤さび病"],
})

# サンプルの月別詳細データ
SAMPLE_DETAIL_DF = pd.DataFrame({
    "月": [4, 5, 6],
    "作物": ["てんさい", "大豆", "春小麦"],
    "対象": ["苗立枯病", "アブラムシ", "赤さび病"],
    "農薬名": ["トップジンM水和剤", "スミチオン乳剤", "ダコニール1000"],
    "必要量": ["5.00L", "3.50L", "2.00L"],
    "面積(ha)": [10.0, 8.5, 5.0],
})


# =============================================================================
# DB保存テスト
# =============================================================================

class TestPesticideOrderDBSave:
    """農薬発注 DB保存テスト"""

    def test_save_order_to_db_success(self):
        """発注リストをDBに正常に保存できること"""
        order_name = "テスト発注_save_test"
        target_year = "R8"
        plan_id = 1
        area_unit = "ha"

        result = save_order_to_db(
            order_name=order_name,
            target_year=target_year,
            plan_id=plan_id,
            area_unit=area_unit,
            summary_df=SAMPLE_SUMMARY_DF,
            detail_df=SAMPLE_DETAIL_DF,
            user_state=TEST_USER_STATE
        )

        # 保存成功を確認
        assert "保存完了" in result or "ID" in result, f"保存失敗: {result}"

        # クリーンアップ: 保存した発注を削除
        orders = PesticideOrderRepository.get_orders(TEST_USER_STATE["user_id"])
        for order in orders:
            if order["name"] == order_name:
                PesticideOrderRepository.delete_order(order["id"])
                break

    def test_save_order_to_db_without_login(self):
        """未ログイン時は保存できないこと"""
        result = save_order_to_db(
            order_name="テスト発注",
            target_year="R8",
            plan_id=1,
            area_unit="ha",
            summary_df=SAMPLE_SUMMARY_DF,
            detail_df=SAMPLE_DETAIL_DF,
            user_state={}
        )

        assert "エラー" in result
        assert "ログイン" in result

    def test_save_order_to_db_without_name(self):
        """発注名なしでは保存できないこと"""
        result = save_order_to_db(
            order_name="",
            target_year="R8",
            plan_id=1,
            area_unit="ha",
            summary_df=SAMPLE_SUMMARY_DF,
            detail_df=SAMPLE_DETAIL_DF,
            user_state=TEST_USER_STATE
        )

        assert "エラー" in result
        assert "発注名" in result

    def test_save_order_to_db_without_data(self):
        """データなしでは保存できないこと"""
        result = save_order_to_db(
            order_name="テスト発注",
            target_year="R8",
            plan_id=1,
            area_unit="ha",
            summary_df=None,
            detail_df=None,
            user_state=TEST_USER_STATE
        )

        assert "エラー" in result
        assert "発注リスト" in result or "実行" in result


# =============================================================================
# PDF出力テスト
# =============================================================================

class TestPesticideOrderPDF:
    """農薬発注 PDF出力テスト"""

    @pytest.mark.skipif(not REPORTLAB_AVAILABLE, reason="reportlab not installed")
    def test_generate_pdf_success(self):
        """PDFが正常に生成されること"""
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            output_path = f.name

        try:
            result_path = generate_pesticide_order_pdf(
                summary_df=SAMPLE_SUMMARY_DF,
                detail_df=SAMPLE_DETAIL_DF,
                order_name="テスト発注",
                target_year="R8",
                output_path=output_path
            )

            # ファイルが生成されたか確認
            assert result_path == output_path
            assert os.path.exists(output_path)

            # ファイルサイズが0より大きいか確認（PDF生成成功の簡易チェック）
            file_size = os.path.getsize(output_path)
            assert file_size > 0, "PDFファイルが空です"

        finally:
            # クリーンアップ
            if os.path.exists(output_path):
                os.remove(output_path)

    @pytest.mark.skipif(not REPORTLAB_AVAILABLE, reason="reportlab not installed")
    def test_generate_pdf_from_results_success(self):
        """generate_pdf_from_results関数が正常に動作すること"""
        pdf_path, message = generate_pdf_from_results(
            summary_df=SAMPLE_SUMMARY_DF,
            detail_df=SAMPLE_DETAIL_DF,
            order_name="テスト発注",
            target_year="R8"
        )

        # PDFが生成されたか確認
        assert pdf_path is not None or "エラー" not in message
        if pdf_path:
            assert os.path.exists(pdf_path)
            os.remove(pdf_path)  # クリーンアップ

    def test_generate_pdf_from_results_without_data(self):
        """データなしではPDF生成エラーになること"""
        pdf_path, message = generate_pdf_from_results(
            summary_df=None,
            detail_df=None,
            order_name="テスト発注",
            target_year="R8"
        )

        assert pdf_path is None
        assert "エラー" in message

    def test_check_pdf_support(self):
        """PDF出力サポート状況が取得できること"""
        support = check_pdf_support()

        assert "reportlab_available" in support
        assert "japanese_font_available" in support
        assert "font_name" in support

        # reportlabがインストールされている場合の追加チェック
        if support["reportlab_available"]:
            assert support["font_name"] is not None


# =============================================================================
# 保存済み発注一覧テスト
# =============================================================================

class TestPesticideOrderList:
    """保存済み発注一覧テスト"""

    @pytest.fixture
    def saved_order(self):
        """テスト用の保存済み発注を作成"""
        order_data = {
            "name": "テスト発注_list_test",
            "target_year": "R8",
            "rotation_plan_id": 1,
            "area_unit": "ha",
            "order_data": {
                "summary": SAMPLE_SUMMARY_DF.to_dict("records"),
                "details": SAMPLE_DETAIL_DF.to_dict("records"),
            }
        }
        order_id = PesticideOrderRepository.create_order(
            TEST_USER_STATE["user_id"],
            order_data
        )
        yield order_id

        # クリーンアップ
        try:
            PesticideOrderRepository.delete_order(order_id)
        except Exception:
            pass

    def test_load_saved_orders(self, saved_order):
        """保存済み発注一覧が取得できること"""
        orders_df = load_saved_orders(TEST_USER_STATE)

        assert orders_df is not None
        assert not orders_df.empty
        assert "ID" in orders_df.columns
        assert "発注名" in orders_df.columns

        # テスト用発注が含まれているか確認
        order_names = orders_df["発注名"].tolist()
        assert "テスト発注_list_test" in order_names

    def test_load_saved_orders_without_login(self):
        """未ログイン時は空のDataFrameが返ること"""
        orders_df = load_saved_orders({})

        assert orders_df is not None
        assert orders_df.empty

    def test_load_order_from_db(self, saved_order):
        """保存済み発注を読み込めること"""
        # まず一覧を取得
        orders_df = load_saved_orders(TEST_USER_STATE)

        # テスト用発注の行を取得
        test_row_idx = orders_df[orders_df["発注名"] == "テスト発注_list_test"].index[0]

        # 読み込み
        summary_df, detail_df, message = load_order_from_db(
            orders_df=orders_df,
            selected_index=[test_row_idx],
            user_state=TEST_USER_STATE
        )

        assert "エラー" not in message
        assert summary_df is not None
        assert not summary_df.empty

    def test_delete_saved_order(self):
        """保存済み発注を削除できること"""
        # 削除用の発注を作成
        order_data = {
            "name": "テスト発注_delete_test",
            "target_year": "R8",
            "order_data": {}
        }
        order_id = PesticideOrderRepository.create_order(
            TEST_USER_STATE["user_id"],
            order_data
        )

        # 一覧を取得
        orders_df = load_saved_orders(TEST_USER_STATE)
        test_row_idx = orders_df[orders_df["発注名"] == "テスト発注_delete_test"].index[0]

        # 削除
        new_orders_df, message = delete_saved_order(
            orders_df=orders_df,
            selected_index=[test_row_idx],
            user_state=TEST_USER_STATE
        )

        assert "削除" in message
        # 削除後の一覧に含まれていないことを確認
        assert "テスト発注_delete_test" not in new_orders_df["発注名"].tolist()


# =============================================================================
# 発注計算テスト
# =============================================================================

class TestPesticideOrderCalculation:
    """農薬発注計算テスト"""

    def test_calculate_pesticide_requirements_basic(self):
        """農薬必要量計算の基本テスト"""
        # 輪作計画データ
        rotation_df = pd.DataFrame({
            "ほ場ID": ["F001", "F002"],
            "面積(ha)": [1.0, 2.0],
            "R8": ["てんさい", "大豆"],
        })

        # 防除マスタ
        master_df = pd.DataFrame({
            "crop": ["てんさい", "大豆"],
            "month": [4, 5],
            "period": ["播種前", "生育期"],
            "target": ["苗立枯病", "アブラムシ"],
            "pesticide_name": ["トップジンM水和剤", "スミチオン乳剤"],
            "dilution_rate": [1000, 1000],
            "amount_per_10a": [None, None],
            "unit": ["mL", "mL"],
        })

        summary_df, detail_df, message = calculate_pesticide_requirements(
            rotation_df=rotation_df,
            year_cols=["R8"],
            target_year="R8",
            master_df=master_df,
            area_unit="ha",
            inventory=None
        )

        # 結果確認
        if summary_df is not None:
            assert not summary_df.empty
            assert "農薬名" in summary_df.columns
        # マスタがマッチしない場合は警告が返る
        assert message is not None

    def test_process_order_db_without_plan(self):
        """輪作計画未選択時はエラーになること"""
        summary_df, detail_df, csv_path, message = process_order_db(
            plan_id=None,
            target_year="R8",
            area_unit="ha",
            user_state=TEST_USER_STATE
        )

        assert summary_df is None
        assert "エラー" in message
        assert "計画" in message


# =============================================================================
# エンドツーエンドテスト
# =============================================================================

class TestPesticideOrderE2E:
    """農薬発注のエンドツーエンドテスト"""

    def test_full_workflow(self):
        """発注リスト作成 → DB保存 → 読み込み → 削除 のフルワークフロー"""
        # 1. 発注リストを作成してDB保存
        order_name = "E2E_テスト発注"
        result = save_order_to_db(
            order_name=order_name,
            target_year="R8",
            plan_id=1,
            area_unit="ha",
            summary_df=SAMPLE_SUMMARY_DF,
            detail_df=SAMPLE_DETAIL_DF,
            user_state=TEST_USER_STATE
        )
        assert "保存完了" in result or "ID" in result

        # 2. 一覧から取得
        orders_df = load_saved_orders(TEST_USER_STATE)
        assert order_name in orders_df["発注名"].tolist()

        # 3. 読み込み
        test_row_idx = orders_df[orders_df["発注名"] == order_name].index[0]
        summary_df, detail_df, message = load_order_from_db(
            orders_df=orders_df,
            selected_index=[test_row_idx],
            user_state=TEST_USER_STATE
        )
        assert "エラー" not in message
        assert summary_df is not None

        # 4. 削除
        new_orders_df, message = delete_saved_order(
            orders_df=orders_df,
            selected_index=[test_row_idx],
            user_state=TEST_USER_STATE
        )
        assert "削除" in message
        assert order_name not in new_orders_df["発注名"].tolist()
