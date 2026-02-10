"""作付けポリゴン（crop_polygons）のテスト — Repository + API"""
import os
import json
import tempfile
import pytest

_test_db_fd, _test_db_path = tempfile.mkstemp(suffix='.db')
os.environ['DB_PATH'] = _test_db_path

from rotation_planner.common.db_access import (
    CropPolygonRepository,
    ensure_crop_polygons_table,
    get_db,
)
from rotation_planner.field.spatial import (
    geojson_to_shapely,
    calculate_geodesic_area_ha,
)

# 北海道十勝の四角形ポリゴン（約0.01度四方）
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

SAMPLE_GEOJSON_DICT = {
    "type": "Polygon",
    "coordinates": [[
        [143.20, 42.92],
        [143.21, 42.92],
        [143.21, 42.93],
        [143.20, 42.93],
        [143.20, 42.92],
    ]]
}


@pytest.fixture(autouse=True)
def setup_db(test_db):
    """各テスト前にDBを初期化（test_dbフィクスチャで独立DB使用）"""
    ensure_crop_polygons_table()
    with get_db() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO organizations (id, name, type) VALUES (1, 'テスト組織', 'JA')"
        )
        conn.execute(
            "INSERT OR IGNORE INTO users (id, username, password_hash, display_name, org_id, role) VALUES (1, 'testuser', 'hash', 'テストユーザー', 1, 'admin')"
        )
        conn.execute(
            "INSERT OR IGNORE INTO users (id, username, password_hash, display_name, org_id, role) VALUES (2, 'otheruser', 'hash', '他ユーザー', 1, 'farmer')"
        )
        conn.execute(
            "INSERT OR IGNORE INTO fields (id, user_id, name, field_code, area_ha) VALUES (1, 1, 'テスト圃場A', 'F001', 1.0)"
        )
        conn.execute(
            "INSERT OR IGNORE INTO fields (id, user_id, name, field_code, area_ha) VALUES (2, 1, 'テスト圃場B', 'F002', 2.0)"
        )
        conn.execute(
            "INSERT OR IGNORE INTO fields (id, user_id, name, field_code, area_ha) VALUES (3, 2, '他ユーザー圃場', 'F003', 1.5)"
        )
        conn.commit()
    yield


# =============================================================================
# CropPolygonRepository CRUD テスト
# =============================================================================

class TestCropPolygonCreate:
    def test_create_basic(self):
        pid = CropPolygonRepository.create(
            field_id=1, year=2025, crop_name="小麦",
            geometry=SAMPLE_GEOJSON, area_ha=1.5
        )
        assert pid > 0

    def test_create_with_notes(self):
        pid = CropPolygonRepository.create(
            field_id=1, year=2025, crop_name="大豆",
            geometry=SAMPLE_GEOJSON, area_ha=0.8,
            notes="転作2年目"
        )
        p = CropPolygonRepository.get_by_id(pid)
        assert p['notes'] == "転作2年目"
        assert p['crop_name'] == "大豆"
        assert p['year'] == 2025


class TestCropPolygonGetById:
    def test_get_existing(self):
        pid = CropPolygonRepository.create(
            field_id=1, year=2025, crop_name="小麦",
            geometry=SAMPLE_GEOJSON, area_ha=1.0
        )
        p = CropPolygonRepository.get_by_id(pid)
        assert p is not None
        assert p['field_id'] == 1
        assert p['year'] == 2025
        assert p['crop_name'] == "小麦"

    def test_get_nonexistent(self):
        p = CropPolygonRepository.get_by_id(9999)
        assert p is None


class TestCropPolygonGetByFieldYear:
    def test_get_by_field_year(self):
        CropPolygonRepository.create(
            field_id=1, year=2025, crop_name="小麦",
            geometry=SAMPLE_GEOJSON, area_ha=1.0
        )
        CropPolygonRepository.create(
            field_id=1, year=2025, crop_name="大豆",
            geometry=SAMPLE_GEOJSON_2, area_ha=0.8
        )
        CropPolygonRepository.create(
            field_id=1, year=2024, crop_name="ビート",
            geometry=SAMPLE_GEOJSON, area_ha=1.2
        )
        rows = CropPolygonRepository.get_by_field_year(1, 2025)
        assert len(rows) == 2

    def test_get_by_field_year_empty(self):
        rows = CropPolygonRepository.get_by_field_year(1, 2030)
        assert len(rows) == 0


