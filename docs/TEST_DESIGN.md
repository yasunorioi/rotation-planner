# rotation-planner テスト設計書（統合版）

**プロジェクト**: rotation-planner
**技術スタック**: pytest + GitHub Actions + Gradio
**作成日**: 2026-02-06
**Version**: 1.0

---

## 1. 概要

### 1.1 本ドキュメントの構成

本ドキュメントは以下3つの設計書を統合した最終成果物である。

| ドキュメント | 担当 | 内容 |
|-------------|------|------|
| TEST_UNIT.md | 足軽5号 | 単体テスト設計 |
| TEST_INTEGRATION.md | 足軽6号 | 統合テスト・データ整合性テスト |
| TEST_EDGE_CI.md | 足軽7号 | エッジケース・CI/CD設計 |

### 1.2 テスト戦略

**テストピラミッド構成**:

```
                    ┌─────────┐
                    │  E2E    │  5%  - Gradio UIからの操作
                    │ Tests   │       Playwright/Selenium
                    ├─────────┤
                    │ 統合    │ 25%  - DB操作の流れ
                    │ テスト  │       データ整合性 ★重要
                    ├─────────┤
                    │ 単体    │ 70%  - 関数単位
                    │ テスト  │       バリデーション、計算
                    └─────────┘
```

### 1.3 品質目標

| 指標 | 目標値 | 必須 |
|------|--------|------|
| コードカバレッジ | 80% | 60% |
| 単体テストパス率 | 100% | 100% |
| 統合テストパス率 | 100% | 100% |
| セキュリティテスト | 全パス | 全パス |

---

## 2. テスト構成

### 2.1 既存テスト状況

| ファイル | テスト数 | 対象モジュール |
|---------|---------|---------------|
| test_auth.py | 17 | common/auth.py |
| test_csv_validation.py | 18 | data_management/ui.py |
| test_db_access.py | 16 | common/db_access.py |
| test_ja_staff.py | 23 | pesticide/ja_staff_ui.py |
| test_pesticide_order.py | 15 | pesticide/ui.py |
| test_pesticide_record.py | 36 | pesticide_record/ |
| test_security.py | 10 | 横断的セキュリティ |
| **合計** | **135** | - |

### 2.2 新規テストファイル計画

```
tests/
├── conftest.py                  # 共通フィクスチャ
├── fixtures/
│   ├── seed_data.py             # シードデータ
│   └── test_db.py               # テストDB管理
├── unit/                        # 単体テスト
│   ├── test_db.py               # P0: common/db.py
│   ├── test_constraints.py      # P0: app/constraints.py
│   ├── test_optimizer.py        # P1: app/optimizer.py
│   ├── test_calculator.py       # P1: pesticide/calculator.py
│   ├── test_year_utils.py       # P1: common/year_utils.py
│   ├── test_validation.py       # P1: バリデーション
│   └── test_kml_parser.py       # P2: field/kml_parser.py
├── integration/                 # 統合テスト
│   ├── test_crud_crops.py       # 作物CRUD
│   ├── test_crud_fields.py      # 圃場CRUD
│   ├── test_crud_plantings.py   # 栽培履歴CRUD
│   ├── test_data_integrity.py   # データ整合性 ★最重要
│   ├── test_csv_import.py       # CSVインポート
│   └── test_csv_export.py       # CSVエクスポート
├── edge/                        # エッジケーステスト
│   ├── test_edge_null.py        # NULL・空値
│   ├── test_edge_boundary.py    # 境界値
│   ├── test_edge_date.py        # 日付異常
│   ├── test_edge_security.py    # セキュリティ
│   ├── test_edge_performance.py # 性能境界
│   └── test_edge_db_failure.py  # DB障害
├── security/                    # セキュリティテスト
│   ├── test_sql_injection.py
│   ├── test_access_control.py
│   └── test_data_isolation.py
└── smoke/                       # スモークテスト
    └── test_smoke.py
```

---

## 3. 単体テスト設計

### 3.1 優先順位

| 優先度 | モジュール | 理由 |
|--------|-----------|------|
| **P0** | common/db.py | 全DBアクセスの基盤 |
| **P0** | app/constraints.py | 輪作計画の核心ロジック |
| **P1** | app/optimizer.py | 最適化アルゴリズム |
| **P1** | pesticide/calculator.py | 農薬計算（数値精度重要） |
| **P1** | common/year_utils.py | 年度計算 |
| **P2** | field/kml_parser.py | ファイル入出力 |
| **P2** | common/export.py | CSV/PDF出力 |

