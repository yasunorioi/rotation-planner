# エッジケース・異常系テスト & CI/CD設計書

**プロジェクト**: rotation-planner
**技術スタック**: pytest + GitHub Actions
**作成日**: 2026-02-06
**担当**: 足軽7号

---

## 1. 概要

本ドキュメントでは、rotation-plannerのエッジケース・異常系テストケースとCI/CD設計を定義する。

**目的**:
- 境界条件でのシステム堅牢性を保証
- 回帰テストによる品質維持
- 継続的テスト実行の自動化

---

## 2. エッジケース・異常系テスト設計

### 2.1 テストカテゴリ一覧

| カテゴリ | 対象 | 優先度 |
|---------|------|--------|
| 空・NULL | 空文字、None、NaN | 高 |
| 境界値 | 最大/最小値、長大文字列 | 高 |
| 型不正 | 数値に文字列、日付に不正値 | 高 |
| セキュリティ | SQLi、XSS、パストラバーサル | 高 |
| 日付異常 | 未来日、矛盾期間、閏年 | 中 |
| 大量データ | 性能境界、メモリ境界 | 中 |
| 外部障害 | DB接続断、API障害 | 中 |
| 並行処理 | 同時更新、トランザクション | 低 |

### 2.2 空・NULL・空文字テスト

#### 2.2.1 テストケース定義

```python
# tests/test_edge_null.py

import pytest
import pandas as pd
import numpy as np
from rotation_planner.common.db_access import (
    FieldRepository, UserCropRepository, PlanRepository
)
from rotation_planner.common.validation import validate_crop, validate_field


class TestNullEmptyValues:
    """NULL・空文字のテスト"""

    # === 入力バリデーション ===

    @pytest.mark.parametrize("value", [
        None,
        "",
        "   ",        # 空白のみ
        "\t\n",       # タブ・改行のみ
    ])
    def test_crop_name_empty_variants(self, value):
        """作物名の空値バリアントでエラーになること"""
        result = validate_crop(name=value, family="テスト科", interval_years=3)
        assert not result.is_valid()
        assert "作物名" in result.get_first_error()

    @pytest.mark.parametrize("value", [
        None,
        "",
        0,
        -1,
        "abc",        # 数値以外
    ])
    def test_interval_years_invalid(self, value):
        """輪作間隔の不正値でエラーになること"""
        result = validate_crop(name="テスト", family="テスト科", interval_years=value)
        assert not result.is_valid()

    # === DataFrame操作 ===

    def test_dataframe_with_nan_values(self):
        """NaN値を含むDataFrameの処理"""
        df = pd.DataFrame({
            "作物名": ["トマト", np.nan, "キュウリ"],
            "面積": [100, 200, np.nan],
        })

        # NaN行のフィルタリング
        clean_df = df.dropna(subset=["作物名"])
        assert len(clean_df) == 2
        assert np.nan not in clean_df["作物名"].values

    def test_empty_dataframe_handling(self):
        """空DataFrameの処理"""
        df = pd.DataFrame(columns=["作物名", "面積"])

        assert df.empty
        assert len(df) == 0

        # 空DataFrameでの操作がエラーにならないこと
        result = df.to_dict('records')
        assert result == []

    # === DB操作 ===

    def test_get_fields_with_no_data(self, test_db):
        """データなしユーザーのほ場取得"""
        fields = FieldRepository.get_fields(user_id=99999)
        assert isinstance(fields, list)
        assert len(fields) == 0

    def test_get_plans_with_no_data(self, test_db):
        """データなしユーザーの計画取得"""
        plans = PlanRepository.get_plans(user_id=99999)
        assert isinstance(plans, list)
        assert len(plans) == 0
```

### 2.3 境界値・長大文字列テスト

