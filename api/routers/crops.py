"""
作物管理ルーター

作物マスタ、ユーザー作物、科マッピング、FAMIC連携
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import logging

from rotation_planner.common import (
    CropMasterRepository,
    UserCropRepository,
    PesticideUsageRepository,
)
from rotation_planner.common.exceptions import DuplicateKeyError
from api.deps import get_current_user, require_admin

router = APIRouter(tags=["作物"])
logger = logging.getLogger("rotation_planner.api")


# =============================================================================
# Pydantic モデル
# =============================================================================

class CropResponse(BaseModel):
    id: int
    name: str
    category: Optional[str] = None
    family: Optional[str] = None
    is_active: bool = True


class UserCropUpdate(BaseModel):
    crop_ids: List[int]


class UserCropCustomName(BaseModel):
    crop_id: int
    custom_name: str


class UserCropAddCustom(BaseModel):
    parent_crop_id: int
    custom_name: str


# =============================================================================
# 作物マスタエンドポイント
# =============================================================================

@router.get("/api/crops", response_model=List[CropResponse])
def list_crops(current_user: Dict = Depends(get_current_user)):
    crops = CropMasterRepository.get_all(active_only=True)
    result = []
    for c in crops:
        result.append(CropResponse(
            id=c.get("id", 0),
            name=c.get("name", ""),
            category=c.get("category"),
            family=c.get("family"),
            is_active=c.get("is_active", True)
        ))
    return result


@router.get("/api/crop-families", response_model=Dict[str, str])
def get_crop_families(current_user: Dict = Depends(get_current_user)):
    """作物名→科名マッピングを取得（隣接筆制約で使用）"""
    return CropMasterRepository.get_family_map()


@router.get("/api/user-crops", response_model=List[Dict[str, Any]])
def list_user_crops(current_user: Dict = Depends(get_current_user)):
    crops = UserCropRepository.get_user_crops(current_user["id"])
    return crops


@router.put("/api/user-crops")
def update_user_crops(req: UserCropUpdate, current_user: Dict = Depends(get_current_user)):
    UserCropRepository.set_user_crops(current_user["id"], req.crop_ids)
    return {"status": "ok"}


@router.put("/api/user-crops/custom-name")
def set_crop_custom_name(req: UserCropCustomName, current_user: Dict = Depends(get_current_user)):
    UserCropRepository.set_custom_name(current_user["id"], req.crop_id, req.custom_name)
    return {"status": "ok"}


@router.post("/api/user-crops/custom", status_code=201)
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
    except DuplicateKeyError:
        raise HTTPException(status_code=409, detail="この作物は既に登録されています")
    except Exception as e:
        logger.error("カスタム作物追加エラー: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="作物の追加に失敗しました")


@router.delete("/api/user-crops/{user_crop_id}", status_code=204)
def delete_custom_crop(user_crop_id: int, current_user: Dict = Depends(get_current_user)):
    """
    カスタム作物を削除

    user_crops.id を指定して削除する。
    """
    UserCropRepository.remove_user_crop(current_user["id"], user_crop_id)


# =============================================================================
# FAMIC作物名検索エンドポイント
# =============================================================================

@router.get("/api/famic/crops")
def search_famic_crops(q: Optional[str] = None, limit: int = 50, current_user: Dict = Depends(get_current_user)):
    """
    FAMIC登録適用情報から作物名を検索

    パラメータ:
    - q: 検索キーワード（部分一致）
    - limit: 最大件数（デフォルト50）

    Returns:
        作物名のリスト
    """
    crops = PesticideUsageRepository.get_distinct_crops(q, limit)
    return crops


@router.post("/api/crops/from-famic", status_code=201)
def add_crop_from_famic(name: str, current_user: Dict = Depends(require_admin)):
    """
    FAMIC作物名をマスタ作物として追加（管理者のみ）

    FAMIC適用情報に存在する作物名をcrop_masterに追加する。
    """
    # FAMIC作物名として存在するか確認
    famic_crops = PesticideUsageRepository.get_distinct_crops(name, 1)
    exact_match = [c for c in famic_crops if c == name]
    if not exact_match:
        # 部分一致で探す
        famic_crops = PesticideUsageRepository.get_distinct_crops(name, 100)
        exact_match = [c for c in famic_crops if c == name]
        if not exact_match:
            raise HTTPException(status_code=400, detail=f"FAMIC適用情報に '{name}' が見つかりません")

    # 既に登録されているか確認
    existing = CropMasterRepository.get_all(active_only=False)
    if any(c["name"] == name for c in existing):
        raise HTTPException(status_code=400, detail=f"'{name}' は既に登録されています")

    # マスタに追加
    crop_id = CropMasterRepository.create(name)
    return {"status": "ok", "id": crop_id, "name": name}
