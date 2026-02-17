"""
農薬管理ルーター

農薬マスタ、発注、防除記録、画像解析
"""

from fastapi import APIRouter, HTTPException, Depends, UploadFile, File
from fastapi.responses import StreamingResponse, FileResponse
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime
from pathlib import Path
import logging
import io
import csv
import os
import base64
import uuid
import shutil
import json

from rotation_planner.common import (
    PesticideMasterRepository,
    PesticideOrderRepository,
    PesticideRecordRepository,
    InventoryRepository,
    PlanRepository,
    FieldRepository,
)
from api.error_handlers import require_found
from api.deps import get_current_user, require_admin

router = APIRouter(tags=["農薬"])
logger = logging.getLogger("rotation_planner.api")

# 定数
SPRAY_VOLUME_PER_10A = 100  # L
UPLOAD_DIR = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) / "uploads" / "pesticide_records"


# =============================================================================
# Pydantic モデル
# =============================================================================

# 農薬マスタ
class PesticideMasterCreate(BaseModel):
    name: str
    crop: str
    target_pest: Optional[str] = None
    dilution_rate: Optional[str] = None
    application_method: Optional[str] = None
    unit: Optional[str] = None
    unit_price: Optional[float] = None
    notes: Optional[str] = None


class PesticideMasterResponse(BaseModel):
    id: int
    name: str
    crop: str
    target_pest: Optional[str] = None
    dilution_rate: Optional[str] = None
    application_method: Optional[str] = None
    unit: Optional[str] = None
    unit_price: Optional[float] = None
    notes: Optional[str] = None


# 農薬発注
class PesticideOrderCreate(BaseModel):
    plan_id: Optional[int] = None
    year: int
    items: List[Dict[str, Any]]  # [{pesticide_id, crop, area_ha, quantity, ...}]


class PesticideOrderResponse(BaseModel):
    id: int
    user_id: int
    plan_id: Optional[int]
    year: int
    items: List[Dict[str, Any]]
    created_at: Optional[str]


class PesticideOrderUpdate(BaseModel):
    """農薬発注の更新リクエスト（部分更新対応）"""
    year: Optional[int] = None
    items: Optional[List[Dict[str, Any]]] = None
    notes: Optional[str] = None


# 農薬必要量計算
class CalculateFromPlanRequest(BaseModel):
    """輪作計画から農薬必要量を計算するリクエスト"""
    plan_id: int
    year: int


class CalculatedPesticideItem(BaseModel):
    """計算された農薬必要量"""
    pesticide_name: str
    crop: str
    area_ha: float
    quantity: float
    unit: str
    target_pest: Optional[str] = None
    dilution_rate: Optional[str] = None


class CalculateFromPlanResponse(BaseModel):
    """計算結果レスポンス"""
    items: List[CalculatedPesticideItem]
    summary: Dict[str, Any]
    message: str


# 防除記録
class PesticideRecordCreate(BaseModel):
    field_id: int
    date: str
    pesticide_name: str
    crop: str
    target_pest: Optional[str] = None
    dilution_rate: Optional[str] = None
    area_ha: Optional[float] = None
    quantity: Optional[float] = None
    unit: Optional[str] = None
    weather: Optional[str] = None
    temperature: Optional[float] = None
    operator: Optional[str] = None
    notes: Optional[str] = None


class PesticideRecordResponse(BaseModel):
    id: int
    user_id: int
    field_id: int
    field_code: Optional[str] = None
    date: str
    pesticide_name: str
    crop: str
    target_pest: Optional[str] = None
    dilution_rate: Optional[str] = None
    area_ha: Optional[float] = None
    quantity: Optional[float] = None
    unit: Optional[str] = None
    weather: Optional[str] = None
    temperature: Optional[float] = None
    operator: Optional[str] = None
    notes: Optional[str] = None
    created_at: Optional[str] = None


class PesticideRecordCreateResponse(BaseModel):
    """防除記録作成レスポンス（在庫警告付き）"""
    record: PesticideRecordResponse
    inventory_warning: bool = False
    inventory_message: Optional[str] = None
    inventory_remaining: Optional[float] = None


class InventoryInfoResponse(BaseModel):
    """在庫情報レスポンス"""
    pesticide_name: str
    amount: Optional[float] = None
    unit: Optional[str] = None
    exists: bool = False
    last_used_date: Optional[str] = None
    usage_count: Optional[int] = None


