# 統合テスト・データ整合性テスト設計書

> **プロジェクト**: rotation-planner
> **技術スタック**: Gradio + SQLite + pytest
> **作成日**: 2026-02-06
> **Version**: 1.0
> **重要度**: 高（殿より「データ整合性テスト重視」の指示）

---

## 1. 概要

本ドキュメントは、rotation-plannerの統合テストおよびデータ整合性テストの設計を定義する。

**テスト方針**:
- データ整合性を最優先で検証
- 輪作ルールのビジネスロジックを厳密にテスト
- 境界条件・異常系を網羅的にカバー
- テストの自動化・CI/CD組み込みを前提

---

## 2. テスト構成

### 2.1 テストレベル

```
┌─────────────────────────────────────────────────────────────────┐
│  E2E Tests (End-to-End)                                         │
│  - Gradio UIからの操作シナリオ                                   │
│  - ブラウザ自動化 (Playwright/Selenium)                          │
└─────────────────────────────────────────────────────────────────┘
                              ▲
┌─────────────────────────────────────────────────────────────────┐
│  Integration Tests（本設計書の対象）                             │
│  - DB操作の一連の流れ                                           │
│  - ビジネスロジック + DB連携                                     │
│  - データ整合性検証 ★最重要                                     │
└─────────────────────────────────────────────────────────────────┘
                              ▲
┌─────────────────────────────────────────────────────────────────┐
│  Unit Tests                                                      │
│  - 個別関数のテスト                                              │
│  - バリデーション関数                                            │
│  - ユーティリティ関数                                            │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 テストディレクトリ構成

```
rotation-planner/
├── tests/
│   ├── conftest.py              # 共通フィクスチャ
│   ├── fixtures/
│   │   ├── seed_data.py         # シードデータ
│   │   └── test_db.py           # テストDB管理
│   ├── unit/
│   │   ├── test_validation.py
│   │   └── test_utils.py
│   ├── integration/
│   │   ├── test_crud_crops.py
│   │   ├── test_crud_fields.py
│   │   ├── test_crud_plantings.py
│   │   └── test_data_integrity.py  ★最重要
│   └── e2e/
│       └── test_scenarios.py
└── pytest.ini
```

---

## 3. 統合テスト設計

### 3.1 テストケース一覧：CRUD操作

#### 3.1.1 作物（Crops）

| ID | テストケース | 期待結果 | 優先度 |
|----|-------------|---------|--------|
| TC-CROP-001 | 作物の新規登録 | 正常にINSERT、IDが返る | 高 |
| TC-CROP-002 | 重複する作物名で登録 | DuplicateKeyError | 高 |
| TC-CROP-003 | 必須項目なしで登録 | NotNullViolationError | 高 |
| TC-CROP-004 | 作物の更新 | 正常にUPDATE | 中 |
| TC-CROP-005 | 存在しないIDで更新 | RecordNotFoundError | 中 |
| TC-CROP-006 | 作物の削除 | 正常にDELETE | 中 |
| TC-CROP-007 | 栽培履歴のある作物を削除 | ForeignKeyViolationError | 高 |
| TC-CROP-008 | 作物一覧取得 | 全件取得、名前順ソート | 低 |
| TC-CROP-009 | 存在しないIDで取得 | None返却 | 低 |

#### 3.1.2 圃場（Fields）

| ID | テストケース | 期待結果 | 優先度 |
|----|-------------|---------|--------|
| TC-FIELD-001 | 圃場の新規登録 | 正常にINSERT | 高 |
| TC-FIELD-002 | 重複する圃場名で登録 | DuplicateKeyError | 高 |
| TC-FIELD-003 | 圃場の更新 | 正常にUPDATE | 中 |
| TC-FIELD-004 | 栽培履歴のある圃場を削除 | ForeignKeyViolationError | 高 |

#### 3.1.3 栽培履歴（Plantings）

| ID | テストケース | 期待結果 | 優先度 |
|----|-------------|---------|--------|
| TC-PLANT-001 | 栽培記録の新規登録 | 正常にINSERT | 高 |
| TC-PLANT-002 | 存在しない作物IDで登録 | ForeignKeyViolationError | 高 |
| TC-PLANT-003 | 存在しない圃場IDで登録 | ForeignKeyViolationError | 高 |
| TC-PLANT-004 | 収穫日の更新 | 正常にUPDATE | 中 |
| TC-PLANT-005 | 栽培記録の削除 | 正常にDELETE | 中 |

### 3.2 テストケース一覧：トランザクション

| ID | テストケース | 期待結果 | 優先度 |
|----|-------------|---------|--------|
| TC-TXN-001 | 複数操作の一括コミット | 全て反映される | 高 |
| TC-TXN-002 | 途中エラーでのロールバック | 全て巻き戻される | 高 |
| TC-TXN-003 | ネストしたトランザクション | 外側でまとめてコミット | 中 |

---

## 4. データ整合性テスト設計（最重要）

### 4.1 輪作ルール違反検出

#### 4.1.1 同一科の連作禁止

**ビジネスルール**:
- 同一科の作物は、設定された輪作間隔（年）を空けなければならない
- 例: ナス科（トマト、ナス、ピーマン）は3年間隔

| ID | テストケース | 入力 | 期待結果 | 優先度 |
|----|-------------|------|---------|--------|
| TC-ROT-001 | 連作間隔内に同一科を作付け | トマト(ナス科)の翌年にナス(ナス科) | RotationViolationError | 最高 |
| TC-ROT-002 | 連作間隔を超えて同一科を作付け | トマト(ナス科)の4年後にナス(ナス科) | 正常登録 | 最高 |
| TC-ROT-003 | 連作間隔ちょうどで同一科を作付け | トマト(ナス科)の3年後にナス(ナス科) | 正常登録 | 最高 |
| TC-ROT-004 | 同一作物の連続作付け | トマトの翌年にトマト | RotationViolationError | 最高 |
| TC-ROT-005 | 異なる科なら連続作付け可能 | トマト(ナス科)の翌年にキャベツ(アブラナ科) | 正常登録 | 高 |

```python
# テストコード例
class TestRotationRules:
    """輪作ルール検証テスト"""

    def test_same_family_within_interval_should_fail(self, db_session, seed_crops, seed_fields):
        """同一科の連作禁止期間内の作付けは失敗すべき"""
        # Given: トマト（ナス科、間隔3年）を2024年に作付け済み
        tomato = seed_crops["tomato"]  # family="ナス科", interval_years=3
        field = seed_fields["field_a"]

        create_planting(
            db_session,
            crop_id=tomato.id,
            field_id=field.id,
            planted_date="2024-04-01"
        )

        # When: 翌年（2025年）に同じ科のナスを作付けしようとする
        eggplant = seed_crops["eggplant"]  # family="ナス科"

        # Then: RotationViolationError が発生すべき
        with pytest.raises(RotationViolationError) as exc_info:
            create_planting(
                db_session,
                crop_id=eggplant.id,
                field_id=field.id,
                planted_date="2025-04-01"
            )

        assert "ナス科" in str(exc_info.value)
        assert "3年" in str(exc_info.value)

    def test_same_family_after_interval_should_succeed(self, db_session, seed_crops, seed_fields):
        """連作間隔を超えた作付けは成功すべき"""
        # Given: トマト（ナス科、間隔3年）を2024年に作付け済み
        tomato = seed_crops["tomato"]
        field = seed_fields["field_a"]

        create_planting(
            db_session,
            crop_id=tomato.id,
            field_id=field.id,
            planted_date="2024-04-01"
        )

        # When: 4年後（2028年）に同じ科のナスを作付け
        eggplant = seed_crops["eggplant"]

        # Then: 正常に登録される
        planting = create_planting(
            db_session,
            crop_id=eggplant.id,
            field_id=field.id,
            planted_date="2028-04-01"
        )

        assert planting.id is not None
