"""
field/map.py の単体テスト
"""
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from rotation_planner.field.map import (
    calculate_area_from_coords,
    m2_to_a,
    m2_to_ha,
)


@pytest.mark.db
class TestMapUnit:
    """field/map.py のテストクラス"""

    def test_MA01_calculate_area_from_coords_square(self):
        """
        MA-01: calculate_area_from_coords 正方形
        期待結果: ~10000 m2
        """
        # 北海道（北緯43度付近）で約100m×100mの正方形
        # 緯度1度 ≈ 111km、経度1度 ≈ 81km（北緯43度）
        # 100m ≈ 0.0009度（緯度）、0.00123度（経度）
        base_lat = 43.0
        base_lng = 141.0

        # 100m × 100m の正方形（反時計回り）
        coordinates = [
            [base_lat, base_lng],                                    # 左下
            [base_lat + 0.0009, base_lng],                          # 左上
            [base_lat + 0.0009, base_lng + 0.00123],                # 右上
            [base_lat, base_lng + 0.00123],                         # 右下
        ]

        area = calculate_area_from_coords(coordinates)

        # 100m × 100m = 10000 m2 に近い値であることを確認
        # 測地線計算なので誤差を許容（±10%）
        assert 9000 <= area <= 11000, f"面積が期待範囲外: {area} m2"
        assert area > 0, "面積は正の値であること"

    def test_MA02_calculate_area_from_coords_triangle(self):
        """
        MA-02: calculate_area_from_coords 三角形
        期待結果: 正の面積
        """
        # 北海道付近の三角形（3点）
        coordinates = [
            [43.0, 141.0],
            [43.001, 141.0],
            [43.0005, 141.001],
        ]

        area = calculate_area_from_coords(coordinates)

        # 三角形なので正の面積が返ること
        assert area > 0, "三角形の面積は正の値であること"
        # 約50m × 100m の三角形なので 2500 m2 程度
        assert 1000 <= area <= 10000, f"面積が期待範囲外: {area} m2"

    def test_MA03_calculate_area_from_coords_two_points_or_less(self):
        """
        MA-03: calculate_area_from_coords 2点以下
        期待結果: 0 or エラー
        """
        # 2点の場合
        coordinates_2 = [
            [43.0, 141.0],
            [43.001, 141.0],
        ]
        area_2 = calculate_area_from_coords(coordinates_2)
        assert area_2 == 0.0, "2点の場合は 0.0 を返すこと"

        # 1点の場合
        coordinates_1 = [
            [43.0, 141.0],
        ]
        area_1 = calculate_area_from_coords(coordinates_1)
        assert area_1 == 0.0, "1点の場合は 0.0 を返すこと"

        # 0点の場合
        coordinates_0 = []
        area_0 = calculate_area_from_coords(coordinates_0)
        assert area_0 == 0.0, "0点の場合は 0.0 を返すこと"

    def test_MA04_m2_to_ha_conversion(self):
        """
        MA-04: m2_to_ha 変換
        期待結果: m²÷10000
        """
        # 10000 m2 = 1 ha
        result = m2_to_ha(10000)
        assert result == 1.0, "10000 m2 は 1.0 ha であること"

        # 25000 m2 = 2.5 ha
        result = m2_to_ha(25000)
        assert result == 2.5, "25000 m2 は 2.5 ha であること"

        # 0 m2 = 0 ha
        result = m2_to_ha(0)
        assert result == 0.0, "0 m2 は 0.0 ha であること"

        # 1 m2 = 0.0001 ha
        result = m2_to_ha(1)
        assert result == 0.0001, "1 m2 は 0.0001 ha であること"

    def test_MA05_m2_to_a_conversion(self):
        """
        MA-05: m2_to_a 変換
        期待結果: m²÷100
        """
        # 100 m2 = 1 a
        result = m2_to_a(100)
        assert result == 1.0, "100 m2 は 1.0 a であること"

        # 250 m2 = 2.5 a
        result = m2_to_a(250)
        assert result == 2.5, "250 m2 は 2.5 a であること"

        # 0 m2 = 0 a
        result = m2_to_a(0)
        assert result == 0.0, "0 m2 は 0.0 a であること"

        # 1 m2 = 0.01 a
        result = m2_to_a(1)
        assert result == 0.01, "1 m2 は 0.01 a であること"

    def test_MA06_calculate_area_non_negative(self):
        """
        MA-06: calculate_area 負の面積にならない
        期待結果: >= 0
        """
        # 様々な座標パターンで面積が負にならないことを確認

        # 通常の四角形
        coords_square = [
            [43.0, 141.0],
            [43.001, 141.0],
            [43.001, 141.001],
            [43.0, 141.001],
        ]
        area_square = calculate_area_from_coords(coords_square)
        assert area_square >= 0, "正方形の面積は非負であること"

        # 時計回りの座標（符号が反転する可能性）
        coords_clockwise = [
            [43.0, 141.0],
            [43.0, 141.001],
            [43.001, 141.001],
            [43.001, 141.0],
        ]
        area_clockwise = calculate_area_from_coords(coords_clockwise)
        assert area_clockwise >= 0, "時計回りでも面積は非負であること"

        # 反時計回りの座標
        coords_counterclockwise = [
            [43.0, 141.0],
            [43.001, 141.0],
            [43.001, 141.001],
            [43.0, 141.001],
        ]
        area_counterclockwise = calculate_area_from_coords(coords_counterclockwise)
        assert area_counterclockwise >= 0, "反時計回りでも面積は非負であること"

        # 三角形
        coords_triangle = [
            [43.0, 141.0],
            [43.002, 141.0],
            [43.001, 141.002],
        ]
        area_triangle = calculate_area_from_coords(coords_triangle)
        assert area_triangle >= 0, "三角形の面積は非負であること"

        # 複雑な多角形
        coords_complex = [
            [43.0, 141.0],
            [43.002, 141.0],
            [43.003, 141.001],
            [43.002, 141.002],
            [43.001, 141.002],
            [43.0, 141.001],
        ]
        area_complex = calculate_area_from_coords(coords_complex)
        assert area_complex >= 0, "複雑な多角形の面積は非負であること"
