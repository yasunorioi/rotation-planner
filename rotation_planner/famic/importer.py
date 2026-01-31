"""
rotation_planner.famic.importer - FAMICデータインポーター

FAMICの農薬登録情報XLSファイルをSQLiteにインポート。

データソース:
- https://www.acis.famic.go.jp/ddata/index.htm

ファイル形式:
- 登録基本部.xls: 農薬の基本情報（名称、有効成分等）
- 登録適用部一.xls / 登録適用部二.xls: 適用作物・使用基準
"""

import os
import sqlite3
from datetime import datetime
from typing import Dict, Optional

import xlrd


# =============================================================================
# 定数
# =============================================================================

# デフォルトDBパス
DEFAULT_DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "data", "rotation_planner.db"
)


# =============================================================================
# インポート関数
# =============================================================================

def import_famic_basic(xls_path: str, db_path: str = None) -> int:
    """
    登録基本部.xls を読み込み pesticide_registry にインポート

    Args:
        xls_path: XLSファイルパス
        db_path: DBファイルパス（省略時はデフォルト）

    Returns:
        インポート件数
    """
    if db_path is None:
        db_path = DEFAULT_DB_PATH

    if not os.path.exists(xls_path):
        raise FileNotFoundError(f"ファイルが見つかりません: {xls_path}")

    # XLS読み込み
    wb = xlrd.open_workbook(xls_path)

    # データシートを探す
    data_sheet = None
    for sheet in wb.sheets():
        if sheet.nrows > 100 and sheet.ncols >= 10:
            data_sheet = sheet
            break

    if data_sheet is None:
        raise ValueError("データシートが見つかりません")

    # ヘッダー行からカラムインデックスを特定
    headers = [str(data_sheet.cell_value(0, j)).strip() for j in range(data_sheet.ncols)]

    col_map = {
        "登録番号": headers.index("登録番号") if "登録番号" in headers else 0,
        "農薬の種類": headers.index("農薬の種類") if "農薬の種類" in headers else 1,
        "農薬の名称": headers.index("農薬の名称") if "農薬の名称" in headers else 2,
        "登録を有する者の名称": headers.index("登録を有する者の名称") if "登録を有する者の名称" in headers else 3,
        "有効成分": headers.index("有効成分") if "有効成分" in headers else 4,
        "用途": headers.index("用途") if "用途" in headers else 8,
        "剤型名": headers.index("剤型名") if "剤型名" in headers else 9,
    }

    # DB接続
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # 既存データをクリア
    cursor.execute("DELETE FROM pesticide_usage")  # 依存テーブルを先に
    cursor.execute("DELETE FROM pesticide_registry")

    # データ投入
    count = 0
    for row_idx in range(1, data_sheet.nrows):
        try:
            reg_no = data_sheet.cell_value(row_idx, col_map["登録番号"])
            if isinstance(reg_no, float):
                reg_no = str(int(reg_no))
            else:
                reg_no = str(reg_no).strip()

            if not reg_no:
                continue

            name = str(data_sheet.cell_value(row_idx, col_map["農薬の名称"])).strip()
            if not name:
                continue

            cursor.execute("""
                INSERT OR REPLACE INTO pesticide_registry
                (registration_number, name, type, manufacturer, active_ingredient, category, formulation, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (
                reg_no,
                name,
                str(data_sheet.cell_value(row_idx, col_map["農薬の種類"])).strip(),
                str(data_sheet.cell_value(row_idx, col_map["登録を有する者の名称"])).strip(),
                str(data_sheet.cell_value(row_idx, col_map["有効成分"])).strip(),
                str(data_sheet.cell_value(row_idx, col_map["用途"])).strip(),
                str(data_sheet.cell_value(row_idx, col_map["剤型名"])).strip(),
            ))
            count += 1

        except Exception as e:
            # エラー行はスキップ
            continue

    # インポートログ記録
    cursor.execute("""
        INSERT INTO famic_import_log (import_type, file_name, record_count)
        VALUES ('basic', ?, ?)
    """, (os.path.basename(xls_path), count))

    conn.commit()
    conn.close()

    return count


def import_famic_usage(xls_path: str, db_path: str = None) -> int:
    """
    登録適用部.xls を読み込み pesticide_usage にインポート

    Args:
        xls_path: XLSファイルパス（登録適用部一.xls または 登録適用部二.xls）
        db_path: DBファイルパス（省略時はデフォルト）

    Returns:
        インポート件数
    """
    if db_path is None:
        db_path = DEFAULT_DB_PATH

    if not os.path.exists(xls_path):
        raise FileNotFoundError(f"ファイルが見つかりません: {xls_path}")

    # XLS読み込み
    wb = xlrd.open_workbook(xls_path)

    # データシートを探す（行数が多いシート）
    data_sheet = None
    for sheet in wb.sheets():
        if sheet.nrows > 1000 and sheet.ncols >= 10:
            data_sheet = sheet
            break

    if data_sheet is None:
        raise ValueError("データシートが見つかりません")

    # ヘッダー行からカラムインデックスを特定
    headers = [str(data_sheet.cell_value(0, j)).strip() for j in range(data_sheet.ncols)]

    def find_col(name):
        return headers.index(name) if name in headers else -1

    col_map = {
        "登録番号": find_col("登録番号"),
        "作物名": find_col("作物名"),
        "適用病害虫雑草名": find_col("適用病害虫雑草名"),
        "使用目的": find_col("使用目的"),
        "希釈倍数使用量": find_col("希釈倍数使用量"),
        "散布液量": find_col("散布液量"),
        "使用時期": find_col("使用時期"),
        "本剤の使用回数": find_col("本剤の使用回数"),
        "使用方法": find_col("使用方法"),
    }

    # 総使用回数カラム（複数ある場合がある）
    total_usage_col = -1
    for i, h in enumerate(headers):
        if "総使用回数" in h:
            total_usage_col = i
            break

    # DB接続
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # 登録番号 → pesticide_id のマッピングを取得
    cursor.execute("SELECT registration_number, id FROM pesticide_registry")
    reg_to_id = {row[0]: row[1] for row in cursor.fetchall()}

    # データ投入
    count = 0
    for row_idx in range(1, data_sheet.nrows):
        try:
            reg_no = data_sheet.cell_value(row_idx, col_map["登録番号"])
            if isinstance(reg_no, float):
                reg_no = str(int(reg_no))
            else:
                reg_no = str(reg_no).strip()

            if not reg_no:
                continue

            # 登録番号からpesticide_idを取得
            pesticide_id = reg_to_id.get(reg_no)
            if not pesticide_id:
                continue  # 基本部にない農薬はスキップ

            crop = str(data_sheet.cell_value(row_idx, col_map["作物名"])).strip() if col_map["作物名"] >= 0 else ""
            if not crop:
                continue

            target = str(data_sheet.cell_value(row_idx, col_map["適用病害虫雑草名"])).strip() if col_map["適用病害虫雑草名"] >= 0 else ""
            purpose = str(data_sheet.cell_value(row_idx, col_map["使用目的"])).strip() if col_map["使用目的"] >= 0 else ""
            dilution = str(data_sheet.cell_value(row_idx, col_map["希釈倍数使用量"])).strip() if col_map["希釈倍数使用量"] >= 0 else ""
            spray_vol = str(data_sheet.cell_value(row_idx, col_map["散布液量"])).strip() if col_map["散布液量"] >= 0 else ""
            timing = str(data_sheet.cell_value(row_idx, col_map["使用時期"])).strip() if col_map["使用時期"] >= 0 else ""
            usage_count = str(data_sheet.cell_value(row_idx, col_map["本剤の使用回数"])).strip() if col_map["本剤の使用回数"] >= 0 else ""
            method = str(data_sheet.cell_value(row_idx, col_map["使用方法"])).strip() if col_map["使用方法"] >= 0 else ""
            total_usage = str(data_sheet.cell_value(row_idx, total_usage_col)).strip() if total_usage_col >= 0 else ""

            cursor.execute("""
                INSERT INTO pesticide_usage
                (pesticide_id, crop, target, purpose, dilution_rate, spray_volume, usage_timing, usage_count, application_method, total_usage_count)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                pesticide_id, crop, target, purpose, dilution, spray_vol, timing, usage_count, method, total_usage
            ))
            count += 1

        except Exception as e:
            # エラー行はスキップ
            continue

    # インポートログ記録
    cursor.execute("""
        INSERT INTO famic_import_log (import_type, file_name, record_count)
        VALUES ('usage', ?, ?)
    """, (os.path.basename(xls_path), count))

    conn.commit()
    conn.close()

    return count