```

#### 4.1.2 相性の悪い作物の検出

**ビジネスルール**:
- 特定の作物同士は連続作付けを避けるべき
- 例: キャベツの後にブロッコリー（同じアブラナ科で病害リスク）

| ID | テストケース | 入力 | 期待結果 | 優先度 |
|----|-------------|------|---------|--------|
| TC-COMPAT-001 | 相性の悪い作物を連続作付け | キャベツ→ブロッコリー | CompanionWarning（警告） | 高 |
| TC-COMPAT-002 | 相性の良い作物を連続作付け | ナス→トウモロコシ | 正常登録（推奨表示） | 中 |

### 4.2 作付け期間の重複検出

**ビジネスルール**:
- 同一圃場で作付け期間が重複する作物は登録できない
- 期間 = planted_date 〜 harvested_date（または現在日）

| ID | テストケース | 入力 | 期待結果 | 優先度 |
|----|-------------|------|---------|--------|
| TC-OVERLAP-001 | 完全重複（同一期間） | 同圃場に同期間で2作物 | PeriodOverlapError | 最高 |
| TC-OVERLAP-002 | 部分重複（開始が期間内） | 作物Aの期間中に作物B開始 | PeriodOverlapError | 最高 |
| TC-OVERLAP-003 | 部分重複（終了が期間内） | 作物Aの期間中に作物B終了 | PeriodOverlapError | 最高 |
| TC-OVERLAP-004 | 包含（既存期間が新規を包含） | 長期作物の期間中に短期作物 | PeriodOverlapError | 最高 |
| TC-OVERLAP-005 | 隣接（終了日=開始日） | 前作の収穫日に次作を開始 | 正常登録 | 高 |
| TC-OVERLAP-006 | 重複なし | 期間が離れている | 正常登録 | 高 |
| TC-OVERLAP-007 | 収穫日未設定（栽培中） | 栽培中作物がある圃場に新規 | PeriodOverlapError | 最高 |
| TC-OVERLAP-008 | 別圃場なら同期間OK | 別圃場で同期間に同作物 | 正常登録 | 高 |

```python
# テストコード例
class TestPeriodOverlap:
    """作付け期間重複検証テスト"""

    def test_complete_overlap_should_fail(self, db_session, seed_crops, seed_fields):
        """完全重複は失敗すべき"""
        # Given: 圃場Aに4/1〜6/30でトマト作付け済み
        tomato = seed_crops["tomato"]
        field = seed_fields["field_a"]

        create_planting(
            db_session,
            crop_id=tomato.id,
            field_id=field.id,
            planted_date="2026-04-01",
            harvested_date="2026-06-30"
        )

        # When: 同圃場に同期間でキュウリを作付けしようとする
        cucumber = seed_crops["cucumber"]

        # Then: PeriodOverlapError が発生すべき
        with pytest.raises(PeriodOverlapError) as exc_info:
            create_planting(
                db_session,
                crop_id=cucumber.id,
                field_id=field.id,
                planted_date="2026-04-01",
                harvested_date="2026-06-30"
            )

        assert "期間が重複" in str(exc_info.value)

    def test_partial_overlap_start_inside_should_fail(self, db_session, seed_crops, seed_fields):
        """部分重複（開始が期間内）は失敗すべき"""
        # Given: 圃場Aに4/1〜6/30でトマト作付け済み
        tomato = seed_crops["tomato"]
        field = seed_fields["field_a"]

        create_planting(
            db_session,
            crop_id=tomato.id,
            field_id=field.id,
            planted_date="2026-04-01",
            harvested_date="2026-06-30"
        )

        # When: 5/1〜7/31でキュウリを作付けしようとする
        cucumber = seed_crops["cucumber"]

        # Then: PeriodOverlapError が発生すべき
        with pytest.raises(PeriodOverlapError):
            create_planting(
                db_session,
                crop_id=cucumber.id,
                field_id=field.id,
                planted_date="2026-05-01",
                harvested_date="2026-07-31"
            )

    def test_adjacent_periods_should_succeed(self, db_session, seed_crops, seed_fields):
        """隣接期間（終了日=開始日）は成功すべき"""
        # Given: 圃場Aに4/1〜6/30でトマト作付け済み
        tomato = seed_crops["tomato"]
        field = seed_fields["field_a"]

        create_planting(
            db_session,
            crop_id=tomato.id,
            field_id=field.id,
            planted_date="2026-04-01",
            harvested_date="2026-06-30"
        )

        # When: 7/1〜（収穫日当日に次作開始）でキュウリを作付け
        cucumber = seed_crops["cucumber"]

        # Then: 正常に登録される
        planting = create_planting(
            db_session,
            crop_id=cucumber.id,
            field_id=field.id,
            planted_date="2026-07-01"
        )

        assert planting.id is not None

    def test_ongoing_cultivation_should_block(self, db_session, seed_crops, seed_fields):
        """栽培中（収穫日未設定）の圃場への作付けは失敗すべき"""
        # Given: 圃場Aに4/1〜（栽培中）でトマト作付け済み
        tomato = seed_crops["tomato"]
        field = seed_fields["field_a"]

        create_planting(
            db_session,
            crop_id=tomato.id,
            field_id=field.id,
            planted_date="2026-04-01",
            harvested_date=None  # 栽培中
        )

        # When: 同圃場に新規作付けしようとする
        cucumber = seed_crops["cucumber"]

        # Then: PeriodOverlapError が発生すべき
        with pytest.raises(PeriodOverlapError) as exc_info:
            create_planting(
                db_session,
                crop_id=cucumber.id,
                field_id=field.id,
                planted_date="2026-05-01"
            )

        assert "栽培中" in str(exc_info.value)
