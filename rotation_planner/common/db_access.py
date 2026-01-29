"""
DBアクセス層 - SQLiteデータベースへのCRUD操作モジュール

使用方法:
    from db_access import FieldRepository, PlanRepository, JAStaffRepository

    # ほ場操作
    fields = FieldRepository.get_fields(user_id=1)
    FieldRepository.create_field(user_id=1, data={...})

    # 輪作計画操作
    plans = PlanRepository.get_plans(user_id=1)
    PlanRepository.create_plan(user_id=1, data={...})

    # JA職員用
    all_fields = JAStaffRepository.get_all_fields(org_id=1)
"""

import sqlite3
import json
import os
from pathlib import Path
from typing import List, Dict, Optional, Any, Tuple
from datetime import datetime
from contextlib import contextmanager

# =============================================================================
# 設定
# =============================================================================

# rotation_planner_ui/data/ を参照（common/からの相対パス）
DB_DIR = Path(__file__).parent.parent.parent / "data"
DB_PATH = DB_DIR / "rotation_planner.db"
JSON_DATA_DIR = DB_DIR


# =============================================================================
# 接続管理
# =============================================================================

def get_connection() -> sqlite3.Connection:
    """
    DB接続を取得

    Returns:
        sqlite3.Connection: データベース接続
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # 辞書形式でアクセス可能
    conn.execute("PRAGMA foreign_keys = ON")  # 外部キー制約有効化
    return conn


@contextmanager
def get_db():
    """
    コンテキストマネージャでDB接続を管理

    Usage:
        with get_db() as conn:
            cursor = conn.execute(...)
    """
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


def row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    """sqlite3.Rowを辞書に変換"""
    return dict(row) if row else None


def rows_to_list(rows: List[sqlite3.Row]) -> List[Dict[str, Any]]:
    """sqlite3.Rowのリストを辞書のリストに変換"""
    return [dict(row) for row in rows]


# =============================================================================
# ほ場（Fields）リポジトリ
# =============================================================================

class FieldRepository:
    """ほ場データのCRUD操作"""

    @staticmethod
    def get_fields(user_id: int) -> List[Dict[str, Any]]:
        """
        ユーザーのほ場一覧を取得

        Args:
            user_id: ユーザーID

        Returns:
            ほ場データのリスト
        """
        with get_db() as conn:
            cursor = conn.execute("""
                SELECT id, field_code, district, name, area_ha, area_a,
                       beet_forbidden, coordinates_json, notes, created_at, updated_at
                FROM fields
                WHERE user_id = ?
                ORDER BY field_code
            """, (user_id,))
            return rows_to_list(cursor.fetchall())

    @staticmethod
    def get_field(field_id: int) -> Optional[Dict[str, Any]]:
        """
        ほ場詳細を取得

        Args:
            field_id: ほ場ID

        Returns:
            ほ場データ（見つからない場合はNone）
        """
        with get_db() as conn:
            cursor = conn.execute("""
                SELECT f.*, u.username as owner_username, u.display_name as owner_name
                FROM fields f
                JOIN users u ON f.user_id = u.id
                WHERE f.id = ?
            """, (field_id,))
            row = cursor.fetchone()
            return row_to_dict(row)

    @staticmethod
    def get_field_by_code(user_id: int, field_code: str) -> Optional[Dict[str, Any]]:
        """ほ場コードでほ場を取得"""
        with get_db() as conn:
            cursor = conn.execute("""
                SELECT * FROM fields WHERE user_id = ? AND field_code = ?
            """, (user_id, field_code))
            row = cursor.fetchone()
            return row_to_dict(row)

    @staticmethod
    def create_field(user_id: int, data: Dict[str, Any]) -> int:
        """
        ほ場を作成

        Args:
            user_id: ユーザーID
            data: ほ場データ
                - field_code: ほ場コード（必須）
                - district: 地区
                - name: ほ場名
                - area_ha: 面積（ha）（必須）
                - beet_forbidden: てんさい禁止フラグ
                - coordinates_json: 座標JSON
                - notes: 備考

        Returns:
            作成されたほ場のID
        """
        with get_db() as conn:
            cursor = conn.execute("""
                INSERT INTO fields (user_id, field_code, district, name, area_ha,
                                   beet_forbidden, coordinates_json, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                user_id,
                data['field_code'],
                data.get('district'),
                data.get('name'),
                data['area_ha'],
                data.get('beet_forbidden', 0),
                data.get('coordinates_json'),
                data.get('notes')
            ))
            return cursor.lastrowid

    @staticmethod
    def update_field(field_id: int, data: Dict[str, Any]) -> bool:
        """
        ほ場を更新

        Args:
            field_id: ほ場ID
            data: 更新データ

        Returns:
            更新成功ならTrue
        """
        with get_db() as conn:
            # 更新対象カラムを動的に構築
            updates = []
            values = []
            for key in ['field_code', 'district', 'name', 'area_ha',
                       'beet_forbidden', 'coordinates_json', 'notes']:
                if key in data:
                    updates.append(f"{key} = ?")
                    values.append(data[key])

            if not updates:
                return False

            updates.append("updated_at = CURRENT_TIMESTAMP")
            values.append(field_id)

            sql = f"UPDATE fields SET {', '.join(updates)} WHERE id = ?"
            cursor = conn.execute(sql, values)
            return cursor.rowcount > 0

    @staticmethod
    def delete_field(field_id: int) -> bool:
        """
        ほ場を削除

        Args:
            field_id: ほ場ID

        Returns:
            削除成功ならTrue
        """
        with get_db() as conn:
            cursor = conn.execute("DELETE FROM fields WHERE id = ?", (field_id,))
            return cursor.rowcount > 0

    @staticmethod
    def get_field_with_history(field_id: int) -> Optional[Dict[str, Any]]:
        """ほ場と作付履歴を取得"""
        with get_db() as conn:
            # ほ場情報
            cursor = conn.execute("SELECT * FROM fields WHERE id = ?", (field_id,))
            field = row_to_dict(cursor.fetchone())
            if not field:
                return None

            # 作付履歴
            cursor = conn.execute("""
                SELECT year, crop, is_inferred
                FROM crop_history
                WHERE field_id = ?
                ORDER BY year
            """, (field_id,))
            field['history'] = rows_to_list(cursor.fetchall())

            return field


