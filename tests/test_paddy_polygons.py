"""水田ポリゴン（paddy_polygons）のテスト — Repository + spatial.py"""
import os
import json
import pytest

# conftest.py で DB_PATH はテスト用に設定済み
import rotation_planner.common.db_access as _db_mod
_test_db_path = str(_db_mod.DB_PATH)

from rotation_planner.common.db_access import (
    PaddyPolygonRepository,
    ensure_crop_tables,
    ensure_paddy_polygons_table,
    get_db,
)
from rotation_planner.field.spatial import (
    coords_to_shapely,
    shapely_to_coords,
    geojson_to_shapely,
    shapely_to_geojson,
    calculate_geodesic_area_ha,
    merge_paddy_polygons,
)

# 北海道十勝の四角形ポリゴン（約1ha）
SAMPLE_GEOJSON = json.dumps({
    "type": "Polygon",
    "coordinates": [[
        [143.20, 42.92],
        [143.21, 42.92],
        [143.21, 42.93],
        [143.20, 42.93],
        [143.20, 42.92],
    ]]
})

SAMPLE_GEOJSON_2 = json.dumps({
    "type": "Polygon",
    "coordinates": [[
        [143.22, 42.92],
        [143.23, 42.92],
        [143.23, 42.93],
        [143.22, 42.93],
        [143.22, 42.92],
    ]]
})


@pytest.fixture(autouse=True)
def setup_db(test_db):
    """各テスト前にDBを初期化（test_dbフィクスチャで独立DB使用）"""
    with get_db() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO organizations (id, name, type) VALUES (1, 'テストJA', 'JA')"
        )
        conn.execute(
            "INSERT OR IGNORE INTO users (id, username, password_hash, display_name, org_id, role) "
            "VALUES (1, 'testuser', 'hash', 'テストユーザー', 1, 'admin')"
        )
        conn.execute(
            "INSERT OR IGNORE INTO fields (id, user_id, name, field_code, area_ha) VALUES (1, 1, 'テスト圃場', 'F001', 1.0)"
        )
        conn.execute(
            "INSERT OR IGNORE INTO fields (id, user_id, name, field_code, area_ha) VALUES (2, 1, 'テスト圃場2', 'F002', 2.0)"
        )
        conn.commit()
    ensure_crop_tables()
    ensure_paddy_polygons_table()
    yield


# =============================================================================
# spatial.py テスト
# =============================================================================

class TestCoordsToShapely:
    def test_basic_conversion(self):
        coords = [[42.92, 143.20], [42.92, 143.21], [42.93, 143.21], [42.93, 143.20]]
        poly = coords_to_shapely(coords)
        assert poly.is_valid
        assert not poly.is_empty

    def test_too_few_points(self):
        with pytest.raises(ValueError, match="最低3点"):
            coords_to_shapely([[42.92, 143.20], [42.93, 143.21]])


class TestShapelyToCoords:
    def test_roundtrip(self):
        coords = [[42.92, 143.20], [42.92, 143.21], [42.93, 143.21], [42.93, 143.20]]
        poly = coords_to_shapely(coords)
        result = shapely_to_coords(poly)
        assert len(result) == 4
        assert abs(result[0][0] - 42.92) < 0.001


class TestGeojsonToShapely:
    def test_valid_geojson(self):
        poly = geojson_to_shapely(SAMPLE_GEOJSON)
        assert poly.is_valid

    def test_invalid_json(self):
        with pytest.raises(ValueError, match="不正なJSON"):
            geojson_to_shapely("not json")

    def test_non_polygon(self):
        point_geojson = json.dumps({"type": "Point", "coordinates": [143.20, 42.92]})
        with pytest.raises(ValueError, match="ポリゴンまたはマルチポリゴン"):
            geojson_to_shapely(point_geojson)


class TestShapelyToGeojson:
    def test_roundtrip(self):
        poly = geojson_to_shapely(SAMPLE_GEOJSON)
        result_str = shapely_to_geojson(poly)
        result = json.loads(result_str)
        assert result["type"] == "Polygon"
        assert len(result["coordinates"][0]) >= 4


class TestCalculateGeodesicAreaHa:
    def test_area_positive(self):
        poly = geojson_to_shapely(SAMPLE_GEOJSON)
        area = calculate_geodesic_area_ha(poly)
        assert area > 0
        # 約0.01度四方 ≈ 約0.8-1.0 km² = 約80-100 ha
        assert 50 < area < 150

    def test_empty_polygon(self):
        from shapely.geometry import Polygon as ShapelyPolygon
        empty = ShapelyPolygon()
        area = calculate_geodesic_area_ha(empty)
        assert area == 0.0


