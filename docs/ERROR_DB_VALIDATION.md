# DB操作・入力バリデーション エラー処理設計

> **プロジェクト**: rotation-planner
> **技術スタック**: Gradio + SQLite
> **作成日**: 2026-02-06
> **Version**: 1.0

---

## 1. 概要

本ドキュメントは、rotation-plannerにおけるDB操作エラーと入力バリデーションの設計を定義する。

**設計方針**:
- ユーザーに分かりやすいエラーメッセージを表示
- 詳細なエラーはログに記録
- データ整合性を保証（トランザクション管理）
- 入力段階で不正データを防止

---

## 2. DB操作エラー設計

### 2.1 エラー分類

| カテゴリ | エラータイプ | 重要度 | ユーザー通知 |
|---------|-------------|--------|-------------|
| **接続** | 接続失敗 | 高 | Yes |
| | DB破損 | 高 | Yes |
| **INSERT** | 重複キー | 中 | Yes |
| | NOT NULL違反 | 中 | Yes |
| | FK制約違反 | 中 | Yes |
| **UPDATE** | 対象なし | 低 | Yes |
| | 制約違反 | 中 | Yes |
| **DELETE** | FK制約違反 | 中 | Yes |
| | 対象なし | 低 | Yes |
| **SELECT** | 結果なし | 低 | No（空表示） |

### 2.2 SQLite接続エラー

#### 2.2.1 接続失敗

```python
import sqlite3
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

DB_PATH = "data/rotation.db"

def get_connection():
    """データベース接続を取得"""
    try:
        # ファイルの存在確認
        db_path = Path(DB_PATH)
        if not db_path.parent.exists():
            db_path.parent.mkdir(parents=True)

        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    except sqlite3.OperationalError as e:
        logger.error(f"DB接続失敗: {e}")
        raise DatabaseConnectionError(f"データベースに接続できません: {e}")

    except sqlite3.DatabaseError as e:
        logger.error(f"DBエラー: {e}")
        raise DatabaseConnectionError(f"データベースエラー: {e}")
```

#### 2.2.2 DB破損時の対応

```python
import shutil
from datetime import datetime

def check_db_integrity():
    """データベース整合性チェック"""
    try:
        conn = get_connection()
        result = conn.execute("PRAGMA integrity_check").fetchone()
        conn.close()

        if result[0] != "ok":
            logger.error(f"DB整合性エラー: {result[0]}")
            return False, result[0]
        return True, "ok"

    except Exception as e:
        logger.error(f"整合性チェック失敗: {e}")
        return False, str(e)

def backup_and_recreate_db():
    """破損DBのバックアップと再作成"""
    db_path = Path(DB_PATH)

    if db_path.exists():
        # バックアップ作成
        backup_name = f"{DB_PATH}.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        shutil.copy(DB_PATH, backup_name)
        logger.info(f"DBバックアップ作成: {backup_name}")

        # 破損DBを削除
        db_path.unlink()

    # 新規DB作成（スキーマ適用）
    init_database()
    logger.info("新規DB作成完了")
```

### 2.3 CRUD操作エラー

#### 2.3.1 INSERT エラー

```python
class DuplicateKeyError(Exception):
    """重複キーエラー"""
    pass

class NotNullViolationError(Exception):
    """NOT NULL制約違反"""
    pass

class ForeignKeyViolationError(Exception):
    """外部キー制約違反"""
    pass

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
        return cursor.lastrowid

    except sqlite3.IntegrityError as e:
        error_msg = str(e).lower()

        if "unique constraint" in error_msg:
            logger.warning(f"重複キー: {name}")
            raise DuplicateKeyError(f"「{name}」は既に登録されています")

        elif "not null constraint" in error_msg:
            logger.warning(f"NOT NULL違反: {e}")
            raise NotNullViolationError("必須項目が入力されていません")

        elif "foreign key constraint" in error_msg:
            logger.warning(f"FK制約違反: {e}")
            raise ForeignKeyViolationError("参照先のデータが存在しません")

        else:
            logger.error(f"整合性エラー: {e}")
            raise

    except sqlite3.Error as e:
        logger.error(f"INSERT失敗: {e}")
        raise DatabaseError(f"データの登録に失敗しました: {e}")

    finally:
        if conn:
            conn.close()
```

