-- ═══════════════════════════════════════════════════════════════
-- Migration: Add polygon tables for field registration
-- Date: 2026-02-06
-- Idempotent: safe to run multiple times
-- 実行: sqlite3 data/rotation_planner.db < scripts/migrate_field_polygons.sql
-- ═══════════════════════════════════════════════════════════════

-- 1. 水田ポリゴンテーブル
CREATE TABLE IF NOT EXISTS paddy_polygons (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    field_id INTEGER NOT NULL REFERENCES fields(id) ON DELETE CASCADE,
    geometry TEXT NOT NULL,
    area_ha REAL NOT NULL DEFAULT 0.0,
    is_converted BOOLEAN NOT NULL DEFAULT 0,
    conversion_start_year INTEGER,
    source TEXT NOT NULL DEFAULT 'manual' CHECK (source IN ('maff', 'kml', 'manual')),
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

-- 2. 作付けポリゴンテーブル
CREATE TABLE IF NOT EXISTS crop_polygons (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    field_id INTEGER NOT NULL REFERENCES fields(id) ON DELETE CASCADE,
    year INTEGER NOT NULL,
    crop_name TEXT NOT NULL,
    geometry TEXT NOT NULL,
    area_ha REAL NOT NULL DEFAULT 0.0,
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

-- 3. fields テーブルに land_category カラム追加
-- SQLite では IF NOT EXISTS が ALTER TABLE に使えないため、
-- エラーが発生した場合は既に追加済みと判断
ALTER TABLE fields ADD COLUMN land_category TEXT DEFAULT NULL;

-- 4. インデックス作成
CREATE INDEX IF NOT EXISTS idx_paddy_polygons_field_id ON paddy_polygons(field_id);
CREATE INDEX IF NOT EXISTS idx_crop_polygons_field_id_year ON crop_polygons(field_id, year);
CREATE INDEX IF NOT EXISTS idx_paddy_polygons_is_converted ON paddy_polygons(is_converted);
