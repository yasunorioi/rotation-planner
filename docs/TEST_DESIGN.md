# rotation-planner テスト設計書（統合版）

**プロジェクト**: rotation-planner
**技術スタック**: pytest + FastAPI (TestClient) + SQLite
**作成日**: 2026-02-06
**最終更新**: 2026-02-10
**Version**: 2.0

---

## 1. 概要

### 1.1 本ドキュメントの構成

本ドキュメントは以下3つの設計書を統合し、実装完了後の現状を反映した最終成果物である。

| ドキュメント | 担当 | 内容 |
|-------------|------|------|
| TEST_UNIT.md | 足軽5号 | 単体テスト設計 |
| TEST_INTEGRATION.md | 足軽6号 | 統合テスト・データ整合性テスト |
| TEST_EDGE_CI.md | 足軽7号 | エッジケース・CI/CD設計 |

### 1.2 テスト戦略

**テストピラミッド構成**（実績値）:

```
                    ┌─────────┐
                    │  E2E    │  0%   - 未実装（将来: Playwright）
                    │ Tests   │
                    ├─────────┤
                    │ 統合    │ 30%  - DB操作・API・リポジトリ
                    │ テスト  │       データ整合性 ★重要
                    ├─────────┤
                    │ 単体    │ 40%  - 関数単位
                    │ テスト  │       バリデーション、計算
                    ├─────────┤
                    │ ドメイン │ 14%  - 農薬・JA職員
                    │ テスト  │
                    ├─────────┤
                    │アルゴリズム│ 8%  - 隣接制約・最適化・GPS
                    │ テスト  │
                    ├─────────┤
                    │セキュリティ│ 8%  - 認証・権限・SQLi・XSS
                    │ テスト  │
                    └─────────┘
```

### 1.3 品質目標

| 指標 | 目標値 | 必須 | 現状（2026-02-10） |
|------|--------|------|-------------------|
| コードカバレッジ | 80% | 60% | 未計測 |
| テストパス率 | 100% | 100% | **100%（519/519）** |
| 警告数 | 0 | - | **0** |
| セキュリティテスト | 全パス | 全パス | **全パス** |

---

## 2. テスト構成

### 2.1 テスト実績（2026-02-10時点）

全テストは `tests/` ディレクトリにフラット配置。37ファイル、519テスト。

#### 単体テスト（207テスト）

| ファイル | テスト数 | 対象モジュール |
|---------|---------|---------------|
| test_kml_parser_unit.py | 24 | field/kml_parser.py |
| test_validation_unit.py | 21 | バリデーション |
| test_polygon_repository_unit.py | 20 | ポリゴンリポジトリ |
| test_optimizer_unit.py | 18 | app/optimizer.py |
| test_constraints_unit.py | 18 | app/constraints.py |
| test_spatial_unit.py | 17 | 空間計算 |
| test_calculator_unit.py | 13 | pesticide/calculator.py |
| test_aggregation_unit.py | 12 | 集計ロジック |
| test_aggregation_service_unit.py | 10 | 集計サービス |
| test_csv_io_unit.py | 10 | CSV入出力 |
| test_field_crud_unit.py | 9 | ほ場CRUD |
| test_ui_utils_unit.py | 7 | UIユーティリティ |
| test_map_unit.py | 6 | 地図表示 |

#### 統合テスト（157テスト）

| ファイル | テスト数 | 対象モジュール |
|---------|---------|---------------|
| test_aggregation.py | 31 | 集計（DB連携） |
| test_paddy_polygons.py | 23 | 水田ポリゴンAPI |
| test_crop_polygons.py | 23 | 作物ポリゴンAPI |
| test_csv_validation.py | 18 | CSVバリデーション |
| test_db_access.py | 16 | DB共通アクセス |
| test_export.py | 13 | CSV/PDFエクスポート |
| test_crop_family.py | 12 | 作物科分類 |
| test_field_repository.py | 11 | ほ場リポジトリ |
| test_crop_history_repository.py | 7 | 作付履歴リポジトリ |
| test_user_repository.py | 6 | ユーザーリポジトリ |
| test_plan_repository.py | 6 | 計画リポジトリ |
| test_user_crop_repository.py | 5 | ユーザー作物リポジトリ |
| test_user_constraints_repository.py | 4 | ユーザー制約リポジトリ |
| test_pesticide_master_repository.py | 4 | 農薬マスタリポジトリ |

