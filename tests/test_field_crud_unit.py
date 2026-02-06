"""
field/crud.py のテスト
"""
import pytest
import json
import pandas as pd
from rotation_planner.field.crud import (
    get_user_id_from_state,
    get_next_field_id,
    get_user_fields,
    fields_to_dataframe,
    register_field_with_state,
    delete_field_with_state,
)
from rotation_planner.common.db_access import FieldRepository


# =============================================================================
# FC-01: get_next_field_id 初回 → "F001"
# =============================================================================
def test_fc01_get_next_field_id_first(test_db, admin_state):
    """FC-01: ほ場が存在しない場合、初回IDとして"F001"を返す"""
    user_id = admin_state['user_id']

    next_id = get_next_field_id(user_id, prefix="F")

    assert next_id == "F001"


# =============================================================================
# FC-02: get_next_field_id 連番 → max+1
# =============================================================================
def test_fc02_get_next_field_id_sequential(test_db, admin_state):
    """FC-02: F001が存在する場合、F002を返す"""
    user_id = admin_state['user_id']

    # 既存ほ場を作成（F001）
    field_data = {
        'field_code': 'F001',
        'district': 'テスト地区',
        'name': 'テストほ場1',
        'area_ha': 1.0,
        'beet_forbidden': False,
        'coordinates_json': None,
        'notes': None,
    }
    FieldRepository.create_field(user_id, field_data)

    next_id = get_next_field_id(user_id, prefix="F")

    assert next_id == "F002"


# =============================================================================
# FC-03: get_user_id_from_state 有効state → user_id
# =============================================================================
def test_fc03_get_user_id_from_state_valid(admin_state):
    """FC-03: 有効なstateからuser_idを取得できる"""
    user_id = get_user_id_from_state(admin_state)

    assert isinstance(user_id, int)
    assert user_id == admin_state['user_id']


# =============================================================================
# FC-04: get_user_id_from_state 空state → None
# =============================================================================
def test_fc04_get_user_id_from_state_empty():
    """FC-04: 空stateではNoneを返す"""
    empty_state = {}

    user_id = get_user_id_from_state(empty_state)

    assert user_id is None


# =============================================================================
# FC-05: fields_to_dataframe 変換 → DataFrame
# =============================================================================
def test_fc05_fields_to_dataframe_conversion(test_db, admin_state):
    """FC-05: ほ場リストをDataFrameに変換できる"""
    user_id = admin_state['user_id']

    # テスト用ほ場を作成
    field_data = {
        'field_code': 'TEST01',
        'district': 'テスト地区',
        'name': 'テストほ場',
        'area_ha': 2.5,
        'beet_forbidden': False,
        'coordinates_json': None,
        'notes': 'テスト',
    }
    FieldRepository.create_field(user_id, field_data)

    # ほ場リストを取得（正しいメソッド名）
    fields = get_user_fields(user_id)

    # DataFrameに変換
    df = fields_to_dataframe(fields)

    assert isinstance(df, pd.DataFrame)
    assert len(df) == 1
    # 日本語カラム名を確認
    assert 'ほ場ID' in df.columns
    assert '地区' in df.columns
    assert 'ほ場名' in df.columns
    assert df.iloc[0]['ほ場ID'] == 'TEST01'


# =============================================================================
# FC-06: fields_to_dataframe 空リスト → 空DataFrame
# =============================================================================
def test_fc06_fields_to_dataframe_empty():
    """FC-06: 空リストから空DataFrameを生成する"""
    empty_fields = []

    df = fields_to_dataframe(empty_fields)

    assert isinstance(df, pd.DataFrame)
    assert len(df) == 0


# =============================================================================
# FC-07: register_field 正常登録 → 成功メッセージ
# =============================================================================
def test_fc07_register_field_success(test_db, admin_state):
    """FC-07: 正常なほ場登録で成功メッセージを返す"""
    # テスト用の座標データ（[lat, lng] 形式）
    # 北海道の100m四方の正方形を想定
    test_coords = [
        [43.0, 141.0],
        [43.0, 141.001],
        [43.001, 141.001],
        [43.001, 141.0]
    ]
    coords_json = json.dumps(test_coords)

    # register_field_with_state の戻り値: (df, message, map_json, next_id)
    df, message, map_json, next_id = register_field_with_state(
        field_id='TEST001',
        district='テスト地区',
        name='テストほ場',
        crop_year='R7',
        crop='じゃがいも',
        beet_forbidden=False,
        coords_json=coords_json,
        user_state=admin_state
    )

    assert isinstance(df, pd.DataFrame)
    assert isinstance(message, str)
    assert "登録しました" in message
    assert len(df) == 1


# =============================================================================
# FC-08: register_field 未ログイン → エラーメッセージ
# =============================================================================
def test_fc08_register_field_not_logged_in(test_db):
    """FC-08: 未ログイン状態でエラーメッセージを返す"""
    empty_state = {}

    # テスト用の座標データ（[lat, lng] 形式）
    test_coords = [[43.0, 141.0], [43.0, 141.001], [43.001, 141.001]]
    coords_json = json.dumps(test_coords)

    # register_field_with_state の戻り値: (df, message, map_json, next_id)
    df, message, map_json, next_id = register_field_with_state(
        field_id='TEST002',
        district='テスト地区',
        name='テストほ場2',
        crop_year='R7',
        crop='',
        beet_forbidden=False,
        coords_json=coords_json,
        user_state=empty_state
    )

    assert isinstance(df, pd.DataFrame)
    assert isinstance(message, str)
    assert "ログイン" in message


# =============================================================================
# FC-09: delete_field 正常削除 → 成功メッセージ
# =============================================================================
def test_fc09_delete_field_success(test_db, admin_state):
    """FC-09: 正常なほ場削除で成功メッセージを返す"""
    user_id = admin_state['user_id']

    # まずほ場を登録
    field_data = {
        'field_code': 'DEL001',
        'district': '削除テスト地区',
        'name': '削除用ほ場',
        'area_ha': 1.5,
        'beet_forbidden': False,
        'coordinates_json': None,
        'notes': None,
    }
    FieldRepository.create_field(user_id, field_data)

    # delete_field_with_state の戻り値: (df, message, map_json)
    df, message, map_json = delete_field_with_state(
        field_id='DEL001',
        user_state=admin_state
    )

    assert isinstance(df, pd.DataFrame)
    assert isinstance(message, str)
    assert "削除しました" in message