#### 2.3.2 UPDATE エラー

```python
class RecordNotFoundError(Exception):
    """対象レコードなし"""
    pass

def update_crop(crop_id: int, name: str, family: str, interval_years: int):
    """作物を更新"""
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE crops
            SET name = ?, family = ?, interval_years = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (name, family, interval_years, crop_id))

        if cursor.rowcount == 0:
            logger.warning(f"UPDATE対象なし: crop_id={crop_id}")
            raise RecordNotFoundError(f"ID {crop_id} のデータが見つかりません")

        conn.commit()
        return True

    except sqlite3.IntegrityError as e:
        error_msg = str(e).lower()

        if "unique constraint" in error_msg:
            raise DuplicateKeyError(f"「{name}」は既に登録されています")

        elif "foreign key constraint" in error_msg:
            raise ForeignKeyViolationError("参照先のデータが存在しません")

        else:
            raise

    except sqlite3.Error as e:
        logger.error(f"UPDATE失敗: {e}")
        raise DatabaseError(f"データの更新に失敗しました: {e}")

    finally:
        if conn:
            conn.close()
```

#### 2.3.3 DELETE エラー

```python
def delete_crop(crop_id: int):
    """作物を削除"""
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # FK制約チェック（参照されているか確認）
        cursor.execute("""
            SELECT COUNT(*) FROM planting_history WHERE crop_id = ?
        """, (crop_id,))

        if cursor.fetchone()[0] > 0:
            raise ForeignKeyViolationError(
                "この作物は栽培履歴で使用されているため削除できません"
            )

        cursor.execute("DELETE FROM crops WHERE id = ?", (crop_id,))

        if cursor.rowcount == 0:
            raise RecordNotFoundError(f"ID {crop_id} のデータが見つかりません")

        conn.commit()
        return True

    except sqlite3.IntegrityError as e:
        if "foreign key constraint" in str(e).lower():
            raise ForeignKeyViolationError(
                "このデータは他のデータから参照されているため削除できません"
            )
        raise

    except sqlite3.Error as e:
        logger.error(f"DELETE失敗: {e}")
        raise DatabaseError(f"データの削除に失敗しました: {e}")

    finally:
        if conn:
            conn.close()
```

#### 2.3.4 SELECT エラー

```python
def get_crop(crop_id: int):
    """作物を取得"""
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM crops WHERE id = ?", (crop_id,))
        row = cursor.fetchone()

        if row is None:
            # SELECTで結果なしはNoneを返す（エラーではない）
            return None

        return dict(row)

    except sqlite3.Error as e:
        logger.error(f"SELECT失敗: {e}")
        raise DatabaseError(f"データの取得に失敗しました: {e}")

    finally:
        if conn:
            conn.close()

def get_all_crops():
    """全作物を取得"""
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM crops ORDER BY name")
        rows = cursor.fetchall()

        # 結果なしは空リスト（エラーではない）
        return [dict(row) for row in rows]

    except sqlite3.Error as e:
        logger.error(f"SELECT失敗: {e}")
        raise DatabaseError(f"データの取得に失敗しました: {e}")

    finally:
        if conn:
            conn.close()
```

### 2.4 トランザクション管理

```python
from contextlib import contextmanager

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

# 使用例
def register_planting_with_crop(crop_name: str, family: str, field_id: int, planted_date: str):
    """作物登録と栽培記録を同時に行う"""
    with transaction() as conn:
        cursor = conn.cursor()

        # 作物登録
        cursor.execute("""
            INSERT INTO crops (name, family, interval_years)
            VALUES (?, ?, 3)
        """, (crop_name, family))
        crop_id = cursor.lastrowid

        # 栽培記録
        cursor.execute("""
            INSERT INTO planting_history (crop_id, field_id, planted_date)
            VALUES (?, ?, ?)
        """, (crop_id, field_id, planted_date))

        return crop_id
```

### 2.5 エラーハンドリングユーティリティ

```python
class DatabaseError(Exception):
    """汎用DBエラー"""
    pass

class DatabaseConnectionError(DatabaseError):
    """DB接続エラー"""
    pass

def handle_db_error(func):
    """DBエラーハンドリングデコレーター"""
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

# 使用例
@handle_db_error
def safe_insert_crop(name: str, family: str, interval_years: int):
    return insert_crop(name, family, interval_years), None
```