#### セキュリティテスト（40テスト）

| ファイル | テスト数 | 対象モジュール |
|---------|---------|---------------|
| test_auth.py | 17 | 認証（ログイン・トークン） |
| test_auth_extended.py | 13 | 認証（拡張・エッジケース） |
| test_security.py | 10 | SQLi・XSS・データ分離・アクセス制御 |

#### アルゴリズムテスト（43テスト）

| ファイル | テスト数 | 対象モジュール |
|---------|---------|---------------|
| test_gps_matcher.py | 15 | GPSマッチング |
| test_adjacency.py | 11 | ほ場隣接判定 |
| test_adjacency_constraint.py | 10 | 隣接制約 |
| test_optimizer_adjacency.py | 7 | 最適化（隣接考慮） |

#### ドメインテスト（72テスト）

| ファイル | テスト数 | 対象モジュール |
|---------|---------|---------------|
| test_pesticide_record.py | 34 | 農薬散布記録・FAMICインポート |
| test_ja_staff.py | 23 | JA職員機能 |
| test_pesticide_order.py | 15 | 農薬発注 |

### 2.2 テスト分布サマリ

| カテゴリ | テスト数 | 割合 |
|---------|---------|------|
| 単体テスト | 207 | 40% |
| 統合テスト | 157 | 30% |
| ドメインテスト | 72 | 14% |
| アルゴリズムテスト | 43 | 8% |
| セキュリティテスト | 40 | 8% |
| **合計** | **519** | **100%** |

---

## 3. 単体テスト設計

### 3.1 実装済み優先順位

| 優先度 | モジュール | 状態 | テスト数 |
|--------|-----------|------|---------|
| **P0** | common/db.py（db_access経由） | 実装済 | 16 |
| **P0** | app/constraints.py | 実装済 | 18 |
| **P1** | app/optimizer.py | 実装済 | 18 |
| **P1** | pesticide/calculator.py | 実装済 | 13 |
| **P1** | バリデーション | 実装済 | 21 |
| **P2** | field/kml_parser.py | 実装済 | 24 |
| **P2** | common/export.py | 実装済 | 13 |

### 3.2 主要テストケース

#### 3.2.1 common/db.py（test_db_access.py）

| ID | ケース | 期待結果 | 状態 |
|----|--------|---------|------|
| DB-001 | 正常接続 | Connection取得成功 | PASS |
| DB-002 | 正常コミット | データ永続化 | PASS |
| DB-003 | ロールバック | 例外時にデータ巻き戻し | PASS |
| DB-004 | 外部キー有効 | FK違反でIntegrityError | PASS |

#### 3.2.2 app/constraints.py（test_constraints_unit.py）

| ID | ケース | 期待結果 | 状態 |
|----|--------|---------|------|
| CON-001 | 正常パース | Constraintsオブジェクト | PASS |
| CON-002 | 空テーブル | デフォルト制約 | PASS |
| CON-010 | 禁止遷移パース | [("小麦", "大豆")] | PASS |

> **注**: 作物名はFAMIC表記（`だいず`, `小麦(春播)` 等）を使用。

#### 3.2.3 pesticide/calculator.py（test_calculator_unit.py）

| ID | ケース | 入力 | 期待結果 | 状態 |
|----|--------|------|---------|------|
| CAL-001 | 正常計算 | 1ha, 100ml/10a | 1000ml | PASS |
| CAL-002 | 面積0 | 0ha | 0 | PASS |
| CAL-004 | 小数精度 | 0.33ha | 330ml | PASS |

---

## 4. 統合テスト設計

### 4.1 CRUD操作テスト

#### 作物（Crops）

