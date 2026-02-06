"""
農薬計算（calculator.py）の単体テスト

テスト対象: rotation_planner/pesticide/calculator.py
テストケース: PC-01 ~ PC-13 (P1)
設計書: docs/TEST_UNIT.md セクション3.5
"""
import pytest
import pandas as pd

from rotation_planner.pesticide.calculator import (
    convert_to_base_unit,
    convert_from_base_unit,
    normalize_crop,
    load_rotation_plan,
    load_inventory_csv,
    calculate_pesticide_requirements,
)


# ============================================================
# PC-01 ~ PC-04: convert_to_base_unit
# ============================================================

class TestConvertToBaseUnit:
    """convert_to_base_unit のテスト"""

    def test_pc01_ml_to_ml(self):
        """PC-01: mL→mL は値そのまま（100mL → 100.0）"""
        assert convert_to_base_unit(100, "mL") == 100.0

    def test_pc02_l_to_ml(self):
        """PC-02: L→mL は×1000（1L → 1000.0mL）"""
        assert convert_to_base_unit(1, "L") == 1000.0

    def test_pc03_kg_to_g(self):
        """PC-03: kg→g は×1000（1kg → 1000.0g）"""
        assert convert_to_base_unit(1, "kg") == 1000.0

    def test_pc04_unknown_unit(self):
        """PC-04: 不明単位 → 係数1.0でそのまま返る"""
        assert convert_to_base_unit(1, "不明") == 1.0


# ============================================================
# PC-05: convert_from_base_unit
# ============================================================

class TestConvertFromBaseUnit:
    """convert_from_base_unit のテスト"""

    def test_pc05_ml_to_l(self):
        """PC-05: 1000mL → 1.0L"""
        assert convert_from_base_unit(1000, "L") == 1.0


# ============================================================
# PC-06 ~ PC-08: normalize_crop
# ============================================================

class TestNormalizeCrop:
    """normalize_crop のテスト"""

    def test_pc06_tensai(self):
        """PC-06: "テンサイ" → "てんさい"（カタカナ→ひらがな正規化）"""
        assert normalize_crop("テンサイ") == "てんさい"

    def test_pc07_bareisho(self):
        """PC-07: "ばれいしょ" → "馬鈴薯"（ひらがな→漢字正規化）"""
        assert normalize_crop("ばれいしょ") == "馬鈴薯"

    def test_pc08_unknown_crop(self):
        """PC-08: 未知の作物 → そのまま返る"""
        assert normalize_crop("未知作物") == "未知作物"


# ============================================================
# PC-09 ~ PC-10: load_rotation_plan
# ============================================================

class TestLoadRotationPlan:
    """load_rotation_plan のテスト"""

    def test_pc09_valid_csv(self, temp_csv):
        """PC-09: 有効CSV → (DataFrame, year_cols, None)"""
        csv_content = (
            "ほ場名,面積(ha),R5,R6,R7\n"
            "A圃場,2.5,大豆,てんさい,春小麦\n"
            "B圃場,3.0,春小麦,大豆,てんさい\n"
        )
        path = temp_csv(csv_content, "rotation.csv")
        df, year_cols, msg = load_rotation_plan(path)

        assert df is not None
        assert isinstance(df, pd.DataFrame)
        assert len(year_cols) == 3  # R5, R6, R7
        assert msg is None

    def test_pc10_missing_file(self):
        """PC-10: 存在しないファイル → 例外発生"""
        with pytest.raises(Exception):
            load_rotation_plan("/nonexistent/path/missing.csv")


# ============================================================
# PC-11: load_inventory_csv
# ============================================================

class TestLoadInventoryCsv:
    """load_inventory_csv のテスト"""

    def test_pc11_valid_csv(self, temp_csv):
        """PC-11: 有効CSV → (Dict, "")"""
        csv_content = (
            "農薬名,在庫量,単位\n"
            "テスト農薬A,500,mL\n"
            "テスト農薬B,2,L\n"
        )
        path = temp_csv(csv_content, "inventory.csv")
        inventory, msg = load_inventory_csv(path)

        assert isinstance(inventory, dict)
        assert len(inventory) == 2
        # テスト農薬A: 500mL → 基準単位500.0
        assert inventory["テスト農薬A"][0] == 500.0
        assert inventory["テスト農薬A"][1] == "mL"
        # テスト農薬B: 2L → 基準単位2000.0mL
        assert inventory["テスト農薬B"][0] == 2000.0
        assert inventory["テスト農薬B"][1] == "L"


# ============================================================
# PC-12 ~ PC-13: calculate_pesticide_requirements
# ============================================================

class TestCalculatePesticideRequirements:
    """calculate_pesticide_requirements のテスト"""

    def test_pc12_normal_calculation(self):
        """PC-12: 正常計算 → summary_df, detail_df が返る"""
        rotation_df = pd.DataFrame({
            "ほ場名": ["A圃場"],
            "面積(ha)": [2.5],
            "R7": ["てんさい"],
        })
        year_cols = ["R7"]
        target_year = "R7"

        master_df = pd.DataFrame({
            "crop": ["てんさい"],
            "pesticide_name": ["テスト農薬A"],
            "dilution_rate": [1000],
            "amount_per_10a": [pd.NA],
            "unit": ["mL"],
            "month": [6],
            "target": ["テスト病害"],
        })

        summary_df, detail_df, message = calculate_pesticide_requirements(
            rotation_df, year_cols, target_year, master_df, area_unit="ha"
        )

        assert summary_df is not None
        assert isinstance(summary_df, pd.DataFrame)
        assert len(summary_df) > 0
        assert detail_df is not None
        assert isinstance(detail_df, pd.DataFrame)
        assert "✅" in message

    def test_pc13_empty_master(self):
        """PC-13: マスタに該当作物なし → 警告メッセージ"""
        rotation_df = pd.DataFrame({
            "ほ場名": ["A圃場"],
            "面積(ha)": [2.5],
            "R7": ["てんさい"],
        })
        year_cols = ["R7"]
        target_year = "R7"

        master_df = pd.DataFrame(columns=[
            "crop", "pesticide_name", "dilution_rate",
            "amount_per_10a", "unit", "month", "target",
        ])

        summary_df, detail_df, message = calculate_pesticide_requirements(
            rotation_df, year_cols, target_year, master_df, area_unit="ha"
        )

        assert summary_df is None
        assert "警告" in message
