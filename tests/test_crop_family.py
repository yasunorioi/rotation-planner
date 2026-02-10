"""crop_family（作物科）機能のテスト"""
import os
import sqlite3
import pytest

# conftest.py で DB_PATH はテスト用に設定済み
import rotation_planner.common.db_access as _db_mod
_test_db_path = str(_db_mod.DB_PATH)

from rotation_planner.common.db_access import (
    CropMasterRepository,
    ensure_crop_tables,
    get_db,
)


@pytest.fixture(autouse=True)
def setup_db():
    """各テスト前にDBを初期化"""
    # 既存テーブルを削除
    with get_db() as conn:
        conn.execute("DROP TABLE IF EXISTS user_crops")
        conn.execute("DROP TABLE IF EXISTS crop_master")
        conn.execute("DROP TABLE IF EXISTS _migration_log")
        conn.commit()
    # テーブル再作成
    ensure_crop_tables()
    yield
    # テスト後クリーンアップ
    with get_db() as conn:
        conn.execute("DROP TABLE IF EXISTS user_crops")
        conn.execute("DROP TABLE IF EXISTS crop_master")
        conn.execute("DROP TABLE IF EXISTS _migration_log")
        conn.commit()


class TestCropFamilyInitialData:
    """初期データにfamilyが含まれることを確認"""

    def test_initial_crops_have_family(self):
        crops = CropMasterRepository.get_all(active_only=True)
        for crop in crops:
            assert crop['family'] is not None, f"{crop['name']} にfamilyが設定されていない"

    def test_initial_family_mapping(self):
        crops = CropMasterRepository.get_all(active_only=True)
        crop_map = {c['name']: c['family'] for c in crops}
        assert crop_map['小麦(春播)'] == 'イネ科'
        assert crop_map['小麦(秋播)'] == 'イネ科'
        assert crop_map['だいず'] == 'マメ科'
        assert crop_map['てんさい'] == 'アカザ科'
        assert crop_map['ばれいしょ'] == 'ナス科'
        assert crop_map['あずき'] == 'マメ科'
        assert crop_map['たまねぎ'] == 'ユリ科'
        assert crop_map['にんじん'] == 'セリ科'
        assert crop_map['かぼちゃ'] == 'ウリ科'
        assert crop_map['スイートコーン'] == 'イネ科'


class TestGetFamilyMap:
    """get_family_map() のテスト"""

    def test_returns_dict(self):
        result = CropMasterRepository.get_family_map()
        assert isinstance(result, dict)
        assert len(result) > 0

    def test_family_map_values(self):
        family_map = CropMasterRepository.get_family_map()
        assert family_map['小麦(春播)'] == 'イネ科'
        assert family_map['だいず'] == 'マメ科'
        assert family_map['てんさい'] == 'アカザ科'

    def test_excludes_null_family(self):
        """familyがNULLの作物は除外される"""
        # familyなしの作物を追加
        CropMasterRepository.create('テスト作物', display_order=99, family=None)
        family_map = CropMasterRepository.get_family_map()
        assert 'テスト作物' not in family_map

    def test_excludes_inactive(self):
        """非アクティブの作物は除外される"""
        crop_id = CropMasterRepository.create('非アクティブ作物', display_order=99, family='テスト科')
        CropMasterRepository.delete(crop_id)
        family_map = CropMasterRepository.get_family_map()
        assert '非アクティブ作物' not in family_map


class TestCropCreateWithFamily:
    """create() のfamily引数テスト"""

    def test_create_with_family(self):
        crop_id = CropMasterRepository.create('テスト麦', display_order=99, family='イネ科')
        crop = CropMasterRepository.get_by_id(crop_id)
        assert crop['family'] == 'イネ科'

    def test_create_without_family(self):
        crop_id = CropMasterRepository.create('不明作物', display_order=99)
        crop = CropMasterRepository.get_by_id(crop_id)
        assert crop['family'] is None


class TestCropUpdateWithFamily:
    """update() のfamilyフィールドテスト"""

    def test_update_family(self):
        crop_id = CropMasterRepository.create('更新テスト', display_order=99)
        CropMasterRepository.update(crop_id, {'family': 'マメ科'})
        crop = CropMasterRepository.get_by_id(crop_id)
        assert crop['family'] == 'マメ科'

    def test_update_family_to_none(self):
        crop_id = CropMasterRepository.create('削除テスト', display_order=99, family='イネ科')
        CropMasterRepository.update(crop_id, {'family': None})
        crop = CropMasterRepository.get_by_id(crop_id)
        assert crop['family'] is None


class TestMigrationIdempotency:
    """マイグレーションSQLの冪等性テスト"""

    def test_alter_table_idempotent(self):
        """familyカラムが既に存在する場合、ALTER TABLEがエラーにならないこと"""
        with get_db() as conn:
            # familyカラムが既に存在する状態でALTER TABLEを実行
            try:
                conn.execute("ALTER TABLE crop_master ADD COLUMN family TEXT DEFAULT NULL")
                # カラムが存在しなかった場合は成功（初回）
            except sqlite3.OperationalError as e:
                # "duplicate column name: family" はOK（冪等性確認）
                assert "duplicate column name" in str(e)

    def test_update_family_idempotent(self):
        """UPDATEは何回実行しても同じ結果"""
        with get_db() as conn:
            conn.execute("UPDATE crop_master SET family = 'イネ科' WHERE name = '小麦(春播)'")
            conn.execute("UPDATE crop_master SET family = 'イネ科' WHERE name = '小麦(春播)'")
            conn.commit()
        crop = CropMasterRepository.get_by_name('小麦(春播)')
        assert crop['family'] == 'イネ科'
