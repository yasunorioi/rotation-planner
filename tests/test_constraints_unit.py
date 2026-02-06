"""
constraints.py 単体テスト（CN-01 ~ CN-18）

対象: rotation_planner/app/constraints.py
テストID: CN-01 ~ CN-18
"""

import pytest
import os
import sys
import tempfile
import pandas as pd
from unittest.mock import patch, MagicMock

# プロジェクトルートをパスに追加
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rotation_planner.app.constraints import (
    get_default_crops,
    build_constraints_table,
    parse_constraints_table,
    parse_forbidden_transitions,
    parse_preferred_transitions,
    update_constraints_table,
    load_constraints_csv,
    _FALLBACK_CROPS,
    DEFAULT_CONSTRAINTS,
)


# =============================================================================
# TestGetDefaultCrops（CN-01 ~ CN-03）
# =============================================================================

class TestGetDefaultCrops:
    """get_default_crops のテスト"""

    def test_cn01_user_crops_exist(self):
        """CN-01: ユーザー設定あり → ユーザーの作物リスト"""
        # get_default_crops は関数内で from rotation_planner.common import するため
        # パッチ先は rotation_planner.common のモジュール属性
        mock_user_crop = MagicMock()
        mock_user_crop.get_user_crops.return_value = [
            {"name": "大豆", "custom_name": ""},
            {"name": "てんさい", "custom_name": "ビート"},
        ]

        with patch("rotation_planner.common.UserCropRepository", mock_user_crop):
            result = get_default_crops(user_id=3)

        assert isinstance(result, list)
        assert len(result) == 2
        # custom_name が空なら name を使う、custom_name があればそれを使う
        assert "大豆" in result
        assert "ビート" in result

    def test_cn02_no_user_setting(self):
        """CN-02: ユーザー設定なし（user_id=None）→ マスタの作物リスト"""
        mock_master = MagicMock()
        mock_master.get_all.return_value = [
            {"name": "春小麦"},
            {"name": "大豆"},
            {"name": "てんさい"},
        ]

        with patch("rotation_planner.common.CropMasterRepository", mock_master):
            result = get_default_crops(user_id=None)

        assert isinstance(result, list)
        assert len(result) == 3
        assert "春小麦" in result
        assert "大豆" in result

    def test_cn03_user_id_none_fallback(self):
        """CN-03: user_id=None かつ マスタ空 → フォールバック作物リスト"""
        mock_master = MagicMock()
        mock_master.get_all.return_value = []

        with patch("rotation_planner.common.CropMasterRepository", mock_master):
            result = get_default_crops(user_id=None)

        # マスタが空の場合、フォールバックが返る
        assert result == _FALLBACK_CROPS


# =============================================================================
# TestBuildConstraintsTable（CN-04 ~ CN-06）
# =============================================================================

class TestBuildConstraintsTable:
    """build_constraints_table のテスト"""

    def test_cn04_normal_build(self):
        """CN-04: 正常構築 → DataFrame"""
        crops = ["大豆", "てんさい", "春小麦"]
        df = build_constraints_table(crops)

        assert isinstance(df, pd.DataFrame)
        assert len(df) == 3
        assert "crop" in df.columns
        assert "cap_ha" in df.columns
        assert "min_gap_years" in df.columns
        assert "min_fields" in df.columns
        assert "max_fields" in df.columns
        # 大豆のcap_haがDEFAULT_CONSTRAINTSと一致
        soy_row = df[df["crop"] == "大豆"].iloc[0]
        assert soy_row["cap_ha"] == DEFAULT_CONSTRAINTS["大豆"]["cap_ha"]

    def test_cn05_empty_list(self):
        """CN-05: 空リスト → 空DataFrame"""
        df = build_constraints_table([])

        assert isinstance(df, pd.DataFrame)
        assert len(df) == 0

    def test_cn06_single_crop(self):
        """CN-06: 1作物 → 1行DataFrame"""
        df = build_constraints_table(["大豆"])

        assert isinstance(df, pd.DataFrame)
        assert len(df) == 1
        assert df.iloc[0]["crop"] == "大豆"