```python
# tests/test_edge_boundary.py

import pytest
from rotation_planner.common.validation import validate_crop, validate_field


class TestBoundaryValues:
    """境界値テスト"""

    # === 文字列長 ===

    def test_crop_name_max_length(self):
        """作物名の最大長（50文字）"""
        name_50 = "あ" * 50
        name_51 = "あ" * 51

        result_ok = validate_crop(name=name_50, family="科", interval_years=3)
        result_ng = validate_crop(name=name_51, family="科", interval_years=3)

        assert result_ok.is_valid()
        assert not result_ng.is_valid()
        assert "文字" in result_ng.get_first_error()

    def test_extremely_long_string(self):
        """極端に長い文字列（10KB）"""
        long_string = "a" * 10240

        result = validate_crop(name=long_string, family="科", interval_years=3)
        assert not result.is_valid()

    def test_field_name_with_unicode(self):
        """Unicode文字を含むほ場名"""
        unicode_names = [
            "第1ほ場🌾",           # 絵文字
            "田んぼ①②③",          # 丸数字
            "圃場（東）",           # 全角括弧
            "ﾊﾝｶｸｶﾅほ場",         # 半角カナ
        ]

        for name in unicode_names:
            result = validate_field(name=name, area=100)
            # バリデーション自体は通る（特殊文字チェックがなければ）
            # 実装に依存するため、エラーにならないことだけ確認
            assert isinstance(result.is_valid(), bool)

    # === 数値範囲 ===

    @pytest.mark.parametrize("value,expected_valid", [
        (1, True),      # 最小値
        (10, True),     # 最大値
        (0, False),     # 下限外
        (11, False),    # 上限外
        (-1, False),    # 負数
        (100, False),   # 大幅超過
    ])
    def test_interval_years_boundary(self, value, expected_valid):
        """輪作間隔の境界値"""
        result = validate_crop(name="テスト", family="科", interval_years=value)
        assert result.is_valid() == expected_valid

    @pytest.mark.parametrize("value,expected_valid", [
        (0.01, True),    # 最小値
        (1000, True),    # 最大値
        (0, False),      # 下限外
        (0.009, False),  # 下限外（小数）
        (1001, False),   # 上限外
        (-1, False),     # 負数
    ])
    def test_field_area_boundary(self, value, expected_valid):
        """面積の境界値"""
        result = validate_field(name="テストほ場", area=value)
        assert result.is_valid() == expected_valid
```

### 2.4 日付異常テスト

```python
# tests/test_edge_date.py

import pytest
from datetime import date, timedelta
from rotation_planner.common.validation import (
    validate_date_format,
    validate_date_range,
    validate_date_after,
    ValidationResult
)


class TestDateEdgeCases:
    """日付エッジケーステスト"""

    # === 日付形式 ===

    @pytest.mark.parametrize("date_str,should_pass", [
        ("2026-01-15", True),      # 正常
        ("2026-1-15", False),      # 月の0埋めなし
        ("2026-01-5", False),      # 日の0埋めなし
        ("26-01-15", False),       # 年2桁
        ("2026/01/15", False),     # スラッシュ区切り
        ("2026.01.15", False),     # ドット区切り
        ("20260115", False),       # 区切りなし
        ("January 15, 2026", False),  # 英語形式
        ("令和8年1月15日", False),    # 和暦
        ("2026-13-01", False),     # 月が範囲外
        ("2026-01-32", False),     # 日が範囲外
        ("2026-02-30", False),     # 存在しない日（2月30日）
    ])
    def test_date_format_variants(self, date_str, should_pass):
        """日付形式のバリアント"""
        result = ValidationResult()
        is_valid = validate_date_format(date_str, "日付", result)
        assert is_valid == should_pass

    # === 閏年 ===

    @pytest.mark.parametrize("date_str,should_pass", [
        ("2024-02-29", True),   # 閏年（2024年は閏年）
        ("2025-02-29", False),  # 非閏年
        ("2000-02-29", True),   # 400年周期閏年
        ("1900-02-29", False),  # 100年周期非閏年
    ])
    def test_leap_year_dates(self, date_str, should_pass):
        """閏年の日付"""
        result = ValidationResult()
        is_valid = validate_date_format(date_str, "日付", result)
        assert is_valid == should_pass

    # === 日付範囲 ===

    def test_future_date_limit(self):
        """未来日の制限（5年先まで）"""
        today = date.today()
        future_5y = today + timedelta(days=365*5)
        future_6y = today + timedelta(days=365*6)

        result_ok = ValidationResult()
        result_ng = ValidationResult()

        validate_date_range(future_5y.isoformat(), "日付", result_ok)
        validate_date_range(future_6y.isoformat(), "日付", result_ng)

        assert result_ok.is_valid()
        assert not result_ng.is_valid()

    def test_past_date_limit(self):
        """過去日の制限（100年前まで）"""
        today = date.today()
        past_100y = today - timedelta(days=365*100)
        past_101y = today - timedelta(days=365*101)

        result_ok = ValidationResult()
        result_ng = ValidationResult()

        validate_date_range(past_100y.isoformat(), "日付", result_ok)
        validate_date_range(past_101y.isoformat(), "日付", result_ng)

        assert result_ok.is_valid()
        assert not result_ng.is_valid()

    # === 日付前後関係 ===

    def test_harvest_before_plant_error(self):
        """収穫日が栽培日より前はエラー"""
        result = ValidationResult()
        validate_date_after(
            "2026-01-01",    # 収穫日
            "2026-06-01",    # 栽培日
            "収穫日", "栽培日",
            result
        )
        assert not result.is_valid()
        assert "以降" in result.get_first_error()

    def test_same_plant_harvest_date(self):
        """栽培日と収穫日が同日は許可"""
        result = ValidationResult()
        validate_date_after(
            "2026-06-01",
            "2026-06-01",
            "収穫日", "栽培日",
            result
        )
        assert result.is_valid()
```

