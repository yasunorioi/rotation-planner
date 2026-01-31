-- ═══════════════════════════════════════════════════════════════
-- 農薬発注テーブル マイグレーション
-- 作成日: 2026-01-31
-- 目的: 農薬発注データのDB保存機能を実現
-- ═══════════════════════════════════════════════════════════════

-- pesticide_orders テーブル作成
CREATE TABLE IF NOT EXISTS pesticide_orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    rotation_plan_id INTEGER,
    target_year TEXT NOT NULL,
    area_unit TEXT NOT NULL DEFAULT 'ha',
    order_data_json TEXT,
    status TEXT DEFAULT 'draft',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (rotation_plan_id) REFERENCES rotation_plans(id)
);

-- インデックス作成
CREATE INDEX IF NOT EXISTS idx_pesticide_orders_user_id ON pesticide_orders(user_id);
CREATE INDEX IF NOT EXISTS idx_pesticide_orders_target_year ON pesticide_orders(target_year);

-- ═══════════════════════════════════════════════════════════════
-- order_data_json の構造（参考）:
-- {
--     "summary": [
--         {"pesticide_name": "...", "amount": 10.0, "unit": "L", "crops": "...", "targets": "..."},
--         ...
--     ],
--     "details": [
--         {"month": "5月", "crop": "てんさい", "target": "ヨトウムシ", "pesticide_name": "...", "amount": 2.5, "area_ha": 5.0},
--         ...
--     ]
-- }
-- ═══════════════════════════════════════════════════════════════

-- status の値:
-- - 'draft': 下書き（計算結果を保存）
-- - 'confirmed': 確定（発注確定）
-- - 'ordered': 発注済み
-- ═══════════════════════════════════════════════════════════════
