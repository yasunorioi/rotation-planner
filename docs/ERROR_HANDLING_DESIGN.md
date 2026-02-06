# rotation-planner エラー処理 統合設計書

**プロジェクト**: rotation-planner
**技術スタック**: Gradio 4.x + SQLite + Python
**作成日**: 2026-02-06
**Version**: 1.0

---

## 1. 概要

### 1.1 目的

本ドキュメントは、rotation-plannerのエラー処理を体系的に設計・実装するための統合設計書である。
以下の3つの設計書を統合している：

| ドキュメント | 担当 | 内容 |
|-------------|------|------|
| ERROR_ANALYSIS.md | 足軽5号 | 現状分析、エラー発生箇所特定 |
| ERROR_DB_VALIDATION.md | 足軽6号 | DB操作エラー、入力バリデーション |
| ERROR_FILE_UI.md | 足軽7号 | ファイル操作エラー、ユーザー通知UI |

### 1.2 設計方針

1. **ユーザーファースト**: 技術用語を避け、解決策を提示する
2. **ログ記録**: 全てのエラーをログに記録し、トラブルシュートを容易に
3. **データ保護**: トランザクション管理でデータ整合性を保証
4. **入力段階での防止**: バリデーションで不正データをブロック
5. **段階的適用**: 既存コードへの影響を最小限に

### 1.3 現状の課題（ERROR_ANALYSIS.mdより）

| 課題 | 件数 | 影響 |
|------|------|------|
| 裸の`except:`使用 | 25箇所 | 例外の種類が不明、デバッグ困難 |
| ログ機構なし | 0箇所 | 本番エラーの追跡不可 |
| Gradio標準通知未使用 | 未使用 | ユーザー通知が不十分 |
| エラー黙殺 | 15% | 問題の見逃し |

---

## 2. アーキテクチャ概要

### 2.1 エラー処理レイヤー

```
┌─────────────────────────────────────────────────────────────┐
│  UI Layer (Gradio)                                          │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  gr.Info / gr.Warning / gr.Error                    │    │
│  │  ユーザー向けメッセージ表示                          │    │
│  └─────────────────────────────────────────────────────┘    │
├─────────────────────────────────────────────────────────────┤
│  Handler Layer (イベントハンドラ)                            │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  @safe_handler デコレータ                           │    │
│  │  例外をキャッチし、UI通知 + ログ記録                  │    │
│  └─────────────────────────────────────────────────────┘    │
├─────────────────────────────────────────────────────────────┤
│  Validation Layer (入力バリデーション)                       │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  ValidationResult / ValidationError                 │    │
│  │  エンティティ別バリデーション関数                     │    │
│  └─────────────────────────────────────────────────────┘    │
├─────────────────────────────────────────────────────────────┤
│  Service Layer (ビジネスロジック)                            │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  read_csv_safe / write_csv_safe                     │    │
│  │  generate_pdf_safe                                  │    │
│  │  ファイル操作の安全ラッパー                          │    │
│  └─────────────────────────────────────────────────────┘    │
├─────────────────────────────────────────────────────────────┤
│  Data Layer (リポジトリ層)                                   │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  @handle_db_error デコレータ                        │    │
│  │  トランザクション管理 (transaction())               │    │
│  │  カスタム例外 (DuplicateKeyError, etc.)             │    │
│  └─────────────────────────────────────────────────────┘    │
├─────────────────────────────────────────────────────────────┤
│  Infrastructure Layer                                        │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  logging (RotatingFileHandler)                      │    │
│  │  SQLite (PRAGMA設定, WALモード)                     │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 例外クラス階層

```python
Exception
├── RotationPlannerError          # アプリ固有エラーの基底
│   ├── DatabaseError             # DB操作エラー
│   │   ├── DatabaseConnectionError   # 接続エラー
│   │   ├── DuplicateKeyError         # 重複キー
│   │   ├── NotNullViolationError     # NOT NULL違反
│   │   ├── ForeignKeyViolationError  # FK制約違反
│   │   └── RecordNotFoundError       # レコードなし
│   ├── FileOperationError        # ファイル操作エラー
│   │   ├── CSVReadError              # CSV読み込みエラー
│   │   ├── CSVWriteError             # CSV書き出しエラー
│   │   └── PDFGenerationError        # PDF生成エラー
│   └── ValidationError           # バリデーションエラー
└── (Python標準例外)
```

---

## 3. カスタム例外クラス定義

```python
# rotation_planner/common/exceptions.py

