"""
管理ルーター

ユーザー管理、バックアップ、システム情報、FAMIC、筆ポリゴン管理等
"""

from fastapi import APIRouter, HTTPException, Depends, UploadFile, File
from fastapi.responses import StreamingResponse, FileResponse
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime
import os
import sys
import tempfile
import zipfile
import json
import sqlite3
from glob import glob

from rotation_planner.common import (
    get_user_info,
    add_user,
    update_password,
    update_user_role,
    delete_user,
    load_users,
)
from api.deps import require_admin
from api.error_handlers import require_found

router = APIRouter(prefix="/api/admin", tags=["管理"])


# =============================================================================
# Pydantic モデル
# =============================================================================

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


class DebugModeRequest(BaseModel):
    enabled: bool


class DebugModeResponse(BaseModel):
    debug_mode: bool
    message: str


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
    message: Optional[str] = None


class FamicStatusResponse(BaseModel):
    registry_count: int
    usage_count: int
    last_update: Optional[str] = None
    auto_update_enabled: bool
    next_update: Optional[str] = None
    terms_accepted: bool


class FamicUpdateResponse(BaseModel):
    success: bool
    basic_count: int
    usage_count: int
    message: str


# =============================================================================
# エンドポイント
# =============================================================================

# ユーザー管理
@router.get("/users", response_model=List[UserResponse])
def list_users(current_user: Dict = Depends(require_admin)):
    """ユーザー一覧取得（管理者のみ）"""
    users_data = load_users()
    return [
        UserResponse(
            id=i + 1,
            username=u["username"],
            role=u["role"],
            display_name=u.get("display_name")
        )
        for i, u in enumerate(users_data)
    ]


@router.post("/users", response_model=UserResponse, status_code=201)
def create_user(user: UserCreate, current_user: Dict = Depends(require_admin)):
    """ユーザー作成（管理者のみ）"""
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


@router.put("/users/{username}", response_model=UserResponse)
def update_user(username: str, user: UserUpdate, current_user: Dict = Depends(require_admin)):
    """ユーザー更新（管理者のみ）"""
    if user.password:
        update_password(username, user.password)
    if user.role:
        update_user_role(username, user.role)
    updated = require_found(get_user_info(username), "ユーザー")
    return UserResponse(
        id=updated["id"],
        username=updated["username"],
        role=updated["role"],
        display_name=updated.get("display_name")
    )


@router.delete("/users/{username}", status_code=204)
def remove_user(username: str, current_user: Dict = Depends(require_admin)):
    """ユーザー削除（管理者のみ）"""
    delete_user(username)


# =============================================================================
# 設定ファイル・キャッシュディレクトリ
# =============================================================================

SETTINGS_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "data",
    "settings.json"
)

FUDE_CACHE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "data",
    "fude_cache"
)


def load_app_settings() -> Dict[str, Any]:
    """アプリ設定を読み込む"""
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return {"debug_mode": False}


def save_app_settings(settings: Dict[str, Any]) -> None:
    """アプリ設定を保存"""
    os.makedirs(os.path.dirname(SETTINGS_FILE), exist_ok=True)
    with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
        json.dump(settings, f, ensure_ascii=False, indent=2)


# =============================================================================
# 管理系エンドポイント（バックアップ、システム情報、デバッグ、筆ポリゴン、FAMIC）
# =============================================================================

@router.get("/backup")
def download_backup(current_user: Dict = Depends(require_admin)):
    """
    DBバックアップをダウンロード（管理者のみ）

    Returns:
        rotation_planner.db のダウンロード
    """
    # DBファイルのパスを取得
    db_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
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


