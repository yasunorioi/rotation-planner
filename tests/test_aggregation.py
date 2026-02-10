"""面積集計（aggregation）のテスト — 地目判定 + クロス集計表 + サービス層"""
import os
import json
import datetime
import pytest

# conftest.py で DB_PATH はテスト用に設定済み
import rotation_planner.common.db_access as _db_mod
_test_db_path = str(_db_mod.DB_PATH)

from rotation_planner.common.db_access import (
    PaddyPolygonRepository,
    CropPolygonRepository,
    ensure_paddy_polygons_table,
    ensure_crop_polygons_table,
    get_db,
)
from rotation_planner.common.models import LandCategory, AggregationRow
from rotation_planner.field.spatial import (
    determine_land_category,
    split_crop_by_land_category,
    geojson_to_shapely,
)
from rotation_planner.field.aggregation import (
    CropLandBreakdown,
    aggregate_by_crop,
    get_conversion_year_columns,
    build_cross_tabulation,
    format_cross_table_for_display,
)
from rotation_planner.field.aggregation_service import (
    build_land_breakdown_for_crop,
    get_cross_tabulation_for_user,
    get_subsidy_summary,
    export_cross_tabulation_csv,
)


# 北海道十勝の四角形ポリゴン群（テスト用）
# ポリゴンA: 大きい範囲（0.01度四方）
POLY_A = json.dumps({
    "type": "Polygon",
    "coordinates": [[
        [143.20, 42.92],
        [143.21, 42.92],
        [143.21, 42.93],
        [143.20, 42.93],
        [143.20, 42.92],
    ]]
})

# ポリゴンB: Aと完全に重なる（同じ範囲）
POLY_B = POLY_A

# ポリゴンC: Aと半分重なる
POLY_C = json.dumps({
    "type": "Polygon",
    "coordinates": [[
        [143.205, 42.92],
        [143.215, 42.92],
        [143.215, 42.93],
        [143.205, 42.93],
        [143.205, 42.92],
    ]]
})

# ポリゴンD: Aと全く重ならない
POLY_D = json.dumps({
    "type": "Polygon",
    "coordinates": [[
        [143.30, 42.92],
        [143.31, 42.92],
        [143.31, 42.93],
        [143.30, 42.93],
        [143.30, 42.92],
    ]]
})


@pytest.fixture(autouse=True)
def setup_db(test_db):
    """各テスト前にDBを初期化（test_dbフィクスチャで独立DB使用）"""
    with get_db() as conn:
        conn.execute("PRAGMA foreign_keys = OFF")
        conn.execute(
            "INSERT OR IGNORE INTO organizations (id, name, type) VALUES (1, 'テストJA', 'JA')"
        )
        conn.execute(
            "INSERT OR IGNORE INTO users (id, username, password_hash, display_name, org_id, role) "
            "VALUES (1, 'testuser', 'hash', 'テストユーザー', 1, 'admin')"
        )
        conn.execute(
            "INSERT OR IGNORE INTO fields (id, user_id, name, field_code, area_ha) "
            "VALUES (1, 1, 'テスト圃場', 'F001', 1.0)"
        )
        conn.execute(
            "INSERT OR IGNORE INTO fields (id, user_id, name, field_code, area_ha) "
            "VALUES (2, 1, 'テスト圃場2', 'F002', 2.0)"
        )
        conn.commit()
    ensure_paddy_polygons_table()
    ensure_crop_polygons_table()
    yield


# =============================================================================
# determine_land_category テスト
# =============================================================================

