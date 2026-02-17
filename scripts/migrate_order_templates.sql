-- NOTE: 新規インストールではこのマイグレーションは不要です。
-- db_schema.sql に統合済みです。
-- 既存DBからのアップグレード時のみ使用してください。

-- 発注テンプレートテーブルのマイグレーション
-- 実行: sqlite3 data/rotation_planner.db < scripts/migrate_order_templates.sql

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