```

### 4.3 マスタデータとの整合性

| ID | テストケース | 入力 | 期待結果 | 優先度 |
|----|-------------|------|---------|--------|
| TC-REF-001 | 存在しない作物IDで栽培記録 | crop_id=9999 | ForeignKeyViolationError | 高 |
| TC-REF-002 | 存在しない圃場IDで栽培記録 | field_id=9999 | ForeignKeyViolationError | 高 |
| TC-REF-003 | 削除済み作物IDで栽培記録 | 論理削除された作物 | ForeignKeyViolationError or 警告 | 中 |

### 4.4 FK制約・カスケード動作

| ID | テストケース | 操作 | 期待結果 | 優先度 |
|----|-------------|------|---------|--------|
| TC-FK-001 | 栽培履歴のある作物を削除 | DELETE crops WHERE id=X | ForeignKeyViolationError | 最高 |
| TC-FK-002 | 栽培履歴のある圃場を削除 | DELETE fields WHERE id=X | ForeignKeyViolationError | 最高 |
| TC-FK-003 | 作物削除後に栽培履歴確認 | 削除成功した場合 | 関連履歴は残る or 削除される | 高 |
| TC-FK-004 | 圃場削除後に栽培履歴確認 | 削除成功した場合 | 関連履歴は残る or 削除される | 高 |

```python
# テストコード例
class TestForeignKeyConstraints:
    """外部キー制約検証テスト"""

    def test_delete_crop_with_history_should_fail(self, db_session, seed_crops, seed_fields):
        """栽培履歴のある作物は削除できないべき"""
        # Given: トマトに栽培履歴がある
        tomato = seed_crops["tomato"]
        field = seed_fields["field_a"]

        create_planting(
            db_session,
            crop_id=tomato.id,
            field_id=field.id,
            planted_date="2026-04-01"
        )

        # When: トマトを削除しようとする
        # Then: ForeignKeyViolationError が発生すべき
        with pytest.raises(ForeignKeyViolationError) as exc_info:
            delete_crop(db_session, tomato.id)

        assert "栽培履歴" in str(exc_info.value)