class TestCropPolygonGetAllForUserYear:
    def test_get_all_for_user_year(self):
        CropPolygonRepository.create(
            field_id=1, year=2025, crop_name="小麦",
            geometry=SAMPLE_GEOJSON, area_ha=1.0
        )
        CropPolygonRepository.create(
            field_id=2, year=2025, crop_name="大豆",
            geometry=SAMPLE_GEOJSON_2, area_ha=0.8
        )
        # 他ユーザーのほ場
        CropPolygonRepository.create(
            field_id=3, year=2025, crop_name="ビート",
            geometry=SAMPLE_GEOJSON, area_ha=1.5
        )
        rows = CropPolygonRepository.get_all_for_user_year(1, 2025)
        assert len(rows) == 2

    def test_get_all_for_user_year_other_user(self):
        CropPolygonRepository.create(
            field_id=1, year=2025, crop_name="小麦",
            geometry=SAMPLE_GEOJSON, area_ha=1.0
        )
        rows = CropPolygonRepository.get_all_for_user_year(2, 2025)
        assert len(rows) == 0


class TestCropPolygonUpdate:
    def test_update_crop_name(self):
        pid = CropPolygonRepository.create(
            field_id=1, year=2025, crop_name="小麦",
            geometry=SAMPLE_GEOJSON, area_ha=1.0
        )
        result = CropPolygonRepository.update(pid, crop_name="大豆")
        assert result is True
        p = CropPolygonRepository.get_by_id(pid)
        assert p['crop_name'] == "大豆"

    def test_update_multiple_fields(self):
        pid = CropPolygonRepository.create(
            field_id=1, year=2025, crop_name="小麦",
            geometry=SAMPLE_GEOJSON, area_ha=1.0
        )
        CropPolygonRepository.update(pid, year=2026, notes="更新テスト")
        p = CropPolygonRepository.get_by_id(pid)
        assert p['year'] == 2026
        assert p['notes'] == "更新テスト"

    def test_update_no_fields(self):
        pid = CropPolygonRepository.create(
            field_id=1, year=2025, crop_name="小麦",
            geometry=SAMPLE_GEOJSON, area_ha=1.0
        )
        result = CropPolygonRepository.update(pid)
        assert result is False

    def test_update_nonexistent(self):
        result = CropPolygonRepository.update(9999, crop_name="大豆")
        assert result is False


class TestCropPolygonDelete:
    def test_delete(self):
        pid = CropPolygonRepository.create(
            field_id=1, year=2025, crop_name="小麦",
            geometry=SAMPLE_GEOJSON, area_ha=1.0
        )
        assert CropPolygonRepository.delete(pid) is True
        assert CropPolygonRepository.get_by_id(pid) is None

    def test_delete_nonexistent(self):
        assert CropPolygonRepository.delete(9999) is False


# =============================================================================
# area_ha 自動計算テスト
# =============================================================================

class TestAreaHaCalculation:
    def test_area_from_geojson(self):
        """GeoJSONからarea_haが正しく計算できることを確認"""
        polygon = geojson_to_shapely(SAMPLE_GEOJSON)
        area_ha = calculate_geodesic_area_ha(polygon)
        assert area_ha > 0
        # 約0.01度四方 ≈ 約80-100 ha
        assert 50 < area_ha < 150

    def test_area_stored_in_db(self):
        """area_haがDBに正しく保存されることを確認"""
        polygon = geojson_to_shapely(SAMPLE_GEOJSON)
        area_ha = calculate_geodesic_area_ha(polygon)

        pid = CropPolygonRepository.create(
            field_id=1, year=2025, crop_name="小麦",
            geometry=SAMPLE_GEOJSON, area_ha=area_ha
        )
        p = CropPolygonRepository.get_by_id(pid)
        assert abs(p['area_ha'] - area_ha) < 0.001


# =============================================================================
# 前年度コピー機能テスト
# =============================================================================

