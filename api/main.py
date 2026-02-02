"""
農業管理アプリ REST API

FastAPI を使用した REST API。
認証は JWT トークン、データは SQLite に保存。
"""

from fastapi import FastAPI, HTTPException, Depends, status, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import StreamingResponse, FileResponse
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import jwt
import sys
import os
import io
import csv

# 親ディレクトリをパスに追加（rotation_planner モジュールを使用するため）
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

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
    InventoryRepository,
    JAStaffRepository,
    ensure_crop_tables,
    ensure_inventory_tables,
)

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
from inventory_api import router as inventory_router, create_inventory_routes, ensure_inventory_tables

# =============================================================================
# アプリケーション設定
# =============================================================================

app = FastAPI(
    title="農業管理アプリ API",
    description="輪作計画・ほ場管理のREST API",
    version="2.0.0"
)

# CORS設定（開発環境用）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173", "http://localhost:5174"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 起動時にテーブル初期化
@app.on_event("startup")
def startup_event():
    ensure_crop_tables()
    ensure_inventory_tables()

# JWT設定
JWT_SECRET = os.environ.get("JWT_SECRET")
if not JWT_SECRET:
    raise RuntimeError("JWT_SECRET environment variable is required")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_HOURS = 24

security = HTTPBearer()


# =============================================================================
# Pydantic モデル
# =============================================================================

class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: Dict[str, Any]


class UserResponse(BaseModel):
    id: int
    username: str
    role: str
    display_name: Optional[str] = None


class UserCreate(BaseModel):
    username: str
    password: str
    role: str = "farmer"
    display_name: Optional[str] = None


class UserUpdate(BaseModel):
    display_name: Optional[str] = None
    role: Optional[str] = None
    password: Optional[str] = None


class FieldCreate(BaseModel):
    field_code: str
    field_name: Optional[str] = None
    district: Optional[str] = None
    area_ha: float  # 正の値が必要（エンドポイントでバリデーション）
    beet_forbidden: bool = False
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


class PlanCreate(BaseModel):
    name: str
    start_year: int
    end_year: int
    details: List[Dict[str, Any]]


class PlanResponse(BaseModel):
    id: int
    user_id: int
    name: str
    start_year: int
    end_year: int
    created_at: Optional[str]
    updated_at: Optional[str]
    details: Optional[List[Dict[str, Any]]] = None


class PlanUpdate(BaseModel):
    """輪作計画の更新リクエスト（部分更新対応）"""
    name: Optional[str] = None
    start_year: Optional[int] = None
    end_year: Optional[int] = None
    details: Optional[List[Dict[str, Any]]] = None


class ConstraintsUpdate(BaseModel):
    constraints: List[Dict[str, Any]]
    forbidden_transitions: Optional[str] = ""
    preferred_transitions: Optional[str] = ""
    main_crops: Optional[str] = ""


class ConstraintsResponse(BaseModel):
    constraints: List[Dict[str, Any]]
    forbidden_transitions: str
    preferred_transitions: str
    main_crops: str


class CropResponse(BaseModel):
    id: int
    name: str
    category: Optional[str] = None
    is_active: bool = True


class UserCropUpdate(BaseModel):
    crop_ids: List[int]


class UserCropCustomName(BaseModel):
    crop_id: int
    custom_name: str


class UserCropAddCustom(BaseModel):
    parent_crop_id: int
    custom_name: str


# 農薬マスタ
class PesticideMasterCreate(BaseModel):
    name: str
    crop: str
    target_pest: Optional[str] = None
    dilution_rate: Optional[str] = None
    application_method: Optional[str] = None
    unit: Optional[str] = None
    unit_price: Optional[float] = None
    notes: Optional[str] = None


class PesticideMasterResponse(BaseModel):
    id: int
    name: str
    crop: str
    target_pest: Optional[str] = None
    dilution_rate: Optional[str] = None
    application_method: Optional[str] = None
    unit: Optional[str] = None
    unit_price: Optional[float] = None
    notes: Optional[str] = None


# 農薬発注
class PesticideOrderCreate(BaseModel):
    plan_id: Optional[int] = None
    year: int
    items: List[Dict[str, Any]]  # [{pesticide_id, crop, area_ha, quantity, ...}]


class PesticideOrderResponse(BaseModel):
    id: int
    user_id: int
    plan_id: Optional[int]
    year: int
    items: List[Dict[str, Any]]
    created_at: Optional[str]


class PesticideOrderUpdate(BaseModel):
    """農薬発注の更新リクエスト（部分更新対応）"""
    year: Optional[int] = None
    items: Optional[List[Dict[str, Any]]] = None
    notes: Optional[str] = None


# 防除記録
class PesticideRecordCreate(BaseModel):
    field_id: int
    date: str
    pesticide_name: str
    crop: str
    target_pest: Optional[str] = None
    dilution_rate: Optional[str] = None
    area_ha: Optional[float] = None
    quantity: Optional[float] = None
    unit: Optional[str] = None
    weather: Optional[str] = None
    temperature: Optional[float] = None
    operator: Optional[str] = None
    notes: Optional[str] = None


class PesticideRecordResponse(BaseModel):
    id: int
    user_id: int
    field_id: int
    field_code: Optional[str] = None
    date: str
    pesticide_name: str
    crop: str
    target_pest: Optional[str] = None
    dilution_rate: Optional[str] = None
    area_ha: Optional[float] = None
    quantity: Optional[float] = None
    unit: Optional[str] = None
    weather: Optional[str] = None
    temperature: Optional[float] = None
    operator: Optional[str] = None
    notes: Optional[str] = None
    created_at: Optional[str] = None


class PesticideRecordCreateResponse(BaseModel):
    """防除記録作成レスポンス（在庫警告付き）"""
    record: PesticideRecordResponse
    inventory_warning: bool = False
    inventory_message: Optional[str] = None
    inventory_remaining: Optional[float] = None


class InventoryInfoResponse(BaseModel):
    """在庫情報レスポンス"""
    pesticide_name: str
    amount: Optional[float] = None
    unit: Optional[str] = None
    exists: bool = False
    last_used_date: Optional[str] = None
    usage_count: Optional[int] = None


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


# システム情報
class TableInfo(BaseModel):
    name: str
    count: int


class SystemInfoResponse(BaseModel):
    app_version: str
    db_size_kb: float
    db_last_modified: Optional[str] = None
    tables: List[TableInfo]
    user_count: int
    environment: Dict[str, str]
    last_backup: Optional[str] = None


# =============================================================================
# 認証ヘルパー
# =============================================================================