@router.get("/system-info", response_model=SystemInfoResponse)
def get_system_info(current_user: Dict = Depends(require_admin)):
    """
    システム情報を取得（管理者のみ）

    Returns:
        アプリバージョン、DB情報、環境情報など
    """
    import fastapi

    # DBファイルのパス
    db_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
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
                if not table_name.isidentifier():
                    continue
                cursor.execute(f"SELECT COUNT(*) FROM [{table_name}]")
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
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "data",
        "backups"
    )
    last_backup = None
    if os.path.exists(backup_dir):
        backup_files = glob(os.path.join(backup_dir, "*.db"))
        if backup_files:
            latest = max(backup_files, key=os.path.getmtime)
            last_backup = datetime.fromtimestamp(os.path.getmtime(latest)).strftime("%Y-%m-%d %H:%M:%S")

    # app.version を取得するために main モジュールを import
    from api.main import app
    return SystemInfoResponse(
        app_version=app.version,
        db_size_kb=round(db_size_kb, 1),
        db_last_modified=db_last_modified,
        tables=tables,
        user_count=user_count,
        environment=environment,
        last_backup=last_backup
    )


@router.get("/settings/debug", response_model=DebugModeResponse)
def get_debug_mode(current_user: Dict = Depends(require_admin)):
    """デバッグモードの状態を取得"""
    settings = load_app_settings()
    return DebugModeResponse(
        debug_mode=settings.get("debug_mode", False),
        message=""
    )


@router.put("/settings/debug", response_model=DebugModeResponse)
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


@router.get("/fude-polygon", response_model=FudePolygonListResponse)
def list_fude_polygons(current_user: Dict = Depends(require_admin)):
    """筆ポリゴンファイル一覧を取得"""
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
                        data = json.load(f)
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
                        data = json.load(f)
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


@router.post("/fude-polygon", response_model=FudePolygonUploadResponse)
async def upload_fude_polygon(file: UploadFile = File(...), current_user: Dict = Depends(require_admin)):
    """筆ポリゴンGeoJSONをアップロード"""
    os.makedirs(FUDE_CACHE_DIR, exist_ok=True)
    content = await file.read()
    try:
        data = json.loads(content.decode('utf-8'))
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
        json.dump(data, f, ensure_ascii=False)
    return FudePolygonUploadResponse(
        success=True, filename=filename, feature_count=feature_count,
        message=f"アップロード完了（{feature_count}筆）"
    )


@router.delete("/fude-polygon/{filename}", status_code=204)
def delete_fude_polygon(filename: str, current_user: Dict = Depends(require_admin)):
    """筆ポリゴンファイルを削除"""
    if '..' in filename or '/' in filename or '\\' in filename:
        raise HTTPException(status_code=400, detail="無効なファイル名")
    file_path = os.path.join(FUDE_CACHE_DIR, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="ファイルが見つかりません")
    os.remove(file_path)


@router.get("/famic/status", response_model=FamicStatusResponse)
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
            next_update=settings.get("next_update"),
            terms_accepted=settings.get("terms_accepted", False)
        )
    except ImportError:
        return FamicStatusResponse(
            registry_count=0, usage_count=0, last_update=None,
            auto_update_enabled=False, next_update=None, terms_accepted=False
        )


@router.post("/famic/update", response_model=FamicUpdateResponse)
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


@router.put("/famic/auto-update")
def set_famic_auto_update(enabled: bool, current_user: Dict = Depends(require_admin)):
    """FAMIC自動更新設定を変更"""
    try:
        from rotation_planner.famic import set_famic_settings
        set_famic_settings(auto_update_enabled=enabled)
        status = "有効" if enabled else "無効"
        return {"success": True, "message": f"自動更新を「{status}」に変更しました"}
    except ImportError:
        raise HTTPException(status_code=500, detail="FAMICモジュールが利用できません")


@router.post("/famic/accept-terms")
def accept_famic_terms(current_user: Dict = Depends(require_admin)):
    """FAMIC利用規約に同意"""
    try:
        from rotation_planner.famic import set_famic_settings
        set_famic_settings(terms_accepted=True)
        return {"success": True, "message": "FAMIC利用規約に同意しました"}
    except ImportError:
        raise HTTPException(status_code=500, detail="FAMICモジュールが利用できません")