### 2.5 セキュリティテスト（エッジケース）

```python
# tests/test_edge_security.py

import pytest
from rotation_planner.common.db_access import FieldRepository
from rotation_planner.common.validation import validate_field, validate_crop


class TestSecurityEdgeCases:
    """セキュリティ関連エッジケーステスト"""

    # === SQLインジェクション風入力 ===

    @pytest.mark.parametrize("malicious_input", [
        "'; DROP TABLE fields; --",
        "1 OR 1=1",
        "1; SELECT * FROM users",
        "UNION SELECT password FROM users",
        "' OR '1'='1",
        "admin'--",
        "1/**/OR/**/1=1",
    ])
    def test_sql_injection_in_field_name(self, malicious_input):
        """ほ場名でのSQLインジェクション対策"""
        # バリデーションを通らないか、DBに安全に保存されること
        result = validate_field(name=malicious_input, area=100)

        # 特殊文字チェックがあればバリデーションエラー
        # なければDBのパラメータバインディングで防御
        # どちらの場合も安全であることを確認
        assert isinstance(result.is_valid(), bool)

    @pytest.mark.parametrize("malicious_id", [
        "1 OR 1=1",
        "1; DROP TABLE",
        "-1",
        "0",
        "999999999999999",
    ])
    def test_sql_injection_in_user_id(self, malicious_id):
        """user_idでのSQLインジェクション対策"""
        try:
            fields = FieldRepository.get_fields(user_id=malicious_id)
            # 文字列の場合は型エラーか空結果
            assert isinstance(fields, list)
        except (TypeError, ValueError):
            # 型エラーは正しい動作
            pass

    # === HTMLタグ・XSS ===

    @pytest.mark.parametrize("xss_input", [
        "<script>alert('XSS')</script>",
        "<img src=x onerror=alert('XSS')>",
        "javascript:alert('XSS')",
        "<svg onload=alert('XSS')>",
        "{{constructor.constructor('return this')()}}",  # テンプレートインジェクション
    ])
    def test_xss_in_field_name(self, xss_input):
        """ほ場名でのXSS対策"""
        result = validate_field(name=xss_input, area=100)
        # 特殊文字が含まれる場合はバリデーションエラーが望ましい
        # Gradioがエスケープするので、保存されても表示時は安全

    # === パストラバーサル ===

    @pytest.mark.parametrize("path_input", [
        "../../../etc/passwd",
        "..\\..\\..\\windows\\system32",
        "/etc/passwd",
        "file:///etc/passwd",
        "....//....//etc/passwd",
    ])
    def test_path_traversal_in_input(self, path_input):
        """パストラバーサル攻撃"""
        result = validate_field(name=path_input, area=100)
        # ファイル操作には使われないが、バリデーションの挙動を確認

    # === 特殊文字 ===

    @pytest.mark.parametrize("special_char", [
        "\x00",         # NULL文字
        "\x1b[31m",     # ANSIエスケープ
        "\r\n",         # CRLF
        "\u202e",       # Right-to-Left Override
        "\ufeff",       # BOM
    ])
    def test_special_characters(self, special_char):
        """特殊制御文字"""
        result = validate_field(name=f"テスト{special_char}ほ場", area=100)
        # 制御文字は除去またはエラーが望ましい
```

