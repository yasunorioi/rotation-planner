"""
FieldRepository 単体テスト
"""
import pytest
from rotation_planner.common.db_access import FieldRepository


@pytest.mark.db
def test_f01_create_field_success(test_db, farmer_state, sample_field_data):
    """F-01: create_field 正常登録 → lastrowid返却"""
    field_id = FieldRepository.create_field(farmer_state["user_id"], sample_field_data)

    assert isinstance(field_id, int)
    assert field_id > 0

    # 作成されたデータを確認
    field = FieldRepository.get_field(field_id)
    assert field is not None
    assert field["field_code"] == sample_field_data["field_code"]
    assert field["area_ha"] == sample_field_data["area_ha"]


@pytest.mark.db
def test_f02_create_field_duplicate_code(test_db, farmer_state, sample_field_data):
    """F-02: create_field field_code重複 → IntegrityError"""
    # 1回目: 成功
    FieldRepository.create_field(farmer_state["user_id"], sample_field_data)

    # 2回目: 同じfield_codeで重複エラー
    from rotation_planner.common.exceptions import DuplicateKeyError
    with pytest.raises(DuplicateKeyError):
        FieldRepository.create_field(farmer_state["user_id"], sample_field_data)


@pytest.mark.db
def test_f03_create_field_missing_required(test_db, farmer_state):
    """F-03: create_field 必須項目欠落 → エラー"""
    incomplete_data = {
        "district": "テスト地区",
        # field_code と area_ha が欠落
    }

    with pytest.raises(KeyError):
        FieldRepository.create_field(farmer_state["user_id"], incomplete_data)


@pytest.mark.db
def test_f04_update_field_success(test_db, farmer_state, sample_field_data):
    """F-04: update_field 正常更新 → True"""
    field_id = FieldRepository.create_field(farmer_state["user_id"], sample_field_data)

    update_data = {
        "name": "更新後のほ場名",
        "area_ha": 3.0,
    }
    result = FieldRepository.update_field(field_id, update_data)

    assert result is True

    # 更新されたデータを確認
    field = FieldRepository.get_field(field_id)
    assert field["name"] == "更新後のほ場名"
    assert field["area_ha"] == 3.0


@pytest.mark.db
def test_f05_update_field_not_found(test_db):
    """F-05: update_field 存在しないID → False"""
    result = FieldRepository.update_field(99999, {"name": "存在しない"})

    assert result is False


@pytest.mark.db
def test_f06_delete_field_success(test_db, farmer_state, sample_field_data):
    """F-06: delete_field 正常削除 → True"""
    field_id = FieldRepository.create_field(farmer_state["user_id"], sample_field_data)

    result = FieldRepository.delete_field(field_id)

    assert result is True

    # 削除されたことを確認
    field = FieldRepository.get_field(field_id)
    assert field is None


@pytest.mark.db
def test_f07_delete_field_not_found(test_db):
    """F-07: delete_field 存在しないID → False"""
    result = FieldRepository.delete_field(99999)

    assert result is False


@pytest.mark.db
def test_f08_get_field_exists(test_db, farmer_state, sample_field_data):
    """F-08: get_field 存在するID → Dict"""
    field_id = FieldRepository.create_field(farmer_state["user_id"], sample_field_data)

    field = FieldRepository.get_field(field_id)

    assert field is not None
    assert isinstance(field, dict)
    assert field["id"] == field_id
    assert field["field_code"] == sample_field_data["field_code"]


@pytest.mark.db
def test_f09_get_field_not_found(test_db):
    """F-09: get_field 存在しないID → None"""
    field = FieldRepository.get_field(99999)

    assert field is None


@pytest.mark.db
def test_f10_get_field_with_history(test_db, farmer_state, sample_field_data):
    """F-10: get_field_with_history 履歴付き取得"""
    from rotation_planner.common.db_access import CropHistoryRepository

    # ほ場作成
    field_id = FieldRepository.create_field(farmer_state["user_id"], sample_field_data)

    # 作付履歴追加
    CropHistoryRepository.add_history(field_id, 2023, "大豆", False)
    CropHistoryRepository.add_history(field_id, 2024, "てんさい", False)

    # 履歴付きで取得
    field_with_history = FieldRepository.get_field_with_history(field_id)

    assert field_with_history is not None
    assert "history" in field_with_history
    assert len(field_with_history["history"]) == 2


@pytest.mark.db
def test_f11_get_fields_empty_for_user_zero(test_db):
    """F-11: get_fields user_id=0 → 空リスト"""
    fields = FieldRepository.get_fields(0)

    assert isinstance(fields, list)
    assert len(fields) == 0