class TestMergePaddyPolygons:
    def test_merge_two(self):
        result = merge_paddy_polygons([SAMPLE_GEOJSON, SAMPLE_GEOJSON_2])
        result_dict = json.loads(result)
        assert result_dict["type"] in ("Polygon", "MultiPolygon")

    def test_empty_list(self):
        with pytest.raises(ValueError, match="結合するポリゴン"):
            merge_paddy_polygons([])


# =============================================================================
# PaddyPolygonRepository テスト
# =============================================================================

class TestPaddyPolygonCreate:
    def test_create_basic(self):
        pid = PaddyPolygonRepository.create(
            field_id=1, geometry=SAMPLE_GEOJSON, area_ha=1.5
        )
        assert pid > 0

    def test_create_with_conversion(self):
        pid = PaddyPolygonRepository.create(
            field_id=1, geometry=SAMPLE_GEOJSON, area_ha=1.5,
            is_converted=True, conversion_start_year=2020
        )
        p = PaddyPolygonRepository.get_by_id(pid)
        assert p['is_converted'] == 1
        assert p['conversion_start_year'] == 2020


class TestPaddyPolygonGetById:
    def test_get_existing(self):
        pid = PaddyPolygonRepository.create(
            field_id=1, geometry=SAMPLE_GEOJSON, area_ha=1.0
        )
        p = PaddyPolygonRepository.get_by_id(pid)
        assert p is not None
        assert p['field_id'] == 1

    def test_get_nonexistent(self):
        p = PaddyPolygonRepository.get_by_id(9999)
        assert p is None


class TestPaddyPolygonGetByField:
    def test_get_by_field(self):
        PaddyPolygonRepository.create(field_id=1, geometry=SAMPLE_GEOJSON, area_ha=1.0)
        PaddyPolygonRepository.create(field_id=1, geometry=SAMPLE_GEOJSON_2, area_ha=2.0)
        PaddyPolygonRepository.create(field_id=2, geometry=SAMPLE_GEOJSON, area_ha=3.0)
        rows = PaddyPolygonRepository.get_by_field(1)
        assert len(rows) == 2


class TestPaddyPolygonGetAllForUser:
    def test_get_all_for_user(self):
        PaddyPolygonRepository.create(field_id=1, geometry=SAMPLE_GEOJSON, area_ha=1.0)
        PaddyPolygonRepository.create(field_id=2, geometry=SAMPLE_GEOJSON_2, area_ha=2.0)
        rows = PaddyPolygonRepository.get_all_for_user(1)
        assert len(rows) == 2


class TestPaddyPolygonUpdate:
    def test_update_conversion(self):
        pid = PaddyPolygonRepository.create(
            field_id=1, geometry=SAMPLE_GEOJSON, area_ha=1.0
        )
        PaddyPolygonRepository.update(pid, is_converted=True, conversion_start_year=2023)
        p = PaddyPolygonRepository.get_by_id(pid)
        assert p['is_converted'] == 1
        assert p['conversion_start_year'] == 2023

    def test_update_no_fields(self):
        pid = PaddyPolygonRepository.create(
            field_id=1, geometry=SAMPLE_GEOJSON, area_ha=1.0
        )
        result = PaddyPolygonRepository.update(pid)
        assert result is False


class TestPaddyPolygonDelete:
    def test_delete(self):
        pid = PaddyPolygonRepository.create(
            field_id=1, geometry=SAMPLE_GEOJSON, area_ha=1.0
        )
        assert PaddyPolygonRepository.delete(pid) is True
        assert PaddyPolygonRepository.get_by_id(pid) is None

    def test_delete_nonexistent(self):
        assert PaddyPolygonRepository.delete(9999) is False


class TestPaddyPolygonStats:
    def test_stats(self):
        PaddyPolygonRepository.create(
            field_id=1, geometry=SAMPLE_GEOJSON, area_ha=1.0, is_converted=False
        )
        PaddyPolygonRepository.create(
            field_id=1, geometry=SAMPLE_GEOJSON_2, area_ha=0.5, is_converted=True,
            conversion_start_year=2021
        )
        stats = PaddyPolygonRepository.get_stats(1)
        assert stats['total_count'] == 2
        assert abs(stats['total_area_ha'] - 1.5) < 0.01
        assert stats['paddy_count'] == 1
        assert stats['converted_count'] == 1
        assert abs(stats['paddy_area_ha'] - 1.0) < 0.01
        assert abs(stats['converted_area_ha'] - 0.5) < 0.01

    def test_stats_empty(self):
        stats = PaddyPolygonRepository.get_stats(1)
        assert stats['total_count'] == 0