### 3.2 主要テストケース

#### 3.2.1 common/db.py

| ID | ケース | 期待結果 |
|----|--------|---------|
| DB-001 | 正常接続 | Connection取得成功 |
| DB-002 | 正常コミット | データ永続化 |
| DB-003 | ロールバック | 例外時にデータ巻き戻し |
| DB-004 | 外部キー有効 | FK違反でIntegrityError |

#### 3.2.2 app/constraints.py

| ID | ケース | 期待結果 |
|----|--------|---------|
| CON-001 | 正常パース | Constraintsオブジェクト |
| CON-002 | 空テーブル | デフォルト制約 |
| CON-010 | 禁止遷移パース | [("小麦", "大豆")] |

#### 3.2.3 pesticide/calculator.py

| ID | ケース | 入力 | 期待結果 |
|----|--------|------|---------|
| CAL-001 | 正常計算 | 1ha, 100ml/10a | 1000ml |
| CAL-002 | 面積0 | 0ha | 0 |
| CAL-004 | 小数精度 | 0.33ha | 330ml |

---

## 4. 統合テスト設計

### 4.1 CRUD操作テスト

#### 作物（Crops）

| ID | テストケース | 期待結果 | 優先度 |
|----|-------------|---------|--------|
| TC-CROP-001 | 新規登録 | 正常INSERT | 高 |
| TC-CROP-002 | 重複名登録 | DuplicateKeyError | 高 |
| TC-CROP-007 | 履歴付き削除 | ForeignKeyViolationError | 高 |

#### 圃場（Fields）

| ID | テストケース | 期待結果 | 優先度 |
|----|-------------|---------|--------|
| TC-FIELD-001 | 新規登録 | 正常INSERT | 高 |
| TC-FIELD-002 | 重複名登録 | DuplicateKeyError | 高 |
| TC-FIELD-004 | 履歴付き削除 | ForeignKeyViolationError | 高 |

### 4.2 データ整合性テスト（最重要）

#### 4.2.1 輪作ルール違反検出

| ID | テストケース | 期待結果 | 優先度 |
|----|-------------|---------|--------|
| TC-ROT-001 | 連作間隔内に同一科 | RotationViolationError | 最高 |
| TC-ROT-002 | 連作間隔超過 | 正常登録 | 最高 |
| TC-ROT-004 | 同一作物連続 | RotationViolationError | 最高 |

#### 4.2.2 作付け期間重複検出

| ID | テストケース | 期待結果 | 優先度 |
|----|-------------|---------|--------|
| TC-OVERLAP-001 | 完全重複 | PeriodOverlapError | 最高 |
| TC-OVERLAP-002 | 部分重複（開始が期間内） | PeriodOverlapError | 最高 |
| TC-OVERLAP-005 | 隣接（終了日=開始日） | 正常登録 | 高 |
| TC-OVERLAP-007 | 栽培中への新規作付け | PeriodOverlapError | 最高 |

#### 4.2.3 FK制約テスト

| ID | テストケース | 期待結果 | 優先度 |
|----|-------------|---------|--------|
| TC-FK-001 | 履歴付き作物削除 | ForeignKeyViolationError | 最高 |
| TC-FK-002 | 履歴付き圃場削除 | ForeignKeyViolationError | 最高 |

### 4.3 トランザクションテスト

| ID | テストケース | 期待結果 |
|----|-------------|---------|
| TC-TXN-001 | 複数操作一括コミット | 全て反映 |
| TC-TXN-002 | 途中エラーでロールバック | 全て巻き戻し |

---

## 5. エッジケース・異常系テスト

### 5.1 NULL・空値テスト

| カテゴリ | テストケース |
|---------|-------------|
| None | 作物名=None でバリデーションエラー |
| 空文字 | 作物名="" でバリデーションエラー |
| 空白のみ | 作物名="   " でバリデーションエラー |
| NaN | DataFrameのNaN値を適切にフィルタ |

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

### 5.4 セキュリティテスト

| ケース | 入力 | 期待結果 |
|--------|------|---------|
| SQLインジェクション | `'; DROP TABLE` | 安全に処理 |
| XSS | `<script>alert()` | エスケープ |
| パストラバーサル | `../../../etc/passwd` | 拒否 |

### 5.5 DB障害テスト

