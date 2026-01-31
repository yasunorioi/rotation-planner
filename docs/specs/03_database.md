# DB仕様書

> **Version**: 1.0
> **Last Updated**: 2026-02-01

## 1. データベース概要

### 1.1 データベース情報

| 項目 | 値 |
|------|-----|
| DBMS | SQLite 3 |
| ファイルパス | `data/rotation_planner.db` |
| 文字コード | UTF-8 |
| 外部キー制約 | 有効（`PRAGMA foreign_keys = ON`） |

### 1.2 ファイル配置

```
rotation_planner_ui/
├── data/
│   ├── rotation_planner.db          # 本番DB
│   └── backups/
│       ├── rotation_planner_YYYYMMDD_HHMMSS.db         # 日次バックアップ
│       └── rotation_planner_YYYYMMDD_HHMMSS_yearly.db  # 年次バックアップ
├── db_schema.sql                    # 初期スキーマ
└── scripts/
    ├── migrate_crop_schema.sql      # 作物スキーマ マイグレーション
    └── migrate_pesticide_orders.sql # 農薬発注 マイグレーション
```

---

## 2. テーブル一覧

| # | テーブル名 | 用途 |
|---|-----------|------|
| 1 | organizations | 組織マスタ（JA、個人農家グループ等） |
| 2 | users | ユーザー（農家、JA職員、管理者） |
| 3 | fields | ほ場 |
| 4 | crop_history | 作付履歴 |
| 5 | rotation_plans | 輪作計画 |
| 6 | plan_details | 輪作計画詳細 |
| 7 | crop_constraints | 作物制約 |
| 8 | pesticide_masters | 防除マスタ |
| 9 | inventory | 在庫 |
| 10 | crop_master | 作物マスタ |
| 11 | user_crops | ユーザー作物選択 |
| 12 | pesticide_orders | 農薬発注 |

---

## 3. テーブル定義

### 3.1 organizations（組織マスタ）

JA、協同組合、個人農家グループなどの組織情報を管理。

| カラム名 | 型 | 制約 | 説明 |
|---------|-----|------|------|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT | 組織ID |
| name | TEXT | NOT NULL | 組織名 |
| type | TEXT | NOT NULL, CHECK | 組織種別（'JA', 'cooperative', 'individual'） |
| settings_json | TEXT | - | 設定情報（JSON） |
| created_at | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | 作成日時 |
| updated_at | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | 更新日時 |

**制約**:
- `type IN ('JA', 'cooperative', 'individual')`

**初期データ**:
- `id=1`: JA北海道（JA）
- `id=2`: 個人農家（デフォルト）（individual）

---

### 3.2 users（ユーザー）

農家、JA職員、管理者のアカウント情報を管理。

| カラム名 | 型 | 制約 | 説明 |
|---------|-----|------|------|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT | ユーザーID |
| username | TEXT | NOT NULL UNIQUE | ログインID |
| password_hash | TEXT | NOT NULL | パスワードハッシュ |
| display_name | TEXT | NOT NULL | 表示名 |
| email | TEXT | - | メールアドレス |
| role | TEXT | NOT NULL, CHECK | 権限（'farmer', 'ja_staff', 'admin'） |
| org_id | INTEGER | REFERENCES organizations(id) | 所属組織ID |
| is_active | INTEGER | DEFAULT 1 | アクティブフラグ（1:有効, 0:無効） |
| created_at | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | 作成日時 |
| updated_at | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | 更新日時 |

**制約**:
- `role IN ('farmer', 'ja_staff', 'admin')`

**インデックス**:
- `idx_users_org` ON users(org_id)
- `idx_users_role` ON users(role)

---

### 3.3 fields（ほ場）

農家が管理するほ場（農地）の情報。

| カラム名 | 型 | 制約 | 説明 |
|---------|-----|------|------|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT | ほ場ID |
| user_id | INTEGER | NOT NULL, FK | 所有者ユーザーID |
| field_code | TEXT | NOT NULL | ほ場コード（ユーザー内で一意） |
| district | TEXT | - | 地区名 |
| name | TEXT | - | ほ場名 |
| area_ha | REAL | NOT NULL | 面積（ha） |
| area_a | REAL | GENERATED | 面積（a）= area_ha * 100 |
| beet_forbidden | INTEGER | DEFAULT 0 | てんさい・馬鈴薯作付禁止フラグ（土壌条件等で栽培不可のほ場） |
| coordinates_json | TEXT | - | 座標データ（GeoJSON） |
| notes | TEXT | - | 備考 |
| created_at | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | 作成日時 |
| updated_at | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | 更新日時 |

