"""
CropHistoryRepository 単体テスト
"""
import pytest
from rotation_planner.common.db_access import FieldRepository, CropHistoryRepository


@pytest.mark.db
def test_ch01_add_history_success(test_db, farmer_state, sample_field_data):
    """CH-01: add_history 正常登録"""
    # ほ場作成
    field_id = FieldRepository.create_field(farmer_state["user_id"], sample_field_data)

    # 作付履歴追加
    history_id = CropHistoryRepository.add_history(field_id, "2023", "大豆", False)

    assert isinstance(history_id, int)
    assert history_id > 0

    # 登録されたデータを確認
    history = CropHistoryRepository.get_history(field_id)
    assert len(history) == 1
    assert history[0]["year"] == "2023"
    assert history[0]["crop"] == "大豆"
    assert history[0]["is_inferred"] == 0


@pytest.mark.db
def test_ch02_add_history_replace(test_db, farmer_state, sample_field_data):
    """CH-02: add_history 同一field_id+year上書き（REPLACE）"""
    # ほ場作成
    field_id = FieldRepository.create_field(farmer_state["user_id"], sample_field_data)

    # 1回目: 大豆
    CropHistoryRepository.add_history(field_id, "2023", "大豆", False)

    # 2回目: 同じ年に上書き（てんさい）
    CropHistoryRepository.add_history(field_id, "2023", "てんさい", False)

    # 上書きされていることを確認
    history = CropHistoryRepository.get_history(field_id)
    assert len(history) == 1
    assert history[0]["year"] == "2023"
    assert history[0]["crop"] == "てんさい"


@pytest.mark.db
def test_ch03_get_history_sorted_by_year(test_db, farmer_state, sample_field_data):
    """CH-03: get_history 年度順ソート"""
    # ほ場作成
    field_id = FieldRepository.create_field(farmer_state["user_id"], sample_field_data)

    # 順不同で追加
    CropHistoryRepository.add_history(field_id, "2025", "春小麦", False)
    CropHistoryRepository.add_history(field_id, "2023", "大豆", False)
    CropHistoryRepository.add_history(field_id, "2024", "てんさい", False)

    # 取得して年度順を確認
    history = CropHistoryRepository.get_history(field_id)
    assert len(history) == 3
    assert history[0]["year"] == "2023"
    assert history[1]["year"] == "2024"
    assert history[2]["year"] == "2025"


@pytest.mark.db
def test_ch04_delete_history(test_db, farmer_state, sample_field_data):
    """CH-04: delete_history 特定年度削除"""
    # ほ場作成
    field_id = FieldRepository.create_field(farmer_state["user_id"], sample_field_data)

    # 複数年度追加
    CropHistoryRepository.add_history(field_id, "2023", "大豆", False)
    CropHistoryRepository.add_history(field_id, "2024", "てんさい", False)

    # 2023年度を削除
    result = CropHistoryRepository.delete_history(field_id, "2023")

    assert result is True

    # 削除されたことを確認
    history = CropHistoryRepository.get_history(field_id)
    assert len(history) == 1
    assert history[0]["year"] == "2024"


@pytest.mark.db
def test_ch05_bulk_update_history(test_db, farmer_state, sample_field_data):
    """CH-05: bulk_update_history 複数レコード更新"""
    # ほ場作成
    field_id = FieldRepository.create_field(farmer_state["user_id"], sample_field_data)

    # 一括更新データ
    updates = [
        {"field_id": field_id, "year": "2023", "crop": "大豆"},
        {"field_id": field_id, "year": "2024", "crop": "てんさい"},
        {"field_id": field_id, "year": "2025", "crop": "春小麦"},
    ]

    count = CropHistoryRepository.bulk_update_history(updates)

    assert count == 3

    # 登録されたデータを確認
    history = CropHistoryRepository.get_history(field_id)
    assert len(history) == 3


@pytest.mark.db
def test_ch06_bulk_update_history_empty_list(test_db):
    """CH-06: bulk_update_history 空リスト → 0"""
    count = CropHistoryRepository.bulk_update_history([])

    assert count == 0


@pytest.mark.db
def test_ch07_get_all_history_for_user_isolation(test_db, farmer_state, admin_state, sample_field_data):
    """CH-07: get_all_history_for_user ユーザー分離"""
    # farmer_state のほ場作成
    farmer_field_data = sample_field_data.copy()
    farmer_field_data["field_code"] = "FARMER001"
    farmer_field_id = FieldRepository.create_field(farmer_state["user_id"], farmer_field_data)
    CropHistoryRepository.add_history(farmer_field_id, "2023", "大豆", False)

    # admin_state のほ場作成
    admin_field_data = sample_field_data.copy()
    admin_field_data["field_code"] = "ADMIN001"
    admin_field_id = FieldRepository.create_field(admin_state["user_id"], admin_field_data)
    CropHistoryRepository.add_history(admin_field_id, "2023", "てんさい", False)

    # farmer_state のユーザーの履歴のみ取得
    farmer_history = CropHistoryRepository.get_all_history_for_user(farmer_state["user_id"])
    assert len(farmer_history) == 1
    assert farmer_history[0]["field_code"] == "FARMER001"

    # admin_state のユーザーの履歴のみ取得
    admin_history = CropHistoryRepository.get_all_history_for_user(admin_state["user_id"])
    assert len(admin_history) == 1
    assert admin_history[0]["field_code"] == "ADMIN001"