| ID | テストケース | 期待結果 | 優先度 | 状態 |
|----|-------------|---------|--------|------|
| TC-CROP-001 | 新規登録 | 正常INSERT | 高 | PASS |
| TC-CROP-002 | 重複名登録 | DuplicateKeyError | 高 | PASS |
| TC-CROP-007 | 履歴付き削除 | ForeignKeyViolationError | 高 | PASS |

#### 圃場（Fields）

| ID | テストケース | 期待結果 | 優先度 | 状態 |
|----|-------------|---------|--------|------|
| TC-FIELD-001 | 新規登録 | 正常INSERT | 高 | PASS |
| TC-FIELD-002 | 重複名登録 | DuplicateKeyError | 高 | PASS |
| TC-FIELD-004 | 履歴付き削除 | ForeignKeyViolationError | 高 | PASS |

### 4.2 データ整合性テスト（最重要）

#### 4.2.1 輪作ルール違反検出

| ID | テストケース | 期待結果 | 優先度 | 状態 |
|----|-------------|---------|--------|------|
| TC-ROT-001 | 連作間隔内に同一科 | RotationViolationError | 最高 | PASS |
| TC-ROT-002 | 連作間隔超過 | 正常登録 | 最高 | PASS |
| TC-ROT-004 | 同一作物連続 | RotationViolationError | 最高 | PASS |

#### 4.2.2 作付け期間重複検出

| ID | テストケース | 期待結果 | 優先度 | 状態 |
|----|-------------|---------|--------|------|
| TC-OVERLAP-001 | 完全重複 | PeriodOverlapError | 最高 | PASS |
| TC-OVERLAP-002 | 部分重複（開始が期間内） | PeriodOverlapError | 最高 | PASS |
| TC-OVERLAP-005 | 隣接（終了日=開始日） | 正常登録 | 高 | PASS |
| TC-OVERLAP-007 | 栽培中への新規作付け | PeriodOverlapError | 最高 | PASS |

#### 4.2.3 FK制約テスト

| ID | テストケース | 期待結果 | 優先度 | 状態 |
|----|-------------|---------|--------|------|
| TC-FK-001 | 履歴付き作物削除 | ForeignKeyViolationError | 最高 | PASS |
| TC-FK-002 | 履歴付き圃場削除 | ForeignKeyViolationError | 最高 | PASS |

### 4.3 トランザクションテスト

| ID | テストケース | 期待結果 | 状態 |
|----|-------------|---------|------|
| TC-TXN-001 | 複数操作一括コミット | 全て反映 | PASS |
| TC-TXN-002 | 途中エラーでロールバック | 全て巻き戻し | PASS |

---

## 5. エッジケース・異常系テスト

### 5.1 NULL・空値テスト

| カテゴリ | テストケース | 状態 |
|---------|-------------|------|
| None | 作物名=None でバリデーションエラー | PASS |
| 空文字 | 作物名="" でバリデーションエラー | PASS |
| 空白のみ | 作物名="   " でバリデーションエラー | PASS |
| NaN | DataFrameのNaN値を適切にフィルタ | PASS（修正済: pd.isna()チェック追加） |

### 5.2 境界値テスト

| フィールド | 境界値 | 期待結果 |
|-----------|--------|---------|
| 作物名 | 50文字 | OK |
| 作物名 | 51文字 | エラー |
| 輪作間隔 | 1年 | OK |
| 輪作間隔 | 0年 | エラー |
| 面積 | 0.01a | OK |
| 面積 | 0a | エラー |

### 5.3 日付異常テスト

| ケース | 入力 | 期待結果 |
|--------|------|---------|
| 閏年2/29 | 2024-02-29 | OK |
| 非閏年2/29 | 2025-02-29 | エラー |
| 未来5年超 | 2032-01-01 | エラー |
| 収穫日<栽培日 | 収穫2026-01, 栽培2026-06 | エラー |

### 5.4 セキュリティテスト（test_security.py）