**制約**:
- `UNIQUE(user_id, field_code)` - 同一ユーザー内でほ場コードは一意
- `ON DELETE CASCADE` - ユーザー削除時にほ場も削除

**インデックス**:
- `idx_fields_user` ON fields(user_id)
- `idx_fields_district` ON fields(district)

---

### 3.4 crop_history（作付履歴）

各ほ場の年度ごとの作付実績。

| カラム名 | 型 | 制約 | 説明 |
|---------|-----|------|------|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT | 履歴ID |
| field_id | INTEGER | NOT NULL, FK | ほ場ID |
| year | TEXT | NOT NULL | 年度（例: 'R5', 'R6'） |
| crop | TEXT | NOT NULL | 作物名 |
| is_inferred | INTEGER | DEFAULT 0 | 推論フラグ（1:推論データ） |
| created_at | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | 作成日時 |

**制約**:
- `UNIQUE(field_id, year)` - 同一ほ場・年度に複数の履歴は不可
- `ON DELETE CASCADE` - ほ場削除時に履歴も削除

**インデックス**:
- `idx_crop_history_field` ON crop_history(field_id)
- `idx_crop_history_year` ON crop_history(year)

---

### 3.5 rotation_plans（輪作計画）

ユーザーが作成した輪作計画のメタデータ。

| カラム名 | 型 | 制約 | 説明 |
|---------|-----|------|------|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT | 計画ID |
| user_id | INTEGER | NOT NULL, FK | 所有者ユーザーID |
| name | TEXT | NOT NULL | 計画名 |
| start_year | TEXT | NOT NULL | 開始年度 |
| end_year | TEXT | NOT NULL | 終了年度 |
| constraints_json | TEXT | - | 制約設定（JSON） |
| metadata_json | TEXT | - | メタデータ（JSON） |
| created_at | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | 作成日時 |
| updated_at | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | 更新日時 |

**制約**:
- `ON DELETE CASCADE` - ユーザー削除時に計画も削除

**インデックス**:
- `idx_rotation_plans_user` ON rotation_plans(user_id)

---

### 3.6 plan_details（輪作計画詳細）

輪作計画の各ほ場・年度ごとの作付内容。

| カラム名 | 型 | 制約 | 説明 |
|---------|-----|------|------|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT | 詳細ID |
| plan_id | INTEGER | NOT NULL, FK | 輪作計画ID |
| field_id | INTEGER | NOT NULL, FK | ほ場ID |
| year | TEXT | NOT NULL | 年度 |
| crop | TEXT | NOT NULL | 作物名 |
| created_at | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | 作成日時 |

**制約**:
- `UNIQUE(plan_id, field_id, year)` - 同一計画・ほ場・年度の重複不可
- `ON DELETE CASCADE` - 計画削除時に詳細も削除

**インデックス**:
- `idx_plan_details_plan` ON plan_details(plan_id)
- `idx_plan_details_field` ON plan_details(field_id)

---

### 3.7 crop_constraints（作物制約）

ユーザーごとの作物に対する制約条件。

| カラム名 | 型 | 制約 | 説明 |
|---------|-----|------|------|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT | 制約ID |
| user_id | INTEGER | NOT NULL, FK | ユーザーID |
| crop | TEXT | NOT NULL | 作物名 |
| cap_ha | REAL | - | 面積上限（ha） |
| min_ha | REAL | - | 面積下限（ha） |
| min_gap_years | INTEGER | - | 最小間隔年数 |
| min_fields | INTEGER | - | 最小ほ場数 |
| max_fields | INTEGER | - | 最大ほ場数 |
| created_at | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | 作成日時 |

**制約**:
- `UNIQUE(user_id, crop)` - 同一ユーザー・作物の重複不可
- `ON DELETE CASCADE` - ユーザー削除時に制約も削除

**インデックス**:
- `idx_crop_constraints_user` ON crop_constraints(user_id)

> **注意**: 現在このテーブルはスキーマのみ存在し、Repository/UIは未実装。
> 輪作計画の制約は `rotation_plans.constraints_json` に保存されている。
> 将来的にはこのテーブルを活用し、ユーザーごとのデフォルト制約を管理予定。

---

### 3.8 pesticide_masters（防除マスタ）

組織単位で共有される防除情報（農薬・防除スケジュール）。

