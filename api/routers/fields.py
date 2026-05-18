"""
ほ場管理ルーター

ほ場CRUD、GPS、作付履歴、筆ポリゴン、KMLインポート
"""

from fastapi import APIRouter, HTTPException, Depends, UploadFile, File
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime
import json
import logging

from rotation_planner.common import (
    FieldRepository,
    CropHistoryRepository,
    PlanRepository,
)
from api.deps import get_current_user
from api.error_handlers import require_found

# GPSマッチング機能
from rotation_planner.field.gps_matcher import (
    get_field_candidates,
    SHAPELY_AVAILABLE,
    MAX_DISTANCE_METERS,
)

# KMLパーサー
from rotation_planner.field.kml_parser import parse_kml_or_kmz_bytes

router = APIRouter(tags=["ほ場"])
logger = logging.getLogger("rotation_planner.api")


# =============================================================================
# Pydantic モデル
# =============================================================================

class FieldCreate(BaseModel):
    field_code: str
    field_name: Optional[str] = None
    district: Optional[str] = None
    area_ha: float  # 正の値が必要（エンドポイントでバリデーション）
    beet_forbidden: bool = False
    coordinates_json: Optional[str] = None  # ポリゴン座標JSON
    # 初期作付情報（任意）
    crop_year: Optional[str] = None  # 令和形式 (例: "R7") または西暦 (例: "2025")
    crop_name: Optional[str] = None  # 作物名


class FieldUpdate(BaseModel):
    field_code: Optional[str] = None
    field_name: Optional[str] = None
    district: Optional[str] = None
    area_ha: Optional[float] = None  # 正の値が必要（エンドポイントでバリデーション）
    beet_forbidden: Optional[bool] = None


class FieldResponse(BaseModel):
    id: int
    user_id: int
    field_code: str
    field_name: Optional[str] = None
    district: Optional[str] = None
    area_ha: float
    beet_forbidden: bool = False
    coordinates_json: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    @classmethod
    def from_db(cls, data: dict, user_id: int = None) -> "FieldResponse":
        return cls(
            id=data["id"],
            user_id=data.get("user_id") or user_id or 0,
            field_code=data["field_code"],
            field_name=data.get("name") or data.get("field_name"),
            district=data.get("district"),
            area_ha=data["area_ha"],
            beet_forbidden=bool(data.get("beet_forbidden", 0)),
            coordinates_json=data.get("coordinates_json"),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
        )


class CropHistoryCreate(BaseModel):
    field_id: int
    year: int
    crop: str


class CropHistoryResponse(BaseModel):
    id: int
    field_id: int
    year: int
    crop: str


# GPSマッチング
class GpsMatchRequest(BaseModel):
    lat: float  # 緯度 -90〜90（エンドポイントでバリデーション）
    lon: float  # 経度 -180〜180（エンドポイントでバリデーション）


class FieldCandidate(BaseModel):
    id: int
    field_code: str
    field_name: Optional[str] = None
    district: Optional[str] = None
    area_ha: float
    distance_m: float
    is_inside: bool


class GpsMatchResponse(BaseModel):
    matched_field: Optional[FieldCandidate] = None
    candidates: List[FieldCandidate]
    shapely_available: bool


# KMLインポート
class KmlImportResponse(BaseModel):
    imported_fields: List[FieldResponse]
    errors: List[str]


# 筆ポリゴン
class FudePolygonItem(BaseModel):
    fude_id: str
    local_gov_code: str
    land_type: str
    area_ha: float
    coordinates: List[List[float]]
    point_count: int = 0
    issue_year: str = ""


class FudePolygonResponse(BaseModel):
    polygons: List[FudePolygonItem]
    count: int


# =============================================================================
# ヘルパー関数
# =============================================================================

def _parse_crop_year(crop_year: str) -> int:
    """作付年度を西暦年に変換（R7→2025, 2025→2025）"""
    if not crop_year:
        return None
    crop_year = crop_year.strip().upper()
    if crop_year.startswith("R"):
        # 令和形式: R7 → 2025 (2018 + 7 = 2025)
        try:
            reiwa_num = int(crop_year[1:])
            return 2018 + reiwa_num
        except ValueError:
            return None
    else:
        # 西暦形式
        try:
            return int(crop_year)
        except ValueError:
            return None


