# ファイル操作エラー・ユーザー通知UI設計書

**プロジェクト**: rotation-planner
**対象範囲**: ファイル操作エラー処理、ユーザー通知UI
**作成日**: 2026-02-06
**担当**: 足軽7号

---

## 1. 概要

本設計書では、rotation-plannerにおけるファイル操作（CSV読み込み/書き出し、PDF生成）のエラー処理と、Gradioを使用したユーザー通知UIの設計を記述する。

---

## 2. ファイル操作エラー設計

### 2.1 CSV読み込みエラー

#### 2.1.1 エラーカテゴリ

| エラー種別 | 発生条件 | 重要度 | 例外型 |
|-----------|---------|--------|--------|
| ファイルなし | 指定パスにファイルが存在しない | Error | `FileNotFoundError` |
| 権限エラー | 読み取り権限がない | Error | `PermissionError` |
| エンコーディングエラー | UTF-8/Shift-JIS以外 | Error | `UnicodeDecodeError` |
| フォーマットエラー | 必須列の欠落 | Error | `ValueError` |
| データ不整合 | 列数不一致、型エラー | Warning | `pd.errors.ParserError` |
| 空ファイル | データ行が0件 | Warning | - |

#### 2.1.2 現状の実装（csv_io.py）

```python
# 現状: 基本的なエンコーディングフォールバックのみ
try:
    df = pd.read_csv(csv_file.name, encoding='utf-8-sig')
except Exception as e:
    try:
        df = pd.read_csv(csv_file.name, encoding='utf-8')
    except Exception as e2:
        return [], [f"CSV読み込みエラー: {e2}"]
```

#### 2.1.3 改善後の実装パターン

```python
from pathlib import Path
from typing import Tuple, List, Dict, Any
import pandas as pd

class CSVReadError(Exception):
    """CSV読み込みエラーの基底クラス"""
    def __init__(self, message: str, recoverable: bool = False):
        self.message = message
        self.recoverable = recoverable
        super().__init__(message)


def read_csv_safe(
    file_path,
    required_columns: List[str] = None,
    optional_columns: List[str] = None
) -> Tuple[pd.DataFrame, List[str]]:
    """
    安全なCSV読み込み（エラーハンドリング付き）

    Args:
        file_path: ファイルパス or Gradioファイルオブジェクト
        required_columns: 必須カラム名リスト
        optional_columns: オプションカラム名リスト

    Returns:
        (DataFrame, warnings)

    Raises:
        CSVReadError: 読み込み失敗時
    """
    warnings = []

    # 1. パス解決
    if hasattr(file_path, 'name'):
        actual_path = Path(file_path.name)
    elif isinstance(file_path, (str, Path)):
        actual_path = Path(file_path)
    else:
        raise CSVReadError("不正なファイル形式です", recoverable=False)

    # 2. ファイル存在チェック
    if not actual_path.exists():
        raise CSVReadError(
            f"ファイルが見つかりません: {actual_path.name}",
            recoverable=False
        )

    # 3. 権限チェック
    if not os.access(actual_path, os.R_OK):
        raise CSVReadError(
            f"ファイルの読み取り権限がありません: {actual_path.name}",
            recoverable=False
        )

    # 4. 空ファイルチェック
    if actual_path.stat().st_size == 0:
        raise CSVReadError("ファイルが空です", recoverable=False)

    # 5. エンコーディング自動判定 + 読み込み
    encodings = ['utf-8-sig', 'utf-8', 'shift-jis', 'cp932']
    df = None

    for enc in encodings:
        try:
            df = pd.read_csv(actual_path, encoding=enc)
            break
        except UnicodeDecodeError:
            continue
        except pd.errors.EmptyDataError:
            raise CSVReadError("CSVにデータがありません", recoverable=False)
        except pd.errors.ParserError as e:
            raise CSVReadError(
                f"CSV形式エラー: {str(e)[:100]}",
                recoverable=False
            )

    if df is None:
        raise CSVReadError(
            "文字エンコーディングを自動判定できませんでした。UTF-8またはShift-JISで保存してください。",
            recoverable=False
        )

    # 6. 必須カラムチェック
    if required_columns:
        missing = [c for c in required_columns if c not in df.columns]
        if missing:
            raise CSVReadError(
                f"必須カラムがありません: {', '.join(missing)}",
                recoverable=False
            )

    # 7. オプションカラム警告
    if optional_columns:
        missing_opt = [c for c in optional_columns if c not in df.columns]
        if missing_opt:
            warnings.append(f"オプションカラムがありません: {', '.join(missing_opt)}")

    # 8. 空行警告
    if df.empty or len(df) == 0:
        warnings.append("データ行がありません（ヘッダーのみ）")

    return df, warnings
```

