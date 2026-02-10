"""
空間演算（spatial.py）の単体テスト

テスト設計: cmd_072 タスクYAML
テストケース: SC-01～SC-04, SA-01～SA-03, SL-01～SL-08
合計: 15テスト
"""
import json

import pytest
from shapely.geometry import Polygon, MultiPolygon

from rotation_planner.field.spatial import (
    coords_to_shapely,
    shapely_to_coords,
    geojson_to_shapely,
    shapely_to_geojson,
    calculate_geodesic_area_ha,
    determine_land_category,
    split_crop_by_land_category,
    merge_paddy_polygons,
    LandCategory,
)


# ============================================================
# テストデータ（帯広付近の座標）
# ============================================================

# 作付けポリゴン [lat, lng] 形式 約1km x 1km
CROP_COORDS = [
    [42.92, 143.20],
    [42.92, 143.21],
    [42.93, 143.21],
    [42.93, 143.20],
]

# 作付けを完全に覆う大きな水田ポリゴン
BIG_PADDY_COORDS = [
    [42.91, 143.19],
    [42.91, 143.22],
    [42.94, 143.22],
    [42.94, 143.19],
]

# 作付けの左半分のみ覆う水田ポリゴン
HALF_PADDY_COORDS = [
    [42.91, 143.19],
    [42.91, 143.205],
    [42.94, 143.205],
    [42.94, 143.19],
]

# 作付けと重ならない遠い水田ポリゴン
FAR_PADDY_COORDS = [
    [43.00, 144.00],
    [43.00, 144.01],
    [43.01, 144.01],
    [43.01, 144.00],
]

# 非常に小さいポリゴン（数メートル四方）
TINY_COORDS = [
    [42.920000, 143.200000],
    [42.920000, 143.200010],
    [42.920010, 143.200010],
    [42.920010, 143.200000],
]

# 隣接する2つのポリゴン（merge テスト用）
ADJACENT_1_COORDS = [
    [42.92, 143.20],
    [42.92, 143.21],
    [42.93, 143.21],
    [42.93, 143.20],
]
ADJACENT_2_COORDS = [
    [42.92, 143.21],
    [42.92, 143.22],
    [42.93, 143.22],
    [42.93, 143.21],
]


def _coords_to_geojson_str(coords):
    """テスト用ヘルパー: [lat,lng]座標リスト → GeoJSON文字列"""
    # [lat, lng] → [lng, lat] に変換し、ポリゴンを閉じる
    ring = [[c[1], c[0]] for c in coords]
    if ring[0] != ring[-1]:
        ring.append(ring[0])
    return json.dumps({"type": "Polygon", "coordinates": [ring]})


# ============================================================
# SC-01～SC-04: 座標変換テスト
# ============================================================

class TestCoordinateConversion:
    """座標変換関数のテスト"""

    def test_sc01_coords_to_shapely(self):
        """SC-01: [[lat,lng],...] → 有効な Shapely Polygon"""
        poly = coords_to_shapely(CROP_COORDS)
        assert isinstance(poly, Polygon)
        assert poly.is_valid
        assert not poly.is_empty

    def test_sc02_shapely_to_coords_roundtrip(self):
        """SC-02: coords → shapely → coords ラウンドトリップ"""
        poly = coords_to_shapely(CROP_COORDS)
        result = shapely_to_coords(poly)

        assert len(result) == len(CROP_COORDS)
        for original, converted in zip(CROP_COORDS, result):
            assert abs(original[0] - converted[0]) < 1e-6  # lat
            assert abs(original[1] - converted[1]) < 1e-6  # lng

    def test_sc03_geojson_to_shapely(self):
        """SC-03: GeoJSON文字列 → Shapely geometry"""
        geojson_str = _coords_to_geojson_str(CROP_COORDS)
        geom = geojson_to_shapely(geojson_str)
        assert isinstance(geom, (Polygon, MultiPolygon))
        assert geom.is_valid
        assert not geom.is_empty

    def test_sc04_shapely_to_geojson_roundtrip(self):
        """SC-04: shapely → GeoJSON → shapely ラウンドトリップ"""
        geojson_str = _coords_to_geojson_str(CROP_COORDS)
        geom1 = geojson_to_shapely(geojson_str)
        geojson_out = shapely_to_geojson(geom1)
        geom2 = geojson_to_shapely(geojson_out)

        # 面積の差が十分小さいこと
        assert abs(geom1.area - geom2.area) < 1e-10


# ============================================================
# SA-01～SA-03: 面積計算テスト
# ============================================================

class TestGeodesicArea:
    """面積計算のテスト"""

    def test_sa01_positive_area(self):
        """SA-01: 北海道の小区画 → 正の面積"""
        poly = coords_to_shapely(CROP_COORDS)
        area_ha = calculate_geodesic_area_ha(poly)
        assert area_ha > 0

    def test_sa02_approximately_1ha(self):
        """SA-02: 約1km x 1km区画 → 合理的な面積範囲"""
        poly = coords_to_shapely(CROP_COORDS)
        area_ha = calculate_geodesic_area_ha(poly)
        # CROP_COORDS は約0.01度 x 0.01度 ≈ 約1km x 0.8km ≈ 約80ha
        # 広めの範囲で検証
        assert 10 < area_ha < 200

    def test_sa03_tiny_area(self):
        """SA-03: 非常に小さい区画 → 0に近い値"""
        poly = coords_to_shapely(TINY_COORDS)
        area_ha = calculate_geodesic_area_ha(poly)
        assert area_ha < 0.01


