"""
在庫管理API

農薬在庫の管理、CSVインポート/エクスポート、取引履歴の機能を提供。
"""

from fastapi import APIRouter, HTTPException, Depends, UploadFile, File
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional, Dict
from datetime import datetime
import sqlite3
import csv
import io
import os


router = APIRouter(prefix="/api/inventory", tags=["inventory"])


# =============================================================================
# Pydantic モデル
# =============================================================================

class InventoryItem(BaseModel):
    """在庫アイテム"""
    id: int
    user_id: int
    pesticide_name: str
    amount: float
    unit: str
    storage_location: Optional[str] = None
    expiry_date: Optional[str] = None
    purchase_date: Optional[str] = None
    purchase_price: Optional[float] = None
    supplier: Optional[str] = None
    lot_number: Optional[str] = None
    last_used_date: Optional[str] = None
    usage_count: int = 0
    updated_at: Optional[str] = None


class InventoryListResponse(BaseModel):
    """在庫一覧レスポンス"""
    items: List[InventoryItem]
    total: int


class InventoryCreate(BaseModel):
    """在庫追加/更新リクエスト"""
    pesticide_name: str
    quantity: float
    unit: str
    storage_location: Optional[str] = None
    expiry_date: Optional[str] = None
    purchase_date: Optional[str] = None
    purchase_price: Optional[float] = None
    supplier: Optional[str] = None
    lot_number: Optional[str] = None
    notes: Optional[str] = None


class InventoryImportResponse(BaseModel):
    """CSVインポートレスポンス"""
    imported: int
    updated: int
    errors: List[str]


class InventoryTransaction(BaseModel):
    """取引履歴アイテム"""
    id: int
    inventory_id: int
    transaction_type: str
    quantity: float
    unit: Optional[str] = None
    reference_type: Optional[str] = None
    reference_id: Optional[int] = None
    notes: Optional[str] = None
    created_by: Optional[int] = None
    created_at: Optional[str] = None


class TransactionListResponse(BaseModel):
    """取引履歴レスポンス"""
    transactions: List[InventoryTransaction]
    total: int


# =============================================================================
# ユーティリティ関数
# =============================================================================

def get_db_path():
    """データベースパスを取得"""
    return os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "rotation_planner.db")


def ensure_inventory_tables():
    """在庫管理テーブルを確保"""
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # inventory_transactions テーブル
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS inventory_transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            inventory_id INTEGER NOT NULL,
            transaction_type TEXT NOT NULL,
            quantity REAL NOT NULL,
            unit TEXT,
            reference_type TEXT,
            reference_id INTEGER,
            notes TEXT,
            created_by INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # inventory_csv_operations テーブル
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS inventory_csv_operations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            operation_type TEXT NOT NULL,
            filename TEXT,
            record_count INTEGER,
            status TEXT,
            error_message TEXT,
            created_by INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()


def row_to_inventory_item(row) -> InventoryItem:
    """SQLite Rowを InventoryItem に変換"""
    return InventoryItem(
        id=row["id"],
        user_id=row["user_id"],
        pesticide_name=row["pesticide_name"],
        amount=row["amount"],
        unit=row["unit"],
        storage_location=row["storage_location"] if "storage_location" in row.keys() else None,
        expiry_date=row["expiry_date"] if "expiry_date" in row.keys() else None,
        purchase_date=row["purchase_date"] if "purchase_date" in row.keys() else None,
        purchase_price=row["purchase_price"] if "purchase_price" in row.keys() else None,
        supplier=row["supplier"] if "supplier" in row.keys() else None,
        lot_number=row["lot_number"] if "lot_number" in row.keys() else None,
        last_used_date=row["last_used_date"] if "last_used_date" in row.keys() else None,
        usage_count=row["usage_count"] if "usage_count" in row.keys() else 0,
        updated_at=row["updated_at"] if "updated_at" in row.keys() else None,
    )


# =============================================================================
# エンドポイント
# =============================================================================

