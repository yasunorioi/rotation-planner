"""
crop_master family列のテスト
- get_family_map
- create with family
- NULLファミリー除外
"""
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from rotation_planner.common.db_access import CropMasterRepository, UserCropRepository
from rotation_planner.common import get_db


@pytest.fixture
def setup_crop_tables(test_db):
    """crop_master + user_crops テーブルをfamily列付きで作成"""
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS crop_master (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                family TEXT DEFAULT NULL,
                display_order INTEGER DEFAULT 0,
                is_active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS user_crops (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                parent_crop_id INTEGER NOT NULL REFERENCES crop_master(id) ON DELETE CASCADE,
                custom_name TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # テスト用作物データ（family付き）
        crops = [
            ("春小麦", "イネ科", 1),
            ("秋小麦", "イネ科", 2),
            ("大豆", "マメ科", 3),
            ("てんさい", "アカザ科", 4),
            ("馬鈴薯", "ナス科", 5),
            ("カスタム作物", None, 6),  # familyなし
        ]
        for name, family, order in crops:
            conn.execute(
                "INSERT INTO crop_master (name, family, display_order) VALUES (?, ?, ?)",
                (name, family, order)
            )
    return test_db


class TestGetFamilyMap:
    """get_family_map のテスト"""

    def test_basic_family_map(self, setup_crop_tables):
        """基本的なファミリーマップ取得"""
        fm = CropMasterRepository.get_family_map()
        assert fm["春小麦"] == "イネ科"
        assert fm["秋小麦"] == "イネ科"
        assert fm["大豆"] == "マメ科"
        assert fm["てんさい"] == "アカザ科"
        assert fm["馬鈴薯"] == "ナス科"

    def test_null_family_excluded(self, setup_crop_tables):
        """familyがNULLの作物は除外される"""
        fm = CropMasterRepository.get_family_map()
        assert "カスタム作物" not in fm

    def test_user_crop_custom_name_resolved(self, setup_crop_tables):
        """UserCropのcustom_nameも親のfamilyを引き継ぐ"""
        with get_db() as conn:
            # user_id=1のユーザーに「春小麦」のカスタム名「うちの小麦」を登録
            wheat_id = conn.execute(
                "SELECT id FROM crop_master WHERE name = '春小麦'"
            ).fetchone()[0]
            conn.execute(
                "INSERT INTO user_crops (user_id, parent_crop_id, custom_name) VALUES (?, ?, ?)",
                (1, wheat_id, "うちの小麦")
            )

        fm = CropMasterRepository.get_family_map()
        assert fm["うちの小麦"] == "イネ科"
        assert fm["春小麦"] == "イネ科"  # 元のマスタも残っている

    def test_inactive_crop_excluded(self, setup_crop_tables):
        """非アクティブ作物は除外"""
        with get_db() as conn:
            conn.execute("UPDATE crop_master SET is_active = 0 WHERE name = '馬鈴薯'")

        fm = CropMasterRepository.get_family_map()
        assert "馬鈴薯" not in fm


class TestCreateWithFamily:
    """create with family のテスト"""

    def test_create_with_family(self, setup_crop_tables):
        """familyを指定して作物を作成"""
        crop_id = CropMasterRepository.create("にんじん", display_order=7, family="セリ科")
        assert crop_id > 0

        crop = CropMasterRepository.get_by_id(crop_id)
        assert crop["name"] == "にんじん"
        assert crop["family"] == "セリ科"

    def test_create_without_family(self, setup_crop_tables):
        """familyなしで作物を作成（NULL）"""
        crop_id = CropMasterRepository.create("その他作物", display_order=8)
        crop = CropMasterRepository.get_by_id(crop_id)
        assert crop["family"] is None


class TestUpdateWithFamily:
    """update with family のテスト"""

    def test_update_family(self, setup_crop_tables):
        """familyを更新"""
        crop = CropMasterRepository.get_by_name("カスタム作物")
        assert crop["family"] is None

        CropMasterRepository.update(crop["id"], {"family": "テスト科"})
        updated = CropMasterRepository.get_by_id(crop["id"])
        assert updated["family"] == "テスト科"
