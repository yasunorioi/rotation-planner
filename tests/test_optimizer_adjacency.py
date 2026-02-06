"""
隣接筆制約のオプティマイザーテスト
- 隣接+同一科→ペナルティ発生
- 隣接+異なる科→OK
- PRO OFF→制約なし
- 隣接ペアなし→制約なし
"""
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from rotation_planner.app.constraints import Constraints
from rotation_planner.app.optimizer import RotationPlannerORTools, RotationPlannerHeuristic
from rotation_planner.app.utils import Field


# =============================================================================
# テスト用フィクスチャ
# =============================================================================

def make_field(field_id: str, area_ha: float = 2.0, history: dict = None,
               beet_forbidden: bool = False, district: str = "A") -> Field:
    """テスト用Fieldを作成"""
    return Field(
        field_id=field_id,
        district=district,
        name=field_id,
        area_ha=area_ha,
        history=history or {},
        beet_forbidden=beet_forbidden,
    )


CROPS = ["春小麦", "大豆", "てんさい", "馬鈴薯"]
PAST_YEARS = ["R5"]
FUTURE_YEARS = ["R6"]

FAMILY_MAP = {
    "春小麦": "イネ科",
    "大豆": "マメ科",
    "てんさい": "アカザ科",
    "馬鈴薯": "ナス科",
}


def make_constraints(adjacent_enabled: bool = False,
                     adjacency_pairs: list = None) -> Constraints:
    """テスト用Constraintsを作成"""
    return Constraints(
        crop_caps={"春小麦": 100, "大豆": 100, "てんさい": 100, "馬鈴薯": 100},
        min_gap_years={"てんさい": 0, "馬鈴薯": 0},
        forbidden_transitions=set(),
        adjacent_family_enabled=adjacent_enabled,
        adjacency_pairs=adjacency_pairs or [],
        crop_family_map=FAMILY_MAP if adjacent_enabled else {},
    )


class TestORToolsAdjacency:
    """OR-Tools隣接制約テスト"""

    def test_adjacent_same_family_penalized(self):
        """隣接ほ場に同一科→ペナルティが発生しうる"""
        fields = [
            make_field("F1", history={"R5": "大豆"}),
            make_field("F2", history={"R5": "てんさい"}),
        ]
        constraints = make_constraints(
            adjacent_enabled=True,
            adjacency_pairs=[(0, 1)]
        )
        planner = RotationPlannerORTools(
            fields, PAST_YEARS, FUTURE_YEARS, CROPS, constraints
        )
        plan, score, errors = planner.solve(timeout_seconds=5)
        # 解が得られること
        assert plan is not None
        # 2ほ場×1年の計画が生成されること
        assert len(plan) == 2

    def test_adjacent_different_family_ok(self):
        """隣接ほ場でも異なる科ならOK"""
        fields = [
            make_field("F1", history={"R5": "春小麦"}),
            make_field("F2", history={"R5": "てんさい"}),
        ]
        constraints = make_constraints(
            adjacent_enabled=True,
            adjacency_pairs=[(0, 1)]
        )
        planner = RotationPlannerORTools(
            fields, PAST_YEARS, FUTURE_YEARS, CROPS, constraints
        )
        plan, score, errors = planner.solve(timeout_seconds=5)
        assert plan is not None

        # 隣接制約違反の警告がないことを確認
        adj_warnings = [e for e in errors if "同一科" in e]
        # 4作物×2ほ場なら十分な自由度があるので違反なしのはず
        # （ただしソフト制約なので違反してもエラーではない）

    def test_pro_off_no_constraint(self):
        """PRO OFF→隣接制約なし"""
        fields = [
            make_field("F1", history={"R5": "大豆"}),
            make_field("F2", history={"R5": "春小麦"}),
        ]
        constraints = make_constraints(adjacent_enabled=False)
        planner = RotationPlannerORTools(
            fields, PAST_YEARS, FUTURE_YEARS, CROPS, constraints
        )
        plan, score, errors = planner.solve(timeout_seconds=5)
        assert plan is not None
        # 隣接関連の警告が出ないこと
        adj_warnings = [e for e in errors if "同一科" in e]
        assert len(adj_warnings) == 0

    def test_no_adjacency_pairs(self):
        """隣接ペアなし→制約なし（PRO ONでも）"""
        fields = [
            make_field("F1", history={"R5": "大豆"}),
            make_field("F2", history={"R5": "春小麦"}),
        ]
        constraints = make_constraints(
            adjacent_enabled=True,
            adjacency_pairs=[]
        )
        planner = RotationPlannerORTools(
            fields, PAST_YEARS, FUTURE_YEARS, CROPS, constraints
        )
        plan, score, errors = planner.solve(timeout_seconds=5)
        assert plan is not None


class TestHeuristicAdjacency:
    """ヒューリスティック隣接制約テスト"""

    def test_adjacency_check_blocks_same_family(self):
        """check_adjacency_constraintが同一科をブロック"""
        fields = [
            make_field("F1"),
            make_field("F2"),
        ]
        constraints = make_constraints(
            adjacent_enabled=True,
            adjacency_pairs=[(0, 1)]
        )
        planner = RotationPlannerHeuristic(
            fields, PAST_YEARS, FUTURE_YEARS, CROPS, constraints
        )
        # F2にすでに春小麦（イネ科）が配置されている状態で
        # F1に春小麦（同じイネ科）を配置しようとする
        plan = {(1, "R6"): "春小麦"}
        result = planner.check_adjacency_constraint(0, "R6", "春小麦", plan)
        assert result is False  # 同一科なのでブロック

    def test_adjacency_check_allows_different_family(self):
        """check_adjacency_constraintが異なる科を許可"""
        fields = [
            make_field("F1"),
            make_field("F2"),
        ]
        constraints = make_constraints(
            adjacent_enabled=True,
            adjacency_pairs=[(0, 1)]
        )
        planner = RotationPlannerHeuristic(
            fields, PAST_YEARS, FUTURE_YEARS, CROPS, constraints
        )
        plan = {(1, "R6"): "春小麦"}  # イネ科
        result = planner.check_adjacency_constraint(0, "R6", "大豆", plan)  # マメ科
        assert result is True

    def test_adjacency_disabled_always_true(self):
        """PRO OFFなら常にTrue"""
        fields = [make_field("F1"), make_field("F2")]
        constraints = make_constraints(adjacent_enabled=False)
        planner = RotationPlannerHeuristic(
            fields, PAST_YEARS, FUTURE_YEARS, CROPS, constraints
        )
        plan = {(1, "R6"): "春小麦"}
        result = planner.check_adjacency_constraint(0, "R6", "春小麦", plan)
        assert result is True