| カラム名 | 型 | 制約 | 説明 |
|---------|-----|------|------|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT | マスタID |
| org_id | INTEGER | REFERENCES organizations(id) | 組織ID（NULLは共通） |
| crop | TEXT | NOT NULL | 対象作物 |
| month | INTEGER | - | 防除月 |
| period | TEXT | - | 時期（例: '上旬', '中旬'） |
| target | TEXT | - | 防除対象（病害虫名） |
| pesticide_name | TEXT | NOT NULL | 農薬名 |
| dilution_rate | TEXT | - | 希釈倍率 |
| amount_per_10a | REAL | - | 10aあたり使用量 |
| unit | TEXT | - | 単位（L, kg等） |
| days_before_harvest | TEXT | - | 収穫前日数 |
| notes | TEXT | - | 備考 |
| created_at | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | 作成日時 |

**インデックス**:
- `idx_pesticide_masters_org` ON pesticide_masters(org_id)
- `idx_pesticide_masters_crop` ON pesticide_masters(crop)

---

### 3.9 inventory（在庫）

ユーザーの農薬在庫情報。

| カラム名 | 型 | 制約 | 説明 |
|---------|-----|------|------|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT | 在庫ID |
| user_id | INTEGER | NOT NULL, FK | ユーザーID |
| pesticide_name | TEXT | NOT NULL | 農薬名 |
| amount | REAL | NOT NULL | 在庫量 |
| unit | TEXT | NOT NULL | 単位 |
| updated_at | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | 更新日時 |

**制約**:
- `UNIQUE(user_id, pesticide_name)` - 同一ユーザー・農薬の重複不可
- `ON DELETE CASCADE` - ユーザー削除時に在庫も削除

**インデックス**:
- `idx_inventory_user` ON inventory(user_id)

---

### 3.10 crop_master（作物マスタ）

JA管理の作物マスタ。全ユーザー共通で参照。

| カラム名 | 型 | 制約 | 説明 |
|---------|-----|------|------|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT | 作物ID |
| name | TEXT | NOT NULL UNIQUE | 作物名 |
| display_order | INTEGER | DEFAULT 0 | 表示順 |
| is_active | INTEGER | DEFAULT 1 | 有効フラグ |
| created_at | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | 作成日時 |

**初期データ**:
- 春小麦（display_order=1）
- 秋小麦（display_order=2）
- 大豆（display_order=3）
- てんさい（display_order=4）
- 馬鈴薯（display_order=5）

---

### 3.11 user_crops（ユーザー作物選択）

ユーザーが選択した作物（カスタム名対応）。

| カラム名 | 型 | 制約 | 説明 |
|---------|-----|------|------|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT | ユーザー作物ID |
| user_id | INTEGER | NOT NULL, FK | ユーザーID |
| parent_crop_id | INTEGER | NOT NULL, FK | 親作物ID（crop_master参照） |
| custom_name | TEXT | - | カスタム名（NULLならマスタ名を使用） |
| created_at | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | 作成日時 |

**制約**:
- `UNIQUE(user_id, parent_crop_id, custom_name)` - 同一ユーザー・親作物・カスタム名の重複不可
- `FOREIGN KEY (user_id) REFERENCES users(id)`
- `FOREIGN KEY (parent_crop_id) REFERENCES crop_master(id)`

**用途**:
- ユーザーが使用する作物を選択
- カスタム名で同一作物の複数バリエーション（例: 「ブロッコリー（2作目）」）に対応
- 防除マスタとは `parent_crop_id` で連携

---

### 3.12 pesticide_orders（農薬発注）

農薬発注リストの保存。

| カラム名 | 型 | 制約 | 説明 |
|---------|-----|------|------|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT | 発注ID |
| user_id | INTEGER | NOT NULL, FK | ユーザーID |
| name | TEXT | NOT NULL | 発注リスト名 |
| rotation_plan_id | INTEGER | FK | 関連する輪作計画ID |
| target_year | TEXT | NOT NULL | 対象年度 |
| area_unit | TEXT | NOT NULL DEFAULT 'ha' | 面積単位 |
| order_data_json | TEXT | - | 発注内容（JSON） |
| status | TEXT | DEFAULT 'draft' | ステータス |
| created_at | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | 作成日時 |
| updated_at | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | 更新日時 |

**制約**:
- `FOREIGN KEY (user_id) REFERENCES users(id)`
- `FOREIGN KEY (rotation_plan_id) REFERENCES rotation_plans(id)`

