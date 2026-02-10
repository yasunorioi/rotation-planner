"""
隣接筆制約（PRO機能）のテスト

- check_adjacency_constraint() のユニットテスト
- build_adjacency_graph() のテスト
"""

import json
import pytest
from rotation_planner.app.constraints import Constraints
from rotation_planner.app.optimizer import RotationPlannerHeuristic
from rotation_planner.app.utils import Field


# =============================================================================
# テスト用ヘルパー
# =============================================================================

def make_field(field_id: str, area: float = 3.0) -> Field:
    """テスト用Fieldオブジェクト生成"""
    return Field(
        field_id=field_id,
        name=field_id,
        area_ha=area,
        district="test",
        history={},
        beet_forbidden=False,
    )


def make_planner_with_adjacency(
    fields, crops, adjacency_pairs, crop_family_map, enabled=True
):
    """隣接制約付きプランナー生成"""
    constraints = Constraints(
        adjacent_family_enabled=enabled,
        adjacency_pairs=adjacency_pairs,
        crop_family_map=crop_family_map,
    )
    return RotationPlannerHeuristic(
        fields=fields,
        past_years=[],
        future_years=["2026"],
        crops=crops,
        constraints=constraints,
    )


# =============================================================================
# check_adjacency_constraint テスト
# =============================================================================

class TestCheckAdjacencyConstraint:
    """check_adjacency_constraint メソッドのテスト"""

    def test_same_family_adjacent_violates(self):
        """隣接する同科作物 → False（制約違反）"""
        fields = [make_field("A"), make_field("B")]
        crops = ["てんさい", "だいず", "小麦(春播)"]
        planner = make_planner_with_adjacency(
            fields, crops,
            adjacency_pairs=[(0, 1)],
            crop_family_map={"てんさい": "アカザ科", "だいず": "マメ科", "小麦(春播)": "イネ科"},
        )
        # field 1 に "だいず" を配置済み
        plan = {(1, "2026"): "だいず"}
        # field 0 に同じマメ科の作物を置こうとする（だいずはマメ科）
        # → 別の作物で試す。"だいず"はマメ科
        result = planner.check_adjacency_constraint(0, "2026", "だいず", plan)
        assert result is False

    def test_different_family_adjacent_ok(self):
        """隣接する異科作物 → True（OK）"""
        fields = [make_field("A"), make_field("B")]
        crops = ["てんさい", "だいず", "小麦(春播)"]
        planner = make_planner_with_adjacency(
            fields, crops,
            adjacency_pairs=[(0, 1)],
            crop_family_map={"てんさい": "アカザ科", "だいず": "マメ科", "小麦(春播)": "イネ科"},
        )
        plan = {(1, "2026"): "だいず"}
        # field 0 にイネ科の小麦 → マメ科と異なるのでOK
        result = planner.check_adjacency_constraint(0, "2026", "小麦(春播)", plan)
        assert result is True

    def test_disabled_always_true(self):
        """隣接制約無効時 → 常にTrue"""
        fields = [make_field("A"), make_field("B")]
        crops = ["てんさい", "だいず"]
        planner = make_planner_with_adjacency(
            fields, crops,
            adjacency_pairs=[(0, 1)],
            crop_family_map={"てんさい": "アカザ科", "だいず": "マメ科"},
            enabled=False,
        )
        plan = {(1, "2026"): "だいず"}
        # 無効なので同科でもTrue
        result = planner.check_adjacency_constraint(0, "2026", "だいず", plan)
        assert result is True

    def test_no_family_info_ok(self):
        """crop_family_mapにない作物 → True（制約スキップ）"""
        fields = [make_field("A"), make_field("B")]
        crops = ["unknown_crop"]
        planner = make_planner_with_adjacency(
            fields, crops,
            adjacency_pairs=[(0, 1)],
            crop_family_map={},
        )
        plan = {(1, "2026"): "unknown_crop"}
        result = planner.check_adjacency_constraint(0, "2026", "unknown_crop", plan)
        assert result is True

    def test_non_adjacent_fields_ok(self):
        """隣接しないほ場同士 → 制約に引っかからない"""
        fields = [make_field("A"), make_field("B"), make_field("C")]
        crops = ["だいず"]
        planner = make_planner_with_adjacency(
            fields, crops,
            adjacency_pairs=[(0, 1)],  # AとBだけ隣接
            crop_family_map={"だいず": "マメ科"},
        )
        plan = {(2, "2026"): "だいず"}  # Cにだいず
        # AとCは隣接していないのでOK
        result = planner.check_adjacency_constraint(0, "2026", "だいず", plan)
        assert result is True

    def test_get_valid_crops_excludes_same_family(self):
        """get_valid_crops が隣接同科作物を除外する"""
        fields = [make_field("A"), make_field("B")]
        crops = ["てんさい", "だいず", "小麦(春播)"]
        planner = make_planner_with_adjacency(
            fields, crops,
            adjacency_pairs=[(0, 1)],
            crop_family_map={"てんさい": "アカザ科", "だいず": "マメ科", "小麦(春播)": "イネ科"},
        )
        plan = {(1, "2026"): "だいず"}
        valid = planner.get_valid_crops(0, "2026", plan)
        assert "だいず" not in valid
        assert "てんさい" in valid
        assert "小麦(春播)" in valid


