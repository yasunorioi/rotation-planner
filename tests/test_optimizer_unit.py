"""
optimizer.py 単体テスト（OH-01 ~ OH-15, OO-01 ~ OO-03）

対象: rotation_planner/app/optimizer.py
テストID: OH-01 ~ OH-15（ヒューリスティック）、OO-01 ~ OO-03（OR-Tools）
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rotation_planner.app.utils import Field, UNKNOWN_MARKER
from rotation_planner.app.constraints import Constraints

try:
    import ortools
    HAS_ORTOOLS = True
except ImportError:
    HAS_ORTOOLS = False

from rotation_planner.app.optimizer import RotationPlannerHeuristic

if HAS_ORTOOLS:
    from rotation_planner.app.optimizer import RotationPlannerORTools


# =============================================================================
# 共通フィクスチャ
# =============================================================================

@pytest.fixture
def simple_fields():
    """最小構成: 2ほ場"""
    return [
        Field(field_id="F001", district="A", name="ほ場1", area_ha=2.0,
              history={"R6": "大豆", "R7": "春小麦"}),
        Field(field_id="F002", district="A", name="ほ場2", area_ha=3.0,
              history={"R6": "てんさい", "R7": "大豆"}),
    ]


@pytest.fixture
def simple_crops():
    """最小構成: 3作物"""
    return ["大豆", "春小麦", "てんさい"]


@pytest.fixture
def simple_constraints():
    """最小構成: 基本制約"""
    return Constraints(
        crop_mins={},
        crop_caps={"大豆": 12.0, "春小麦": 10.0, "てんさい": None},
        min_gap_years={"てんさい": 4},
        min_fields={"てんさい": 0},
        max_fields={"てんさい": 2},
        forbidden_transitions={("てんさい", "秋小麦"), ("春小麦", "秋小麦")},
        preferred_transitions={("てんさい", "大豆"): 10.0, ("てんさい", "春小麦"): 5.0},
        main_crops=["春小麦", "大豆"],
        unknown_mode="ignore",
    )


@pytest.fixture
def past_years():
    return ["R6", "R7"]


@pytest.fixture
def future_years():
    return ["R8", "R9"]


@pytest.fixture
def heuristic_planner(simple_fields, past_years, future_years, simple_crops, simple_constraints):
    """ヒューリスティックプランナーのインスタンス"""
    return RotationPlannerHeuristic(
        fields=simple_fields,
        past_years=past_years,
        future_years=future_years,
        crops=simple_crops,
        constraints=simple_constraints,
    )


# =============================================================================
# TestRotationPlannerHeuristicInit（OH-01）
# =============================================================================

class TestRotationPlannerHeuristicInit:
    """RotationPlannerHeuristic の初期化テスト"""

    def test_oh01_initialization(self, heuristic_planner, simple_fields, simple_crops):
        """OH-01: 最小構成で初期化 → Instance created"""
        p = heuristic_planner
        assert p.fields == simple_fields
        assert p.crops == simple_crops
        assert p.all_years == ["R6", "R7", "R8", "R9"]
        assert p.past_years == ["R6", "R7"]
        assert p.future_years == ["R8", "R9"]
        assert p.errors == []


# =============================================================================
# TestGetLastNCrops（OH-02 ~ OH-03）
# =============================================================================

class TestGetLastNCrops:
    """get_last_n_crops のテスト"""

    def test_oh02_history_available(self, heuristic_planner):
        """OH-02: 履歴取得 → 過去作物リスト"""
        plan = {}
        # R8 の前 2年: R7=春小麦, R6=大豆（field_idx=0）
        result = heuristic_planner.get_last_n_crops(0, "R8", 2, plan)
        assert len(result) == 2
        assert result[0] == "春小麦"  # R7
        assert result[1] == "大豆"    # R6

    def test_oh03_insufficient_history(self, heuristic_planner):
        """OH-03: 履歴不足 → 取得可能分だけ返す"""
        plan = {}
        # R7 の前 5年: R6のみ取得可能（field_idx=0）
        result = heuristic_planner.get_last_n_crops(0, "R7", 5, plan)
        assert len(result) == 1
        assert result[0] == "大豆"  # R6


# =============================================================================
# TestCheckGapConstraint（OH-04 ~ OH-05）
# =============================================================================

class TestCheckGapConstraint:
    """check_gap_constraint のテスト"""

    def test_oh04_gap_ok(self, heuristic_planner):
        """OH-04: 間隔OK → True"""
        plan = {}
        # てんさいの min_gap_years=4, field_idx=0
        # R8の前年はR7=春小麦, R6=大豆 → てんさいなし → OK
        result = heuristic_planner.check_gap_constraint(0, "R8", "てんさい", plan)
        assert result is True

    def test_oh05_gap_ng(self, heuristic_planner):
        """OH-05: 間隔NG → False"""
        plan = {}
        # field_idx=1: R6=てんさい, R7=大豆
        # てんさいの min_gap_years=4, R8の前4年にてんさい(R6)あり → NG
        result = heuristic_planner.check_gap_constraint(1, "R8", "てんさい", plan)
        assert result is False


# =============================================================================
# TestCheckTransitionConstraint（OH-06 ~ OH-07）
# =============================================================================

class TestCheckTransitionConstraint:
    """check_transition_constraint のテスト"""

    def test_oh06_allowed_transition(self, heuristic_planner):
        """OH-06: 許可遷移 → True"""
        plan = {}
        # field_idx=0: R7=春小麦 → R8=大豆（禁止リストにない）→ True
        result = heuristic_planner.check_transition_constraint(0, "R8", "大豆", plan)
        assert result is True

    def test_oh07_forbidden_transition(self, heuristic_planner):
        """OH-07: 禁止遷移（連作） → False"""
        plan = {}
        # field_idx=0: R7=春小麦 → R8=春小麦（連作禁止） → False
        result = heuristic_planner.check_transition_constraint(0, "R8", "春小麦", plan)
        assert result is False


# =============================================================================
# TestGetValidCrops（OH-08）
# =============================================================================

class TestGetValidCrops:
    """get_valid_crops のテスト"""

    def test_oh08_filtering(self, heuristic_planner):
        """OH-08: フィルタリング → 有効作物のみ"""
        plan = {}
        # field_idx=0: R7=春小麦
        # - 大豆: gap OK, transition OK → valid
        # - 春小麦: transition NG（連作）→ invalid
        # - てんさい: gap OK（history に最近のてんさいなし）, transition OK → valid
        result = heuristic_planner.get_valid_crops(0, "R8", plan)
        assert "大豆" in result
        assert "春小麦" not in result  # 連作禁止
        assert "てんさい" in result


# =============================================================================
# TestCheckCapConstraint（OH-09 ~ OH-10）
# =============================================================================

class TestCheckCapConstraint:
    """check_cap_constraint のテスト"""

    def test_oh09_within_cap(self, heuristic_planner):
        """OH-09: 上限内 → True"""
        plan = {}
        # 大豆のcap=12.0ha, 追加2.0ha → 2.0 <= 12.0 → True
        result = heuristic_planner.check_cap_constraint("R8", "大豆", plan, additional_ha=2.0)
        assert result is True

    def test_oh10_exceeds_cap(self, heuristic_planner):
        """OH-10: 上限超過 → False"""
        # 全ほ場を大豆にして上限近くまで埋める
        plan = {(0, "R8"): "大豆", (1, "R8"): "大豆"}
        # 現在 2.0+3.0=5.0ha, cap=12.0ha, 追加8.0ha → 13.0 > 12.0 → False
        result = heuristic_planner.check_cap_constraint("R8", "大豆", plan, additional_ha=8.0)
        assert result is False


# =============================================================================
# TestCheckFieldCountConstraint（OH-11 ~ OH-12）
# =============================================================================

class TestCheckFieldCountConstraint:
    """check_field_count_constraint のテスト"""

    def test_oh11_within_range(self, heuristic_planner):
        """OH-11: 範囲内 → (True, "")"""
        plan = {(0, "R8"): "てんさい"}
        # てんさい max_fields=2, 現在1ほ場, adding=True → 2 <= 2 → OK
        ok, msg = heuristic_planner.check_field_count_constraint("R8", "てんさい", plan, adding=True)
        assert ok is True
        assert msg == ""

    def test_oh12_exceeds_range(self, heuristic_planner):
        """OH-12: 範囲外 → (False, msg)"""
        plan = {(0, "R8"): "てんさい", (1, "R8"): "てんさい"}
        # てんさい max_fields=2, 現在2ほ場, adding=True → 3 > 2 → NG
        ok, msg = heuristic_planner.check_field_count_constraint("R8", "てんさい", plan, adding=True)
        assert ok is False
        assert "てんさい" in msg
        assert "上限" in msg


# =============================================================================
# TestSolveHeuristic（OH-13 ~ OH-14）
# =============================================================================

class TestSolveHeuristic:
    """ヒューリスティック solve のテスト"""

    def test_oh13_minimal_solvable(self, heuristic_planner):
        """OH-13: 最小問題 → 実行可能解"""
        plan, score, errors = heuristic_planner.solve()

        # planは非空のdict
        assert isinstance(plan, dict)
        assert len(plan) > 0

        # 全ほ場×全将来年に割当がある
        for i in range(len(heuristic_planner.fields)):
            for year in heuristic_planner.future_years:
                assert (i, year) in plan
                assert plan[(i, year)] in heuristic_planner.crops

        # scoreはfloat
        assert isinstance(score, float)

    def test_oh14_over_constrained(self):
        """OH-14: 過剰制約 → violations あり or 警告"""
        # 1ほ場・3作物・1年 + 厳しい制約
        fields = [
            Field(field_id="F001", district="A", name="ほ場1", area_ha=2.0,
                  history={"R7": "大豆"}),
        ]
        constraints = Constraints(
            crop_mins={},
            crop_caps={"大豆": 0.5, "春小麦": 0.5, "てんさい": 0.5},  # 全て面積上限0.5haだがほ場は2.0ha
            min_gap_years={},
            min_fields={},
            max_fields={},
            forbidden_transitions=set(),
            preferred_transitions={},
            main_crops=[],
            unknown_mode="ignore",
        )

        planner = RotationPlannerHeuristic(
            fields=fields,
            past_years=["R7"],
            future_years=["R8"],
            crops=["大豆", "春小麦", "てんさい"],
            constraints=constraints,
        )

        plan, score, errors = planner.solve()

        # 解は返る（ヒューリスティックは常に解を出す）
        assert isinstance(plan, dict)
        assert len(plan) > 0
        # 制約違反があるはず（面積上限超過）
        assert score < 0 or len(errors) > 0


# =============================================================================
# TestEvaluateSolution（OH-15）
# =============================================================================

class TestEvaluateSolution:
    """evaluate_solution のテスト"""

    def test_oh15_score_calculation(self, heuristic_planner):
        """OH-15: スコア計算"""
        # 手動で計画を作成
        plan = {
            (0, "R8"): "大豆",
            (0, "R9"): "春小麦",
            (1, "R8"): "春小麦",
            (1, "R9"): "大豆",
        }

        score, violations = heuristic_planner.evaluate_solution(plan)

        # scoreはfloat
        assert isinstance(score, float)
        # violationsはリスト
        assert isinstance(violations, list)

        # この計画は基本的に制約違反なし（連作なし、上限内）
        # てんさいの max_fields チェックも通る（てんさい=0ほ場）
        cap_violations = [v for v in violations if "面積" in v and "超過" in v]
        assert len(cap_violations) == 0


# =============================================================================
# TestRotationPlannerORTools（OO-01 ~ OO-03）
# =============================================================================

@pytest.mark.skipif(not HAS_ORTOOLS, reason="ortools not installed")
class TestRotationPlannerORTools:
    """RotationPlannerORTools のテスト"""

    @pytest.fixture
    def ortools_planner(self, simple_fields, past_years, future_years, simple_crops, simple_constraints):
        """OR-Toolsプランナーのインスタンス"""
        return RotationPlannerORTools(
            fields=simple_fields,
            past_years=past_years,
            future_years=future_years,
            crops=simple_crops,
            constraints=simple_constraints,
        )

    def test_oo01_minimal_solve(self, ortools_planner):
        """OO-01: 最小問題 → 実行可能解"""
        plan, score, errors = ortools_planner.solve(timeout_seconds=10)

        # planは非空のdict
        assert isinstance(plan, dict)
        assert len(plan) > 0

        # 全ほ場×全将来年に割当がある
        for i in range(len(ortools_planner.fields)):
            for year in ortools_planner.future_years:
                assert (i, year) in plan
                assert plan[(i, year)] in ortools_planner.crops

    def test_oo02_timeout(self, simple_fields, simple_crops, simple_constraints):
        """OO-02: 短タイムアウト → 実行可能解 or ヒューリスティックフォールバック"""
        # 少し大きめの問題で短タイムアウト
        fields = []
        for i in range(5):
            fields.append(
                Field(field_id=f"F{i:03d}", district="A", name=f"ほ場{i}",
                      area_ha=2.0, history={"R6": "大豆", "R7": "春小麦"})
            )

        planner = RotationPlannerORTools(
            fields=fields,
            past_years=["R6", "R7"],
            future_years=["R8", "R9", "R10"],
            crops=simple_crops,
            constraints=simple_constraints,
        )

        plan, score, errors = planner.solve(timeout_seconds=1)

        # タイムアウトしてもヒューリスティックフォールバックで解が返る
        assert isinstance(plan, dict)
        assert len(plan) > 0

    def test_oo03_high_precision(self, ortools_planner):
        """OO-03: high_precision=True → 解が返る"""
        plan, score, errors = ortools_planner.solve(
            timeout_seconds=10,
            high_precision=True,
        )

        assert isinstance(plan, dict)
        assert len(plan) > 0
