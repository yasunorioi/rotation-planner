"""
隣接判定のテスト
- build_adjacency_graph
- get_adjacent_field_pairs
"""
import pytest
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from rotation_planner.field.spatial import (
    build_adjacency_graph,
    get_adjacent_field_pairs,
    _meters_to_degrees,
)


# =============================================================================
# テスト用ほ場データ（北海道十勝付近 緯度43度）
# =============================================================================

def make_field(field_code: str, coords: list) -> dict:
    """テスト用ほ場dictを作成"""
    return {
        'field_code': field_code,
        'coordinates_json': json.dumps(coords),
    }


# 隣接する2つの正方形ほ場（共有辺あり）
# A: (0,0)-(0,0.001)-(0.001,0.001)-(0.001,0) → [lat,lng]形式
FIELD_A_COORDS = [
    [43.0, 141.0],
    [43.0, 141.001],
    [43.001, 141.001],
    [43.001, 141.0],
]
# B: Aの東隣（経度方向に隣接）
FIELD_B_COORDS = [
    [43.0, 141.001],
    [43.0, 141.002],
    [43.001, 141.002],
    [43.001, 141.001],
]
# C: Aから離れた場所（1km以上離れている）
FIELD_C_COORDS = [
    [43.1, 141.1],
    [43.1, 141.101],
    [43.101, 141.101],
    [43.101, 141.1],
]
# D: Aから0.5mギャップ（非常に近い）
# 経度方向に約0.5mのギャップ ≈ 約0.0000065度
FIELD_D_COORDS = [
    [43.0, 141.00100650],
    [43.0, 141.002],
    [43.001, 141.002],
    [43.001, 141.00100650],
]


class TestBuildAdjacencyGraph:
    """build_adjacency_graph のテスト"""

    def test_adjacent_fields_detected(self):
        """隣接する2ほ場が検出される"""
        fields = [make_field("A", FIELD_A_COORDS), make_field("B", FIELD_B_COORDS)]
        graph = build_adjacency_graph(fields)
        assert "B" in graph["A"]
        assert "A" in graph["B"]

    def test_distant_fields_not_adjacent(self):
        """離れたほ場は隣接しない"""
        fields = [make_field("A", FIELD_A_COORDS), make_field("C", FIELD_C_COORDS)]
        graph = build_adjacency_graph(fields)
        assert "C" not in graph["A"]
        assert "A" not in graph["C"]

    def test_small_gap_detected_with_buffer(self):
        """0.5mギャップでもバッファ1mなら検出される"""
        fields = [make_field("A", FIELD_A_COORDS), make_field("D", FIELD_D_COORDS)]
        graph = build_adjacency_graph(fields, buffer_meters=1.0)
        assert "D" in graph["A"]

    def test_no_coordinates_skipped(self):
        """座標なしほ場はスキップ"""
        fields = [
            make_field("A", FIELD_A_COORDS),
            {'field_code': 'X', 'coordinates_json': None},
        ]
        graph = build_adjacency_graph(fields)
        assert "X" not in graph
        assert "A" in graph
        assert len(graph["A"]) == 0

    def test_single_field_no_adjacency(self):
        """1ほ場のみ→隣接なし"""
        fields = [make_field("A", FIELD_A_COORDS)]
        graph = build_adjacency_graph(fields)
        assert graph == {"A": []}

    def test_empty_fields(self):
        """空リスト→空グラフ"""
        graph = build_adjacency_graph([])
        assert graph == {}

    def test_three_fields_chain(self):
        """3ほ場チェーン（A-B隣接、B-C離れている）"""
        fields = [
            make_field("A", FIELD_A_COORDS),
            make_field("B", FIELD_B_COORDS),
            make_field("C", FIELD_C_COORDS),
        ]
        graph = build_adjacency_graph(fields)
        assert "B" in graph["A"]
        assert "A" in graph["B"]
        assert "C" not in graph["A"]
        assert "C" not in graph["B"]

    def test_invalid_coordinates_skipped(self):
        """不正な座標はスキップ"""
        fields = [
            make_field("A", FIELD_A_COORDS),
            {'field_code': 'BAD', 'coordinates_json': 'not-json'},
        ]
        graph = build_adjacency_graph(fields)
        assert "BAD" not in graph


class TestGetAdjacentFieldPairs:
    """get_adjacent_field_pairs のテスト"""

    def test_basic_pairs(self):
        """基本的なペア取得"""
        fields = [
            make_field("A", FIELD_A_COORDS),
            make_field("B", FIELD_B_COORDS),
            make_field("C", FIELD_C_COORDS),
        ]
        pairs = get_adjacent_field_pairs(fields)
        assert len(pairs) == 1
        pair = pairs[0]
        assert set(pair) == {"A", "B"}

    def test_no_duplicates(self):
        """重複なし（A-BとB-Aは1つだけ）"""
        fields = [make_field("A", FIELD_A_COORDS), make_field("B", FIELD_B_COORDS)]
        pairs = get_adjacent_field_pairs(fields)
        assert len(pairs) == 1


class TestMetersToDegreesHelper:
    """_meters_to_degrees ヘルパーのテスト"""

    def test_approximate_conversion(self):
        """1m ≈ 0.000009度 @ 北緯43度"""
        deg = _meters_to_degrees(1.0, latitude=43.0)
        assert 0.000005 < deg < 0.000015  # 大まかな範囲