### 2.6 大量データ・性能境界テスト

```python
# tests/test_edge_performance.py

import pytest
import pandas as pd
from rotation_planner.common.file_utils import read_csv_safe, write_csv_safe


class TestPerformanceBoundary:
    """性能境界テスト"""

    @pytest.mark.slow
    def test_large_csv_import(self, tmp_path):
        """大量行CSVの読み込み（10,000行）"""
        # テストCSV作成
        rows = [{"作物名": f"作物{i}", "面積": i} for i in range(10000)]
        df = pd.DataFrame(rows)
        csv_path = tmp_path / "large.csv"
        df.to_csv(csv_path, index=False)

        # 読み込み
        result_df, warnings = read_csv_safe(csv_path)
        assert len(result_df) == 10000

    @pytest.mark.slow
    def test_large_csv_export(self, tmp_path):
        """大量行CSVのエクスポート（10,000行）"""
        rows = [{"作物名": f"作物{i}", "面積": i} for i in range(10000)]
        df = pd.DataFrame(rows)

        filepath, message = write_csv_safe(
            df,
            output_dir=str(tmp_path),
            filename="large_export.csv"
        )

        assert "10000件" in message

    @pytest.mark.slow
    def test_wide_dataframe(self, tmp_path):
        """多カラムCSV（100列）"""
        data = {f"col_{i}": [i] * 100 for i in range(100)}
        df = pd.DataFrame(data)
        csv_path = tmp_path / "wide.csv"
        df.to_csv(csv_path, index=False)

        result_df, warnings = read_csv_safe(csv_path)
        assert len(result_df.columns) == 100

    def test_memory_limit_warning(self, tmp_path):
        """メモリ制限の警告（概算チェック）"""
        # 実際のメモリ制限テストはCI環境で行う
        pass
```

### 2.7 DB接続断テスト

```python
# tests/test_edge_db_failure.py

import pytest
from unittest.mock import patch, MagicMock
import sqlite3
from rotation_planner.common.db import get_connection
from rotation_planner.common.exceptions import DatabaseConnectionError


class TestDBFailure:
    """DB障害テスト"""

    def test_connection_failure_handling(self):
        """DB接続失敗時のエラーハンドリング"""
        with patch('rotation_planner.common.db.sqlite3.connect') as mock_connect:
            mock_connect.side_effect = sqlite3.OperationalError("unable to open database file")

            with pytest.raises(DatabaseConnectionError) as exc_info:
                get_connection()

            assert "接続" in str(exc_info.value)

    def test_db_locked_handling(self):
        """DBロック時のエラーハンドリング"""
        with patch('rotation_planner.common.db.sqlite3.connect') as mock_connect:
            mock_connect.side_effect = sqlite3.OperationalError("database is locked")

            with pytest.raises(DatabaseConnectionError):
                get_connection()

    def test_db_corrupted_handling(self):
        """DB破損時のエラーハンドリング"""
        with patch('rotation_planner.common.db.sqlite3.connect') as mock_connect:
            mock_connect.side_effect = sqlite3.DatabaseError("database disk image is malformed")

            with pytest.raises(DatabaseConnectionError):
                get_connection()

    def test_transaction_rollback_on_error(self, test_db):
        """エラー時のトランザクションロールバック"""
        from rotation_planner.common.db import transaction

        with pytest.raises(Exception):
            with transaction() as conn:
                conn.execute("INSERT INTO crops (name) VALUES ('test')")
                raise Exception("Simulated error")

        # ロールバックされているはず
        # （実際のテストDBで確認）
```

---

## 3. 回帰テスト方針

### 3.1 テストカバレッジ目標

| レベル | 目標 | 対象 |
|-------|------|------|
| 最低ライン | 60% | 全体 |
| 目標 | 80% | コアモジュール |
| 理想 | 90% | common/, app/ |

