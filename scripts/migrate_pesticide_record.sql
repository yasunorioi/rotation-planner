-- ═══════════════════════════════════════════════════════════════
-- 防除記録機能 マイグレーション
-- 作成日: 2026-02-01
-- 目的: 農薬登録情報DB、防除記録管理機能を実現
-- ═══════════════════════════════════════════════════════════════

-- ═══════════════════════════════════════════════════════════════
-- 1. pesticide_registry テーブル（農薬登録情報）
-- FAMICの登録基本部データを格納
-- ═══════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS pesticide_registry (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    registration_number TEXT UNIQUE NOT NULL,  -- 農薬登録番号
    name TEXT NOT NULL,                        -- 農薬の名称
    category TEXT,                             -- 用途（殺虫剤、殺菌剤、除草剤等）
    type TEXT,                                 -- 農薬の種類
    active_ingredient TEXT,                    -- 有効成分
    manufacturer TEXT,                         -- 登録を有する者の名称
    formulation TEXT,                          -- 剤型名
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_pesticide_registry_name ON pesticide_registry(name);
CREATE INDEX IF NOT EXISTS idx_pesticide_registry_reg_no ON pesticide_registry(registration_number);

-- ═══════════════════════════════════════════════════════════════
-- 2. pesticide_usage テーブル（農薬適用情報）
-- FAMICの登録適用部データを格納
-- ═══════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS pesticide_usage (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pesticide_id INTEGER NOT NULL,             -- pesticide_registry.id へのFK
    crop TEXT NOT NULL,                        -- 作物名
    target TEXT,                               -- 適用病害虫雑草名
    purpose TEXT,                              -- 使用目的
    dilution_rate TEXT,                        -- 希釈倍数使用量
    spray_volume TEXT,                         -- 散布液量
    usage_timing TEXT,                         -- 使用時期
    usage_count TEXT,                          -- 本剤の使用回数
    application_method TEXT,                   -- 使用方法
    total_usage_count TEXT,                    -- 有効成分を含む農薬の総使用回数
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (pesticide_id) REFERENCES pesticide_registry(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_pesticide_usage_pesticide ON pesticide_usage(pesticide_id);
CREATE INDEX IF NOT EXISTS idx_pesticide_usage_crop ON pesticide_usage(crop);

-- ═══════════════════════════════════════════════════════════════
-- 3. pesticide_records テーブル（防除記録）
-- 農家が散布した農薬の記録
-- ═══════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS pesticide_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,                  -- users.id へのFK
    field_id INTEGER NOT NULL,                 -- fields.id へのFK
    spray_date DATE NOT NULL,                  -- 散布日
    pesticide_name TEXT NOT NULL,              -- 農薬名（手入力も可）
    pesticide_id INTEGER,                      -- pesticide_registry.id（任意、紐付け用）
    dilution_rate TEXT,                        -- 希釈倍率
    spray_amount REAL,                         -- 散布量
    spray_unit TEXT,                           -- 散布量単位（L, kg 等）
    photo_path TEXT,                           -- 写真ファイルパス
    notes TEXT,                                -- 備考
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (field_id) REFERENCES fields(id) ON DELETE CASCADE,
    FOREIGN KEY (pesticide_id) REFERENCES pesticide_registry(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_pesticide_records_user ON pesticide_records(user_id);
CREATE INDEX IF NOT EXISTS idx_pesticide_records_field ON pesticide_records(field_id);
CREATE INDEX IF NOT EXISTS idx_pesticide_records_date ON pesticide_records(spray_date);

-- ═══════════════════════════════════════════════════════════════
-- 4. famic_import_log テーブル（FAMICインポート履歴）
-- データ更新履歴を管理
-- ═══════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS famic_import_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    import_type TEXT NOT NULL,                 -- 'basic' or 'usage'
    file_name TEXT,                            -- インポートしたファイル名
    record_count INTEGER,                      -- インポート件数
    imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