# =============================================================================
# TestParseConstraintsTable（CN-07 ~ CN-08）
# =============================================================================

class TestParseConstraintsTable:
    """parse_constraints_table のテスト"""

    def test_cn07_normal_parse(self):
        """CN-07: 正常パース → 5つのdict"""
        df = pd.DataFrame([
            {"crop": "大豆", "min_ha": "", "cap_ha": 12, "min_gap_years": 0, "min_fields": 0, "max_fields": ""},
            {"crop": "てんさい", "min_ha": 5.0, "cap_ha": "", "min_gap_years": 4, "min_fields": 0, "max_fields": 2},
        ])

        crop_mins, crop_caps, min_gap, min_f, max_f = parse_constraints_table(df)

        # 5つのdictが返ること
        assert isinstance(crop_mins, dict)
        assert isinstance(crop_caps, dict)
        assert isinstance(min_gap, dict)
        assert isinstance(min_f, dict)
        assert isinstance(max_f, dict)

        # 大豆: cap_ha=12, min_ha=None（空文字）
        assert crop_mins["大豆"] is None
        assert crop_caps["大豆"] == 12.0

        # てんさい: min_ha=5.0, cap_ha=None（空文字）, min_gap_years=4, max_fields=2
        assert crop_mins["てんさい"] == 5.0
        assert crop_caps["てんさい"] is None
        assert min_gap["てんさい"] == 4
        assert max_f["てんさい"] == 2

    def test_cn08_empty_table(self):
        """CN-08: 空テーブル → 空dict群"""
        df = pd.DataFrame(columns=["crop", "min_ha", "cap_ha", "min_gap_years", "min_fields", "max_fields"])

        crop_mins, crop_caps, min_gap, min_f, max_f = parse_constraints_table(df)

        assert crop_mins == {}
        assert crop_caps == {}
        assert min_gap == {}
        assert min_f == {}
        assert max_f == {}


# =============================================================================
# TestParseForbiddenTransitions（CN-09 ~ CN-12）
# =============================================================================

class TestParseForbiddenTransitions:
    """parse_forbidden_transitions のテスト"""

    def test_cn09_single_transition(self):
        """CN-09: 正常パース → Set"""
        result = parse_forbidden_transitions("大豆->てんさい")

        assert isinstance(result, set)
        assert ("大豆", "てんさい") in result
        assert len(result) == 1

    def test_cn10_multiple_transitions(self):
        """CN-10: 複数 → 2要素Set"""
        result = parse_forbidden_transitions("大豆->てんさい, 春小麦->秋小麦")

        assert len(result) == 2
        assert ("大豆", "てんさい") in result
        assert ("春小麦", "秋小麦") in result

    def test_cn11_empty_string(self):
        """CN-11: 空文字 → 空Set"""
        result = parse_forbidden_transitions("")
        assert result == set()

        # スペースのみも空
        result2 = parse_forbidden_transitions("   ")
        assert result2 == set()

    def test_cn12_invalid_format(self):
        """CN-12: 不正形式 → 空Set（矢印なし）"""
        # 矢印なし
        result = parse_forbidden_transitions("大豆-てんさい")
        assert len(result) == 0

        # 片方が空
        result2 = parse_forbidden_transitions("->てんさい")
        assert len(result2) == 0

        # 全く関係ない文字列
        result3 = parse_forbidden_transitions("ただの文字列")
        assert len(result3) == 0


# =============================================================================
# TestParsePreferredTransitions（CN-13 ~ CN-14）
# =============================================================================

class TestParsePreferredTransitions:
    """parse_preferred_transitions のテスト"""

    def test_cn13_normal_parse(self):
        """CN-13: 正常パース → Dict"""
        result = parse_preferred_transitions("てんさい->大豆:10, デントコーン->秋小麦:8")

        assert isinstance(result, dict)
        assert len(result) == 2
        assert result[("てんさい", "大豆")] == 10.0
        assert result[("デントコーン", "秋小麦")] == 8.0

    def test_cn14_weight_omitted(self):
        """CN-14: weight省略 → パースされない（コロン必須のため）"""
        # parse_preferred_transitions は '->' と ':' の両方が必要
        # weight省略（コロンなし）の場合はスキップされる
        result = parse_preferred_transitions("てんさい->大豆")

        # コロンがないのでパースされず空Dict
        assert result == {}


