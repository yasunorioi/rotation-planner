"""
rotation_planner.field.spatial - 空間演算モジュール

Shapely + pyprojを使った座標変換、面積計算、地目判定機能を提供。

Usage:
    from rotation_planner.field.spatial import (
        coords_to_shapely, shapely_to_coords,
        geojson_to_shapely, shapely_to_geojson,
        calculate_geodesic_area_ha,
        determine_land_category, split_crop_by_land_category,
        merge_paddy_polygons
    )
"""

import json
from typing import Union
from shapely.geometry import shape, mapping, Polygon, MultiPolygon
from shapely.ops import unary_union
from pyproj import Geod

from rotation_planner.common.models import LandCategory


# =============================================================================
# 座標変換関数
# =============================================================================

def coords_to_shapely(coords: list[list[float]]) -> Polygon:
    """
    [[lat, lng], ...] 形式 → Shapely Polygon

    Args:
        coords: [[lat, lng], ...] 形式の座標リスト

    Returns:
        Shapely Polygon（座標は (lng, lat) 形式）

    Notes:
        - 既存コードの座標形式は [lat, lng]
        - Shapely は (x, y) = (lng, lat) なので変換が必要
        - 最初と最後の座標が同じでなければ自動的に閉じる
    """
    if len(coords) < 3:
        raise ValueError("ポリゴンには最低3点の座標が必要です")

    # [lat, lng] → (lng, lat) に変換
    coords_lnglat = [(coord[1], coord[0]) for coord in coords]

    # ポリゴンを閉じる（最初と最後が同じでなければ）
    if coords_lnglat[0] != coords_lnglat[-1]:
        coords_lnglat.append(coords_lnglat[0])

    return Polygon(coords_lnglat)


def shapely_to_coords(polygon: Polygon) -> list[list[float]]:
    """
    Shapely Polygon → [[lat, lng], ...] 形式

    Args:
        polygon: Shapely Polygon

    Returns:
        [[lat, lng], ...] 形式の座標リスト
    """
    # Shapely の exterior.coords は (lng, lat) 形式
    # [lat, lng] 形式に戻す
    coords = [[lat, lng] for lng, lat in polygon.exterior.coords[:-1]]
    return coords


def geojson_to_shapely(geojson_str: str) -> Union[Polygon, MultiPolygon]:
    """
    GeoJSON文字列 → Shapely geometry

    Args:
        geojson_str: GeoJSON文字列

    Returns:
        Shapely Polygon or MultiPolygon

    Raises:
        ValueError: 不正なGeoJSON形式
    """
    try:
        geojson_dict = json.loads(geojson_str)
        geom = shape(geojson_dict)

        if not isinstance(geom, (Polygon, MultiPolygon)):
            raise ValueError(f"ポリゴンまたはマルチポリゴンが必要です（実際: {type(geom).__name__}）")

        return geom
    except json.JSONDecodeError as e:
        raise ValueError(f"不正なJSON形式: {e}")
    except Exception as e:
        raise ValueError(f"GeoJSON解析エラー: {e}")


def shapely_to_geojson(geom: Union[Polygon, MultiPolygon]) -> str:
    """
    Shapely geometry → GeoJSON文字列

    Args:
        geom: Shapely Polygon or MultiPolygon

    Returns:
        GeoJSON文字列
    """
    geojson_dict = mapping(geom)
    return json.dumps(geojson_dict)


# =============================================================================
# 面積計算関数
# =============================================================================

def calculate_geodesic_area_ha(polygon: Polygon) -> float:
    """
    Shapely Polygon → 測地線面積（ヘクタール）

    Args:
        polygon: Shapely Polygon（座標は (lng, lat) 形式）

    Returns:
        面積（ヘクタール）

    Notes:
        - WGS84楕円体上の面積を正確に計算
        - pyproj.Geod を使用
        - Shapely座標は (lng, lat) なので、そのまま渡せる
    """
    if polygon.is_empty:
        return 0.0

    # 外周の座標を取得
    coords = list(polygon.exterior.coords)

    # 座標リストを分離
    lons = [c[0] for c in coords]
    lats = [c[1] for c in coords]

    # Geod（測地線計算）を使用して面積を計算
    geod = Geod(ellps="WGS84")

    # polygon_area_perimeter は (面積, 周長) を返す
    # 面積は符号付きで返されるので abs() を使用
    area_m2, _ = geod.polygon_area_perimeter(lons, lats)

    # 平方メートルをヘクタールに変換（1ha = 10,000m²）
    area_ha = abs(area_m2) / 10000.0

    return area_ha


# =============================================================================
# 地目判定関数
# =============================================================================

