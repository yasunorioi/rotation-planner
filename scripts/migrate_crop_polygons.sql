-- NOTE: 新規インストールではこのマイグレーションは不要です。
-- db_schema.sql に統合済みです。
-- 既存DBからのアップグレード時のみ使用してください。

-- =============================================================================
-- 作付けポリゴン（crop_polygons）テーブル マイグレーション
-- Wave3b: 各年度の作物配置を管理するデータ
-- =============================================================================

CREATE TABLE IF NOT EXISTS crop_polygons (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    field_id INTEGER NOT NULL,
    year INTEGER NOT NULL,
    crop_name TEXT NOT NULL,
    geometry TEXT NOT NULL,        -- GeoJSON文字列
    area_ha REAL NOT NULL,         -- 面積（ha）
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (field_id) REFERENCES fields(id)
);

CREATE INDEX IF NOT EXISTS idx_crop_polygons_field_year ON crop_polygons(field_id, year);
CREATE INDEX IF NOT EXISTS idx_crop_polygons_year ON crop_polygons(year);
