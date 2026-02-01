"""
農業管理アプリ REST API

FastAPI を使用した REST API。
認証は JWT トークン、データは SQLite に保存。
"""

from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import jwt
import sys
import os

# 親ディレクトリをパスに追加（rotation_planner モジュールを使用するため）
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rotation_planner.common import (
    authenticate,
    get_user_info,
    FieldRepository,
    CropHistoryRepository,
    PlanRepository,
    UserRepository,
    CropMasterRepository,
    UserCropRepository,
    UserConstraintsRepository,
)

# =============================================================================
# アプリケーション設定
# =============================================================================

app = FastAPI(
    title="農業管理アプリ API",
    description="輪作計画・ほ場管理のREST API",
    version="1.0.0"
)

# CORS設定（開発環境用）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# JWT設定
JWT_SECRET = os.environ.get("JWT_SECRET", "dev-secret-key-change-in-production")
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


class FieldCreate(BaseModel):
    field_code: str
    field_name: Optional[str] = None
    district: Optional[str] = None
    area_ha: float = Field(gt=0)
    beet_forbidden: bool = False


class FieldUpdate(BaseModel):
    field_code: Optional[str] = None
    field_name: Optional[str] = None
    district: Optional[str] = None
    area_ha: Optional[float] = Field(default=None, gt=0)
    beet_forbidden: Optional[bool] = None


class FieldResponse(BaseModel):
    id: int
    user_id: int
    field_code: str
    field_name: Optional[str]
    district: Optional[str]
    area_ha: float
    beet_forbidden: bool
    created_at: Optional[str]
    updated_at: Optional[str]


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
    details: List[Dict[str, Any]]  # [{field_id, year, crop}, ...]


class PlanResponse(BaseModel):
    id: int
    user_id: int
    name: str
    start_year: int
    end_year: int
    created_at: Optional[str]
    updated_at: Optional[str]
    details: Optional[List[Dict[str, Any]]] = None


class ConstraintsUpdate(BaseModel):
    constraints: List[Dict[str, Any]]  # 制約テーブル
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
    category: Optional[str]
    is_active: bool


# =============================================================================
# 認証ヘルパー
# =============================================================================