# ============================================================
# SL-01～SL-08: 地目判定テスト
# ============================================================

class TestDetermineLandCategory:
    """地目判定のテスト"""

    def test_sl01_all_paddy(self):
        """SL-01: 作付け全体が水田内 → 全てPADDY"""
        crop_geom = coords_to_shapely(CROP_COORDS)
        paddy_polygons = [
            {'geometry': _coords_to_geojson_str(BIG_PADDY_COORDS), 'is_converted': False}
        ]

        parts = determine_land_category(crop_geom, paddy_polygons)
        categories = [cat for _, cat, _, _ in parts]

        assert len(parts) >= 1
        assert all(c == LandCategory.PADDY for c in categories)

    def test_sl02_all_converted(self):
        """SL-02: 作付け全体が畑地化内 → 全てCONVERTED"""
        crop_geom = coords_to_shapely(CROP_COORDS)
        paddy_polygons = [
            {'geometry': _coords_to_geojson_str(BIG_PADDY_COORDS), 'is_converted': True}
        ]

        parts = determine_land_category(crop_geom, paddy_polygons)
        categories = [cat for _, cat, _, _ in parts]

        assert len(parts) >= 1
        assert all(c == LandCategory.CONVERTED for c in categories)

    def test_sl03_all_field(self):
        """SL-03: 作付け全体が水田外 → 全てFIELD"""
        crop_geom = coords_to_shapely(CROP_COORDS)
        paddy_polygons = [
            {'geometry': _coords_to_geojson_str(FAR_PADDY_COORDS), 'is_converted': False}
        ]

        parts = determine_land_category(crop_geom, paddy_polygons)
        categories = [cat for _, cat, _, _ in parts]

        assert len(parts) >= 1
        assert all(c == LandCategory.FIELD for c in categories)

    def test_sl04_paddy_and_field(self):
        """SL-04: 作付けが水田と畑にまたがる → PADDY + FIELD"""
        crop_geom = coords_to_shapely(CROP_COORDS)
        paddy_polygons = [
            {'geometry': _coords_to_geojson_str(HALF_PADDY_COORDS), 'is_converted': False}
        ]

        parts = determine_land_category(crop_geom, paddy_polygons)
        categories = set(cat for _, cat, _, _ in parts)

        assert LandCategory.PADDY in categories
        assert LandCategory.FIELD in categories

    def test_sl05_converted_and_field(self):
        """SL-05: 作付けが畑地化と畑にまたがる → CONVERTED + FIELD"""
        crop_geom = coords_to_shapely(CROP_COORDS)
        paddy_polygons = [
            {'geometry': _coords_to_geojson_str(HALF_PADDY_COORDS), 'is_converted': True}
        ]

        parts = determine_land_category(crop_geom, paddy_polygons)
        categories = set(cat for _, cat, _, _ in parts)

        assert LandCategory.CONVERTED in categories
        assert LandCategory.FIELD in categories

    def test_sl06_empty_paddy_list(self):
        """SL-06: 空の水田ポリゴンリスト → 全てFIELD"""
        crop_geom = coords_to_shapely(CROP_COORDS)
        paddy_polygons = []

        parts = determine_land_category(crop_geom, paddy_polygons)
        categories = [cat for _, cat, _, _ in parts]

        assert len(parts) >= 1
        assert all(c == LandCategory.FIELD for c in categories)

    def test_sl07_split_crop_geojson_wrapper(self):
        """SL-07: split_crop_by_land_category GeoJSONラッパー確認"""
        crop_geojson = _coords_to_geojson_str(CROP_COORDS)
        paddy_polygons = [
            {'geometry': _coords_to_geojson_str(HALF_PADDY_COORDS), 'is_converted': False}
        ]

        result = split_crop_by_land_category(crop_geojson, paddy_polygons)

        assert isinstance(result, list)
        assert len(result) >= 2
        for item in result:
            assert 'geometry' in item
            assert 'land_category' in item
            assert 'area_ha' in item
            assert isinstance(item['geometry'], str)
            assert isinstance(item['area_ha'], float)

    def test_sl08_merge_paddy_polygons(self):
        """SL-08: 隣接2ポリゴン → 結合"""
        geojson1 = _coords_to_geojson_str(ADJACENT_1_COORDS)
        geojson2 = _coords_to_geojson_str(ADJACENT_2_COORDS)

        merged = merge_paddy_polygons([geojson1, geojson2])

        merged_geom = geojson_to_shapely(merged)
        assert merged_geom.is_valid
        assert not merged_geom.is_empty

        # 結合前の2つの面積合計と概ね同じ
        geom1 = geojson_to_shapely(geojson1)
        geom2 = geojson_to_shapely(geojson2)
        total_area = geom1.area + geom2.area
        assert abs(merged_geom.area - total_area) < total_area * 0.01
