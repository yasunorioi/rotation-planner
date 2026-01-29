"""
認証モジュール - Gradio標準認証 + ユーザーマスタJSON

使用方法:
    from rotation_planner.common.auth import authenticate, get_user_info, can_access_farmer

    # Gradio launchで使用
    demo.launch(auth=authenticate)

    # ユーザー情報取得
    user = get_user_info(request.username)

    # アクセス権限チェック
    if can_access_farmer(username, farmer_id):
        # データにアクセス
        pass
"""

import json
import hashlib
from pathlib import Path
from typing import List, Dict, Optional, Any
from datetime import datetime


# =============================================================================
# 設定
# =============================================================================

# ユーザーマスタファイル（rotation_planner_ui/data/users.json）
USERS_FILE = Path(__file__).parent.parent.parent / "data" / "users.json"

# ロール定義
ROLE_ADMIN = "admin"
ROLE_JA_STAFF = "ja_staff"
ROLE_FARMER = "farmer"

# 管理者ロール（全農家データにアクセス可能）
ADMIN_ROLES = {ROLE_ADMIN, ROLE_JA_STAFF}


# =============================================================================
# ユーザー管理
# =============================================================================

def load_users() -> List[Dict[str, Any]]:
    """
    ユーザー一覧を読み込み

    Returns:
        ユーザー情報のリスト
    """
    if not USERS_FILE.exists():
        return []

    with open(USERS_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    return data.get("users", [])


def save_users(users: List[Dict[str, Any]]) -> None:
    """
    ユーザー一覧を保存

    Args:
        users: ユーザー情報のリスト
    """
    USERS_FILE.parent.mkdir(parents=True, exist_ok=True)

    data = {
        "version": "1.0",
        "updated_at": datetime.now().isoformat(),
        "users": users
    }

    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def hash_password(password: str) -> str:
    """
    パスワードをSHA256でハッシュ化

    Args:
        password: 平文パスワード

    Returns:
        ハッシュ化されたパスワード
    """
    return hashlib.sha256(password.encode()).hexdigest()


# =============================================================================
# 認証
# =============================================================================

def authenticate(username: str, password: str) -> bool:
    """
    Gradio auth関数 - ユーザー認証

    Args:
        username: ユーザー名
        password: パスワード

    Returns:
        認証成功ならTrue
    """
    users = load_users()
    pw_hash = hash_password(password)

    for user in users:
        if user.get("username") == username and user.get("password_hash") == pw_hash:
            return True

    return False


def get_user_info(username: str) -> Optional[Dict[str, Any]]:
    """
    ユーザー情報を取得

    Args:
        username: ユーザー名

    Returns:
        ユーザー情報（見つからない場合はNone）
    """
    for user in load_users():
        if user.get("username") == username:
            # パスワードハッシュは返さない
            return {
                "username": user.get("username"),
                "role": user.get("role"),
                "farmer_id": user.get("farmer_id"),
                "display_name": user.get("display_name"),
            }

    return None


# =============================================================================
# アクセス制御
# =============================================================================

def can_access_farmer(username: str, farmer_id: str) -> bool:
    """
    特定の農家データへのアクセス権限をチェック

    Args:
        username: ユーザー名
        farmer_id: 農家ID

    Returns:
        アクセス可能ならTrue
    """
    user = get_user_info(username)
    if not user:
        return False

    role = user.get("role")

    # 管理者・JA職員は全農家にアクセス可能
    if role in ADMIN_ROLES:
        return True

    # 農家は自分のデータのみ
    return user.get("farmer_id") == farmer_id


def get_accessible_farmers(username: str) -> List[str]:
    """
    アクセス可能な農家IDのリストを取得

    Args:
        username: ユーザー名

    Returns:
        アクセス可能な農家IDのリスト
        管理者・JA職員の場合は ["*"]（全農家）
    """
    user = get_user_info(username)
    if not user:
        return []

    role = user.get("role")

    # 管理者・JA職員は全農家
    if role in ADMIN_ROLES:
        return ["*"]

    # 農家は自分のみ
    farmer_id = user.get("farmer_id")
    if farmer_id:
        return [farmer_id]

    return []


def is_admin_role(username: str) -> bool:
    """
    管理者ロール（admin または ja_staff）かどうかをチェック

    Args:
        username: ユーザー名

    Returns:
        管理者ロールならTrue
    """
    user = get_user_info(username)
    if not user:
        return False

    return user.get("role") in ADMIN_ROLES


def get_user_role(username: str) -> Optional[str]:
    """
    ユーザーのロールを取得

    Args:
        username: ユーザー名

    Returns:
        ロール（見つからない場合はNone）
    """
    user = get_user_info(username)
    if not user:
        return None

    return user.get("role")


# =============================================================================
# ユーザー管理（管理者用）
# =============================================================================

def add_user(
    username: str,
    password: str,
    role: str,
    farmer_id: Optional[str] = None,
    display_name: Optional[str] = None
) -> bool:
    """
    新規ユーザーを追加

    Args:
        username: ユーザー名
        password: パスワード
        role: ロール（admin, ja_staff, farmer）
        farmer_id: 農家ID（role=farmerの場合のみ）
        display_name: 表示名

    Returns:
        追加成功ならTrue
    """
    users = load_users()

    # 既存ユーザーチェック
    for user in users:
        if user.get("username") == username:
            return False

    new_user = {
        "username": username,
        "password_hash": hash_password(password),
        "role": role,
        "farmer_id": farmer_id,
        "display_name": display_name or username,
        "created_at": datetime.now().isoformat()
    }

    users.append(new_user)
    save_users(users)

    return True


def update_password(username: str, new_password: str) -> bool:
    """
    パスワードを更新

    Args:
        username: ユーザー名
        new_password: 新しいパスワード

    Returns:
        更新成功ならTrue
    """
    users = load_users()

    for user in users:
        if user.get("username") == username:
            user["password_hash"] = hash_password(new_password)
            save_users(users)
            return True

    return False


def delete_user(username: str) -> bool:
    """
    ユーザーを削除

    Args:
        username: ユーザー名

    Returns:
        削除成功ならTrue
    """
    users = load_users()
    original_count = len(users)

    users = [u for u in users if u.get("username") != username]

    if len(users) < original_count:
        save_users(users)
        return True

    return False