**インデックス**:
- `idx_pesticide_orders_user_id` ON pesticide_orders(user_id)
- `idx_pesticide_orders_target_year` ON pesticide_orders(target_year)

**ステータス値**:
- `draft`: 下書き
- `confirmed`: 確定
- `ordered`: 発注済み

**order_data_json の構造**:
```json
{
    "summary": [
        {
            "pesticide_name": "農薬A",
            "amount": 10.0,
            "unit": "L",
            "crops": "てんさい、大豆",
            "targets": "ヨトウムシ"
        }
    ],
    "details": [
        {
            "month": "5月",
            "crop": "てんさい",
            "target": "ヨトウムシ",
            "pesticide_name": "農薬A",
            "amount": 2.5,
            "area_ha": 5.0
        }
    ]
}
```

---

## 4. ER図

```
                                    ┌─────────────────┐
                                    │  organizations  │
                                    ├─────────────────┤
                                    │ id (PK)         │
                                    │ name            │
                                    │ type            │
                                    │ settings_json   │
                                    └────────┬────────┘
                                             │
                     ┌───────────────────────┼───────────────────────┐
                     │                       │                       │
                     │ 1                     │ 1                     │ 1
                     ▼                       ▼                       ▼
              ┌──────┴──────┐         ┌──────┴──────┐         ┌──────┴──────┐
              │    users    │         │ pesticide_  │         │             │
              ├─────────────┤         │   masters   │         │             │
              │ id (PK)     │◀───┐    ├─────────────┤         │             │
              │ username    │    │    │ id (PK)     │         │             │
              │ display_name│    │    │ org_id (FK) │         │             │
              │ role        │    │    │ crop        │         │             │
              │ org_id (FK) │    │    │ pesticide_  │         │             │
              └──────┬──────┘    │    │   name      │         │             │
                     │           │    └─────────────┘         │             │
   ┌─────────────────┼───────────┼───────────────────────────┼─────────────┘
   │                 │           │                           │
   │ 1               │ 1         │ 1                         │ 1
   ▼                 ▼           ▼                           ▼
┌──┴──────────┐ ┌────┴─────┐ ┌──┴──────────┐          ┌──────┴──────┐
│   fields    │ │ rotation │ │  inventory  │          │ pesticide_  │
├─────────────┤ │  _plans  │ ├─────────────┤          │   orders    │
│ id (PK)     │ ├──────────┤ │ id (PK)     │          ├─────────────┤
│ user_id(FK) │ │ id (PK)  │ │ user_id(FK) │          │ id (PK)     │
│ field_code  │ │ user_id  │ │ pesticide_  │          │ user_id(FK) │
│ area_ha     │ │   (FK)   │ │   name      │          │ rotation_   │
│ beet_       │ │ name     │ │ amount      │          │  plan_id(FK)│
│  forbidden  │ │ start_   │ └─────────────┘          │ target_year │
└──────┬──────┘ │   year   │                          │ order_data_ │
       │        │ end_year │                          │   json      │
       │ 1      └────┬─────┘                          └─────────────┘
       ▼             │ 1
┌──────┴──────┐      ▼
│crop_history │ ┌────┴─────┐
├─────────────┤ │  plan_   │
│ id (PK)     │ │ details  │
│ field_id    │ ├──────────┤
│   (FK)      │ │ id (PK)  │
│ year        │ │ plan_id  │
│ crop        │ │   (FK)   │◀───────────────────┐
│ is_inferred │ │ field_id │                    │
└─────────────┘ │   (FK)   │                    │
                │ year     │                    │
                │ crop     │                    │
                └──────────┘                    │
                                                │
                                                │
┌─────────────────┐      ┌─────────────────┐    │
│   crop_master   │      │   user_crops    │    │
├─────────────────┤      ├─────────────────┤    │
│ id (PK)         │◀─────│ parent_crop_id  │    │
│ name            │      │   (FK)          │    │
│ display_order   │      │ id (PK)         │    │
│ is_active       │      │ user_id (FK)    │────┘
└─────────────────┘      │ custom_name     │
                         └─────────────────┘


┌─────────────────┐
│crop_constraints │
├─────────────────┤
│ id (PK)         │
│ user_id (FK)    │────────▶ users
│ crop            │
│ cap_ha          │
│ min_gap_years   │
└─────────────────┘
```

### 4.1 リレーション一覧