```

### 4.5 同時更新時の競合（排他制御）

| ID | テストケース | シナリオ | 期待結果 | 優先度 |
|----|-------------|---------|---------|--------|
| TC-LOCK-001 | 楽観的ロック違反 | 同一レコードを2つのセッションが更新 | OptimisticLockError | 中 |
| TC-LOCK-002 | 更新中にロック待ち | セッション1がロック中にセッション2が更新 | タイムアウト or 待機 | 中 |
| TC-LOCK-003 | デッドロック | 相互ロック | デッドロック検出、片方ロールバック | 低 |

```python
# テストコード例（楽観的ロック）
class TestOptimisticLocking:
    """楽観的ロック検証テスト"""

    def test_concurrent_update_should_fail_for_second(self, db_session):
        """同時更新で後の更新は失敗すべき（楽観的ロック）"""
        # Given: 作物レコードを取得（version=1）
        crop = get_crop(db_session, 1)
        original_version = crop.version

        # When: セッション1が更新（version→2）
        update_crop(db_session, crop.id, name="トマト改", version=original_version)

        # Then: 同じversionで別の更新を試みると失敗
        with pytest.raises(OptimisticLockError):
            update_crop(db_session, crop.id, name="トマト改2", version=original_version)
```

---

## 5. テストデータ設計

### 5.1 フィクスチャ設計（pytest fixtures）

```python
# tests/conftest.py
import pytest
import sqlite3
import os
from pathlib import Path

