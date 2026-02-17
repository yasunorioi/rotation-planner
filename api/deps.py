"""
共通依存性（Dependencies）

JWT認証、ユーザー権限チェック等、複数のルーターから使われる依存性を定義。
"""

from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Dict, Any
from datetime import datetime, timedelta, timezone
import jwt
import os

# JWT設定
JWT_SECRET = os.environ.get("JWT_SECRET")
if not JWT_SECRET:
    raise RuntimeError("JWT_SECRET environment variable is required")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_HOURS = 24

security = HTTPBearer()


def create_token(user_id: int, username: str, role: str) -> str:
    """JWTトークンを生成する"""
    payload = {
        "sub": str(user_id),
        "username": username,
        "role": role,
        "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRE_HOURS)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Dict[str, Any]:
    """
    JWTトークンから現在のユーザーを取得する（認証済みユーザー）

    Raises:
        HTTPException: トークンが無効または期限切れの場合
    """
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
    """
    管理者権限をチェックする（admin または ja_staff のみ許可）

    Raises:
        HTTPException: 管理者権限がない場合
    """
    if current_user["role"] not in ["admin", "ja_staff"]:
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user
