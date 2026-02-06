"""
集計サービス層 - UI層とDB層を繋ぐ高レベルAPI

Repository + spatial.py + aggregation.py を組み合わせた集計サービスを提供。

Usage:
    from rotation_planner.field.aggregation_service import (
        get_cross_tabulation_for_user,
        copy_crop_polygons_to_next_year,
        get_subsidy_summary,
        export_cross_tabulation_csv,
        build_land_breakdown_for_crop
    )

    # クロス集計表取得
    raw_df, display_df = get_cross_tabulation_for_user(user_id=1, year=2025)

    # 前年度コピー
    count, message = copy_crop_polygons_to_next_year(user_id=1, from_year=2024, to_year=2025)

    # 補助金サマリ
    summary = get_subsidy_summary(user_id=1)

    # CSV出力
    csv_str = export_cross_tabulation_csv(user_id=1, year=2025)
"""

import csv
import io
import logging
from typing import List, Dict, Optional, Tuple, Union
import pandas as pd

from rotation_planner.common.db_access import PaddyPolygonRepository, CropPolygonRepository
from rotation_planner.common.models import LandCategory, PaddyPolygon, CropPolygon, AggregationRow
from rotation_planner.field.spatial import split_crop_by_land_category
from rotation_planner.field.aggregation import (
    CropLandBreakdown, aggregate_by_crop, build_cross_tabulation,
    format_cross_table_for_display, get_conversion_year_columns
)

logger = logging.getLogger(__name__)


# =============================================================================
# 1. get_cross_tabulation_for_user
# =============================================================================