# =============================================================================
# 作付履歴リポジトリ
# =============================================================================

class CropHistoryRepository:
    """作付履歴のCRUD操作"""

    @staticmethod
    def get_history(field_id: int) -> List[Dict[str, Any]]:
        """ほ場の作付履歴を取得"""
        with get_db() as conn:
            cursor = conn.execute("""
                SELECT * FROM crop_history
                WHERE field_id = ?
                ORDER BY year
            """, (field_id,))
            return rows_to_list(cursor.fetchall())

    @staticmethod
    def add_history(field_id: int, year: str, crop: str, is_inferred: bool = False) -> int:
        """作付履歴を追加"""
        with get_db() as conn:
            cursor = conn.execute("""
                INSERT OR REPLACE INTO crop_history (field_id, year, crop, is_inferred)
                VALUES (?, ?, ?, ?)
            """, (field_id, year, crop, 1 if is_inferred else 0))
            return cursor.lastrowid

    @staticmethod
    def bulk_add_history(field_id: int, history: Dict[str, str]) -> int:
        """作付履歴を一括追加（年: 作物の辞書）"""
        count = 0
        with get_db() as conn:
            for year, crop in history.items():
                conn.execute("""
                    INSERT OR REPLACE INTO crop_history (field_id, year, crop, is_inferred)
                    VALUES (?, ?, ?, 0)
                """, (field_id, year, crop))
                count += 1
        return count


# =============================================================================
# 輪作計画（Rotation Plans）リポジトリ
# =============================================================================