---

## 3. 入力バリデーション設計

### 3.1 バリデーションルール一覧

| フィールド | 型 | 必須 | 制約 |
|-----------|---|------|------|
| **作物名** | 文字列 | Yes | 1-50文字、重複不可 |
| **科名** | 文字列 | Yes | 1-30文字 |
| **輪作間隔** | 整数 | Yes | 1-10年 |
| **圃場名** | 文字列 | Yes | 1-50文字、重複不可 |
| **面積** | 数値 | No | 0.01-1000（a） |
| **栽培日** | 日付 | Yes | 過去100年〜未来5年 |
| **収穫日** | 日付 | No | 栽培日以降 |

### 3.2 バリデーションエラー定義

```python
from dataclasses import dataclass
from typing import Optional, List

@dataclass
class ValidationError:
    """バリデーションエラー"""
    field: str
    message: str
    value: Optional[str] = None

class ValidationResult:
    """バリデーション結果"""
    def __init__(self):
        self.errors: List[ValidationError] = []

    def add_error(self, field: str, message: str, value: Optional[str] = None):
        self.errors.append(ValidationError(field, message, value))

    def is_valid(self) -> bool:
        return len(self.errors) == 0

    def get_error_messages(self) -> List[str]:
        return [f"{e.field}: {e.message}" for e in self.errors]

    def get_first_error(self) -> Optional[str]:
        if self.errors:
            return f"{self.errors[0].field}: {self.errors[0].message}"
        return None
```

### 3.3 バリデーション関数

#### 3.3.1 文字列バリデーション

```python
def validate_required(value: Optional[str], field_name: str, result: ValidationResult):
    """必須チェック"""
    if value is None or str(value).strip() == "":
        result.add_error(field_name, "入力してください", value)
        return False
    return True

def validate_string_length(value: str, field_name: str, min_len: int, max_len: int,
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

def validate_no_special_chars(value: str, field_name: str, result: ValidationResult):
    """特殊文字チェック"""
    import re
    if re.search(r'[<>"\';]', value):
        result.add_error(field_name, "使用できない文字が含まれています", value)
        return False
    return True
```

#### 3.3.2 数値バリデーション

```python
def validate_integer(value, field_name: str, result: ValidationResult):
    """整数チェック"""
    try:
        int(value)
        return True
    except (ValueError, TypeError):
        result.add_error(field_name, "整数を入力してください", str(value))
        return False

def validate_float(value, field_name: str, result: ValidationResult):
    """数値チェック"""
    try:
        float(value)
        return True
    except (ValueError, TypeError):
        result.add_error(field_name, "数値を入力してください", str(value))
        return False

def validate_range(value: float, field_name: str, min_val: float, max_val: float,
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

#### 3.3.3 日付バリデーション

```python
from datetime import datetime, date, timedelta

def validate_date_format(value: str, field_name: str, result: ValidationResult):
    """日付形式チェック"""
    try:
        datetime.strptime(value, "%Y-%m-%d")
        return True
    except ValueError:
        result.add_error(field_name, "正しい日付形式で入力してください（例: 2026-01-15）", value)
        return False

def validate_date_range(value: str, field_name: str, result: ValidationResult):
    """日付範囲チェック（過去100年〜未来5年）"""
    try:
        d = datetime.strptime(value, "%Y-%m-%d").date()
        today = date.today()

        min_date = today - timedelta(days=365*100)
        max_date = today + timedelta(days=365*5)

        if d < min_date:
            result.add_error(field_name, "日付が古すぎます", value)
            return False

        if d > max_date:
            result.add_error(field_name, "日付が未来すぎます", value)
            return False

        return True
    except ValueError:
        return False

def validate_date_after(value: str, after_value: str, field_name: str,
                        after_field_name: str, result: ValidationResult):
    """日付前後関係チェック"""
    try:
        d1 = datetime.strptime(value, "%Y-%m-%d").date()
        d2 = datetime.strptime(after_value, "%Y-%m-%d").date()

        if d1 < d2:
            result.add_error(field_name, f"{after_field_name}以降の日付を入力してください", value)
            return False

        return True
    except ValueError:
        return False