TEST_DB_PATH = "tests/test_rotation.db"

@pytest.fixture(scope="function")
def db_session():
    """テスト用DBセッション（各テスト後にロールバック）"""
    # テストDB作成
    conn = sqlite3.connect(TEST_DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")

    # スキーマ適用
    apply_schema(conn)

    yield conn

    # クリーンアップ
    conn.rollback()
    conn.close()
    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)

@pytest.fixture(scope="function")
def db_session_committed(db_session):
    """コミット済みDBセッション（データ永続化テスト用）"""
    yield db_session
    db_session.commit()

@pytest.fixture
def seed_crops(db_session):
    """テスト用作物データ"""
    crops = {
        "tomato": insert_crop(db_session, "トマト", "ナス科", 3),
        "eggplant": insert_crop(db_session, "ナス", "ナス科", 3),
        "pepper": insert_crop(db_session, "ピーマン", "ナス科", 3),
        "cabbage": insert_crop(db_session, "キャベツ", "アブラナ科", 2),
        "broccoli": insert_crop(db_session, "ブロッコリー", "アブラナ科", 2),
        "cucumber": insert_crop(db_session, "キュウリ", "ウリ科", 2),
        "corn": insert_crop(db_session, "トウモロコシ", "イネ科", 1),
    }
    db_session.commit()
    return crops

@pytest.fixture
def seed_fields(db_session):
    """テスト用圃場データ"""
    fields = {
        "field_a": insert_field(db_session, "圃場A", area=10.0),
        "field_b": insert_field(db_session, "圃場B", area=15.0),
        "field_c": insert_field(db_session, "圃場C", area=8.5),
    }
    db_session.commit()
    return fields

@pytest.fixture
def seed_plantings(db_session, seed_crops, seed_fields):
    """テスト用栽培履歴データ"""
    plantings = [
        # 圃場A: 2024年トマト、2025年キュウリ
        insert_planting(db_session, seed_crops["tomato"].id, seed_fields["field_a"].id,
                        "2024-04-01", "2024-08-31"),
        insert_planting(db_session, seed_crops["cucumber"].id, seed_fields["field_a"].id,
                        "2025-04-01", "2025-07-31"),
        # 圃場B: 2024年キャベツ（栽培中）
        insert_planting(db_session, seed_crops["cabbage"].id, seed_fields["field_b"].id,
                        "2024-09-01", None),
    ]
    db_session.commit()
    return plantings