# =============================================================================
# build_adjacency_graph テスト
# =============================================================================

class TestBuildAdjacencyGraph:
    """build_adjacency_graph のテスト"""

    def test_adjacent_fields(self):
        """隣接する2ほ場 → ペアが返る"""
        from rotation_planner.field.spatial import build_adjacency_graph
        # 2つの隣接する正方形（北海道の緯度付近）
        fields = [
            {
                "field_code": "F1",
                "coordinates_json": json.dumps([
                    [43.0, 141.0], [43.0, 141.001],
                    [43.001, 141.001], [43.001, 141.0]
                ])
            },
            {
                "field_code": "F2",
                "coordinates_json": json.dumps([
                    [43.0, 141.001], [43.0, 141.002],
                    [43.001, 141.002], [43.001, 141.001]
                ])
            }
        ]
        graph = build_adjacency_graph(fields, buffer_meters=1.0)
        assert "F2" in graph["F1"]
        assert "F1" in graph["F2"]

    def test_distant_fields_no_adjacency(self):
        """離れた2ほ場 → 空"""
        from rotation_planner.field.spatial import build_adjacency_graph
        fields = [
            {
                "field_code": "F1",
                "coordinates_json": json.dumps([
                    [43.0, 141.0], [43.0, 141.001],
                    [43.001, 141.001], [43.001, 141.0]
                ])
            },
            {
                "field_code": "F2",
                "coordinates_json": json.dumps([
                    [43.1, 142.0], [43.1, 142.001],
                    [43.101, 142.001], [43.101, 142.0]
                ])
            }
        ]
        graph = build_adjacency_graph(fields, buffer_meters=1.0)
        assert graph["F1"] == []
        assert graph["F2"] == []

    def test_no_coordinates_skipped(self):
        """座標なしのほ場はスキップ"""
        from rotation_planner.field.spatial import build_adjacency_graph
        fields = [
            {"field_code": "F1", "coordinates_json": ""},
            {"field_code": "F2", "coordinates_json": None},
        ]
        graph = build_adjacency_graph(fields, buffer_meters=1.0)
        assert graph == {}

    def test_get_adjacent_field_pairs(self):
        """get_adjacent_field_pairs のテスト"""
        from rotation_planner.field.spatial import get_adjacent_field_pairs
        fields = [
            {
                "field_code": "F1",
                "coordinates_json": json.dumps([
                    [43.0, 141.0], [43.0, 141.001],
                    [43.001, 141.001], [43.001, 141.0]
                ])
            },
            {
                "field_code": "F2",
                "coordinates_json": json.dumps([
                    [43.0, 141.001], [43.0, 141.002],
                    [43.001, 141.002], [43.001, 141.001]
                ])
            }
        ]
        pairs = get_adjacent_field_pairs(fields, buffer_meters=1.0)
        assert len(pairs) == 1
        assert tuple(sorted(pairs[0])) == ("F1", "F2")