# 画像解析
class ImageAnalyzeResponse(BaseModel):
    pesticide_name: Optional[str] = None
    confidence: Optional[float] = None
    raw_text: Optional[str] = None
    error: Optional[str] = None


# 防除記録画像
class RecordImageResponse(BaseModel):
    id: str
    record_id: int
    filename: str
    original_name: str
    url: str
    created_at: str


# =============================================================================
# 農薬マスタエンドポイント
# =============================================================================

@router.get("/api/pesticide-masters", response_model=List[PesticideMasterResponse])
def list_pesticide_masters(crop: Optional[str] = None, current_user: Dict = Depends(get_current_user)):
    if crop:
        masters = PesticideMasterRepository.get_by_crop(crop)
    else:
        masters = PesticideMasterRepository.get_all()
    return [PesticideMasterResponse(**m) for m in masters]


@router.post("/api/pesticide-masters", response_model=PesticideMasterResponse, status_code=201)
def create_pesticide_master(master: PesticideMasterCreate, current_user: Dict = Depends(require_admin)):
    master_id = PesticideMasterRepository.create(master.model_dump())
    created = PesticideMasterRepository.get(master_id)
    return PesticideMasterResponse(**created)


@router.put("/api/pesticide-masters/{master_id}", response_model=PesticideMasterResponse)
def update_pesticide_master(master_id: int, master: PesticideMasterCreate, current_user: Dict = Depends(require_admin)):
    PesticideMasterRepository.update(master_id, master.model_dump())
    updated = require_found(PesticideMasterRepository.get(master_id), "農薬マスタ")
    return PesticideMasterResponse(**updated)


@router.delete("/api/pesticide-masters/{master_id}", status_code=204)
def delete_pesticide_master(master_id: int, current_user: Dict = Depends(require_admin)):
    PesticideMasterRepository.delete(master_id)


@router.get("/api/pesticide-masters/by-name/{name}/dilution-rates")
def get_dilution_rates_by_name(name: str, current_user: Dict = Depends(get_current_user)):
    """
    農薬名から希釈倍率候補を取得

    同名の農薬マスタから希釈倍率と対象病害虫の組み合わせを返す。
    防除記録入力時の補完に使用。
    """
    masters = PesticideMasterRepository.get_all()
    results = []
    seen = set()

    for m in masters:
        if m.get("name") == name:
            key = (m.get("dilution_rate", ""), m.get("target_pest", ""), m.get("crop", ""))
            if key not in seen and key[0]:  # 希釈倍率があるもののみ
                results.append({
                    "dilution_rate": m.get("dilution_rate", ""),
                    "target_pest": m.get("target_pest", ""),
                    "crop": m.get("crop", ""),
                    "application_method": m.get("application_method", ""),
                })
                seen.add(key)

    return results


# =============================================================================
# 農薬発注エンドポイント
# =============================================================================

@router.get("/api/pesticide-orders", response_model=List[PesticideOrderResponse])
def list_pesticide_orders(year: Optional[int] = None, current_user: Dict = Depends(get_current_user)):
    orders = PesticideOrderRepository.get_orders(current_user["id"], year)
    return [PesticideOrderResponse(**o) for o in orders]


@router.post("/api/pesticide-orders", response_model=PesticideOrderResponse, status_code=201)
def create_pesticide_order(order: PesticideOrderCreate, current_user: Dict = Depends(get_current_user)):
    order_id = PesticideOrderRepository.create_order(
        user_id=current_user["id"],
        plan_id=order.plan_id,
        year=order.year,
        items=order.items
    )
    created = PesticideOrderRepository.get_order(order_id)
    return PesticideOrderResponse(**created)