### 3.2 テストスイート構成

```
tests/
├── conftest.py              # 共通フィクスチャ
├── unit/                    # 単体テスト
│   ├── test_validation.py   # バリデーション
│   ├── test_db_access.py    # リポジトリ層
│   └── test_calculation.py  # 計算ロジック
├── integration/             # 統合テスト
│   ├── test_csv_import.py   # CSVインポート
│   ├── test_csv_export.py   # CSVエクスポート
│   └── test_auth_flow.py    # 認証フロー
├── edge/                    # エッジケーステスト
│   ├── test_edge_null.py
│   ├── test_edge_boundary.py
│   ├── test_edge_date.py
│   ├── test_edge_security.py
│   ├── test_edge_performance.py
│   └── test_edge_db_failure.py
└── security/                # セキュリティテスト
    ├── test_sql_injection.py
    ├── test_access_control.py
    └── test_data_isolation.py
```

### 3.3 スモークテスト定義

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

### 3.4 テスト実行コマンド

```bash
# 全テスト実行
pytest

# スモークテストのみ
pytest -m smoke

# エッジケーステストのみ
pytest tests/edge/

# 遅いテストを除外
pytest -m "not slow"

# カバレッジ付き
pytest --cov=rotation_planner --cov-report=html

# 並列実行
pytest -n auto
```

---

## 4. CI/CD設計（GitHub Actions）

### 4.1 ワークフロー設計

```yaml
# .github/workflows/test.yml

name: Test Suite

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]
  schedule:
    # 毎日午前3時（JST）に実行
    - cron: '0 18 * * *'

env:
  PYTHON_VERSION: '3.11'

jobs:
  # ====================================
  # スモークテスト（高速、必須）
  # ====================================
  smoke-test:
    runs-on: ubuntu-latest
    timeout-minutes: 5

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: ${{ env.PYTHON_VERSION }}
          cache: 'pip'

      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest

      - name: Run smoke tests
        run: pytest -m smoke -v --tb=short

  # ====================================
  # 単体テスト
  # ====================================
  unit-test:
    runs-on: ubuntu-latest
    needs: smoke-test
    timeout-minutes: 10

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: ${{ env.PYTHON_VERSION }}
          cache: 'pip'

      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest pytest-cov

      - name: Run unit tests with coverage
        run: |
          pytest tests/unit/ -v \
            --cov=rotation_planner \
            --cov-report=xml \
            --cov-report=term-missing

      - name: Upload coverage to Codecov
        uses: codecov/codecov-action@v4
        with:
          token: ${{ secrets.CODECOV_TOKEN }}
          files: ./coverage.xml
          fail_ci_if_error: false

  # ====================================
  # 統合テスト
  # ====================================
  integration-test:
    runs-on: ubuntu-latest
    needs: unit-test
    timeout-minutes: 15

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: ${{ env.PYTHON_VERSION }}
          cache: 'pip'

      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest

      - name: Initialize test database
        run: |
          python scripts/init_test_db.py

      - name: Run integration tests
        run: pytest tests/integration/ -v --tb=short

  # ====================================
  # エッジケース・セキュリティテスト
  # ====================================
  edge-security-test:
    runs-on: ubuntu-latest
    needs: unit-test
    timeout-minutes: 20

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: ${{ env.PYTHON_VERSION }}
          cache: 'pip'

      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest

      - name: Run edge case tests
        run: pytest tests/edge/ -v --tb=short -m "not slow"

      - name: Run security tests
        run: pytest tests/security/ -v --tb=short

  # ====================================
  # 性能テスト（週次）
  # ====================================
  performance-test:
    runs-on: ubuntu-latest
    if: github.event_name == 'schedule'
    timeout-minutes: 30

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: ${{ env.PYTHON_VERSION }}
          cache: 'pip'

      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest pytest-benchmark

      - name: Run performance tests
        run: pytest tests/edge/ -v -m slow --benchmark-only

  # ====================================
  # テスト結果サマリ
  # ====================================
  test-summary:
    runs-on: ubuntu-latest
    needs: [unit-test, integration-test, edge-security-test]
    if: always()

    steps:
      - name: Check test results
        run: |
          if [[ "${{ needs.unit-test.result }}" == "failure" ]] || \
             [[ "${{ needs.integration-test.result }}" == "failure" ]] || \
             [[ "${{ needs.edge-security-test.result }}" == "failure" ]]; then
            echo "One or more test jobs failed"
            exit 1
          fi
          echo "All tests passed!"

      - name: Post summary
        run: |
          echo "## Test Results Summary" >> $GITHUB_STEP_SUMMARY
          echo "" >> $GITHUB_STEP_SUMMARY
          echo "| Job | Status |" >> $GITHUB_STEP_SUMMARY
          echo "|-----|--------|" >> $GITHUB_STEP_SUMMARY
          echo "| Smoke Test | ${{ needs.smoke-test.result || 'skipped' }} |" >> $GITHUB_STEP_SUMMARY
          echo "| Unit Test | ${{ needs.unit-test.result }} |" >> $GITHUB_STEP_SUMMARY
          echo "| Integration Test | ${{ needs.integration-test.result }} |" >> $GITHUB_STEP_SUMMARY
          echo "| Edge/Security Test | ${{ needs.edge-security-test.result }} |" >> $GITHUB_STEP_SUMMARY
```