| 親テーブル | 子テーブル | カーディナリティ | ON DELETE |
|-----------|-----------|-----------------|-----------|
| organizations | users | 1:N | - |
| organizations | pesticide_masters | 1:N | - |
| users | fields | 1:N | CASCADE |
| users | rotation_plans | 1:N | CASCADE |
| users | inventory | 1:N | CASCADE |
| users | crop_constraints | 1:N | CASCADE |
| users | user_crops | 1:N | - |
| users | pesticide_orders | 1:N | - |
| fields | crop_history | 1:N | CASCADE |
| fields | plan_details | 1:N | CASCADE |
| rotation_plans | plan_details | 1:N | CASCADE |
| rotation_plans | pesticide_orders | 1:N | - |
| crop_master | user_crops | 1:N | - |

---

## 5. Repository層

### 5.1 概要

Repository層は `/rotation_planner/common/db_access.py` に実装されている。
各Repositoryクラスはスタティックメソッドで構成され、SQLiteデータベースへのCRUD操作を提供する。

### 5.2 接続管理

```python
# 接続取得
conn = get_connection()

# コンテキストマネージャ（推奨）
with get_db() as conn:
    cursor = conn.execute(...)
```

### 5.3 Repositoryクラス一覧

#### 5.3.1 FieldRepository（ほ場）

| メソッド | 引数 | 戻り値 | 説明 |
|---------|------|--------|------|
| get_fields | user_id: int | List[Dict] | ユーザーのほ場一覧を取得 |
| get_field | field_id: int | Optional[Dict] | ほ場詳細を取得 |
| get_field_by_code | user_id: int, field_code: str | Optional[Dict] | ほ場コードで取得 |
| create_field | user_id: int, data: Dict | int | ほ場を作成、IDを返す |
| update_field | field_id: int, data: Dict | bool | ほ場を更新 |
| delete_field | field_id: int | bool | ほ場を削除 |
| get_field_with_history | field_id: int | Optional[Dict] | ほ場と作付履歴を取得 |

#### 5.3.2 CropHistoryRepository（作付履歴）

| メソッド | 引数 | 戻り値 | 説明 |
|---------|------|--------|------|
| get_history | field_id: int | List[Dict] | ほ場の作付履歴を取得 |
| get_all_history_for_user | user_id: int | List[Dict] | ユーザーの全ほ場履歴を取得 |
| delete_history | field_id: int, year: str | bool | 特定の履歴を削除 |
| bulk_update_history | updates: List[Dict] | int | 複数レコード一括更新 |
| add_history | field_id: int, year: str, crop: str, is_inferred: bool | int | 履歴を追加 |
| bulk_add_history | field_id: int, history: Dict[str, str] | int | 履歴を一括追加 |

#### 5.3.3 PlanRepository（輪作計画）

| メソッド | 引数 | 戻り値 | 説明 |
|---------|------|--------|------|
| get_plans | user_id: int | List[Dict] | 計画一覧を取得 |
| get_plan | plan_id: int | Optional[Dict] | 計画詳細を取得（details含む） |
| create_plan | user_id: int, data: Dict | int | 計画を作成、IDを返す |
| update_plan | plan_id: int, data: Dict | bool | 計画を更新 |
| delete_plan | plan_id: int | bool | 計画を削除 |

#### 5.3.4 JAStaffRepository（JA職員用）

| メソッド | 引数 | 戻り値 | 説明 |
|---------|------|--------|------|
| get_all_fields | org_id: int | List[Dict] | 組織内の全ほ場を取得 |
| get_all_farmers | org_id: int | List[Dict] | 組織内の農家一覧を取得 |
| get_aggregate_stats | org_id: int | Dict | 組織の集計データを取得 |

#### 5.3.5 UserRepository（ユーザー）

| メソッド | 引数 | 戻り値 | 説明 |
|---------|------|--------|------|
| get_user | user_id: int | Optional[Dict] | ユーザー情報を取得 |
| get_user_by_username | username: str | Optional[Dict] | ユーザー名で取得 |
| create_user | data: Dict | int | ユーザーを作成 |
| authenticate | username: str, password_hash: str | Optional[Dict] | 認証 |

#### 5.3.6 PesticideMasterRepository（防除マスタ）

| メソッド | 引数 | 戻り値 | 説明 |
|---------|------|--------|------|
| get_by_crop | crop: str, org_id: int | List[Dict] | 作物の防除データを取得 |
| get_all | org_id: int | List[Dict] | 全防除マスタを取得 |

