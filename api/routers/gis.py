"""
GISルーター

水田ポリゴン、作付けポリゴン、面積集計
"""

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import Response
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import json
import logging

from rotation_planner.common.db_access import (
    PaddyPolygonRepository,
    CropPolygonRepository,
    FieldRepository,
    ensure_paddy_polygons_table,
    ensure_crop_polygons_table,
)
from rotation_planner.field.spatial import geojson_to_shapely, calculate_geodesic_area_ha
from rotation_planner.field.aggregation_service import (
    get_cross_tabulation_for_user,
    export_cross_tabulation_csv,
    get_subsidy_summary,
    build_land_breakdown_for_crop,
)
from rotation_planner.field.aggregation import get_conversion_year_columns
from api.error_handlers import require_found
from api.deps import get_current_user

router = APIRouter(tags=["GIS"])
logger = logging.getLogger("rotation_planner.api")


# =============================================================================
# Pydantic モデル
# =============================================================================

class PaddyPolygonCreate(BaseModel):
    field_id: int
    geometry: dict
    is_converted: bool = False
    conversion_start_year: Optional[int] = None
    source: str = "manual"
    notes: Optional[str] = None


class PaddyPolygonUpdate(BaseModel):
    geometry: Optional[dict] = None
    is_converted: Optional[bool] = None
    conversion_start_year: Optional[int] = None
    source: Optional[str] = None
    notes: Optional[str] = None


class PaddyPolygonResponse(BaseModel):
    id: int
    field_id: int
    geometry: dict
    area_ha: float
    is_converted: bool
    conversion_start_year: Optional[int] = None
    source: str = "manual"
    notes: Optional[str] = None


class CropPolygonCreate(BaseModel):
    field_id: int
    year: int
    crop_name: str
    geometry: dict
    notes: Optional[str] = None


class CropPolygonUpdate(BaseModel):
    year: Optional[int] = None
    crop_name: Optional[str] = None
    geometry: Optional[dict] = None
    notes: Optional[str] = None


class CropPolygonResponse(BaseModel):
    id: int
    field_id: int
    year: int
    crop_name: str
    geometry: dict
    area_ha: float
    notes: Optional[str] = None


class CropPolygonCopyRequest(BaseModel):
    from_year: int
    to_year: int


# =============================================================================
# ヘルパー関数
# =============================================================================

def _polygon_to_response(p: Dict[str, Any]) -> PaddyPolygonResponse:
    """DB行をPaddyPolygonResponseに変換"""
    geom = p.get("geometry", "{}")
    if isinstance(geom, str):
        geom = json.loads(geom)
    return PaddyPolygonResponse(
        id=p["id"],
        field_id=p["field_id"],
        geometry=geom,
        area_ha=p.get("area_ha", 0),
        is_converted=bool(p.get("is_converted", 0)),
        conversion_start_year=p.get("conversion_start_year"),
        source=p.get("source", "manual"),
        notes=p.get("notes"),
    )


def _crop_polygon_to_response(p: Dict[str, Any]) -> CropPolygonResponse:
    """DB行をCropPolygonResponseに変換"""
    geom = p.get("geometry", "{}")
    if isinstance(geom, str):
        geom = json.loads(geom)
    return CropPolygonResponse(
        id=p["id"],
        field_id=p["field_id"],
        year=p["year"],
        crop_name=p["crop_name"],
        geometry=geom,
        area_ha=p.get("area_ha", 0),
        notes=p.get("notes"),
    )


# =============================================================================
# 水田ポリゴン（Paddy Polygons）エンドポイント
# =============================================================================

@router.get("/api/paddy-polygons", response_model=List[PaddyPolygonResponse])
def list_paddy_polygons(
    field_id: Optional[int] = None,
    current_user: Dict = Depends(get_current_user),
):
    """ほ場別水田ポリゴン一覧（field_id未指定時はユーザー全体）"""
    ensure_paddy_polygons_table()
    if field_id is not None:
        rows = PaddyPolygonRepository.get_by_field(field_id)
    else:
        rows = PaddyPolygonRepository.get_all_for_user(current_user["id"])
    return [_polygon_to_response(r) for r in rows]