```

### 3.4 エンティティ別バリデーション

#### 3.4.1 作物バリデーション

```python
def validate_crop(name: str, family: str, interval_years) -> ValidationResult:
    """作物入力のバリデーション"""
    result = ValidationResult()

    # 作物名
    if validate_required(name, "作物名", result):
        validate_string_length(name, "作物名", 1, 50, result)
        validate_no_special_chars(name, "作物名", result)

    # 科名
    if validate_required(family, "科名", result):
        validate_string_length(family, "科名", 1, 30, result)

    # 輪作間隔
    if validate_required(interval_years, "輪作間隔", result):
        if validate_integer(interval_years, "輪作間隔", result):
            validate_range(int(interval_years), "輪作間隔", 1, 10, result)

    return result
```

#### 3.4.2 圃場バリデーション

```python
def validate_field(name: str, area) -> ValidationResult:
    """圃場入力のバリデーション"""
    result = ValidationResult()

    # 圃場名
    if validate_required(name, "圃場名", result):
        validate_string_length(name, "圃場名", 1, 50, result)
        validate_no_special_chars(name, "圃場名", result)

    # 面積（任意）
    if area is not None and str(area).strip() != "":
        if validate_float(area, "面積", result):
            validate_range(float(area), "面積", 0.01, 1000, result)

    return result
```

#### 3.4.3 栽培記録バリデーション

```python
def validate_planting(crop_id, field_id, planted_date: str,
                      harvested_date: Optional[str] = None) -> ValidationResult:
    """栽培記録入力のバリデーション"""
    result = ValidationResult()

    # 作物ID
    if validate_required(crop_id, "作物", result):
        validate_integer(crop_id, "作物", result)

    # 圃場ID
    if validate_required(field_id, "圃場", result):
        validate_integer(field_id, "圃場", result)

    # 栽培日
    if validate_required(planted_date, "栽培日", result):
        if validate_date_format(planted_date, "栽培日", result):
            validate_date_range(planted_date, "栽培日", result)

    # 収穫日（任意）
    if harvested_date is not None and str(harvested_date).strip() != "":
        if validate_date_format(harvested_date, "収穫日", result):
            if validate_date_range(harvested_date, "収穫日", result):
                validate_date_after(harvested_date, planted_date,
                                   "収穫日", "栽培日", result)

    return result
```

### 3.5 Gradioでのバリデーション実装

#### 3.5.1 入力コンポーネント設定

```python
import gradio as gr

def create_crop_form():
    """作物登録フォーム"""
    with gr.Row():
        name_input = gr.Textbox(
            label="作物名",
            placeholder="例: トマト",
            max_lines=1,
            # Gradioのmax_chars制限
        )

        family_input = gr.Textbox(
            label="科名",
            placeholder="例: ナス科",
            max_lines=1,
        )

        interval_input = gr.Number(
            label="輪作間隔（年）",
            value=3,
            minimum=1,
            maximum=10,
            step=1,
            precision=0,
        )

    return name_input, family_input, interval_input
```

#### 3.5.2 フォーム送信ハンドラ

```python
def handle_crop_submit(name: str, family: str, interval_years: int):
    """作物登録フォームの送信処理"""

    # バリデーション
    validation_result = validate_crop(name, family, interval_years)

    if not validation_result.is_valid():
        # エラーメッセージを返す
        error_msg = "\n".join(validation_result.get_error_messages())
        return gr.update(value=None), f"入力エラー:\n{error_msg}"

    # DB登録
    try:
        crop_id = insert_crop(name.strip(), family.strip(), int(interval_years))
        return gr.update(value=crop_id), f"「{name}」を登録しました"

    except DuplicateKeyError as e:
        return gr.update(value=None), str(e)

    except DatabaseError as e:
        return gr.update(value=None), str(e)
```

#### 3.5.3 Gradio Interfaceへの組み込み

```python
def create_app():
    """Gradioアプリ作成"""

    with gr.Blocks(title="Rotation Planner") as app:
        gr.Markdown("# 輪作計画管理")

        with gr.Tab("作物登録"):
            with gr.Column():
                name_input, family_input, interval_input = create_crop_form()

                submit_btn = gr.Button("登録", variant="primary")
                result_output = gr.Textbox(label="結果", interactive=False)

                submit_btn.click(
                    fn=handle_crop_submit,
                    inputs=[name_input, family_input, interval_input],
                    outputs=[gr.State(), result_output]
                )

        # 他のタブ...

    return app