@router.get("/api/pesticide-orders/{order_id}", response_model=PesticideOrderResponse)
def get_pesticide_order(order_id: int, current_user: Dict = Depends(get_current_user)):
    order = PesticideOrderRepository.get_order(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order["user_id"] != current_user["id"] and current_user["role"] not in ["admin", "ja_staff"]:
        raise HTTPException(status_code=403, detail="Access denied")
    return PesticideOrderResponse(**order)


@router.put("/api/pesticide-orders/{order_id}", response_model=PesticideOrderResponse)
def update_pesticide_order(
    order_id: int,
    order_update: PesticideOrderUpdate,
    current_user: Dict = Depends(get_current_user)
):
    """農薬発注を更新（部分更新対応）"""
    order = require_found(PesticideOrderRepository.get_order(order_id), "農薬発注")
    if order["user_id"] != current_user["id"] and current_user["role"] not in ["admin", "ja_staff"]:
        raise HTTPException(status_code=403, detail="Access denied")

    # 更新データを構築（Noneでないフィールドのみ）
    update_data = {}
    if order_update.year is not None:
        update_data["year"] = order_update.year
    if order_update.items is not None:
        update_data["items"] = order_update.items
    if order_update.notes is not None:
        update_data["notes"] = order_update.notes

    if update_data:
        PesticideOrderRepository.update_order(order_id, update_data)

    updated = PesticideOrderRepository.get_order(order_id)
    return PesticideOrderResponse(**updated)


@router.delete("/api/pesticide-orders/{order_id}", status_code=204)
def delete_pesticide_order(order_id: int, current_user: Dict = Depends(get_current_user)):
    order = require_found(PesticideOrderRepository.get_order(order_id), "農薬発注")
    if order["user_id"] != current_user["id"] and current_user["role"] not in ["admin", "ja_staff"]:
        raise HTTPException(status_code=403, detail="Access denied")
    PesticideOrderRepository.delete_order(order_id)


# =============================================================================
# 農薬必要量自動計算エンドポイント
# =============================================================================

@router.post("/api/pesticide-orders/calculate-from-plan", response_model=CalculateFromPlanResponse)
def calculate_pesticide_from_plan(
    req: CalculateFromPlanRequest,
    current_user: Dict = Depends(get_current_user)
):
    """
    輪作計画から農薬必要量を自動計算

    指定された計画と年度から、各ほ場の作物・面積を取得し、
    農薬マスタを参照して必要量を計算する。
    """
    # 計画を取得
    plan = require_found(PlanRepository.get_plan(req.plan_id), "輪作計画")
    if plan["user_id"] != current_user["id"] and current_user["role"] not in ["admin", "ja_staff"]:
        raise HTTPException(status_code=403, detail="アクセス権限がありません")

    details = plan.get("details", [])
    if not details:
        raise HTTPException(status_code=400, detail="計画に詳細データがありません")

    # 指定年度のデータを抽出
    year_str = str(req.year)
    target_details = [d for d in details if str(d.get("year", "")) == year_str]
    if not target_details:
        raise HTTPException(
            status_code=400,
            detail=f"{req.year}年のデータが計画に含まれていません"
        )

    # ほ場IDごとに面積を取得
    field_areas = {}
    for d in target_details:
        field_id = d.get("field_id")
        if field_id and field_id not in field_areas:
            field = FieldRepository.get_field(field_id)
            if field:
                field_areas[field_id] = field.get("area_ha", 0)

    # 作物ごとの面積を集計
    crop_areas = {}
    for d in target_details:
        crop = d.get("crop", "").strip()
        if not crop:
            continue
        field_id = d.get("field_id")
        area_ha = field_areas.get(field_id, 0)
        if crop not in crop_areas:
            crop_areas[crop] = 0
        crop_areas[crop] += area_ha

    if not crop_areas:
        return CalculateFromPlanResponse(
            items=[],
            summary={},
            message="対象となる作物データがありません"
        )

    # 農薬マスタから作物別の農薬を取得して必要量を計算
    calculated_items = []

    for crop, area_ha in crop_areas.items():
        masters = PesticideMasterRepository.get_by_crop(crop)
        area_10a = area_ha * 10

        for m in masters:
            pesticide_name = m.get("name", "")
            dilution_rate = m.get("dilution_rate", "")
            target_pest = m.get("target_pest", "")

            if dilution_rate:
                try:
                    rate_str = str(dilution_rate).replace("倍", "").replace(",", "")
                    rate_str = rate_str.split("〜")[0].split("-")[0].split("/")[0]
                    rate = float(rate_str)
                    if rate > 0:
                        quantity_ml = (SPRAY_VOLUME_PER_10A / rate) * area_10a * 1000
                        quantity = quantity_ml / 1000
                        final_unit = "L"
                    else:
                        continue
                except (ValueError, ZeroDivisionError):
                    continue
            else:
                continue

            item = CalculatedPesticideItem(
                pesticide_name=pesticide_name,
                crop=crop,
                area_ha=area_ha,
                quantity=round(quantity, 2),
                unit=final_unit,
                target_pest=target_pest,
                dilution_rate=dilution_rate
            )
            calculated_items.append(item)

    crop_summary = ", ".join(f"{c}({a:.2f}ha)" for c, a in sorted(crop_areas.items()))
    message = f"計算完了: {len(calculated_items)}件の農薬\n対象: {crop_summary}"

    return CalculateFromPlanResponse(
        items=calculated_items,
        summary=crop_areas,
        message=message
    )


@router.get("/api/pesticide-orders/export/csv")
def export_pesticide_orders_csv(
    year: Optional[int] = None,
    current_user: Dict = Depends(get_current_user)
):
    """
    農薬発注データをCSV形式でエクスポート（BOM付きUTF-8でExcel対応）
    """
    orders = PesticideOrderRepository.get_orders(current_user["id"], year)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["発注ID", "年度", "作成日", "農薬名", "対象作物", "数量", "単位", "面積(ha)", "対象病害虫", "希釈倍率"])

    for order in orders:
        order_id = order.get("id", "")
        order_year = order.get("year", "")
        created_at = order.get("created_at", "")
        items = order.get("items", [])
        for item in items:
            writer.writerow([
                order_id,
                order_year,
                created_at,
                item.get("pesticide_name", ""),
                item.get("crop", ""),
                item.get("quantity", ""),
                item.get("unit", ""),
                item.get("area_ha", ""),
                item.get("target_pest", ""),
                item.get("dilution_rate", ""),
            ])

    output.seek(0)
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode("utf-8-sig")),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=pesticide_orders_{year or 'all'}.csv"}
    )


