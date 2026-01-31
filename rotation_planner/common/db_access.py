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
    def get_all_history_for_user(user_id: int) -> List[Dict[str, Any]]:
        """
        ユーザーの全ほ場の履歴を取得（マトリックス表示用）

        Args:
            user_id: ユーザーID

        Returns:
            履歴データのリスト。各要素は:
            - field_id: ほ場ID（DB主キー）
            - field_code: ほ場コード（表示用）
            - field_name: ほ場名
            - year: 年度（R7, R8など）
            - crop: 作物名
            - is_inferred: 推論フラグ（1なら推論で補完）
        """
        with get_db() as conn:
            cursor = conn.execute("""
                SELECT
                    ch.field_id,
                    f.field_code,
                    f.name as field_name,
                    ch.year,
                    ch.crop,
                    ch.is_inferred
                FROM crop_history ch
                INNER JOIN fields f ON f.id = ch.field_id
                WHERE f.user_id = ?
                ORDER BY f.field_code, ch.year
            """, (user_id,))
            return rows_to_list(cursor.fetchall())

    @staticmethod
    def delete_history(field_id: int, year: str) -> bool:
        """
        特定ほ場・年度の履歴を削除

        Args:
            field_id: ほ場ID
            year: 年度（R7, R8など）

        Returns:
            削除成功ならTrue
        """
        with get_db() as conn:
            cursor = conn.execute("""
                DELETE FROM crop_history
                WHERE field_id = ? AND year = ?
            """, (field_id, year))
            return cursor.rowcount > 0

    @staticmethod
    def bulk_update_history(updates: List[Dict[str, Any]]) -> int:
        """
        複数レコードの一括更新（トランザクション内で実行）

        Args:
            updates: 更新データのリスト。各要素は:
                - field_id: ほ場ID
                - year: 年度
                - crop: 作物名（空文字の場合は削除）

        Returns:
            更新・挿入された件数
        """
        count = 0
        with get_db() as conn:
            for update in updates:
                field_id = update.get('field_id')
                year = update.get('year')
                crop = update.get('crop', '').strip()

                if not field_id or not year:
                    continue

                if not crop:
                    # 空の場合は削除
                    conn.execute("""
                        DELETE FROM crop_history
                        WHERE field_id = ? AND year = ?
                    """, (field_id, year))
                else:
                    # INSERT OR REPLACE で追加/更新
                    conn.execute("""
                        INSERT OR REPLACE INTO crop_history (field_id, year, crop, is_inferred)
                        VALUES (?, ?, ?, 0)
                    """, (field_id, year, crop))
                count += 1
        return count

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

    @staticmethod
    def get_by_id(master_id: int) -> Optional[Dict[str, Any]]:
        """IDで防除マスタを取得"""
        with get_db() as conn:
            cursor = conn.execute(
                "SELECT * FROM pesticide_masters WHERE id = ?",
                (master_id,)
            )
            return row_to_dict(cursor.fetchone())

    @staticmethod
    def create(data: Dict[str, Any]) -> int:
        """防除マスタを作成"""
        with get_db() as conn:
            cursor = conn.execute("""
                INSERT INTO pesticide_masters
                (org_id, crop, month, period, target, pesticide_name,
                 dilution_rate, amount_per_10a, unit, days_before_harvest, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                data.get('org_id'),
                data.get('crop'),
                data.get('month'),
                data.get('period'),
                data.get('target'),
                data.get('pesticide_name'),
                data.get('dilution_rate'),
                data.get('amount_per_10a'),
                data.get('unit'),
                data.get('days_before_harvest'),
                data.get('notes'),
            ))
            return cursor.lastrowid

    @staticmethod
    def update(master_id: int, data: Dict[str, Any]) -> bool:
        """防除マスタを更新"""
        with get_db() as conn:
            cursor = conn.execute("""
                UPDATE pesticide_masters SET
                    crop = ?,
                    month = ?,
                    period = ?,
                    target = ?,
                    pesticide_name = ?,
                    dilution_rate = ?,
                    amount_per_10a = ?,
                    unit = ?,
                    days_before_harvest = ?,
                    notes = ?
                WHERE id = ?
            """, (
                data.get('crop'),
                data.get('month'),
                data.get('period'),
                data.get('target'),
                data.get('pesticide_name'),
                data.get('dilution_rate'),
                data.get('amount_per_10a'),
                data.get('unit'),
                data.get('days_before_harvest'),
                data.get('notes'),
                master_id,
            ))
            return cursor.rowcount > 0

    @staticmethod
    def delete(master_id: int) -> bool:
        """防除マスタを削除"""
        with get_db() as conn:
            cursor = conn.execute(
                "DELETE FROM pesticide_masters WHERE id = ?",
                (master_id,)
            )
            return cursor.rowcount > 0

    @staticmethod
    def bulk_import(records: List[Dict[str, Any]], org_id: int = None) -> int:
        """CSVからの一括インポート"""
        count = 0
        with get_db() as conn:
            for record in records:
                record['org_id'] = org_id
                conn.execute("""
                    INSERT INTO pesticide_masters
                    (org_id, crop, month, period, target, pesticide_name,
                     dilution_rate, amount_per_10a, unit, days_before_harvest, notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    record.get('org_id'),
                    record.get('crop'),
                    record.get('month'),
                    record.get('period'),
                    record.get('target'),
                    record.get('pesticide_name'),
                    record.get('dilution_rate'),
                    record.get('amount_per_10a'),
                    record.get('unit'),
                    record.get('days_before_harvest'),
                    record.get('notes'),
                ))
                count += 1
        return count

    @staticmethod
    def delete_all(org_id: int = None) -> int:
        """全レコード削除（インポート前のクリア用）"""
        with get_db() as conn:
            if org_id is None:
                cursor = conn.execute("DELETE FROM pesticide_masters WHERE org_id IS NULL")
            else:
                cursor = conn.execute(
                    "DELETE FROM pesticide_masters WHERE org_id = ?",
                    (org_id,)
                )
            return cursor.rowcount