# =============================================================================
# TestUpdateConstraintsTable（CN-15 ~ CN-16）
# =============================================================================

class TestUpdateConstraintsTable:
    """update_constraints_table のテスト"""

    def test_cn15_add_crop(self):
        """CN-15: 作物追加 → 行追加されたDF"""
        # 既存テーブル（2作物）
        existing = pd.DataFrame([
            {"crop": "大豆", "min_ha": "", "cap_ha": 12, "min_gap_years": 0, "min_fields": 0, "max_fields": ""},
            {"crop": "てんさい", "min_ha": "", "cap_ha": "", "min_gap_years": 4, "min_fields": 0, "max_fields": 2},
        ])

        # 3作物に増やす（春小麦を追加）
        result = update_constraints_table("大豆\nてんさい\n春小麦", existing)

        assert isinstance(result, pd.DataFrame)
        assert len(result) == 3
        crops = result["crop"].tolist()
        assert "大豆" in crops
        assert "てんさい" in crops
        assert "春小麦" in crops

        # 既存の大豆の値は保持されること
        soy_row = result[result["crop"] == "大豆"].iloc[0]
        assert soy_row["cap_ha"] == 12

        # 既存のてんさいの値も保持されること
        beet_row = result[result["crop"] == "てんさい"].iloc[0]
        assert beet_row["min_gap_years"] == 4

    def test_cn16_remove_crop(self):
        """CN-16: 作物削除 → 行削除されたDF"""
        existing = pd.DataFrame([
            {"crop": "大豆", "min_ha": "", "cap_ha": 12, "min_gap_years": 0, "min_fields": 0, "max_fields": ""},
            {"crop": "てんさい", "min_ha": "", "cap_ha": "", "min_gap_years": 4, "min_fields": 0, "max_fields": 2},
            {"crop": "春小麦", "min_ha": "", "cap_ha": 10, "min_gap_years": 0, "min_fields": 0, "max_fields": ""},
        ])

        # 2作物に減らす（春小麦を削除）
        result = update_constraints_table("大豆\nてんさい", existing)

        assert len(result) == 2
        crops = result["crop"].tolist()
        assert "大豆" in crops
        assert "てんさい" in crops
        assert "春小麦" not in crops


# =============================================================================
# TestLoadConstraintsCsv（CN-17 ~ CN-18）
# =============================================================================

class TestLoadConstraintsCsv:
    """load_constraints_csv のテスト"""

    def test_cn17_valid_csv(self):
        """CN-17: 正常CSV → DataFrame"""
        csv_content = "crop,min_ha,cap_ha,min_gap_years,min_fields,max_fields\n大豆,,12,0,0,\nてんさい,5,,4,0,2\n"

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, encoding="utf-8-sig"
        ) as f:
            f.write(csv_content)
            f.flush()
            tmp_path = f.name

        try:
            df = load_constraints_csv(tmp_path)

            assert isinstance(df, pd.DataFrame)
            assert not df.empty
            assert "crop" in df.columns
            assert len(df) == 2
            crops = df["crop"].tolist()
            assert "大豆" in crops
            assert "てんさい" in crops
        finally:
            os.remove(tmp_path)

    def test_cn18_invalid_csv(self):
        """CN-18: 不正CSV（crop列なし） → 空DataFrame"""
        csv_content = "name,value\nfoo,1\nbar,2\n"

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, encoding="utf-8-sig"
        ) as f:
            f.write(csv_content)
            f.flush()
            tmp_path = f.name

        try:
            df = load_constraints_csv(tmp_path)

            # crop列がないので空DataFrameが返る
            assert isinstance(df, pd.DataFrame)
            assert df.empty
        finally:
            os.remove(tmp_path)
