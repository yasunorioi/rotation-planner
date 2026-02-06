"""
ほ場面積集計モジュール

作付け×地目の内訳を集約し、クロス集計表を生成する。
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Union
import pandas as pd

from rotation_planner.common.models import LandCategory, AggregationRow


# =============================================================================
# CropLandBreakdown
# =============================================================================

@dataclass
class CropLandBreakdown:
    """作付け1件の地目内訳"""
    crop_name: str
    field_id: int
    year: int
    field_area_ha: float = 0.0
    converted_areas: dict = field(default_factory=dict)  # {year_or_'unknown': area_ha}
    paddy_area_ha: float = 0.0
    total_area_ha: float = 0.0


# =============================================================================
# aggregate_by_crop
# =============================================================================

def aggregate_by_crop(breakdowns: List[CropLandBreakdown]) -> List[AggregationRow]:
    """
    CropLandBreakdown のリストを作物名でグループ化し、AggregationRow に集約。

    ロジック:
    1. crop_name でグループ化
    2. 各グループ内で field_area_ha, paddy_area_ha を合計
    3. converted_areas は年度別にマージ（同じ年度は面積を加算）
    4. AggregationRow として返す
    """
    groups: Dict[str, List[CropLandBreakdown]] = {}
    for bd in breakdowns:
        groups.setdefault(bd.crop_name, []).append(bd)

    rows = []
    for crop_name, items in groups.items():
        field_area = sum(bd.field_area_ha for bd in items)
        paddy_area = sum(bd.paddy_area_ha for bd in items)

        # converted_areas を年度別にマージ
        merged_converted: Dict[Union[int, str], float] = {}
        for bd in items:
            for year_key, area in bd.converted_areas.items():
                merged_converted[year_key] = merged_converted.get(year_key, 0.0) + area

        total = field_area + paddy_area + sum(merged_converted.values())

        rows.append(AggregationRow(
            crop_name=crop_name,
            field_area_ha=field_area,
            converted_areas=merged_converted,
            paddy_area_ha=paddy_area,
        ))

    return rows


# =============================================================================
# get_conversion_year_columns
# =============================================================================

def get_conversion_year_columns(rows: List[AggregationRow]) -> List[str]:
    """
    集計表で使用する畑地化年度の列名リストを返す。

    全AggregationRowの converted_areas キーを収集し、昇順ソート。
    int年度は「畑地化(YYYY)」、'unknown'は「畑地化(不明)」に変換。
    """
    year_keys: set = set()
    for row in rows:
        year_keys.update(row.converted_areas.keys())

    # int と str('unknown') を分離してソート
    int_keys = sorted(k for k in year_keys if isinstance(k, int))
    has_unknown = 'unknown' in year_keys

    columns = [f"畑地化({k})" for k in int_keys]
    if has_unknown:
        columns.append("畑地化(不明)")

    return columns


# =============================================================================
# build_cross_tabulation
# =============================================================================

def build_cross_tabulation(rows: List[AggregationRow]) -> pd.DataFrame:
    """
    AggregationRow のリストからクロス集計表DataFrameを作成。

    行: 作物名
    列: 畑 | 畑地化(YYYY) | ... | 畑地化(不明) | 水田 | 合計
    最終行に「合計」行を追加。
    """
    conversion_cols = get_conversion_year_columns(rows)
    all_columns = ["作物", "畑"] + conversion_cols + ["水田", "合計"]

    data = []
    for row in rows:
        record = {
            "作物": row.crop_name,
            "畑": row.field_area_ha,
            "水田": row.paddy_area_ha,
            "合計": row.total_area,
        }
        # 畑地化列を埋める
        for col in conversion_cols:
            if col == "畑地化(不明)":
                record[col] = row.converted_areas.get('unknown', 0.0)
            else:
                # 「畑地化(YYYY)」からYYYYを抽出
                year_str = col.replace("畑地化(", "").replace(")", "")
                try:
                    year_int = int(year_str)
                    record[col] = row.converted_areas.get(year_int, 0.0)
                except ValueError:
                    record[col] = 0.0

        data.append(record)

    df = pd.DataFrame(data, columns=all_columns)

    # 合計行を追加
    totals = {"作物": "合計"}
    for col in all_columns[1:]:  # 「作物」列以外
        totals[col] = df[col].sum()

    totals_df = pd.DataFrame([totals], columns=all_columns)
    df = pd.concat([df, totals_df], ignore_index=True)

    return df


# =============================================================================
# format_cross_table_for_display
# =============================================================================

def format_cross_table_for_display(df: pd.DataFrame) -> pd.DataFrame:
    """
    表示用フォーマット:
    - 0.0 → '-'（ダッシュ）
    - 小数点以下2桁
    """
    display_df = df.copy()

    for col in display_df.columns:
        if col == "作物":
            continue
        display_df[col] = display_df[col].apply(
            lambda x: "-" if x == 0.0 or x == 0 else f"{x:.2f}"
        )

    return display_df
