-- NOTE: 新規インストールではこのマイグレーションは不要です。
-- db_schema.sql に統合済みです。
-- 既存DBからのアップグレード時のみ使用してください。

-- crop_master に family（科名）列を追加するマイグレーション
-- 使い方: sqlite3 data/rotation_planner.db < scripts/migrate_crop_family.sql
-- 冪等: 複数回実行してもエラーにならない

-- family列追加（SQLiteはIF NOT EXISTSをサポートしないためPRAGMAで確認）
-- ALTER TABLE は列が既に存在する場合エラーになるが、
-- 以下のトリックで冪等にする
CREATE TABLE IF NOT EXISTS _migration_log (
    migration TEXT PRIMARY KEY,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

INSERT OR IGNORE INTO _migration_log (migration) VALUES ('add_crop_family');

-- family列がなければ追加（エラー時は無視されるようにBEGIN/COMMITの外で実行）
ALTER TABLE crop_master ADD COLUMN family TEXT DEFAULT NULL;

-- 北海道主要作物の科マッピング
-- FAMIC表記（React版初期データ）とGradio版表記の両方を対象に含む
UPDATE crop_master SET family = 'イネ科' WHERE name IN ('小麦(春播)', '小麦(秋播)', '春小麦', '秋小麦', 'スイートコーン', 'デントコーン', 'WCS');
UPDATE crop_master SET family = 'マメ科' WHERE name IN ('だいず', '大豆', 'あずき', '小豆', 'インゲン');
UPDATE crop_master SET family = 'アカザ科' WHERE name = 'てんさい';
UPDATE crop_master SET family = 'ナス科' WHERE name IN ('ばれいしょ', '馬鈴薯');
UPDATE crop_master SET family = 'アブラナ科' WHERE name IN ('キャベツ', 'だいこん', 'ブロッコリー', 'カリフラワー');
UPDATE crop_master SET family = 'セリ科' WHERE name = 'にんじん';
UPDATE crop_master SET family = 'ウリ科' WHERE name IN ('かぼちゃ', 'メロン');
UPDATE crop_master SET family = 'キク科' WHERE name IN ('ごぼう', 'レタス');
UPDATE crop_master SET family = 'ユリ科' WHERE name IN ('たまねぎ', 'アスパラガス', 'ながいも');

-- 確認
SELECT '=== crop_master with family ===' AS info;
SELECT id, name, family, is_active FROM crop_master ORDER BY display_order;