```

### 5.2 シードデータ定義

```python
# tests/fixtures/seed_data.py
"""テスト用シードデータ定義"""

SEED_CROPS = [
    {"name": "トマト", "family": "ナス科", "interval_years": 3},
    {"name": "ナス", "family": "ナス科", "interval_years": 3},
    {"name": "ピーマン", "family": "ナス科", "interval_years": 3},
    {"name": "キャベツ", "family": "アブラナ科", "interval_years": 2},
    {"name": "ブロッコリー", "family": "アブラナ科", "interval_years": 2},
    {"name": "ハクサイ", "family": "アブラナ科", "interval_years": 2},
    {"name": "キュウリ", "family": "ウリ科", "interval_years": 2},
    {"name": "スイカ", "family": "ウリ科", "interval_years": 4},
    {"name": "トウモロコシ", "family": "イネ科", "interval_years": 1},
    {"name": "ニンジン", "family": "セリ科", "interval_years": 2},
]

SEED_FIELDS = [
    {"name": "圃場A", "area": 10.0},
    {"name": "圃場B", "area": 15.0},
    {"name": "圃場C", "area": 8.5},
    {"name": "圃場D", "area": 20.0},
]

# 輪作ルール検証用の履歴データ
SEED_PLANTINGS_FOR_ROTATION_TEST = [
    # 圃場A: ナス科→（3年必要）
    {"field": "圃場A", "crop": "トマト", "planted": "2024-04-01", "harvested": "2024-08-31"},

    # 圃場B: アブラナ科→（2年必要）
    {"field": "圃場B", "crop": "キャベツ", "planted": "2024-09-01", "harvested": "2024-12-31"},

    # 圃場C: ウリ科→ウリ科で連作テスト用
    {"field": "圃場C", "crop": "キュウリ", "planted": "2025-04-01", "harvested": "2025-07-31"},
]
```

### 5.3 テストDB初期化・クリーンアップ

```python
# tests/fixtures/test_db.py
"""テストDB管理"""

import sqlite3
import os
from pathlib import Path

SCHEMA_PATH = "schema/rotation_planner.sql"

def apply_schema(conn: sqlite3.Connection):
    """スキーマを適用"""
    schema_sql = Path(SCHEMA_PATH).read_text()
    conn.executescript(schema_sql)

def reset_test_db(db_path: str):
    """テストDBを完全リセット"""
    if os.path.exists(db_path):
        os.remove(db_path)

    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    apply_schema(conn)
    conn.close()

def seed_all(conn: sqlite3.Connection):
    """全シードデータを投入"""
    from tests.fixtures.seed_data import SEED_CROPS, SEED_FIELDS

    for crop in SEED_CROPS:
        conn.execute(
            "INSERT INTO crops (name, family, interval_years) VALUES (?, ?, ?)",
            (crop["name"], crop["family"], crop["interval_years"])
        )

    for field in SEED_FIELDS:
        conn.execute(
            "INSERT INTO fields (name, area) VALUES (?, ?)",
            (field["name"], field["area"])
        )

    conn.commit()
```

---

## 6. テストコード実装例

### 6.1 CRUD統合テスト

```python
# tests/integration/test_crud_crops.py
"""作物CRUD統合テスト"""

import pytest
from rotation_planner.repository import (
    insert_crop, get_crop, update_crop, delete_crop, get_all_crops
)
from rotation_planner.exceptions import (
    DuplicateKeyError, NotNullViolationError, ForeignKeyViolationError, RecordNotFoundError
)