@router.get("/api/paddy-polygons/stats")
def paddy_polygon_stats(current_user: Dict = Depends(get_current_user)):
    """水田ポリゴン統計情報"""
    ensure_paddy_polygons_table()
    return PaddyPolygonRepository.get_stats(current_user["id"])


@router.get("/api/paddy-polygons/{polygon_id}", response_model=PaddyPolygonResponse)
def get_paddy_polygon(polygon_id: int, current_user: Dict = Depends(get_current_user)):
    """水田ポリゴン詳細"""
    ensure_paddy_polygons_table()
    p = require_found(PaddyPolygonRepository.get_by_id(polygon_id), "水田ポリゴン")
    return _polygon_to_response(p)


@router.post("/api/paddy-polygons", response_model=PaddyPolygonResponse, status_code=201)
def create_paddy_polygon(req: PaddyPolygonCreate, current_user: Dict = Depends(get_current_user)):
    """水田ポリゴン作成（area_haはgeometryから自動計算）"""
    ensure_paddy_polygons_table()

    # ほ場の存在・所有確認
    field = require_found(FieldRepository.get_field(req.field_id), "ほ場")
    if field.get("user_id") != current_user["id"]:
        raise HTTPException(status_code=403, detail="このほ場にアクセスする権限がありません")

    # GeoJSON → 面積自動計算
    geometry_str = json.dumps(req.geometry)
    try:
        polygon = geojson_to_shapely(geometry_str)
        area_ha = calculate_geodesic_area_ha(polygon)
    except (ValueError, TypeError, KeyError) as e:
        raise HTTPException(status_code=400, detail=f"ジオメトリの解析に失敗: {e}")

    polygon_id = PaddyPolygonRepository.create(
        field_id=req.field_id,
        geometry=geometry_str,
        area_ha=area_ha,
        is_converted=req.is_converted,
        conversion_start_year=req.conversion_start_year,
        source=req.source,
        notes=req.notes,
    )
    p = PaddyPolygonRepository.get_by_id(polygon_id)
    return _polygon_to_response(p)


@router.put("/api/paddy-polygons/{polygon_id}", response_model=PaddyPolygonResponse)
def update_paddy_polygon(
    polygon_id: int,
    req: PaddyPolygonUpdate,
    current_user: Dict = Depends(get_current_user),
):
    """水田ポリゴン更新"""
    ensure_paddy_polygons_table()

    p = require_found(PaddyPolygonRepository.get_by_id(polygon_id), "水田ポリゴン")
    field = FieldRepository.get_field(p["field_id"])
    if not field or field.get("user_id") != current_user["id"]:
        raise HTTPException(status_code=403, detail="このポリゴンを更新する権限がありません")

    kwargs = {}
    if req.geometry is not None:
        geometry_str = json.dumps(req.geometry)
        try:
            polygon = geojson_to_shapely(geometry_str)
            kwargs['geometry'] = geometry_str
            kwargs['area_ha'] = calculate_geodesic_area_ha(polygon)
        except (ValueError, TypeError, KeyError) as e:
            raise HTTPException(status_code=400, detail=f"ジオメトリの解析に失敗: {e}")
    if req.is_converted is not None:
        kwargs['is_converted'] = req.is_converted
    if req.conversion_start_year is not None:
        kwargs['conversion_start_year'] = req.conversion_start_year
    if req.source is not None:
        kwargs['source'] = req.source
    if req.notes is not None:
        kwargs['notes'] = req.notes

    if not kwargs:
        raise HTTPException(status_code=400, detail="更新するフィールドがありません")

    PaddyPolygonRepository.update(polygon_id, **kwargs)
    updated = PaddyPolygonRepository.get_by_id(polygon_id)
    return _polygon_to_response(updated)


@router.delete("/api/paddy-polygons/{polygon_id}")
def delete_paddy_polygon(polygon_id: int, current_user: Dict = Depends(get_current_user)):
    """水田ポリゴン削除"""
    ensure_paddy_polygons_table()

    p = require_found(PaddyPolygonRepository.get_by_id(polygon_id), "水田ポリゴン")
    field = FieldRepository.get_field(p["field_id"])
    if not field or field.get("user_id") != current_user["id"]:
        raise HTTPException(status_code=403, detail="このポリゴンを削除する権限がありません")

    PaddyPolygonRepository.delete(polygon_id)
    return {"status": "ok", "message": f"水田ポリゴン（ID: {polygon_id}）を削除しました"}