# =============================================================================
# 作物マスタリポジトリ
# =============================================================================

class CropMasterRepository:
    """作物マスタのCRUD操作（JA管理）"""

    @staticmethod
    def get_all(active_only: bool = True) -> List[Dict[str, Any]]:
        """全作物を取得"""
        with get_db() as conn:
            if active_only:
                cursor = conn.execute("""
                    SELECT * FROM crop_master
                    WHERE is_active = 1
                    ORDER BY display_order, name
                """)
            else:
                cursor = conn.execute("""
                    SELECT * FROM crop_master
                    ORDER BY display_order, name
                """)
            return rows_to_list(cursor.fetchall())

    @staticmethod
    def get_by_id(crop_id: int) -> Optional[Dict[str, Any]]:
        """IDで作物を取得"""
        with get_db() as conn:
            cursor = conn.execute(
                "SELECT * FROM crop_master WHERE id = ?", (crop_id,)
            )
            return row_to_dict(cursor.fetchone())

    @staticmethod
    def get_by_name(name: str) -> Optional[Dict[str, Any]]:
        """名前で作物を取得"""
        with get_db() as conn:
            cursor = conn.execute(
                "SELECT * FROM crop_master WHERE name = ?", (name,)
            )
            return row_to_dict(cursor.fetchone())

    @staticmethod
    def create(name: str, display_order: int = 0) -> int:
        """作物を追加"""
        with get_db() as conn:
            cursor = conn.execute("""
                INSERT INTO crop_master (name, display_order)
                VALUES (?, ?)
            """, (name, display_order))
            conn.commit()
            return cursor.lastrowid

    @staticmethod
    def update(crop_id: int, data: Dict[str, Any]) -> bool:
        """作物を更新"""
        with get_db() as conn:
            fields = []
            values = []
            for key in ['name', 'display_order', 'is_active']:
                if key in data:
                    fields.append(f"{key} = ?")
                    values.append(data[key])

            if not fields:
                return False

            values.append(crop_id)
            conn.execute(f"""
                UPDATE crop_master SET {', '.join(fields)}
                WHERE id = ?
            """, values)
            conn.commit()
            return True

    @staticmethod
    def delete(crop_id: int) -> bool:
        """作物を削除（非アクティブ化）"""
        with get_db() as conn:
            conn.execute(
                "UPDATE crop_master SET is_active = 0 WHERE id = ?",
                (crop_id,)
            )
            conn.commit()
            return True