@router.get("/api/pesticide-orders/export/pdf")
def export_pesticide_orders_pdf(
    year: Optional[int] = None,
    current_user: Dict = Depends(get_current_user)
):
    """農薬発注リストをPDFで出力"""
    try:
        from rotation_planner.pesticide.pdf_export import (
            generate_pesticide_order_pdf,
            REPORTLAB_AVAILABLE
        )
    except ImportError:
        raise HTTPException(status_code=501, detail="PDF機能が利用できません")

    if not REPORTLAB_AVAILABLE:
        raise HTTPException(status_code=501, detail="reportlabがインストールされていません")

    import pandas as pd
    import tempfile

    orders = PesticideOrderRepository.get_orders(current_user["id"], year)
    if not orders:
        raise HTTPException(status_code=404, detail=f"{year or '全'}年の発注データがありません")

    summary_data = []
    for order in orders:
        for item in order.get("items", []):
            summary_data.append({
                "農薬名": item.get("pesticide_name", ""),
                "必要量": str(item.get("quantity", "")),
                "単位": item.get("unit", ""),
                "対象作物": item.get("crop", ""),
                "対象病害虫": item.get("target_pest", ""),
            })

    if not summary_data:
        raise HTTPException(status_code=404, detail="発注明細がありません")

    summary_df = pd.DataFrame(summary_data)
    detail_df = pd.DataFrame()

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        output_path = generate_pesticide_order_pdf(
            summary_df=summary_df,
            detail_df=detail_df,
            order_name=f"{year or '全年度'}発注リスト",
            target_year=str(year or "全年度"),
            output_path=tmp_path
        )
        if not output_path:
            raise HTTPException(status_code=500, detail="PDF生成に失敗しました")

        with open(tmp_path, "rb") as f:
            pdf_bytes = f.read()

        return StreamingResponse(
            io.BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename=pesticide_orders_{year or 'all'}.pdf"}
        )
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


# =============================================================================
# 防除記録エンドポイント
# =============================================================================

@router.get("/api/pesticide-records", response_model=List[PesticideRecordResponse])
def list_pesticide_records(
    year: Optional[int] = None,
    field_id: Optional[int] = None,
    current_user: Dict = Depends(get_current_user)
):
    records = PesticideRecordRepository.get_records(
        user_id=current_user["id"],
        year=year,
        field_id=field_id
    )
    return [PesticideRecordResponse(**r) for r in records]