class TestDetermineLandCategory:
    def test_full_overlap_paddy(self):
        """作付けと水田が完全重複 → PADDY"""
        crop_geom = geojson_to_shapely(POLY_A)
        paddy_polys = [{'geometry': POLY_B, 'is_converted': False}]
        result = determine_land_category(crop_geom, paddy_polys)
        categories = [cat for _, cat, _, _ in result]
        assert LandCategory.PADDY in categories
        assert LandCategory.FIELD not in categories

    def test_full_overlap_converted(self):
        """作付けと畑地化済が完全重複 → CONVERTED"""
        crop_geom = geojson_to_shapely(POLY_A)
        paddy_polys = [{
            'geometry': POLY_B, 'is_converted': True,
            'conversion_start_year': 2022,
        }]
        result = determine_land_category(crop_geom, paddy_polys)
        categories = [cat for _, cat, _, _ in result]
        assert LandCategory.CONVERTED in categories
        # conversion_start_year が引き継がれること
        conv_years = [yr for _, cat, _, yr in result if cat == LandCategory.CONVERTED]
        assert 2022 in conv_years

    def test_partial_overlap(self):
        """半分重複 → PADDY + FIELD"""
        crop_geom = geojson_to_shapely(POLY_A)
        paddy_polys = [{'geometry': POLY_C, 'is_converted': False}]
        result = determine_land_category(crop_geom, paddy_polys)
        categories = {cat for _, cat, _, _ in result}
        assert LandCategory.PADDY in categories
        assert LandCategory.FIELD in categories

    def test_no_overlap(self):
        """重複なし → 全て FIELD"""
        crop_geom = geojson_to_shapely(POLY_A)
        paddy_polys = [{'geometry': POLY_D, 'is_converted': False}]
        result = determine_land_category(crop_geom, paddy_polys)
        categories = [cat for _, cat, _, _ in result]
        assert all(c == LandCategory.FIELD for c in categories)

    def test_no_paddy_polygons(self):
        """水田ポリゴンなし → 全て FIELD"""
        crop_geom = geojson_to_shapely(POLY_A)
        result = determine_land_category(crop_geom, [])
        assert len(result) == 1
        assert result[0][1] == LandCategory.FIELD

    def test_area_sum_preserved(self):
        """分割後の面積合計が元の面積とほぼ一致"""
        crop_geom = geojson_to_shapely(POLY_A)
        from rotation_planner.field.spatial import calculate_geodesic_area_ha
        original_area = calculate_geodesic_area_ha(crop_geom)

        paddy_polys = [{'geometry': POLY_C, 'is_converted': False}]
        result = determine_land_category(crop_geom, paddy_polys)
        split_total = sum(area for _, _, area, _ in result)
        assert abs(split_total - original_area) / original_area < 0.01  # 1%以内


class TestSplitCropByLandCategory:
    def test_returns_dicts(self):
        """dictリスト形式で返ること"""
        paddy_polys = [{'geometry': POLY_C, 'is_converted': True, 'conversion_start_year': 2021}]
        result = split_crop_by_land_category(POLY_A, paddy_polys)
        assert isinstance(result, list)
        for item in result:
            assert 'geometry' in item
            assert 'land_category' in item
            assert 'area_ha' in item
            assert 'conversion_start_year' in item

    def test_conversion_year_passed_through(self):
        """conversion_start_year がCONVERTED部分に引き継がれること"""
        paddy_polys = [{'geometry': POLY_B, 'is_converted': True, 'conversion_start_year': 2020}]
        result = split_crop_by_land_category(POLY_A, paddy_polys)
        converted = [r for r in result if r['land_category'] == LandCategory.CONVERTED]
        assert len(converted) >= 1
        assert converted[0]['conversion_start_year'] == 2020


# =============================================================================
# aggregation.py テスト
# =============================================================================

class TestAggregateByCrop:
    def test_single_crop(self):
        """同一作物の複数ブレークダウンが1行に集約"""
        bds = [
            CropLandBreakdown(crop_name='大豆', field_id=1, year=2025,
                              field_area_ha=1.0, paddy_area_ha=0.5),
            CropLandBreakdown(crop_name='大豆', field_id=2, year=2025,
                              field_area_ha=2.0, paddy_area_ha=0.3),
        ]
        rows = aggregate_by_crop(bds)
        assert len(rows) == 1
        assert rows[0].crop_name == '大豆'
        assert abs(rows[0].field_area_ha - 3.0) < 0.01
        assert abs(rows[0].paddy_area_ha - 0.8) < 0.01

    def test_multiple_crops(self):
        """異なる作物は別行"""
        bds = [
            CropLandBreakdown(crop_name='大豆', field_id=1, year=2025,
                              field_area_ha=1.0, paddy_area_ha=0.0),
            CropLandBreakdown(crop_name='てんさい', field_id=2, year=2025,
                              field_area_ha=2.0, paddy_area_ha=0.0),
        ]
        rows = aggregate_by_crop(bds)
        assert len(rows) == 2
        names = {r.crop_name for r in rows}
        assert names == {'大豆', 'てんさい'}

    def test_converted_areas_merged(self):
        """畑地化年度別面積がマージされる"""
        bds = [
            CropLandBreakdown(crop_name='大豆', field_id=1, year=2025,
                              converted_areas={2022: 1.0, 'unknown': 0.5}),
            CropLandBreakdown(crop_name='大豆', field_id=2, year=2025,
                              converted_areas={2022: 0.5, 2023: 2.0}),
        ]
        rows = aggregate_by_crop(bds)
        assert abs(rows[0].converted_areas[2022] - 1.5) < 0.01
        assert abs(rows[0].converted_areas[2023] - 2.0) < 0.01
        assert abs(rows[0].converted_areas['unknown'] - 0.5) < 0.01

    def test_empty_input(self):
        """空リスト → 空結果"""
        assert aggregate_by_crop([]) == []