class TestCropPolygonCopyFromPreviousYear:
    def test_copy_basic(self):
        CropPolygonRepository.create(
            field_id=1, year=2025, crop_name="小麦",
            geometry=SAMPLE_GEOJSON, area_ha=1.0
        )
        CropPolygonRepository.create(
            field_id=2, year=2025, crop_name="大豆",
            geometry=SAMPLE_GEOJSON_2, area_ha=0.8
        )
        count = CropPolygonRepository.copy_from_previous_year(
            user_id=1, from_year=2025, to_year=2026
        )
        assert count == 2

        # コピー先にデータが存在
        rows = CropPolygonRepository.get_all_for_user_year(1, 2026)
        assert len(rows) == 2
        crop_names = {r['crop_name'] for r in rows}
        assert crop_names == {"小麦", "大豆"}

    def test_copy_no_data(self):
        count = CropPolygonRepository.copy_from_previous_year(
            user_id=1, from_year=2020, to_year=2021
        )
        assert count == 0

    def test_copy_does_not_include_other_user(self):
        """他ユーザーのポリゴンはコピーされない"""
        CropPolygonRepository.create(
            field_id=1, year=2025, crop_name="小麦",
            geometry=SAMPLE_GEOJSON, area_ha=1.0
        )
        CropPolygonRepository.create(
            field_id=3, year=2025, crop_name="ビート",
            geometry=SAMPLE_GEOJSON, area_ha=1.5
        )
        count = CropPolygonRepository.copy_from_previous_year(
            user_id=1, from_year=2025, to_year=2026
        )
        assert count == 1  # ユーザー1のもののみ

    def test_copy_preserves_original(self):
        """コピー後も元データは残っている"""
        CropPolygonRepository.create(
            field_id=1, year=2025, crop_name="小麦",
            geometry=SAMPLE_GEOJSON, area_ha=1.0
        )
        CropPolygonRepository.copy_from_previous_year(
            user_id=1, from_year=2025, to_year=2026
        )
        orig = CropPolygonRepository.get_all_for_user_year(1, 2025)
        assert len(orig) == 1


# =============================================================================
# API エンドポイントテスト
# =============================================================================

class TestCropPolygonAPI:
    """FastAPI TestClient を使ったAPIテスト"""

    @pytest.fixture
    def client(self):
        """テスト用FastAPIクライアント"""
        os.environ.setdefault("JWT_SECRET", "test-secret-key-for-testing-32bytes!")
        import sys
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
        from api.main import app
        from fastapi.testclient import TestClient
        return TestClient(app)

    @pytest.fixture
    def auth_headers(self):
        """認証ヘッダー取得（JWTトークンを直接生成）"""
        import jwt
        from datetime import datetime, timedelta, timezone
        secret = os.environ.get("JWT_SECRET", "test-secret-key-for-testing-32bytes!")
        payload = {
            "sub": "1",
            "username": "testuser",
            "role": "admin",
            "exp": datetime.now(timezone.utc) + timedelta(hours=1)
        }
        token = jwt.encode(payload, secret, algorithm="HS256")
        return {"Authorization": f"Bearer {token}"}

    def test_create_and_get(self, client, auth_headers):
        """POST→GET の基本フロー"""
        resp = client.post("/api/crop-polygons", json={
            "field_id": 1,
            "year": 2025,
            "crop_name": "小麦",
            "geometry": SAMPLE_GEOJSON_DICT,
        }, headers=auth_headers)
        assert resp.status_code == 201
        data = resp.json()
        assert data["crop_name"] == "小麦"
        assert data["area_ha"] > 0

        # GET by id
        polygon_id = data["id"]
        resp2 = client.get(f"/api/crop-polygons/{polygon_id}", headers=auth_headers)
        assert resp2.status_code == 200
        assert resp2.json()["id"] == polygon_id

    def test_list_by_year(self, client, auth_headers):
        """年度でのリスト取得"""
        client.post("/api/crop-polygons", json={
            "field_id": 1, "year": 2025, "crop_name": "小麦",
            "geometry": SAMPLE_GEOJSON_DICT,
        }, headers=auth_headers)
        resp = client.get("/api/crop-polygons?year=2025", headers=auth_headers)
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    def test_list_requires_year(self, client, auth_headers):
        """yearなしはエラー"""
        resp = client.get("/api/crop-polygons", headers=auth_headers)
        assert resp.status_code == 400
