"""
輪作計画ルーター

輪作計画のCRUD、制約設定
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import logging

from rotation_planner.common import (
    PlanRepository,
    UserConstraintsRepository,
)
from api.error_handlers import require_found
from api.deps import get_current_user

router = APIRouter(tags=["輪作計画"])
logger = logging.getLogger("rotation_planner.api")


# =============================================================================
# Pydantic モデル
# =============================================================================

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


# =============================================================================
# 輪作計画エンドポイント
# =============================================================================

@router.get("/api/plans", response_model=List[PlanResponse])
def list_plans(current_user: Dict = Depends(get_current_user)):
    plans = PlanRepository.get_plans(current_user["id"])
    return [PlanResponse(**p) for p in plans]


@router.post("/api/plans", response_model=PlanResponse, status_code=201)
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
    created = require_found(PlanRepository.get_plan(plan_id), "輪作計画")
    return PlanResponse(**created)


@router.get("/api/plans/{plan_id}", response_model=PlanResponse)
def get_plan(plan_id: int, current_user: Dict = Depends(get_current_user)):
    plan = require_found(PlanRepository.get_plan(plan_id), "輪作計画")
    if plan["user_id"] != current_user["id"] and current_user["role"] not in ["admin", "ja_staff"]:
        raise HTTPException(status_code=403, detail="Access denied")
    return PlanResponse(**plan)


@router.put("/api/plans/{plan_id}", response_model=PlanResponse)
def update_plan(plan_id: int, plan_update: PlanUpdate, current_user: Dict = Depends(get_current_user)):
    """輪作計画を更新（部分更新対応）"""
    plan = require_found(PlanRepository.get_plan(plan_id), "輪作計画")
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


@router.delete("/api/plans/{plan_id}", status_code=204)
def delete_plan(plan_id: int, current_user: Dict = Depends(get_current_user)):
    plan = require_found(PlanRepository.get_plan(plan_id), "輪作計画")
    if plan["user_id"] != current_user["id"] and current_user["role"] not in ["admin", "ja_staff"]:
        raise HTTPException(status_code=403, detail="Access denied")
    PlanRepository.delete_plan(plan_id)


# =============================================================================
# 制約設定エンドポイント
# =============================================================================

@router.get("/api/constraints", response_model=ConstraintsResponse)
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


@router.put("/api/constraints", response_model=ConstraintsResponse)
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