@router.post("/api/pesticide-records", response_model=PesticideRecordCreateResponse, status_code=201)
def create_pesticide_record(record: PesticideRecordCreate, current_user: Dict = Depends(get_current_user)):
    # 防除記録を作成
    record_id = PesticideRecordRepository.create_record(
        user_id=current_user["id"],
        data=record.model_dump()
    )
    created = PesticideRecordRepository.get_record(record_id)

    # 在庫自動控除
    inventory_warning = False
    inventory_message = None
    inventory_remaining = None

    if record.quantity and record.quantity > 0 and record.pesticide_name:
        inv_result = InventoryRepository.deduct_inventory(
            user_id=current_user["id"],
            pesticide_name=record.pesticide_name,
            quantity=record.quantity,
            unit=record.unit or "L",
            reference_type="pesticide_record",
            reference_id=record_id,
            created_by=current_user["id"]
        )
        inventory_warning = inv_result.get("warning", False)
        inventory_message = inv_result.get("message")
        inventory_remaining = inv_result.get("remaining")

    return PesticideRecordCreateResponse(
        record=PesticideRecordResponse(**created),
        inventory_warning=inventory_warning,
        inventory_message=inventory_message,
        inventory_remaining=inventory_remaining
    )


@router.get("/api/pesticide-records/{record_id}", response_model=PesticideRecordResponse)
def get_pesticide_record(record_id: int, current_user: Dict = Depends(get_current_user)):
    record = require_found(PesticideRecordRepository.get_record(record_id), "防除記録")
    if record["user_id"] != current_user["id"] and current_user["role"] not in ["admin", "ja_staff"]:
        raise HTTPException(status_code=403, detail="Access denied")
    return PesticideRecordResponse(**record)


@router.put("/api/pesticide-records/{record_id}", response_model=PesticideRecordResponse)
def update_pesticide_record(record_id: int, record: PesticideRecordCreate, current_user: Dict = Depends(get_current_user)):
    existing = require_found(PesticideRecordRepository.get_record(record_id), "防除記録")
    if existing["user_id"] != current_user["id"] and current_user["role"] not in ["admin", "ja_staff"]:
        raise HTTPException(status_code=403, detail="Access denied")
    PesticideRecordRepository.update_record(record_id, record.model_dump())
    updated = PesticideRecordRepository.get_record(record_id)
    return PesticideRecordResponse(**updated)


@router.delete("/api/pesticide-records/{record_id}", status_code=204)
def delete_pesticide_record(record_id: int, current_user: Dict = Depends(get_current_user)):
    existing = require_found(PesticideRecordRepository.get_record(record_id), "防除記録")
    if existing["user_id"] != current_user["id"] and current_user["role"] not in ["admin", "ja_staff"]:
        raise HTTPException(status_code=403, detail="Access denied")
    PesticideRecordRepository.delete_record(record_id)


# =============================================================================
# 在庫情報取得（防除記録との連携用）
# =============================================================================

@router.get("/api/inventory/by-pesticide", response_model=InventoryInfoResponse)
def get_inventory_by_pesticide(
    pesticide_name: str,
    current_user: Dict = Depends(get_current_user)
):
    """農薬名で在庫情報を取得"""
    inv = InventoryRepository.get_inventory_by_pesticide(
        user_id=current_user["id"],
        pesticide_name=pesticide_name
    )

    if inv:
        return InventoryInfoResponse(
            pesticide_name=pesticide_name,
            amount=inv.get("amount"),
            unit=inv.get("unit"),
            exists=True,
            last_used_date=inv.get("last_used_date"),
            usage_count=inv.get("usage_count")
        )
    else:
        return InventoryInfoResponse(
            pesticide_name=pesticide_name,
            exists=False
        )


@router.get("/api/pesticide-records/export/csv")
def export_pesticide_records_csv(
    year: Optional[int] = None,
    current_user: Dict = Depends(get_current_user)
):
    records = PesticideRecordRepository.get_records(user_id=current_user["id"], year=year)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["日付", "ほ場", "作物", "農薬名", "対象病害虫", "希釈倍率", "面積(ha)", "使用量", "単位", "天気", "気温", "作業者", "備考"])
    for r in records:
        writer.writerow([
            r.get("date", ""),
            r.get("field_code", ""),
            r.get("crop", ""),
            r.get("pesticide_name", ""),
            r.get("target_pest", ""),
            r.get("dilution_rate", ""),
            r.get("area_ha", ""),
            r.get("quantity", ""),
            r.get("unit", ""),
            r.get("weather", ""),
            r.get("temperature", ""),
            r.get("operator", ""),
            r.get("notes", ""),
        ])
    output.seek(0)
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode("utf-8-sig")),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=pesticide_records_{year or 'all'}.csv"}
    )


