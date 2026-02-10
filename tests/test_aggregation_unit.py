"""
集計ロジック（field/aggregation.py）の単体テスト

テストケース: AG-01 ~ AG-12（cmd_072 Phase 1）
依存: models.py（AggregationRow）, field/aggregation.py

注: AggregationRow のフィールド名は models.py 完成後に変わる可能性あり。
    現時点では aggregation.py の fallback 定義に合わせている。
"""
import pytest
import pandas as pd

from rotation_planner.field.aggregation import (
    CropLandBreakdown,
    aggregate_by_crop,
    build_cross_tabulation,
    format_cross_table_for_display,
    get_conversion_year_columns,
)

# AggregationRow は aggregation.py が models.py or fallback から取得したものを使用
import rotation_planner.field.aggregation as _agg
AggregationRow = _agg.AggregationRow


# ============================================================
# AggregationRow フィールド名の自動検出
# models.py と fallback でフィールド名が異なるため対応
# ============================================================

def _has_attr(cls, name):
    """dataclass フィールドにnameがあるか"""
    import dataclasses
    if dataclasses.is_dataclass(cls):
        return name in {f.name for f in dataclasses.fields(cls)}
    return hasattr(cls, name)

# models.py版: field_area_ha, paddy_area_ha / fallback版: field_area, paddy_area
_USE_HA_SUFFIX = _has_attr(AggregationRow, "field_area_ha")
_FIELD_AREA_KEY = "field_area_ha" if _USE_HA_SUFFIX else "field_area"
_PADDY_AREA_KEY = "paddy_area_ha" if _USE_HA_SUFFIX else "paddy_area"


def _make_agg_row(crop_name, field_area, converted_areas, paddy_area):
    """AggregationRow をフィールド名の違いを吸収して生成"""
    kwargs = {
        "crop_name": crop_name,
        _FIELD_AREA_KEY: field_area,
        "converted_areas": converted_areas,
        _PADDY_AREA_KEY: paddy_area,
    }
    # fallback版は total_area が引数
    if not _USE_HA_SUFFIX:
        kwargs["total_area"] = field_area + sum(converted_areas.values()) + paddy_area
    return AggregationRow(**kwargs)


def _get_field_area(row):
    return getattr(row, _FIELD_AREA_KEY)


def _get_paddy_area(row):
    return getattr(row, _PADDY_AREA_KEY)


# ============================================================
# テストデータフィクスチャ
# ============================================================

@pytest.fixture
def sample_breakdowns_single_crop():
    """同一作物2件のBreakdownリスト（AG-04用）"""
    return [
        CropLandBreakdown(
            crop_name="だいず",
            field_id=1,
            year=2026,
            field_area_ha=3.2,
            converted_areas={2022: 1.0},
            paddy_area_ha=0.0,
            total_area_ha=4.2,
        ),
        CropLandBreakdown(
            crop_name="だいず",
            field_id=2,
            year=2026,
            field_area_ha=0.0,
            converted_areas={2024: 0.5, "unknown": 0.3},
            paddy_area_ha=0.0,
            total_area_ha=0.8,
        ),
    ]


@pytest.fixture
def sample_breakdowns_two_crops(sample_breakdowns_single_crop):
    """2作物のBreakdownリスト（AG-05用）"""
    return sample_breakdowns_single_crop + [
        CropLandBreakdown(
            crop_name="てんさい",
            field_id=3,
            year=2026,
            field_area_ha=1.8,
            converted_areas={2024: 0.8},
            paddy_area_ha=0.0,
            total_area_ha=2.6,
        ),
    ]


@pytest.fixture
def sample_aggregation_rows():
    """AggregationRowリスト（殿の仕様書の例）"""
    return [
        _make_agg_row(
            crop_name="だいず",
            field_area=3.2,
            converted_areas={2022: 1.0, 2024: 0.5, "unknown": 0.3},
            paddy_area=0.0,
        ),
        _make_agg_row(
            crop_name="てんさい",
            field_area=1.8,
            converted_areas={2024: 0.8},
            paddy_area=0.0,
        ),
    ]


# ============================================================
# AG-01 ~ AG-03: CropLandBreakdown テスト
# ============================================================

class TestCropLandBreakdown:
    """CropLandBreakdown のテスト"""

    def test_ag01_default_values(self):
        """AG-01: デフォルト値で作成"""
        b = CropLandBreakdown(
            crop_name="だいず",
            field_id=1,
            year=2026,
        )
        assert b.crop_name == "だいず"
        assert b.field_id == 1
        assert b.year == 2026
        assert b.field_area_ha == 0.0
        assert b.converted_areas == {}
        assert b.paddy_area_ha == 0.0
        assert b.total_area_ha == 0.0

    def test_ag02_converted_areas_multiple_years(self):
        """AG-02: converted_areas に複数年度"""
        b = CropLandBreakdown(
            crop_name="だいず",
            field_id=1,
            year=2026,
            converted_areas={2022: 1.0, 2024: 0.5, "unknown": 0.3},
        )
        assert len(b.converted_areas) == 3
        assert b.converted_areas[2022] == 1.0
        assert b.converted_areas[2024] == 0.5
        assert b.converted_areas["unknown"] == 0.3

    def test_ag03_total_area_ha(self):
        """AG-03: total_area_ha の確認"""
        b = CropLandBreakdown(
            crop_name="だいず",
            field_id=1,
            year=2026,
            field_area_ha=3.2,
            converted_areas={2022: 1.0},
            paddy_area_ha=0.0,
            total_area_ha=4.2,
        )
        assert b.total_area_ha == 4.2


# ============================================================
# AG-04 ~ AG-06: aggregate_by_crop テスト
# ============================================================