# =============================================================================
# 作付けポリゴン（Crop Polygons）エンドポイント
# =============================================================================

@router.get("/api/crop-polygons", response_model=List[CropPolygonResponse])
def list_crop_polygons(
    field_id: Optional[int] = None,
    year: Optional[int] = None,
    current_user: Dict = Depends(get_current_user),
):
    """ほ場・年度別作付けポリゴン一覧"""
    ensure_crop_polygons_table()

    if field_id is not None and year is not None:
        rows = CropPolygonRepository.get_by_field_year(field_id, year)
    elif year is not None:
        rows = CropPolygonRepository.get_all_for_user_year(current_user["id"], year)
    else:
        raise HTTPException(status_code=400, detail="yearパラメータは必須です")
    return [_crop_polygon_to_response(r) for r in rows]


@router.get("/api/crop-polygons/{polygon_id}", response_model=CropPolygonResponse)
def get_crop_polygon(polygon_id: int, current_user: Dict = Depends(get_current_user)):
    """作付けポリゴン詳細"""
    ensure_crop_polygons_table()

    p = require_found(CropPolygonRepository.get_by_id(polygon_id), "作付けポリゴン")
    field = FieldRepository.get_field(p["field_id"])
    if not field or field.get("user_id") != current_user["id"]:
        raise HTTPException(status_code=403, detail="このポリゴンにアクセスする権限がありません")
    return _crop_polygon_to_response(p)


@router.post("/api/crop-polygons", response_model=CropPolygonResponse, status_code=201)
def create_crop_polygon(req: CropPolygonCreate, current_user: Dict = Depends(get_current_user)):
    """作付けポリゴン作成（area_haはgeometryから自動計算）"""
    ensure_crop_polygons_table()

    field = require_found(FieldRepository.get_field(req.field_id), "ほ場")
    if field.get("user_id") != current_user["id"]:
        raise HTTPException(status_code=403, detail="このほ場にアクセスする権限がありません")

    geometry_str = json.dumps(req.geometry)
    try:
        polygon = geojson_to_shapely(geometry_str)
        area_ha = calculate_geodesic_area_ha(polygon)
    except (ValueError, TypeError, KeyError) as e:
        raise HTTPException(status_code=400, detail=f"ジオメトリの解析に失敗: {e}")

    polygon_id = CropPolygonRepository.create(
        field_id=req.field_id,
        year=req.year,
        crop_name=req.crop_name,
        geometry=geometry_str,
        area_ha=area_ha,
        notes=req.notes,
    )
    p = CropPolygonRepository.get_by_id(polygon_id)
    return _crop_polygon_to_response(p)


@router.put("/api/crop-polygons/{polygon_id}", response_model=CropPolygonResponse)
def update_crop_polygon(
    polygon_id: int,
    req: CropPolygonUpdate,
    current_user: Dict = Depends(get_current_user),
):
    """作付けポリゴン更新"""
    ensure_crop_polygons_table()

    p = require_found(CropPolygonRepository.get_by_id(polygon_id), "作付けポリゴン")
    field = FieldRepository.get_field(p["field_id"])
    if not field or field.get("user_id") != current_user["id"]:
        raise HTTPException(status_code=403, detail="このポリゴンを更新する権限がありません")

    kwargs = {}
    if req.year is not None:
        kwargs['year'] = req.year
    if req.crop_name is not None:
        kwargs['crop_name'] = req.crop_name
    if req.geometry is not None:
        geometry_str = json.dumps(req.geometry)
        try:
            polygon = geojson_to_shapely(geometry_str)
            kwargs['area_ha'] = calculate_geodesic_area_ha(polygon)
        except (ValueError, TypeError, KeyError) as e:
            raise HTTPException(status_code=400, detail=f"ジオメトリの解析に失敗: {e}")
        kwargs['geometry'] = geometry_str
    if req.notes is not None:
        kwargs['notes'] = req.notes

    CropPolygonRepository.update(polygon_id, **kwargs)
    updated = CropPolygonRepository.get_by_id(polygon_id)
    return _crop_polygon_to_response(updated)