#### 5.3.7 CropMasterRepository（作物マスタ）

| メソッド | 引数 | 戻り値 | 説明 |
|---------|------|--------|------|
| get_all | active_only: bool | List[Dict] | 全作物を取得 |
| get_by_id | crop_id: int | Optional[Dict] | IDで取得 |
| get_by_name | name: str | Optional[Dict] | 名前で取得 |
| create | name: str, display_order: int | int | 作物を追加 |
| update | crop_id: int, data: Dict | bool | 作物を更新 |
| delete | crop_id: int | bool | 作物を非アクティブ化 |

#### 5.3.8 UserCropRepository（ユーザー作物）

| メソッド | 引数 | 戻り値 | 説明 |
|---------|------|--------|------|
| get_user_crops | user_id: int | List[Dict] | ユーザーの選択した作物を取得 |
| get_user_crop_ids | user_id: int | List[int] | 親作物IDリストを取得 |
| set_user_crops | user_id: int, crop_ids: List[int] | bool | 作物選択を設定 |
| add_user_crop | user_id: int, parent_crop_id: int, custom_name: str | int | 作物を追加 |
| remove_user_crop | user_id: int, user_crop_id: int | bool | 作物を削除 |
| remove_user_crop_by_parent | user_id: int, parent_crop_id: int, custom_name: str | bool | 親ID+カスタム名で削除 |
| get_parent_crop_id_by_name | user_id: int, crop_name: str | Optional[int] | 作物名から親IDを取得 |

#### 5.3.9 PesticideOrderRepository（農薬発注）

| メソッド | 引数 | 戻り値 | 説明 |
|---------|------|--------|------|
| get_orders | user_id: int | List[Dict] | 発注リスト一覧を取得 |
| get_order | order_id: int | Optional[Dict] | 発注リスト詳細を取得 |
| create_order | user_id: int, data: Dict | int | 発注リストを作成 |
| update_order | order_id: int, data: Dict | bool | 発注リストを更新 |
| delete_order | order_id: int | bool | 発注リストを削除 |

### 5.4 その他のRepository

#### 5.4.1 RotationPlanRepository（農薬発注UI用）

`/rotation_planner/pesticide/rotation.py` に実装。PlanRepositoryをラップし、農薬計算に必要な形式でデータを提供。

| メソッド | 引数 | 戻り値 | 説明 |
|---------|------|--------|------|
| get_plans | user_id: int | List[Dict] | 計画一覧を取得 |
| get_plan | plan_id: int | Optional[Dict] | 計画詳細を取得 |
| get_plan_as_dataframe | plan_id: int | Tuple[DataFrame, List[str], str] | DataFrame形式で取得 |
| save_plan | user_id: int, plan_data: Dict | int | 計画を保存 |

---

## 6. マイグレーション

### 6.1 初期スキーマの適用

```bash
sqlite3 data/rotation_planner.db < db_schema.sql
```

### 6.2 作物スキーマ マイグレーション

```bash
sqlite3 data/rotation_planner.db < scripts/migrate_crop_schema.sql
```

### 6.3 農薬発注 マイグレーション

```bash
sqlite3 data/rotation_planner.db < scripts/migrate_pesticide_orders.sql
```

### 6.4 MigrationUtilsクラス

既存JSONデータからの移行ユーティリティが `db_access.py` に実装されている。

| メソッド | 説明 |
|---------|------|
| migrate_json_fields | fields.jsonからほ場データを移行 |
| migrate_json_plans | rotation_plans/から輪作計画を移行 |
| migrate_pesticide_master | pesticide_master.csvから防除マスタを移行 |

---

## 7. 備考

### 7.1 年度表記

年度は和暦（'R5', 'R6', ...）で保存される。

### 7.2 JSON列の用途

| テーブル | 列 | 用途 |
|---------|-----|------|
| organizations | settings_json | 地域設定、デフォルト作物リスト |
| fields | coordinates_json | GeoJSON形式の座標データ |
| rotation_plans | constraints_json | 輪作制約設定 |
| rotation_plans | metadata_json | メタデータ |
| pesticide_orders | order_data_json | 発注詳細（summary, details） |

### 7.3 計算列

`fields.area_a` は `area_ha * 100` の計算列（STORED）。

### 7.4 ソフトデリート

- `crop_master.is_active` - 作物マスタの論理削除
- `users.is_active` - ユーザーの論理削除