class RotationPlannerError(Exception):
    """アプリケーション固有エラーの基底クラス"""
    def __init__(self, message: str, user_message: str = None):
        self.message = message
        self.user_message = user_message or message
        super().__init__(message)


# === DB関連 ===
class DatabaseError(RotationPlannerError):
    """DB操作エラーの基底クラス"""
    pass

class DatabaseConnectionError(DatabaseError):
    """DB接続エラー"""
    pass

class DuplicateKeyError(DatabaseError):
    """重複キーエラー"""
    pass

class NotNullViolationError(DatabaseError):
    """NOT NULL制約違反"""
    pass

class ForeignKeyViolationError(DatabaseError):
    """外部キー制約違反"""
    pass

class RecordNotFoundError(DatabaseError):
    """対象レコードなし"""
    pass


# === ファイル操作関連 ===
class FileOperationError(RotationPlannerError):
    """ファイル操作エラーの基底クラス"""
    def __init__(self, message: str, recoverable: bool = False):
        super().__init__(message)
        self.recoverable = recoverable

class CSVReadError(FileOperationError):
    """CSV読み込みエラー"""
    pass

class CSVWriteError(FileOperationError):
    """CSV書き出しエラー"""
    pass

class PDFGenerationError(FileOperationError):
    """PDF生成エラー"""
    pass


# === バリデーション関連 ===
class ValidationError(RotationPlannerError):
    """バリデーションエラー"""
    def __init__(self, field: str, message: str, value=None):
        self.field = field
        self.value = value
        super().__init__(message)
```

---

## 4. DB操作エラー設計

### 4.1 接続管理

```python
# rotation_planner/common/db.py

import sqlite3
import logging
from pathlib import Path
from contextlib import contextmanager
from .exceptions import DatabaseConnectionError

logger = logging.getLogger(__name__)
DB_PATH = "data/rotation.db"


def get_connection():
    """データベース接続を取得"""
    try:
        db_path = Path(DB_PATH)
        if not db_path.parent.exists():
            db_path.parent.mkdir(parents=True)

        conn = sqlite3.connect(DB_PATH, timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        return conn

    except sqlite3.OperationalError as e:
        logger.error(f"DB接続失敗: {e}")
        raise DatabaseConnectionError(
            f"DB接続失敗: {e}",
            user_message="データベースに接続できません。管理者に連絡してください。"
        )


@contextmanager
def transaction():
    """トランザクションコンテキストマネージャー"""
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"トランザクション失敗、ロールバック: {e}")
        raise
    finally:
        conn.close()
```

### 4.2 CRUD操作のエラー処理

```python
# rotation_planner/common/db_access.py

import sqlite3
from .exceptions import (
    DatabaseError, DuplicateKeyError, NotNullViolationError,
    ForeignKeyViolationError, RecordNotFoundError
)
from .db import get_connection

logger = logging.getLogger(__name__)


