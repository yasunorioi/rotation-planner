-- VPS用 作物スキーマ マイグレーション
-- 使い方: sqlite3 data/rotation_planner.db < scripts/migrate_crop_schema.sql

-- 古いテーブルを削除
DROP TABLE IF EXISTS user_crops;
DROP TABLE IF EXISTS crop_master;

-- crop_master テーブル作成
CREATE TABLE crop_master (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    family TEXT DEFAULT NULL,
    display_order INTEGER DEFAULT 0,
    is_active INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- user_crops テーブル作成
CREATE TABLE user_crops (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    parent_crop_id INTEGER NOT NULL,
    custom_name TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (parent_crop_id) REFERENCES crop_master(id),
    UNIQUE(user_id, parent_crop_id, custom_name)
);

-- 初期作物データ
INSERT INTO crop_master (name, family, display_order) VALUES ('春小麦', 'イネ科', 1);
INSERT INTO crop_master (name, family, display_order) VALUES ('秋小麦', 'イネ科', 2);
INSERT INTO crop_master (name, family, display_order) VALUES ('大豆', 'マメ科', 3);
INSERT INTO crop_master (name, family, display_order) VALUES ('てんさい', 'アカザ科', 4);
INSERT INTO crop_master (name, family, display_order) VALUES ('馬鈴薯', 'ナス科', 5);

-- 確認
SELECT '=== crop_master ===' AS info;
SELECT * FROM crop_master;
SELECT '=== user_crops ===' AS info;
SELECT * FROM user_crops;
