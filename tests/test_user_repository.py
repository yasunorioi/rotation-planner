"""
UserRepository のテスト
"""
import pytest
import hashlib
import sqlite3
from rotation_planner.common.db_access import UserRepository


# =============================================================================
# UR-01: create_user 正常登録 → lastrowid
# =============================================================================
def test_create_user_normal(test_db):
    """UR-01: 正常なユーザー作成が lastrowid を返すことを確認"""
    password_hash = hashlib.sha256('test_password'.encode()).hexdigest()

    user_data = {
        'username': 'test_user',
        'password_hash': password_hash,
        'display_name': 'テストユーザー',
        'email': 'test@example.com',
        'role': 'farmer',
        'org_id': 1
    }

    user_id = UserRepository.create_user(user_data)

    assert isinstance(user_id, int)
    assert user_id > 0

    # 作成されたユーザーを取得して確認
    user = UserRepository.get_user(user_id)
    assert user is not None
    assert user['username'] == 'test_user'
    assert user['display_name'] == 'テストユーザー'
    assert user['role'] == 'farmer'


# =============================================================================
# UR-02: create_user username重複 → IntegrityError
# =============================================================================
def test_create_user_duplicate_username(test_db, admin_state):
    """UR-02: username重複時に IntegrityError が発生することを確認"""
    # admin_state で admin ユーザーは既に存在している
    existing_username = admin_state['username']  # 'admin'

    password_hash = hashlib.sha256('another_password'.encode()).hexdigest()

    user_data = {
        'username': existing_username,  # 重複
        'password_hash': password_hash,
        'display_name': '重複ユーザー',
        'role': 'farmer',
        'org_id': 1
    }

    # DuplicateKeyError が発生することを確認（Phase 2でカスタム例外に変換）
    from rotation_planner.common.exceptions import DuplicateKeyError
    with pytest.raises(DuplicateKeyError):
        UserRepository.create_user(user_data)


# =============================================================================
# UR-03: get_user org_name JOIN確認 → org_nameフィールドあり
# =============================================================================
def test_get_user_with_org_name(test_db, admin_state):
    """UR-03: get_user が org_name を JOIN して返すことを確認"""
    user_id = admin_state['user_id']

    user = UserRepository.get_user(user_id)

    assert user is not None
    assert 'org_name' in user
    # admin は org_id=1 で組織名が設定されているはず（初期データ依存）
    # 組織名は init_db() で作成される organizations テーブルに依存
    # ここでは org_name フィールドが存在することを確認
    assert user['org_name'] is not None or user['org_name'] == ''


# =============================================================================
# UR-04: authenticate 正しいハッシュ → userデータ返却
# =============================================================================
def test_authenticate_correct_password(test_db, admin_state):
    """UR-04: 正しいパスワードハッシュで認証成功することを確認"""
    username = admin_state['username']  # 'admin'
    # admin_state のパスワードは 'admin123' → ハッシュ化
    password_hash = hashlib.sha256('admin123'.encode()).hexdigest()

    user = UserRepository.authenticate(username, password_hash)

    assert user is not None
    assert user['username'] == username
    assert user['is_active'] == 1


# =============================================================================
# UR-05: authenticate 誤ったハッシュ → None
# =============================================================================
def test_authenticate_incorrect_password(test_db, admin_state):
    """UR-05: 誤ったパスワードハッシュで認証失敗することを確認"""
    username = admin_state['username']  # 'admin'
    wrong_password_hash = hashlib.sha256('wrong_password'.encode()).hexdigest()

    user = UserRepository.authenticate(username, wrong_password_hash)

    assert user is None


def test_authenticate_nonexistent_user(test_db):
    """追加: 存在しないユーザー名で認証失敗することを確認"""
    password_hash = hashlib.sha256('any_password'.encode()).hexdigest()

    user = UserRepository.authenticate('nonexistent_user', password_hash)

    assert user is None
