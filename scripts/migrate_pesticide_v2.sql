-- NOTE: 新規インストールではこのマイグレーションは不要です。
-- db_schema.sql に統合済みです。
-- 既存DBからのアップグレード時のみ使用してください。

-- ═══════════════════════════════════════════════════════════════
-- 防除マスタ v2 マイグレーション
-- Created: 2026-02-11
-- Description: React版フロントエンドに合わせてpesticide_mastersテーブルを更新
-- ═══════════════════════════════════════════════════════════════

BEGIN TRANSACTION;

-- ステップ1: 新テーブルを作成
CREATE TABLE IF NOT EXISTS pesticide_masters_new (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    org_id INTEGER REFERENCES organizations(id),
    name TEXT NOT NULL,
    crop TEXT,
    category TEXT,
    manufacturer TEXT,
    active_ingredient TEXT,
    usage_timing TEXT,
    dilution_rate TEXT,
    application_method TEXT,
    safety_interval INTEGER,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ステップ2: 旧テーブルから新テーブルへデータ移行
-- 旧カラム → 新カラムのマッピング:
--   pesticide_name → name
--   days_before_harvest → safety_interval (TEXT → INTEGER 変換)
--   月・期間・対象作物・単価等は削除（新設計では不使用）
INSERT INTO pesticide_masters_new (
    id, org_id, name, crop, dilution_rate, notes, created_at
)
SELECT
    id,
    org_id,
    pesticide_name AS name,
    crop,
    dilution_rate,
    notes,
    created_at
FROM pesticide_masters;

-- ステップ3: 旧テーブルを削除
DROP TABLE pesticide_masters;

-- ステップ4: 新テーブルをリネーム
ALTER TABLE pesticide_masters_new RENAME TO pesticide_masters;

-- ステップ5: インデックスを再作成
CREATE INDEX IF NOT EXISTS idx_pesticide_masters_org ON pesticide_masters(org_id);
CREATE INDEX IF NOT EXISTS idx_pesticide_masters_crop ON pesticide_masters(crop);

COMMIT;

-- ═══════════════════════════════════════════════════════════════
-- マイグレーション実行後の確認:
--   SELECT * FROM pesticide_masters LIMIT 5;
--   PRAGMA table_info(pesticide_masters);
-- ═══════════════════════════════════════════════════════════════