| ケース | 入力 | 期待結果 | 状態 |
|--------|------|---------|------|
| SQLインジェクション | `'; DROP TABLE` | 安全に処理 | PASS |
| XSS | `<script>alert()` | html.escapeでエスケープ | PASS（修正済） |
| データ分離 | 農家A→農家Bのデータ | 見えない | PASS |
| ロール権限 | farmer→admin昇格 | 不可 | PASS |
| CSVエクスポート権限 | 未ログインユーザー | エラー返却 | PASS |

### 5.5 DB障害テスト

| ケース | シミュレーション | 期待結果 |
|--------|----------------|---------|
| 接続失敗 | sqlite3.OperationalError | DatabaseConnectionError |
| DBロック | database is locked | 適切なエラー |
| 破損 | malformed | 検出・報告 |

---

## 6. CI/CD設計

### 6.1 現状

| 項目 | 状態 |
|------|------|
| GitHub Actions テストワークフロー | 未作成 |
| PRチェックワークフロー | 未作成 |
| deploy-demo.yml | 存在（デプロイ用） |

### 6.2 GitHub Actions ワークフロー（計画）

```yaml
# .github/workflows/test.yml
name: Test Suite

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
          cache: 'pip'
      - run: pip install -r requirements.txt pytest pytest-cov
      - name: Run tests
        env:
          JWT_SECRET: test-secret-key-for-ci-testing-32bytes!
        run: pytest tests/ -v --tb=short --cov=rotation_planner --cov-report=xml
      - uses: codecov/codecov-action@v4
        with:
          token: ${{ secrets.CODECOV_TOKEN }}
```

### 6.3 テスト実行コマンド

```bash
# 全テスト（推奨）
python3 -m pytest tests/ -v --tb=short

# カバレッジ付き
python3 -m pytest tests/ --cov=rotation_planner --cov-report=html

# 特定カテゴリのみ
python3 -m pytest tests/test_security.py -v              # セキュリティ
python3 -m pytest tests/test_*_unit.py -v                # 単体テスト
python3 -m pytest tests/test_*_repository*.py -v         # リポジトリ

# 遅いテストを除外
python3 -m pytest tests/ -m "not slow"

# 並列実行（pytest-xdist必要）
python3 -m pytest tests/ -n auto
```

---

## 7. テストインフラ

### 7.1 DB管理アーキテクチャ

```
conftest.py
├── 共有DB（モジュールレベル）
│   ├── tempfile.mkstemp() で一時DB作成
│   ├── db_schema.sql でスキーマ初期化
│   ├── init_db() で初期ユーザー作成
│   └── シードデータ挿入（rotation_plans, fields）
│
└── test_db フィクスチャ（関数レベル）
    ├── 各テスト関数で独立した一時DB
    ├── monkeypatch で db.DB_PATH, db_access.DB_PATH を差し替え
    ├── db_schema.sql でスキーマ初期化
    ├── init_db() + シードデータ
    └── テスト終了時に自動クリーンアップ
```

**重要**: DB状態を変更するテストは必ず `test_db` フィクスチャを使用すること。
共有DBに対する `DROP TABLE` や `DELETE` は他テストを破壊する。

### 7.2 Gradioモック

Gradio はレガシー依存。テスト実行時は未インストール環境を想定し、
conftest.py で `gradio`, `gradio.themes`, `gradio.components`, `gradio_folium` をMagicMockで差し替え。

### 7.3 JWT認証テスト

FastAPI エンドポイントのテストでは、ログインAPIを呼ばずにJWTトークンを直接生成する。

```python
import jwt
from datetime import datetime, timedelta, timezone

secret = os.environ.get("JWT_SECRET", "test-secret-key-for-testing-32bytes!")
payload = {
    "sub": "1", "username": "testuser", "role": "admin",
    "exp": datetime.now(timezone.utc) + timedelta(hours=1)
}
token = jwt.encode(payload, secret, algorithm="HS256")
headers = {"Authorization": f"Bearer {token}"}
```

> **注意**: JWT秘密鍵は32バイト以上を使用すること（RFC 7518 Section 3.2）。
> `datetime.utcnow()` は非推奨。`datetime.now(timezone.utc)` を使用すること。

---

## 8. 共通フィクスチャ（実装済み）