class PlanRepository:
    """輪作計画のCRUD操作"""

    @staticmethod
    def get_plans(user_id: int) -> List[Dict[str, Any]]:
        """
        ユーザーの輪作計画一覧を取得

        Args:
            user_id: ユーザーID

        Returns:
            計画データのリスト
        """
        with get_db() as conn:
            cursor = conn.execute("""
                SELECT id, name, start_year, end_year, created_at, updated_at
                FROM rotation_plans
                WHERE user_id = ?
                ORDER BY updated_at DESC
            """, (user_id,))
            return rows_to_list(cursor.fetchall())

    @staticmethod
    def get_plan(plan_id: int) -> Optional[Dict[str, Any]]:
        """
        輪作計画詳細を取得（詳細データ含む）

        Args:
            plan_id: 計画ID

        Returns:
            計画データ（見つからない場合はNone）
        """
        with get_db() as conn:
            # 計画メタデータ
            cursor = conn.execute("""
                SELECT * FROM rotation_plans WHERE id = ?
            """, (plan_id,))
            plan = row_to_dict(cursor.fetchone())
            if not plan:
                return None

            # 計画詳細（ほ場×年の作付）
            cursor = conn.execute("""
                SELECT pd.*, f.field_code, f.name as field_name, f.district
                FROM plan_details pd
                JOIN fields f ON pd.field_id = f.id
                WHERE pd.plan_id = ?
                ORDER BY f.field_code, pd.year
            """, (plan_id,))
            plan['details'] = rows_to_list(cursor.fetchall())

            # 制約をパース
            if plan.get('constraints_json'):
                plan['constraints'] = json.loads(plan['constraints_json'])

            return plan

    @staticmethod
    def create_plan(user_id: int, data: Dict[str, Any]) -> int:
        """
        輪作計画を作成

        Args:
            user_id: ユーザーID
            data: 計画データ
                - name: 計画名（必須）
                - start_year: 開始年（必須）
                - end_year: 終了年（必須）
                - constraints: 制約設定（dict）
                - details: 計画詳細リスト [{field_id, year, crop}, ...]

        Returns:
            作成された計画のID
        """
        with get_db() as conn:
            # 計画メタデータ
            constraints_json = json.dumps(data.get('constraints', {}), ensure_ascii=False)
            metadata_json = json.dumps(data.get('metadata', {}), ensure_ascii=False)

            cursor = conn.execute("""
                INSERT INTO rotation_plans (user_id, name, start_year, end_year,
                                           constraints_json, metadata_json)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                user_id,
                data['name'],
                data['start_year'],
                data['end_year'],
                constraints_json,
                metadata_json
            ))
            plan_id = cursor.lastrowid

            # 計画詳細
            for detail in data.get('details', []):
                conn.execute("""
                    INSERT INTO plan_details (plan_id, field_id, year, crop)
                    VALUES (?, ?, ?, ?)
                """, (plan_id, detail['field_id'], detail['year'], detail['crop']))

            return plan_id

    @staticmethod
    def update_plan(plan_id: int, data: Dict[str, Any]) -> bool:
        """
        輪作計画を更新

        Args:
            plan_id: 計画ID
            data: 更新データ

        Returns:
            更新成功ならTrue
        """
        with get_db() as conn:
            # メタデータ更新
            updates = []
            values = []
            for key in ['name', 'start_year', 'end_year']:
                if key in data:
                    updates.append(f"{key} = ?")
                    values.append(data[key])

            if 'constraints' in data:
                updates.append("constraints_json = ?")
                values.append(json.dumps(data['constraints'], ensure_ascii=False))

            if updates:
                updates.append("updated_at = CURRENT_TIMESTAMP")
                values.append(plan_id)
                sql = f"UPDATE rotation_plans SET {', '.join(updates)} WHERE id = ?"
                conn.execute(sql, values)

            # 詳細更新（全削除して再作成）
            if 'details' in data:
                conn.execute("DELETE FROM plan_details WHERE plan_id = ?", (plan_id,))
                for detail in data['details']:
                    conn.execute("""
                        INSERT INTO plan_details (plan_id, field_id, year, crop)
                        VALUES (?, ?, ?, ?)
                    """, (plan_id, detail['field_id'], detail['year'], detail['crop']))

            return True

    @staticmethod
    def delete_plan(plan_id: int) -> bool:
        """
        輪作計画を削除

        Args:
            plan_id: 計画ID

        Returns:
            削除成功ならTrue
        """
        with get_db() as conn:
            cursor = conn.execute("DELETE FROM rotation_plans WHERE id = ?", (plan_id,))
            return cursor.rowcount > 0


# =============================================================================
# JA職員用リポジトリ（組織内全データアクセス）
# =============================================================================

class JAStaffRepository:
    """JA職員用のデータアクセス（組織内全農家のデータ参照）"""

    @staticmethod
    def get_all_fields(org_id: int) -> List[Dict[str, Any]]:
        """
        組織内の全ほ場を取得

        Args:
            org_id: 組織ID

        Returns:
            ほ場データのリスト（農家情報付き）
        """
        with get_db() as conn:
            cursor = conn.execute("""
                SELECT f.*, u.username, u.display_name as farmer_name
                FROM fields f
                JOIN users u ON f.user_id = u.id
                WHERE u.org_id = ?
                ORDER BY u.display_name, f.field_code
            """, (org_id,))
            return rows_to_list(cursor.fetchall())

    @staticmethod
    def get_all_farmers(org_id: int) -> List[Dict[str, Any]]:
        """
        組織内の農家一覧を取得

        Args:
            org_id: 組織ID

        Returns:
            農家データのリスト（ほ場数付き）
        """
        with get_db() as conn:
            cursor = conn.execute("""
                SELECT u.id, u.username, u.display_name, u.email, u.created_at,
                       COUNT(f.id) as field_count,
                       COALESCE(SUM(f.area_ha), 0) as total_area_ha
                FROM users u
                LEFT JOIN fields f ON u.id = f.user_id
                WHERE u.org_id = ? AND u.role = 'farmer'
                GROUP BY u.id
                ORDER BY u.display_name
            """, (org_id,))
            return rows_to_list(cursor.fetchall())

    @staticmethod
    def get_aggregate_stats(org_id: int) -> Dict[str, Any]:
        """
        組織の集計データを取得

        Args:
            org_id: 組織ID

        Returns:
            集計データ
        """
        with get_db() as conn:
            stats = {}

            # 農家数
            cursor = conn.execute("""
                SELECT COUNT(*) as count FROM users
                WHERE org_id = ? AND role = 'farmer'
            """, (org_id,))
            stats['farmer_count'] = cursor.fetchone()['count']

            # ほ場数・総面積
            cursor = conn.execute("""
                SELECT COUNT(*) as count, COALESCE(SUM(area_ha), 0) as total_area
                FROM fields f
                JOIN users u ON f.user_id = u.id
                WHERE u.org_id = ?
            """, (org_id,))
            row = cursor.fetchone()
            stats['field_count'] = row['count']
            stats['total_area_ha'] = row['total_area']

            # 作物別面積（最新年）
            cursor = conn.execute("""
                SELECT ch.crop, SUM(f.area_ha) as area_ha, COUNT(*) as field_count
                FROM crop_history ch
                JOIN fields f ON ch.field_id = f.id
                JOIN users u ON f.user_id = u.id
                WHERE u.org_id = ?
                AND ch.year = (SELECT MAX(year) FROM crop_history)
                GROUP BY ch.crop
                ORDER BY area_ha DESC
            """, (org_id,))
            stats['crop_areas'] = rows_to_list(cursor.fetchall())

            return stats


# =============================================================================
# ユーザーリポジトリ
# =============================================================================

class UserRepository:
    """ユーザーのCRUD操作"""

    @staticmethod
    def get_user(user_id: int) -> Optional[Dict[str, Any]]:
        """ユーザー情報を取得"""
        with get_db() as conn:
            cursor = conn.execute("""
                SELECT u.*, o.name as org_name
                FROM users u
                LEFT JOIN organizations o ON u.org_id = o.id
                WHERE u.id = ?
            """, (user_id,))
            return row_to_dict(cursor.fetchone())

    @staticmethod
    def get_user_by_username(username: str) -> Optional[Dict[str, Any]]:
        """ユーザー名でユーザーを取得"""
        with get_db() as conn:
            cursor = conn.execute("""
                SELECT * FROM users WHERE username = ?
            """, (username,))
            return row_to_dict(cursor.fetchone())

    @staticmethod
    def create_user(data: Dict[str, Any]) -> int:
        """ユーザーを作成"""
        with get_db() as conn:
            cursor = conn.execute("""
                INSERT INTO users (username, password_hash, display_name, email, role, org_id)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                data['username'],
                data['password_hash'],
                data['display_name'],
                data.get('email'),
                data.get('role', 'farmer'),
                data.get('org_id')
            ))
            return cursor.lastrowid

    @staticmethod
    def authenticate(username: str, password_hash: str) -> Optional[Dict[str, Any]]:
        """認証（パスワードハッシュで照合）"""
        with get_db() as conn:
            cursor = conn.execute("""
                SELECT * FROM users
                WHERE username = ? AND password_hash = ? AND is_active = 1
            """, (username, password_hash))
            return row_to_dict(cursor.fetchone())