#### 2.1.4 ユーザーメッセージ例

| 内部エラー | ユーザー向けメッセージ |
|-----------|----------------------|
| `FileNotFoundError` | ファイルが見つかりません。ファイルを選択してください。 |
| `PermissionError` | ファイルを開けません。他のアプリで開いている場合は閉じてください。 |
| `UnicodeDecodeError` | ファイルの文字コードを認識できません。UTF-8またはShift-JISで保存してください。 |
| 必須カラム欠落 | CSVに必要な項目がありません: 〇〇、△△ |
| 空ファイル | ファイルが空です。データを入力してください。 |

---

### 2.2 CSV書き出しエラー

#### 2.2.1 エラーカテゴリ

| エラー種別 | 発生条件 | 重要度 | 例外型 |
|-----------|---------|--------|--------|
| 権限エラー | 書き込み権限がない | Error | `PermissionError` |
| ディスク容量不足 | 空き容量なし | Error | `OSError` |
| パスエラー | 不正なパス | Error | `OSError` |
| データなし | 出力データが空 | Warning | - |

#### 2.2.2 改善後の実装パターン

```python
import shutil
import tempfile
from pathlib import Path

class CSVWriteError(Exception):
    """CSV書き出しエラー"""
    pass


def write_csv_safe(
    df: pd.DataFrame,
    output_dir: str = "/tmp",
    filename: str = None,
    encoding: str = "utf-8-sig"
) -> Tuple[str, str]:
    """
    安全なCSV書き出し

    Args:
        df: 出力するDataFrame
        output_dir: 出力ディレクトリ
        filename: ファイル名（Noneの場合は自動生成）
        encoding: 文字エンコーディング

    Returns:
        (filepath, message)

    Raises:
        CSVWriteError: 書き出し失敗時
    """
    # 1. データ存在チェック
    if df is None or df.empty:
        raise CSVWriteError("出力するデータがありません")

    # 2. 出力ディレクトリ確認
    output_path = Path(output_dir)
    if not output_path.exists():
        try:
            output_path.mkdir(parents=True, exist_ok=True)
        except PermissionError:
            raise CSVWriteError(
                f"出力フォルダを作成できません: {output_dir}"
            )

    # 3. 書き込み権限チェック
    if not os.access(output_path, os.W_OK):
        raise CSVWriteError(
            f"出力フォルダへの書き込み権限がありません: {output_dir}"
        )

    # 4. ディスク容量チェック（概算）
    estimated_size = len(df) * 100  # 1行あたり約100バイト概算
    free_space = shutil.disk_usage(output_path).free
    if free_space < estimated_size * 2:  # 2倍のマージン
        raise CSVWriteError(
            "ディスク容量が不足しています。不要なファイルを削除してください。"
        )

    # 5. ファイル名生成
    if filename is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"export_{timestamp}.csv"

    filepath = output_path / filename

    # 6. 一時ファイルに書き込み後、移動（原子性確保）
    try:
        with tempfile.NamedTemporaryFile(
            mode='w',
            suffix='.csv',
            delete=False,
            encoding=encoding,
            newline=''
        ) as tmp:
            df.to_csv(tmp, index=False)
            tmp_path = tmp.name

        # 成功したら正式パスに移動
        shutil.move(tmp_path, filepath)

    except PermissionError:
        raise CSVWriteError(
            "ファイルを保存できません。他のアプリで開いている場合は閉じてください。"
        )
    except OSError as e:
        if "No space left" in str(e):
            raise CSVWriteError(
                "ディスク容量が不足しています。"
            )
        raise CSVWriteError(f"ファイル保存エラー: {str(e)[:100]}")

    return str(filepath), f"CSVを出力しました（{len(df)}件）"
```