# =============================================================================
# 画像解析エンドポイント (Claude Vision API)
# =============================================================================

@router.post("/api/pesticide-records/analyze-image", response_model=ImageAnalyzeResponse)
async def analyze_pesticide_image(
    image: UploadFile = File(...),
    current_user: Dict = Depends(get_current_user)
):
    """
    画像から農薬名を認識（Claude Vision API）

    - ANTHROPIC_API_KEYが設定されている場合: Claude Vision APIで解析
    - 設定されていない場合: モック応答を返す
    """
    # 画像データを読み込み
    image_data = await image.read()

    # ファイル形式チェック
    content_type = image.content_type or ""
    if not content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="画像ファイルをアップロードしてください")

    # MIMEタイプ決定
    media_type_map = {
        "image/jpeg": "image/jpeg",
        "image/jpg": "image/jpeg",
        "image/png": "image/png",
        "image/gif": "image/gif",
        "image/webp": "image/webp",
    }
    media_type = media_type_map.get(content_type, "image/jpeg")

    # API キーの確認
    api_key = os.environ.get("ANTHROPIC_API_KEY")

    if not api_key:
        # モック応答（API_KEYがない場合）
        return ImageAnalyzeResponse(
            pesticide_name="ダコニール1000（モック）",
            confidence=0.85,
            raw_text="[モック応答] ANTHROPIC_API_KEYが設定されていないため、モックデータを返しています。",
            error=None
        )

    try:
        import anthropic

        # Base64エンコード
        image_base64 = base64.standard_b64encode(image_data).decode("utf-8")

        # Claude Vision API 呼び出し
        client = anthropic.Anthropic(api_key=api_key)
        message = client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=256,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": image_base64
                        }
                    },
                    {
                        "type": "text",
                        "text": """この画像から農薬名を抽出してください。
以下の形式で回答してください:
農薬名: [農薬名]
確信度: [0.0-1.0の数値]

農薬名が読み取れない場合は「農薬名: 不明」「確信度: 0.0」と回答してください。"""
                    }
                ]
            }]
        )

        # 応答を解析
        response_text = message.content[0].text
        pesticide_name = None
        confidence = None

        for line in response_text.split('\n'):
            line = line.strip()
            if line.startswith('農薬名:') or line.startswith('農薬名：'):
                name = line.split(':', 1)[-1].split('：', 1)[-1].strip()
                if name and name != '不明':
                    pesticide_name = name

            if line.startswith('確信度:') or line.startswith('確信度：'):
                conf_str = line.split(':', 1)[-1].split('：', 1)[-1].strip()
                try:
                    confidence = float(conf_str)
                except ValueError:
                    # high/medium/low形式の場合
                    conf_map = {"high": 0.9, "medium": 0.6, "low": 0.3}
                    confidence = conf_map.get(conf_str.lower(), 0.5)

        # デフォルト確信度
        if pesticide_name and confidence is None:
            confidence = 0.6

        return ImageAnalyzeResponse(
            pesticide_name=pesticide_name,
            confidence=confidence,
            raw_text=response_text,
            error=None
        )

    except ImportError:
        return ImageAnalyzeResponse(
            pesticide_name=None,
            confidence=None,
            raw_text=None,
            error="anthropicパッケージがインストールされていません"
        )
    except Exception as e:
        return ImageAnalyzeResponse(
            pesticide_name=None,
            confidence=None,
            raw_text=None,
            error=f"画像解析エラー: {str(e)}"
        )


# =============================================================================
# 防除記録画像保存・取得
# =============================================================================

