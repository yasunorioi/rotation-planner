"""
UserCropRepository のテスト
"""
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from rotation_planner.common.db_access import UserCropRepository, CropMasterRepository
from rotation_planner.common import get_db


@pytest.fixture
def setup_crop_tables(test_db):
    """
    crop_master と user_crops テーブルを作成
    （これらは db_schema.sql に未定義のため、テスト用に作成）
    """
    with get_db() as conn:
        # crop_master テーブル作成
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

        # user_crops テーブル作成
        conn.execute("""
            CREATE TABLE IF NOT EXISTS user_crops (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                parent_crop_id INTEGER NOT NULL REFERENCES crop_master(id) ON DELETE CASCADE,
                custom_name TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # テスト用作物マスタデータ挿入
        crops = [
            ("春小麦", 1),
            ("秋小麦", 2),
            ("大豆", 3),
            ("てんさい", 4),
            ("馬鈴薯", 5),
        ]
        for name, order in crops:
            conn.execute(
                "INSERT OR IGNORE INTO crop_master (name, display_order, is_active) VALUES (?, ?, 1)",
                (name, order)
            )

        conn.commit()

    yield

    # クリーンアップ（test_db フィクスチャが自動で削除するので不要）


@pytest.mark.db
class TestUserCropRepository:
    """UserCropRepository のテストクラス"""

    def test_UC01_set_user_crops_normal(self, test_db, setup_crop_tables, admin_state):
        """
        UC-01: set_user_crops 作物選択設定
        期待結果: True
        """
        user_id = admin_state["user_id"]

        # crop_master から作物IDを取得
        crops = CropMasterRepository.get_all(active_only=True)
        assert len(crops) > 0, "crop_master にアクティブな作物が存在すること"

        # 最初の3つの作物を選択
        crop_ids = [crops[0]["id"], crops[1]["id"], crops[2]["id"]]

        # 作物選択を設定
        result = UserCropRepository.set_user_crops(user_id, crop_ids)

        # 検証
        assert result is True, "set_user_crops は True を返すこと"

        # 保存された作物を確認
        user_crops = UserCropRepository.get_user_crops(user_id)
        assert len(user_crops) == 3, "3つの作物が設定されていること"

        # parent_crop_id が設定されていることを確認
        saved_ids = [c["parent_crop_id"] for c in user_crops]
        assert set(saved_ids) == set(crop_ids), "設定した作物IDが保存されていること"

    def test_UC02_set_user_crops_empty_list(self, test_db, setup_crop_tables, farmer_state):
        """
        UC-02: set_user_crops 空リスト
        期待結果: True (全解除)
        """
        user_id = farmer_state["user_id"]

        # まず作物を設定
        crops = CropMasterRepository.get_all(active_only=True)
        assert len(crops) > 0
        crop_ids = [crops[0]["id"]]
        UserCropRepository.set_user_crops(user_id, crop_ids)

        # 作物があることを確認
        user_crops = UserCropRepository.get_user_crops(user_id)
        assert len(user_crops) > 0, "作物が設定されていること"

        # 空リストで全解除
        result = UserCropRepository.set_user_crops(user_id, [])

        # 検証
        assert result is True, "空リストでも True を返すこと"

        # カスタム名なしの作物が削除されていることを確認
        user_crops_after = UserCropRepository.get_user_crops(user_id)
        # custom_name なしのものは削除される
        custom_crops = [c for c in user_crops_after if c.get("custom_name")]
        assert len(user_crops_after) == len(custom_crops), "カスタム名なしの作物が全て削除されていること"

    def test_UC03_add_user_crop_custom_name(self, test_db, setup_crop_tables, admin_state):
        """
        UC-03: add_user_crop カスタム作物追加
        期待結果: lastrowid
        """
        user_id = admin_state["user_id"]

        # crop_master から作物IDを取得
        crops = CropMasterRepository.get_all(active_only=True)
        assert len(crops) > 0
        parent_crop_id = crops[0]["id"]

        # カスタム作物を追加
        custom_name = "テスト作物（2作目）"
        result = UserCropRepository.add_user_crop(user_id, parent_crop_id, custom_name)

        # 検証
        assert isinstance(result, int), "lastrowid（int）を返すこと"
        assert result > 0, "lastrowid は正の整数であること"

        # 追加された作物を確認
        user_crops = UserCropRepository.get_user_crops(user_id)
        added_crop = next((c for c in user_crops if c.get("custom_name") == custom_name), None)
        assert added_crop is not None, "カスタム作物が追加されていること"
        assert added_crop["parent_crop_id"] == parent_crop_id, "parent_crop_id が正しいこと"
        assert added_crop["name"] == custom_name, "表示名がカスタム名であること"

    def test_UC04_remove_user_crop(self, test_db, setup_crop_tables, farmer_state):
        """
        UC-04: remove_user_crop 削除
        期待結果: True
        """
        user_id = farmer_state["user_id"]

        # まず作物を追加
        crops = CropMasterRepository.get_all(active_only=True)
        assert len(crops) > 0
        parent_crop_id = crops[0]["id"]

        user_crop_id = UserCropRepository.add_user_crop(user_id, parent_crop_id, "削除テスト作物")

        # 追加されたことを確認
        user_crops_before = UserCropRepository.get_user_crops(user_id)
        crop_ids_before = [c["id"] for c in user_crops_before]
        assert user_crop_id in crop_ids_before, "作物が追加されていること"

        # 削除
        result = UserCropRepository.remove_user_crop(user_id, user_crop_id)

        # 検証
        assert result is True, "remove_user_crop は True を返すこと"

        # 削除されたことを確認
        user_crops_after = UserCropRepository.get_user_crops(user_id)
        crop_ids_after = [c["id"] for c in user_crops_after]
        assert user_crop_id not in crop_ids_after, "作物が削除されていること"

    def test_UC05_get_parent_crop_id_by_name_not_found(self, test_db, setup_crop_tables, admin_state):
        """
        UC-05: get_parent_crop_id_by_name 存在しない名前
        期待結果: None
        """
        user_id = admin_state["user_id"]

        # 存在しない作物名で検索
        non_existent_name = "存在しない作物名_12345"
        result = UserCropRepository.get_parent_crop_id_by_name(user_id, non_existent_name)

        # 検証
        assert result is None, "存在しない作物名の場合は None を返すこと"