def create_token(user_id: int, username: str, role: str) -> str:
    payload = {
        "sub": str(user_id),
        "username": username,
        "role": role,
        "exp": datetime.utcnow() + timedelta(hours=JWT_EXPIRE_HOURS)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Dict[str, Any]:
    token = credentials.credentials
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user_id = int(payload.get("sub"))
        username = payload.get("username")
        role = payload.get("role")
        if not user_id or not username:
            raise HTTPException(status_code=401, detail="Invalid token")
        return {"id": user_id, "username": username, "role": role}
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


def require_admin(current_user: Dict = Depends(get_current_user)) -> Dict:
    if current_user["role"] not in ["admin", "ja_staff"]:
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user


# =============================================================================
# 在庫管理ルーター登録
# =============================================================================
create_inventory_routes(get_current_user)
app.include_router(inventory_router)


# =============================================================================
# 認証エンドポイント
# =============================================================================

@app.post("/api/auth/login", response_model=TokenResponse)
def login(req: LoginRequest):
    if not authenticate(req.username, req.password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    user = get_user_info(req.username)
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    token = create_token(user["id"], user["username"], user["role"])
    return TokenResponse(
        access_token=token,
        user={
            "id": user["id"],
            "username": user["username"],
            "role": user["role"],
            "display_name": user.get("display_name")
        }
    )


@app.get("/api/auth/me", response_model=UserResponse)
def get_me(current_user: Dict = Depends(get_current_user)):
    user = get_user_info(current_user["username"])
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return UserResponse(
        id=user["id"],
        username=user["username"],
        role=user["role"],
        display_name=user.get("display_name")
    )


# =============================================================================
# ユーザー管理エンドポイント (管理者用)
# =============================================================================

@app.get("/api/admin/users", response_model=List[UserResponse])
def list_users(current_user: Dict = Depends(require_admin)):
    users_data = load_users()
    return [
        UserResponse(
            id=i + 1,
            username=u["username"],
            role=u["role"],
            display_name=u.get("display_name")
        )
        for i, u in enumerate(users_data.get("users", []))
    ]


@app.post("/api/admin/users", response_model=UserResponse, status_code=201)
def create_user(user: UserCreate, current_user: Dict = Depends(require_admin)):
    try:
        add_user(user.username, user.password, user.role, user.display_name)
        new_user = get_user_info(user.username)
        return UserResponse(
            id=new_user["id"],
            username=new_user["username"],
            role=new_user["role"],
            display_name=new_user.get("display_name")
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.put("/api/admin/users/{username}", response_model=UserResponse)
def update_user(username: str, user: UserUpdate, current_user: Dict = Depends(require_admin)):
    if user.password:
        update_password(username, user.password)
    if user.role:
        update_user_role(username, user.role)
    updated = get_user_info(username)
    if not updated:
        raise HTTPException(status_code=404, detail="User not found")
    return UserResponse(
        id=updated["id"],
        username=updated["username"],
        role=updated["role"],
        display_name=updated.get("display_name")
    )


@app.delete("/api/admin/users/{username}", status_code=204)
def remove_user(username: str, current_user: Dict = Depends(require_admin)):
    if username == current_user["username"]:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")
    try:
        delete_user(username)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/admin/backup")
def download_backup(current_user: Dict = Depends(require_admin)):
    """
    DBバックアップをダウンロード（管理者のみ）

    Returns:
        rotation_planner.db のダウンロード
    """
    # DBファイルのパスを取得
    db_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "data",
        "rotation_planner.db"
    )

    if not os.path.exists(db_path):
        raise HTTPException(status_code=404, detail="Database file not found")

    # ファイル名に日付を付与
    date_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"rotation_planner_backup_{date_str}.db"

    return FileResponse(
        path=db_path,
        filename=filename,
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        }
    )


@app.get("/api/admin/system-info", response_model=SystemInfoResponse)
def get_system_info(current_user: Dict = Depends(require_admin)):
    """
    システム情報を取得（管理者のみ）

    Returns:
        アプリバージョン、DB情報、環境情報など
    """
    import sqlite3
    import fastapi
    from glob import glob

    # DBファイルのパス
    db_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "data",
        "rotation_planner.db"
    )

    # DBサイズと更新日時
    db_size_kb = 0.0
    db_last_modified = None
    if os.path.exists(db_path):
        stat = os.stat(db_path)
        db_size_kb = stat.st_size / 1024
        db_last_modified = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")

    # テーブル別レコード数
    tables = []
    if os.path.exists(db_path):
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
            table_names = cursor.fetchall()
            for (table_name,) in table_names:
                if table_name.startswith('sqlite_'):
                    continue
                cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                count = cursor.fetchone()[0]
                tables.append(TableInfo(name=table_name, count=count))
            conn.close()
        except sqlite3.Error:
            pass

    # ユーザー数
    user_count = len(load_users())

    # 環境情報
    environment = {
        "Python": sys.version.split()[0],
        "FastAPI": fastapi.__version__,
    }

    # 最終バックアップ日時（backupディレクトリがあれば）
    backup_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "data",
        "backups"
    )
    last_backup = None
    if os.path.exists(backup_dir):
        backup_files = glob(os.path.join(backup_dir, "*.db"))
        if backup_files:
            latest = max(backup_files, key=os.path.getmtime)
            last_backup = datetime.fromtimestamp(os.path.getmtime(latest)).strftime("%Y-%m-%d %H:%M:%S")

    return SystemInfoResponse(
        app_version=app.version,
        db_size_kb=round(db_size_kb, 1),
        db_last_modified=db_last_modified,
        tables=tables,
        user_count=user_count,
        environment=environment,
        last_backup=last_backup
    )


# =============================================================================
# デバッグモード設定
# =============================================================================

SETTINGS_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data",
    "settings.json"
)


def load_app_settings() -> Dict[str, Any]:
    """アプリ設定を読み込む"""
    import json as json_module
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                return json_module.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return {"debug_mode": False}


def save_app_settings(settings: Dict[str, Any]) -> None:
    """アプリ設定を保存"""
    import json as json_module
    os.makedirs(os.path.dirname(SETTINGS_FILE), exist_ok=True)
    with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
        json_module.dump(settings, f, ensure_ascii=False, indent=2)


class DebugModeRequest(BaseModel):
    enabled: bool


class DebugModeResponse(BaseModel):
    debug_mode: bool
    message: str


@app.get("/api/admin/settings/debug", response_model=DebugModeResponse)
def get_debug_mode(current_user: Dict = Depends(require_admin)):
    """デバッグモードの状態を取得"""
    settings = load_app_settings()
    return DebugModeResponse(
        debug_mode=settings.get("debug_mode", False),
        message=""
    )


@app.put("/api/admin/settings/debug", response_model=DebugModeResponse)
def set_debug_mode(req: DebugModeRequest, current_user: Dict = Depends(require_admin)):
    """デバッグモードを設定"""
    settings = load_app_settings()
    settings["debug_mode"] = req.enabled
    save_app_settings(settings)
    status = "ON" if req.enabled else "OFF"
    return DebugModeResponse(
        debug_mode=req.enabled,
        message=f"デバッグモードを {status} に変更しました"
    )


# =============================================================================
# 筆ポリゴン管理
# =============================================================================

FUDE_CACHE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data",
    "fude_cache"
)


class FudePolygonInfo(BaseModel):
    id: str
    filename: str
    size_kb: float
    feature_count: int
    updated_at: str


class FudePolygonListResponse(BaseModel):
    files: List[FudePolygonInfo]


class FudePolygonUploadResponse(BaseModel):
    success: bool
    filename: str
    feature_count: int
    message: str


@app.get("/api/admin/fude-polygon", response_model=FudePolygonListResponse)
def list_fude_polygons(current_user: Dict = Depends(require_admin)):
    """筆ポリゴンファイル一覧を取得"""
    import json as json_module
    files = []
    if os.path.exists(FUDE_CACHE_DIR):
        for file_path in sorted(glob(os.path.join(FUDE_CACHE_DIR, "*.geojson"))):
            try:
                stat = os.stat(file_path)
                size_kb = stat.st_size / 1024
                mtime = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M")
                feature_count = 0
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data = json_module.load(f)
                        if data.get("type") == "FeatureCollection":
                            feature_count = len(data.get("features", []))
                except (json.JSONDecodeError, OSError):
                    pass
                files.append(FudePolygonInfo(
                    id=os.path.basename(file_path),
                    filename=os.path.basename(file_path),
                    size_kb=round(size_kb, 1),
                    feature_count=feature_count,
                    updated_at=mtime
                ))
            except OSError:
                continue
        for file_path in sorted(glob(os.path.join(FUDE_CACHE_DIR, "*.json"))):
            if file_path.endswith(".geojson"):
                continue
            try:
                stat = os.stat(file_path)
                size_kb = stat.st_size / 1024
                mtime = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M")
                feature_count = 0
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data = json_module.load(f)
                        if data.get("type") == "FeatureCollection":
                            feature_count = len(data.get("features", []))
                except (json.JSONDecodeError, OSError):
                    pass
                files.append(FudePolygonInfo(
                    id=os.path.basename(file_path),
                    filename=os.path.basename(file_path),
                    size_kb=round(size_kb, 1),
                    feature_count=feature_count,
                    updated_at=mtime
                ))
            except OSError:
                continue
    return FudePolygonListResponse(files=files)