class TestCropCRUD:
    """作物CRUDテスト"""

    def test_insert_crop_success(self, db_session):
        """作物の新規登録が成功すること"""
        # When
        crop = insert_crop(db_session, "トマト", "ナス科", 3)

        # Then
        assert crop.id is not None
        assert crop.name == "トマト"
        assert crop.family == "ナス科"
        assert crop.interval_years == 3

    def test_insert_duplicate_name_should_fail(self, db_session):
        """重複する作物名での登録は失敗すること"""
        # Given
        insert_crop(db_session, "トマト", "ナス科", 3)

        # When/Then
        with pytest.raises(DuplicateKeyError) as exc_info:
            insert_crop(db_session, "トマト", "ナス科", 3)

        assert "トマト" in str(exc_info.value)

    def test_insert_without_required_field_should_fail(self, db_session):
        """必須項目なしでの登録は失敗すること"""
        # When/Then
        with pytest.raises(NotNullViolationError):
            insert_crop(db_session, None, "ナス科", 3)

    def test_update_crop_success(self, db_session, seed_crops):
        """作物の更新が成功すること"""
        # Given
        tomato = seed_crops["tomato"]

        # When
        update_crop(db_session, tomato.id, name="ミニトマト", family="ナス科", interval_years=3)

        # Then
        updated = get_crop(db_session, tomato.id)
        assert updated.name == "ミニトマト"

    def test_update_nonexistent_should_fail(self, db_session):
        """存在しないIDでの更新は失敗すること"""
        # When/Then
        with pytest.raises(RecordNotFoundError):
            update_crop(db_session, 9999, name="Test", family="Test", interval_years=1)

    def test_delete_crop_with_history_should_fail(self, db_session, seed_crops, seed_plantings):
        """栽培履歴のある作物の削除は失敗すること"""
        # Given: seed_plantingsでトマトに履歴がある
        tomato = seed_crops["tomato"]

        # When/Then
        with pytest.raises(ForeignKeyViolationError) as exc_info:
            delete_crop(db_session, tomato.id)

        assert "栽培履歴" in str(exc_info.value)
```

### 6.2 データ整合性テスト

```python
# tests/integration/test_data_integrity.py
"""データ整合性テスト（最重要）"""

import pytest
from datetime import date, timedelta
from rotation_planner.repository import create_planting
from rotation_planner.exceptions import (
    RotationViolationError, PeriodOverlapError, ForeignKeyViolationError
)

class TestRotationRulesIntegrity:
    """輪作ルール整合性テスト"""

    @pytest.mark.parametrize("years_after,should_fail", [
        (1, True),   # 1年後: 失敗
        (2, True),   # 2年後: 失敗
        (3, False),  # 3年後（ちょうど）: 成功
        (4, False),  # 4年後: 成功
    ])
    def test_same_family_rotation_interval(
        self, db_session, seed_crops, seed_fields, years_after, should_fail
    ):
        """同一科の輪作間隔が正しく検証されること"""
        # Given: トマト（ナス科、間隔3年）を2024年に作付け
        tomato = seed_crops["tomato"]
        eggplant = seed_crops["eggplant"]
        field = seed_fields["field_a"]

        create_planting(db_session, tomato.id, field.id, "2024-04-01", "2024-08-31")
        db_session.commit()

        # When: N年後にナスを作付け
        target_year = 2024 + years_after
        planted_date = f"{target_year}-04-01"

        # Then
        if should_fail:
            with pytest.raises(RotationViolationError):
                create_planting(db_session, eggplant.id, field.id, planted_date)
        else:
            planting = create_planting(db_session, eggplant.id, field.id, planted_date)
            assert planting.id is not None


