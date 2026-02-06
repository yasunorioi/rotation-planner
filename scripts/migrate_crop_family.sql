-- crop_master に family（科名）列を追加するマイグレーション
-- 使い方: sqlite3 data/rotation_planner.db < scripts/migrate_crop_family.sql

-- family列追加（既に存在する場合はスキップ）
ALTER TABLE crop_master ADD COLUMN family TEXT DEFAULT NULL;

-- 北海道主要作物の科マッピング
UPDATE crop_master SET family = 'イネ科' WHERE name IN ('春小麦', '秋小麦', 'デントコーン', 'WCS');
UPDATE crop_master SET family = 'マメ科' WHERE name IN ('大豆', '小豆', 'インゲン');
UPDATE crop_master SET family = 'アカザ科' WHERE name = 'てんさい';
UPDATE crop_master SET family = 'ナス科' WHERE name = '馬鈴薯';
UPDATE crop_master SET family = 'アブラナ科' WHERE name IN ('キャベツ', 'だいこん', 'ブロッコリー', 'カリフラワー');
UPDATE crop_master SET family = 'セリ科' WHERE name = 'にんじん';
UPDATE crop_master SET family = 'ウリ科' WHERE name IN ('かぼちゃ', 'メロン');
UPDATE crop_master SET family = 'キク科' WHERE name IN ('ごぼう', 'レタス');
UPDATE crop_master SET family = 'ユリ科' WHERE name IN ('たまねぎ', 'アスパラガス', 'ながいも');

-- 確認
SELECT '=== crop_master with family ===' AS info;
SELECT id, name, family, is_active FROM crop_master ORDER BY display_order;
