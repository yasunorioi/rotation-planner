# rotation-planner エラー処理 現状分析レポート

> **作成日**: 2026-02-06
> **調査対象**: rotation-planner v1.x
> **技術スタック**: Gradio + SQLite + Python

## 1. コード構成サマリ

### 1.1 ディレクトリ構成

```
rotation-planner/
├── portal.py              # メインエントリポイント（39KB）
├── admin_ui.py            # 管理画面UI（26KB）
├── pesticide_master_ui.py # 農薬マスタUI（15KB）
├── rotation_planner/      # メインパッケージ
│   ├── common/            # 共通機能
│   │   ├── db.py          # DB接続管理
│   │   ├── db_access.py   # リポジトリ層（1,975行）
│   │   ├── auth.py        # 認証
│   │   ├── ui_utils.py    # UI共通関数
│   │   └── export.py      # エクスポート
│   ├── app/               # アプリケーションロジック
│   │   ├── optimizer.py   # 輪作最適化
│   │   ├── constraints.py # 制約処理
│   │   └── ui.py          # 輪作計画UI
│   ├── field/             # 圃場管理
│   │   ├── crud.py        # CRUD操作
│   │   ├── ui.py          # 圃場登録UI
│   │   ├── map.py         # 地図連携
│   │   ├── kml_parser.py  # KML/KMZパーサー
│   │   └── fude_polygon.py # 筆ポリゴン取得
│   ├── pesticide/         # 農薬管理
│   ├── pesticide_record/  # 農薬使用記録
│   └── crop_history/      # 作付履歴
├── data/                  # データディレクトリ
├── tests/                 # テスト
└── scripts/               # ユーティリティスクリプト
```

### 1.2 主要ファイル一覧（行数）

| ファイル | 行数 | 役割 |
|---------|------|------|
| `common/db_access.py` | 1,975 | 全リポジトリ層 |
| `portal.py` | 900+ | メインUI、認証、タブ統合 |
| `admin_ui.py` | 600+ | 管理画面 |
| `app/constraints.py` | 300+ | 制約処理 |
| `field/kml_parser.py` | 350+ | KML/KMZパース |
| `pesticide/calculator.py` | 300+ | 農薬計算 |

### 1.3 依存ライブラリ

```
gradio>=4.0.0      # WebUI
pandas>=2.0.0      # データ操作
numpy>=1.24.0      # 数値計算
ortools>=9.0       # 輪作最適化
shapely>=2.0.0     # 地理演算
pyproj>=3.0.0      # 座標変換
requests>=2.28.0   # HTTP通信
reportlab>=4.0.0   # PDF生成
```

---

## 2. 既存エラー処理の調査

### 2.1 try-except 使用状況

| カテゴリ | 箇所数 | 備考 |
|---------|--------|------|
| `try:` ブロック | 161 | 全体 |
| `except Exception as e:` | 100+ | 適切なパターン |
| **`except:` (裸)** | **25** | **アンチパターン** |

### 2.2 裸の `except:` 箇所（要改善）

以下のファイルに裸の `except:` が存在（例外の種類を特定できない）:

| ファイル | 行番号 | 問題点 |
|---------|--------|--------|
| `admin_ui.py` | 221, 266, 368, 395 | JSON解析、ファイル操作 |
| `db_access.py` | 694, 741 | JSONパース |
| `app/constraints.py` | 140, 143, 177, 188, 197, 204, 213, 258 | 制約解析 |
| `field/kml_parser.py` | 273, 317 | KML解析 |
| `pesticide/calculator.py` | 80, 112, 221, 266, 276 | 数値計算 |
| `pesticide/ui.py` | 262 | UI操作 |
| `portal.py` | 841 | メイン処理 |

### 2.3 エラー時の挙動分析

| パターン | 割合 | 挙動 |
|---------|------|------|
| 例外をre-raise | 30% | 呼び出し元に伝播（適切） |
| 文字列でエラー返却 | 50% | UIに「エラー: ...」表示 |
| 黙殺（pass/continue） | 15% | エラー無視（問題あり） |
| ログ出力 | **0%** | **未実装** |

### 2.4 ログ出力の状況

```
logging モジュール使用: 0箇所
print() デバッグ出力: 45箇所（主にテスト・スクリプト）
```

**問題**: 本番環境でのエラートラッキングが困難

---

## 3. エラー発生リスク箇所の特定

### 3.1 DB操作箇所

| 箇所 | リスク | 現状の対策 |
|------|--------|-----------|
| `db.py:get_db()` | 接続失敗、トランザクションエラー | contextmanagerでrollback+re-raise（良好） |
| 全リポジトリメソッド | SQL実行エラー | 個別対策なし（上位で処理） |
| `db.py:init_db()` | スキーマファイル不在 | FileNotFoundError raise（良好） |

**DB層の評価**: 基本的な対策あり。ただしリトライ機構なし。