def get_cross_tabulation_for_user(user_id: int, year: int) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    指定ユーザー・年度のクロス集計表を生成。

    処理フロー:
    1. CropPolygonRepository.get_all_for_user_year(user_id, year) で作付けポリゴン取得
    2. PaddyPolygonRepository.get_all_for_user(user_id) で水田ポリゴン取得
    3. 各作付けポリゴンについて split_crop_by_land_category で地目別分割
    4. CropLandBreakdown リスト構築
    5. aggregate_by_crop → build_cross_tabulation → format_cross_table_for_display

    Args:
        user_id: ユーザーID
        year: 年度

    Returns:
        (raw_df, display_df)
        - raw_df: 数値DataFrame（計算用）
        - display_df: 表示用DataFrame（0.0→'-'、小数2桁）

    Example:
        >>> raw_df, display_df = get_cross_tabulation_for_user(user_id=1, year=2025)
        >>> print(display_df)
              作物名  普通畑  畑地化(2020)  畑地化(不明)  水田  合計
        0     大豆   5.23        10.50         2.30  0.00 18.03
        1  てんさい  12.00         0.00         0.00  0.00 12.00
    """
    # 1. 作付けポリゴン取得
    crop_polygons = CropPolygonRepository.get_all_for_user_year(user_id, year)

    # 2. 水田ポリゴン取得
    paddy_polygons = PaddyPolygonRepository.get_all_for_user(user_id)

    # 3. 各作付けポリゴンの地目内訳を計算
    breakdowns: List[CropLandBreakdown] = []
    for crop_poly in crop_polygons:
        breakdown = build_land_breakdown_for_crop(crop_poly, paddy_polygons)
        breakdowns.append(breakdown)

    # 4. 作物別に集約
    agg_rows = aggregate_by_crop(breakdowns)

    # 5. クロス集計表生成
    raw_df = build_cross_tabulation(agg_rows)
    display_df = format_cross_table_for_display(raw_df)

    return raw_df, display_df


# =============================================================================
# 2. copy_crop_polygons_to_next_year
# =============================================================================

def copy_crop_polygons_to_next_year(user_id: int, from_year: int, to_year: int) -> Tuple[int, str]:
    """
    前年度の作付けポリゴンを次年度にコピー。

    Args:
        user_id: ユーザーID
        from_year: コピー元年度
        to_year: コピー先年度

    Returns:
        (コピー件数, メッセージ文字列)

    Example:
        >>> count, message = copy_crop_polygons_to_next_year(1, 2024, 2025)
        >>> print(message)
        "2024年度の作付けポリゴン15件を2025年度にコピーしました"
    """
    count = CropPolygonRepository.copy_from_previous_year(user_id, from_year, to_year)

    if count > 0:
        message = f"{from_year}年度の作付けポリゴン{count}件を{to_year}年度にコピーしました"
    else:
        message = f"{from_year}年度に作付けポリゴンが存在しないため、コピーできませんでした"

    logger.info(f"copy_crop_polygons_to_next_year: user_id={user_id}, {from_year}→{to_year}, count={count}")

    return count, message


# =============================================================================
# 3. get_subsidy_summary
# =============================================================================

def get_subsidy_summary(user_id: int) -> List[Dict]:
    """
    畑地化補助金の残り年数サマリを取得。

    処理:
    1. PaddyPolygonRepository.get_converted(user_id) で畑地化済み取得
    2. PaddyPolygon.from_dict() でモデル化
    3. subsidy_remaining_years プロパティで残年数計算

    Args:
        user_id: ユーザーID

    Returns:
        [{'field_id': int, 'area_ha': float, 'start_year': int|None,
          'remaining_years': int|None}, ...]

    Example:
        >>> summary = get_subsidy_summary(user_id=1)
        >>> print(summary)
        [
            {'field_id': 1, 'area_ha': 5.5, 'start_year': 2020, 'remaining_years': 2},
            {'field_id': 2, 'area_ha': 3.2, 'start_year': None, 'remaining_years': None}
        ]
    """
    converted_polygons = PaddyPolygonRepository.get_converted(user_id)

    summary = []
    for poly_dict in converted_polygons:
        poly = PaddyPolygon.from_dict(poly_dict)
        summary.append({
            'field_id': poly.field_id,
            'area_ha': poly.area_ha,
            'start_year': poly.conversion_start_year,
            'remaining_years': poly.subsidy_remaining_years
        })

    return summary


# =============================================================================
# 4. export_cross_tabulation_csv
# =============================================================================

def export_cross_tabulation_csv(user_id: int, year: int) -> str:
    """
    クロス集計表をCSV文字列として出力。

    処理:
    1. get_cross_tabulation_for_user でraw_df取得
    2. io.StringIO + csv.writer で日本語ヘッダ付きCSV生成

    Args:
        user_id: ユーザーID
        year: 年度

    Returns:
        CSV文字列（UTF-8, BOM付き推奨）

    Example:
        >>> csv_str = export_cross_tabulation_csv(user_id=1, year=2025)
        >>> with open('output.csv', 'w', encoding='utf-8-sig') as f:
        ...     f.write(csv_str)
    """
    raw_df, display_df = get_cross_tabulation_for_user(user_id, year)

    # StringIO でCSV文字列を生成
    output = io.StringIO()
    # UTF-8 BOM付きで出力（Excel対応）
    output.write('\ufeff')  # BOM

    writer = csv.writer(output)

    # ヘッダ行
    writer.writerow(display_df.columns.tolist())

    # データ行
    for _, row in display_df.iterrows():
        writer.writerow(row.tolist())

    csv_str = output.getvalue()
    output.close()

    logger.info(f"export_cross_tabulation_csv: user_id={user_id}, year={year}, rows={len(display_df)}")

    return csv_str


# =============================================================================
# 5. build_land_breakdown_for_crop
# =============================================================================

def build_land_breakdown_for_crop(crop_polygon: dict, paddy_polygons: list) -> CropLandBreakdown:
    """
    1件の作付けポリゴンの地目内訳を計算。

    処理:
    1. split_crop_by_land_category で地目分割
    2. 各部分を LandCategory ごとに集計
    3. 畑地化部分は conversion_start_year で年度別に分類
    4. CropLandBreakdown を返す

    Args:
        crop_polygon: dict (id, field_id, year, crop_name, geometry, area_ha, ...)
        paddy_polygons: list of dict (id, field_id, geometry, is_converted, conversion_start_year, ...)

    Returns:
        CropLandBreakdown

    Example:
        >>> breakdown = build_land_breakdown_for_crop(
        ...     {'crop_name': '大豆', 'field_id': 1, 'year': 2025, 'geometry': '...', ...},
        ...     [{'field_id': 1, 'is_converted': 1, 'conversion_start_year': 2020, ...}, ...]
        ... )
        >>> print(breakdown.crop_name, breakdown.total_area_ha)
        "大豆" 12.5
    """
    crop_name = crop_polygon['crop_name']
    field_id = crop_polygon['field_id']
    year = crop_polygon['year']
    crop_geom_str = crop_polygon['geometry']

    # 地目分割（GeoJSON文字列を直接渡す）
    split_result = split_crop_by_land_category(crop_geom_str, paddy_polygons)

    # 各カテゴリの面積を集計
    field_area_ha = 0.0  # 普通畑
    converted_areas: Dict[Union[int, str], float] = {}  # {年度|'unknown': 面積}
    paddy_area_ha = 0.0  # 水田

    for item in split_result:
        category = item['land_category']
        area_ha = item['area_ha']
        conversion_year = item.get('conversion_start_year')

        if category == LandCategory.FIELD:
            field_area_ha += area_ha
        elif category == LandCategory.CONVERTED:
            year_key = conversion_year if conversion_year is not None else 'unknown'
            converted_areas[year_key] = converted_areas.get(year_key, 0.0) + area_ha
        elif category == LandCategory.PADDY:
            paddy_area_ha += area_ha

    total_area_ha = field_area_ha + sum(converted_areas.values()) + paddy_area_ha

    return CropLandBreakdown(
        crop_name=crop_name,
        field_id=field_id,
        year=year,
        field_area_ha=field_area_ha,
        converted_areas=converted_areas,
        paddy_area_ha=paddy_area_ha,
        total_area_ha=total_area_ha
    )
