"""
農業管理アプリ REST API

FastAPI を使用した REST API。
認証は JWT トークン、データは SQLite に保存。
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Depends, status, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import StreamingResponse, FileResponse
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta, timezone
import jwt
import sys
import os
import io
import csv

# 親ディレクトリをパスに追加（rotation_planner モジュールを使用するため）
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging

from rotation_planner.common import (
    authenticate,
    get_user_info,
    add_user,
    update_password,
    update_user_role,
    delete_user,
    load_users,
    hash_password,
    FieldRepository,
    CropHistoryRepository,
    PlanRepository,
    UserRepository,
    CropMasterRepository,
    UserCropRepository,
    UserConstraintsRepository,
    PesticideMasterRepository,
    PesticideOrderRepository,
    PesticideRecordRepository,
    PesticideUsageRepository,
    InventoryRepository,
    JAStaffRepository,
    ensure_crop_tables,
    ensure_inventory_tables,
)
from rotation_planner.common.exceptions import DuplicateKeyError
from api.error_handlers import register_exception_handlers, require_found

logger = logging.getLogger("rotation_planner.api")

# GPSマッチング機能
from rotation_planner.field.gps_matcher import (
    get_field_candidates,
    find_field_by_gps,
    SHAPELY_AVAILABLE,
    MAX_DISTANCE_METERS,
)

# KMLパーサー
from rotation_planner.field.kml_parser import parse_kml_or_kmz_bytes, generate_kml_content
import zipfile

# OR-Tools最適化
from rotation_planner.app.optimizer import RotationPlannerORTools
from rotation_planner.app.utils import Field
from rotation_planner.app.constraints import Constraints, FIXED_FORBIDDEN_TRANSITIONS

# 在庫管理API
from api.inventory_api import router as inventory_router, create_inventory_routes, ensure_inventory_tables

# 共通依存性
from api.deps import get_current_user, require_admin

# APIルーター
from api.routers.auth import router as auth_router
from api.routers.admin import router as admin_router
from api.routers.fields import router as fields_router
from api.routers.crops import router as crops_router
from api.routers.plans import router as plans_router
from api.routers.pesticides import router as pesticides_router
from api.routers.gis import router as gis_router
from api.routers.dashboard import router as dashboard_router

# =============================================================================
# アプリケーション設定
# =============================================================================

@asynccontextmanager
async def lifespan(app):
    # ロギング設定
    from api.logging_config import setup_api_logging
    setup_api_logging()
    # 起動時にDB初期化（スキーマ全体 + 初期ユーザー + 初期組織）
    from rotation_planner.common.db import init_db
    init_db()
    # 追加テーブル初期化（マイグレーション）
    ensure_crop_tables()
    ensure_inventory_tables()
    # FAMIC自動更新チェック（半年経過していれば更新）
    try:
        from rotation_planner.famic import check_and_update_if_needed
        result = check_and_update_if_needed()
        if result:
            print(f"FAMIC data auto-updated: {result.get('basic_count', 0)} records")
    except Exception as e:
        print(f"FAMIC auto-update check failed: {e}")
    yield

app = FastAPI(
    title="農業管理アプリ API",
    description="輪作計画・ほ場管理のREST API",
    version="2.0.0",
    lifespan=lifespan,
)

# グローバル例外ハンドラ登録
register_exception_handlers(app)

# CORS設定（開発環境用）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173", "http://localhost:5174"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# JWT設定
JWT_SECRET = os.environ.get("JWT_SECRET")
if not JWT_SECRET:
    raise RuntimeError("JWT_SECRET environment variable is required")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_HOURS = 24

security = HTTPBearer()


# Plans/Pesticides/GIS/Dashboard のモデルはルーター側に移動済み


# GPSマッチング


# システム情報

# =============================================================================
# ルーター登録
# =============================================================================
create_inventory_routes(get_current_user)
app.include_router(inventory_router)
app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(fields_router)
app.include_router(crops_router)
app.include_router(plans_router)
app.include_router(pesticides_router)
app.include_router(gis_router)
app.include_router(dashboard_router)


# Plans/Constraints エンドポイントは api/routers/plans.py に移動済み

# Pesticides エンドポイントは api/routers/pesticides.py に移動済み (削除開始)
# =============================================================================
# =============================================================================
# JA集計エンドポイント (JA職員/管理者用)
# =============================================================================

@app.get("/api/ja/farmers")
def list_farmers(current_user: Dict = Depends(require_admin)):
    """農家一覧取得"""
    farmers = JAStaffRepository.get_accessible_farmers(current_user["id"])
    return farmers


@app.get("/api/ja/farmers/{farmer_id}/fields")
def get_farmer_fields(farmer_id: int, current_user: Dict = Depends(require_admin)):
    """農家のほ場一覧取得"""
    fields = FieldRepository.get_fields(farmer_id)
    return [FieldResponse.from_db(f, user_id=farmer_id) for f in fields]


@app.get("/api/ja/farmers/{farmer_id}/plans")
def get_farmer_plans(farmer_id: int, current_user: Dict = Depends(require_admin)):
    """農家の輪作計画一覧取得"""
    plans = PlanRepository.get_plans(farmer_id)
    return [PlanResponse(**p) for p in plans]


@app.get("/api/ja/aggregate/pesticide-orders")
def aggregate_pesticide_orders(year: int, current_user: Dict = Depends(require_admin)):
    """農薬発注集計"""
    farmers = JAStaffRepository.get_accessible_farmers(current_user["id"])
    aggregated = {}
    for farmer in farmers:
        orders = PesticideOrderRepository.get_orders(farmer["id"], year)
        for order in orders:
            for item in order.get("items", []):
                key = (item.get("pesticide_name", ""), item.get("crop", ""))
                if key not in aggregated:
                    aggregated[key] = {"pesticide_name": key[0], "crop": key[1], "total_quantity": 0, "farmers": []}
                aggregated[key]["total_quantity"] += item.get("quantity", 0)
                aggregated[key]["farmers"].append(farmer["username"])
    return list(aggregated.values())


@app.get("/api/ja/aggregate/pesticide-orders/detail")
def aggregate_pesticide_orders_detail(
    year: int,
    group_by: str = "farmer",
    current_user: Dict = Depends(require_admin)
):
    """農薬発注詳細集計（農家別/農薬別）"""
    farmers = JAStaffRepository.get_accessible_farmers(current_user["id"])

    if group_by == "farmer":
        result = []
        for farmer in farmers:
            farmer_data = {
                "farmer_id": farmer["id"],
                "farmer_name": farmer.get("display_name") or farmer["username"],
                "pesticides": [],
            }
            orders = PesticideOrderRepository.get_orders(farmer["id"], year)
            pest_totals = {}
            for order in orders:
                for item in order.get("items", []):
                    pname = item.get("pesticide_name", "")
                    if pname not in pest_totals:
                        pest_totals[pname] = {"quantity": 0, "unit": item.get("unit", "")}
                    pest_totals[pname]["quantity"] += item.get("quantity", 0)

            for pname, pdata in sorted(pest_totals.items()):
                farmer_data["pesticides"].append({
                    "pesticide_name": pname,
                    "quantity": round(pdata["quantity"], 2),
                    "unit": pdata["unit"],
                })

            if farmer_data["pesticides"]:
                result.append(farmer_data)
        return result

    else:  # pesticide
        pest_farmers = {}
        for farmer in farmers:
            orders = PesticideOrderRepository.get_orders(farmer["id"], year)
            for order in orders:
                for item in order.get("items", []):
                    pname = item.get("pesticide_name", "")
                    if pname not in pest_farmers:
                        pest_farmers[pname] = {"total": 0, "unit": item.get("unit", ""), "farmers": []}
                    pest_farmers[pname]["total"] += item.get("quantity", 0)
                    pest_farmers[pname]["farmers"].append({
                        "name": farmer.get("display_name") or farmer["username"],
                        "quantity": item.get("quantity", 0),
                    })

        return [{"pesticide_name": k, "total_quantity": round(v["total"], 2), "unit": v["unit"], "farmers": v["farmers"]}
                for k, v in sorted(pest_farmers.items())]


# =============================================================================
# データ管理エンドポイント
# =============================================================================

@app.get("/api/export/fields/csv")
def export_fields_csv(current_user: Dict = Depends(get_current_user)):
    """ほ場データCSVエクスポート"""
    fields = FieldRepository.get_fields(current_user["id"])
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ほ場コード", "ほ場名", "地区", "面積(ha)", "てんさい禁止"])
    for f in fields:
        writer.writerow([
            f.get("field_code", ""),
            f.get("name", ""),
            f.get("district", ""),
            f.get("area_ha", ""),
            "○" if f.get("beet_forbidden") else "",
        ])
    output.seek(0)
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode("utf-8-sig")),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=fields.csv"}
    )


@app.get("/api/export/plans/{plan_id}/csv")
def export_plan_csv(plan_id: int, current_user: Dict = Depends(get_current_user)):
    """輪作計画CSVエクスポート"""
    plan = require_found(PlanRepository.get_plan(plan_id), "輪作計画")
    if plan["user_id"] != current_user["id"] and current_user["role"] not in ["admin", "ja_staff"]:
        raise HTTPException(status_code=403, detail="Access denied")

    details = plan.get("details", [])
    fields_map = {}
    years = set()
    for d in details:
        fid = d["field_id"]
        year = f"R{d['year']}"
        years.add(year)
        if fid not in fields_map:
            fields_map[fid] = {"field_code": d.get("field_code", f"F{fid}"), "crops": {}}
        fields_map[fid]["crops"][year] = d["crop"]

    sorted_years = sorted(years)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ほ場コード"] + sorted_years)
    for fid, data in fields_map.items():
        row = [data["field_code"]] + [data["crops"].get(y, "") for y in sorted_years]
        writer.writerow(row)
    output.seek(0)
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode("utf-8-sig")),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=plan_{plan_id}.csv"}
    )


@app.get("/api/export/fields/kmz")
def export_fields_kmz(current_user: Dict = Depends(get_current_user)):
    """
    ほ場データKMZエクスポート

    ほ場のポリゴン座標をKML形式にしてKMZ（ZIP圧縮）で出力する。
    """
    import json

    user_id = current_user["id"]
    fields = FieldRepository.get_fields(user_id)

    # KML用のほ場データを準備
    kml_fields = []
    for f in fields:
        coordinates = f.get("coordinates_json")
        if isinstance(coordinates, str):
            try:
                coordinates = json.loads(coordinates)
            except json.JSONDecodeError:
                continue
        if not coordinates or len(coordinates) < 3:
            continue

        kml_fields.append({
            "field_id": f.get("field_code", f"F{f['id']}"),
            "name": f.get("name") or f.get("field_code", ""),
            "coordinates": coordinates,
            "area_ha": f.get("area_ha"),
        })

    if not kml_fields:
        raise HTTPException(status_code=400, detail="エクスポート可能なほ場がありません（座標データなし）")

    # KML生成
    kml_content = generate_kml_content(kml_fields, name="ほ場一覧")

    # KMZ（ZIP圧縮）
    output = io.BytesIO()
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr('doc.kml', kml_content.encode('utf-8'))
    output.seek(0)

    # ファイル名に日付を付与
    filename = f"fields_export_{datetime.now().strftime('%Y%m%d')}.kmz"

    return StreamingResponse(
        output,
        media_type="application/vnd.google-earth.kmz",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


class ApplyToHistoryRequest(BaseModel):
    """履歴反映リクエスト"""
    confirm_overwrite: bool = False


class ApplyToHistoryResponse(BaseModel):
    """履歴反映レスポンス"""
    success: bool
    applied_count: int
    message: str


@app.post("/api/plans/{plan_id}/apply-to-history", response_model=ApplyToHistoryResponse)
def apply_plan_to_history(
    plan_id: int,
    request: ApplyToHistoryRequest,
    current_user: Dict = Depends(get_current_user)
):
    """
    輪作計画を作付履歴に反映

    計画の各ほ場×年の作物を作付履歴テーブルに一括登録する。
    既存の履歴がある場合は上書きされる。
    """
    plan = require_found(PlanRepository.get_plan(plan_id), "輪作計画")

    # 権限チェック
    if plan["user_id"] != current_user["id"] and current_user["role"] not in ["admin", "ja_staff"]:
        raise HTTPException(status_code=403, detail="この計画にアクセスする権限がありません")

    details = plan.get("details", [])
    if not details:
        raise HTTPException(status_code=400, detail="計画に詳細データがありません")

    # 履歴に反映
    applied_count = 0
    for d in details:
        field_id = d.get("field_id")
        year = d.get("year")
        crop = d.get("crop")

        if not field_id or not year or not crop:
            continue

        # 年度を令和年に変換（計画では令和年を使用）
        year_str = f"R{year}" if isinstance(year, int) else str(year)
        if not year_str.startswith("R"):
            year_str = f"R{year_str}"

        # 履歴に追加（INSERT OR REPLACE）
        CropHistoryRepository.add_history(field_id, year_str, crop, is_inferred=False)
        applied_count += 1

    return ApplyToHistoryResponse(
        success=True,
        applied_count=applied_count,
        message=f"{applied_count}件の作付履歴を登録しました"
    )


# =============================================================================
# 輪作計画CSVインポート
# =============================================================================

class RotationImportRequest(BaseModel):
    """輪作計画CSVインポートリクエスト"""
    plan_name: str
    csv_data: List[Dict[str, Any]]  # [{field_code, year, crop}, ...]


class RotationImportResponse(BaseModel):
    """輪作計画CSVインポートレスポンス"""
    success: bool
    plan_id: Optional[int] = None
    import_count: int
    error_count: int
    errors: List[str]
    warnings: List[str]


@app.post("/api/rotation/import-csv", response_model=RotationImportResponse)
def import_rotation_csv(req: RotationImportRequest, current_user: Dict = Depends(get_current_user)):
    """
    輪作計画CSVインポート

    CSVデータを受け取り、バリデーション後に計画として保存する。
    """
    user_id = current_user["id"]
    errors = []
    warnings = []

    # 計画名チェック
    if not req.plan_name.strip():
        return RotationImportResponse(
            success=False,
            import_count=0,
            error_count=1,
            errors=["計画名を入力してください"],
            warnings=[]
        )

    if not req.csv_data:
        return RotationImportResponse(
            success=False,
            import_count=0,
            error_count=1,
            errors=["インポートするデータがありません"],
            warnings=[]
        )

    # ユーザーの作物設定を取得
    user_crops = UserCropRepository.get_user_crops(user_id)
    user_crop_names = set(c.get("name", "") for c in user_crops if c.get("name"))

    # ユーザーのほ場一覧を取得
    fields = FieldRepository.get_fields(user_id)
    field_code_to_id = {f["field_code"]: f["id"] for f in fields}

    # バリデーション
    valid_rows = []
    for idx, row in enumerate(req.csv_data):
        row_num = idx + 1
        field_code = str(row.get("field_code", row.get("field_id", ""))).strip()
        year_str = str(row.get("year", "")).strip()
        crop = str(row.get("crop", row.get("crop_name", ""))).strip()

        # 必須フィールドチェック
        if not field_code:
            errors.append(f"行{row_num}: ほ場IDが空です")
            continue
        if not year_str:
            errors.append(f"行{row_num}: 年が空です")
            continue
        if not crop:
            errors.append(f"行{row_num}: 作物が空です")
            continue

        # ほ場存在チェック
        if field_code not in field_code_to_id:
            errors.append(f"行{row_num}: ほ場ID「{field_code}」が見つかりません")
            continue

        # 年のバリデーション
        try:
            year = int(year_str)
            if year < 1900 or year > 2100:
                errors.append(f"行{row_num}: 年「{year_str}」が無効です（1900-2100）")
                continue
        except ValueError:
            errors.append(f"行{row_num}: 年「{year_str}」は数値で入力してください")
            continue

        # 作物存在チェック（ユーザー作物設定がある場合のみ）
        if user_crop_names and crop not in user_crop_names:
            errors.append(f"行{row_num}: 作物「{crop}」は作物設定に登録されていません")
            continue

        valid_rows.append({
            "field_code": field_code,
            "field_id": field_code_to_id[field_code],
            "year": year,
            "crop": crop,
        })

    # エラーがあればインポート中断
    if errors:
        return RotationImportResponse(
            success=False,
            import_count=0,
            error_count=len(errors),
            errors=errors[:20],  # 最初の20件まで
            warnings=warnings
        )

    # 計画詳細を作成
    details = []
    for row in valid_rows:
        details.append({
            "field_id": row["field_id"],
            "field_code": row["field_code"],
            "year": row["year"],
            "crop": row["crop"],
        })

    # 計画を保存
    try:
        plan_id = PlanRepository.create_plan(
            user_id=user_id,
            name=req.plan_name.strip(),
            details=details
        )
    except Exception as e:
        logger.error("輪作計画の保存に失敗: %s", e, exc_info=True)
        return RotationImportResponse(
            success=False,
            import_count=0,
            error_count=1,
            errors=["計画の保存に失敗しました"],
            warnings=warnings
        )

    return RotationImportResponse(
        success=True,
        plan_id=plan_id,
        import_count=len(details),
        error_count=0,
        errors=[],
        warnings=warnings
    )


# =============================================================================
# 輪作計画最適化（OR-Tools）
# =============================================================================

class RotationOptimizeRequest(BaseModel):
    """輪作最適化リクエスト"""
    fields: List[Dict[str, Any]]  # [{field_id, field_code, district, area_ha, history, beet_forbidden}]
    crops: List[str]
    past_years: List[str]
    future_years: List[str]
    constraints: Optional[Dict[str, Any]] = None
    options: Optional[Dict[str, Any]] = None


class RotationOptimizeResponse(BaseModel):
    """輪作最適化レスポンス"""
    plan: Dict[str, str]  # {"fieldIdx,year": crop}
    score: float
    errors: List[str]
    field_table: List[Dict[str, Any]]
    summary_table: List[Dict[str, Any]]
    elapsed_ms: int


@app.post("/api/rotation/optimize", response_model=RotationOptimizeResponse)
def optimize_rotation(req: RotationOptimizeRequest, current_user: Dict = Depends(get_current_user)):
    """OR-Toolsを使用した輪作計画最適化"""
    import time
    start_time = time.time()

    try:
        # ほ場データをFieldオブジェクトに変換
        field_objects = []
        for f in req.fields:
            field_obj = Field(
                field_id=str(f.get("field_id", f.get("fieldId", ""))),
                field_code=f.get("field_code", f.get("fieldCode", "")),
                area_ha=float(f.get("area_ha", f.get("areaHa", 0))),
                district=f.get("district", ""),
                history=f.get("history", {}),
                beet_forbidden=f.get("beet_forbidden", f.get("beetForbidden", False))
            )
            field_objects.append(field_obj)

        # 制約データを構築
        c = req.constraints or {}

        crop_mins = {}
        crop_caps = {}
        min_gap_years = {}
        min_fields = {}
        max_fields = {}

        # 制約テーブルから
        for row in c.get("constraints", []):
            crop = row.get("crop")
            if not crop:
                continue
            if row.get("min_ha") and row["min_ha"] > 0:
                crop_mins[crop] = row["min_ha"]
            if row.get("cap_ha") and row["cap_ha"] > 0:
                crop_caps[crop] = row["cap_ha"]
            if row.get("min_gap_years") and row["min_gap_years"] > 0:
                min_gap_years[crop] = row["min_gap_years"]
            if row.get("min_fields") and row["min_fields"] > 0:
                min_fields[crop] = row["min_fields"]
            if row.get("max_fields") and row["max_fields"] > 0:
                max_fields[crop] = row["max_fields"]

        # 禁止遷移
        forbidden = set(FIXED_FORBIDDEN_TRANSITIONS)
        forbidden_text = c.get("forbidden_transitions", "")
        if forbidden_text:
            import re
            pairs = forbidden_text.split(",")
            for pair in pairs:
                match = re.match(r"(.+)->(.+)", pair.strip())
                if match:
                    forbidden.add((match.group(1).strip(), match.group(2).strip()))

        # 優先遷移
        preferred = {}
        preferred_text = c.get("preferred_transitions", "")
        if preferred_text:
            import re
            pairs = preferred_text.split(",")
            for pair in pairs:
                match = re.match(r"(.+)->(.+):(\d+)", pair.strip())
                if match:
                    preferred[(match.group(1).strip(), match.group(2).strip())] = int(match.group(3))

        # 主作物
        main_crops_text = c.get("main_crops", "")
        main_crops = [x.strip() for x in main_crops_text.split(",") if x.strip()]

        # オプション
        opts = req.options or {}
        timeout = opts.get("timeout", 10)
        high_precision = opts.get("high_precision", False)
        district_grouping = opts.get("district_grouping", True)
        infer_unknown = opts.get("infer_unknown", False)
        tensai_required = opts.get("tensai_required", False)
        unknown_mode = opts.get("unknown_mode", "ignore")

        # 空欄推論が有効な場合、履歴の空欄を推論で補完
        if infer_unknown:
            for f in field_objects:
                for year in req.past_years:
                    if year not in f.history or not f.history[year]:
                        # 前年の作物から推論（簡易版）
                        prev_year_num = int(year[1:]) - 1
                        prev_year = f"R{prev_year_num}"
                        if prev_year in f.history and f.history[prev_year]:
                            # 前年と異なる作物を推論（*マーク付き）
                            f.history[year] = f"{f.history[prev_year]}*"

        # てんさい必須の場合、min_fieldsに追加
        if tensai_required:
            if 'てんさい' not in min_fields or min_fields['てんさい'] < 1:
                min_fields['てんさい'] = 1

        # 隣接筆制約（PRO機能）
        adjacent_family_enabled = c.get("adjacent_family_enabled", False)
        adjacency_pairs = []
        crop_family_map = {}

        if adjacent_family_enabled:
            from rotation_planner.common import CropMasterRepository
            from rotation_planner.field.spatial import build_adjacency_graph
            crop_family_map = CropMasterRepository.get_family_map()
            adjacency_buffer = c.get("adjacency_buffer_meters", 1.0)
            # fields から座標情報を取得して隣接グラフ構築
            field_dicts_for_adj = []
            field_code_to_idx = {}
            for i, f in enumerate(req.fields):
                fc = f.get("field_code", f.get("fieldCode", ""))
                field_code_to_idx[fc] = i
                field_dicts_for_adj.append({
                    "field_code": fc,
                    "coordinates_json": f.get("coordinates_json", f.get("coordinatesJson", ""))
                })
            adj_graph = build_adjacency_graph(field_dicts_for_adj, buffer_meters=adjacency_buffer)
            seen = set()
            for code, neighbors in adj_graph.items():
                for neighbor in neighbors:
                    pair = tuple(sorted([code, neighbor]))
                    if pair not in seen:
                        seen.add(pair)
                        idx_a = field_code_to_idx.get(pair[0])
                        idx_b = field_code_to_idx.get(pair[1])
                        if idx_a is not None and idx_b is not None:
                            adjacency_pairs.append((idx_a, idx_b))

        constraints_obj = Constraints(
            crop_mins=crop_mins,
            crop_caps=crop_caps,
            min_gap_years=min_gap_years,
            min_fields=min_fields,
            max_fields=max_fields,
            forbidden_transitions=forbidden,
            preferred_transitions=preferred,
            main_crops=main_crops,
            unknown_mode=unknown_mode,
            adjacent_family_enabled=adjacent_family_enabled,
            adjacency_pairs=adjacency_pairs,
            crop_family_map=crop_family_map
        )

        # 最適化実行
        planner = RotationPlannerORTools(
            field_objects,
            req.past_years,
            req.future_years,
            req.crops,
            constraints_obj
        )
        plan, score, errors = planner.solve(
            timeout_seconds=timeout,
            high_precision=high_precision,
            district_grouping=district_grouping
        )

        # plan を文字列キーの辞書に変換
        plan_dict = {}
        for (field_idx, year), crop in plan.items():
            plan_dict[f"{field_idx},{year}"] = crop

        # 結果テーブル生成
        all_years = req.past_years + req.future_years
        field_table = []
        for i, f in enumerate(field_objects):
            row = {
                "field_code": f.field_code,
                "district": f.district or "",
                "area_ha": f.area_ha
            }
            for year in all_years:
                if year in req.past_years:
                    row[year] = f.history.get(year, "")
                else:
                    row[year] = plan.get((i, year), "")
            field_table.append(row)

        # サマリーテーブル生成
        summary_table = []
        for year in all_years:
            row = {"year": year}
            for crop in req.crops:
                total_ha = 0.0
                for i, f in enumerate(field_objects):
                    if year in req.past_years:
                        c = f.history.get(year, "")
                    else:
                        c = plan.get((i, year), "")
                    if c == crop:
                        total_ha += f.area_ha
                row[crop] = round(total_ha, 2)
            summary_table.append(row)

        elapsed_ms = int((time.time() - start_time) * 1000)

        return RotationOptimizeResponse(
            plan=plan_dict,
            score=score,
            errors=errors,
            field_table=field_table,
            summary_table=summary_table,
            elapsed_ms=elapsed_ms
        )

    except Exception as e:
        logger.error("最適化エラー: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="最適化の実行に失敗しました")

# 開発サーバー起動
# =============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