### 3.2 ファイル操作箇所

| ファイル | 操作 | リスク | 対策 |
|---------|------|--------|------|
| `field/kml_parser.py` | KML/KMZパース | 不正ファイル、文字化け | try-except（裸） |
| `field/fude_polygon.py` | GeoJSONダウンロード | ファイル保存失敗 | 一部対策あり |
| `common/export.py` | CSV/PDF出力 | 書き込み権限なし | try-except |
| `pesticide_record/export.py` | 帳票PDF生成 | フォント不在、メモリ不足 | try-except |

### 3.3 ユーザー入力受付箇所

| 入力種別 | バリデーション | 問題点 |
|---------|---------------|--------|
| ログインフォーム | ユーザー名/パスワード長チェック | 問題なし |
| ほ場登録 | 必須項目チェック | 一部不足 |
| CSV一括インポート | ヘッダー/型チェック | 詳細なエラーメッセージなし |
| 数値入力（面積等） | float変換 | 変換失敗時のエラーメッセージが不明確 |
| 年度選択 | 選択肢制限 | 問題なし |

### 3.4 外部API呼び出し箇所

| API | ファイル | タイムアウト | リトライ |
|-----|---------|-------------|---------|
| Nominatim（住所検索） | `field/map.py:114` | 10秒 | なし |
| 筆ポリゴンAPI | `field/fude_polygon.py:137` | 不明 | なし |
| Claude Vision API | `pesticide_record/image_analyzer.py` | 不明 | なし |

---

## 4. Gradio UIの確認

### 4.1 エラー表示方法

現状、Gradio標準のエラー表示機能（`gr.Warning`, `gr.Error`, `gr.Info`）は**未使用**。

**現在の実装**:
```python
# common/ui_utils.py
def format_error(message: str) -> str:
    """エラーメッセージ（赤）"""
    return format_alert(message, "error")  # HTML文字列を返す
```

UIコンポーネント（`gr.HTML`）にHTML文字列として表示。

### 4.2 Gradio標準機能の活用状況

| 機能 | 使用状況 | 推奨 |
|------|---------|------|
| `gr.Warning()` | 未使用 | 警告表示に使用すべき |
| `gr.Error()` | 未使用 | 致命的エラーに使用すべき |
| `gr.Info()` | 未使用 | 情報表示に使用すべき |
| `raise gr.Error()` | 未使用 | イベントハンドラでの例外に使用すべき |

### 4.3 ユーザーへのフィードバック

| シナリオ | 現状 | 問題点 |
|---------|------|--------|
| ログイン失敗 | HTMLで「エラー: ...」表示 | 目立たない |
| DB保存成功 | HTMLで「保存しました」 | 問題なし |
| ファイル読込失敗 | HTMLで「エラー: ...」 | 詳細不足 |
| API通信失敗 | 例外メッセージそのまま | 技術的すぎる |

---

## 5. 改善提案（概要レベル）

### 5.1 優先度: 高

| 項目 | 対策 | 工数目安 |
|------|------|---------|
| **裸の`except:`撲滅** | 具体的な例外型を指定 | 2-3時間 |
| **ログ機構導入** | `logging`モジュール導入、ファイル出力 | 4-6時間 |
| **Gradioエラー表示改善** | `gr.Warning/Error/Info`活用 | 2-4時間 |

### 5.2 優先度: 中

| 項目 | 対策 | 工数目安 |
|------|------|---------|
| 入力バリデーション強化 | 型チェック、範囲チェック統一 | 4-6時間 |
| API通信リトライ機構 | `tenacity`等でリトライ実装 | 2-3時間 |
| エラーメッセージ改善 | ユーザー向けメッセージと技術詳細を分離 | 3-4時間 |

### 5.3 優先度: 低

| 項目 | 対策 | 工数目安 |
|------|------|---------|
| カスタム例外クラス導入 | `RotationPlannerError`等を定義 | 2-3時間 |
| エラー通知機構 | 重大エラー時のメール/Slack通知 | 4-6時間 |

---

## 6. 次のステップ

1. **Phase 1: 基盤整備**
   - ログ機構の導入（`logging`モジュール）
   - 裸の`except:`の修正

2. **Phase 2: UI改善**
   - `gr.Warning/Error/Info`の活用
   - エラーメッセージの統一

3. **Phase 3: 堅牢化**
   - API通信のリトライ・タイムアウト統一
   - 入力バリデーションの強化

---

## 付録: 調査コマンド

```bash
# try-except 箇所数
grep -r "try:" --include="*.py" | wc -l

# 裸の except 箇所
grep -rn "except:" --include="*.py" | grep -v "except.*:"

# logging 使用状況
grep -r "import logging\|logging\.\|logger\." --include="*.py"

# Gradio エラー表示
grep -r "gr\.Warning\|gr\.Error\|gr\.Info" --include="*.py"
```