# =============================================================================
# 防除マスタリポジトリ
# =============================================================================

class PesticideMasterRepository:
    """防除マスタのCRUD操作"""

    @staticmethod
    def get_by_crop(crop: str, org_id: int = None) -> List[Dict[str, Any]]:
        """作物の防除データを取得"""
        with get_db() as conn:
            cursor = conn.execute("""
                SELECT * FROM pesticide_masters
                WHERE crop = ? AND (org_id IS NULL OR org_id = ?)
                ORDER BY month, period
            """, (crop, org_id))
            return rows_to_list(cursor.fetchall())

    @staticmethod
    def get_all(org_id: int = None) -> List[Dict[str, Any]]:
        """全防除マスタを取得"""
        with get_db() as conn:
            cursor = conn.execute("""
                SELECT * FROM pesticide_masters
                WHERE org_id IS NULL OR org_id = ?
                ORDER BY crop, month, period
            """, (org_id,))
            return rows_to_list(cursor.fetchall())


# =============================================================================
# 移行ユーティリティ
# =============================================================================

class MigrationUtils:
    """既存JSONデータからの移行ユーティリティ"""

    @staticmethod
    def migrate_json_fields(user_id: int, json_path: Path = None) -> Tuple[int, List[str]]:
        """
        fields.jsonからほ場データを移行

        Args:
            user_id: 移行先ユーザーID
            json_path: JSONファイルパス（デフォルト: data/fields.json）

        Returns:
            (移行件数, エラーリスト)
        """
        if json_path is None:
            json_path = JSON_DATA_DIR / "fields.json"

        if not json_path.exists():
            return 0, ["ファイルが見つかりません: " + str(json_path)]

        errors = []
        count = 0

        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        for field in data.get('fields', []):
            try:
                # 既存チェック
                existing = FieldRepository.get_field_by_code(user_id, field['field_id'])
                if existing:
                    errors.append(f"スキップ（既存）: {field['field_id']}")
                    continue

                FieldRepository.create_field(user_id, {
                    'field_code': field['field_id'],
                    'district': field.get('district'),
                    'name': field.get('name'),
                    'area_ha': field.get('area_ha', field.get('area_a', 0) / 100),
                    'beet_forbidden': 1 if field.get('beet_forbidden') else 0,
                    'coordinates_json': json.dumps(field.get('coordinates')) if field.get('coordinates') else None
                })
                count += 1
            except Exception as e:
                errors.append(f"エラー ({field.get('field_id', '?')}): {str(e)}")

        return count, errors

    @staticmethod
    def migrate_json_plans(user_id: int, plans_dir: Path = None) -> Tuple[int, List[str]]:
        """
        rotation_plans/ディレクトリから輪作計画を移行

        Args:
            user_id: 移行先ユーザーID
            plans_dir: 計画ディレクトリパス

        Returns:
            (移行件数, エラーリスト)
        """
        if plans_dir is None:
            plans_dir = JSON_DATA_DIR / "rotation_plans"

        if not plans_dir.exists():
            return 0, ["ディレクトリが見つかりません: " + str(plans_dir)]

        errors = []
        count = 0

        for plan_file in plans_dir.glob("*.json"):
            try:
                with open(plan_file, 'r', encoding='utf-8') as f:
                    plan_data = json.load(f)

                # 計画作成
                PlanRepository.create_plan(user_id, {
                    'name': plan_data.get('name', plan_file.stem),
                    'start_year': plan_data.get('start_year', 'R5'),
                    'end_year': plan_data.get('end_year', 'R10'),
                    'constraints': plan_data.get('constraints', {}),
                    'metadata': plan_data.get('metadata', {}),
                    'details': []  # 詳細は別途移行が必要
                })
                count += 1
            except Exception as e:
                errors.append(f"エラー ({plan_file.name}): {str(e)}")

        return count, errors

    @staticmethod
    def migrate_pesticide_master(csv_path: Path = None, org_id: int = None) -> Tuple[int, List[str]]:
        """
        pesticide_master.csvから防除マスタを移行

        Args:
            csv_path: CSVファイルパス
            org_id: 組織ID（NULLなら共通マスタ）

        Returns:
            (移行件数, エラーリスト)
        """
        import csv

        if csv_path is None:
            csv_path = Path(__file__).parent / "pesticide_master.csv"

        if not csv_path.exists():
            return 0, ["ファイルが見つかりません: " + str(csv_path)]

        errors = []
        count = 0

        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            with get_db() as conn:
                for row in reader:
                    try:
                        conn.execute("""
                            INSERT INTO pesticide_masters
                            (org_id, crop, month, period, target, pesticide_name,
                             dilution_rate, amount_per_10a, unit, days_before_harvest, notes)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            org_id,
                            row.get('crop'),
                            int(row['month']) if row.get('month') else None,
                            row.get('period'),
                            row.get('target'),
                            row.get('pesticide_name'),
                            row.get('dilution_rate'),
                            float(row['amount_per_10a']) if row.get('amount_per_10a') else None,
                            row.get('unit'),
                            row.get('days_before_harvest'),
                            row.get('notes')
                        ))
                        count += 1
                    except Exception as e:
                        errors.append(f"エラー: {str(e)}")

        return count, errors


# =============================================================================
# 動作確認用
# =============================================================================

if __name__ == "__main__":
    print("=== DB接続テスト ===")
    with get_db() as conn:
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        print(f"テーブル数: {len(tables)}")
        for t in tables:
            print(f"  - {t['name']}")

    print("\n=== リポジトリテスト ===")
    # 組織確認
    with get_db() as conn:
        cursor = conn.execute("SELECT * FROM organizations")
        orgs = cursor.fetchall()
        print(f"組織数: {len(orgs)}")
        for o in orgs:
            print(f"  - {o['name']} ({o['type']})")
