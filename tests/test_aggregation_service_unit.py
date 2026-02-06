"""
集計サービス層（field/aggregation_service.py）の単体テスト

テストケース: AS-01 ~ AS-10（cmd_073 Phase 2）
依存: aggregation_service.py, db_access.py, models.py, aggregation.py

注: build_land_breakdown_for_crop に複数のバグ（BUG-S1～S5）があるため、
    AS-01～AS-04 では build_land_breakdown_for_crop をモック、
    AS-09～AS-10 では split_crop_by_land_category + calculate_geodesic_area_ha をモックし、
    LandCategory.CONVERTED_PADDY バグ + Union未インポートバグを monkeypatch で回避。
    バグ詳細は TestBuildLandBreakdownForCrop のdocstring参照。
"""
import pytest
from unittest.mock import patch
import pandas as pd

from rotation_planner.common.db_access import (
    FieldRepository,
    PaddyPolygonRepository,
    CropPolygonRepository,
)
from rotation_planner.field.aggregation import CropLandBreakdown
from rotation_planner.common.models import LandCategory, PaddyPolygon
from rotation_planner.field.aggregation_service import (
    get_cross_tabulation_for_user,
    copy_crop_polygons_to_next_year,
    get_subsidy_summary,
    export_cross_tabulation_csv,
    build_land_breakdown_for_crop,
)


# ============================================================
# テスト用GeoJSON（北海道帯広付近）
# ============================================================

PADDY_GEOJSON = (
    '{"type":"Polygon","coordinates":'
    '[[[143.0,42.9],[143.02,42.9],[143.02,42.92],[143.0,42.92],[143.0,42.9]]]}'
)
CROP_GEOJSON_1 = (
    '{"type":"Polygon","coordinates":'
    '[[[143.01,42.9],[143.03,42.9],[143.03,42.92],[143.01,42.92],[143.01,42.9]]]}'
)
CROP_GEOJSON_2 = (
    '{"type":"Polygon","coordinates":'
    '[[[143.05,42.9],[143.07,42.9],[143.07,42.92],[143.05,42.92],[143.05,42.9]]]}'
)
CONVERTED_GEOJSON = (
    '{"type":"Polygon","coordinates":'
    '[[[143.1,42.9],[143.12,42.9],[143.12,42.92],[143.1,42.92],[143.1,42.9]]]}'
)


# ============================================================
# ヘルパー
# ============================================================

def _create_test_field(user_id, field_code="TF001"):
    """テスト用ほ場を作成し field_id を返す"""
    field_data = {
        "field_code": field_code,
        "district": "テスト地区",
        "name": "テストほ場",
        "area_ha": 1.0,
        "beet_forbidden": False,
        "coordinates_json": None,
        "notes": None,
    }
    return FieldRepository.create_field(user_id, field_data)


class _PatchedLandCategory:
    """BUG-S3回避: LandCategory に存在しない CONVERTED_PADDY を追加"""
    FIELD = LandCategory.FIELD
    PADDY = LandCategory.PADDY
    CONVERTED = LandCategory.CONVERTED
    CONVERTED_PADDY = LandCategory.CONVERTED  # 本来は CONVERTED が正しい
    UNKNOWN = LandCategory.UNKNOWN


# ============================================================
# ■ get_cross_tabulation_for_user テスト（AS-01〜AS-04）
# ============================================================

