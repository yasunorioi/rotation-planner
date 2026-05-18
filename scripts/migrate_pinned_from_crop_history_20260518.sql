-- ====================================================================
-- 既存 crop_history 未来年 -> pinned_assignments 一括マイグレーション
-- cmd_586 subtask_1260 (Wave 3)・冪等 (INSERT OR IGNORE)
-- 殿動作確認部分OK・R9以降の既存データを pinned_assignments に投入
-- ====================================================================
-- 実体schema準拠: pinned_assignments(id, user_id, field_id, year TEXT, crop TEXT,
--   pinned_by, pinned_reason, is_active DEFAULT 1, notes, created_at, updated_at)
-- 部屋子1判断: 対象範囲=全ユーザの未来年(現在年度+1以降・2027以降)
-- Q2=a 過去年pin禁止(cmd_584殿裁定)踏襲: 現在年度未満は対象外
-- pinned_by=NULL (システムマイグレーション・代行登録ではない)
-- notes に migration マーカー(rollback時の LIKE 識別用)

INSERT OR IGNORE INTO pinned_assignments
    (user_id, field_id, year, crop, is_active, notes)
SELECT
    f.user_id,
    ch.field_id,
    ch.year,
    ch.crop,
    1,
    'migrated_from_crop_history_subtask_1260_20260518'
FROM crop_history ch
JOIN fields f ON ch.field_id = f.id
WHERE CAST(ch.year AS INTEGER) >= 2027;

-- 検証クエリ
-- SELECT count(*) FROM pinned_assignments WHERE notes LIKE 'migrated_from_crop_history_subtask_1260%';
-- 期待: 14件 (yasu R9=2027 9件+R10=2028 5件・実行時の crop_history 未来年内容に依存)

-- rollback (1行で戻せる)
-- DELETE FROM pinned_assignments WHERE notes LIKE 'migrated_from_crop_history_subtask_1260%';
