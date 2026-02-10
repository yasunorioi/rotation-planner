"""
GPS→ほ場マッチング機能のテスト
"""

import pytest
import json
import time
import random
from rotation_planner.field.gps_matcher import (
    find_field_by_gps,
    get_field_candidates,
    format_field_candidates_for_display,
    SHAPELY_AVAILABLE,
)


# テスト用ほ場データ（北海道恵庭市周辺の架空のほ場）
TEST_FIELDS = [
    {
        "id": 1,
        "field_code": "F001",
        "name": "北1号",
        "area_ha": 2.5,
        # 恵庭市の架空のポリゴン（中心: 42.88, 141.58）
        "coordinates_json": json.dumps([
            [42.880, 141.575],
            [42.880, 141.585],
            [42.885, 141.585],
            [42.885, 141.575],
        ])
    },
    {
        "id": 2,
        "field_code": "F002",
        "name": "北2号",
        "area_ha": 1.8,
        # 少し離れた位置（中心: 42.89, 141.58）
        "coordinates_json": json.dumps([
            [42.888, 141.575],
            [42.888, 141.585],
            [42.892, 141.585],
            [42.892, 141.575],
        ])
    },
    {
        "id": 3,
        "field_code": "F003",
        "name": "南1号",
        "area_ha": 3.0,
        # 離れた位置（中心: 42.87, 141.59）
        "coordinates_json": json.dumps([
            [42.868, 141.585],
            [42.868, 141.595],
            [42.872, 141.595],
            [42.872, 141.585],
        ])
    },
]

# 座標なしのほ場
FIELD_WITHOUT_COORDS = {
    "id": 4,
    "field_code": "F004",
    "name": "座標なし",
    "area_ha": 1.0,
    "coordinates_json": None
}


class TestFindFieldByGps:
    """find_field_by_gps関数のテスト"""

    @pytest.mark.skipif(not SHAPELY_AVAILABLE, reason="Shapely not available")
    def test_find_field_inside_polygon(self):
        """ポリゴン内のGPS座標でほ場を特定できる"""
        # F001の中心付近
        gps_lat = 42.8825
        gps_lon = 141.580

        result = find_field_by_gps(gps_lat, gps_lon, TEST_FIELDS)

        assert result is not None
        assert result["field_code"] == "F001"

    @pytest.mark.skipif(not SHAPELY_AVAILABLE, reason="Shapely not available")
    def test_find_field_outside_polygon(self):
        """ポリゴン外のGPS座標ではNoneを返す"""
        # 全ほ場から離れた位置
        gps_lat = 43.0
        gps_lon = 142.0

        result = find_field_by_gps(gps_lat, gps_lon, TEST_FIELDS)

        assert result is None

    def test_find_field_with_empty_list(self):
        """空のほ場リストでNoneを返す"""
        result = find_field_by_gps(42.88, 141.58, [])
        assert result is None


class TestGetFieldCandidates:
    """get_field_candidates関数のテスト"""

    @pytest.mark.skipif(not SHAPELY_AVAILABLE, reason="Shapely not available")
    def test_candidates_sorted_by_distance(self):
        """候補が距離順でソートされる"""
        # F001の中心付近
        gps_lat = 42.8825
        gps_lon = 141.580

        candidates = get_field_candidates(gps_lat, gps_lon, TEST_FIELDS, max_results=3)

        assert len(candidates) >= 1
        # 最初の候補がF001（最も近い/内部）
        assert candidates[0]["field_code"] == "F001"

        # 距離が昇順になっている
        for i in range(len(candidates) - 1):
            # is_inside優先、次に距離
            c1, c2 = candidates[i], candidates[i + 1]
            if c1["is_inside"] == c2["is_inside"]:
                assert c1["distance_m"] <= c2["distance_m"]

    @pytest.mark.skipif(not SHAPELY_AVAILABLE, reason="Shapely not available")
    def test_inside_field_has_zero_distance(self):
        """ポリゴン内のほ場は距離0でis_inside=True"""
        gps_lat = 42.8825
        gps_lon = 141.580

        candidates = get_field_candidates(gps_lat, gps_lon, TEST_FIELDS)

        inside_fields = [c for c in candidates if c["is_inside"]]
        assert len(inside_fields) >= 1
        assert inside_fields[0]["distance_m"] == 0.0

    def test_candidates_with_empty_list(self):
        """空のほ場リストで空リストを返す"""
        candidates = get_field_candidates(42.88, 141.58, [])
        assert candidates == []

    def test_candidates_max_results(self):
        """max_resultsで結果件数が制限される"""
        gps_lat = 42.88
        gps_lon = 141.58

        candidates = get_field_candidates(gps_lat, gps_lon, TEST_FIELDS, max_results=2)
        assert len(candidates) <= 2

    def test_candidates_skip_field_without_coords(self):
        """座標なしのほ場はスキップされる"""
        fields_with_empty = TEST_FIELDS + [FIELD_WITHOUT_COORDS]
        gps_lat = 42.88
        gps_lon = 141.58

        candidates = get_field_candidates(gps_lat, gps_lon, fields_with_empty)

        # F004は候補に含まれない
        field_codes = [c["field_code"] for c in candidates]
        assert "F004" not in field_codes