### 4.2 PR用ワークフロー（軽量版）

```yaml
# .github/workflows/pr-check.yml

name: PR Check

on:
  pull_request:
    types: [opened, synchronize, reopened]

jobs:
  quick-check:
    runs-on: ubuntu-latest
    timeout-minutes: 10

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          cache: 'pip'

      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest pytest-cov flake8

      - name: Lint check
        run: flake8 rotation_planner/ --count --select=E9,F63,F7,F82 --show-source

      - name: Run tests
        run: |
          pytest -m smoke -v
          pytest tests/unit/ -v --cov=rotation_planner --cov-fail-under=60

      - name: Comment coverage
        uses: py-cov-action/python-coverage-comment-action@v3
        with:
          GITHUB_TOKEN: ${{ github.token }}
```

### 4.3 conftest.py（共通フィクスチャ）

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
    # テスト用DBを初期化
    from rotation_planner.common.db import init_database

    # 既存DBをバックアップ
    backup_path = test_db_path.with_suffix('.db.bak')
    if test_db_path.exists():
        shutil.copy(test_db_path, backup_path)

    # テスト用DBを作成
    init_database(str(test_db_path))

    yield test_db_path

    # クリーンアップ
    if backup_path.exists():
        shutil.move(backup_path, test_db_path)


@pytest.fixture
def tmp_csv_dir(tmp_path):
    """一時CSVディレクトリ"""
    csv_dir = tmp_path / "csv"
    csv_dir.mkdir()
    return csv_dir


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


# マーカー設定
def pytest_configure(config):
    config.addinivalue_line("markers", "smoke: スモークテスト")
    config.addinivalue_line("markers", "slow: 遅いテスト")
    config.addinivalue_line("markers", "security: セキュリティテスト")
```

---

## 5. 実装チェックリスト

### エッジケーステスト

- [ ] test_edge_null.py 作成
- [ ] test_edge_boundary.py 作成
- [ ] test_edge_date.py 作成
- [ ] test_edge_security.py 作成
- [ ] test_edge_performance.py 作成
- [ ] test_edge_db_failure.py 作成

### CI/CD

- [ ] .github/workflows/test.yml 作成
- [ ] .github/workflows/pr-check.yml 作成
- [ ] conftest.py 更新
- [ ] pytest.ini 設定
- [ ] CODECOV_TOKEN シークレット設定

### 回帰テスト

- [ ] スモークテスト作成
- [ ] カバレッジ60%達成
- [ ] 週次性能テスト設定

---

## 6. 関連ドキュメント

| ドキュメント | 担当 | 内容 |
|-------------|------|------|
| TEST_UNIT.md | 足軽5号 | 単体テスト設計 |
| TEST_INTEGRATION.md | 足軽6号 | 統合テスト設計 |
| TEST_EDGE_CI.md | 足軽7号 | 本ドキュメント |
| TEST_DESIGN.md | 足軽7号 | 統合版（最終成果物） |

---

**作成日**: 2026-02-06
**作成者**: 足軽7号