def insert_crop(name: str, family: str, interval_years: int):
    """作物を登録"""
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO crops (name, family, interval_years)
            VALUES (?, ?, ?)
        """, (name, family, interval_years))
        conn.commit()
        logger.info(f"作物登録成功: {name}")
        return cursor.lastrowid

    except sqlite3.IntegrityError as e:
        error_msg = str(e).lower()
        if "unique constraint" in error_msg:
            logger.warning(f"重複キー: {name}")
            raise DuplicateKeyError(f"「{name}」は既に登録されています")
        elif "not null constraint" in error_msg:
            raise NotNullViolationError("必須項目が入力されていません")
        elif "foreign key constraint" in error_msg:
            raise ForeignKeyViolationError("参照先のデータが存在しません")
        else:
            raise DatabaseError(f"整合性エラー: {e}")

    except sqlite3.Error as e:
        logger.error(f"INSERT失敗: {e}")
        raise DatabaseError(f"データの登録に失敗しました")

    finally:
        if conn:
            conn.close()
```

### 4.3 DBエラーハンドリングデコレータ

```python
def handle_db_error(func):
    """DBエラーハンドリングデコレータ"""
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except DuplicateKeyError as e:
            return None, str(e)
        except NotNullViolationError as e:
            return None, str(e)
        except ForeignKeyViolationError as e:
            return None, str(e)
        except RecordNotFoundError as e:
            return None, str(e)
        except DatabaseConnectionError as e:
            logger.critical(f"DB接続エラー: {e}")
            return None, "データベースに接続できません。管理者に連絡してください。"
        except DatabaseError as e:
            return None, str(e)
        except Exception as e:
            logger.exception(f"予期しないエラー: {e}")
            return None, "予期しないエラーが発生しました"
    return wrapper
```

---

## 5. ファイル操作エラー設計

### 5.1 CSV読み込み

```python
# rotation_planner/common/file_utils.py

import os
import pandas as pd
from pathlib import Path
from typing import Tuple, List
from .exceptions import CSVReadError

logger = logging.getLogger(__name__)


def read_csv_safe(
    file_path,
    required_columns: List[str] = None,
    optional_columns: List[str] = None
) -> Tuple[pd.DataFrame, List[str]]:
    """
    安全なCSV読み込み

    Returns:
        (DataFrame, warnings)

    Raises:
        CSVReadError
    """
    warnings = []

    # パス解決
    if hasattr(file_path, 'name'):
        actual_path = Path(file_path.name)
    elif isinstance(file_path, (str, Path)):
        actual_path = Path(file_path)
    else:
        raise CSVReadError("不正なファイル形式です", recoverable=False)

    # ファイル存在チェック
    if not actual_path.exists():
        raise CSVReadError(f"ファイルが見つかりません: {actual_path.name}")

    # 権限チェック
    if not os.access(actual_path, os.R_OK):
        raise CSVReadError(f"ファイルの読み取り権限がありません")

    # 空ファイルチェック
    if actual_path.stat().st_size == 0:
        raise CSVReadError("ファイルが空です")

    # エンコーディング自動判定
    encodings = ['utf-8-sig', 'utf-8', 'shift-jis', 'cp932']
    df = None

    for enc in encodings:
        try:
            df = pd.read_csv(actual_path, encoding=enc)
            break
        except UnicodeDecodeError:
            continue
        except pd.errors.EmptyDataError:
            raise CSVReadError("CSVにデータがありません")
        except pd.errors.ParserError as e:
            raise CSVReadError(f"CSV形式エラー: {str(e)[:100]}")

    if df is None:
        raise CSVReadError("文字コードを認識できません。UTF-8で保存してください。")

    # 必須カラムチェック
    if required_columns:
        missing = [c for c in required_columns if c not in df.columns]
        if missing:
            raise CSVReadError(f"必須カラムがありません: {', '.join(missing)}")

    # オプションカラム警告
    if optional_columns:
        missing_opt = [c for c in optional_columns if c not in df.columns]
        if missing_opt:
            warnings.append(f"オプションカラムなし: {', '.join(missing_opt)}")

    logger.info(f"CSV読み込み成功: {actual_path.name}, {len(df)}行")
    return df, warnings
```

### 5.2 CSV書き出し

```python
import shutil
import tempfile
from datetime import datetime
from .exceptions import CSVWriteError


def write_csv_safe(
    df: pd.DataFrame,
    output_dir: str = "/tmp",
    filename: str = None,
    encoding: str = "utf-8-sig"
) -> Tuple[str, str]:
    """
    安全なCSV書き出し

    Returns:
        (filepath, message)

    Raises:
        CSVWriteError
    """
    # データ存在チェック
    if df is None or df.empty:
        raise CSVWriteError("出力するデータがありません")

    output_path = Path(output_dir)

    # ディレクトリ作成
    if not output_path.exists():
        try:
            output_path.mkdir(parents=True, exist_ok=True)
        except PermissionError:
            raise CSVWriteError(f"出力フォルダを作成できません")

    # 書き込み権限チェック
    if not os.access(output_path, os.W_OK):
        raise CSVWriteError(f"書き込み権限がありません")

    # ディスク容量チェック
    estimated_size = len(df) * 100
    free_space = shutil.disk_usage(output_path).free
    if free_space < estimated_size * 2:
        raise CSVWriteError("ディスク容量が不足しています")

    # ファイル名生成
    if filename is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"export_{timestamp}.csv"

    filepath = output_path / filename

    # 一時ファイル経由で書き込み（原子性確保）
    try:
        with tempfile.NamedTemporaryFile(
            mode='w', suffix='.csv', delete=False,
            encoding=encoding, newline=''
        ) as tmp:
            df.to_csv(tmp, index=False)
            tmp_path = tmp.name

        shutil.move(tmp_path, filepath)
        logger.info(f"CSV出力成功: {filepath}, {len(df)}行")

    except PermissionError:
        raise CSVWriteError("ファイルを保存できません（使用中？）")
    except OSError as e:
        if "No space left" in str(e):
            raise CSVWriteError("ディスク容量が不足しています")
        raise CSVWriteError(f"ファイル保存エラー: {str(e)[:100]}")

    return str(filepath), f"CSVを出力しました（{len(df)}件）"
```

---

## 6. 入力バリデーション設計

### 6.1 バリデーション結果クラス

```python
# rotation_planner/common/validation.py

from dataclasses import dataclass
from typing import Optional, List


@dataclass
class FieldError:
    """フィールドエラー"""
    field: str
    message: str
    value: Optional[str] = None


class ValidationResult:
    """バリデーション結果"""
    def __init__(self):
        self.errors: List[FieldError] = []

    def add_error(self, field: str, message: str, value: Optional[str] = None):
        self.errors.append(FieldError(field, message, value))

    def is_valid(self) -> bool:
        return len(self.errors) == 0

    def get_error_messages(self) -> List[str]:
        return [f"{e.field}: {e.message}" for e in self.errors]

    def get_first_error(self) -> Optional[str]:
        if self.errors:
            return f"{self.errors[0].field}: {self.errors[0].message}"
        return None
```

### 6.2 バリデーション関数

```python
def validate_required(value, field_name: str, result: ValidationResult):
    """必須チェック"""
    if value is None or str(value).strip() == "":
        result.add_error(field_name, "入力してください", value)
        return False
    return True


def validate_string_length(value: str, field_name: str,
                          min_len: int, max_len: int,
                          result: ValidationResult):
    """文字数チェック"""
    length = len(str(value).strip())
    if length < min_len:
        result.add_error(field_name, f"{min_len}文字以上で入力してください", value)
        return False
    if length > max_len:
        result.add_error(field_name, f"{max_len}文字以内で入力してください", value)
        return False
    return True


def validate_range(value: float, field_name: str,
                  min_val: float, max_val: float,
                  result: ValidationResult):
    """範囲チェック"""
    if value < min_val:
        result.add_error(field_name, f"{min_val}以上を入力してください", str(value))
        return False
    if value > max_val:
        result.add_error(field_name, f"{max_val}以下を入力してください", str(value))
        return False
    return True
```

### 6.3 エンティティ別バリデーション

```python
def validate_crop(name: str, family: str, interval_years) -> ValidationResult:
    """作物入力のバリデーション"""
    result = ValidationResult()

    if validate_required(name, "作物名", result):
        validate_string_length(name, "作物名", 1, 50, result)

    if validate_required(family, "科名", result):
        validate_string_length(family, "科名", 1, 30, result)

    if validate_required(interval_years, "輪作間隔", result):
        try:
            val = int(interval_years)
            validate_range(val, "輪作間隔", 1, 10, result)
        except (ValueError, TypeError):
            result.add_error("輪作間隔", "整数を入力してください")

    return result


def validate_field(name: str, area) -> ValidationResult:
    """圃場入力のバリデーション"""
    result = ValidationResult()

    if validate_required(name, "圃場名", result):
        validate_string_length(name, "圃場名", 1, 50, result)

    if area is not None and str(area).strip() != "":
        try:
            val = float(area)
            validate_range(val, "面積", 0.01, 1000, result)
        except (ValueError, TypeError):
            result.add_error("面積", "数値を入力してください")

    return result
```

---

## 7. ユーザー通知UI設計

### 7.1 Gradio通知の使い分け

| 関数 | 用途 | 自動消去 |
|------|------|---------|
| `gr.Info(message)` | 成功通知、情報提供 | 5秒 |
| `gr.Warning(message)` | 警告（続行可能） | 10秒 |
| `gr.Error(message)` | 致命的エラー | 消えない |

### 7.2 メッセージテンプレート

```python
# rotation_planner/common/messages.py

MESSAGES = {
    # 成功
    "save_success": "✅ 保存しました（{count}件）",
    "import_success": "✅ インポートしました（{count}件）",
    "export_success": "✅ ダウンロード準備完了",
    "delete_success": "✅ 削除しました",

    # 警告
    "partial_import": "⚠️ 一部スキップしました（{skipped}件）",
    "missing_optional": "⚠️ オプション項目なし: {columns}",
    "duplicate_found": "⚠️ 重複データあり（{count}件）",

    # エラー
    "file_not_found": "📁 ファイルが見つかりません",
    "file_permission": "📁 ファイルを開けません（使用中？）",
    "encoding_error": "📁 文字コードを認識できません（UTF-8推奨）",
    "missing_required": "📁 必須項目なし: {columns}",
    "disk_full": "💾 ディスク容量不足",
    "db_error": "🗄️ データベースエラー",
    "unexpected": "⚠️ 予期せぬエラーが発生しました",
}


def get_message(key: str, **kwargs) -> str:
    """メッセージテンプレートを取得"""
    template = MESSAGES.get(key, MESSAGES["unexpected"])
    try:
        return template.format(**kwargs)
    except KeyError:
        return template
```

### 7.3 安全ハンドラデコレータ

```python
# rotation_planner/common/handlers.py

import gradio as gr
from functools import wraps
from typing import Any, Callable
from .exceptions import (
    CSVReadError, CSVWriteError, DatabaseError, DatabaseConnectionError
)

logger = logging.getLogger(__name__)


def safe_handler(default_return: Any = None, show_traceback: bool = False):
    """
    Gradioイベントハンドラ用の安全ラッパー

    使用例:
        @safe_handler(default_return=(None, "エラー"))
        def my_handler(input1, input2):
            return result, message
    """
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)

            except CSVReadError as e:
                gr.Error(e.message)
                logger.warning(f"CSV読み込みエラー: {e.message}")
                return default_return

            except CSVWriteError as e:
                gr.Error(e.message)
                logger.warning(f"CSV書き出しエラー: {e.message}")
                return default_return

            except DatabaseConnectionError as e:
                gr.Error("データベースに接続できません")
                logger.critical(f"DB接続エラー: {e}")
                return default_return

            except DatabaseError as e:
                gr.Error(str(e))
                logger.error(f"DBエラー: {e}")
                return default_return

            except PermissionError:
                gr.Error("アクセス権限がありません")
                logger.error("権限エラー")
                return default_return

            except Exception as e:
                gr.Error(f"予期せぬエラー: {str(e)[:100]}")
                if show_traceback:
                    import traceback
                    logger.error(traceback.format_exc())
                else:
                    logger.error(f"エラー: {e}")
                return default_return

        return wrapper
    return decorator
```

### 7.4 使用例

```python
import gradio as gr
from rotation_planner.common.handlers import safe_handler
from rotation_planner.common.file_utils import read_csv_safe
from rotation_planner.common.validation import validate_crop


@safe_handler(default_return=(None, "エラー"))
def handle_csv_import(file, user_state):
    """CSVインポートハンドラ"""
    if file is None:
        gr.Warning("ファイルを選択してください")
        return None, "ファイル未選択"

    df, warnings = read_csv_safe(
        file,
        required_columns=["農薬名"],
        optional_columns=["必要量", "単位"]
    )

    for warn in warnings:
        gr.Warning(warn)

    gr.Info(f"✅ {len(df)}件読み込みました")
    return df.to_dict('records'), f"{len(df)}件完了"


@safe_handler(default_return=(None, "エラー"))
def handle_crop_submit(name, family, interval_years):
    """作物登録ハンドラ"""
    # バリデーション
    result = validate_crop(name, family, interval_years)
    if not result.is_valid():
        error_msg = result.get_first_error()
        gr.Error(error_msg)
        return None, error_msg

    # DB登録
    crop_id = insert_crop(name.strip(), family.strip(), int(interval_years))
    gr.Info(f"✅ 「{name}」を登録しました")
    return crop_id, f"登録完了: {name}"
```

---

## 8. ログ設計

### 8.1 ログ設定

```python
# rotation_planner/common/logging_config.py

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


def setup_logging(log_dir: str = "logs"):
    """ロギング設定"""
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    # ファイルハンドラ（ローテーション: 5MB × 5ファイル）
    file_handler = RotatingFileHandler(
        log_path / "rotation-planner.log",
        maxBytes=5 * 1024 * 1024,
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.INFO)
    file_format = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    file_handler.setFormatter(file_format)
    logger.addHandler(file_handler)

    # コンソールハンドラ（WARNING以上）
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.WARNING)
    console_handler.setFormatter(file_format)
    logger.addHandler(console_handler)

    return logger
```

### 8.2 ログレベル使い分け

| レベル | 用途 | 例 |
|-------|------|-----|
| DEBUG | 開発時詳細 | 変数の値、処理フロー |
| INFO | 正常動作記録 | ログイン成功、データ保存 |
| WARNING | 注意が必要 | 重複キー検出、オプション欠落 |
| ERROR | エラー発生 | DB接続失敗、ファイル読込エラー |
| CRITICAL | 致命的エラー | システム停止レベル |

---

## 9. 既存コード改善計画

### 9.1 裸の`except:`修正対象（ERROR_ANALYSIS.mdより）

| ファイル | 行番号 | 対応 |
|---------|--------|------|
| `admin_ui.py` | 221, 266, 368, 395 | `except (JSONDecodeError, KeyError) as e:` |
| `db_access.py` | 694, 741 | `except json.JSONDecodeError as e:` |
| `app/constraints.py` | 140, 143, 177, 188, 197, 204, 213, 258 | `except (ValueError, KeyError) as e:` |
| `field/kml_parser.py` | 273, 317 | `except (ET.ParseError, KeyError) as e:` |
| `pesticide/calculator.py` | 80, 112, 221, 266, 276 | `except (ValueError, ZeroDivisionError) as e:` |

### 9.2 gr.Warning/Error/Info への移行

**現状**:
```python
# format_alert() による HTML 表示
return format_error("エラーメッセージ")
```

**改善後**:
```python
# Gradio標準通知
gr.Error("エラーメッセージ")
return None, "エラー"
```

---

## 10. 実装優先順位

### Phase 1: 基盤整備（優先度: 高）

| タスク | 対象ファイル | 工数 |
|-------|-------------|------|
| 例外クラス定義 | `common/exceptions.py` (新規) | 1h |
| ログ設定 | `common/logging_config.py` (新規) | 1h |
| 裸の`except:`修正 | 25箇所 | 3h |
| **合計** | | **5h** |

### Phase 2: エラー処理実装（優先度: 高）

| タスク | 対象ファイル | 工数 |
|-------|-------------|------|
| DB操作エラー処理 | `common/db.py`, `common/db_access.py` | 3h |
| ファイル操作エラー処理 | `common/file_utils.py` (新規) | 2h |
| safe_handler実装 | `common/handlers.py` (新規) | 1h |
| **合計** | | **6h** |

### Phase 3: バリデーション（優先度: 中）

| タスク | 対象ファイル | 工数 |
|-------|-------------|------|
| バリデーションクラス | `common/validation.py` (新規) | 2h |
| エンティティ別関数 | `common/validation.py` | 2h |
| UI組み込み | 各UIファイル | 2h |
| **合計** | | **6h** |

### Phase 4: UI通知改善（優先度: 中）

| タスク | 対象ファイル | 工数 |
|-------|-------------|------|
| メッセージテンプレート | `common/messages.py` (新規) | 1h |
| gr.Info/Warning/Error移行 | 各UIファイル | 3h |
| **合計** | | **4h** |

### 総工数見積り: **21h**

---

## 11. 新規ファイル一覧

| ファイル | 内容 |
|---------|------|
| `rotation_planner/common/exceptions.py` | カスタム例外クラス |
| `rotation_planner/common/logging_config.py` | ログ設定 |
| `rotation_planner/common/file_utils.py` | ファイル操作ユーティリティ |
| `rotation_planner/common/validation.py` | バリデーション |
| `rotation_planner/common/handlers.py` | safe_handlerデコレータ |
| `rotation_planner/common/messages.py` | メッセージテンプレート |

---

## 12. チェックリスト

### 基盤
- [ ] `exceptions.py` 作成
- [ ] `logging_config.py` 作成
- [ ] 裸の`except:`を25箇所修正

### DB操作
- [ ] `get_connection()` に例外処理追加
- [ ] `transaction()` コンテキストマネージャー実装
- [ ] CRUD関数にtry-except追加
- [ ] PRAGMA設定（FK有効化、WAL）

### ファイル操作
- [ ] `read_csv_safe()` 実装
- [ ] `write_csv_safe()` 実装
- [ ] エンコーディング自動判定
- [ ] ディスク容量チェック

### バリデーション
- [ ] `ValidationResult` クラス実装
- [ ] エンティティ別バリデーション関数実装
- [ ] Gradioフォームへの組み込み

### UI通知
- [ ] メッセージテンプレート整備
- [ ] `safe_handler` デコレータ実装
- [ ] `gr.Info/Warning/Error` への移行

### ログ
- [ ] RotatingFileHandler設定
- [ ] 各モジュールでlogger取得

---

## 参考資料

- [Python logging ドキュメント](https://docs.python.org/3/library/logging.html)
- [Python sqlite3 ドキュメント](https://docs.python.org/3/library/sqlite3.html)
- [Gradio ドキュメント](https://gradio.app/docs/)
- [SQLite PRAGMA](https://www.sqlite.org/pragma.html)

---

**作成日**: 2026-02-06
**統合担当**: 足軽7号
**元ドキュメント**: ERROR_ANALYSIS.md, ERROR_DB_VALIDATION.md, ERROR_FILE_UI.md