class TestGetConversionYearColumns:
    def test_sorted_years(self):
        """年度が昇順ソート"""
        rows = [
            AggregationRow(crop_name='大豆', field_area_ha=0, paddy_area_ha=0,
                           converted_areas={2023: 1.0, 2021: 0.5}),
        ]
        cols = get_conversion_year_columns(rows)
        assert cols == ['畑地化(2021)', '畑地化(2023)']

    def test_unknown_at_end(self):
        """'unknown'は末尾"""
        rows = [
            AggregationRow(crop_name='大豆', field_area_ha=0, paddy_area_ha=0,
                           converted_areas={2022: 1.0, 'unknown': 0.3}),
        ]
        cols = get_conversion_year_columns(rows)
        assert cols[-1] == '畑地化(不明)'

    def test_no_converted(self):
        """畑地化なし → 空リスト"""
        rows = [
            AggregationRow(crop_name='大豆', field_area_ha=1.0, paddy_area_ha=0,
                           converted_areas={}),
        ]
        assert get_conversion_year_columns(rows) == []


class TestBuildCrossTabulation:
    def test_basic_table(self):
        """基本的なクロス集計表生成"""
        rows = [
            AggregationRow(crop_name='大豆', field_area_ha=5.0,
                           converted_areas={2022: 3.0}, paddy_area_ha=2.0),
            AggregationRow(crop_name='てんさい', field_area_ha=4.0,
                           converted_areas={}, paddy_area_ha=0.0),
        ]
        df = build_cross_tabulation(rows)
        assert '作物' in df.columns
        assert '畑' in df.columns
        assert '水田' in df.columns
        assert '合計' in df.columns
        # 最終行は合計
        assert df.iloc[-1]['作物'] == '合計'
        assert abs(df.iloc[-1]['畑'] - 9.0) < 0.01

    def test_totals_row(self):
        """合計行の値が正しい"""
        rows = [
            AggregationRow(crop_name='大豆', field_area_ha=1.0,
                           converted_areas={2022: 2.0}, paddy_area_ha=3.0),
        ]
        df = build_cross_tabulation(rows)
        total_row = df[df['作物'] == '合計'].iloc[0]
        assert abs(total_row['合計'] - 6.0) < 0.01

    def test_empty_rows(self):
        """空入力でも合計行が生成される"""
        df = build_cross_tabulation([])
        assert len(df) == 1  # 合計行のみ
        assert df.iloc[0]['作物'] == '合計'


class TestFormatCrossTableForDisplay:
    def test_zero_to_dash(self):
        """0.0 → '-' 変換"""
        rows = [
            AggregationRow(crop_name='大豆', field_area_ha=0.0,
                           converted_areas={}, paddy_area_ha=1.5),
        ]
        df = build_cross_tabulation(rows)
        display_df = format_cross_table_for_display(df)
        # 畑が0.0 → '-'
        daizu_row = display_df[display_df['作物'] == '大豆'].iloc[0]
        assert daizu_row['畑'] == '-'
        assert daizu_row['水田'] == '1.50'


# =============================================================================
# aggregation_service.py テスト
# =============================================================================