def get_import_stats(db_path: str = None) -> Dict:
    """
    現在のインポート状況を取得

    Returns:
        {
            "registry_count": int,
            "usage_count": int,
            "last_basic_import": str or None,
            "last_usage_import": str or None,
        }
    """
    if db_path is None:
        db_path = DEFAULT_DB_PATH

    if not os.path.exists(db_path):
        return {
            "registry_count": 0,
            "usage_count": 0,
            "last_basic_import": None,
            "last_usage_import": None,
        }

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # 件数取得
    cursor.execute("SELECT COUNT(*) FROM pesticide_registry")
    registry_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM pesticide_usage")
    usage_count = cursor.fetchone()[0]

    # 最終インポート日時
    cursor.execute("""
        SELECT imported_at FROM famic_import_log
        WHERE import_type = 'basic'
        ORDER BY imported_at DESC LIMIT 1
    """)
    row = cursor.fetchone()
    last_basic = row[0] if row else None

    cursor.execute("""
        SELECT imported_at FROM famic_import_log
        WHERE import_type = 'usage'
        ORDER BY imported_at DESC LIMIT 1
    """)
    row = cursor.fetchone()
    last_usage = row[0] if row else None

    conn.close()

    return {
        "registry_count": registry_count,
        "usage_count": usage_count,
        "last_basic_import": last_basic,
        "last_usage_import": last_usage,
    }