@app.post("/api/admin/fude-polygon", response_model=FudePolygonUploadResponse)
async def upload_fude_polygon(file: UploadFile = File(...), current_user: Dict = Depends(require_admin)):
    """筆ポリゴンGeoJSONをアップロード"""
    import json as json_module
    os.makedirs(FUDE_CACHE_DIR, exist_ok=True)
    content = await file.read()
    try:
        data = json_module.loads(content.decode('utf-8'))
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        raise HTTPException(status_code=400, detail=f"無効なJSONファイル: {str(e)}")
    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail="無効なJSON形式")
    if data.get("type") not in ["FeatureCollection", "Feature", "GeometryCollection"]:
        if "features" not in data and "geometry" not in data:
            raise HTTPException(status_code=400, detail="GeoJSON形式ではありません")
    feature_count = 0
    if data.get("type") == "FeatureCollection":
        feature_count = len(data.get("features", []))
    elif data.get("type") == "Feature":
        feature_count = 1
    filename = file.filename
    if not filename.endswith(('.geojson', '.json')):
        filename += '.geojson'
    dest_path = os.path.join(FUDE_CACHE_DIR, filename)
    with open(dest_path, 'w', encoding='utf-8') as f:
        json_module.dump(data, f, ensure_ascii=False)
    return FudePolygonUploadResponse(
        success=True, filename=filename, feature_count=feature_count,
        message=f"アップロード完了（{feature_count}筆）"
    )


@app.delete("/api/admin/fude-polygon/{filename}", status_code=204)
def delete_fude_polygon(filename: str, current_user: Dict = Depends(require_admin)):
    """筆ポリゴンファイルを削除"""
    if '..' in filename or '/' in filename or '\\' in filename:
        raise HTTPException(status_code=400, detail="無効なファイル名")
    file_path = os.path.join(FUDE_CACHE_DIR, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="ファイルが見つかりません")
    os.remove(file_path)


# =============================================================================
# FAMIC連携
# =============================================================================

class FamicStatusResponse(BaseModel):
    registry_count: int
    usage_count: int
    last_update: Optional[str]
    auto_update_enabled: bool
    next_update: Optional[str]


class FamicUpdateResponse(BaseModel):
    success: bool
    basic_count: int
    usage_count: int
    message: str


@app.get("/api/admin/famic/status", response_model=FamicStatusResponse)
def get_famic_status(current_user: Dict = Depends(require_admin)):
    """FAMICデータの状態を取得"""
    try:
        from rotation_planner.famic import get_import_stats, get_famic_settings
        stats = get_import_stats()
        settings = get_famic_settings()
        return FamicStatusResponse(
            registry_count=stats.get("registry_count", 0),
            usage_count=stats.get("usage_count", 0),
            last_update=stats.get("last_basic_import"),
            auto_update_enabled=settings.get("auto_update_enabled", False),
            next_update=settings.get("next_update")
        )
    except ImportError:
        return FamicStatusResponse(
            registry_count=0, usage_count=0, last_update=None,
            auto_update_enabled=False, next_update=None
        )


@app.post("/api/admin/famic/update", response_model=FamicUpdateResponse)
def update_famic_data(current_user: Dict = Depends(require_admin)):
    """FAMICデータを手動更新"""
    try:
        from rotation_planner.famic import download_and_import_all
        result = download_and_import_all()
        if result.get("success"):
            return FamicUpdateResponse(
                success=True, basic_count=result.get("basic_count", 0),
                usage_count=result.get("usage_count", 0), message="更新完了"
            )
        else:
            return FamicUpdateResponse(
                success=False, basic_count=0, usage_count=0,
                message=f"更新失敗: {result.get('error', '不明なエラー')}"
            )
    except ImportError:
        return FamicUpdateResponse(
            success=False, basic_count=0, usage_count=0,
            message="FAMICモジュールが利用できません"
        )


@app.put("/api/admin/famic/auto-update")
def set_famic_auto_update(enabled: bool, current_user: Dict = Depends(require_admin)):
    """FAMIC自動更新設定を変更"""
    try:
        from rotation_planner.famic import set_famic_settings
        set_famic_settings(auto_update_enabled=enabled)
        status = "有効" if enabled else "無効"
        return {"success": True, "message": f"自動更新を「{status}」に変更しました"}
    except ImportError:
        raise HTTPException(status_code=500, detail="FAMICモジュールが利用できません")


# =============================================================================
# ほ場エンドポイント
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


@app.get("/api/fields", response_model=List[FieldResponse])
def list_fields(current_user: Dict = Depends(get_current_user)):
    fields = FieldRepository.get_fields(current_user["id"])
    return [FieldResponse.from_db(f, user_id=current_user["id"]) for f in fields]


@app.post("/api/fields", response_model=FieldResponse, status_code=201)
def create_field(field: FieldCreate, current_user: Dict = Depends(get_current_user)):
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
                "beet_forbidden": field.beet_forbidden
            }
        )
        created = FieldRepository.get_field(field_id)
        if not created:
            raise HTTPException(status_code=500, detail="Failed to create field")

        # 初期作付情報が指定されている場合はcrop_historyに保存
        if field.crop_year and field.crop_name:
            western_year = _parse_crop_year(field.crop_year)
            if western_year:
                CropHistoryRepository.add_history(field_id, western_year, field.crop_name)

        return FieldResponse.from_db(created)
    except Exception as e:
        if "UNIQUE constraint" in str(e):
            raise HTTPException(status_code=400, detail=f"ほ場コード '{field.field_code}' は既に使用されています")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/fields/{field_id}", response_model=FieldResponse)
def get_field(field_id: int, current_user: Dict = Depends(get_current_user)):
    field = FieldRepository.get_field(field_id)
    if not field:
        raise HTTPException(status_code=404, detail="Field not found")
    if field["user_id"] != current_user["id"] and current_user["role"] not in ["admin", "ja_staff"]:
        raise HTTPException(status_code=403, detail="Access denied")
    return FieldResponse.from_db(field)


