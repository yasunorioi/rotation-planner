#!/usr/bin/env python3
"""
rotation_planner DBバックアップスクリプト

機能:
  - SQLiteデータベースの安全なバックアップ（sqlite3.backup使用）
  - 季節に応じたバックアップ戦略
    - アクティブ期間（12-3月）: 毎回バックアップ
    - 休眠期間（4-11月）: 差分が閾値以上の場合のみ
  - 世代管理（古いバックアップの自動削除）
  - 年度末バックアップの保護

使い方:
  python backup_db.py                    # 通常実行
  python backup_db.py --force            # 強制バックアップ
  python backup_db.py --yearly           # 年度末バックアップ（削除対象外）
  python backup_db.py --status           # 状況表示

cron設定例:
  0 3 * * * cd /var/www/rotation-planner/app && ./venv/bin/python scripts/backup_db.py
  0 4 1 4 * cd /var/www/rotation-planner/app && ./venv/bin/python scripts/backup_db.py --yearly
"""

import os
import sys
import sqlite3
import shutil
import argparse
from datetime import datetime
from pathlib import Path


# =============================================================================
# 設定
# =============================================================================

SCRIPT_DIR = Path(__file__).parent
APP_DIR = SCRIPT_DIR.parent
DB_PATH = Path(os.environ.get("DB_PATH", APP_DIR / "data" / "rotation_planner.db"))
BACKUP_DIR = Path(os.environ.get("BACKUP_DIR", APP_DIR / "data" / "backups"))

# バックアップ設定
MAX_BACKUPS = 7              # 保持する世代数（年度末バックアップ除く）
DIFF_THRESHOLD_KB = 10       # 休眠期間の差分閾値（KB）

# アクティブ期間（12月〜3月）
ACTIVE_MONTHS = {12, 1, 2, 3}


# =============================================================================
# 関数
# =============================================================================

def log(message: str):
    """ログ出力"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {message}")


def error(message: str):
    """エラー出力して終了"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] ERROR: {message}", file=sys.stderr)
    sys.exit(1)


def is_active_season() -> bool:
    """アクティブ期間（12-3月）かどうか"""
    return datetime.now().month in ACTIVE_MONTHS


def get_file_size_kb(path: Path) -> int:
    """ファイルサイズをKB単位で取得"""
    if path.exists():
        return path.stat().st_size // 1024
    return 0


def get_latest_backup() -> Path | None:
    """最新の通常バックアップを取得（年度末バックアップ除く）"""
    if not BACKUP_DIR.exists():
        return None

    backups = [
        f for f in BACKUP_DIR.glob("rotation_planner_*.db")
        if "_yearly_" not in f.name
    ]

    if not backups:
        return None

    return max(backups, key=lambda f: f.stat().st_mtime)


def should_backup(force: bool) -> bool:
    """バックアップを実行すべきか判定"""

    # 強制フラグがあれば常にバックアップ
    if force:
        log("強制バックアップモード")
        return True

    # アクティブ期間は常にバックアップ
    if is_active_season():
        log("アクティブ期間（12-3月）: バックアップ実行")
        return True

    # 休眠期間は差分チェック
    latest_backup = get_latest_backup()
    if latest_backup is None:
        log("前回バックアップなし: バックアップ実行")
        return True

    current_size = get_file_size_kb(DB_PATH)
    backup_size = get_file_size_kb(latest_backup)
    diff = abs(current_size - backup_size)

    log(f"休眠期間: DB={current_size} KB, 前回={backup_size} KB, 差分={diff} KB, 閾値={DIFF_THRESHOLD_KB} KB")

    if diff >= DIFF_THRESHOLD_KB:
        log("差分が閾値以上: バックアップ実行")
        return True
    else:
        log("差分が閾値未満: バックアップスキップ")
        return False


def do_backup(suffix: str = ""):
    """バックアップ実行"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = BACKUP_DIR / f"rotation_planner_{timestamp}{suffix}.db"

    # バックアップディレクトリ作成
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    log(f"バックアップ開始: {backup_file}")

    # sqlite3のbackup機能で安全にバックアップ
    try:
        source = sqlite3.connect(DB_PATH)
        dest = sqlite3.connect(backup_file)
        source.backup(dest)
        dest.close()
        source.close()
    except Exception as e:
        error(f"バックアップ失敗: {e}")

    if backup_file.exists():
        size = get_file_size_kb(backup_file)
        log(f"バックアップ完了: {backup_file} ({size} KB)")
    else:
        error("バックアップファイルが作成されませんでした")


def cleanup_old_backups():
    """古いバックアップを削除"""
    log(f"古いバックアップの削除（保持数: {MAX_BACKUPS}）")

    if not BACKUP_DIR.exists():
        return

    # 年度末バックアップ以外を取得
    backups = [
        f for f in BACKUP_DIR.glob("rotation_planner_*.db")
        if "_yearly_" not in f.name
    ]

    # 新しい順にソート
    backups.sort(key=lambda f: f.stat().st_mtime, reverse=True)

    # 古いものを削除
    for backup in backups[MAX_BACKUPS:]:
        log(f"削除: {backup}")
        backup.unlink()


def show_status():
    """バックアップ状況を表示"""
    log("=== バックアップ状況 ===")
    log(f"DB: {DB_PATH} ({get_file_size_kb(DB_PATH)} KB)")
    log(f"バックアップ先: {BACKUP_DIR}")

    if is_active_season():
        log("現在: アクティブ期間（毎回バックアップ）")
    else:
        log(f"現在: 休眠期間（差分{DIFF_THRESHOLD_KB}KB以上でバックアップ）")

    log("--- 既存バックアップ ---")

    if not BACKUP_DIR.exists():
        log("バックアップなし")
        return

    backups = list(BACKUP_DIR.glob("rotation_planner_*.db"))
    if not backups:
        log("バックアップなし")
        return

    backups.sort(key=lambda f: f.stat().st_mtime, reverse=True)
    for backup in backups:
        size = get_file_size_kb(backup)
        mtime = datetime.fromtimestamp(backup.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
        yearly = " [年度末]" if "_yearly_" in backup.name else ""
        log(f"  {backup.name} ({size} KB) {mtime}{yearly}")


# =============================================================================
# メイン処理
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description="rotation_planner DBバックアップ")
    parser.add_argument("--force", action="store_true", help="強制バックアップ")
    parser.add_argument("--yearly", action="store_true", help="年度末バックアップ（削除対象外）")
    parser.add_argument("--status", action="store_true", help="状況表示")
    args = parser.parse_args()

    # 状況表示モード
    if args.status:
        show_status()
        return

    # DBファイル存在確認
    if not DB_PATH.exists():
        error(f"DBファイルが見つかりません: {DB_PATH}")

    log("=== DBバックアップ開始 ===")

    # 強制フラグ（yearlyの場合も強制）
    force = args.force or args.yearly

    # バックアップ要否判定
    if should_backup(force):
        if args.yearly:
            do_backup("_yearly")
            log("年度末バックアップを作成しました（削除対象外）")
        else:
            do_backup()
            cleanup_old_backups()

    log("=== DBバックアップ終了 ===")


if __name__ == "__main__":
    main()
