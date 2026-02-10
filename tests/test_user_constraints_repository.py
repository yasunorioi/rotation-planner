"""
UserConstraintsRepository のテスト
"""
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from rotation_planner.common.db_access import UserConstraintsRepository


@pytest.mark.db
class TestUserConstraintsRepository:
    """UserConstraintsRepository のテストクラス"""

    def test_CO01_save_constraints_normal(self, test_db, admin_state):
        """
        CO-01: save_constraints 正常保存
        期待結果: True
        """
        user_id = admin_state["user_id"]

        # 制約データを準備
        constraints = [
            {"crop": "春小麦", "min_ha": 1.0, "cap_ha": 10.0, "min_gap_years": 0},
            {"crop": "大豆", "min_ha": 0.5, "cap_ha": 8.0, "min_gap_years": 2},
        ]
        forbidden_transitions = "春小麦->秋小麦, てんさい->秋小麦"
        preferred_transitions = "てんさい->大豆:10, デントコーン->秋小麦:8"
        main_crops = "春小麦, 秋小麦, 大豆"

        # 保存
        result = UserConstraintsRepository.save_constraints(
            user_id,
            constraints,
            forbidden_transitions,
            preferred_transitions,
            main_crops
        )

        # 検証
        assert result is True, "save_constraints は True を返すこと"

        # 保存されたデータを取得して確認
        saved = UserConstraintsRepository.get_constraints(user_id)
        assert saved is not None, "保存された制約が取得できること"
        assert saved["constraints"] == constraints, "制約テーブルが正しく保存されていること"
        assert saved["forbidden_transitions"] == forbidden_transitions, "禁止遷移が正しく保存されていること"
        assert saved["preferred_transitions"] == preferred_transitions, "優先遷移が正しく保存されていること"
        assert saved["main_crops"] == main_crops, "主作物が正しく保存されていること"

    def test_CO02_get_constraints_exists(self, test_db, farmer_state):
        """
        CO-02: get_constraints 保存済み取得
        期待結果: Dict
        """
        user_id = farmer_state["user_id"]

        # まず制約を保存
        constraints = [
            {"crop": "てんさい", "min_ha": None, "cap_ha": None, "min_gap_years": 4},
        ]
        forbidden = "てんさい->秋小麦"
        preferred = "てんさい->大豆:10"
        main_crops = "てんさい"

        UserConstraintsRepository.save_constraints(
            user_id, constraints, forbidden, preferred, main_crops
        )

        # 取得
        result = UserConstraintsRepository.get_constraints(user_id)

        # 検証
        assert isinstance(result, dict), "Dictを返すこと"
        assert "constraints" in result, "constraints キーが存在すること"
        assert "forbidden_transitions" in result, "forbidden_transitions キーが存在すること"
        assert "preferred_transitions" in result, "preferred_transitions キーが存在すること"
        assert "main_crops" in result, "main_crops キーが存在すること"

        # 値の確認
        assert result["constraints"] == constraints, "制約テーブルが正しいこと"
        assert result["forbidden_transitions"] == forbidden, "禁止遷移が正しいこと"
        assert result["preferred_transitions"] == preferred, "優先遷移が正しいこと"
        assert result["main_crops"] == main_crops, "主作物が正しいこと"

    def test_CO03_get_constraints_not_exists(self, test_db, ja_staff_state):
        """
        CO-03: get_constraints 未設定ユーザー
        期待結果: None
        """
        user_id = ja_staff_state["user_id"]

        # 制約を保存せずに取得
        result = UserConstraintsRepository.get_constraints(user_id)

        # 検証
        assert result is None, "未設定のユーザーは None を返すこと"

    def test_CO04_delete_constraints_normal(self, test_db, admin_state):
        """
        CO-04: delete_constraints 正常削除
        期待結果: True
        """
        user_id = admin_state["user_id"]

        # まず制約を保存
        constraints = [{"crop": "大豆", "min_ha": 1.0, "cap_ha": 10.0, "min_gap_years": 0}]
        UserConstraintsRepository.save_constraints(user_id, constraints, "", "", "")

        # 保存されたことを確認
        saved = UserConstraintsRepository.get_constraints(user_id)
        assert saved is not None, "制約が保存されていること"

        # 削除
        result = UserConstraintsRepository.delete_constraints(user_id)

        # 検証
        assert result is True, "delete_constraints は True を返すこと"

        # 削除されたことを確認
        deleted = UserConstraintsRepository.get_constraints(user_id)
        assert deleted is None, "制約が削除されていること"