if __name__ == "__main__":
    app = create_app()
    app.launch()
```

---

## 4. SQLite特有の注意事項

### 4.1 外部キー制約

```python
# SQLiteはデフォルトでFKが無効
# 接続時に必ず有効化する
conn.execute("PRAGMA foreign_keys = ON")
```

### 4.2 型の緩さ

```python
# SQLiteは型チェックが緩いため、アプリ側でバリデーション必須
# 例: INTEGER列に文字列を入れてもエラーにならない場合がある
```

### 4.3 同時アクセス

```python
# SQLiteは書き込み時にDBファイル全体をロック
# 同時書き込みが多い場合はタイムアウト設定
conn = sqlite3.connect(DB_PATH, timeout=30.0)
```

### 4.4 WALモード

```python
# 読み取り性能向上のためWALモード推奨
conn.execute("PRAGMA journal_mode=WAL")
```

### 4.5 バキューム

```python
# 定期的にVACUUMでDBファイルサイズを最適化
def vacuum_database():
    conn = get_connection()
    conn.execute("VACUUM")
    conn.close()
```

---

## 5. エラーメッセージガイドライン

### 5.1 ユーザー向けメッセージ

| 状況 | メッセージ例 |
|------|-------------|
| 必須項目未入力 | 「作物名を入力してください」 |
| 文字数超過 | 「作物名は50文字以内で入力してください」 |
| 重複登録 | 「トマトは既に登録されています」 |
| 参照エラー | 「選択した科が見つかりません」 |
| 削除不可 | 「この作物は栽培履歴で使用されているため削除できません」 |
| DB接続失敗 | 「データベースに接続できません。しばらくしてから再試行してください」 |

### 5.2 避けるべきメッセージ

| NG | OK |
|----|---|
| `IntegrityError: UNIQUE constraint failed` | 「トマトは既に登録されています」 |
| `sqlite3.OperationalError` | 「データベースエラーが発生しました」 |
| `None` / 空文字 | 「予期しないエラーが発生しました」 |

---

## 6. ログ設計

```python
import logging
from logging.handlers import RotatingFileHandler

def setup_logging():
    """ロギング設定"""
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    # ファイルハンドラ（ローテーション）
    file_handler = RotatingFileHandler(
        "logs/rotation-planner.log",
        maxBytes=5*1024*1024,  # 5MB
        backupCount=5
    )
    file_handler.setLevel(logging.INFO)
    file_format = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    file_handler.setFormatter(file_format)
    logger.addHandler(file_handler)

    # コンソールハンドラ（開発時）
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.WARNING)
    console_handler.setFormatter(file_format)
    logger.addHandler(console_handler)

# 使用例
logger = logging.getLogger(__name__)
logger.info(f"作物登録成功: {crop_name}")
logger.warning(f"重複キー検出: {crop_name}")
logger.error(f"DB接続失敗: {error}")
```

---

## 7. 実装チェックリスト

### 7.1 DB操作

- [ ] get_connection()に例外処理追加
- [ ] 各CRUD関数にtry-except追加
- [ ] トランザクションコンテキストマネージャー実装
- [ ] DB整合性チェック関数実装
- [ ] PRAGMA設定（FK有効化、WAL）

### 7.2 バリデーション

- [ ] ValidationResult/ValidationError クラス定義
- [ ] 各フィールド用バリデーション関数実装
- [ ] エンティティ別バリデーション関数実装
- [ ] Gradio入力コンポーネントに制約設定
- [ ] フォームハンドラにバリデーション組み込み

### 7.3 ログ・運用

- [ ] ロギング設定
- [ ] エラーメッセージ統一
- [ ] 定期バキューム設定

---

## 参考資料

- [Python sqlite3 ドキュメント](https://docs.python.org/3/library/sqlite3.html)
- [Gradio ドキュメント](https://gradio.app/docs/)
- [SQLite PRAGMA](https://www.sqlite.org/pragma.html)