# =============================================================================
# ほ場エンドポイント
# =============================================================================

@router.get("/api/fields", response_model=List[FieldResponse])
def list_fields(current_user: Dict = Depends(get_current_user)):
    fields = FieldRepository.get_fields(current_user["id"])
    return [FieldResponse.from_db(f, user_id=current_user["id"]) for f in fields]


@router.get("/api/fields/districts")
def list_districts(current_user: Dict = Depends(get_current_user)):
    """ユーザーの登録済みほ場からユニークな地区名一覧を返す"""
    fields = FieldRepository.get_fields(current_user["id"])
    districts = sorted(set(f["district"] for f in fields if f.get("district")))
    return {"districts": districts}


@router.post("/api/fields", response_model=FieldResponse, status_code=201)
def create_field(field: FieldCreate, current_user: Dict = Depends(get_current_user)):
    from rotation_planner.common.exceptions import DuplicateKeyError
    # 面積バリデーション
    if field.area_ha <= 0:
        raise HTTPException(status_code=400, detail="面積は0より大きい値を指定してください")
    try:
        field_id = FieldRepository.create_field(
            user_id=current_user["id"],
            data={
                "field_code": field.field_code,
                "name": field.field_name,
                "district": field.district,
                "area_ha": field.area_ha,
                "beet_forbidden": field.beet_forbidden,
                "coordinates_json": field.coordinates_json,
            }
        )
        created = require_found(FieldRepository.get_field(field_id), "ほ場")

        # 初期作付情報が指定されている場合はcrop_historyに保存
        if field.crop_year and field.crop_name:
            western_year = _parse_crop_year(field.crop_year)
            if western_year:
                CropHistoryRepository.add_history(field_id, western_year, field.crop_name)

        return FieldResponse.from_db(created)
    except DuplicateKeyError:
        raise HTTPException(status_code=409, detail=f"ほ場コード '{field.field_code}' は既に使用されています")
    except HTTPException:
        raise
    except Exception as e:
        logger.error("ほ場作成エラー: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="ほ場の作成に失敗しました")


@router.get("/api/fields/{field_id}", response_model=FieldResponse)
def get_field(field_id: int, current_user: Dict = Depends(get_current_user)):
    field = require_found(FieldRepository.get_field(field_id), "ほ場")
    if field["user_id"] != current_user["id"] and current_user["role"] not in ["admin", "ja_staff"]:
        raise HTTPException(status_code=403, detail="Access denied")
    return FieldResponse.from_db(field)


@router.put("/api/fields/{field_id}", response_model=FieldResponse)
def update_field(field_id: int, field: FieldUpdate, current_user: Dict = Depends(get_current_user)):
    existing = require_found(FieldRepository.get_field(field_id), "ほ場")
    if existing["user_id"] != current_user["id"] and current_user["role"] not in ["admin", "ja_staff"]:
        raise HTTPException(status_code=403, detail="Access denied")
    # 面積バリデーション
    if field.area_ha is not None and field.area_ha <= 0:
        raise HTTPException(status_code=400, detail="面積は0より大きい値を指定してください")
    update_data = field.model_dump(exclude_unset=True)
    if "field_name" in update_data:
        update_data["name"] = update_data.pop("field_name")
    if update_data:
        FieldRepository.update_field(field_id, update_data)
    updated = FieldRepository.get_field(field_id)
    return FieldResponse.from_db(updated)


@router.delete("/api/fields/{field_id}", status_code=204)
def delete_field(field_id: int, current_user: Dict = Depends(get_current_user)):
    existing = require_found(FieldRepository.get_field(field_id), "ほ場")
    if existing["user_id"] != current_user["id"] and current_user["role"] not in ["admin", "ja_staff"]:
        raise HTTPException(status_code=403, detail="Access denied")
    FieldRepository.delete_field(field_id)


@router.post("/api/fields/import-kml", response_model=KmlImportResponse)
async def import_kml(
    file: UploadFile = File(...),
    current_user: Dict = Depends(get_current_user)
):
    """
    KML/KMZファイルからほ場をインポート

    アップロードされたKML/KMZファイルをパースし、
    含まれるポリゴンをほ場として登録する。
    """
    errors = []
    imported_fields = []

    # ファイル拡張子チェック
    filename = file.filename or ""
    ext = filename.lower().split('.')[-1] if '.' in filename else ""
    if ext not in ['kml', 'kmz']:
        raise HTTPException(
            status_code=400,
            detail="KMLまたはKMZファイルをアップロードしてください"
        )

    try:
        # ファイル読み込み
        file_bytes = await file.read()

        # KML/KMZパース
        parsed_fields = parse_kml_or_kmz_bytes(file_bytes, filename)

        if not parsed_fields:
            errors.append("KMLファイルからほ場データを抽出できませんでした")
            return KmlImportResponse(imported_fields=[], errors=errors)

        # 各ほ場を登録
        for i, pf in enumerate(parsed_fields, 1):
            try:
                # ほ場コード生成（名前がなければ連番）
                field_name = pf.get("name", "") or f"インポートほ場{i}"
                field_code = f"IMP_{current_user['id']}_{i:03d}"

                # 面積（ha）
                area_ha = pf.get("area_ha", 0.0)
                if area_ha <= 0:
                    area_ha = 0.01  # 最小値

                # 座標データをJSON文字列に
                coordinates = pf.get("coordinates", [])
                coordinates_json = json.dumps(coordinates) if coordinates else None

                # ほ場作成
                field_id = FieldRepository.create_field(
                    user_id=current_user["id"],
                    data={
                        "field_code": field_code,
                        "name": field_name,
                        "district": "",
                        "area_ha": area_ha,
                        "beet_forbidden": False,
                        "coordinates_json": coordinates_json,
                    }
                )

                # 作成したほ場を取得
                created = FieldRepository.get_field(field_id)
                if created:
                    imported_fields.append(FieldResponse.from_db(created))

            except Exception as e:
                logger.warning("KMLインポート: ほ場登録失敗 %s - %s", pf.get('name', f'#{i}'), e)
                error_msg = f"ほ場「{pf.get('name', f'#{i}')}」の登録に失敗しました"
                errors.append(error_msg)

    except Exception as e:
        logger.error("KMLファイル処理エラー: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="ファイルの処理に失敗しました")

    return KmlImportResponse(imported_fields=imported_fields, errors=errors)


@router.post("/api/fields/preview-kml")
async def preview_kml(
    file: UploadFile = File(...),
    current_user: Dict = Depends(get_current_user)
):
    """
    KML/KMZファイルをパースしてプレビュー用データを返す（DB登録しない）
    """
    filename = file.filename or ""
    ext = filename.lower().split('.')[-1] if '.' in filename else ""
    if ext not in ['kml', 'kmz']:
        raise HTTPException(
            status_code=400,
            detail="KMLまたはKMZファイルをアップロードしてください"
        )

    try:
        file_bytes = await file.read()
        parsed_fields = parse_kml_or_kmz_bytes(file_bytes, filename)

        if not parsed_fields:
            return {"fields": [], "count": 0}

        result = []
        for i, pf in enumerate(parsed_fields, 1):
            coords = pf.get("coordinates", [])
            if len(coords) < 3:
                continue
            result.append({
                "name": pf.get("name", f"ほ場{i}"),
                "coordinates": coords,
                "area_ha": pf.get("area_ha", 0.0),
                "area_m2": pf.get("area_m2", 0.0),
            })

        return {"fields": result, "count": len(result)}

    except Exception as e:
        logger.error("KMLプレビュー処理エラー: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="ファイルの処理に失敗しました")


# =============================================================================
# 筆ポリゴンエンドポイント
# =============================================================================

@router.get("/api/fude-polygon/geojson", response_model=FudePolygonResponse)
def get_fude_polygons(
    min_lat: float,
    min_lng: float,
    max_lat: float,
    max_lng: float,
    max_results: int = 200,
    current_user: Dict = Depends(get_current_user)
):
    """
    指定範囲内の筆ポリゴンを取得

    農林水産省の筆ポリゴンデータ（ローカルキャッシュ）から
    バウンディングボックス内のポリゴンを検索して返す。

    Note:
        事前にdata/fude_cacheにGeoJSONファイルを配置する必要あり
    """
    from rotation_planner.field.fude_polygon import fetch_fude_polygons_in_bbox

    # バウンディングボックス検証
    if not (-90 <= min_lat <= 90) or not (-90 <= max_lat <= 90):
        raise HTTPException(status_code=400, detail="緯度は-90〜90の範囲で指定してください")
    if not (-180 <= min_lng <= 180) or not (-180 <= max_lng <= 180):
        raise HTTPException(status_code=400, detail="経度は-180〜180の範囲で指定してください")
    if min_lat > max_lat or min_lng > max_lng:
        raise HTTPException(status_code=400, detail="最小値は最大値より小さくしてください")

    # 筆ポリゴン取得
    polygons_raw = fetch_fude_polygons_in_bbox(
        min_lat=min_lat,
        min_lng=min_lng,
        max_lat=max_lat,
        max_lng=max_lng,
        max_results=max_results
    )

    # レスポンス形式に変換
    polygons = [
        FudePolygonItem(
            fude_id=p.get("fude_id", ""),
            local_gov_code=p.get("local_gov_code", ""),
            land_type=p.get("land_type", ""),
            area_ha=p.get("area_ha", 0),
            coordinates=p.get("coordinates", []),
            point_count=p.get("point_count", 0),
            issue_year=p.get("issue_year", ""),
        )
        for p in polygons_raw
    ]

    return FudePolygonResponse(polygons=polygons, count=len(polygons))


# =============================================================================
# GPSマッチングエンドポイント
# =============================================================================

@router.post("/api/gps/match-field", response_model=GpsMatchResponse)
def match_field_by_gps(req: GpsMatchRequest, current_user: Dict = Depends(get_current_user)):
    """
    GPS座標からほ場をマッチング

    GPS座標を受け取り、ユーザーの登録済みほ場の中から
    座標が含まれるほ場、または最寄りのほ場候補を返す。
    """
    # 座標バリデーション
    if not (-90 <= req.lat <= 90):
        raise HTTPException(status_code=400, detail="緯度は-90〜90の範囲で指定してください")
    if not (-180 <= req.lon <= 180):
        raise HTTPException(status_code=400, detail="経度は-180〜180の範囲で指定してください")

    # ユーザーのほ場を取得（座標情報を含む）
    fields = FieldRepository.get_fields(current_user["id"])

    # ほ場データにcoordinates_jsonがあるか確認
    fields_with_coords = [f for f in fields if f.get("coordinates_json")]

    if not fields_with_coords:
        return GpsMatchResponse(
            matched_field=None,
            candidates=[],
            shapely_available=SHAPELY_AVAILABLE
        )

    # マッチング実行
    candidates = get_field_candidates(
        gps_lat=req.lat,
        gps_lon=req.lon,
        fields=fields_with_coords,
        max_results=5,
        max_distance=MAX_DISTANCE_METERS
    )

    # レスポンス形式に変換
    candidate_responses = []
    matched_field = None

    for c in candidates:
        candidate = FieldCandidate(
            id=c["id"],
            field_code=c["field_code"],
            field_name=c.get("name") or c.get("field_name"),
            district=c.get("district"),
            area_ha=c["area_ha"],
            distance_m=c["distance_m"],
            is_inside=c["is_inside"]
        )
        candidate_responses.append(candidate)

        # 内部にある場合はマッチしたほ場として設定
        if c["is_inside"] and matched_field is None:
            matched_field = candidate

    return GpsMatchResponse(
        matched_field=matched_field,
        candidates=candidate_responses,
        shapely_available=SHAPELY_AVAILABLE
    )


# =============================================================================
# 作付履歴エンドポイント
# =============================================================================

@router.get("/api/fields/{field_id}/history", response_model=List[CropHistoryResponse])
def list_crop_history(field_id: int, current_user: Dict = Depends(get_current_user)):
    field = require_found(FieldRepository.get_field(field_id), "ほ場")
    if field["user_id"] != current_user["id"] and current_user["role"] not in ["admin", "ja_staff"]:
        raise HTTPException(status_code=403, detail="Access denied")
    history = CropHistoryRepository.get_history(field_id)
    return [CropHistoryResponse(**h) for h in history]


@router.get("/api/fields/{field_id}/current-crop")
def get_field_current_crop(field_id: int, year: int = None, current_user: Dict = Depends(get_current_user)):
    """
    ほ場の当年作物を輪作計画から取得
    輪作計画がない場合は作付履歴から取得
    """
    field = require_found(FieldRepository.get_field(field_id), "ほ場")
    if field["user_id"] != current_user["id"] and current_user["role"] not in ["admin", "ja_staff"]:
        raise HTTPException(status_code=403, detail="Access denied")

    if year is None:
        year = datetime.now().year

    # 輪作計画から作物を取得（最新の計画を優先）
    plans = PlanRepository.get_plans(current_user["id"])
    for plan_summary in plans:
        plan = PlanRepository.get_plan(plan_summary["id"])
        if not plan or not plan.get("details"):
            continue
        # 計画の期間内かチェック
        if plan["start_year"] <= year <= plan["end_year"]:
            # 該当ほ場・年の作物を検索
            for detail in plan["details"]:
                if detail["field_id"] == field_id and detail["year"] == year:
                    return {
                        "crop": detail["crop"],
                        "source": "plan",
                        "plan_id": plan["id"],
                        "plan_name": plan["name"]
                    }

    # 輪作計画にない場合は作付履歴から取得
    history = CropHistoryRepository.get_history(field_id)
    for h in history:
        if h["year"] == year:
            return {
                "crop": h["crop"],
                "source": "history",
                "plan_id": None,
                "plan_name": None
            }

    # どちらにもない場合
    return {
        "crop": None,
        "source": None,
        "plan_id": None,
        "plan_name": None
    }


@router.post("/api/fields/{field_id}/history", response_model=CropHistoryResponse, status_code=201)
def add_crop_history(field_id: int, history: CropHistoryCreate, current_user: Dict = Depends(get_current_user)):
    field = require_found(FieldRepository.get_field(field_id), "ほ場")
    if field["user_id"] != current_user["id"] and current_user["role"] not in ["admin", "ja_staff"]:
        raise HTTPException(status_code=403, detail="Access denied")
    history_id = CropHistoryRepository.add_history(field_id, history.year, history.crop)
    # cmd_586 subtask_1259: 暗黙pin (crop_history POST と同時に pinned_assignments 自動書込)
    # Q2=a 過去年 (year < 現在年度) は skip・crop_history のみ
    _y = str(history.year).strip()
    try:
        _yn = 2018 + int(_y[1:]) if _y.upper().startswith("R") else int(_y)
    except (ValueError, IndexError):
        _yn = None
    if _yn is not None and _yn >= datetime.now().year:
        try:
            from rotation_planner.common.db import get_db
            with get_db() as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO pinned_assignments "
                    "(user_id, field_id, year, crop, pinned_by, pinned_reason, is_active, updated_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, 1, CURRENT_TIMESTAMP)",
                    (field["user_id"], field_id, history.year, history.crop,
                     current_user["id"], "implicit pin via crop_history POST")
                )
                conn.commit()
        except Exception as _e:
            logger.warning(f"暗黙pin書込失敗(crop_historyは成功): {_e}")
    return CropHistoryResponse(id=history_id, field_id=field_id, year=history.year, crop=history.crop)


@router.delete("/api/history/{history_id}", status_code=204)
def delete_crop_history(history_id: int, current_user: Dict = Depends(get_current_user)):
    history = require_found(CropHistoryRepository.get_history_by_id(history_id), "作付履歴")
    field = require_found(FieldRepository.get_field(history["field_id"]), "ほ場")
    if field["user_id"] != current_user["id"] and current_user["role"] not in ["admin", "ja_staff"]:
        raise HTTPException(status_code=403, detail="Access denied")
    CropHistoryRepository.delete_history_by_id(history_id)