@router.post("/api/pesticide-records/{record_id}/images", response_model=RecordImageResponse, status_code=201)
async def upload_record_image(record_id: int, image: UploadFile = File(...), current_user: Dict = Depends(get_current_user)):
    """防除記録に画像を添付"""
    record = require_found(PesticideRecordRepository.get_record(record_id), "防除記録")
    if record["user_id"] != current_user["id"] and current_user["role"] not in ["admin", "ja_staff"]:
        raise HTTPException(status_code=403, detail="Access denied")
    if not (image.content_type or "").startswith("image/"):
        raise HTTPException(status_code=400, detail="画像ファイルをアップロードしてください")
    record_dir = UPLOAD_DIR / str(record_id)
    record_dir.mkdir(parents=True, exist_ok=True)
    ext = os.path.splitext(image.filename or ".jpg")[1] or ".jpg"
    image_id = str(uuid.uuid4())
    file_path = record_dir / f"{image_id}{ext}"
    with open(file_path, "wb") as f:
        shutil.copyfileobj(image.file, f)
    meta_file = record_dir / "meta.json"
    meta = json.load(open(meta_file, "r", encoding="utf-8")) if meta_file.exists() else []
    created_at = datetime.now().isoformat()
    meta.append({"id": image_id, "filename": f"{image_id}{ext}", "original_name": image.filename or "image.jpg", "created_at": created_at})
    json.dump(meta, open(meta_file, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    return RecordImageResponse(id=image_id, record_id=record_id, filename=f"{image_id}{ext}", original_name=image.filename or "image.jpg", url=f"/api/pesticide-records/{record_id}/images/{image_id}", created_at=created_at)


@router.get("/api/pesticide-records/{record_id}/images", response_model=List[RecordImageResponse])
def list_record_images(record_id: int, current_user: Dict = Depends(get_current_user)):
    """防除記録の画像一覧"""
    record = require_found(PesticideRecordRepository.get_record(record_id), "防除記録")
    if record["user_id"] != current_user["id"] and current_user["role"] not in ["admin", "ja_staff"]:
        raise HTTPException(status_code=403, detail="Access denied")
    meta_file = UPLOAD_DIR / str(record_id) / "meta.json"
    if not meta_file.exists():
        return []
    meta = json.load(open(meta_file, "r", encoding="utf-8"))
    return [RecordImageResponse(id=m["id"], record_id=record_id, filename=m["filename"], original_name=m["original_name"], url=f"/api/pesticide-records/{record_id}/images/{m['id']}", created_at=m["created_at"]) for m in meta]


@router.get("/api/pesticide-records/{record_id}/images/{image_id}")
def get_record_image(record_id: int, image_id: str, current_user: Dict = Depends(get_current_user)):
    """防除記録の画像取得"""
    record = require_found(PesticideRecordRepository.get_record(record_id), "防除記録")
    if record["user_id"] != current_user["id"] and current_user["role"] not in ["admin", "ja_staff"]:
        raise HTTPException(status_code=403, detail="Access denied")
    meta_file = UPLOAD_DIR / str(record_id) / "meta.json"
    if not meta_file.exists():
        raise HTTPException(status_code=404, detail="Image not found")
    meta = json.load(open(meta_file, "r", encoding="utf-8"))
    img = next((m for m in meta if m["id"] == image_id), None)
    if not img:
        raise HTTPException(status_code=404, detail="Image not found")
    fp = UPLOAD_DIR / str(record_id) / img["filename"]
    if not fp.exists():
        raise HTTPException(status_code=404, detail="Image file not found")
    return FileResponse(fp, filename=img["original_name"], media_type="image/jpeg")


@router.delete("/api/pesticide-records/{record_id}/images/{image_id}", status_code=204)
def delete_record_image(record_id: int, image_id: str, current_user: Dict = Depends(get_current_user)):
    """防除記録の画像削除"""
    record = require_found(PesticideRecordRepository.get_record(record_id), "防除記録")
    if record["user_id"] != current_user["id"] and current_user["role"] not in ["admin", "ja_staff"]:
        raise HTTPException(status_code=403, detail="Access denied")
    meta_file = UPLOAD_DIR / str(record_id) / "meta.json"
    if not meta_file.exists():
        raise HTTPException(status_code=404, detail="Image not found")
    meta = json.load(open(meta_file, "r", encoding="utf-8"))
    img = next((m for m in meta if m["id"] == image_id), None)
    if not img:
        raise HTTPException(status_code=404, detail="Image not found")
    fp = UPLOAD_DIR / str(record_id) / img["filename"]
    if fp.exists():
        fp.unlink()
    meta = [m for m in meta if m["id"] != image_id]
    json.dump(meta, open(meta_file, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