def create_inventory_routes(get_current_user):
    """在庫管理ルートを作成（認証依存性を注入）"""

    @router.get("", response_model=InventoryListResponse)
    def list_inventory(
        search: Optional[str] = None,
        sort_by: Optional[str] = "pesticide_name",
        order: Optional[str] = "asc",
        current_user: Dict = Depends(get_current_user)
    ):
        """在庫一覧を取得"""
        ensure_inventory_tables()

        db_path = get_db_path()
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        query = "SELECT * FROM inventory WHERE 1=1"
        params = []

        if current_user["role"] not in ["admin", "ja_staff"]:
            query += " AND user_id = ?"
            params.append(current_user["id"])

        if search:
            query += " AND pesticide_name LIKE ?"
            params.append(f"%{search}%")

        allowed_sort = ["pesticide_name", "amount", "updated_at", "expiry_date"]
        if sort_by in allowed_sort:
            order_dir = "DESC" if order.lower() == "desc" else "ASC"
            query += f" ORDER BY {sort_by} {order_dir}"

        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()

        items = [row_to_inventory_item(row) for row in rows]
        return InventoryListResponse(items=items, total=len(items))


    @router.post("", response_model=InventoryItem)
    def create_or_update_inventory(data: InventoryCreate, current_user: Dict = Depends(get_current_user)):
        """在庫を追加または更新（upsert）"""
        ensure_inventory_tables()

        db_path = get_db_path()
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        user_id = current_user["id"]

        cursor.execute("SELECT * FROM inventory WHERE user_id = ? AND pesticide_name = ?", (user_id, data.pesticide_name))
        existing = cursor.fetchone()

        if existing:
            new_amount = existing["amount"] + data.quantity
            cursor.execute("""
                UPDATE inventory SET amount = ?, unit = ?,
                    storage_location = COALESCE(?, storage_location),
                    expiry_date = COALESCE(?, expiry_date),
                    purchase_date = COALESCE(?, purchase_date),
                    purchase_price = COALESCE(?, purchase_price),
                    supplier = COALESCE(?, supplier),
                    lot_number = COALESCE(?, lot_number),
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (new_amount, data.unit, data.storage_location, data.expiry_date, data.purchase_date,
                  data.purchase_price, data.supplier, data.lot_number, existing["id"]))
            inventory_id = existing["id"]
        else:
            cursor.execute("""
                INSERT INTO inventory (user_id, pesticide_name, amount, unit, storage_location,
                    expiry_date, purchase_date, purchase_price, supplier, lot_number, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (user_id, data.pesticide_name, data.quantity, data.unit, data.storage_location,
                  data.expiry_date, data.purchase_date, data.purchase_price, data.supplier, data.lot_number))
            inventory_id = cursor.lastrowid

        cursor.execute("""
            INSERT INTO inventory_transactions (inventory_id, transaction_type, quantity, unit, reference_type, notes, created_by)
            VALUES (?, 'in', ?, ?, 'manual', ?, ?)
        """, (inventory_id, data.quantity, data.unit, data.notes, user_id))

        conn.commit()
        cursor.execute("SELECT * FROM inventory WHERE id = ?", (inventory_id,))
        row = cursor.fetchone()
        conn.close()

        return row_to_inventory_item(row)


    @router.delete("/{inventory_id}")
    def delete_inventory(inventory_id: int, current_user: Dict = Depends(get_current_user)):
        """在庫を削除"""
        ensure_inventory_tables()

        db_path = get_db_path()
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM inventory WHERE id = ?", (inventory_id,))
        inventory = cursor.fetchone()

        if not inventory:
            conn.close()
            raise HTTPException(status_code=404, detail="在庫が見つかりません")

        if inventory["user_id"] != current_user["id"] and current_user["role"] not in ["admin", "ja_staff"]:
            conn.close()
            raise HTTPException(status_code=403, detail="この在庫を削除する権限がありません")

        cursor.execute("""
            INSERT INTO inventory_transactions (inventory_id, transaction_type, quantity, unit, reference_type, notes, created_by)
            VALUES (?, 'adjust', ?, ?, 'adjustment', '在庫削除', ?)
        """, (inventory_id, -inventory["amount"], inventory["unit"], current_user["id"]))

        cursor.execute("DELETE FROM inventory WHERE id = ?", (inventory_id,))
        conn.commit()
        conn.close()

        return {"message": "在庫を削除しました", "deleted_id": inventory_id}


    @router.post("/import-csv", response_model=InventoryImportResponse)
    async def import_inventory_csv(file: UploadFile = File(...), current_user: Dict = Depends(get_current_user)):
        """CSVから在庫を一括インポート"""
        ensure_inventory_tables()

        if not file.filename.lower().endswith('.csv'):
            raise HTTPException(status_code=400, detail="CSVファイルを選択してください")

        content = await file.read()
        try:
            text = content.decode('utf-8-sig')
        except UnicodeDecodeError:
            text = content.decode('shift_jis', errors='replace')

        db_path = get_db_path()
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        user_id = current_user["id"]
        imported, updated = 0, 0
        errors = []

        reader = csv.reader(io.StringIO(text))
        header = next(reader, None)
        if not header:
            conn.close()
            raise HTTPException(status_code=400, detail="CSVファイルが空です")

        for idx, row in enumerate(reader):
            line_num = idx + 2
            if len(row) < 3:
                errors.append(f"行{line_num}: 列数が不足")
                continue

            pesticide_name, quantity_str, unit = row[0].strip(), row[1].strip(), row[2].strip()
            storage_location = row[3].strip() if len(row) > 3 else None
            expiry_date = row[4].strip() if len(row) > 4 else None
            notes = row[5].strip() if len(row) > 5 else None

            if not pesticide_name:
                errors.append(f"行{line_num}: 農薬名が空")
                continue
            try:
                quantity = float(quantity_str)
                if quantity <= 0:
                    raise ValueError()
            except ValueError:
                errors.append(f"行{line_num}: 数量「{quantity_str}」が無効")
                continue

            cursor.execute("SELECT * FROM inventory WHERE user_id = ? AND pesticide_name = ?", (user_id, pesticide_name))
            existing = cursor.fetchone()

            if existing:
                cursor.execute("""
                    UPDATE inventory SET amount = amount + ?, storage_location = COALESCE(?, storage_location),
                        expiry_date = COALESCE(?, expiry_date), updated_at = CURRENT_TIMESTAMP WHERE id = ?
                """, (quantity, storage_location, expiry_date, existing["id"]))
                inventory_id = existing["id"]
                updated += 1
            else:
                cursor.execute("""
                    INSERT INTO inventory (user_id, pesticide_name, amount, unit, storage_location, expiry_date, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """, (user_id, pesticide_name, quantity, unit, storage_location, expiry_date))
                inventory_id = cursor.lastrowid
                imported += 1

            cursor.execute("""
                INSERT INTO inventory_transactions (inventory_id, transaction_type, quantity, unit, reference_type, notes, created_by)
                VALUES (?, 'in', ?, ?, 'csv_import', ?, ?)
            """, (inventory_id, quantity, unit, notes, user_id))

        status = "success" if not errors else ("partial" if imported + updated > 0 else "failed")
        cursor.execute("""
            INSERT INTO inventory_csv_operations (operation_type, filename, record_count, status, error_message, created_by)
            VALUES ('import', ?, ?, ?, ?, ?)
        """, (file.filename, imported + updated, status, "; ".join(errors[:5]) if errors else None, user_id))

        conn.commit()
        conn.close()
        return InventoryImportResponse(imported=imported, updated=updated, errors=errors)


    @router.get("/export-csv")
    def export_inventory_csv(current_user: Dict = Depends(get_current_user)):
        """在庫をCSVでエクスポート"""
        ensure_inventory_tables()

        db_path = get_db_path()
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        user_id = current_user["id"]

        if current_user["role"] in ["admin", "ja_staff"]:
            cursor.execute("SELECT * FROM inventory ORDER BY pesticide_name")
        else:
            cursor.execute("SELECT * FROM inventory WHERE user_id = ? ORDER BY pesticide_name", (user_id,))
        rows = cursor.fetchall()

        cursor.execute("""
            INSERT INTO inventory_csv_operations (operation_type, filename, record_count, status, created_by)
            VALUES ('export', 'inventory_export.csv', ?, 'success', ?)
        """, (len(rows), user_id))
        conn.commit()
        conn.close()

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["農薬名", "在庫量", "単位", "保管場所", "有効期限", "備考", "最終使用日", "使用回数", "出力日時"])

        export_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for row in rows:
            writer.writerow([
                row["pesticide_name"], row["amount"], row["unit"],
                row["storage_location"] if "storage_location" in row.keys() else "",
                row["expiry_date"] if "expiry_date" in row.keys() else "", "",
                row["last_used_date"] if "last_used_date" in row.keys() else "",
                row["usage_count"] if "usage_count" in row.keys() else 0, export_time,
            ])

        output.seek(0)
        return StreamingResponse(
            io.BytesIO(output.getvalue().encode("utf-8-sig")),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=inventory_export_{datetime.now().strftime('%Y%m%d')}.csv"}
        )


    @router.get("/transactions", response_model=TransactionListResponse)
    def list_inventory_transactions(
        inventory_id: Optional[int] = None,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        current_user: Dict = Depends(get_current_user)
    ):
        """取引履歴を取得"""
        ensure_inventory_tables()

        db_path = get_db_path()
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        if current_user["role"] in ["admin", "ja_staff"]:
            query = "SELECT t.* FROM inventory_transactions t JOIN inventory i ON t.inventory_id = i.id WHERE 1=1"
            params = []
        else:
            query = "SELECT t.* FROM inventory_transactions t JOIN inventory i ON t.inventory_id = i.id WHERE i.user_id = ?"
            params = [current_user["id"]]

        if inventory_id:
            query += " AND t.inventory_id = ?"
            params.append(inventory_id)
        if from_date:
            query += " AND t.created_at >= ?"
            params.append(from_date)
        if to_date:
            query += " AND t.created_at <= ?"
            params.append(to_date)
        query += " ORDER BY t.created_at DESC"

        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()

        transactions = [InventoryTransaction(
            id=row["id"], inventory_id=row["inventory_id"], transaction_type=row["transaction_type"],
            quantity=row["quantity"], unit=row["unit"], reference_type=row["reference_type"],
            reference_id=row["reference_id"], notes=row["notes"], created_by=row["created_by"],
            created_at=row["created_at"],
        ) for row in rows]

        return TransactionListResponse(transactions=transactions, total=len(transactions))

    return router
