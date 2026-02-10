"""
PlanRepository のテスト
"""
import pytest
import json
import sqlite3
from rotation_planner.common.db_access import PlanRepository, FieldRepository


@pytest.fixture
def test_field(test_db, admin_state):
    """テスト用ほ場を作成し、field_idを返す"""
    user_id = admin_state['user_id']
    field_data = {
        'field_code': 'PLAN_TEST_F001',
        'district': 'テスト地区',
        'name': 'テストほ場',
        'area_ha': 2.5,
        'beet_forbidden': False,
        'coordinates_json': None,
        'notes': 'PlanRepositoryテスト用',
    }
    field_id = FieldRepository.create_field(user_id, field_data)
    return field_id


# =============================================================================
# PL-01: create_plan 正常な計画作成 → lastrowid
# =============================================================================
def test_create_plan_normal(test_db, admin_state, test_field):
    """PL-01: 正常な計画作成が lastrowid を返すことを確認"""
    user_id = admin_state['user_id']

    plan_data = {
        'name': 'テスト計画2025',
        'start_year': 'R7',
        'end_year': 'R12',
        'constraints': {
            'min_interval': 3,
            'forbidden': ['トマト→ナス']
        },
        'metadata': {'created_by': 'test'},
        'details': [
            {'field_id': test_field, 'year': 'R7', 'crop': 'じゃがいも'},
            {'field_id': test_field, 'year': 'R8', 'crop': 'にんじん'},
        ]
    }

    plan_id = PlanRepository.create_plan(user_id, plan_data)

    assert isinstance(plan_id, int)
    assert plan_id > 0

    # 作成された計画を取得して確認
    plan = PlanRepository.get_plan(plan_id)
    assert plan is not None
    assert plan['name'] == 'テスト計画2025'
    assert plan['start_year'] == 'R7'
    assert plan['end_year'] == 'R12'
    assert len(plan['details']) == 2


# =============================================================================
# PL-02: create_plan name空文字 → エラーまたは空名保存
# =============================================================================
def test_create_plan_empty_name(test_db, admin_state):
    """PL-02: name空文字で計画作成した場合の挙動を確認"""
    user_id = admin_state['user_id']

    plan_data = {
        'name': '',
        'start_year': 'R7',
        'end_year': 'R10',
        'details': []
    }

    # 空文字でも保存される（エラーにはならない）
    plan_id = PlanRepository.create_plan(user_id, plan_data)
    assert isinstance(plan_id, int)

    plan = PlanRepository.get_plan(plan_id)
    assert plan['name'] == ''


# =============================================================================
# PL-03: get_plan constraints JSONパース → dictにパース済み
# =============================================================================
def test_get_plan_constraints_parsed(test_db, admin_state):
    """PL-03: get_plan が constraints を dict にパースして返すことを確認"""
    user_id = admin_state['user_id']

    plan_data = {
        'name': '制約テスト',
        'start_year': 'R7',
        'end_year': 'R10',
        'constraints': {
            'min_interval': 2,
            'max_continuous': 3,
            'forbidden': ['作物A→作物B']
        },
        'details': []
    }

    plan_id = PlanRepository.create_plan(user_id, plan_data)
    plan = PlanRepository.get_plan(plan_id)

    # constraints が dict としてパース済みであることを確認
    assert 'constraints' in plan
    assert isinstance(plan['constraints'], dict)
    assert plan['constraints']['min_interval'] == 2
    assert plan['constraints']['max_continuous'] == 3
    assert 'forbidden' in plan['constraints']


# =============================================================================
# PL-04: get_plan constraints JSON不正 → エラーハンドリング確認
# =============================================================================
def test_get_plan_invalid_json(test_db, admin_state):
    """PL-04: constraints_json が不正な場合のエラーハンドリングを確認"""
    user_id = admin_state['user_id']

    # まず正常な計画を作成
    plan_data = {
        'name': '不正JSON',
        'start_year': 'R7',
        'end_year': 'R10',
        'constraints': {},
        'details': []
    }
    plan_id = PlanRepository.create_plan(user_id, plan_data)

    # 直接DBに不正なJSONを書き込む
    from rotation_planner.common.db_access import get_db
    with get_db() as conn:
        conn.execute(
            "UPDATE rotation_plans SET constraints_json = ? WHERE id = ?",
            ('{"invalid json', plan_id)
        )

    # get_plan を呼び出す（JSONDecodeError が発生する）
    with pytest.raises(json.JSONDecodeError):
        PlanRepository.get_plan(plan_id)


# =============================================================================
# PL-05: update_plan details再作成 → 旧details削除+新規追加
# =============================================================================
def test_update_plan_details_recreated(test_db, admin_state, test_field):
    """PL-05: update_plan が details を全削除→再作成することを確認"""
    user_id = admin_state['user_id']

    # 初期計画作成
    plan_data = {
        'name': '更新テスト',
        'start_year': 'R7',
        'end_year': 'R10',
        'details': [
            {'field_id': test_field, 'year': 'R7', 'crop': '作物A'},
            {'field_id': test_field, 'year': 'R8', 'crop': '作物B'},
        ]
    }
    plan_id = PlanRepository.create_plan(user_id, plan_data)

    # 更新（details を別の内容に変更）
    update_data = {
        'name': '更新後',
        'details': [
            {'field_id': test_field, 'year': 'R7', 'crop': '作物X'},
            {'field_id': test_field, 'year': 'R8', 'crop': '作物Y'},
            {'field_id': test_field, 'year': 'R9', 'crop': '作物Z'},
        ]
    }
    result = PlanRepository.update_plan(plan_id, update_data)
    assert result is True

    # 更新後の計画を取得
    plan = PlanRepository.get_plan(plan_id)
    assert plan['name'] == '更新後'
    assert len(plan['details']) == 3
    assert plan['details'][0]['crop'] == '作物X'
    assert plan['details'][1]['crop'] == '作物Y'
    assert plan['details'][2]['crop'] == '作物Z'


# =============================================================================
# PL-06: delete_plan 関連data含め削除 → True + details削除
# =============================================================================
def test_delete_plan_cascade(test_db, admin_state, test_field):
    """PL-06: delete_plan が計画本体と関連 details を削除することを確認"""
    user_id = admin_state['user_id']

    # 計画作成
    plan_data = {
        'name': '削除テスト',
        'start_year': 'R7',
        'end_year': 'R10',
        'details': [
            {'field_id': test_field, 'year': 'R7', 'crop': '作物A'},
        ]
    }
    plan_id = PlanRepository.create_plan(user_id, plan_data)

    # 削除前に存在確認
    plan = PlanRepository.get_plan(plan_id)
    assert plan is not None
    assert len(plan['details']) == 1

    # 削除実行
    result = PlanRepository.delete_plan(plan_id)
    assert result is True

    # 削除後に存在しないことを確認
    plan = PlanRepository.get_plan(plan_id)
    assert plan is None

    # details も削除されていることを確認（直接SQL）
    from rotation_planner.common.db_access import get_db
    with get_db() as conn:
        cursor = conn.execute(
            "SELECT COUNT(*) as cnt FROM plan_details WHERE plan_id = ?",
            (plan_id,)
        )
        count = cursor.fetchone()['cnt']
        assert count == 0