---

### 2.3 PDF生成エラー

#### 2.3.1 エラーカテゴリ

| エラー種別 | 発生条件 | 重要度 |
|-----------|---------|--------|
| ライブラリ未インストール | reportlab/weasyprint欠落 | Error |
| フォント欠落 | 日本語フォントなし | Error |
| メモリ不足 | 大量データ | Error |
| データなし | 空のレポート | Warning |

#### 2.3.2 改善後の実装パターン

```python
class PDFGenerationError(Exception):
    """PDF生成エラー"""
    pass


def check_pdf_dependencies() -> List[str]:
    """PDF生成に必要な依存関係をチェック"""
    issues = []

    # reportlab チェック
    try:
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
    except ImportError:
        issues.append("reportlabがインストールされていません: pip install reportlab")

    # 日本語フォントチェック
    font_paths = [
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc",  # macOS
    ]
    font_found = any(Path(p).exists() for p in font_paths)
    if not font_found:
        issues.append("日本語フォントが見つかりません")

    return issues


def generate_pdf_safe(
    data: pd.DataFrame,
    output_path: str,
    title: str = "レポート"
) -> Tuple[str, str]:
    """
    安全なPDF生成

    Returns:
        (filepath, message)

    Raises:
        PDFGenerationError: 生成失敗時
    """
    # 1. 依存関係チェック
    issues = check_pdf_dependencies()
    if issues:
        raise PDFGenerationError(
            f"PDF生成の準備ができていません:\n" + "\n".join(issues)
        )

    # 2. データチェック
    if data is None or data.empty:
        raise PDFGenerationError("出力するデータがありません")

    # 3. メモリ使用量概算チェック
    estimated_memory = len(data) * 1000  # 1行あたり約1KB概算
    if estimated_memory > 100 * 1024 * 1024:  # 100MB超
        raise PDFGenerationError(
            "データ量が多すぎます。CSVでのエクスポートをお勧めします。"
        )

    try:
        # PDF生成処理...
        pass
    except MemoryError:
        raise PDFGenerationError(
            "メモリ不足です。データ量を減らすか、CSVでエクスポートしてください。"
        )

    return output_path, f"PDFを生成しました（{len(data)}件）"
```

---

## 3. ユーザー通知UI設計

### 3.1 Gradio通知メカニズム

Gradio 4.x では以下の3つの通知方法が使用可能：

| 関数 | 用途 | 表示位置 | 自動消去 |
|------|------|---------|---------|
| `gr.Info(message)` | 情報通知 | 右下トースト | 5秒 |
| `gr.Warning(message)` | 警告（続行可能） | 右下トースト | 10秒 |
| `gr.Error(message)` | エラー（処理中断） | 右下トースト | 消えない |

**注意**: これらはイベントハンドラ関数内で呼び出す必要がある。

### 3.2 通知レベルの使い分け基準

| レベル | 使用場面 | 例 |
|-------|---------|-----|
| **Info** | 正常完了、情報提供 | 「保存しました」「5件読み込みました」 |
| **Warning** | 続行可能な問題、注意喚起 | 「一部データをスキップしました」「オプション項目がありません」 |
| **Error** | 処理中断が必要な致命的エラー | 「ファイルが見つかりません」「必須項目がありません」 |

### 3.3 通知メッセージ設計原則

1. **簡潔に**: 1〜2文で要点を伝える
2. **専門用語を避ける**: 「UnicodeDecodeError」→「文字コードエラー」
3. **解決策を提示**: 何をすればよいかを伝える
4. **数値を含める**: 「5件保存しました」「3件エラー」