conftest.py で提供するフィクスチャ:

| フィクスチャ | スコープ | 用途 |
|------------|--------|------|
| `test_db` | function | 独立した一時DB（DB変更テスト用） |
| `admin_state` | function | 管理者ユーザー状態 dict |
| `farmer_state` | function | 農家ユーザー状態 dict |
| `ja_staff_state` | function | JA職員ユーザー状態 dict |
| `temp_dir` | function | 一時ディレクトリ |
| `temp_csv` | function | 一時CSVファイル作成ファクトリ |
| `sample_field_data` | function | サンプルほ場データ dict |
| `sample_crop_history` | function | サンプル作付履歴 dict |
| `sample_constraints` | function | サンプル制約データ dict |

pytestマーカー:

| マーカー | 用途 |
|---------|------|
| `@pytest.mark.slow` | 時間のかかるテスト |
| `@pytest.mark.db` | データベース操作を含むテスト |
| `@pytest.mark.api` | API呼び出しを含むテスト |
| `@pytest.mark.security` | セキュリティ関連のテスト |

---

## 9. 修正履歴

### 2026-02-10: テストスイート全修正

#### Phase 1: 60 FAIL + 6 ERROR → 0（commit 599eadf）

| 原因 | 修正内容 | 影響テスト数 |
|------|---------|------------|
| db_schema.sql に7テーブル不足 | crop_master, user_crops, pesticide_registry 等を追加 | ~25 |
| テスト順序によるDB汚染 | autouse DROP TABLE → test_db フィクスチャに移行 | ~34 |
| 作物名がFAMIC表記と不一致 | `大豆` → `だいず`, `春小麦` → `小麦(春播)` | 1 |
| FastAPI未インストール | pip install fastapi httpx uvicorn python-multipart | 6 ERROR |

#### Phase 2: 7 SKIPPED → 0（commit b6dea44）

| 原因 | 修正内容 |
|------|---------|
| CropPolygonAPI認証フィクスチャ失敗 | ログインAPI → JWT直接生成に変更 |
| XSS脆弱性（format_alert） | html.escape追加、skipマーカー削除 |
| csv_exportインポートパス不正 | 正しいモジュールパスに修正 |
| テスト用フィールドデータ不足 | conftest.py にシードデータ追加 |
| FieldRepository.get_field_by_id 不在 | api/main.py で get_field に修正（7箇所） |

#### Phase 3: 11 warnings → 0（commit bed612b）

| 原因 | 修正内容 |
|------|---------|
| FastAPI on_event 非推奨 | lifespan コンテキストマネージャに移行 |
| datetime.utcnow() 非推奨 | datetime.now(timezone.utc) に変更（3箇所） |
| JWT秘密鍵が短すぎる | 32バイト以上のテスト用鍵に拡張 |

---

## 10. TODO

### CI/CD
- [ ] .github/workflows/test.yml 作成
- [ ] .github/workflows/pr-check.yml 作成
- [ ] CODECOV_TOKEN シークレット設定

### カバレッジ
- [ ] カバレッジ計測の実施
- [ ] カバレッジ 60%達成
- [ ] カバレッジ 80%達成

### 追加テスト（将来）
- [ ] E2Eテスト（Playwright）
- [ ] DB障害シミュレーションテスト
- [ ] パフォーマンステスト
- [ ] スモークテスト（`@pytest.mark.smoke`）

---

## 参考資料

- [pytest ドキュメント](https://docs.pytest.org/)
- [FastAPI テスト](https://fastapi.tiangolo.com/tutorial/testing/)
- [GitHub Actions ドキュメント](https://docs.github.com/en/actions)
- [Codecov ドキュメント](https://docs.codecov.com/)
- [SQLite テスト](https://www.sqlite.org/testing.html)

---

**作成日**: 2026-02-06
**統合担当**: 足軽7号
**更新**: 2026-02-10（テスト全修正後の現状反映 — Version 2.0）
**元ドキュメント**: TEST_UNIT.md, TEST_INTEGRATION.md, TEST_EDGE_CI.md