@app.put("/api/fields/{field_id}", response_model=FieldResponse)
def update_field(field_id: int, field: FieldUpdate, current_user: Dict = Depends(get_current_user)):
    existing = FieldRepository.get_field(field_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Field not found")
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


@app.delete("/api/fields/{field_id}", status_code=204)
def delete_field(field_id: int, current_user: Dict = Depends(get_current_user)):
    existing = FieldRepository.get_field(field_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Field not found")
    if existing["user_id"] != current_user["id"] and current_user["role"] not in ["admin", "ja_staff"]:
        raise HTTPException(status_code=403, detail="Access denied")
    FieldRepository.delete_field(field_id)


@app.post("/api/fields/import-kml", response_model=KmlImportResponse)
async def import_kml(
    file: UploadFile = File(...),
    current_user: Dict = Depends(get_current_user)
):
    """
    KML/KMZファイルからほ場をインポート

    アップロードされたKML/KMZファイルをパースし、
    含まれるポリゴンをほ場として登録する。
    """
    import json

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
                error_msg = f"ほ場「{pf.get('name', f'#{i}')}」の登録に失敗: {str(e)}"
                errors.append(error_msg)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"ファイル処理エラー: {str(e)}")

    return KmlImportResponse(imported_fields=imported_fields, errors=errors)


# =============================================================================
# 筆ポリゴンエンドポイント
# =============================================================================

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


@app.get("/api/fude-polygon/geojson", response_model=FudePolygonResponse)
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

@app.post("/api/gps/match-field", response_model=GpsMatchResponse)
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

@app.get("/api/fields/{field_id}/history", response_model=List[CropHistoryResponse])
def list_crop_history(field_id: int, current_user: Dict = Depends(get_current_user)):
    field = FieldRepository.get_field(field_id)
    if not field:
        raise HTTPException(status_code=404, detail="Field not found")
    if field["user_id"] != current_user["id"] and current_user["role"] not in ["admin", "ja_staff"]:
        raise HTTPException(status_code=403, detail="Access denied")
    history = CropHistoryRepository.get_history(field_id)
    return [CropHistoryResponse(**h) for h in history]


@app.get("/api/fields/{field_id}/current-crop")
def get_field_current_crop(field_id: int, year: int = None, current_user: Dict = Depends(get_current_user)):
    """
    ほ場の当年作物を輪作計画から取得
    輪作計画がない場合は作付履歴から取得
    """
    field = FieldRepository.get_field(field_id)
    if not field:
        raise HTTPException(status_code=404, detail="Field not found")
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


@app.post("/api/fields/{field_id}/history", response_model=CropHistoryResponse, status_code=201)
def add_crop_history(field_id: int, history: CropHistoryCreate, current_user: Dict = Depends(get_current_user)):
    field = FieldRepository.get_field(field_id)
    if not field:
        raise HTTPException(status_code=404, detail="Field not found")
    if field["user_id"] != current_user["id"] and current_user["role"] not in ["admin", "ja_staff"]:
        raise HTTPException(status_code=403, detail="Access denied")
    history_id = CropHistoryRepository.add_history(field_id, history.year, history.crop)
    return CropHistoryResponse(id=history_id, field_id=field_id, year=history.year, crop=history.crop)


@app.delete("/api/history/{history_id}", status_code=204)
def delete_crop_history(history_id: int, current_user: Dict = Depends(get_current_user)):
    history = CropHistoryRepository.get_history_by_id(history_id)
    if not history:
        raise HTTPException(status_code=404, detail="History not found")
    field = FieldRepository.get_field(history["field_id"])
    if not field:
        raise HTTPException(status_code=404, detail="Field not found")
    if field["user_id"] != current_user["id"] and current_user["role"] not in ["admin", "ja_staff"]:
        raise HTTPException(status_code=403, detail="Access denied")
    CropHistoryRepository.delete_history_by_id(history_id)


# =============================================================================
# 輪作計画エンドポイント
# =============================================================================

@app.get("/api/plans", response_model=List[PlanResponse])
def list_plans(current_user: Dict = Depends(get_current_user)):
    plans = PlanRepository.get_plans(current_user["id"])
    return [PlanResponse(**p) for p in plans]


@app.post("/api/plans", response_model=PlanResponse, status_code=201)
def create_plan(plan: PlanCreate, current_user: Dict = Depends(get_current_user)):
    plan_id = PlanRepository.create_plan(
        user_id=current_user["id"],
        plan_data={
            "name": plan.name,
            "start_year": plan.start_year,
            "end_year": plan.end_year,
            "details": plan.details
        }
    )
    created = PlanRepository.get_plan(plan_id)
    if not created:
        raise HTTPException(status_code=500, detail="Failed to create plan")
    return PlanResponse(**created)


@app.get("/api/plans/{plan_id}", response_model=PlanResponse)
def get_plan(plan_id: int, current_user: Dict = Depends(get_current_user)):
    plan = PlanRepository.get_plan(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    if plan["user_id"] != current_user["id"] and current_user["role"] not in ["admin", "ja_staff"]:
        raise HTTPException(status_code=403, detail="Access denied")
    return PlanResponse(**plan)


@app.put("/api/plans/{plan_id}", response_model=PlanResponse)
def update_plan(plan_id: int, plan_update: PlanUpdate, current_user: Dict = Depends(get_current_user)):
    """輪作計画を更新（部分更新対応）"""
    plan = PlanRepository.get_plan(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    if plan["user_id"] != current_user["id"] and current_user["role"] not in ["admin", "ja_staff"]:
        raise HTTPException(status_code=403, detail="Access denied")

    # 更新データを構築（Noneでないフィールドのみ）
    update_data = {}
    if plan_update.name is not None:
        update_data["name"] = plan_update.name
    if plan_update.start_year is not None:
        update_data["start_year"] = plan_update.start_year
    if plan_update.end_year is not None:
        update_data["end_year"] = plan_update.end_year
    if plan_update.details is not None:
        update_data["details"] = plan_update.details

    if update_data:
        PlanRepository.update_plan(plan_id, update_data)

    updated = PlanRepository.get_plan(plan_id)
    return PlanResponse(**updated)


@app.delete("/api/plans/{plan_id}", status_code=204)
def delete_plan(plan_id: int, current_user: Dict = Depends(get_current_user)):
    plan = PlanRepository.get_plan(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    if plan["user_id"] != current_user["id"] and current_user["role"] not in ["admin", "ja_staff"]:
        raise HTTPException(status_code=403, detail="Access denied")
    PlanRepository.delete_plan(plan_id)


# =============================================================================
# 制約設定エンドポイント
# =============================================================================

@app.get("/api/constraints", response_model=ConstraintsResponse)
def get_constraints(current_user: Dict = Depends(get_current_user)):
    data = UserConstraintsRepository.get_constraints(current_user["id"])
    if not data:
        return ConstraintsResponse(
            constraints=[],
            forbidden_transitions="",
            preferred_transitions="",
            main_crops=""
        )
    return ConstraintsResponse(
        constraints=data.get("constraints", []),
        forbidden_transitions=data.get("forbidden_transitions", ""),
        preferred_transitions=data.get("preferred_transitions", ""),
        main_crops=data.get("main_crops", "")
    )


@app.put("/api/constraints", response_model=ConstraintsResponse)
def update_constraints(req: ConstraintsUpdate, current_user: Dict = Depends(get_current_user)):
    UserConstraintsRepository.save_constraints(
        user_id=current_user["id"],
        constraints=req.constraints,
        forbidden_transitions=req.forbidden_transitions or "",
        preferred_transitions=req.preferred_transitions or "",
        main_crops=req.main_crops or ""
    )
    return ConstraintsResponse(
        constraints=req.constraints,
        forbidden_transitions=req.forbidden_transitions or "",
        preferred_transitions=req.preferred_transitions or "",
        main_crops=req.main_crops or ""
    )


# =============================================================================
# 作物マスタエンドポイント
# =============================================================================

@app.get("/api/crops", response_model=List[CropResponse])
def list_crops(current_user: Dict = Depends(get_current_user)):
    crops = CropMasterRepository.get_all(active_only=True)
    result = []
    for c in crops:
        result.append(CropResponse(
            id=c.get("id", 0),
            name=c.get("name", ""),
            category=c.get("category"),
            is_active=c.get("is_active", True)
        ))
    return result


@app.get("/api/user-crops", response_model=List[Dict[str, Any]])
def list_user_crops(current_user: Dict = Depends(get_current_user)):
    crops = UserCropRepository.get_user_crops(current_user["id"])
    return crops


@app.put("/api/user-crops")
def update_user_crops(req: UserCropUpdate, current_user: Dict = Depends(get_current_user)):
    UserCropRepository.set_user_crops(current_user["id"], req.crop_ids)
    return {"status": "ok"}


@app.put("/api/user-crops/custom-name")
def set_crop_custom_name(req: UserCropCustomName, current_user: Dict = Depends(get_current_user)):
    UserCropRepository.set_custom_name(current_user["id"], req.crop_id, req.custom_name)
    return {"status": "ok"}


@app.post("/api/user-crops/custom", status_code=201)
def add_custom_crop(req: UserCropAddCustom, current_user: Dict = Depends(get_current_user)):
    """
    カスタム作物を追加

    親作物（防除連携用）を指定して、カスタム名の作物を追加する。
    例: 親作物=ブロッコリー、カスタム名=ブロッコリー（2作目）
    """
    if not req.custom_name or not req.custom_name.strip():
        raise HTTPException(status_code=400, detail="カスタム名を入力してください")

    # 親作物の存在確認
    parent_crop = CropMasterRepository.get_by_id(req.parent_crop_id)
    if not parent_crop:
        raise HTTPException(status_code=400, detail="親作物が見つかりません")

    try:
        user_crop_id = UserCropRepository.add_user_crop(
            current_user["id"],
            req.parent_crop_id,
            req.custom_name.strip()
        )
        return {"status": "ok", "id": user_crop_id}
    except Exception as e:
        if "UNIQUE constraint" in str(e):
            raise HTTPException(status_code=400, detail="この作物は既に登録されています")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/user-crops/{user_crop_id}", status_code=204)
def delete_custom_crop(user_crop_id: int, current_user: Dict = Depends(get_current_user)):
    """
    カスタム作物を削除

    user_crops.id を指定して削除する。
    """
    UserCropRepository.remove_user_crop(current_user["id"], user_crop_id)


# =============================================================================
# 農薬マスタエンドポイント
# =============================================================================

@app.get("/api/pesticide-masters", response_model=List[PesticideMasterResponse])
def list_pesticide_masters(crop: Optional[str] = None, current_user: Dict = Depends(get_current_user)):
    if crop:
        masters = PesticideMasterRepository.get_by_crop(crop)
    else:
        masters = PesticideMasterRepository.get_all()
    return [PesticideMasterResponse(**m) for m in masters]


@app.post("/api/pesticide-masters", response_model=PesticideMasterResponse, status_code=201)
def create_pesticide_master(master: PesticideMasterCreate, current_user: Dict = Depends(require_admin)):
    master_id = PesticideMasterRepository.create(master.model_dump())
    created = PesticideMasterRepository.get(master_id)
    return PesticideMasterResponse(**created)


@app.put("/api/pesticide-masters/{master_id}", response_model=PesticideMasterResponse)
def update_pesticide_master(master_id: int, master: PesticideMasterCreate, current_user: Dict = Depends(require_admin)):
    PesticideMasterRepository.update(master_id, master.model_dump())
    updated = PesticideMasterRepository.get(master_id)
    if not updated:
        raise HTTPException(status_code=404, detail="Pesticide master not found")
    return PesticideMasterResponse(**updated)


@app.delete("/api/pesticide-masters/{master_id}", status_code=204)
def delete_pesticide_master(master_id: int, current_user: Dict = Depends(require_admin)):
    PesticideMasterRepository.delete(master_id)


@app.get("/api/pesticide-masters/by-name/{name}/dilution-rates")
def get_dilution_rates_by_name(name: str, current_user: Dict = Depends(get_current_user)):
    """
    農薬名から希釈倍率候補を取得

    同名の農薬マスタから希釈倍率と対象病害虫の組み合わせを返す。
    防除記録入力時の補完に使用。
    """
    masters = PesticideMasterRepository.get_all()
    results = []
    seen = set()

    for m in masters:
        if m.get("name") == name:
            key = (m.get("dilution_rate", ""), m.get("target_pest", ""), m.get("crop", ""))
            if key not in seen and key[0]:  # 希釈倍率があるもののみ
                results.append({
                    "dilution_rate": m.get("dilution_rate", ""),
                    "target_pest": m.get("target_pest", ""),
                    "crop": m.get("crop", ""),
                    "application_method": m.get("application_method", ""),
                })
                seen.add(key)

    return results


# =============================================================================
# 農薬発注エンドポイント
# =============================================================================

@app.get("/api/pesticide-orders", response_model=List[PesticideOrderResponse])
def list_pesticide_orders(year: Optional[int] = None, current_user: Dict = Depends(get_current_user)):
    orders = PesticideOrderRepository.get_orders(current_user["id"], year)
    return [PesticideOrderResponse(**o) for o in orders]


@app.post("/api/pesticide-orders", response_model=PesticideOrderResponse, status_code=201)
def create_pesticide_order(order: PesticideOrderCreate, current_user: Dict = Depends(get_current_user)):
    order_id = PesticideOrderRepository.create_order(
        user_id=current_user["id"],
        plan_id=order.plan_id,
        year=order.year,
        items=order.items
    )
    created = PesticideOrderRepository.get_order(order_id)
    return PesticideOrderResponse(**created)


@app.get("/api/pesticide-orders/{order_id}", response_model=PesticideOrderResponse)
def get_pesticide_order(order_id: int, current_user: Dict = Depends(get_current_user)):
    order = PesticideOrderRepository.get_order(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order["user_id"] != current_user["id"] and current_user["role"] not in ["admin", "ja_staff"]:
        raise HTTPException(status_code=403, detail="Access denied")
    return PesticideOrderResponse(**order)


@app.put("/api/pesticide-orders/{order_id}", response_model=PesticideOrderResponse)
def update_pesticide_order(
    order_id: int,
    order_update: PesticideOrderUpdate,
    current_user: Dict = Depends(get_current_user)
):
    """農薬発注を更新（部分更新対応）"""
    order = PesticideOrderRepository.get_order(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order["user_id"] != current_user["id"] and current_user["role"] not in ["admin", "ja_staff"]:
        raise HTTPException(status_code=403, detail="Access denied")

    # 更新データを構築（Noneでないフィールドのみ）
    update_data = {}
    if order_update.year is not None:
        update_data["year"] = order_update.year
    if order_update.items is not None:
        update_data["items"] = order_update.items
    if order_update.notes is not None:
        update_data["notes"] = order_update.notes

    if update_data:
        PesticideOrderRepository.update_order(order_id, update_data)

    updated = PesticideOrderRepository.get_order(order_id)
    return PesticideOrderResponse(**updated)


@app.delete("/api/pesticide-orders/{order_id}", status_code=204)
def delete_pesticide_order(order_id: int, current_user: Dict = Depends(get_current_user)):
    order = PesticideOrderRepository.get_order(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order["user_id"] != current_user["id"] and current_user["role"] not in ["admin", "ja_staff"]:
        raise HTTPException(status_code=403, detail="Access denied")
    PesticideOrderRepository.delete_order(order_id)


# =============================================================================
# 農薬必要量自動計算エンドポイント
# =============================================================================

class CalculateFromPlanRequest(BaseModel):
    """輪作計画から農薬必要量を計算するリクエスト"""
    plan_id: int
    year: int


class CalculatedPesticideItem(BaseModel):
    """計算された農薬必要量"""
    pesticide_name: str
    crop: str
    area_ha: float
    quantity: float
    unit: str
    target_pest: Optional[str] = None
    dilution_rate: Optional[str] = None


class CalculateFromPlanResponse(BaseModel):
    """計算結果レスポンス"""
    items: List[CalculatedPesticideItem]
    summary: Dict[str, Any]
    message: str


# 散布基準: 10a あたり 100L
SPRAY_VOLUME_PER_10A = 100  # L


@app.post("/api/pesticide-orders/calculate-from-plan", response_model=CalculateFromPlanResponse)
def calculate_pesticide_from_plan(
    req: CalculateFromPlanRequest,
    current_user: Dict = Depends(get_current_user)
):
    """
    輪作計画から農薬必要量を自動計算

    指定された計画と年度から、各ほ場の作物・面積を取得し、
    農薬マスタを参照して必要量を計算する。
    """
    # 計画を取得
    plan = PlanRepository.get_plan(req.plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="計画が見つかりません")
    if plan["user_id"] != current_user["id"] and current_user["role"] not in ["admin", "ja_staff"]:
        raise HTTPException(status_code=403, detail="アクセス権限がありません")

    details = plan.get("details", [])
    if not details:
        raise HTTPException(status_code=400, detail="計画に詳細データがありません")

    # 指定年度のデータを抽出
    year_str = str(req.year)
    target_details = [d for d in details if str(d.get("year", "")) == year_str]
    if not target_details:
        raise HTTPException(
            status_code=400,
            detail=f"{req.year}年のデータが計画に含まれていません"
        )

    # ほ場IDごとに面積を取得
    field_areas = {}
    for d in target_details:
        field_id = d.get("field_id")
        if field_id and field_id not in field_areas:
            field = FieldRepository.get_field(field_id)
            if field:
                field_areas[field_id] = field.get("area_ha", 0)

    # 作物ごとの面積を集計
    crop_areas = {}
    for d in target_details:
        crop = d.get("crop", "").strip()
        if not crop:
            continue
        field_id = d.get("field_id")
        area_ha = field_areas.get(field_id, 0)
        if crop not in crop_areas:
            crop_areas[crop] = 0
        crop_areas[crop] += area_ha

    if not crop_areas:
        return CalculateFromPlanResponse(
            items=[],
            summary={},
            message="対象となる作物データがありません"
        )

    # 農薬マスタから作物別の農薬を取得して必要量を計算
    calculated_items = []

    for crop, area_ha in crop_areas.items():
        masters = PesticideMasterRepository.get_by_crop(crop)
        area_10a = area_ha * 10

        for m in masters:
            pesticide_name = m.get("name", "")
            dilution_rate = m.get("dilution_rate", "")
            target_pest = m.get("target_pest", "")

            if dilution_rate:
                try:
                    rate_str = str(dilution_rate).replace("倍", "").replace(",", "")
                    rate_str = rate_str.split("〜")[0].split("-")[0].split("/")[0]
                    rate = float(rate_str)
                    if rate > 0:
                        quantity_ml = (SPRAY_VOLUME_PER_10A / rate) * area_10a * 1000
                        quantity = quantity_ml / 1000
                        final_unit = "L"
                    else:
                        continue
                except (ValueError, ZeroDivisionError):
                    continue
            else:
                continue

            item = CalculatedPesticideItem(
                pesticide_name=pesticide_name,
                crop=crop,
                area_ha=area_ha,
                quantity=round(quantity, 2),
                unit=final_unit,
                target_pest=target_pest,
                dilution_rate=dilution_rate
            )
            calculated_items.append(item)

    crop_summary = ", ".join(f"{c}({a:.2f}ha)" for c, a in sorted(crop_areas.items()))
    message = f"計算完了: {len(calculated_items)}件の農薬\n対象: {crop_summary}"

    return CalculateFromPlanResponse(
        items=calculated_items,
        summary=crop_areas,
        message=message
    )


@app.get("/api/pesticide-orders/export/csv")
def export_pesticide_orders_csv(
    year: Optional[int] = None,
    current_user: Dict = Depends(get_current_user)
):
    """
    農薬発注データをCSV形式でエクスポート（BOM付きUTF-8でExcel対応）
    """
    orders = PesticideOrderRepository.get_orders(current_user["id"], year)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["発注ID", "年度", "作成日", "農薬名", "対象作物", "数量", "単位", "面積(ha)", "対象病害虫", "希釈倍率"])

    for order in orders:
        order_id = order.get("id", "")
        order_year = order.get("year", "")
        created_at = order.get("created_at", "")
        items = order.get("items", [])
        for item in items:
            writer.writerow([
                order_id,
                order_year,
                created_at,
                item.get("pesticide_name", ""),
                item.get("crop", ""),
                item.get("quantity", ""),
                item.get("unit", ""),
                item.get("area_ha", ""),
                item.get("target_pest", ""),
                item.get("dilution_rate", ""),
            ])

    output.seek(0)
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode("utf-8-sig")),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=pesticide_orders_{year or 'all'}.csv"}
    )


@app.get("/api/pesticide-orders/export/pdf")
def export_pesticide_orders_pdf(
    year: Optional[int] = None,
    current_user: Dict = Depends(get_current_user)
):
    """農薬発注リストをPDFで出力"""
    try:
        from rotation_planner.pesticide.pdf_export import (
            generate_pesticide_order_pdf,
            REPORTLAB_AVAILABLE
        )
    except ImportError:
        raise HTTPException(status_code=501, detail="PDF機能が利用できません")

    if not REPORTLAB_AVAILABLE:
        raise HTTPException(status_code=501, detail="reportlabがインストールされていません")

    import pandas as pd
    import tempfile

    orders = PesticideOrderRepository.get_orders(current_user["id"], year)
    if not orders:
        raise HTTPException(status_code=404, detail=f"{year or '全'}年の発注データがありません")

    summary_data = []
    for order in orders:
        for item in order.get("items", []):
            summary_data.append({
                "農薬名": item.get("pesticide_name", ""),
                "必要量": str(item.get("quantity", "")),
                "単位": item.get("unit", ""),
                "対象作物": item.get("crop", ""),
                "対象病害虫": item.get("target_pest", ""),
            })

    if not summary_data:
        raise HTTPException(status_code=404, detail="発注明細がありません")

    summary_df = pd.DataFrame(summary_data)
    detail_df = pd.DataFrame()

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        output_path = generate_pesticide_order_pdf(
            summary_df=summary_df,
            detail_df=detail_df,
            order_name=f"{year or '全年度'}発注リスト",
            target_year=str(year or "全年度"),
            output_path=tmp_path
        )
        if not output_path:
            raise HTTPException(status_code=500, detail="PDF生成に失敗しました")

        with open(tmp_path, "rb") as f:
            pdf_bytes = f.read()

        return StreamingResponse(
            io.BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename=pesticide_orders_{year or 'all'}.pdf"}
        )
    finally:
        import os
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


# =============================================================================
# 防除記録エンドポイント
# =============================================================================

@app.get("/api/pesticide-records", response_model=List[PesticideRecordResponse])
def list_pesticide_records(
    year: Optional[int] = None,
    field_id: Optional[int] = None,
    current_user: Dict = Depends(get_current_user)
):
    records = PesticideRecordRepository.get_records(
        user_id=current_user["id"],
        year=year,
        field_id=field_id
    )
    return [PesticideRecordResponse(**r) for r in records]


@app.post("/api/pesticide-records", response_model=PesticideRecordCreateResponse, status_code=201)
def create_pesticide_record(record: PesticideRecordCreate, current_user: Dict = Depends(get_current_user)):
    # 防除記録を作成
    record_id = PesticideRecordRepository.create_record(
        user_id=current_user["id"],
        data=record.model_dump()
    )
    created = PesticideRecordRepository.get_record(record_id)

    # 在庫自動控除
    inventory_warning = False
    inventory_message = None
    inventory_remaining = None

    if record.quantity and record.quantity > 0 and record.pesticide_name:
        inv_result = InventoryRepository.deduct_inventory(
            user_id=current_user["id"],
            pesticide_name=record.pesticide_name,
            quantity=record.quantity,
            unit=record.unit or "L",
            reference_type="pesticide_record",
            reference_id=record_id,
            created_by=current_user["id"]
        )
        inventory_warning = inv_result.get("warning", False)
        inventory_message = inv_result.get("message")
        inventory_remaining = inv_result.get("remaining")

    return PesticideRecordCreateResponse(
        record=PesticideRecordResponse(**created),
        inventory_warning=inventory_warning,
        inventory_message=inventory_message,
        inventory_remaining=inventory_remaining
    )


@app.get("/api/pesticide-records/{record_id}", response_model=PesticideRecordResponse)
def get_pesticide_record(record_id: int, current_user: Dict = Depends(get_current_user)):
    record = PesticideRecordRepository.get_record(record_id)
    if not record:
        raise HTTPException(status_code=404, detail="Record not found")
    if record["user_id"] != current_user["id"] and current_user["role"] not in ["admin", "ja_staff"]:
        raise HTTPException(status_code=403, detail="Access denied")
    return PesticideRecordResponse(**record)


@app.put("/api/pesticide-records/{record_id}", response_model=PesticideRecordResponse)
def update_pesticide_record(record_id: int, record: PesticideRecordCreate, current_user: Dict = Depends(get_current_user)):
    existing = PesticideRecordRepository.get_record(record_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Record not found")
    if existing["user_id"] != current_user["id"] and current_user["role"] not in ["admin", "ja_staff"]:
        raise HTTPException(status_code=403, detail="Access denied")
    PesticideRecordRepository.update_record(record_id, record.model_dump())
    updated = PesticideRecordRepository.get_record(record_id)
    return PesticideRecordResponse(**updated)


@app.delete("/api/pesticide-records/{record_id}", status_code=204)
def delete_pesticide_record(record_id: int, current_user: Dict = Depends(get_current_user)):
    existing = PesticideRecordRepository.get_record(record_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Record not found")
    if existing["user_id"] != current_user["id"] and current_user["role"] not in ["admin", "ja_staff"]:
        raise HTTPException(status_code=403, detail="Access denied")
    PesticideRecordRepository.delete_record(record_id)


# =============================================================================
# 在庫情報取得（防除記録との連携用）
# =============================================================================

@app.get("/api/inventory/by-pesticide", response_model=InventoryInfoResponse)
def get_inventory_by_pesticide(
    pesticide_name: str,
    current_user: Dict = Depends(get_current_user)
):
    """農薬名で在庫情報を取得"""
    inv = InventoryRepository.get_inventory_by_pesticide(
        user_id=current_user["id"],
        pesticide_name=pesticide_name
    )

    if inv:
        return InventoryInfoResponse(
            pesticide_name=pesticide_name,
            amount=inv.get("amount"),
            unit=inv.get("unit"),
            exists=True,
            last_used_date=inv.get("last_used_date"),
            usage_count=inv.get("usage_count")
        )
    else:
        return InventoryInfoResponse(
            pesticide_name=pesticide_name,
            exists=False
        )


@app.get("/api/pesticide-records/export/csv")
def export_pesticide_records_csv(
    year: Optional[int] = None,
    current_user: Dict = Depends(get_current_user)
):
    records = PesticideRecordRepository.get_records(user_id=current_user["id"], year=year)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["日付", "ほ場", "作物", "農薬名", "対象病害虫", "希釈倍率", "面積(ha)", "使用量", "単位", "天気", "気温", "作業者", "備考"])
    for r in records:
        writer.writerow([
            r.get("date", ""),
            r.get("field_code", ""),
            r.get("crop", ""),
            r.get("pesticide_name", ""),
            r.get("target_pest", ""),
            r.get("dilution_rate", ""),
            r.get("area_ha", ""),
            r.get("quantity", ""),
            r.get("unit", ""),
            r.get("weather", ""),
            r.get("temperature", ""),
            r.get("operator", ""),
            r.get("notes", ""),
        ])
    output.seek(0)
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode("utf-8-sig")),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=pesticide_records_{year or 'all'}.csv"}
    )


# =============================================================================
# 画像解析エンドポイント (Claude Vision API)
# =============================================================================

class ImageAnalyzeResponse(BaseModel):
    pesticide_name: Optional[str] = None
    confidence: Optional[float] = None
    raw_text: Optional[str] = None
    error: Optional[str] = None


@app.post("/api/pesticide-records/analyze-image", response_model=ImageAnalyzeResponse)
async def analyze_pesticide_image(
    image: UploadFile = File(...),
    current_user: Dict = Depends(get_current_user)
):
    """
    画像から農薬名を認識（Claude Vision API）

    - ANTHROPIC_API_KEYが設定されている場合: Claude Vision APIで解析
    - 設定されていない場合: モック応答を返す
    """
    import base64

    # 画像データを読み込み
    image_data = await image.read()

    # ファイル形式チェック
    content_type = image.content_type or ""
    if not content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="画像ファイルをアップロードしてください")

    # MIMEタイプ決定
    media_type_map = {
        "image/jpeg": "image/jpeg",
        "image/jpg": "image/jpeg",
        "image/png": "image/png",
        "image/gif": "image/gif",
        "image/webp": "image/webp",
    }
    media_type = media_type_map.get(content_type, "image/jpeg")

    # API キーの確認
    api_key = os.environ.get("ANTHROPIC_API_KEY")

    if not api_key:
        # モック応答（API_KEYがない場合）
        return ImageAnalyzeResponse(
            pesticide_name="ダコニール1000（モック）",
            confidence=0.85,
            raw_text="[モック応答] ANTHROPIC_API_KEYが設定されていないため、モックデータを返しています。",
            error=None
        )

    try:
        import anthropic

        # Base64エンコード
        image_base64 = base64.standard_b64encode(image_data).decode("utf-8")

        # Claude Vision API 呼び出し
        client = anthropic.Anthropic(api_key=api_key)
        message = client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=256,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": image_base64
                        }
                    },
                    {
                        "type": "text",
                        "text": """この画像から農薬名を抽出してください。
以下の形式で回答してください:
農薬名: [農薬名]
確信度: [0.0-1.0の数値]

農薬名が読み取れない場合は「農薬名: 不明」「確信度: 0.0」と回答してください。"""
                    }
                ]
            }]
        )

        # 応答を解析
        response_text = message.content[0].text
        pesticide_name = None
        confidence = None

        for line in response_text.split('\n'):
            line = line.strip()
            if line.startswith('農薬名:') or line.startswith('農薬名：'):
                name = line.split(':', 1)[-1].split('：', 1)[-1].strip()
                if name and name != '不明':
                    pesticide_name = name

            if line.startswith('確信度:') or line.startswith('確信度：'):
                conf_str = line.split(':', 1)[-1].split('：', 1)[-1].strip()
                try:
                    confidence = float(conf_str)
                except ValueError:
                    # high/medium/low形式の場合
                    conf_map = {"high": 0.9, "medium": 0.6, "low": 0.3}
                    confidence = conf_map.get(conf_str.lower(), 0.5)

        # デフォルト確信度
        if pesticide_name and confidence is None:
            confidence = 0.6

        return ImageAnalyzeResponse(
            pesticide_name=pesticide_name,
            confidence=confidence,
            raw_text=response_text,
            error=None
        )

    except ImportError:
        return ImageAnalyzeResponse(
            pesticide_name=None,
            confidence=None,
            raw_text=None,
            error="anthropicパッケージがインストールされていません"
        )
    except Exception as e:
        return ImageAnalyzeResponse(
            pesticide_name=None,
            confidence=None,
            raw_text=None,
            error=f"画像解析エラー: {str(e)}"
        )