### 3.4 現状の実装（ui_utils.py）

現在は `format_alert()` によるHTML形式の通知を使用：

```python
# 現状: HTML形式（Markdownコンポーネントに表示）
def format_error(message: str) -> str:
    return format_alert(message, "error")
```

**問題点**:
- 専用の出力コンポーネントが必要
- トースト通知ではない（画面遷移で消える）
- 視認性が低い

### 3.5 改善後の実装パターン

```python
import gradio as gr
from typing import Tuple, Any, Callable
from functools import wraps


def with_notifications(func: Callable) -> Callable:
    """
    関数にエラー通知機能を追加するデコレータ

    使用例:
        @with_notifications
        def process_csv(file):
            # 処理...
            return result
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            result = func(*args, **kwargs)

            # 成功時の通知（オプション）
            if isinstance(result, tuple) and len(result) >= 2:
                data, message = result[0], result[1]
                if message and not message.startswith("エラー"):
                    gr.Info(message)

            return result

        except CSVReadError as e:
            gr.Error(f"📁 {e.message}")
            return None, e.message

        except CSVWriteError as e:
            gr.Error(f"💾 {e.message}")
            return None, e.message

        except Exception as e:
            gr.Error(f"⚠️ 予期せぬエラーが発生しました: {str(e)[:100]}")
            return None, f"エラー: {str(e)}"

    return wrapper


# ===============================================
# UIイベントハンドラでの使用例
# ===============================================

def handle_csv_import(file, user_state):
    """CSVインポートハンドラ（改善版）"""
    if file is None:
        gr.Warning("ファイルを選択してください")
        return None, "ファイル未選択"

    try:
        df, warnings = read_csv_safe(
            file,
            required_columns=["農薬名"],
            optional_columns=["必要量", "単位", "対象作物"]
        )

        # 警告があれば表示
        for warn in warnings:
            gr.Warning(warn)

        # 成功通知
        gr.Info(f"✅ {len(df)}件のデータを読み込みました")

        return df.to_dict('records'), f"{len(df)}件読み込み完了"

    except CSVReadError as e:
        gr.Error(f"📁 {e.message}")
        return None, e.message


def handle_csv_export(data, user_state):
    """CSVエクスポートハンドラ（改善版）"""
    if not data:
        gr.Warning("エクスポートするデータがありません")
        return None, "データなし"

    try:
        filepath, message = write_csv_safe(
            pd.DataFrame(data),
            filename=f"export_{datetime.now():%Y%m%d_%H%M%S}.csv"
        )

        gr.Info(f"✅ {message}")
        return filepath, message

    except CSVWriteError as e:
        gr.Error(f"💾 {e.message}")
        return None, e.message
```

### 3.6 通知UIコンポーネント設計

```python
def create_notification_area():
    """
    通知エリアコンポーネント（補助用）

    gr.Info/Warning/Error のトーストに加えて、
    永続的なメッセージ表示が必要な場合に使用
    """
    with gr.Row(visible=False) as notification_row:
        notification_box = gr.HTML(
            "",
            elem_classes=["notification-area"]
        )

    return notification_row, notification_box


def show_notification(
    notification_row: gr.Row,
    notification_box: gr.HTML,
    message: str,
    level: str = "info"
) -> Tuple[gr.update, gr.update]:
    """
    永続的な通知を表示

    Args:
        level: "success", "error", "warning", "info"

    Returns:
        (row_update, box_update)
    """
    from rotation_planner.common.ui_utils import format_alert
    html = format_alert(message, level)
    return gr.update(visible=True), gr.update(value=html)


def hide_notification(
    notification_row: gr.Row,
    notification_box: gr.HTML
) -> Tuple[gr.update, gr.update]:
    """通知を非表示"""
    return gr.update(visible=False), gr.update(value="")
```

### 3.7 メッセージテンプレート