# =============================================================================
# ユーザー作物リポジトリ
# =============================================================================

class UserCropRepository:
    """
    ユーザーが選択した作物のCRUD操作

    user_cropsテーブル構造:
        - id: 主キー
        - user_id: ユーザーID
        - parent_crop_id: 親作物ID（crop_masterへの参照、防除連携用）
        - custom_name: カスタム名（NULL=マスタ名をそのまま使用）
        - created_at: 作成日時
    """

    @staticmethod
    def get_user_crops(user_id: int) -> List[Dict[str, Any]]:
        """
        ユーザーの選択した作物を取得

        Returns:
            作物リスト。各要素は:
            - id: user_crops.id
            - parent_crop_id: crop_master.id
            - parent_name: crop_master.name（防除連携用）
            - name: 表示名（custom_nameがあればそれ、なければparent_name）
            - custom_name: カスタム名（NULLの場合あり）
        """
        with get_db() as conn:
            cursor = conn.execute("""
                SELECT
                    uc.id,
                    uc.parent_crop_id,
                    cm.name as parent_name,
                    uc.custom_name,
                    COALESCE(uc.custom_name, cm.name) as name
                FROM user_crops uc
                INNER JOIN crop_master cm ON cm.id = uc.parent_crop_id
                WHERE uc.user_id = ? AND cm.is_active = 1
                ORDER BY cm.display_order, name
            """, (user_id,))
            return rows_to_list(cursor.fetchall())

    @staticmethod
    def get_user_crop_ids(user_id: int) -> List[int]:
        """ユーザーの選択した親作物IDリストを取得（重複なし）"""
        with get_db() as conn:
            cursor = conn.execute("""
                SELECT DISTINCT parent_crop_id FROM user_crops
                WHERE user_id = ?
            """, (user_id,))
            return [row[0] for row in cursor.fetchall()]

    @staticmethod
    def set_user_crops(user_id: int, crop_ids: List[int]) -> bool:
        """
        ユーザーの作物選択を設定（マスタからの選択、カスタム名なし）
        既存のカスタム名なしエントリのみ削除して再登録
        """
        with get_db() as conn:
            # カスタム名なしのエントリを削除
            conn.execute("""
                DELETE FROM user_crops
                WHERE user_id = ? AND custom_name IS NULL
            """, (user_id,))

            # 新規登録
            for crop_id in crop_ids:
                conn.execute("""
                    INSERT OR IGNORE INTO user_crops (user_id, parent_crop_id, custom_name)
                    VALUES (?, ?, NULL)
                """, (user_id, crop_id))

            conn.commit()
            return True

    @staticmethod
    def add_user_crop(user_id: int, parent_crop_id: int, custom_name: str = None) -> int:
        """
        ユーザーに作物を追加

        Args:
            user_id: ユーザーID
            parent_crop_id: 親作物ID（crop_master.id）
            custom_name: カスタム名（例: "ブロッコリー（2作目）"）

        Returns:
            新規作成されたuser_crops.id
        """
        with get_db() as conn:
            cursor = conn.execute("""
                INSERT INTO user_crops (user_id, parent_crop_id, custom_name)
                VALUES (?, ?, ?)
            """, (user_id, parent_crop_id, custom_name))
            conn.commit()
            return cursor.lastrowid

    @staticmethod
    def remove_user_crop(user_id: int, user_crop_id: int) -> bool:
        """ユーザーから作物を削除（user_crops.idで指定）"""
        with get_db() as conn:
            conn.execute("""
                DELETE FROM user_crops
                WHERE user_id = ? AND id = ?
            """, (user_id, user_crop_id))
            conn.commit()
            return True

    @staticmethod
    def remove_user_crop_by_parent(user_id: int, parent_crop_id: int, custom_name: str = None) -> bool:
        """ユーザーから作物を削除（parent_crop_id + custom_nameで指定）"""
        with get_db() as conn:
            if custom_name:
                conn.execute("""
                    DELETE FROM user_crops
                    WHERE user_id = ? AND parent_crop_id = ? AND custom_name = ?
                """, (user_id, parent_crop_id, custom_name))
            else:
                conn.execute("""
                    DELETE FROM user_crops
                    WHERE user_id = ? AND parent_crop_id = ? AND custom_name IS NULL
                """, (user_id, parent_crop_id))
            conn.commit()
            return True

    @staticmethod
    def get_parent_crop_id_by_name(user_id: int, crop_name: str) -> Optional[int]:
        """
        作物名から親作物IDを取得（防除連携用）

        Args:
            user_id: ユーザーID
            crop_name: 作物名（カスタム名 or マスタ名）

        Returns:
            parent_crop_id（見つからない場合はNone）
        """
        with get_db() as conn:
            # まずカスタム名で検索
            cursor = conn.execute("""
                SELECT parent_crop_id FROM user_crops
                WHERE user_id = ? AND custom_name = ?
            """, (user_id, crop_name))
            row = cursor.fetchone()
            if row:
                return row[0]

            # 次にマスタ名で検索
            cursor = conn.execute("""
                SELECT uc.parent_crop_id FROM user_crops uc
                INNER JOIN crop_master cm ON cm.id = uc.parent_crop_id
                WHERE uc.user_id = ? AND cm.name = ? AND uc.custom_name IS NULL
            """, (user_id, crop_name))
            row = cursor.fetchone()
            if row:
                return row[0]

            return None