class TestBuildLandBreakdownForCrop:
    def test_all_field(self):
        """水田ポリゴンなし → 全てFIELD"""
        crop = {'crop_name': '大豆', 'field_id': 1, 'year': 2025, 'geometry': POLY_A}
        bd = build_land_breakdown_for_crop(crop, [])
        assert bd.crop_name == '大豆'
        assert bd.field_area_ha > 0
        assert bd.paddy_area_ha == 0.0
        assert bd.converted_areas == {}

    def test_with_paddy(self):
        """水田と重複 → PADDYの面積が計上"""
        crop = {'crop_name': '大豆', 'field_id': 1, 'year': 2025, 'geometry': POLY_A}
        paddys = [{'geometry': POLY_B, 'is_converted': False}]
        bd = build_land_breakdown_for_crop(crop, paddys)
        assert bd.paddy_area_ha > 0

    def test_with_converted(self):
        """畑地化済と重複 → converted_areasに年度が入る"""
        crop = {'crop_name': '大豆', 'field_id': 1, 'year': 2025, 'geometry': POLY_A}
        paddys = [{
            'geometry': POLY_B, 'is_converted': True,
            'conversion_start_year': 2022,
        }]
        bd = build_land_breakdown_for_crop(crop, paddys)
        assert 2022 in bd.converted_areas
        assert bd.converted_areas[2022] > 0

    def test_converted_unknown_year(self):
        """畑地化済だが開始年度不明 → 'unknown'キー"""
        crop = {'crop_name': '大豆', 'field_id': 1, 'year': 2025, 'geometry': POLY_A}
        paddys = [{
            'geometry': POLY_B, 'is_converted': True,
            'conversion_start_year': None,
        }]
        bd = build_land_breakdown_for_crop(crop, paddys)
        assert 'unknown' in bd.converted_areas


class TestGetCrossTabulationForUser:
    def test_with_data(self):
        """DB上のデータで集計表生成"""
        # 水田ポリゴン作成
        PaddyPolygonRepository.create(
            field_id=1, geometry=POLY_A, area_ha=80.0,
            is_converted=False,
        )
        # 作付けポリゴン作成
        CropPolygonRepository.create(
            field_id=1, year=2025, crop_name='大豆',
            geometry=POLY_A, area_ha=80.0,
        )
        raw_df, display_df = get_cross_tabulation_for_user(user_id=1, year=2025)
        assert '作物' in raw_df.columns
        # 大豆が存在するはず
        crops = raw_df['作物'].tolist()
        assert '大豆' in crops
        assert '合計' in crops

    def test_empty(self):
        """データなし → 合計行のみ"""
        raw_df, display_df = get_cross_tabulation_for_user(user_id=1, year=2025)
        assert len(raw_df) == 1  # 合計行のみ


class TestGetSubsidySummary:
    def test_with_converted(self):
        """畑地化済みポリゴンの残年数が計算される"""
        current_year = datetime.date.today().year
        PaddyPolygonRepository.create(
            field_id=1, geometry=POLY_A, area_ha=5.0,
            is_converted=True, conversion_start_year=current_year - 2,
        )
        summary = get_subsidy_summary(user_id=1)
        assert len(summary) == 1
        assert summary[0]['remaining_years'] == 3  # 5 - 2

    def test_with_unknown_start(self):
        """開始年度不明 → remaining_years=None"""
        PaddyPolygonRepository.create(
            field_id=1, geometry=POLY_A, area_ha=3.0,
            is_converted=True, conversion_start_year=None,
        )
        summary = get_subsidy_summary(user_id=1)
        assert len(summary) == 1
        assert summary[0]['remaining_years'] is None
        assert summary[0]['start_year'] is None

    def test_non_converted_excluded(self):
        """水田（非畑地化）はサマリに含まれない"""
        PaddyPolygonRepository.create(
            field_id=1, geometry=POLY_A, area_ha=10.0,
            is_converted=False,
        )
        summary = get_subsidy_summary(user_id=1)
        assert len(summary) == 0

    def test_expired_subsidy(self):
        """5年以上経過 → remaining_years=0"""
        current_year = datetime.date.today().year
        PaddyPolygonRepository.create(
            field_id=1, geometry=POLY_A, area_ha=4.0,
            is_converted=True, conversion_start_year=current_year - 7,
        )
        summary = get_subsidy_summary(user_id=1)
        assert summary[0]['remaining_years'] == 0


class TestExportCrossTabulationCsv:
    def test_csv_output(self):
        """CSV出力がBOM付きUTF-8であること"""
        CropPolygonRepository.create(
            field_id=1, year=2025, crop_name='大豆',
            geometry=POLY_A, area_ha=80.0,
        )
        csv_str = export_cross_tabulation_csv(user_id=1, year=2025)
        assert csv_str.startswith('\ufeff')  # BOM
        assert '作物' in csv_str
        assert '大豆' in csv_str

    def test_empty_csv(self):
        """データなしでもCSV生成可能"""
        csv_str = export_cross_tabulation_csv(user_id=1, year=2025)
        assert '合計' in csv_str