class TestGetCrossTabulationForUser:
    """get_cross_tabulation_for_user のテスト"""

    def test_as01_data_exists(self, test_db, admin_state):
        """AS-01: データあり → raw_df と display_df の両方返却"""
        user_id = admin_state["user_id"]
        fid = _create_test_field(user_id)

        PaddyPolygonRepository.create(
            field_id=fid, geometry=PADDY_GEOJSON, area_ha=2.0,
        )
        CropPolygonRepository.create(
            field_id=fid, year=2026, crop_name="だいず",
            geometry=CROP_GEOJSON_1, area_ha=2.0,
        )

        mock_bd = CropLandBreakdown(
            crop_name="だいず", field_id=fid, year=2026,
            field_area_ha=1.0, converted_areas={}, paddy_area_ha=1.0,
            total_area_ha=2.0,
        )

        with patch(
            "rotation_planner.field.aggregation_service.build_land_breakdown_for_crop",
            return_value=mock_bd,
        ):
            raw_df, display_df = get_cross_tabulation_for_user(user_id, 2026)

        assert isinstance(raw_df, pd.DataFrame)
        assert isinstance(display_df, pd.DataFrame)
        # データ行 + 合計行 = 2行
        assert len(raw_df) >= 2
        assert len(display_df) >= 2

    def test_as02_no_data(self, test_db, admin_state):
        """AS-02: データなし（空年度）→ 空DataFrame"""
        user_id = admin_state["user_id"]

        raw_df, display_df = get_cross_tabulation_for_user(user_id, 2099)

        assert isinstance(raw_df, pd.DataFrame)
        assert isinstance(display_df, pd.DataFrame)
        # 作物データ行なし（合計行のみ or 完全空）
        if "作物" in raw_df.columns:
            crop_rows = raw_df[raw_df["作物"] != "合計"]
            assert len(crop_rows) == 0
        else:
            assert len(raw_df) == 0

    def test_as03_multiple_crops(self, test_db, admin_state):
        """AS-03: 複数作物 → 行数が作物数+合計行"""
        user_id = admin_state["user_id"]
        fid1 = _create_test_field(user_id, "TF001")
        fid2 = _create_test_field(user_id, "TF002")

        CropPolygonRepository.create(
            field_id=fid1, year=2026, crop_name="だいず",
            geometry=CROP_GEOJSON_1, area_ha=2.0,
        )
        CropPolygonRepository.create(
            field_id=fid2, year=2026, crop_name="てんさい",
            geometry=CROP_GEOJSON_2, area_ha=3.0,
        )

        bds = [
            CropLandBreakdown(
                crop_name="だいず", field_id=fid1, year=2026,
                field_area_ha=2.0, converted_areas={}, paddy_area_ha=0.0,
                total_area_ha=2.0,
            ),
            CropLandBreakdown(
                crop_name="てんさい", field_id=fid2, year=2026,
                field_area_ha=3.0, converted_areas={}, paddy_area_ha=0.0,
                total_area_ha=3.0,
            ),
        ]

        with patch(
            "rotation_planner.field.aggregation_service.build_land_breakdown_for_crop",
            side_effect=bds,
        ):
            raw_df, display_df = get_cross_tabulation_for_user(user_id, 2026)

        # 2作物 + 合計行 = 3
        assert len(raw_df) == 3
        names = set(raw_df["作物"].tolist())
        assert "だいず" in names
        assert "てんさい" in names
        assert "合計" in names

    def test_as04_conversion_year_columns(self, test_db, admin_state):
        """AS-04: 畑地化年度別 → 列名に畑地化(YYYY)が含まれる"""
        user_id = admin_state["user_id"]
        fid = _create_test_field(user_id)

        CropPolygonRepository.create(
            field_id=fid, year=2026, crop_name="だいず",
            geometry=CROP_GEOJSON_1, area_ha=2.0,
        )

        mock_bd = CropLandBreakdown(
            crop_name="だいず", field_id=fid, year=2026,
            field_area_ha=1.0,
            converted_areas={2022: 0.5, 2024: 0.3},
            paddy_area_ha=0.2,
            total_area_ha=2.0,
        )

        with patch(
            "rotation_planner.field.aggregation_service.build_land_breakdown_for_crop",
            return_value=mock_bd,
        ):
            raw_df, display_df = get_cross_tabulation_for_user(user_id, 2026)

        # 列名に畑地化(YYYY)が含まれる
        cols_str = " ".join(str(c) for c in raw_df.columns)
        assert "畑地化" in cols_str
        assert any("2022" in str(c) for c in raw_df.columns)
        assert any("2024" in str(c) for c in raw_df.columns)


# ============================================================
# ■ copy_crop_polygons_to_next_year テスト（AS-05〜AS-06）
# ============================================================