# =============================================================================
# 農薬発注リポジトリ
# =============================================================================

class PesticideOrderRepository:
    """農薬発注リストのCRUD操作"""

    @staticmethod
    def get_orders(user_id: int) -> List[Dict[str, Any]]:
        """
        ユーザーの発注リスト一覧を取得

        Args:
            user_id: ユーザーID

        Returns:
            発注リストのリスト（id, name, target_year, status, created_at, updated_at）
        """
        with get_db() as conn:
            cursor = conn.execute("""
                SELECT id, name, target_year, status, created_at, updated_at
                FROM pesticide_orders
                WHERE user_id = ?
                ORDER BY updated_at DESC
            """, (user_id,))
            return rows_to_list(cursor.fetchall())

    @staticmethod
    def get_order(order_id: int) -> Optional[Dict[str, Any]]:
        """
        発注リスト詳細を取得（order_data_jsonをdictに展開）

        Args:
            order_id: 発注ID

        Returns:
            発注リスト詳細（見つからない場合はNone）
        """
        with get_db() as conn:
            cursor = conn.execute("""
                SELECT * FROM pesticide_orders WHERE id = ?
            """, (order_id,))
            order = row_to_dict(cursor.fetchone())
            if not order:
                return None

            # order_data_json をパース
            if order.get('order_data_json'):
                order['order_data'] = json.loads(order['order_data_json'])
            else:
                order['order_data'] = {}

            return order

    @staticmethod
    def create_order(user_id: int, data: Dict[str, Any]) -> int:
        """
        発注リストを作成

        Args:
            user_id: ユーザーID
            data: 発注データ
                - name: 発注リスト名（必須）
                - target_year: 対象年（必須）
                - rotation_plan_id: 輪作計画ID（任意）
                - area_unit: 面積単位（デフォルト: 'ha'）
                - order_data: 発注内容（dict、JSON化して保存）

        Returns:
            作成された発注リストのID
        """
        with get_db() as conn:
            order_data_json = json.dumps(data.get('order_data', {}), ensure_ascii=False)

            cursor = conn.execute("""
                INSERT INTO pesticide_orders
                (user_id, name, rotation_plan_id, target_year, area_unit, order_data_json, status)
                VALUES (?, ?, ?, ?, ?, ?, 'draft')
            """, (
                user_id,
                data['name'],
                data.get('rotation_plan_id'),
                data['target_year'],
                data.get('area_unit', 'ha'),
                order_data_json
            ))
            conn.commit()
            return cursor.lastrowid

    @staticmethod
    def update_order(order_id: int, data: Dict[str, Any]) -> bool:
        """
        発注リストを更新

        Args:
            order_id: 発注ID
            data: 更新データ（name, target_year, area_unit, order_data, status等）

        Returns:
            更新成功ならTrue
        """
        with get_db() as conn:
            updates = []
            values = []

            if 'name' in data:
                updates.append("name = ?")
                values.append(data['name'])

            if 'target_year' in data:
                updates.append("target_year = ?")
                values.append(data['target_year'])

            if 'area_unit' in data:
                updates.append("area_unit = ?")
                values.append(data['area_unit'])

            if 'order_data' in data:
                updates.append("order_data_json = ?")
                values.append(json.dumps(data['order_data'], ensure_ascii=False))

            if 'status' in data:
                updates.append("status = ?")
                values.append(data['status'])

            if not updates:
                return False

            updates.append("updated_at = CURRENT_TIMESTAMP")
            values.append(order_id)

            conn.execute(f"""
                UPDATE pesticide_orders
                SET {', '.join(updates)}
                WHERE id = ?
            """, tuple(values))
            conn.commit()
            return True

    @staticmethod
    def delete_order(order_id: int) -> bool:
        """
        発注リストを削除

        Args:
            order_id: 発注ID

        Returns:
            削除成功ならTrue
        """
        with get_db() as conn:
            cursor = conn.execute("""
                DELETE FROM pesticide_orders WHERE id = ?
            """, (order_id,))
            conn.commit()
            return cursor.rowcount > 0


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
# PesticideRegistryRepository - 農薬登録情報
# =============================================================================