def determine_land_category(
    crop_geom: Polygon,
    paddy_polygons: list[dict]
) -> list[tuple[Polygon, LandCategory, float]]:
    """
    作付けポリゴンと水田ポリゴン群を空間演算し、地目別に分割する。

    Args:
        crop_geom: 作付けポリゴン（Shapely Polygon）
        paddy_polygons: 水田ポリゴンのリスト。各dictは:
            {'geometry': GeoJSON文字列, 'is_converted': bool}

    Returns:
        [(polygon, land_category, area_ha), ...] のリスト
        - 水田ポリゴンとの交差部分 → PADDY or CONVERTED
        - 残り部分 → FIELD

    Raises:
        ValueError: 不正なGeoJSON形式
    """
    result = []
    remaining_geom = crop_geom

    # 各水田ポリゴンと交差計算
    for paddy_data in paddy_polygons:
        # GeoJSON文字列をShapelyに変換
        paddy_geom = geojson_to_shapely(paddy_data['geometry'])
        is_converted = paddy_data.get('is_converted', False)

        # 交差部分を計算
        intersection = crop_geom.intersection(paddy_geom)

        # 交差部分が空でなければ結果に追加
        if not intersection.is_empty:
            # MultiPolygonの場合は各Polygonを個別に処理
            if isinstance(intersection, MultiPolygon):
                for poly in intersection.geoms:
                    if not poly.is_empty:
                        area_ha = calculate_geodesic_area_ha(poly)
                        category = LandCategory.CONVERTED if is_converted else LandCategory.PADDY
                        result.append((poly, category, area_ha))
            elif isinstance(intersection, Polygon):
                area_ha = calculate_geodesic_area_ha(intersection)
                category = LandCategory.CONVERTED if is_converted else LandCategory.PADDY
                result.append((intersection, category, area_ha))

            # 残り部分を更新
            remaining_geom = remaining_geom.difference(paddy_geom)

    # 残り部分を FIELD として追加
    if not remaining_geom.is_empty:
        # MultiPolygonの場合は各Polygonを個別に処理
        if isinstance(remaining_geom, MultiPolygon):
            for poly in remaining_geom.geoms:
                if not poly.is_empty:
                    area_ha = calculate_geodesic_area_ha(poly)
                    result.append((poly, LandCategory.FIELD, area_ha))
        elif isinstance(remaining_geom, Polygon):
            area_ha = calculate_geodesic_area_ha(remaining_geom)
            result.append((remaining_geom, LandCategory.FIELD, area_ha))

    return result


def split_crop_by_land_category(
    crop_geojson: str,
    paddy_polygons: list[dict]
) -> list[dict]:
    """
    DB格納形式のラッパー。作付けポリゴンを地目別に分割。

    Args:
        crop_geojson: 作付けポリゴンのGeoJSON文字列
        paddy_polygons: DBから取得した水田ポリゴンのリスト
            [{'geometry': geojson_str, 'is_converted': bool}, ...]

    Returns:
        [{'geometry': geojson_str, 'land_category': LandCategory, 'area_ha': float}, ...]

    Raises:
        ValueError: 不正なGeoJSON形式
    """
    # GeoJSON文字列をShapelyに変換
    crop_geom = geojson_to_shapely(crop_geojson)

    # 地目判定
    parts = determine_land_category(crop_geom, paddy_polygons)

    # 結果をDB格納形式に変換
    result = []
    for poly, category, area_ha in parts:
        result.append({
            'geometry': shapely_to_geojson(poly),
            'land_category': category,
            'area_ha': area_ha
        })

    return result


def merge_paddy_polygons(geojson_list: list[str]) -> str:
    """
    複数の水田ポリゴンを結合（unary_union）してGeoJSON文字列を返す。

    Args:
        geojson_list: GeoJSON文字列のリスト

    Returns:
        結合されたポリゴンのGeoJSON文字列

    Raises:
        ValueError: 不正なGeoJSON形式、または空のリスト

    Notes:
        - 合筆等で使用
        - unary_union は隣接するポリゴンを結合し、重複部分を除去
        - 結果はPolygonまたはMultiPolygonになる可能性がある
    """
    if not geojson_list:
        raise ValueError("結合するポリゴンが指定されていません")

    # 全てのGeoJSONをShapelyに変換
    polygons = [geojson_to_shapely(gj) for gj in geojson_list]

    # unary_union で結合
    merged = unary_union(polygons)

    # GeoJSON文字列に変換して返す
    return shapely_to_geojson(merged)


# =============================================================================
# エクスポート
# =============================================================================

__all__ = [
    'coords_to_shapely',
    'shapely_to_coords',
    'geojson_to_shapely',
    'shapely_to_geojson',
    'calculate_geodesic_area_ha',
    'determine_land_category',
    'split_crop_by_land_category',
    'merge_paddy_polygons',
]
