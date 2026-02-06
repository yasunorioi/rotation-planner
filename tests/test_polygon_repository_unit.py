"""
PaddyPolygonRepository / CropPolygonRepository のユニットテスト
cmd_072 Phase 1: subtask_171
"""
import pytest
from rotation_planner.common.db_access import (
    FieldRepository,
    PaddyPolygonRepository,
    CropPolygonRepository,
)
from rotation_planner.common.exceptions import ForeignKeyViolationError


# テスト用GeoJSON
TEST_GEOJSON = '{"type":"Polygon","coordinates":[[[141.0,43.0],[141.01,43.0],[141.01,43.01],[141.0,43.01],[141.0,43.0]]]}'
TEST_GEOJSON_2 = '{"type":"Polygon","coordinates":[[[141.1,43.1],[141.11,43.1],[141.11,43.11],[141.1,43.11],[141.1,43.1]]]}'


# =============================================================================
# ヘルパー: テスト用ほ場を作成
# =============================================================================
def _create_test_field(user_id, field_code="TF001"):
    """テスト用ほ場を作成し、field_id を返す"""
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


# =============================================================================
# ■ PaddyPolygonRepository テスト（PP-01〜PP-10）
# =============================================================================


# PP-01: create - 正常作成 → id返却
def test_pp01_create(test_db, admin_state):
    """PP-01: 水田ポリゴンを正常に作成し、IDが返却される"""
    user_id = admin_state["user_id"]
    field_id = _create_test_field(user_id)

    polygon_id = PaddyPolygonRepository.create(
        field_id=field_id,
        geometry=TEST_GEOJSON,
        area_ha=0.5,
    )

    assert isinstance(polygon_id, int)
    assert polygon_id > 0


# PP-02: get_by_id - 存在するID → dict返却
def test_pp02_get_by_id_exists(test_db, admin_state):
    """PP-02: 存在するIDでポリゴンを取得し、dictが返る"""
    user_id = admin_state["user_id"]
    field_id = _create_test_field(user_id)
    polygon_id = PaddyPolygonRepository.create(
        field_id=field_id,
        geometry=TEST_GEOJSON,
        area_ha=0.5,
        source="maff",
        notes="テスト水田",
    )

    result = PaddyPolygonRepository.get_by_id(polygon_id)

    assert result is not None
    assert isinstance(result, dict)
    assert result["id"] == polygon_id
    assert result["field_id"] == field_id
    assert result["geometry"] == TEST_GEOJSON
    assert result["area_ha"] == 0.5
    assert result["is_converted"] == 0
    assert result["source"] == "maff"
    assert result["notes"] == "テスト水田"


# PP-03: get_by_id - 存在しないID → None
def test_pp03_get_by_id_not_exists(test_db):
    """PP-03: 存在しないIDではNoneが返る"""
    result = PaddyPolygonRepository.get_by_id(99999)

    assert result is None


# PP-04: get_by_field - ほ場IDでフィルタ → リスト
def test_pp04_get_by_field(test_db, admin_state):
    """PP-04: ほ場IDでフィルタしてリストが返る"""
    user_id = admin_state["user_id"]
    field_id_1 = _create_test_field(user_id, "TF001")
    field_id_2 = _create_test_field(user_id, "TF002")

    PaddyPolygonRepository.create(field_id=field_id_1, geometry=TEST_GEOJSON, area_ha=0.3)
    PaddyPolygonRepository.create(field_id=field_id_1, geometry=TEST_GEOJSON_2, area_ha=0.4)
    PaddyPolygonRepository.create(field_id=field_id_2, geometry=TEST_GEOJSON, area_ha=0.5)

    results = PaddyPolygonRepository.get_by_field(field_id_1)

    assert isinstance(results, list)
    assert len(results) == 2
    assert all(r["field_id"] == field_id_1 for r in results)


# PP-05: get_all_for_user - ユーザーID → 全水田ポリゴン
def test_pp05_get_all_for_user(test_db, admin_state):
    """PP-05: ユーザーIDで全水田ポリゴンを取得"""
    user_id = admin_state["user_id"]
    field_id_1 = _create_test_field(user_id, "TF001")
    field_id_2 = _create_test_field(user_id, "TF002")

    PaddyPolygonRepository.create(field_id=field_id_1, geometry=TEST_GEOJSON, area_ha=0.3)
    PaddyPolygonRepository.create(field_id=field_id_2, geometry=TEST_GEOJSON_2, area_ha=0.4)

    results = PaddyPolygonRepository.get_all_for_user(user_id)

    assert isinstance(results, list)
    assert len(results) == 2


# PP-06: update - 1フィールド更新 → True
def test_pp06_update_single_field(test_db, admin_state):
    """PP-06: 1フィールドの更新が成功しTrueが返る"""
    user_id = admin_state["user_id"]
    field_id = _create_test_field(user_id)
    polygon_id = PaddyPolygonRepository.create(
        field_id=field_id, geometry=TEST_GEOJSON, area_ha=0.5
    )

    success = PaddyPolygonRepository.update(polygon_id, area_ha=1.0)

    assert success is True
    updated = PaddyPolygonRepository.get_by_id(polygon_id)
    assert updated["area_ha"] == 1.0


