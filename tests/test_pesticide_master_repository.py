"""
PesticideMasterRepository のテスト
"""
import pytest
from rotation_planner.common.db_access import PesticideMasterRepository


# =============================================================================
# PM-01: bulk_import 正常インポート → 件数
# =============================================================================
def test_bulk_import_normal(test_db):
    """PM-01: 正常な一括インポートが件数を返すことを確認"""
    records = [
        {
            'crop': 'じゃがいも',
            'month': 5,
            'period': '上旬',
            'target': '疫病',
            'pesticide_name': '農薬A',
            'dilution_rate': '1000倍',
            'amount_per_10a': 100.0,
            'unit': 'mL',
            'days_before_harvest': 14,
            'notes': 'テスト用'
        },
        {
            'crop': 'じゃがいも',
            'month': 6,
            'period': '中旬',
            'target': 'アブラムシ',
            'pesticide_name': '農薬B',
            'dilution_rate': '2000倍',
            'amount_per_10a': 50.0,
            'unit': 'mL',
            'days_before_harvest': 7,
            'notes': ''
        },
        {
            'crop': 'にんじん',
            'month': 7,
            'period': '下旬',
            'target': '黒斑病',
            'pesticide_name': '農薬C',
            'dilution_rate': '500倍',
            'amount_per_10a': 200.0,
            'unit': 'g',
            'days_before_harvest': 21,
            'notes': ''
        }
    ]

    org_id = 1
    count = PesticideMasterRepository.bulk_import(records, org_id)

    assert count == 3

    # インポート後に取得して確認
    masters = PesticideMasterRepository.get_by_crop('じゃがいも', org_id)
    assert len(masters) == 2
    assert masters[0]['name'] in ['農薬A', '農薬B']


# =============================================================================
# PM-02: bulk_import 空リスト → 0
# =============================================================================
def test_bulk_import_empty_list(test_db):
    """PM-02: 空リストでインポートした場合に 0 を返すことを確認"""
    records = []
    org_id = 1

    count = PesticideMasterRepository.bulk_import(records, org_id)

    assert count == 0


# =============================================================================
# PM-03: get_by_crop 作物名指定 → List[Dict]
# =============================================================================
def test_get_by_crop(test_db):
    """PM-03: 作物名で防除マスタを取得できることを確認"""
    # まずデータを投入
    records = [
        {
            'crop': 'トマト',
            'month': 5,
            'period': '上旬',
            'target': '葉かび病',
            'pesticide_name': '農薬X',
            'dilution_rate': '1500倍',
            'amount_per_10a': 80.0,
            'unit': 'mL',
            'days_before_harvest': 10,
            'notes': ''
        },
        {
            'crop': 'トマト',
            'month': 6,
            'period': '中旬',
            'target': 'アブラムシ',
            'pesticide_name': '農薬Y',
            'dilution_rate': '1000倍',
            'amount_per_10a': 100.0,
            'unit': 'mL',
            'days_before_harvest': 5,
            'notes': ''
        },
        {
            'crop': 'きゅうり',
            'month': 7,
            'period': '下旬',
            'target': 'うどんこ病',
            'pesticide_name': '農薬Z',
            'dilution_rate': '2000倍',
            'amount_per_10a': 50.0,
            'unit': 'g',
            'days_before_harvest': 3,
            'notes': ''
        }
    ]
    org_id = 1
    PesticideMasterRepository.bulk_import(records, org_id)

    # トマトの防除マスタを取得
    tomato_masters = PesticideMasterRepository.get_by_crop('トマト', org_id)

    assert isinstance(tomato_masters, list)
    assert len(tomato_masters) == 2
    assert all(m['crop'] == 'トマト' for m in tomato_masters)

    # きゅうりの防除マスタを取得
    cucumber_masters = PesticideMasterRepository.get_by_crop('きゅうり', org_id)
    assert len(cucumber_masters) == 1
    assert cucumber_masters[0]['crop'] == 'きゅうり'

    # 存在しない作物
    none_masters = PesticideMasterRepository.get_by_crop('存在しない作物', org_id)
    assert len(none_masters) == 0


# =============================================================================
# PM-04: delete_all 組織内全削除 → 件数
# =============================================================================
def test_delete_all(test_db):
    """PM-04: 組織内の全防除マスタを削除できることを確認"""
    # まずデータを投入
    records = [
        {
            'crop': 'レタス',
            'month': 4,
            'period': '上旬',
            'target': 'アブラムシ',
            'pesticide_name': '農薬P',
            'dilution_rate': '1000倍',
            'amount_per_10a': 100.0,
            'unit': 'mL',
            'days_before_harvest': 7,
            'notes': ''
        },
        {
            'crop': 'レタス',
            'month': 5,
            'period': '中旬',
            'target': '灰色かび病',
            'pesticide_name': '農薬Q',
            'dilution_rate': '1500倍',
            'amount_per_10a': 80.0,
            'unit': 'mL',
            'days_before_harvest': 14,
            'notes': ''
        }
    ]
    org_id = 2
    PesticideMasterRepository.bulk_import(records, org_id)

    # 削除前の件数確認
    before_count = len(PesticideMasterRepository.get_all(org_id))
    assert before_count >= 2

    # 削除実行
    deleted_count = PesticideMasterRepository.delete_all(org_id)
    assert deleted_count >= 2

    # 削除後の件数確認
    after_count = len(PesticideMasterRepository.get_all(org_id))
    assert after_count == 0
