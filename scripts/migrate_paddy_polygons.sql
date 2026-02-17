-- NOTE: 新規インストールではこのマイグレーションは不要です。
-- db_schema.sql に統合済みです。
-- 既存DBからのアップグレード時のみ使用してください。

-- 水田ポリゴン（paddy_polygons）テーブル作成マイグレーション
-- 使い方: sqlite3 data/rotation_planner.db < scripts/migrate_paddy_polygons.sql
-- 冪等: 複数回実行してもエラーにならない（CREATE TABLE IF NOT EXISTS）

CREATE TABLE IF NOT EXISTS paddy_polygons (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    field_id INTEGER NOT NULL,
    geometry TEXT NOT NULL,
    area_ha REAL NOT NULL,
    is_converted INTEGER DEFAULT 0,
    conversion_start_year INTEGER,
    source TEXT DEFAULT 'manual',
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (field_id) REFERENCES fields(id)
);

CREATE INDEX IF NOT EXISTS idx_paddy_polygons_field_id ON paddy_polygons(field_id);

-- 確認
SELECT '=== paddy_polygons table ===' AS info;
SELECT count(*) AS row_count FROM paddy_polygons;