class TestPeriodOverlapIntegrity:
    """作付け期間重複整合性テスト"""

    def test_complete_overlap_detected(self, db_session, seed_crops, seed_fields):
        """完全重複が検出されること"""
        tomato = seed_crops["tomato"]
        cucumber = seed_crops["cucumber"]
        field = seed_fields["field_a"]

        create_planting(db_session, tomato.id, field.id, "2026-04-01", "2026-06-30")
        db_session.commit()

        with pytest.raises(PeriodOverlapError):
            create_planting(db_session, cucumber.id, field.id, "2026-04-01", "2026-06-30")

    def test_partial_overlap_start_detected(self, db_session, seed_crops, seed_fields):
        """部分重複（開始が期間内）が検出されること"""
        tomato = seed_crops["tomato"]
        cucumber = seed_crops["cucumber"]
        field = seed_fields["field_a"]

        create_planting(db_session, tomato.id, field.id, "2026-04-01", "2026-06-30")
        db_session.commit()

        with pytest.raises(PeriodOverlapError):
            create_planting(db_session, cucumber.id, field.id, "2026-05-01", "2026-07-31")

    def test_different_field_no_overlap(self, db_session, seed_crops, seed_fields):
        """別圃場なら同期間でも重複しないこと"""
        tomato = seed_crops["tomato"]
        cucumber = seed_crops["cucumber"]
        field_a = seed_fields["field_a"]
        field_b = seed_fields["field_b"]

        create_planting(db_session, tomato.id, field_a.id, "2026-04-01", "2026-06-30")
        db_session.commit()

        # 別圃場なら同期間OK
        planting = create_planting(db_session, cucumber.id, field_b.id, "2026-04-01", "2026-06-30")
        assert planting.id is not None


class TestForeignKeyIntegrity:
    """外部キー整合性テスト"""

    def test_invalid_crop_id_rejected(self, db_session, seed_fields):
        """存在しない作物IDは拒否されること"""
        field = seed_fields["field_a"]

        with pytest.raises(ForeignKeyViolationError):
            create_planting(db_session, crop_id=9999, field_id=field.id, planted_date="2026-04-01")

    def test_invalid_field_id_rejected(self, db_session, seed_crops):
        """存在しない圃場IDは拒否されること"""
        tomato = seed_crops["tomato"]

        with pytest.raises(ForeignKeyViolationError):
            create_planting(db_session, crop_id=tomato.id, field_id=9999, planted_date="2026-04-01")
```

---

## 7. pytest設定

### 7.1 pytest.ini

```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*

# マーカー定義
markers =
    integration: 統合テスト
    unit: ユニットテスト
    slow: 時間のかかるテスト
    data_integrity: データ整合性テスト（最重要）

# カバレッジ設定
addopts = --cov=rotation_planner --cov-report=html --cov-report=term-missing

# 警告表示
filterwarnings =
    ignore::DeprecationWarning
```

### 7.2 テスト実行コマンド

```bash
# 全テスト実行
pytest

# 統合テストのみ
pytest -m integration

# データ整合性テストのみ（最重要）
pytest -m data_integrity

# 特定ファイル
pytest tests/integration/test_data_integrity.py

# 詳細出力
pytest -v --tb=short

# カバレッジレポート生成
pytest --cov=rotation_planner --cov-report=html
```

---

## 8. 実装チェックリスト

### 8.1 テスト環境

- [ ] pytest インストール
- [ ] pytest-cov インストール
- [ ] tests/ ディレクトリ作成
- [ ] conftest.py 作成
- [ ] pytest.ini 作成

### 8.2 フィクスチャ

- [ ] db_session フィクスチャ
- [ ] seed_crops フィクスチャ
- [ ] seed_fields フィクスチャ
- [ ] seed_plantings フィクスチャ

### 8.3 統合テスト

- [ ] test_crud_crops.py
- [ ] test_crud_fields.py
- [ ] test_crud_plantings.py

### 8.4 データ整合性テスト（最重要）

- [ ] 輪作ルール違反検出テスト
- [ ] 作付け期間重複検出テスト
- [ ] FK制約検証テスト
- [ ] カスケード動作テスト
- [ ] 同時更新競合テスト

---

## 参考資料

- [pytest 公式ドキュメント](https://docs.pytest.org/)
- [pytest-cov](https://pytest-cov.readthedocs.io/)
- [SQLite テストパターン](https://www.sqlite.org/testing.html)
- ERROR_DB_VALIDATION.md - DB操作エラー設計
- ERROR_HANDLING_DESIGN.md - 統合エラー処理設計