# =============================================================================
# 防除記録画像保存・取得
# =============================================================================

import uuid
import shutil
from pathlib import Path

UPLOAD_DIR = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) / "uploads" / "pesticide_records"


class RecordImageResponse(BaseModel):
    id: str
    record_id: int
    filename: str
    original_name: str
    url: str
    created_at: str


@app.post("/api/pesticide-records/{record_id}/images", response_model=RecordImageResponse, status_code=201)
async def upload_record_image(record_id: int, image: UploadFile = File(...), current_user: Dict = Depends(get_current_user)):
    """防除記録に画像を添付"""
    record = PesticideRecordRepository.get_record(record_id)
    if not record:
        raise HTTPException(status_code=404, detail="Record not found")
    if record["user_id"] != current_user["id"] and current_user["role"] not in ["admin", "ja_staff"]:
        raise HTTPException(status_code=403, detail="Access denied")
    if not (image.content_type or "").startswith("image/"):
        raise HTTPException(status_code=400, detail="画像ファイルをアップロードしてください")
    record_dir = UPLOAD_DIR / str(record_id)
    record_dir.mkdir(parents=True, exist_ok=True)
    ext = os.path.splitext(image.filename or ".jpg")[1] or ".jpg"
    image_id = str(uuid.uuid4())
    file_path = record_dir / f"{image_id}{ext}"
    with open(file_path, "wb") as f:
        shutil.copyfileobj(image.file, f)
    import json
    meta_file = record_dir / "meta.json"
    meta = json.load(open(meta_file, "r", encoding="utf-8")) if meta_file.exists() else []
    created_at = datetime.now().isoformat()
    meta.append({"id": image_id, "filename": f"{image_id}{ext}", "original_name": image.filename or "image.jpg", "created_at": created_at})
    json.dump(meta, open(meta_file, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    return RecordImageResponse(id=image_id, record_id=record_id, filename=f"{image_id}{ext}", original_name=image.filename or "image.jpg", url=f"/api/pesticide-records/{record_id}/images/{image_id}", created_at=created_at)


@app.get("/api/pesticide-records/{record_id}/images", response_model=List[RecordImageResponse])
def list_record_images(record_id: int, current_user: Dict = Depends(get_current_user)):
    """防除記録の画像一覧"""
    record = PesticideRecordRepository.get_record(record_id)
    if not record:
        raise HTTPException(status_code=404, detail="Record not found")
    if record["user_id"] != current_user["id"] and current_user["role"] not in ["admin", "ja_staff"]:
        raise HTTPException(status_code=403, detail="Access denied")
    import json
    meta_file = UPLOAD_DIR / str(record_id) / "meta.json"
    if not meta_file.exists():
        return []
    meta = json.load(open(meta_file, "r", encoding="utf-8"))
    return [RecordImageResponse(id=m["id"], record_id=record_id, filename=m["filename"], original_name=m["original_name"], url=f"/api/pesticide-records/{record_id}/images/{m['id']}", created_at=m["created_at"]) for m in meta]


@app.get("/api/pesticide-records/{record_id}/images/{image_id}")
def get_record_image(record_id: int, image_id: str, current_user: Dict = Depends(get_current_user)):
    """防除記録の画像取得"""
    record = PesticideRecordRepository.get_record(record_id)
    if not record:
        raise HTTPException(status_code=404, detail="Record not found")
    if record["user_id"] != current_user["id"] and current_user["role"] not in ["admin", "ja_staff"]:
        raise HTTPException(status_code=403, detail="Access denied")
    import json
    meta_file = UPLOAD_DIR / str(record_id) / "meta.json"
    if not meta_file.exists():
        raise HTTPException(status_code=404, detail="Image not found")
    meta = json.load(open(meta_file, "r", encoding="utf-8"))
    img = next((m for m in meta if m["id"] == image_id), None)
    if not img:
        raise HTTPException(status_code=404, detail="Image not found")
    fp = UPLOAD_DIR / str(record_id) / img["filename"]
    if not fp.exists():
        raise HTTPException(status_code=404, detail="Image file not found")
    return FileResponse(fp, filename=img["original_name"], media_type="image/jpeg")


@app.delete("/api/pesticide-records/{record_id}/images/{image_id}", status_code=204)
def delete_record_image(record_id: int, image_id: str, current_user: Dict = Depends(get_current_user)):
    """防除記録の画像削除"""
    record = PesticideRecordRepository.get_record(record_id)
    if not record:
        raise HTTPException(status_code=404, detail="Record not found")
    if record["user_id"] != current_user["id"] and current_user["role"] not in ["admin", "ja_staff"]:
        raise HTTPException(status_code=403, detail="Access denied")
    import json
    meta_file = UPLOAD_DIR / str(record_id) / "meta.json"
    if not meta_file.exists():
        raise HTTPException(status_code=404, detail="Image not found")
    meta = json.load(open(meta_file, "r", encoding="utf-8"))
    img = next((m for m in meta if m["id"] == image_id), None)
    if not img:
        raise HTTPException(status_code=404, detail="Image not found")
    fp = UPLOAD_DIR / str(record_id) / img["filename"]
    if fp.exists():
        fp.unlink()
    meta = [m for m in meta if m["id"] != image_id]
    json.dump(meta, open(meta_file, "w", encoding="utf-8"), ensure_ascii=False, indent=2)


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
    plan = PlanRepository.get_plan(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
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
        coordinates = f.get("coordinates")
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
    plan = PlanRepository.get_plan(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="計画が見つかりません")

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
        return RotationImportResponse(
            success=False,
            import_count=0,
            error_count=1,
            errors=[f"計画の保存に失敗しました: {str(e)}"],
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

        constraints_obj = Constraints(
            crop_mins=crop_mins,
            crop_caps=crop_caps,
            min_gap_years=min_gap_years,
            min_fields=min_fields,
            max_fields=max_fields,
            forbidden_transitions=forbidden,
            preferred_transitions=preferred,
            main_crops=main_crops,
            unknown_mode=unknown_mode
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
        raise HTTPException(status_code=500, detail=f"最適化エラー: {str(e)}")


# =============================================================================
# ダッシュボード統計
# =============================================================================

class DashboardStatsResponse(BaseModel):
    """ダッシュボード統計レスポンス"""
    fields: Dict[str, Any]
    crops: List[Dict[str, Any]]
    orders: Dict[str, Any]
    records: Dict[str, Any]
    plans: Dict[str, Any]


@app.get("/api/dashboard/stats", response_model=DashboardStatsResponse)
def get_dashboard_stats(current_user: Dict = Depends(get_current_user)):
    """
    ダッシュボード用の統計情報を取得

    Returns:
        - fields: ほ場統計（総数、総面積）
        - crops: 今年度の作付状況（作物別面積）
        - orders: 農薬発注状況（発注済み/未発注）
        - records: 防除記録（今月の記録数）
        - plans: 輪作計画（保存済み計画数）
    """
    user_id = current_user["id"]

    # 1. ほ場統計
    fields = FieldRepository.get_fields(user_id)
    total_area = sum(f.get("area_ha", 0) for f in fields)
    fields_stats = {
        "count": len(fields),
        "total_area_ha": round(total_area, 2)
    }

    # 2. 今年度の作付状況（作物別面積）
    current_year = datetime.now().year
    crops_area = {}
    for field in fields:
        field_id = field.get("id")
        if not field_id:
            continue
        history = CropHistoryRepository.get_history(field_id)
        for h in history:
            if h.get("year") == current_year:
                crop = h.get("crop", "")
                if crop:
                    area = field.get("area_ha", 0)
                    if crop not in crops_area:
                        crops_area[crop] = 0
                    crops_area[crop] += area
    crops_stats = [
        {"name": name, "area_ha": round(area, 2)}
        for name, area in sorted(crops_area.items(), key=lambda x: -x[1])
    ]

    # 3. 農薬発注状況
    orders = PesticideOrderRepository.get_orders(user_id)
    orders_this_year = [o for o in orders if o.get("year") == current_year]
    orders_stats = {
        "total": len(orders_this_year),
        "pending": 0  # 将来的にステータス管理を追加可能
    }

    # 4. 防除記録（今月の記録数）
    records = PesticideRecordRepository.get_records(user_id=user_id)
    current_month = datetime.now().strftime("%Y-%m")
    this_month_count = sum(
        1 for r in records
        if r.get("date", "").startswith(current_month)
    )
    records_stats = {
        "this_month": this_month_count
    }

    # 5. 輪作計画（保存済み計画数）
    plans = PlanRepository.get_plans(user_id)
    plans_stats = {
        "count": len(plans)
    }

    return DashboardStatsResponse(
        fields=fields_stats,
        crops=crops_stats,
        orders=orders_stats,
        records=records_stats,
        plans=plans_stats
    )


# =============================================================================
# ヘルスチェック
# =============================================================================

@app.get("/api/health")
def health_check():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}


# =============================================================================
# 開発サーバー起動
# =============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
