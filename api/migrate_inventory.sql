-- ═══════════════════════════════════════════════════════════════
-- 在庫管理テーブル マイグレーション
-- Version: 1.0
-- Created: 2026-02-02
-- Description: 在庫テーブル拡張、入出庫履歴、CSVログ
-- ═══════════════════════════════════════════════════════════════
--
-- 実行方法:
--   sqlite3 data/rotation_planner.db < api/migrate_inventory.sql
--
-- 注意事項:
--   - 既存データを保持したままカラム追加を行う
--   - SQLite の ALTER TABLE は ADD COLUMN のみサポート
--   - 外部キー制約は CREATE TABLE 時に設定
--
-- ═══════════════════════════════════════════════════════════════

-- 外部キー制約を有効化
PRAGMA foreign_keys = ON;

-- ═══════════════════════════════════════════════════════════════
-- 1. inventory テーブル拡張（既存カラムを保持）
-- ═══════════════════════════════════════════════════════════════

-- 保管場所
ALTER TABLE inventory ADD COLUMN storage_location TEXT;

-- 有効期限
ALTER TABLE inventory ADD COLUMN expiry_date DATE;

-- 購入日
ALTER TABLE inventory ADD COLUMN purchase_date DATE;

-- 購入価格
ALTER TABLE inventory ADD COLUMN purchase_price REAL;

-- 仕入先
ALTER TABLE inventory ADD COLUMN supplier TEXT;

-- ロット番号
ALTER TABLE inventory ADD COLUMN lot_number TEXT;

-- 最終使用日
ALTER TABLE inventory ADD COLUMN last_used_date DATE;

-- 使用回数
ALTER TABLE inventory ADD COLUMN usage_count INTEGER DEFAULT 0;


-- ═══════════════════════════════════════════════════════════════
-- 2. inventory_transactions テーブル（入出庫履歴）
-- ═══════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS inventory_transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    inventory_id INTEGER NOT NULL REFERENCES inventory(id) ON DELETE CASCADE,
    transaction_type TEXT NOT NULL CHECK (transaction_type IN ('in', 'out', 'adjust')),
    quantity REAL NOT NULL,
    unit TEXT,
    -- 参照元の種別: csv_import, manual, pesticide_record, adjustment
    reference_type TEXT,
    -- 参照元のレコードID（防除記録ID、CSVログIDなど）
    reference_id INTEGER,
    notes TEXT,
    created_by INTEGER REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_inv_trans_inventory ON inventory_transactions(inventory_id);
CREATE INDEX IF NOT EXISTS idx_inv_trans_type ON inventory_transactions(transaction_type);
CREATE INDEX IF NOT EXISTS idx_inv_trans_created ON inventory_transactions(created_at);


-- ═══════════════════════════════════════════════════════════════
-- 3. inventory_csv_operations テーブル（CSV操作ログ）
-- ═══════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS inventory_csv_operations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    operation_type TEXT NOT NULL CHECK (operation_type IN ('import', 'export')),
    filename TEXT,
    record_count INTEGER,
    status TEXT CHECK (status IN ('success', 'partial', 'failed')),
    error_message TEXT,
    created_by INTEGER REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_csv_ops_type ON inventory_csv_operations(operation_type);
CREATE INDEX IF NOT EXISTS idx_csv_ops_created ON inventory_csv_operations(created_at);


-- ═══════════════════════════════════════════════════════════════
-- マイグレーション完了メッセージ
-- ═══════════════════════════════════════════════════════════════
SELECT 'Migration completed: inventory tables extended' AS message;