# PP-07: update - is_converted フラグ変更 → 値確認
def test_pp07_update_is_converted(test_db, admin_state):
    """PP-07: is_convertedフラグを変更し値が正しく反映される"""
    user_id = admin_state["user_id"]
    field_id = _create_test_field(user_id)
    polygon_id = PaddyPolygonRepository.create(
        field_id=field_id, geometry=TEST_GEOJSON, area_ha=0.5, is_converted=False
    )

    # False → True に変更
    success = PaddyPolygonRepository.update(polygon_id, is_converted=True)

    assert success is True
    updated = PaddyPolygonRepository.get_by_id(polygon_id)
    assert updated["is_converted"] == 1


# PP-08: delete - 正常削除 → True
def test_pp08_delete(test_db, admin_state):
    """PP-08: 正常に削除しTrueが返る"""
    user_id = admin_state["user_id"]
    field_id = _create_test_field(user_id)
    polygon_id = PaddyPolygonRepository.create(
        field_id=field_id, geometry=TEST_GEOJSON, area_ha=0.5
    )

    success = PaddyPolygonRepository.delete(polygon_id)

    assert success is True
    assert PaddyPolygonRepository.get_by_id(polygon_id) is None


# PP-09: get_converted - 畑地化済のみ取得
def test_pp09_get_converted(test_db, admin_state):
    """PP-09: 畑地化済み(is_converted=1)のポリゴンのみ取得"""
    user_id = admin_state["user_id"]
    field_id = _create_test_field(user_id)

    PaddyPolygonRepository.create(
        field_id=field_id, geometry=TEST_GEOJSON, area_ha=0.3, is_converted=True
    )
    PaddyPolygonRepository.create(
        field_id=field_id, geometry=TEST_GEOJSON_2, area_ha=0.4, is_converted=False
    )

    converted = PaddyPolygonRepository.get_converted(user_id)

    assert isinstance(converted, list)
    assert len(converted) == 1
    assert converted[0]["is_converted"] == 1


# PP-10: get_paddy - 水田のみ取得
def test_pp10_get_paddy(test_db, admin_state):
    """PP-10: 水田(is_converted=0)のポリゴンのみ取得"""
    user_id = admin_state["user_id"]
    field_id = _create_test_field(user_id)

    PaddyPolygonRepository.create(
        field_id=field_id, geometry=TEST_GEOJSON, area_ha=0.3, is_converted=True
    )
    PaddyPolygonRepository.create(
        field_id=field_id, geometry=TEST_GEOJSON_2, area_ha=0.4, is_converted=False
    )

    paddy = PaddyPolygonRepository.get_paddy(user_id)

    assert isinstance(paddy, list)
    assert len(paddy) == 1
    assert paddy[0]["is_converted"] == 0


# =============================================================================
# ■ CropPolygonRepository テスト（CP-01〜CP-10）
# =============================================================================


# CP-01: create - 正常作成 → id返却
def test_cp01_create(test_db, admin_state):
    """CP-01: 作物ポリゴンを正常に作成し、IDが返却される"""
    user_id = admin_state["user_id"]
    field_id = _create_test_field(user_id)

    polygon_id = CropPolygonRepository.create(
        field_id=field_id,
        year=2026,
        crop_name="春小麦",
        geometry=TEST_GEOJSON,
        area_ha=0.5,
    )

    assert isinstance(polygon_id, int)
    assert polygon_id > 0


# CP-02: get_by_id - 存在するID → dict返却
def test_cp02_get_by_id_exists(test_db, admin_state):
    """CP-02: 存在するIDでポリゴンを取得し、dictが返る"""
    user_id = admin_state["user_id"]
    field_id = _create_test_field(user_id)
    polygon_id = CropPolygonRepository.create(
        field_id=field_id,
        year=2026,
        crop_name="てんさい",
        geometry=TEST_GEOJSON,
        area_ha=0.8,
        notes="テスト作物",
    )

    result = CropPolygonRepository.get_by_id(polygon_id)

    assert result is not None
    assert isinstance(result, dict)
    assert result["id"] == polygon_id
    assert result["field_id"] == field_id
    assert result["year"] == 2026
    assert result["crop_name"] == "てんさい"
    assert result["geometry"] == TEST_GEOJSON
    assert result["area_ha"] == 0.8
    assert result["notes"] == "テスト作物"


# CP-03: get_by_id - 存在しないID → None
def test_cp03_get_by_id_not_exists(test_db):
    """CP-03: 存在しないIDではNoneが返る"""
    result = CropPolygonRepository.get_by_id(99999)

    assert result is None


