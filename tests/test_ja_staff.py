"""
JA職員向け機能のテスト
"""
import pytest
import pandas as pd
from unittest.mock import patch, MagicMock


class TestJAStaffUI:
    """JA職員向けUI関数のテスト"""

    def test_get_all_farmers_orders_without_org_id(self):
        """組織IDなしで呼び出した場合"""
        from rotation_planner.pesticide.ui import get_all_farmers_orders
        result = get_all_farmers_orders(None)
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 0

    def test_get_aggregate_pesticide_orders_without_org_id(self):
        """組織IDなしで呼び出した場合"""
        from rotation_planner.pesticide.ui import get_aggregate_pesticide_orders
        result = get_aggregate_pesticide_orders(None)
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 0

    def test_get_all_farmers_orders_returns_dataframe(self):
        """DataFrameを返すことを確認"""
        from rotation_planner.pesticide.ui import get_all_farmers_orders
        result = get_all_farmers_orders(1)
        assert isinstance(result, pd.DataFrame)
        expected_columns = ['農家名', '発注日', '農薬名', '数量', '単位', '状態']
        for col in expected_columns:
            assert col in result.columns

    def test_get_aggregate_pesticide_orders_returns_dataframe(self):
        """DataFrameを返すことを確認"""
        from rotation_planner.pesticide.ui import get_aggregate_pesticide_orders
        result = get_aggregate_pesticide_orders(1)
        assert isinstance(result, pd.DataFrame)
        expected_columns = ['農薬名', '総必要量', '単位', '発注農家数']
        for col in expected_columns:
            assert col in result.columns


class TestJAStaffRepository:
    """JAStaffRepositoryのテスト"""

    def test_get_all_farmers_returns_list(self):
        """農家一覧がリストで返ることを確認"""
        from rotation_planner.common.db_access import JAStaffRepository
        result = JAStaffRepository.get_all_farmers(org_id=1)
        assert isinstance(result, list)

    def test_get_all_fields_returns_list(self):
        """ほ場一覧がリストで返ることを確認"""
        from rotation_planner.common.db_access import JAStaffRepository
        result = JAStaffRepository.get_all_fields(org_id=1)
        assert isinstance(result, list)

    def test_get_orders_by_org_returns_list(self):
        """組織内発注一覧がリストで返ることを確認"""
        from rotation_planner.common.db_access import JAStaffRepository
        result = JAStaffRepository.get_orders_by_org(org_id=1)
        assert isinstance(result, list)

    def test_get_aggregate_orders_by_org_returns_list(self):
        """農薬別集計がリストで返ることを確認"""
        from rotation_planner.common.db_access import JAStaffRepository
        result = JAStaffRepository.get_aggregate_orders_by_org(org_id=1)
        assert isinstance(result, list)

    def test_get_aggregate_stats_returns_dict(self):
        """組織統計が辞書で返ることを確認"""
        from rotation_planner.common.db_access import JAStaffRepository
        result = JAStaffRepository.get_aggregate_stats(org_id=1)
        assert isinstance(result, dict)
        assert 'farmer_count' in result
        assert 'field_count' in result
        assert 'total_area_ha' in result


class TestYearUtils:
    """年度ユーティリティのテスト"""

    def test_get_current_fiscal_year_format(self):
        """現在の農業年度のフォーマット確認"""
        from rotation_planner.common.year_utils import get_current_fiscal_year
        result = get_current_fiscal_year()
        assert result.startswith("R")
        assert result[1:].isdigit()

    def test_get_default_target_year_format(self):
        """デフォルト対象年度のフォーマット確認"""
        from rotation_planner.common.year_utils import get_default_target_year
        result = get_default_target_year()
        assert result.startswith("R")

    def test_generate_year_choices_returns_list(self):
        """年度選択肢がリストで返ることを確認"""
        from rotation_planner.common.year_utils import generate_year_choices
        result = generate_year_choices()
        assert isinstance(result, list)
        assert len(result) > 0
        assert all(y.startswith("R") for y in result)

    def test_reiwa_to_western_conversion(self):
        """令和→西暦変換"""
        from rotation_planner.common.year_utils import reiwa_to_western
        assert reiwa_to_western("R8") == 2026
        assert reiwa_to_western("R1") == 2019
        assert reiwa_to_western("8") == 2026

    def test_western_to_reiwa_conversion(self):
        """西暦→令和変換"""
        from rotation_planner.common.year_utils import western_to_reiwa
        assert western_to_reiwa(2026) == "R8"
        assert western_to_reiwa(2019) == "R1"

    def test_get_fiscal_year_for_date_march(self):
        """3月は前年度"""
        from rotation_planner.common.year_utils import get_fiscal_year_for_date
        from datetime import datetime
        result = get_fiscal_year_for_date(datetime(2026, 3, 31))
        assert result == "R7"

    def test_get_fiscal_year_for_date_april(self):
        """4月は新年度"""
        from rotation_planner.common.year_utils import get_fiscal_year_for_date
        from datetime import datetime
        result = get_fiscal_year_for_date(datetime(2026, 4, 1))
        assert result == "R8"

    def test_generate_year_choices_with_offset(self):
        """オフセット指定での年度選択肢生成"""
        from rotation_planner.common.year_utils import generate_year_choices
        result = generate_year_choices(start_offset=-1, end_offset=1)
        assert len(result) == 3  # -1, 0, +1


class TestJAStaffUIModule:
    """ja_staff_ui.pyモジュールのテスト"""

    def test_load_farmers_list_without_state(self):
        """状態なしで農家一覧読み込み"""
        from rotation_planner.pesticide.ja_staff_ui import load_farmers_list
        result = load_farmers_list(None)
        assert isinstance(result, pd.DataFrame)

    def test_load_farmers_list_without_org_id(self):
        """org_idなしで農家一覧読み込み"""
        from rotation_planner.pesticide.ja_staff_ui import load_farmers_list
        result = load_farmers_list({})
        assert isinstance(result, pd.DataFrame)

    def test_load_farmers_orders_without_state(self):
        """状態なしで発注状況読み込み"""
        from rotation_planner.pesticide.ja_staff_ui import load_farmers_orders
        result = load_farmers_orders(None, None, None)
        assert isinstance(result, pd.DataFrame)

    def test_load_aggregate_orders_without_state(self):
        """状態なしで集計読み込み"""
        from rotation_planner.pesticide.ja_staff_ui import load_aggregate_orders
        result = load_aggregate_orders(None, None)
        assert isinstance(result, pd.DataFrame)

    def test_export_aggregate_csv_without_data(self):
        """データなしでCSVエクスポート"""
        from rotation_planner.pesticide.ja_staff_ui import export_aggregate_csv
        result, message = export_aggregate_csv(None, None)
        assert result is None
        assert "エラー" in message

    def test_export_aggregate_csv_with_empty_dataframe(self):
        """空DataFrameでCSVエクスポート"""
        from rotation_planner.pesticide.ja_staff_ui import export_aggregate_csv
        result, message = export_aggregate_csv(None, pd.DataFrame())
        assert result is None
        assert "エラー" in message