class TestCopyCropPolygonsToNextYear:
    """copy_crop_polygons_to_next_year のテスト"""

    def test_as05_normal_copy(self, test_db, admin_state):
        """AS-05: 正常コピー → コピー件数 > 0"""
        user_id = admin_state["user_id"]
        fid = _create_test_field(user_id)

        for i, crop in enumerate(["だいず", "てんさい", "春小麦"]):
            CropPolygonRepository.create(
                field_id=fid, year=2025, crop_name=crop,
                geometry=CROP_GEOJSON_1, area_ha=1.0 + i,
            )

        count, message = copy_crop_polygons_to_next_year(user_id, 2025, 2026)

        assert count == 3
        assert count > 0
        assert "2025" in message
        assert "2026" in message

        # コピー先にデータが存在
        copied = CropPolygonRepository.get_all_for_user_year(user_id, 2026)
        assert len(copied) == 3

    def test_as06_no_source(self, test_db, admin_state):
        """AS-06: コピー元なし → 0件"""
        user_id = admin_state["user_id"]

        count, message = copy_crop_polygons_to_next_year(user_id, 2090, 2091)

        assert count == 0
        assert "コピーできませんでした" in message


# ============================================================
# ■ get_subsidy_summary テスト（AS-07〜AS-08）
# ============================================================

class TestGetSubsidySummary:
    """get_subsidy_summary のテスト"""

    def test_as07_converted_exists(self, test_db, admin_state):
        """AS-07: 畑地化ポリゴンあり → 残年数計算"""
        user_id = admin_state["user_id"]
        fid = _create_test_field(user_id)

        PaddyPolygonRepository.create(
            field_id=fid, geometry=CONVERTED_GEOJSON, area_ha=3.5,
            is_converted=True, conversion_start_year=2023,
        )

        summary = get_subsidy_summary(user_id)

        assert len(summary) == 1
        item = summary[0]
        assert item["field_id"] == fid
        assert item["area_ha"] == 3.5
        assert item["start_year"] == 2023
        assert item["remaining_years"] is not None
        assert isinstance(item["remaining_years"], int)
        assert 0 <= item["remaining_years"] <= 5

    def test_as08_no_converted(self, test_db, admin_state):
        """AS-08: 畑地化なし → 空リスト"""
        user_id = admin_state["user_id"]
        fid = _create_test_field(user_id)

        # 非転作の水田のみ
        PaddyPolygonRepository.create(
            field_id=fid, geometry=PADDY_GEOJSON, area_ha=2.0,
            is_converted=False,
        )

        summary = get_subsidy_summary(user_id)
        assert summary == []


# ============================================================
# ■ build_land_breakdown_for_crop テスト（AS-09〜AS-10）
# ============================================================

class TestBuildLandBreakdownForCrop:
    """build_land_breakdown_for_crop のテスト

    BUG-S1～S5 は家老により修正済み。
    split_crop_by_land_category のみモックし、
    サービスロジック（地目別面積集計→CropLandBreakdown構築）を検証する。
    """

    @patch("rotation_planner.field.aggregation_service.split_crop_by_land_category")
    def test_as09_paddy_intersection(self, mock_split):
        """AS-09: 水田ポリゴンと交差 → PADDY + FIELD"""
        mock_split.return_value = [
            {"geometry": "p", "land_category": LandCategory.PADDY,
             "area_ha": 1.5, "conversion_start_year": None},
            {"geometry": "f", "land_category": LandCategory.FIELD,
             "area_ha": 2.0},
        ]

        result = build_land_breakdown_for_crop(
            {"crop_name": "だいず", "field_id": 1,
             "year": 2026, "geometry": CROP_GEOJSON_1},
            [{"geometry": PADDY_GEOJSON, "is_converted": 0}],
        )

        assert isinstance(result, CropLandBreakdown)
        assert result.crop_name == "だいず"
        assert result.paddy_area_ha == 1.5
        assert result.field_area_ha == 2.0
        assert result.total_area_ha == pytest.approx(3.5)

    @patch("rotation_planner.field.aggregation_service.split_crop_by_land_category")
    def test_as10_no_paddy(self, mock_split):
        """AS-10: 水田なし → 全て FIELD"""
        mock_split.return_value = [
            {"geometry": "f", "land_category": LandCategory.FIELD,
             "area_ha": 4.2},
        ]

        result = build_land_breakdown_for_crop(
            {"crop_name": "てんさい", "field_id": 2,
             "year": 2026, "geometry": CROP_GEOJSON_2},
            [],
        )

        assert isinstance(result, CropLandBreakdown)
        assert result.crop_name == "てんさい"
        assert result.field_area_ha == pytest.approx(4.2)
        assert result.paddy_area_ha == 0.0
        assert result.converted_areas == {}
        assert result.total_area_ha == pytest.approx(4.2)