# CP-04: get_by_field_year - ほ場+年度でフィルタ
def test_cp04_get_by_field_year(test_db, admin_state):
    """CP-04: ほ場IDと年度でフィルタしてリストが返る"""
    user_id = admin_state["user_id"]
    field_id = _create_test_field(user_id)

    CropPolygonRepository.create(field_id=field_id, year=2025, crop_name="大豆", geometry=TEST_GEOJSON, area_ha=0.3)
    CropPolygonRepository.create(field_id=field_id, year=2026, crop_name="春小麦", geometry=TEST_GEOJSON, area_ha=0.4)
    CropPolygonRepository.create(field_id=field_id, year=2026, crop_name="てんさい", geometry=TEST_GEOJSON_2, area_ha=0.5)

    results = CropPolygonRepository.get_by_field_year(field_id, 2026)

    assert isinstance(results, list)
    assert len(results) == 2
    assert all(r["year"] == 2026 for r in results)


# CP-05: get_all_for_user_year - ユーザー+年度でフィルタ
def test_cp05_get_all_for_user_year(test_db, admin_state):
    """CP-05: ユーザーIDと年度で全作物ポリゴンを取得"""
    user_id = admin_state["user_id"]
    field_id_1 = _create_test_field(user_id, "TF001")
    field_id_2 = _create_test_field(user_id, "TF002")

    CropPolygonRepository.create(field_id=field_id_1, year=2026, crop_name="春小麦", geometry=TEST_GEOJSON, area_ha=0.3)
    CropPolygonRepository.create(field_id=field_id_2, year=2026, crop_name="大豆", geometry=TEST_GEOJSON_2, area_ha=0.4)
    CropPolygonRepository.create(field_id=field_id_1, year=2025, crop_name="てんさい", geometry=TEST_GEOJSON, area_ha=0.5)

    results = CropPolygonRepository.get_all_for_user_year(user_id, 2026)

    assert isinstance(results, list)
    assert len(results) == 2
    assert all(r["year"] == 2026 for r in results)


# CP-06: update - crop_name変更 → 確認
def test_cp06_update_crop_name(test_db, admin_state):
    """CP-06: crop_nameを変更し値が正しく反映される"""
    user_id = admin_state["user_id"]
    field_id = _create_test_field(user_id)
    polygon_id = CropPolygonRepository.create(
        field_id=field_id, year=2026, crop_name="春小麦", geometry=TEST_GEOJSON, area_ha=0.5
    )

    success = CropPolygonRepository.update(polygon_id, crop_name="秋小麦")

    assert success is True
    updated = CropPolygonRepository.get_by_id(polygon_id)
    assert updated["crop_name"] == "秋小麦"


# CP-07: delete - 正常削除 → True
def test_cp07_delete(test_db, admin_state):
    """CP-07: 正常に削除しTrueが返る"""
    user_id = admin_state["user_id"]
    field_id = _create_test_field(user_id)
    polygon_id = CropPolygonRepository.create(
        field_id=field_id, year=2026, crop_name="春小麦", geometry=TEST_GEOJSON, area_ha=0.5
    )

    success = CropPolygonRepository.delete(polygon_id)

    assert success is True
    assert CropPolygonRepository.get_by_id(polygon_id) is None


# CP-08: copy_from_previous_year - コピー → 件数確認
def test_cp08_copy_from_previous_year(test_db, admin_state):
    """CP-08: 前年度の作物ポリゴンをコピーし件数が一致する"""
    user_id = admin_state["user_id"]
    field_id_1 = _create_test_field(user_id, "TF001")
    field_id_2 = _create_test_field(user_id, "TF002")

    CropPolygonRepository.create(field_id=field_id_1, year=2025, crop_name="春小麦", geometry=TEST_GEOJSON, area_ha=0.3)
    CropPolygonRepository.create(field_id=field_id_2, year=2025, crop_name="大豆", geometry=TEST_GEOJSON_2, area_ha=0.4)

    count = CropPolygonRepository.copy_from_previous_year(user_id, from_year=2025, to_year=2026)

    assert count == 2

    # コピー先に正しくデータがあるか確認
    copied = CropPolygonRepository.get_all_for_user_year(user_id, 2026)
    assert len(copied) == 2
    assert all(r["year"] == 2026 for r in copied)


# CP-09: copy_from_previous_year - コピー元なし → 0件
def test_cp09_copy_from_previous_year_empty(test_db, admin_state):
    """CP-09: コピー元にデータがない場合は0件が返る"""
    user_id = admin_state["user_id"]

    count = CropPolygonRepository.copy_from_previous_year(user_id, from_year=2020, to_year=2021)

    assert count == 0


# CP-10: create + FK違反 - 存在しないfield_id → エラー
def test_cp10_create_fk_violation(test_db):
    """CP-10: 存在しないfield_idで作成するとForeignKeyViolationErrorが発生"""
    with pytest.raises(ForeignKeyViolationError):
        CropPolygonRepository.create(
            field_id=99999,
            year=2026,
            crop_name="春小麦",
            geometry=TEST_GEOJSON,
            area_ha=0.5,
        )