def create_token(user_id: int, username: str, role: str) -> str:
    """JWTトークン生成"""
    payload = {
        "sub": str(user_id),
        "username": username,
        "role": role,
        "exp": datetime.utcnow() + timedelta(hours=JWT_EXPIRE_HOURS)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Dict[str, Any]:
    """現在のユーザーを取得"""
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


# =============================================================================
# 認証エンドポイント
# =============================================================================

@app.post("/api/auth/login", response_model=TokenResponse)
def login(req: LoginRequest):
    """ログイン"""
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
    """現在のユーザー情報取得"""
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
# ほ場エンドポイント
# =============================================================================

@app.get("/api/fields", response_model=List[FieldResponse])
def list_fields(current_user: Dict = Depends(get_current_user)):
    """ほ場一覧取得"""
    fields = FieldRepository.get_fields(current_user["id"])
    return [FieldResponse(**f) for f in fields]


@app.post("/api/fields", response_model=FieldResponse, status_code=201)
def create_field(field: FieldCreate, current_user: Dict = Depends(get_current_user)):
    """ほ場作成"""
    field_id = FieldRepository.create_field(
        user_id=current_user["id"],
        field_code=field.field_code,
        field_name=field.field_name,
        district=field.district,
        area_ha=field.area_ha,
        beet_forbidden=field.beet_forbidden
    )
    created = FieldRepository.get_field(field_id)
    if not created:
        raise HTTPException(status_code=500, detail="Failed to create field")
    return FieldResponse(**created)


@app.get("/api/fields/{field_id}", response_model=FieldResponse)
def get_field(field_id: int, current_user: Dict = Depends(get_current_user)):
    """ほ場取得"""
    field = FieldRepository.get_field(field_id)
    if not field:
        raise HTTPException(status_code=404, detail="Field not found")
    if field["user_id"] != current_user["id"] and current_user["role"] not in ["admin", "ja_staff"]:
        raise HTTPException(status_code=403, detail="Access denied")
    return FieldResponse(**field)


@app.put("/api/fields/{field_id}", response_model=FieldResponse)
def update_field(field_id: int, field: FieldUpdate, current_user: Dict = Depends(get_current_user)):
    """ほ場更新"""
    existing = FieldRepository.get_field(field_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Field not found")
    if existing["user_id"] != current_user["id"] and current_user["role"] not in ["admin", "ja_staff"]:
        raise HTTPException(status_code=403, detail="Access denied")

    update_data = field.model_dump(exclude_unset=True)
    if update_data:
        FieldRepository.update_field(field_id, **update_data)

    updated = FieldRepository.get_field(field_id)
    return FieldResponse(**updated)


@app.delete("/api/fields/{field_id}", status_code=204)
def delete_field(field_id: int, current_user: Dict = Depends(get_current_user)):
    """ほ場削除"""
    existing = FieldRepository.get_field(field_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Field not found")
    if existing["user_id"] != current_user["id"] and current_user["role"] not in ["admin", "ja_staff"]:
        raise HTTPException(status_code=403, detail="Access denied")

    FieldRepository.delete_field(field_id)


# =============================================================================
# 作付履歴エンドポイント
# =============================================================================

@app.get("/api/fields/{field_id}/history", response_model=List[CropHistoryResponse])
def list_crop_history(field_id: int, current_user: Dict = Depends(get_current_user)):
    """ほ場の作付履歴取得"""
    field = FieldRepository.get_field(field_id)
    if not field:
        raise HTTPException(status_code=404, detail="Field not found")
    if field["user_id"] != current_user["id"] and current_user["role"] not in ["admin", "ja_staff"]:
        raise HTTPException(status_code=403, detail="Access denied")

    history = CropHistoryRepository.get_history(field_id)
    return [CropHistoryResponse(**h) for h in history]


@app.post("/api/fields/{field_id}/history", response_model=CropHistoryResponse, status_code=201)
def add_crop_history(field_id: int, history: CropHistoryCreate, current_user: Dict = Depends(get_current_user)):
    """作付履歴追加"""
    field = FieldRepository.get_field(field_id)
    if not field:
        raise HTTPException(status_code=404, detail="Field not found")
    if field["user_id"] != current_user["id"] and current_user["role"] not in ["admin", "ja_staff"]:
        raise HTTPException(status_code=403, detail="Access denied")

    history_id = CropHistoryRepository.add_history(field_id, history.year, history.crop)
    return CropHistoryResponse(id=history_id, field_id=field_id, year=history.year, crop=history.crop)


@app.delete("/api/history/{history_id}", status_code=204)
def delete_crop_history(history_id: int, current_user: Dict = Depends(get_current_user)):
    """作付履歴削除"""
    CropHistoryRepository.delete_history(history_id)


# =============================================================================
# 輪作計画エンドポイント
# =============================================================================

@app.get("/api/plans", response_model=List[PlanResponse])
def list_plans(current_user: Dict = Depends(get_current_user)):
    """輪作計画一覧取得"""
    plans = PlanRepository.get_plans(current_user["id"])
    return [PlanResponse(**p) for p in plans]


@app.post("/api/plans", response_model=PlanResponse, status_code=201)
def create_plan(plan: PlanCreate, current_user: Dict = Depends(get_current_user)):
    """輪作計画作成"""
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
    """輪作計画取得（詳細含む）"""
    plan = PlanRepository.get_plan(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    if plan["user_id"] != current_user["id"] and current_user["role"] not in ["admin", "ja_staff"]:
        raise HTTPException(status_code=403, detail="Access denied")
    return PlanResponse(**plan)


@app.delete("/api/plans/{plan_id}", status_code=204)
def delete_plan(plan_id: int, current_user: Dict = Depends(get_current_user)):
    """輪作計画削除"""
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
    """ユーザーの制約設定取得"""
    data = UserConstraintsRepository.get_constraints(current_user["id"])
    if not data:
        # デフォルト値を返す
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
    """ユーザーの制約設定更新"""
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
    """作物マスタ一覧取得"""
    crops = CropMasterRepository.get_all(active_only=True)
    return [CropResponse(**c) for c in crops]


@app.get("/api/user-crops", response_model=List[Dict[str, Any]])
def list_user_crops(current_user: Dict = Depends(get_current_user)):
    """ユーザーの選択作物一覧取得"""
    crops = UserCropRepository.get_user_crops(current_user["id"])
    return crops


# =============================================================================
# ヘルスチェック
# =============================================================================

@app.get("/api/health")
def health_check():
    """ヘルスチェック"""
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}


# =============================================================================
# 開発サーバー起動
# =============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