@router.delete("/api/crop-polygons/{polygon_id}")
def delete_crop_polygon(polygon_id: int, current_user: Dict = Depends(get_current_user)):
    """作付けポリゴン削除"""
    ensure_crop_polygons_table()

    p = require_found(CropPolygonRepository.get_by_id(polygon_id), "作付けポリゴン")
    field = FieldRepository.get_field(p["field_id"])
    if not field or field.get("user_id") != current_user["id"]:
        raise HTTPException(status_code=403, detail="このポリゴンを削除する権限がありません")

    CropPolygonRepository.delete(polygon_id)
    return {"status": "ok", "message": f"作付けポリゴン（ID: {polygon_id}）を削除しました"}


@router.post("/api/crop-polygons/copy-year")
def copy_crop_polygons_year(req: CropPolygonCopyRequest, current_user: Dict = Depends(get_current_user)):
    """前年度の作付けポリゴンを次年度にコピー"""
    ensure_crop_polygons_table()

    if req.from_year == req.to_year:
        raise HTTPException(status_code=400, detail="コピー元とコピー先の年度が同じです")

    count = CropPolygonRepository.copy_from_previous_year(
        user_id=current_user["id"],
        from_year=req.from_year,
        to_year=req.to_year,
    )
    return {"status": "ok", "copied_count": count, "from_year": req.from_year, "to_year": req.to_year}


# =============================================================================
# 面積集計（Aggregation）エンドポイント
# =============================================================================

@router.get("/api/aggregation/cross-table")
def get_cross_table(year: int, current_user: Dict = Depends(get_current_user)):
    """クロス集計表JSON（作物×地目）"""
    ensure_paddy_polygons_table()
    ensure_crop_polygons_table()

    raw_df, display_df = get_cross_tabulation_for_user(current_user["id"], year)

    columns = display_df.columns.tolist()
    rows = []
    for _, row in raw_df.iterrows():
        rows.append({col: row[col] for col in columns})

    totals_row = rows[-1] if rows else {}
    data_rows = rows[:-1] if rows else []

    return {
        "year": year,
        "columns": columns,
        "rows": data_rows,
        "totals": totals_row,
    }


@router.get("/api/aggregation/cross-table/csv")
def get_cross_table_csv(year: int, current_user: Dict = Depends(get_current_user)):
    """クロス集計表CSV形式ダウンロード"""
    ensure_paddy_polygons_table()
    ensure_crop_polygons_table()

    csv_str = export_cross_tabulation_csv(current_user["id"], year)

    return Response(
        content=csv_str,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename=cross_table_{year}.csv"},
    )


@router.get("/api/aggregation/subsidy-summary")
def get_subsidy_summary_api(current_user: Dict = Depends(get_current_user)):
    """補助金残年数サマリ"""
    ensure_paddy_polygons_table()

    summary = get_subsidy_summary(current_user["id"])
    return {"summary": summary}


@router.get("/api/aggregation/land-category")
def get_land_category_for_crop(
    crop_polygon_id: int,
    current_user: Dict = Depends(get_current_user),
):
    """単一作付けの地目内訳（デバッグ/確認用）"""
    ensure_paddy_polygons_table()
    ensure_crop_polygons_table()

    crop_poly = require_found(CropPolygonRepository.get_by_id(crop_polygon_id), "作付けポリゴン")

    field_data = FieldRepository.get_field(crop_poly['field_id'])
    if not field_data or field_data.get('user_id') != current_user["id"]:
        raise HTTPException(status_code=403, detail="このポリゴンを参照する権限がありません")

    paddy_polygons = PaddyPolygonRepository.get_all_for_user(current_user["id"])
    breakdown = build_land_breakdown_for_crop(crop_poly, paddy_polygons)

    return {
        "crop_polygon_id": crop_polygon_id,
        "crop_name": breakdown.crop_name,
        "field_id": breakdown.field_id,
        "year": breakdown.year,
        "field_area_ha": round(breakdown.field_area_ha, 4),
        "converted_areas": {
            str(k): round(v, 4) for k, v in breakdown.converted_areas.items()
        },
        "paddy_area_ha": round(breakdown.paddy_area_ha, 4),
        "total_area_ha": round(breakdown.total_area_ha, 4),
    }
