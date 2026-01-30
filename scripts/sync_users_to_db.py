#!/usr/bin/env python3
"""
users.json のユーザーを DB の users テーブルに同期するスクリプト

Usage:
    python scripts/sync_users_to_db.py
"""

import sys
import json
from pathlib import Path

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from rotation_planner.common import get_db

USERS_FILE = project_root / "data" / "users.json"


def sync_users():
    """users.json のユーザーを DB に同期"""

    if not USERS_FILE.exists():
        print(f"Error: {USERS_FILE} not found")
        return

    with open(USERS_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    users = data.get("users", [])
    print(f"Found {len(users)} users in {USERS_FILE}")

    with get_db() as conn:
        for user in users:
            username = user.get("username")
            password_hash = user.get("password_hash", "")
            display_name = user.get("display_name", username)
            role = user.get("role", "farmer")

            # 既存ユーザーをチェック
            cursor = conn.execute(
                "SELECT id FROM users WHERE username = ?",
                (username,)
            )
            existing = cursor.fetchone()

            if existing:
                print(f"  [SKIP] {username} already exists (id={existing[0]})")
            else:
                # 新規追加
                cursor = conn.execute(
                    """
                    INSERT INTO users (username, password_hash, display_name, role)
                    VALUES (?, ?, ?, ?)
                    """,
                    (username, password_hash, display_name, role)
                )
                new_id = cursor.lastrowid
                print(f"  [ADD] {username} (id={new_id})")

        conn.commit()

    print("Done!")


if __name__ == "__main__":
    sync_users()