| ケース | シミュレーション | 期待結果 |
|--------|----------------|---------|
| 接続失敗 | sqlite3.OperationalError | DatabaseConnectionError |
| DBロック | database is locked | 適切なエラー |
| 破損 | malformed | 検出・報告 |

---

## 6. CI/CD設計

### 6.1 GitHub Actions ワークフロー

```yaml
# .github/workflows/test.yml
name: Test Suite

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]
  schedule:
    - cron: '0 18 * * *'  # 毎日AM3時JST

jobs:
  smoke-test:
    runs-on: ubuntu-latest
    timeout-minutes: 5
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          cache: 'pip'
      - run: pip install -r requirements.txt pytest
      - run: pytest -m smoke -v

  unit-test:
    needs: smoke-test
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          cache: 'pip'
      - run: pip install -r requirements.txt pytest pytest-cov
      - run: pytest tests/unit/ -v --cov=rotation_planner --cov-report=xml
      - uses: codecov/codecov-action@v4
        with:
          token: ${{ secrets.CODECOV_TOKEN }}

  integration-test:
    needs: unit-test
    runs-on: ubuntu-latest
    timeout-minutes: 15
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          cache: 'pip'
      - run: pip install -r requirements.txt pytest
      - run: python scripts/init_test_db.py
      - run: pytest tests/integration/ -v

  edge-security-test:
    needs: unit-test
    runs-on: ubuntu-latest
    timeout-minutes: 20
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          cache: 'pip'
      - run: pip install -r requirements.txt pytest
      - run: pytest tests/edge/ tests/security/ -v -m "not slow"
```

### 6.2 PRチェック（軽量版）

```yaml
# .github/workflows/pr-check.yml
name: PR Check

on:
  pull_request:

jobs:
  quick-check:
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          cache: 'pip'
      - run: pip install -r requirements.txt pytest pytest-cov flake8
      - run: flake8 rotation_planner/ --count --select=E9,F63,F7,F82
      - run: pytest -m smoke && pytest tests/unit/ --cov=rotation_planner --cov-fail-under=60
```

### 6.3 テスト実行コマンド

```bash
# 全テスト
pytest

# スモークテスト
pytest -m smoke

# 単体テストのみ
pytest tests/unit/

# エッジケースのみ
pytest tests/edge/

# カバレッジ付き
pytest --cov=rotation_planner --cov-report=html

# 遅いテストを除外
pytest -m "not slow"

# 並列実行
pytest -n auto
```

---

## 7. スモークテスト

```python
# tests/smoke/test_smoke.py

import pytest

@pytest.mark.smoke
class TestSmoke:
    """スモークテスト（最低限の動作確認）"""

    def test_app_starts(self):
        """アプリが起動すること"""
        from rotation_planner.app.ui import create_app
        app = create_app()
        assert app is not None

    def test_db_connection(self):
        """DB接続できること"""
        from rotation_planner.common.db import get_connection
        conn = get_connection()
        assert conn is not None
        conn.close()

    def test_auth_module_loads(self):
        """認証モジュールがロードできること"""
        from rotation_planner.common import auth
        assert hasattr(auth, 'get_user_info')

    def test_field_repository_accessible(self):
        """FieldRepositoryにアクセスできること"""
        from rotation_planner.common.db_access import FieldRepository
        assert hasattr(FieldRepository, 'get_fields')
```

---

## 8. 共通フィクスチャ

```python
# tests/conftest.py

import pytest
import tempfile
import shutil
from pathlib import Path


@pytest.fixture(scope="session")
def test_db_path():
    """テスト用DBパス"""
    return Path("data/test_rotation.db")


@pytest.fixture(scope="function")
def test_db(test_db_path):
    """テスト用DB（関数ごとにリセット）"""
    from rotation_planner.common.db import init_database

    backup_path = test_db_path.with_suffix('.db.bak')
    if test_db_path.exists():
        shutil.copy(test_db_path, backup_path)

    init_database(str(test_db_path))
    yield test_db_path

    if backup_path.exists():
        shutil.move(backup_path, test_db_path)


@pytest.fixture
def sample_user_state():
    """サンプルユーザー状態"""
    return {
        "user_id": 99,
        "username": "test_user",
        "display_name": "テストユーザー",
        "role": "farmer",
        "org_id": 1,
    }


@pytest.fixture
def seed_crops(test_db):
    """シード作物データ"""
    return {
        "tomato": {"id": 1, "name": "トマト", "family": "ナス科", "interval_years": 3},
        "eggplant": {"id": 2, "name": "ナス", "family": "ナス科", "interval_years": 3},
        "cucumber": {"id": 3, "name": "キュウリ", "family": "ウリ科", "interval_years": 2},
    }


@pytest.fixture
def seed_fields(test_db):
    """シード圃場データ"""
    return {
        "field_a": {"id": 1, "name": "圃場A", "area": 100},
        "field_b": {"id": 2, "name": "圃場B", "area": 200},
    }


# マーカー設定
def pytest_configure(config):
    config.addinivalue_line("markers", "smoke: スモークテスト")
    config.addinivalue_line("markers", "slow: 遅いテスト")
    config.addinivalue_line("markers", "security: セキュリティテスト")
```