class TestFormatFieldCandidates:
    """format_field_candidates_for_display関数のテスト"""

    def test_format_inside_field(self):
        """is_inside=Trueの場合「現在地」と表示"""
        candidates = [{
            "id": 1,
            "field_code": "F001",
            "name": "北1号",
            "distance_m": 0.0,
            "is_inside": True,
        }]

        result = format_field_candidates_for_display(candidates)

        assert len(result) == 1
        display_name, field_id = result[0]
        assert field_id == 1
        assert "現在地" in display_name
        assert "F001" in display_name

    def test_format_nearby_field_meters(self):
        """1km未満の場合メートル表示"""
        candidates = [{
            "id": 2,
            "field_code": "F002",
            "name": "北2号",
            "distance_m": 150.5,
            "is_inside": False,
        }]

        result = format_field_candidates_for_display(candidates)

        display_name, _ = result[0]
        assert "150m" in display_name

    def test_format_distant_field_km(self):
        """1km以上の場合キロメートル表示"""
        candidates = [{
            "id": 3,
            "field_code": "F003",
            "name": "南1号",
            "distance_m": 2500.0,
            "is_inside": False,
        }]

        result = format_field_candidates_for_display(candidates)

        display_name, _ = result[0]
        assert "2.5km" in display_name

    def test_format_empty_candidates(self):
        """空リストで空リストを返す"""
        result = format_field_candidates_for_display([])
        assert result == []


class TestShapelyFallback:
    """Shapely未使用時のフォールバック動作テスト"""

    def test_candidates_work_without_shapely(self):
        """Shapely未使用でも重心ベースで動作する"""
        # この関数はShapely有無にかかわらず動作する
        # （内部でフォールバック処理がある）
        gps_lat = 42.88
        gps_lon = 141.58

        candidates = get_field_candidates(gps_lat, gps_lon, TEST_FIELDS)

        # 何らかの結果が返る
        assert isinstance(candidates, list)


# ============================================================
# パフォーマンステスト（STRtree）
# ============================================================

def _generate_scattered_fields(count: int) -> list:
    """テスト用: count個のほ場をランダムに生成（北海道範囲）"""
    rng = random.Random(42)  # 再現性のためseed固定
    fields = []
    for i in range(count):
        lat = rng.uniform(42.5, 43.5)
        lon = rng.uniform(141.0, 145.0)
        step = 0.001
        coords = [
            [lat, lon],
            [lat, lon + step],
            [lat + step, lon + step],
            [lat + step, lon],
        ]
        fields.append({
            'id': i + 1,
            'field_code': f'F{i:04d}',
            'name': f'テスト{i}号',
            'area_ha': 0.1,
            'coordinates_json': json.dumps(coords),
        })
    return fields


class TestGpsMatcherPerformance:
    """GPSマッチングのパフォーマンステスト"""

    @pytest.mark.slow
    @pytest.mark.skipif(not SHAPELY_AVAILABLE, reason="Shapely not available")
    def test_gps_candidates_performance_500_fields(self):
        """500ほ場のGPSマッチングが0.5秒以内に完了"""
        fields = _generate_scattered_fields(500)
        # 検索対象: フィールド群の中央付近
        target_lat = 43.0
        target_lon = 143.0
        t0 = time.time()
        candidates = get_field_candidates(target_lat, target_lon, fields, max_distance=50000)
        elapsed = time.time() - t0
        assert elapsed < 0.5
        assert isinstance(candidates, list)

    @pytest.mark.slow
    @pytest.mark.skipif(not SHAPELY_AVAILABLE, reason="Shapely not available")
    def test_find_field_performance_1000_fields(self):
        """1000ほ場のfind_field_by_gpsが0.2秒以内に完了"""
        fields = _generate_scattered_fields(1000)
        # 最初のほ場の内部を狙う
        first_coords = json.loads(fields[0]['coordinates_json'])
        target_lat = first_coords[0][0] + 0.0005
        target_lon = first_coords[0][1] + 0.0005
        t0 = time.time()
        result = find_field_by_gps(target_lat, target_lon, fields)
        elapsed = time.time() - t0
        assert elapsed < 0.2
        assert result is not None
