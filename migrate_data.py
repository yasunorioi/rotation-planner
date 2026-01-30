#!/usr/bin/env python3
"""
データ移行スクリプト
既存JSONデータをSQLiteに移行する
"""

import json
import sys
from pathlib import Path
from datetime import datetime

# プロジェクトルートをパスに追加
sys.path.insert(0, str(Path(__file__).parent))

from rotation_planner.common import (
    get_db,
    UserRepository,
    FieldRepository,
    MigrationUtils,
)


def create_organization(name: str = "デモ組織", org_type: str = "JA") -> int:
    """組織を作成"""
    with get_db() as conn:
        # 既存チェック
        cursor = conn.execute("SELECT id FROM organizations WHERE name = ?", (name,))
        row = cursor.fetchone()
        if row:
            print(f"組織 '{name}' は既に存在: ID={row[0]}")
            return row[0]

        cursor = conn.execute("""
            INSERT INTO organizations (name, type, created_at)
            VALUES (?, ?, ?)
        """, (name, org_type, datetime.now().isoformat()))
        org_id = cursor.lastrowid
        print(f"組織作成: '{name}' (ID={org_id})")
        return org_id


def migrate_users_from_json(json_path: Path, org_id: int) -> dict:
    """
    users.json からユーザーを移行

    Returns:
        dict: username -> user_id のマッピング
    """
    if not json_path.exists():
        print(f"警告: {json_path} が見つかりません")
        return {}

    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    user_map = {}

    for user in data.get('users', []):
        username = user['username']

        # 既存チェック
        existing = UserRepository.get_user_by_username(username)
        if existing:
            print(f"スキップ（既存）: {username} (ID={existing['id']})")
            user_map[username] = existing['id']
            continue

        # ユーザー作成
        user_id = UserRepository.create_user({
            'username': username,
            'password_hash': user['password_hash'],
            'display_name': user.get('display_name', username),
            'email': user.get('email'),
            'role': user.get('role', 'farmer'),
            'org_id': org_id
        })
        print(f"ユーザー作成: {username} (ID={user_id})")
        user_map[username] = user_id

    return user_map


def run_migration():
    """メイン移行処理"""
    print("=" * 60)
    print("データ移行開始")
    print("=" * 60)

    data_dir = Path(__file__).parent / "data"

    # 1. 組織作成
    print("\n[1] 組織作成")
    org_id = create_organization("デモ組織")

    # 2. ユーザー移行
    print("\n[2] ユーザー移行")
    users_json = data_dir / "users.json"
    user_map = migrate_users_from_json(users_json, org_id)

    if not user_map:
        print("エラー: ユーザーが作成されませんでした")
        return False

    # 3. デモ農家のuser_idを取得
    farmer_demo_id = user_map.get('farmer_demo')
    if not farmer_demo_id:
        print("エラー: farmer_demo ユーザーが見つかりません")
        return False

    print(f"\nfarmer_demo の user_id: {farmer_demo_id}")

    # 4. ほ場データ移行
    print("\n[3] ほ場データ移行")
    field_count, field_errors = MigrationUtils.migrate_json_fields(farmer_demo_id)
    print(f"移行件数: {field_count}")
    if field_errors:
        for err in field_errors:
            print(f"  - {err}")

    # 5. 輪作計画移行
    print("\n[4] 輪作計画移行")
    plan_count, plan_errors = MigrationUtils.migrate_json_plans(farmer_demo_id)
    print(f"移行件数: {plan_count}")
    if plan_errors:
        for err in plan_errors:
            print(f"  - {err}")

    # 6. 結果確認
    print("\n" + "=" * 60)
    print("移行結果確認")
    print("=" * 60)

    with get_db() as conn:
        # ユーザー数
        cursor = conn.execute("SELECT COUNT(*) FROM users")
        print(f"users テーブル: {cursor.fetchone()[0]} 件")

        # ほ場数
        cursor = conn.execute("SELECT COUNT(*) FROM fields")
        print(f"fields テーブル: {cursor.fetchone()[0]} 件")

        # 計画数
        cursor = conn.execute("SELECT COUNT(*) FROM rotation_plans")
        print(f"rotation_plans テーブル: {cursor.fetchone()[0]} 件")

        # farmer_demo のデータ確認
        print(f"\n--- farmer_demo (user_id={farmer_demo_id}) のデータ ---")
        cursor = conn.execute("""
            SELECT field_code, district, name, area_ha
            FROM fields WHERE user_id = ?
        """, (farmer_demo_id,))
        for row in cursor:
            print(f"  ほ場: {row[0]} | {row[1]} | {row[2]} | {row[3]}ha")

        cursor = conn.execute("""
            SELECT name, start_year, end_year
            FROM rotation_plans WHERE user_id = ?
        """, (farmer_demo_id,))
        for row in cursor:
            print(f"  計画: {row[0]} ({row[1]}〜{row[2]})")

    print("\n" + "=" * 60)
    print("移行完了")
    print("=" * 60)

    return True


if __name__ == "__main__":
    success = run_migration()
    sys.exit(0 if success else 1)
