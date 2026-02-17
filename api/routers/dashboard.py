"""
ダッシュボードルーター

統計情報、ヘルスチェック
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import List, Dict, Any
from datetime import datetime, timezone
import logging

from rotation_planner.common import (
    FieldRepository,
    CropHistoryRepository,
    PesticideOrderRepository,
    PesticideRecordRepository,
    PlanRepository,
)
from api.deps import get_current_user

router = APIRouter(tags=["ダッシュボード"])
logger = logging.getLogger("rotation_planner.api")


# =============================================================================
# Pydantic モデル
# =============================================================================

class DashboardStatsResponse(BaseModel):
    """ダッシュボード統計レスポンス"""
    fields: Dict[str, Any]
    crops: List[Dict[str, Any]]
    orders: Dict[str, Any]
    records: Dict[str, Any]
    plans: Dict[str, Any]


# =============================================================================
# ダッシュボード統計
# =============================================================================

@router.get("/api/dashboard/stats", response_model=DashboardStatsResponse)
def get_dashboard_stats(current_user: Dict = Depends(get_current_user)):
    """
    ダッシュボード用の統計情報を取得

    Returns:
        - fields: ほ場統計（総数、総面積）
        - crops: 今年度の作付状況（作物別面積）
        - orders: 農薬発注状況（発注済み/未発注）
        - records: 防除記録（今月の記録数）
        - plans: 輪作計画（保存済み計画数）
    """
    user_id = current_user["id"]

    # 1. ほ場統計
    fields = FieldRepository.get_fields(user_id)
    total_area = sum(f.get("area_ha", 0) for f in fields)
    fields_stats = {
        "count": len(fields),
        "total_area_ha": round(total_area, 2)
    }

    # 2. 今年度の作付状況（作物別面積）
    current_year = datetime.now().year
    crops_area = {}
    for field in fields:
        field_id = field.get("id")
        if not field_id:
            continue
        history = CropHistoryRepository.get_history(field_id)
        for h in history:
            if h.get("year") == current_year:
                crop = h.get("crop", "")
                if crop:
                    area = field.get("area_ha", 0)
                    if crop not in crops_area:
                        crops_area[crop] = 0
                    crops_area[crop] += area
    crops_stats = [
        {"name": name, "area_ha": round(area, 2)}
        for name, area in sorted(crops_area.items(), key=lambda x: -x[1])
    ]

    # 3. 農薬発注状況
    orders = PesticideOrderRepository.get_orders(user_id)
    orders_this_year = [o for o in orders if o.get("year") == current_year]
    orders_stats = {
        "total": len(orders_this_year),
        "pending": 0  # 将来的にステータス管理を追加可能
    }

    # 4. 防除記録（今月の記録数）
    records = PesticideRecordRepository.get_records(user_id=user_id)
    current_month = datetime.now().strftime("%Y-%m")
    this_month_count = sum(
        1 for r in records
        if r.get("date", "").startswith(current_month)
    )
    records_stats = {
        "this_month": this_month_count
    }

    # 5. 輪作計画（保存済み計画数）
    plans = PlanRepository.get_plans(user_id)
    plans_stats = {
        "count": len(plans)
    }

    return DashboardStatsResponse(
        fields=fields_stats,
        crops=crops_stats,
        orders=orders_stats,
        records=records_stats,
        plans=plans_stats
    )


# =============================================================================
# ヘルスチェック
# =============================================================================

@router.get("/api/health")
def health_check():
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}