class TestAggregateByCrop:
    """aggregate_by_crop のテスト"""

    def test_ag04_single_crop_aggregation(self, sample_breakdowns_single_crop):
        """AG-04: 1作物2件 → 1行に集約"""
        rows = aggregate_by_crop(sample_breakdowns_single_crop)

        assert len(rows) == 1
        row = rows[0]
        assert row.crop_name == "だいず"
        # field_area: 3.2 + 0.0 = 3.2
        assert abs(_get_field_area(row) - 3.2) < 0.01
        # converted_areas: {2022: 1.0, 2024: 0.5, 'unknown': 0.3} マージ
        assert abs(row.converted_areas.get(2022, 0) - 1.0) < 0.01
        assert abs(row.converted_areas.get(2024, 0) - 0.5) < 0.01
        assert abs(row.converted_areas.get("unknown", 0) - 0.3) < 0.01
        # paddy_area: 0.0 + 0.0 = 0.0
        assert abs(_get_paddy_area(row) - 0.0) < 0.01
        # total_area: 3.2 + 1.0 + 0.5 + 0.3 + 0.0 = 5.0
        assert abs(row.total_area - 5.0) < 0.01

    def test_ag05_two_crops(self, sample_breakdowns_two_crops):
        """AG-05: 2作物 → 2行"""
        rows = aggregate_by_crop(sample_breakdowns_two_crops)

        assert len(rows) == 2
        crop_names = {r.crop_name for r in rows}
        assert crop_names == {"だいず", "てんさい"}

    def test_ag06_empty_list(self):
        """AG-06: 空リスト → 空リスト"""
        rows = aggregate_by_crop([])
        assert rows == []


# ============================================================
# AG-07 ~ AG-09: build_cross_tabulation テスト
# ============================================================

class TestBuildCrossTabulation:
    """build_cross_tabulation のテスト"""

    def test_ag07_basic_cross_tab(self, sample_aggregation_rows):
        """AG-07: 基本クロス集計 → DataFrame"""
        df = build_cross_tabulation(sample_aggregation_rows)

        assert isinstance(df, pd.DataFrame)
        # 2作物行 + 合計行 = 3行
        assert len(df) >= 3
        # 基本列の存在確認
        assert "畑" in df.columns
        assert "合計" in df.columns

    def test_ag08_has_total_row(self, sample_aggregation_rows):
        """AG-08: 合計行あり"""
        df = build_cross_tabulation(sample_aggregation_rows)

        # 「作物」列に「合計」がある
        assert "作物" in df.columns
        assert "合計" in df["作物"].values

    def test_ag09_year_order(self, sample_aggregation_rows):
        """AG-09: 畑地化列が年度順"""
        df = build_cross_tabulation(sample_aggregation_rows)

        # 畑地化列を抽出
        converted_cols = [c for c in df.columns if "畑地化" in str(c)]
        assert len(converted_cols) >= 1

        # 年度列（不明以外）が昇順であること
        year_cols = [c for c in converted_cols if "不明" not in str(c)]
        if len(year_cols) >= 2:
            assert year_cols == sorted(year_cols), \
                f"畑地化列が年度順でない: {year_cols}"

        # 「不明」がある場合、年度列の後にあること
        unknown_cols = [c for c in converted_cols if "不明" in str(c)]
        if unknown_cols and year_cols:
            last_year_idx = df.columns.get_loc(year_cols[-1])
            unknown_idx = df.columns.get_loc(unknown_cols[0])
            assert unknown_idx > last_year_idx, \
                "畑地化(不明)が年度列より前にある"


# ============================================================
# AG-10 ~ AG-11: format_cross_table_for_display テスト
# ============================================================

class TestFormatCrossTableForDisplay:
    """format_cross_table_for_display のテスト"""

    def test_ag10_zero_to_dash(self, sample_aggregation_rows):
        """AG-10: 0.0 → '-'"""
        df = build_cross_tabulation(sample_aggregation_rows)
        formatted = format_cross_table_for_display(df)

        # 水田列は全て0.0のはず → '-' に変換されている
        assert "水田" in formatted.columns
        paddy_values = formatted["水田"].tolist()
        for val in paddy_values:
            assert val == "-", \
                f"水田の0.0が'-'に変換されていない: {val}"

    def test_ag11_two_decimal_places(self, sample_aggregation_rows):
        """AG-11: 小数2桁"""
        df = build_cross_tabulation(sample_aggregation_rows)
        formatted = format_cross_table_for_display(df)

        # 数値セルが小数2桁であること
        for col in formatted.columns:
            if col == "作物":
                continue
            for val in formatted[col]:
                if val == "-":
                    continue
                # 数値文字列は小数2桁であること
                assert "." in str(val), f"小数点がない: {val}"
                decimal_part = str(val).split(".")[-1]
                assert len(decimal_part) == 2, \
                    f"小数2桁でない: {val}"


# ============================================================
# AG-12: get_conversion_year_columns テスト
# ============================================================

class TestGetConversionYearColumns:
    """get_conversion_year_columns のテスト"""

    def test_ag12_year_ascending_unknown_last(self, sample_aggregation_rows):
        """AG-12: 年度昇順 + '不明'が最後"""
        cols = get_conversion_year_columns(sample_aggregation_rows)

        # 3キー: 2022, 2024, 'unknown' → 3列
        assert len(cols) == 3

        # 「不明」が最後であること
        assert "不明" in cols[-1]

        # 年度列が昇順であること
        year_cols = cols[:-1]  # 不明以外
        assert year_cols == sorted(year_cols)
        assert "2022" in year_cols[0]
        assert "2024" in year_cols[1]
