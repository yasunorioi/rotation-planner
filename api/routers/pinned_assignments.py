"""
Pinned Assignments ルーター

ほ場×年×作物 の固定割当(pin)管理 API。
- GET /api/pinned-assignments?active_only=true&user_id=N
- POST /api/pinned-assignments (?user_id=N で代行作成・admin/ja_staff のみ)
- DELETE /api/pinned-assignments/{id}?hard=false (デフォルト soft delete)

cmd_584 subtask_1254 (Wave 2b API実装)
殿裁定: Q1=b強制+警告 / Q2=a過去年pin禁止 / Q3=a通知不要
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
import sqlite3

from rotation_planner.common.db import get_db
from api.deps import get_current_user

router = APIRouter(prefix="/api/pinned-assignments", tags=["pinned"])


# =============================================================================
# Pydantic モデル (軍師設計書 §2.C)
# =============================================================================

class PinnedAssignmentCreate(BaseModel):
    field_id: int
    year: str = Field(..., min_length=1, max_length=10)  # "R9", "2027" 等
    crop: str = Field(..., min_length=1, max_length=100)
    pinned_reason: Optional[str] = None
    notes: Optional[str] = None


class PinnedAssignmentResponse(BaseModel):
    id: int
    user_id: int
    field_id: int
    year: str
    crop: str
    pinned_by: Optional[int]
    pinned_reason: Optional[str]
    is_active: int
    notes: Optional[str]
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


# =============================================================================
# ヘルパー
# =============================================================================

_COLS = "id, user_id, field_id, year, crop, pinned_by, pinned_reason, is_active, notes, created_at, updated_at"


def _row_to_dict(row) -> Dict[str, Any]:
    return {
        "id": row[0], "user_id": row[1], "field_id": row[2], "year": row[3],
        "crop": row[4], "pinned_by": row[5], "pinned_reason": row[6],
        "is_active": row[7], "notes": row[8],
        "created_at": str(row[9]) if row[9] else None,
        "updated_at": str(row[10]) if row[10] else None,
    }


def _parse_year_to_seireki(year_str: str) -> int:
    """'R9' → 2027, '2027' → 2027. 失敗時 ValueError."""
    s = year_str.strip()
    if s.upper().startswith("R"):
        return 2018 + int(s[1:])
    return int(s)


# =============================================================================
# エンドポイント
# =============================================================================

@router.get("", response_model=List[PinnedAssignmentResponse])
def list_pinned(
    active_only: bool = Query(True),
    user_id: Optional[int] = Query(None),
    current_user: Dict = Depends(get_current_user),
):
    """pinned_assignments 一覧取得.

    - farmer: 自分の pin のみ (user_id 指定は無視)
    - admin/ja_staff: user_id 指定可・無指定なら全件
    """
    role = current_user.get("role")
    is_admin = role in ("admin", "ja_staff")

    if is_admin:
        target_uid = user_id
    else:
        target_uid = current_user["id"]

    with get_db() as conn:
        clauses = []
        params: List[Any] = []
        if target_uid is not None:
            clauses.append("user_id = ?")
            params.append(target_uid)
        if active_only:
            clauses.append("is_active = 1")
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        sql = f"SELECT {_COLS} FROM pinned_assignments{where} ORDER BY user_id, field_id, year"
        cursor = conn.execute(sql, tuple(params))
        rows = cursor.fetchall()

    return [PinnedAssignmentResponse(**_row_to_dict(r)) for r in rows]


@router.post("", response_model=PinnedAssignmentResponse, status_code=201)
def create_pinned(
    req: PinnedAssignmentCreate,
    user_id: Optional[int] = Query(None),
    current_user: Dict = Depends(get_current_user),
):
    """pinned_assignments 新規作成.

    - 本人 or admin/ja_staff (?user_id=N で代行可)
    - Q2=a 過去年pin禁止: year 西暦解釈 < 現在年 → 400
    - UNIQUE 違反 → 409
    """
    role = current_user.get("role")
    is_admin = role in ("admin", "ja_staff")

    if user_id is not None and not is_admin:
        raise HTTPException(status_code=403, detail="代行作成は admin/ja_staff のみ")
    target_user_id = user_id if user_id is not None else current_user["id"]

    try:
        year_num = _parse_year_to_seireki(req.year)
    except (ValueError, IndexError):
        raise HTTPException(status_code=400, detail=f"year 形式不正: {req.year}")

    current_year = datetime.now().year
    if year_num < current_year:
        raise HTTPException(
            status_code=400,
            detail=f"過去年pin禁止 (year={year_num} < current={current_year})",
        )

    with get_db() as conn:
        try:
            cursor = conn.execute(
                """
                INSERT INTO pinned_assignments
                (user_id, field_id, year, crop, pinned_by, pinned_reason, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    target_user_id, req.field_id, req.year, req.crop,
                    current_user["id"], req.pinned_reason, req.notes,
                ),
            )
            new_id = cursor.lastrowid
            conn.commit()
        except sqlite3.IntegrityError as e:
            if "UNIQUE" in str(e).upper():
                raise HTTPException(
                    status_code=409,
                    detail="既に pin あり (user_id, field_id, year 重複)",
                )
            raise

        cursor = conn.execute(
            f"SELECT {_COLS} FROM pinned_assignments WHERE id = ?", (new_id,)
        )
        row = cursor.fetchone()

    return PinnedAssignmentResponse(**_row_to_dict(row))


@router.delete("/{pin_id}", status_code=204)
def delete_pinned(
    pin_id: int,
    hard: bool = Query(False),
    current_user: Dict = Depends(get_current_user),
):
    """pinned_assignments 削除.

    - デフォルト soft delete (is_active=0)
    - hard=True で物理削除
    - 本人 or admin/ja_staff のみ
    """
    role = current_user.get("role")
    is_admin = role in ("admin", "ja_staff")

    with get_db() as conn:
        cursor = conn.execute(
            "SELECT user_id FROM pinned_assignments WHERE id = ?", (pin_id,)
        )
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="pinned_assignment not found")
        pin_user_id = row[0]

        if not is_admin and current_user["id"] != pin_user_id:
            raise HTTPException(status_code=403, detail="他人の pin は削除不可")

        if hard:
            conn.execute("DELETE FROM pinned_assignments WHERE id = ?", (pin_id,))
        else:
            conn.execute(
                "UPDATE pinned_assignments SET is_active = 0, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (pin_id,),
            )
        conn.commit()
