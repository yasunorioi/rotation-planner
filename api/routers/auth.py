"""
認証ルーター

ログイン、ユーザー情報取得のエンドポイント
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Dict, Any, Optional

from rotation_planner.common import authenticate, get_user_info
from api.deps import create_token, get_current_user
from api.error_handlers import require_found

router = APIRouter(prefix="/api/auth", tags=["認証"])


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


# =============================================================================
# エンドポイント
# =============================================================================

@router.post("/login", response_model=TokenResponse)
def login(req: LoginRequest):
    """ログイン（JWT発行）"""
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


@router.get("/me", response_model=UserResponse)
def get_me(current_user: Dict = Depends(get_current_user)):
    """現在のユーザー情報を取得"""
    user = require_found(get_user_info(current_user["username"]), "ユーザー")
    return UserResponse(
        id=user["id"],
        username=user["username"],
        role=user["role"],
        display_name=user.get("display_name")
    )
