"""
農業管理アプリ REST API

FastAPI を使用した REST API。
認証は JWT トークン、データは SQLite に保存。
"""

from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import StreamingResponse
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
    JAStaffRepository,
)

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


# =============================================================================
# ほ場エンドポイント
# =============================================================================

@app.get("/api/fields", response_model=List[FieldResponse])
def list_fields(current_user: Dict = Depends(get_current_user)):
    fields = FieldRepository.get_fields(current_user["id"])
    return [FieldResponse.from_db(f, user_id=current_user["id"]) for f in fields]


@app.post("/api/fields", response_model=FieldResponse, status_code=201)
def create_field(field: FieldCreate, current_user: Dict = Depends(get_current_user)):
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
    CropHistoryRepository.delete_history(history_id)


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


@app.delete("/api/pesticide-orders/{order_id}", status_code=204)
def delete_pesticide_order(order_id: int, current_user: Dict = Depends(get_current_user)):
    order = PesticideOrderRepository.get_order(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order["user_id"] != current_user["id"] and current_user["role"] not in ["admin", "ja_staff"]:
        raise HTTPException(status_code=403, detail="Access denied")
    PesticideOrderRepository.delete_order(order_id)


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


@app.post("/api/pesticide-records", response_model=PesticideRecordResponse, status_code=201)
def create_pesticide_record(record: PesticideRecordCreate, current_user: Dict = Depends(get_current_user)):
    record_id = PesticideRecordRepository.create_record(
        user_id=current_user["id"],
        data=record.model_dump()
    )
    created = PesticideRecordRepository.get_record(record_id)
    return PesticideRecordResponse(**created)


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