```python
# ===============================================
# メッセージテンプレート定数
# ===============================================

MESSAGES = {
    # 成功メッセージ
    "save_success": "✅ 保存しました（{count}件）",
    "import_success": "✅ インポートしました（{count}件）",
    "export_success": "✅ ダウンロードの準備ができました",
    "delete_success": "✅ 削除しました",

    # 警告メッセージ
    "partial_import": "⚠️ 一部のデータをスキップしました（{skipped}件）",
    "missing_optional": "⚠️ オプション項目がありません: {columns}",
    "duplicate_found": "⚠️ 重複データがあります（{count}件）",
    "data_modified": "⚠️ 未保存の変更があります",

    # エラーメッセージ
    "file_not_found": "📁 ファイルが見つかりません",
    "file_permission": "📁 ファイルを開けません（他のアプリで使用中？）",
    "encoding_error": "📁 ファイルの文字コードを認識できません（UTF-8推奨）",
    "missing_required": "📁 必須項目がありません: {columns}",
    "empty_file": "📁 ファイルが空です",
    "disk_full": "💾 ディスク容量が不足しています",
    "write_permission": "💾 保存先への書き込み権限がありません",
    "login_required": "🔒 ログインが必要です",
    "permission_denied": "🔒 この操作を行う権限がありません",
    "not_found": "🔍 データが見つかりません",
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

---

## 4. 統合エラーハンドラ

### 4.1 グローバルエラーハンドラ

```python
from typing import TypeVar, Callable, Any
from functools import wraps
import traceback
import logging

T = TypeVar('T')

logger = logging.getLogger(__name__)


def safe_handler(
    default_return: Any = None,
    show_traceback: bool = False
) -> Callable:
    """
    Gradioイベントハンドラ用の安全ラッパー

    Args:
        default_return: エラー時のデフォルト戻り値
        show_traceback: トレースバックをログ出力するか

    使用例:
        @safe_handler(default_return=(None, "エラー"))
        def my_handler(input1, input2):
            # 処理...
            return result, message
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
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

            except PermissionError as e:
                gr.Error("アクセス権限がありません")
                logger.error(f"権限エラー: {e}")
                return default_return

            except FileNotFoundError as e:
                gr.Error("ファイルが見つかりません")
                logger.error(f"ファイル未検出: {e}")
                return default_return

            except Exception as e:
                gr.Error(f"予期せぬエラー: {str(e)[:100]}")
                if show_traceback:
                    logger.error(traceback.format_exc())
                else:
                    logger.error(f"エラー: {e}")
                return default_return

        return wrapper
    return decorator
```

---

## 5. 実装チェックリスト

### 5.1 ファイル操作エラー

- [ ] `read_csv_safe()` 関数の実装
- [ ] `write_csv_safe()` 関数の実装
- [ ] `CSVReadError`, `CSVWriteError` 例外クラスの定義
- [ ] エンコーディング自動判定の追加
- [ ] ディスク容量チェックの追加
- [ ] 一時ファイル経由の原子的書き込み

### 5.2 ユーザー通知UI

- [ ] `gr.Info/Warning/Error` への移行
- [ ] メッセージテンプレートの整備
- [ ] `safe_handler` デコレータの適用
- [ ] 既存UIハンドラの修正

### 5.3 テスト

- [ ] ファイルなしエラーのテスト
- [ ] 権限エラーのテスト
- [ ] エンコーディングエラーのテスト
- [ ] フォーマットエラーのテスト
- [ ] ディスク容量不足のテスト（モック）

---

## 6. 関連ドキュメント

| ドキュメント | 担当 | 内容 |
|-------------|------|------|
| ERROR_ANALYSIS.md | 足軽5号 | 現状分析、エラー発生箇所特定 |
| ERROR_DB_VALIDATION.md | 足軽6号 | DB操作エラー、入力バリデーション |
| ERROR_FILE_UI.md | 足軽7号 | 本ドキュメント |
| ERROR_HANDLING_DESIGN.md | 足軽7号 | 統合版（最終成果物） |

---

**作成日**: 2026-02-06
**作成者**: 足軽7号