---

## 9. 実装優先順位

### Phase 1: 基盤整備（目標: 1週間）

| タスク | 対象 | 工数 |
|-------|------|------|
| conftest.py整備 | tests/ | 2h |
| pytest.ini設定 | プロジェクトルート | 0.5h |
| スモークテスト作成 | tests/smoke/ | 2h |
| CI/CDワークフロー作成 | .github/workflows/ | 3h |
| **合計** | | **7.5h** |

### Phase 2: 単体テスト（目標: 2週間）

| タスク | 対象 | 工数 |
|-------|------|------|
| test_db.py | P0 | 3h |
| test_constraints.py | P0 | 4h |
| test_optimizer.py | P1 | 4h |
| test_calculator.py | P1 | 3h |
| test_year_utils.py | P1 | 2h |
| test_validation.py | P1 | 3h |
| **合計** | | **19h** |

### Phase 3: 統合テスト（目標: 2週間）

| タスク | 対象 | 工数 |
|-------|------|------|
| test_crud_crops.py | CRUD | 3h |
| test_crud_fields.py | CRUD | 3h |
| test_crud_plantings.py | CRUD | 3h |
| test_data_integrity.py | ★最重要 | 8h |
| test_csv_import.py | ファイル | 3h |
| test_csv_export.py | ファイル | 2h |
| **合計** | | **22h** |

### Phase 4: エッジケース・セキュリティ（目標: 1週間）

| タスク | 対象 | 工数 |
|-------|------|------|
| test_edge_null.py | NULL・空値 | 2h |
| test_edge_boundary.py | 境界値 | 2h |
| test_edge_date.py | 日付 | 2h |
| test_edge_security.py | セキュリティ | 3h |
| test_edge_db_failure.py | DB障害 | 2h |
| **合計** | | **11h** |

### 総工数見積り: **59.5h**

---

## 10. pytest設定

```ini
# pytest.ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = -v --tb=short
markers =
    smoke: スモークテスト（起動確認）
    slow: 遅いテスト（CI除外可能）
    security: セキュリティテスト
    integration: 統合テスト
    edge: エッジケーステスト
filterwarnings =
    ignore::DeprecationWarning
```

---

## 11. チェックリスト

### 基盤
- [ ] conftest.py 整備
- [ ] pytest.ini 設定
- [ ] .github/workflows/test.yml 作成
- [ ] .github/workflows/pr-check.yml 作成
- [ ] CODECOV_TOKEN シークレット設定

### 単体テスト
- [ ] test_db.py (P0)
- [ ] test_constraints.py (P0)
- [ ] test_optimizer.py (P1)
- [ ] test_calculator.py (P1)
- [ ] test_year_utils.py (P1)
- [ ] test_validation.py (P1)

### 統合テスト
- [ ] test_crud_crops.py
- [ ] test_crud_fields.py
- [ ] test_crud_plantings.py
- [ ] test_data_integrity.py ★
- [ ] test_csv_import.py
- [ ] test_csv_export.py

### エッジケース・セキュリティ
- [ ] test_edge_null.py
- [ ] test_edge_boundary.py
- [ ] test_edge_date.py
- [ ] test_edge_security.py
- [ ] test_edge_db_failure.py

### 品質目標
- [ ] カバレッジ 60%達成
- [ ] カバレッジ 80%達成
- [ ] 全テストパス

---

## 参考資料

- [pytest ドキュメント](https://docs.pytest.org/)
- [GitHub Actions ドキュメント](https://docs.github.com/en/actions)
- [Codecov ドキュメント](https://docs.codecov.com/)
- [SQLite テスト](https://www.sqlite.org/testing.html)

---

**作成日**: 2026-02-06
**統合担当**: 足軽7号
**元ドキュメント**: TEST_UNIT.md, TEST_INTEGRATION.md, TEST_EDGE_CI.md