class PesticideRegistryRepository:
    """農薬登録情報（FAMIC登録基本部）のリポジトリ"""

    @staticmethod
    def get_by_id(pesticide_id: int) -> Optional[Dict[str, Any]]:
        """IDで農薬を取得"""
        with get_db() as conn:
            cursor = conn.execute(
                "SELECT * FROM pesticide_registry WHERE id = ?",
                (pesticide_id,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    @staticmethod
    def get_by_name(name: str) -> Optional[Dict[str, Any]]:
        """農薬名で取得（完全一致）"""
        with get_db() as conn:
            cursor = conn.execute(
                "SELECT * FROM pesticide_registry WHERE name = ?",
                (name,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    @staticmethod
    def search(keyword: str, limit: int = 50) -> List[Dict[str, Any]]:
        """農薬名で部分一致検索"""
        with get_db() as conn:
            cursor = conn.execute(
                "SELECT * FROM pesticide_registry WHERE name LIKE ? ORDER BY name LIMIT ?",
                (f"%{keyword}%", limit)
            )
            return [dict(row) for row in cursor.fetchall()]

    @staticmethod
    def get_by_registration_number(reg_no: str) -> Optional[Dict[str, Any]]:
        """登録番号で取得"""
        with get_db() as conn:
            cursor = conn.execute(
                "SELECT * FROM pesticide_registry WHERE registration_number = ?",
                (reg_no,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    @staticmethod
    def get_all(limit: int = 1000) -> List[Dict[str, Any]]:
        """全件取得（制限付き）"""
        with get_db() as conn:
            cursor = conn.execute(
                "SELECT * FROM pesticide_registry ORDER BY name LIMIT ?",
                (limit,)
            )
            return [dict(row) for row in cursor.fetchall()]


# =============================================================================
# PesticideUsageRepository - 農薬適用情報
# =============================================================================

class PesticideUsageRepository:
    """農薬適用情報（FAMIC登録適用部）のリポジトリ"""

    @staticmethod
    def get_by_pesticide_id(pesticide_id: int) -> List[Dict[str, Any]]:
        """農薬IDで適用情報を取得"""
        with get_db() as conn:
            cursor = conn.execute(
                "SELECT * FROM pesticide_usage WHERE pesticide_id = ? ORDER BY crop",
                (pesticide_id,)
            )
            return [dict(row) for row in cursor.fetchall()]

    @staticmethod
    def get_by_crop(crop: str) -> List[Dict[str, Any]]:
        """作物名で適用情報を取得"""
        with get_db() as conn:
            cursor = conn.execute(
                """
                SELECT u.*, r.name as pesticide_name, r.category, r.formulation
                FROM pesticide_usage u
                JOIN pesticide_registry r ON u.pesticide_id = r.id
                WHERE u.crop = ?
                ORDER BY r.name
                """,
                (crop,)
            )
            return [dict(row) for row in cursor.fetchall()]

    @staticmethod
    def search_by_crop(keyword: str, limit: int = 100) -> List[Dict[str, Any]]:
        """作物名で部分一致検索"""
        with get_db() as conn:
            cursor = conn.execute(
                """
                SELECT u.*, r.name as pesticide_name, r.category
                FROM pesticide_usage u
                JOIN pesticide_registry r ON u.pesticide_id = r.id
                WHERE u.crop LIKE ?
                ORDER BY u.crop, r.name
                LIMIT ?
                """,
                (f"%{keyword}%", limit)
            )
            return [dict(row) for row in cursor.fetchall()]

    @staticmethod
    def get_for_pesticide_and_crop(pesticide_id: int, crop: str) -> List[Dict[str, Any]]:
        """特定農薬×作物の適用情報を取得"""
        with get_db() as conn:
            cursor = conn.execute(
                "SELECT * FROM pesticide_usage WHERE pesticide_id = ? AND crop = ?",
                (pesticide_id, crop)
            )
            return [dict(row) for row in cursor.fetchall()]


# =============================================================================
# PesticideRecordRepository - 防除記録
# =============================================================================

class PesticideRecordRepository:
    """防除記録のリポジトリ"""

    @staticmethod
    def get_records(user_id: int, field_id: int = None, limit: int = 100) -> List[Dict[str, Any]]:
        """ユーザーの防除記録を取得"""
        with get_db() as conn:
            if field_id:
                cursor = conn.execute(
                    """
                    SELECT r.*, f.field_code, f.name as field_name
                    FROM pesticide_records r
                    JOIN fields f ON r.field_id = f.id
                    WHERE r.user_id = ? AND r.field_id = ?
                    ORDER BY r.spray_date DESC
                    LIMIT ?
                    """,
                    (user_id, field_id, limit)
                )
            else:
                cursor = conn.execute(
                    """
                    SELECT r.*, f.field_code, f.name as field_name
                    FROM pesticide_records r
                    JOIN fields f ON r.field_id = f.id
                    WHERE r.user_id = ?
                    ORDER BY r.spray_date DESC
                    LIMIT ?
                    """,
                    (user_id, limit)
                )
            return [dict(row) for row in cursor.fetchall()]

    @staticmethod
    def create_record(user_id: int, data: Dict[str, Any]) -> int:
        """防除記録を作成"""
        with get_db() as conn:
            cursor = conn.execute(
                """
                INSERT INTO pesticide_records
                (user_id, field_id, spray_date, pesticide_name, pesticide_id,
                 dilution_rate, spray_amount, spray_unit, photo_path, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    data.get("field_id"),
                    data.get("spray_date"),
                    data.get("pesticide_name"),
                    data.get("pesticide_id"),
                    data.get("dilution_rate"),
                    data.get("spray_amount"),
                    data.get("spray_unit"),
                    data.get("photo_path"),
                    data.get("notes"),
                )
            )
            conn.commit()
            return cursor.lastrowid

    @staticmethod
    def update_record(record_id: int, data: Dict[str, Any]) -> bool:
        """防除記録を更新"""
        with get_db() as conn:
            cursor = conn.execute(
                """
                UPDATE pesticide_records SET
                    field_id = ?,
                    spray_date = ?,
                    pesticide_name = ?,
                    pesticide_id = ?,
                    dilution_rate = ?,
                    spray_amount = ?,
                    spray_unit = ?,
                    photo_path = ?,
                    notes = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (
                    data.get("field_id"),
                    data.get("spray_date"),
                    data.get("pesticide_name"),
                    data.get("pesticide_id"),
                    data.get("dilution_rate"),
                    data.get("spray_amount"),
                    data.get("spray_unit"),
                    data.get("photo_path"),
                    data.get("notes"),
                    record_id,
                )
            )
            conn.commit()
            return cursor.rowcount > 0

    @staticmethod
    def delete_record(record_id: int) -> bool:
        """防除記録を削除"""
        with get_db() as conn:
            cursor = conn.execute(
                "DELETE FROM pesticide_records WHERE id = ?",
                (record_id,)
            )
            conn.commit()
            return cursor.rowcount > 0


# =============================================================================
# 発注テンプレート
# =============================================================================

class OrderTemplateRepository:
    """発注テンプレートのCRUD操作"""

    @staticmethod
    def get_templates(user_id: int) -> List[Dict[str, Any]]:
        """ユーザーのテンプレート一覧を取得"""
        with get_db() as conn:
            cursor = conn.execute(
                """
                SELECT id, user_id, name, type, items_json, notes, created_at, updated_at
                FROM order_templates
                WHERE user_id = ?
                ORDER BY updated_at DESC
                """,
                (user_id,)
            )
            rows = cursor.fetchall()
            result = []
            for row in rows:
                item = dict(row)
                if item.get("items_json"):
                    item["items"] = json.loads(item["items_json"])
                else:
                    item["items"] = []
                result.append(item)
            return result

    @staticmethod
    def get_template(template_id: int) -> Optional[Dict[str, Any]]:
        """テンプレートを取得"""
        with get_db() as conn:
            cursor = conn.execute(
                """
                SELECT id, user_id, name, type, items_json, notes, created_at, updated_at
                FROM order_templates
                WHERE id = ?
                """,
                (template_id,)
            )
            row = cursor.fetchone()
            if row:
                item = dict(row)
                if item.get("items_json"):
                    item["items"] = json.loads(item["items_json"])
                else:
                    item["items"] = []
                return item
            return None

    @staticmethod
    def create_template(user_id: int, data: Dict[str, Any]) -> int:
        """テンプレートを作成"""
        with get_db() as conn:
            items_json = json.dumps(data.get("items", []), ensure_ascii=False)
            cursor = conn.execute(
                """
                INSERT INTO order_templates (user_id, name, type, items_json, notes)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    data.get("name"),
                    data.get("type", "custom"),
                    items_json,
                    data.get("notes"),
                )
            )
            conn.commit()
            return cursor.lastrowid

    @staticmethod
    def update_template(template_id: int, data: Dict[str, Any]) -> bool:
        """テンプレートを更新"""
        with get_db() as conn:
            items_json = json.dumps(data.get("items", []), ensure_ascii=False)
            cursor = conn.execute(
                """
                UPDATE order_templates
                SET name = ?, type = ?, items_json = ?, notes = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (
                    data.get("name"),
                    data.get("type", "custom"),
                    items_json,
                    data.get("notes"),
                    template_id,
                )
            )
            conn.commit()
            return cursor.rowcount > 0

    @staticmethod
    def delete_template(template_id: int) -> bool:
        """テンプレートを削除"""
        with get_db() as conn:
            cursor = conn.execute(
                "DELETE FROM order_templates WHERE id = ?",
                (template_id,)
            )
            conn.commit()
            return cursor.rowcount > 0


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
