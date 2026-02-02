-- ═══════════════════════════════════════════════════════════════
-- 農業管理アプリ - SQLiteスキーマ
-- Version: 1.2
-- Created: 2026-01-29
-- Updated: 2026-02-02
-- ═══════════════════════════════════════════════════════════════
--
-- 組織(org_id)について:
--   現在は単一JA想定。org_id=1がJA、org_id=2が個人農家。
--   将来の複数JA対応時は、組織ごとのデータ分離を実装する。
--   防除マスタはorg_id=NULLが共通、org_id指定が組織固有。
--
-- ═══════════════════════════════════════════════════════════════

-- 外部キー制約を有効化
PRAGMA foreign_keys = ON;

-- ═══════════════════════════════════════════════════════════════
-- 1. 組織マスタ（JA、個人農家グループ等）
--    現状: id=1 JA北海道, id=2 個人農家（デフォルト）
--    将来: 複数JAに対応する場合は行を追加
-- ═══════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS organizations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    type TEXT NOT NULL CHECK (type IN ('JA', 'cooperative', 'individual')),
    settings_json TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ═══════════════════════════════════════════════════════════════
-- 2. ユーザー（農家、JA職員）
-- ═══════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    display_name TEXT NOT NULL,
    email TEXT,
    role TEXT NOT NULL CHECK (role IN ('farmer', 'ja_staff', 'admin')),
    org_id INTEGER REFERENCES organizations(id),
    is_active INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_users_org ON users(org_id);
CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);

-- ═══════════════════════════════════════════════════════════════
-- 3. ほ場
-- ═══════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS fields (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    field_code TEXT NOT NULL,
    district TEXT,
    name TEXT,
    area_ha REAL NOT NULL,
    area_a REAL GENERATED ALWAYS AS (area_ha * 100) STORED,
    beet_forbidden INTEGER DEFAULT 0,
    coordinates_json TEXT,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, field_code)
);
CREATE INDEX IF NOT EXISTS idx_fields_user ON fields(user_id);
CREATE INDEX IF NOT EXISTS idx_fields_district ON fields(district);

-- ═══════════════════════════════════════════════════════════════
-- 4. 作付履歴
-- ═══════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS crop_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    field_id INTEGER NOT NULL REFERENCES fields(id) ON DELETE CASCADE,
    year TEXT NOT NULL,
    crop TEXT NOT NULL,
    is_inferred INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(field_id, year)
);
CREATE INDEX IF NOT EXISTS idx_crop_history_field ON crop_history(field_id);
CREATE INDEX IF NOT EXISTS idx_crop_history_year ON crop_history(year);

-- ═══════════════════════════════════════════════════════════════
-- 5. 輪作計画
-- ═══════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS rotation_plans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    start_year TEXT NOT NULL,
    end_year TEXT NOT NULL,
    constraints_json TEXT,
    metadata_json TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_rotation_plans_user ON rotation_plans(user_id);

-- ═══════════════════════════════════════════════════════════════
-- 6. 輪作計画詳細（計画されたほ場×年の作付）
-- ═══════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS plan_details (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    plan_id INTEGER NOT NULL REFERENCES rotation_plans(id) ON DELETE CASCADE,
    field_id INTEGER NOT NULL REFERENCES fields(id) ON DELETE CASCADE,
    year TEXT NOT NULL,
    crop TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(plan_id, field_id, year)
);
CREATE INDEX IF NOT EXISTS idx_plan_details_plan ON plan_details(plan_id);
CREATE INDEX IF NOT EXISTS idx_plan_details_field ON plan_details(field_id);

-- ═══════════════════════════════════════════════════════════════
-- 7. 防除マスタ（組織単位で共有）
-- ═══════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS pesticide_masters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    org_id INTEGER REFERENCES organizations(id),
    crop TEXT NOT NULL,
    month INTEGER,
    period TEXT,
    target TEXT,
    pesticide_name TEXT NOT NULL,
    dilution_rate TEXT,
    amount_per_10a REAL,
    unit TEXT,
    days_before_harvest TEXT,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_pesticide_masters_org ON pesticide_masters(org_id);
CREATE INDEX IF NOT EXISTS idx_pesticide_masters_crop ON pesticide_masters(crop);

-- ═══════════════════════════════════════════════════════════════
-- 8. ユーザー輪作制約設定
--    ユーザーごとの制約テーブル・禁止遷移・優先遷移・主作物を保存
-- ═══════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS user_constraints (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    constraints_json TEXT NOT NULL,
    forbidden_transitions TEXT,
    preferred_transitions TEXT,
    main_crops TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id)
);
CREATE INDEX IF NOT EXISTS idx_user_constraints_user ON user_constraints(user_id);

-- ═══════════════════════════════════════════════════════════════
-- 9. 発注テンプレート（ユーザー別カスタムテンプレート）
--    type: default=デフォルト, history=過去履歴ベース, custom=カスタム
-- ═══════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS order_templates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    type TEXT NOT NULL DEFAULT 'custom' CHECK (type IN ('default', 'history', 'custom')),
    items_json TEXT NOT NULL,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, name)
);
CREATE INDEX IF NOT EXISTS idx_order_templates_user ON order_templates(user_id);

-- ═══════════════════════════════════════════════════════════════
-- 10. 在庫
-- ═══════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS inventory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    pesticide_name TEXT NOT NULL,
    amount REAL NOT NULL,
    unit TEXT NOT NULL,
    storage_location TEXT,           -- 保管場所
    expiry_date DATE,                -- 有効期限
    purchase_date DATE,              -- 購入日
    purchase_price REAL,             -- 購入価格
    supplier TEXT,                   -- 仕入先
    lot_number TEXT,                 -- ロット番号
    last_used_date DATE,             -- 最終使用日
    usage_count INTEGER DEFAULT 0,   -- 使用回数
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, pesticide_name)
);
CREATE INDEX IF NOT EXISTS idx_inventory_user ON inventory(user_id);

-- ═══════════════════════════════════════════════════════════════
-- 11. 在庫入出庫履歴
-- ═══════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS inventory_transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    inventory_id INTEGER NOT NULL REFERENCES inventory(id) ON DELETE CASCADE,
    transaction_type TEXT NOT NULL CHECK (transaction_type IN ('in', 'out', 'adjust')),
    quantity REAL NOT NULL,
    unit TEXT,
    reference_type TEXT,             -- 'csv_import', 'manual', 'pesticide_record', 'adjustment'
    reference_id INTEGER,            -- 関連レコードID
    notes TEXT,
    created_by INTEGER REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_inv_trans_inventory ON inventory_transactions(inventory_id);
CREATE INDEX IF NOT EXISTS idx_inv_trans_type ON inventory_transactions(transaction_type);
CREATE INDEX IF NOT EXISTS idx_inv_trans_created ON inventory_transactions(created_at);

-- ═══════════════════════════════════════════════════════════════
-- 12. CSV操作ログ
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
-- 初期データ: デフォルト組織
-- ═══════════════════════════════════════════════════════════════
INSERT OR IGNORE INTO organizations (id, name, type, settings_json)
VALUES (1, 'JA北海道', 'JA', '{"region": "北海道", "default_crops": ["春小麦", "秋小麦", "大豆", "てんさい", "馬鈴薯"]}');

INSERT OR IGNORE INTO organizations (id, name, type, settings_json)
VALUES (2, '個人農家（デフォルト）', 'individual', '{}');
