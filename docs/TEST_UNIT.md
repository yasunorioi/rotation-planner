# rotation-planner 単体テスト設計書

**プロジェクト**: rotation-planner
**技術スタック**: Python + Gradio 4.x + SQLite + pytest
**作成日**: 2026-02-06
**作成者**: 足軽5号（QAエンジニアペルソナ）
**Version**: 2.0

---

## 1. 既存テスト分析

### 1.1 テストファイル一覧

| # | ファイル | テストクラス数 | テストメソッド数 | 主な対象 |
|---|---------|-------------|---------------|---------|
| 1 | `test_db_access.py` | 6 | 12 | DB接続、リポジトリ基本操作、ヘルパー関数 |
| 2 | `test_auth.py` | 6 | 14 | パスワードハッシュ、認証、アクセス制御、ロール |
| 3 | `test_csv_validation.py` | 5 | 13 | CSVインポートバリデーション（ほ場・輪作計画） |
| 4 | `test_security.py` | 5 | 8 | データ分離、SQLインジェクション対策、JA職員アクセス |
| 5 | `test_pesticide_record.py` | 6 | 20 | 防除記録CRUD、FAMIC、画像解析、エクスポート |
| 6 | `test_ja_staff.py` | 4 | 17 | JA職員UI、リポジトリ、年度ユーティリティ |
| 7 | `test_pesticide_order.py` | 5 | 12 | 農薬発注DB保存、PDF出力、発注一覧、計算 |
| | **合計** | **37** | **96** | |

### 1.2 テストフレームワーク・ツール

| 項目 | 現状 |
|------|------|
| フレームワーク | pytest |
| フィクスチャ | `@pytest.fixture`（一部使用） |
| モック | `unittest.mock`（patch, MagicMock） |
| パラメタライズ | 未使用 |
| カバレッジ計測 | 未導入（`pytest-cov` 推奨） |
| CI連携 | 未導入 |

### 1.3 テストパターン分析

**良い点**:
- セキュリティテストが充実（データ分離、SQLインジェクション対策）
- CRUDライフサイクルテスト（create→read→update→delete）パターンあり
- モック活用（Anthropic API、画像解析）
- 一時ファイル・ディレクトリの適切なクリーンアップ
- `pytest.mark.skipif` によるCI/依存環境の切り分け

**改善点**:
- テストが実DB依存（テスト用DBのセットアップなし）
- テストデータがハードコード（fixtureに集約すべき）
- パラメタライズ未使用（同パターンの繰り返しが多い）
- `sys.path.insert` によるパス設定（`conftest.py` で一元化すべき）
- 一部テストが条件付き（`if fields:` でスキップ、assertionなし）

### 1.4 カバレッジ推定

| モジュール | 推定カバレッジ | 備考 |
|-----------|-------------|------|
| `common/db.py` | ~20% | 接続テストのみ |
| `common/db_access.py` | ~10% | 基本取得のみ、CRUD未テスト多数 |
| `common/auth.py` | ~60% | ハッシュ・認証・アクセス制御はカバー |
| `common/year_utils.py` | ~80% | 変換・年度関数カバー済み |
| `common/export.py` | ~0% | 未テスト |
| `common/ui_utils.py` | ~0% | 未テスト |
| `app/optimizer.py` | ~0% | 未テスト（最重要ロジック） |
| `app/constraints.py` | ~0% | 未テスト（最重要ロジック） |
| `field/crud.py` | ~0% | 未テスト |
| `field/kml_parser.py` | ~0% | 未テスト |
| `field/map.py` | ~0% | 未テスト |
| `pesticide/calculator.py` | ~5% | 基本計算のみ |
| `pesticide/csv_io.py` | ~0% | 未テスト |
| `data_management/ui.py` | ~30% | CSVインポートはカバー |
| **全体推定** | **~8%** | |

---

## 2. テスト対象の優先順位

### 優先度定義

| 優先度 | 定義 | 基準 |
|--------|------|------|
| **P0** | 最優先 | データ破損・セキュリティリスク・コアロジック |
| **P1** | 高 | 主要機能・ユーザー影響大 |
| **P2** | 中 | 補助機能・エッジケース |
| **P3** | 低 | UI関連・低リスク |

### 優先順位マトリックス

| 優先度 | モジュール | 理由 |
|--------|-----------|------|
| **P0** | `common/db_access.py`（CRUD全般） | データ整合性の根幹 |
| **P0** | `common/auth.py`（未テスト関数） | セキュリティ |
| **P0** | `app/constraints.py` | 輪作計画の制約ロジック |
| **P1** | `app/optimizer.py` | コアビジネスロジック |
| **P1** | `pesticide/calculator.py` | 農薬計算の正確性 |
| **P1** | `field/kml_parser.py` | ファイル入出力の信頼性 |
| **P1** | `common/export.py` | データエクスポートの正確性 |
| **P2** | `field/crud.py` | ほ場管理ワークフロー |
| **P2** | `field/map.py` | 面積計算の正確性 |
| **P2** | `pesticide/csv_io.py` | CSV入出力 |
| **P2** | `common/ui_utils.py` | HTML生成の正確性 |
| **P3** | `field/fude_polygon.py` | 外部API依存 |
| **P3** | `pesticide/rotation.py` | DB薄ラッパー |

---

## 3. 単体テストケース一覧

### 3.1 P0: DB操作（CRUD）テスト

#### 3.1.1 FieldRepository

| # | テストケース | 種別 | 入力 | 期待結果 |
|---|------------|------|------|---------|
| F-01 | create_field: 正常な圃場登録 | 正常系 | 有効なuser_id, data | lastrowidが返る |
| F-02 | create_field: field_code重複 | 異常系 | 既存のfield_code | IntegrityError |
| F-03 | create_field: 必須項目欠落 | 異常系 | field_code=None | NotNullエラー |
| F-04 | update_field: 正常な更新 | 正常系 | 既存field_id, 新data | True |
| F-05 | update_field: 存在しないID | 異常系 | 999999 | False |
| F-06 | delete_field: 正常な削除 | 正常系 | 既存field_id | True |
| F-07 | delete_field: 存在しないID | 異常系 | 999999 | False |
| F-08 | get_field: 存在するID | 正常系 | 既存field_id | Dictが返る |
| F-09 | get_field: 存在しないID | 異常系 | 999999 | None |
| F-10 | get_field_with_history: 履歴付き取得 | 正常系 | 既存field_id | Dict + crop_history |
| F-11 | get_fields: user_id=0の場合 | 境界値 | 0 | 空リスト |

#### 3.1.2 CropHistoryRepository

| # | テストケース | 種別 | 入力 | 期待結果 |
|---|------------|------|------|---------|
| CH-01 | add_history: 正常登録 | 正常系 | field_id, year, crop | lastrowid |
| CH-02 | add_history: 同一field_id+year上書き | 正常系 | 既存のfield_id+year | REPLACE実行 |
| CH-03 | get_history: 年度順ソート | 正常系 | 複数年データ | year昇順 |
| CH-04 | delete_history: 特定年度削除 | 正常系 | field_id, year | True |
| CH-05 | bulk_update_history: 複数レコード更新 | 正常系 | updates list | 更新件数 |
| CH-06 | bulk_update_history: 空リスト | 境界値 | [] | 0 |
| CH-07 | get_all_history_for_user: ユーザー分離 | 正常系 | user_id | 当該ユーザーのみ |

#### 3.1.3 PlanRepository

| # | テストケース | 種別 | 入力 | 期待結果 |
|---|------------|------|------|---------|
| PL-01 | create_plan: 正常な計画作成 | 正常系 | user_id, data | lastrowid |
| PL-02 | create_plan: name空文字 | 異常系 | name="" | エラーまたは空名保存 |
| PL-03 | get_plan: constraints JSONパース | 正常系 | JSONあり | dictにパース済み |
| PL-04 | get_plan: constraints JSON不正 | 異常系 | 不正JSON | エラーハンドリング確認 |
| PL-05 | update_plan: details再作成 | 正常系 | 新details | 旧details削除+新規追加 |
| PL-06 | delete_plan: 関連data含め削除 | 正常系 | plan_id | True + details削除 |

#### 3.1.4 UserRepository

| # | テストケース | 種別 | 入力 | 期待結果 |
|---|------------|------|------|---------|
| UR-01 | create_user: 正常登録 | 正常系 | 有効data | lastrowid |
| UR-02 | create_user: username重複 | 異常系 | 既存username | IntegrityError |
| UR-03 | get_user: org_name JOIN確認 | 正常系 | 既存user_id | org_nameフィールドあり |
| UR-04 | authenticate: 正しいハッシュ | 正常系 | 正しいhash | userデータ返却 |
| UR-05 | authenticate: 誤ったハッシュ | 異常系 | 誤ったhash | None |

#### 3.1.5 PesticideMasterRepository

| # | テストケース | 種別 | 入力 | 期待結果 |
|---|------------|------|------|---------|
| PM-01 | bulk_import: 正常インポート | 正常系 | records, org_id | 件数 |
| PM-02 | bulk_import: 空リスト | 境界値 | [] | 0 |
| PM-03 | get_by_crop: 作物名指定 | 正常系 | "大豆" | List[Dict] |
| PM-04 | delete_all: 組織内全削除 | 正常系 | org_id | 件数 |

#### 3.1.6 UserCropRepository

| # | テストケース | 種別 | 入力 | 期待結果 |
|---|------------|------|------|---------|
| UC-01 | set_user_crops: 作物選択設定 | 正常系 | user_id, crop_ids | True |
| UC-02 | set_user_crops: 空リスト | 境界値 | [] | True (全解除) |
| UC-03 | add_user_crop: カスタム作物追加 | 正常系 | parent_crop_id, custom_name | lastrowid |
| UC-04 | remove_user_crop: 削除 | 正常系 | user_crop_id | True |
| UC-05 | get_parent_crop_id_by_name: 存在しない名前 | 異常系 | "unknown" | None |

#### 3.1.7 UserConstraintsRepository

| # | テストケース | 種別 | 入力 | 期待結果 |
|---|------------|------|------|---------|
| CO-01 | save_constraints: 正常保存 | 正常系 | constraints dict | True |
| CO-02 | get_constraints: 保存済み取得 | 正常系 | user_id | Dict |
| CO-03 | get_constraints: 未設定ユーザー | 正常系 | 未設定user_id | None |
| CO-04 | delete_constraints: 正常削除 | 正常系 | user_id | True |

### 3.2 P0: 認証・セキュリティテスト（未テスト関数）

#### 3.2.1 auth.py 追加テスト

| # | テストケース | 種別 | 入力 | 期待結果 |
|---|------------|------|------|---------|
| AU-01 | add_user: 正常なユーザー追加 | 正常系 | 有効なデータ | True |
| AU-02 | add_user: 既存ユーザー名 | 異常系 | 既存username | False |
| AU-03 | update_password: パスワード変更 | 正常系 | 有効なusername, new_password | True |
| AU-04 | update_password: 存在しないユーザー | 異常系 | 無効username | False |
| AU-05 | delete_user: 論理削除 | 正常系 | 有効username | True + is_active=0 |
| AU-06 | delete_user: 削除後にログイン不可 | 正常系 | 削除済みユーザー | authenticate=False |
| AU-07 | get_admin_count: 管理者数取得 | 正常系 | - | int >= 1 |
| AU-08 | get_user_role: ロール取得 | 正常系 | 有効username | "admin"/"farmer"等 |
| AU-09 | get_user_role: 存在しないユーザー | 異常系 | 無効username | None |
| AU-10 | get_accessible_user_ids: admin | 正常系 | admin username | 空リスト(=全アクセス) |
| AU-11 | get_accessible_user_ids: farmer | 正常系 | farmer username | [自分のID] |
| AU-12 | load_users: 全ユーザー取得 | 正常系 | - | List[Dict] |
| AU-13 | can_access_farmer: 後方互換確認 | 正常系 | - | can_access_user_dataと同等 |

### 3.3 P0: 制約処理テスト

#### 3.3.1 constraints.py

| # | テストケース | 種別 | 入力 | 期待結果 |
|---|------------|------|------|---------|
| CN-01 | get_default_crops: ユーザー設定あり | 正常系 | 設定済みuser_id | ユーザーの作物リスト |
| CN-02 | get_default_crops: ユーザー設定なし | 正常系 | 未設定user_id | マスタの作物リスト |
| CN-03 | get_default_crops: user_id=None | 境界値 | None | フォールバック作物リスト |
| CN-04 | build_constraints_table: 正常構築 | 正常系 | ["大豆", "てんさい"] | DataFrame |
| CN-05 | build_constraints_table: 空リスト | 境界値 | [] | 空DataFrame |
| CN-06 | build_constraints_table: 1作物 | 境界値 | ["大豆"] | 1行DataFrame |
| CN-07 | parse_constraints_table: 正常パース | 正常系 | 有効DataFrame | 5つのdict |
| CN-08 | parse_constraints_table: 空テーブル | 境界値 | 空DataFrame | 空dict群 |
| CN-09 | parse_forbidden_transitions: 正常パース | 正常系 | "大豆->てんさい" | {("大豆","てんさい")} |
| CN-10 | parse_forbidden_transitions: 複数 | 正常系 | "A->B, C->D" | 2要素Set |
| CN-11 | parse_forbidden_transitions: 空文字 | 境界値 | "" | 空Set |
| CN-12 | parse_forbidden_transitions: 不正形式 | 異常系 | "A-B" (矢印なし) | 空Set or エラー |
| CN-13 | parse_preferred_transitions: 正常パース | 正常系 | "大豆->てんさい:0.8" | Dict |
| CN-14 | parse_preferred_transitions: weight省略 | 境界値 | "A->B" (重みなし) | デフォルト重み |
| CN-15 | update_constraints_table: 作物追加 | 正常系 | 新作物テキスト | 行追加されたDF |
| CN-16 | update_constraints_table: 作物削除 | 正常系 | 作物減 | 行削除されたDF |
| CN-17 | load_constraints_csv: 正常CSV | 正常系 | 有効CSVファイル | DataFrame |
| CN-18 | load_constraints_csv: 不正CSV | 異常系 | 壊れたCSV | エラーハンドリング |

### 3.4 P1: 輪作最適化テスト

#### 3.4.1 optimizer.py - RotationPlannerHeuristic

| # | テストケース | 種別 | 入力 | 期待結果 |
|---|------------|------|------|---------|
| OH-01 | 初期化: 最小構成 | 正常系 | fields=1, crops=2, years=1 | インスタンス生成 |
| OH-02 | get_last_n_crops: 履歴取得 | 正常系 | 複数年の履歴 | 直近n件 |
| OH-03 | get_last_n_crops: 履歴不足 | 境界値 | 1年分のみ、n=3 | 不足分は空 |
| OH-04 | check_gap_constraint: 間隔OK | 正常系 | 十分な間隔 | True |
| OH-05 | check_gap_constraint: 間隔NG | 正常系 | 間隔不足 | False |
| OH-06 | check_transition_constraint: 許可遷移 | 正常系 | 許可された遷移 | True |
| OH-07 | check_transition_constraint: 禁止遷移 | 正常系 | 禁止された遷移 | False |
| OH-08 | get_valid_crops: フィルタリング | 正常系 | 制約付き | 有効作物のみ |
| OH-09 | check_cap_constraint: 上限内 | 正常系 | 面積 < 上限 | True |
| OH-10 | check_cap_constraint: 上限超過 | 正常系 | 面積 > 上限 | False |
| OH-11 | check_field_count_constraint: 範囲内 | 正常系 | min <= count <= max | (True, "") |
| OH-12 | check_field_count_constraint: 範囲外 | 正常系 | count > max | (False, msg) |
| OH-13 | solve: 最小問題 | 正常系 | 2圃場, 3作物, 2年 | 実行可能解 |
| OH-14 | solve: 解なし（過剰制約） | 異常系 | 矛盾する制約 | violations付き結果 |
| OH-15 | evaluate_solution: スコア計算 | 正常系 | 有効な計画 | (score, violations) |

#### 3.4.2 optimizer.py - RotationPlannerORTools

| # | テストケース | 種別 | 入力 | 期待結果 |
|---|------------|------|------|---------|
| OO-01 | solve: 最小問題 | 正常系 | 2圃場, 3作物, 2年 | 実行可能解 |
| OO-02 | solve: タイムアウト | 正常系 | timeout=1秒, 大問題 | 部分解 or 警告 |
| OO-03 | solve: high_precision | 正常系 | high_precision=True | より高品質な解 |

### 3.5 P1: 農薬計算テスト

#### 3.5.1 pesticide/calculator.py

| # | テストケース | 種別 | 入力 | 期待結果 |
|---|------------|------|------|---------|
| PC-01 | convert_to_base_unit: mL→mL | 正常系 | 100, "mL" | 100.0 |
| PC-02 | convert_to_base_unit: L→mL | 正常系 | 1, "L" | 1000.0 |
| PC-03 | convert_to_base_unit: kg→g | 正常系 | 1, "kg" | 1000.0 |
| PC-04 | convert_to_base_unit: 不明単位 | 異常系 | 1, "不明" | 1.0（そのまま） |
| PC-05 | convert_from_base_unit: mL→L | 正常系 | 1000, "L" | 1.0 |
| PC-06 | normalize_crop: てんさい | 正常系 | "テンサイ" | "てんさい" |
| PC-07 | normalize_crop: 馬鈴薯 | 正常系 | "ばれいしょ" | 正規化名 |
| PC-08 | normalize_crop: 未知の作物 | 正常系 | "未知作物" | そのまま |
| PC-09 | load_rotation_plan: 有効CSV | 正常系 | 有効CSVパス | (DataFrame, years, msg) |
| PC-10 | load_rotation_plan: 存在しないファイル | 異常系 | 無効パス | エラー |
| PC-11 | load_inventory_csv: 有効CSV | 正常系 | 在庫CSV | (Dict, msg) |
| PC-12 | calculate_requirements: 正常計算 | 正常系 | 有効な計画+マスタ | summary_df, detail_df |
| PC-13 | calculate_requirements: マスタなし | 境界値 | 空マスタ | 警告メッセージ |

### 3.6 P1: KML/KMZパーサーテスト

#### 3.6.1 field/kml_parser.py

| # | テストケース | 種別 | 入力 | 期待結果 |
|---|------------|------|------|---------|
| KM-01 | parse_coordinates_string: 正常座標 | 正常系 | "141.0,43.0,0" | [[43.0, 141.0]] |
| KM-02 | parse_coordinates_string: 複数座標 | 正常系 | 3点のポリゴン | 3要素リスト |
| KM-03 | parse_coordinates_string: 空文字 | 境界値 | "" | 空リスト |
| KM-04 | parse_kml_content: 有効KML | 正常系 | Placemarkを含むKML | List[Dict] |
| KM-05 | parse_kml_content: Placemark無しKML | 境界値 | 空のKML | 空リスト |
| KM-06 | parse_kml_content: 不正XML | 異常系 | 壊れたXML | エラーハンドリング |
| KM-07 | parse_kml_file: 存在しないファイル | 異常系 | 無効パス | FileNotFoundError |
| KM-08 | parse_kmz_file: 有効KMZ | 正常系 | 有効ZIPファイル | List[Dict] |
| KM-09 | parse_kmz_file: 不正ZIP | 異常系 | 壊れたZIP | エラーハンドリング |
| KM-10 | parse_kml_or_kmz: 自動判定 | 正常系 | .kml拡張子 | KMLとして処理 |
| KM-11 | generate_kml_content: 正常生成 | 正常系 | fields list | 有効なKML文字列 |
| KM-12 | export_fields_to_kml: ファイル出力 | 正常系 | fields, output_path | ファイル生成 |
| KM-13 | fields_to_dataframe_format: 変換 | 正常系 | パース結果 | DataFrame用Dict |

### 3.7 P1: エクスポートテスト

#### 3.7.1 common/export.py

| # | テストケース | 種別 | 入力 | 期待結果 |
|---|------------|------|------|---------|
| EX-01 | can_access_all_data: admin | 正常系 | admin state | True |
| EX-02 | can_access_all_data: farmer | 正常系 | farmer state | False |
| EX-03 | export_rotation_plan_csv: 正常 | 正常系 | 有効plan_id | (path, msg) |
| EX-04 | export_rotation_plan_csv: 権限なし | 異常系 | 他人のplan_id | エラー |
| EX-05 | export_fields_csv: 正常出力 | 正常系 | 有効user_state | (path, msg) |
| EX-06 | export_fields_csv: 未ログイン | 異常系 | 空state | (None, error) |

### 3.8 P2: ほ場管理テスト

#### 3.8.1 field/crud.py

| # | テストケース | 種別 | 入力 | 期待結果 |
|---|------------|------|------|---------|
| FC-01 | get_next_field_id: 初回 | 正常系 | ほ場なし | "F001" |
| FC-02 | get_next_field_id: 連番 | 正常系 | F001存在 | "F002" |
| FC-03 | get_user_id_from_state: 有効state | 正常系 | user_id入り | int |
| FC-04 | get_user_id_from_state: 空state | 異常系 | {} | None |
| FC-05 | fields_to_dataframe: 変換 | 正常系 | fields list | DataFrame |
| FC-06 | fields_to_dataframe: 空リスト | 境界値 | [] | 空DataFrame |
| FC-07 | register_field: 正常登録 | 正常系 | 有効データ | (df, msg, ...) |
| FC-08 | register_field: 未ログイン | 異常系 | 空state | エラーメッセージ |
| FC-09 | delete_field: 正常削除 | 正常系 | 有効field_code | (df, msg, ...) |

### 3.9 P2: 面積計算テスト

#### 3.9.1 field/map.py

| # | テストケース | 種別 | 入力 | 期待結果 |
|---|------------|------|------|---------|
| MA-01 | calculate_area_from_coords: 正方形 | 正常系 | 100m四方の座標 | ~10000 m2 |
| MA-02 | calculate_area_from_coords: 三角形 | 正常系 | 3点座標 | 正の面積 |
| MA-03 | calculate_area_from_coords: 2点以下 | 境界値 | 2点のみ | 0 or エラー |
| MA-04 | m2_to_ha: 変換 | 正常系 | 10000 | 1.0 |
| MA-05 | m2_to_a: 変換 | 正常系 | 100 | 1.0 |
| MA-06 | calculate_area: 負の面積にならない | 正常系 | 任意座標 | >= 0 |

### 3.10 P2: UIユーティリティテスト

#### 3.10.1 common/ui_utils.py

| # | テストケース | 種別 | 入力 | 期待結果 |
|---|------------|------|------|---------|
| UI-01 | format_alert: success | 正常系 | msg, "success" | 緑色HTML |
| UI-02 | format_alert: error | 正常系 | msg, "error" | 赤色HTML |
| UI-03 | format_error: ラッパー | 正常系 | msg | format_alert(msg, "error") |
| UI-04 | format_success: ラッパー | 正常系 | msg | format_alert(msg, "success") |
| UI-05 | format_alert: XSS防止 | セキュリティ | `<script>alert(1)</script>` | エスケープ済み |

### 3.11 P2: CSV入出力テスト

#### 3.11.1 pesticide/csv_io.py

| # | テストケース | 種別 | 入力 | 期待結果 |
|---|------------|------|------|---------|
| CI-01 | export_order_csv: 正常出力 | 正常系 | summary_data, year | (path, bytes) |
| CI-02 | export_order_csv: 空データ | 境界値 | [] | ヘッダーのみ |
| CI-03 | import_order_csv: 有効CSV | 正常系 | 有効CSVファイル | (items, warnings) |
| CI-04 | import_order_csv: 不正CSV | 異常系 | 壊れたCSV | エラー |
| CI-05 | merge_with_calculated: マージ | 正常系 | 2リスト | 統合リスト |

---

## 4. テストコード例（pytest形式）

### 4.1 テスト基盤: conftest.py

```python
# tests/conftest.py
"""
テスト共通フィクスチャ
"""
import pytest
import sqlite3
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch

# プロジェクトルートをパスに追加（conftest.pyで一元化）
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ============================================================
# DB フィクスチャ
# ============================================================

@pytest.fixture(scope="session")
def test_db_path():
    """テスト用DBパス（セッション共有）"""
    tmpdir = tempfile.mkdtemp(prefix="rp_test_")
    db_path = os.path.join(tmpdir, "test_rotation.db")
    yield db_path
    shutil.rmtree(tmpdir, ignore_errors=True)


@pytest.fixture(scope="function")
def isolated_db(test_db_path):
    """
    各テスト関数で独立したDBトランザクション。
    テスト後にロールバックするため、DBを汚染しない。
    """
    from rotation_planner.common import db
    original_path = db.DB_PATH

    # テスト用DBパスに差し替え
    db.DB_PATH = test_db_path

    # スキーマ初期化（初回のみ）
    if not Path(test_db_path).exists():
        db.init_db()

    conn = db.get_connection()
    conn.execute("BEGIN")

    yield conn

    conn.rollback()
    conn.close()
    db.DB_PATH = original_path


@pytest.fixture
def mock_db_connection(isolated_db):
    """get_connection()をモックして隔離DBを返す"""
    from rotation_planner.common import db
    with patch.object(db, 'get_connection', return_value=isolated_db):
        yield isolated_db


# ============================================================
# ユーザー状態フィクスチャ
# ============================================================

@pytest.fixture
def admin_state():
    """管理者ユーザー状態"""
    return {
        "user_id": 1,
        "username": "admin",
        "display_name": "管理者",
        "role": "admin",
        "org_id": 1,
    }


@pytest.fixture
def farmer_state():
    """農家ユーザー状態"""
    return {
        "user_id": 3,
        "username": "farmer_demo",
        "display_name": "デモ農家",
        "role": "farmer",
        "org_id": 1,
    }


@pytest.fixture
def ja_staff_state():
    """JA職員ユーザー状態"""
    return {
        "user_id": 2,
        "username": "ja_staff",
        "display_name": "JA職員",
        "role": "ja_staff",
        "org_id": 1,
    }


# ============================================================
# 一時ファイルフィクスチャ
# ============================================================

@pytest.fixture
def temp_dir():
    """一時ディレクトリ"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def temp_csv(temp_dir):
    """一時CSVファイルを作成するファクトリ"""
    def _create(content: str, filename: str = "test.csv") -> str:
        path = os.path.join(temp_dir, filename)
        with open(path, "w", encoding="utf-8-sig") as f:
            f.write(content)
        return path
    return _create


# ============================================================
# テストデータフィクスチャ
# ============================================================

@pytest.fixture
def sample_field_data():
    """サンプルほ場データ"""
    return {
        "field_code": "TEST001",
        "district": "テスト地区",
        "name": "テストほ場1号",
        "area_ha": 2.5,
        "beet_forbidden": False,
        "coordinates_json": None,
        "notes": "テスト用",
    }


@pytest.fixture
def sample_crop_history():
    """サンプル作付履歴"""
    return {
        "R5": "大豆",
        "R6": "てんさい",
        "R7": "春小麦",
    }


@pytest.fixture
def sample_constraints():
    """サンプル制約データ"""
    return {
        "crop_mins": {"てんさい": 0.2, "大豆": 0.1},
        "crop_caps": {"てんさい": 0.4, "大豆": 0.3},
        "min_gap_years": {"てんさい": 4, "大豆": 2},
        "forbidden_transitions": {("てんさい", "てんさい")},
        "preferred_transitions": {("大豆", "てんさい"): 0.8},
    }
```

### 4.2 制約処理テスト例

```python
# tests/test_constraints.py
"""
制約処理（constraints.py）の単体テスト
"""
import pytest
import pandas as pd

from rotation_planner.app.constraints import (
    build_constraints_table,
    parse_constraints_table,
    parse_forbidden_transitions,
    parse_preferred_transitions,
    update_constraints_table,
)


class TestBuildConstraintsTable:
    """build_constraints_table のテスト"""

    def test_normal_crops(self):
        """正常: 複数作物でテーブル生成"""
        crops = ["てんさい", "大豆", "春小麦"]
        df = build_constraints_table(crops)

        assert isinstance(df, pd.DataFrame)
        assert len(df) == 3
        # 作物名カラムが存在すること
        assert any("作物" in str(c) for c in df.columns)

    def test_single_crop(self):
        """境界値: 1作物"""
        df = build_constraints_table(["大豆"])
        assert len(df) == 1

    def test_empty_crops(self):
        """境界値: 空リスト"""
        df = build_constraints_table([])
        assert len(df) == 0


class TestParseForbiddenTransitions:
    """parse_forbidden_transitions のテスト"""

    def test_single_transition(self):
        """正常: 1つの禁止遷移"""
        result = parse_forbidden_transitions("大豆->てんさい")
        assert ("大豆", "てんさい") in result

    def test_multiple_transitions(self):
        """正常: 複数の禁止遷移"""
        result = parse_forbidden_transitions("大豆->てんさい, 春小麦->大豆")
        assert len(result) == 2
        assert ("大豆", "てんさい") in result
        assert ("春小麦", "大豆") in result

    def test_empty_string(self):
        """境界値: 空文字"""
        result = parse_forbidden_transitions("")
        assert len(result) == 0

    def test_whitespace_handling(self):
        """正常: 前後空白の処理"""
        result = parse_forbidden_transitions("  大豆 -> てんさい  ")
        assert ("大豆", "てんさい") in result


class TestParsePreferredTransitions:
    """parse_preferred_transitions のテスト"""

    def test_with_weight(self):
        """正常: 重み付き"""
        result = parse_preferred_transitions("大豆->てんさい:0.8")
        assert ("大豆", "てんさい") in result
        assert abs(result[("大豆", "てんさい")] - 0.8) < 0.01

    def test_multiple_with_weights(self):
        """正常: 複数の重み付き遷移"""
        result = parse_preferred_transitions("A->B:0.5, C->D:0.9")
        assert len(result) == 2


class TestParseConstraintsTable:
    """parse_constraints_table のテスト"""

    def test_round_trip(self):
        """正常: build -> parse のラウンドトリップ"""
        crops = ["てんさい", "大豆", "春小麦"]
        df = build_constraints_table(crops)
        result = parse_constraints_table(df)

        # 5つのdictが返ること
        assert len(result) == 5

    def test_empty_table(self):
        """境界値: 空テーブル"""
        df = pd.DataFrame()
        result = parse_constraints_table(df)
        # エラーにならないこと
        assert isinstance(result, tuple)
```

### 4.3 農薬計算テスト例

```python
# tests/test_calculator_unit.py
"""
農薬計算（calculator.py）の単体テスト
"""
import pytest

from rotation_planner.pesticide.calculator import (
    convert_to_base_unit,
    convert_from_base_unit,
    normalize_crop,
)


class TestConvertToBaseUnit:
    """convert_to_base_unit のテスト"""

    @pytest.mark.parametrize("amount, unit, expected", [
        (100, "mL", 100.0),
        (1, "L", 1000.0),
        (0.5, "L", 500.0),
        (100, "g", 100.0),
        (1, "kg", 1000.0),
        (0.5, "kg", 500.0),
    ])
    def test_known_conversions(self, amount, unit, expected):
        """既知の単位変換"""
        result = convert_to_base_unit(amount, unit)
        assert abs(result - expected) < 0.01

    def test_zero_amount(self):
        """境界値: 0"""
        result = convert_to_base_unit(0, "L")
        assert result == 0.0

    def test_unknown_unit(self):
        """異常系: 不明な単位"""
        result = convert_to_base_unit(1, "不明")
        # そのまま返るか、エラーを投げるか（実装依存）
        assert isinstance(result, (int, float))


class TestConvertFromBaseUnit:
    """convert_from_base_unit のテスト"""

    @pytest.mark.parametrize("amount_base, target, expected", [
        (1000.0, "L", 1.0),
        (500.0, "L", 0.5),
        (1000.0, "kg", 1.0),
    ])
    def test_known_conversions(self, amount_base, target, expected):
        """既知の逆変換"""
        result = convert_from_base_unit(amount_base, target)
        assert abs(result - expected) < 0.01

    def test_roundtrip(self):
        """ラウンドトリップ: to_base -> from_base"""
        original = 2.5
        base = convert_to_base_unit(original, "L")
        result = convert_from_base_unit(base, "L")
        assert abs(result - original) < 0.01


class TestNormalizeCrop:
    """normalize_crop のテスト"""

    @pytest.mark.parametrize("input_name, expected", [
        ("てんさい", "てんさい"),
        ("テンサイ", "てんさい"),
        ("大豆", "大豆"),
        ("ダイズ", "大豆"),
    ])
    def test_known_normalizations(self, input_name, expected):
        """既知の正規化パターン"""
        result = normalize_crop(input_name)
        assert result == expected

    def test_unknown_crop(self):
        """不明な作物はそのまま"""
        result = normalize_crop("未知の作物ABC")
        assert result == "未知の作物ABC"

    def test_empty_string(self):
        """境界値: 空文字"""
        result = normalize_crop("")
        assert isinstance(result, str)
```

### 4.4 KMLパーサーテスト例

```python
# tests/test_kml_parser_unit.py
"""
KML/KMZパーサー（kml_parser.py）の単体テスト
"""
import pytest
import os
import tempfile

from rotation_planner.field.kml_parser import (
    parse_coordinates_string,
    parse_kml_content,
    parse_kml_file,
    generate_kml_content,
    fields_to_dataframe_format,
)


# ============================================================
# テストデータ
# ============================================================

SAMPLE_KML = """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <Placemark>
      <name>テストほ場</name>
      <Polygon>
        <outerBoundaryIs>
          <LinearRing>
            <coordinates>
              141.0,43.0,0
              141.001,43.0,0
              141.001,43.001,0
              141.0,43.001,0
              141.0,43.0,0
            </coordinates>
          </LinearRing>
        </outerBoundaryIs>
      </Polygon>
    </Placemark>
  </Document>
</kml>"""

EMPTY_KML = """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
  </Document>
</kml>"""


class TestParseCoordinatesString:
    """parse_coordinates_string のテスト"""

    def test_single_coordinate(self):
        """正常: 1点座標"""
        result = parse_coordinates_string("141.0,43.0,0")
        assert len(result) == 1
        assert result[0] == [43.0, 141.0]  # [lat, lng]

    def test_multiple_coordinates(self):
        """正常: 複数座標"""
        coords = "141.0,43.0,0 141.001,43.001,0 141.002,43.002,0"
        result = parse_coordinates_string(coords)
        assert len(result) == 3

    def test_empty_string(self):
        """境界値: 空文字"""
        result = parse_coordinates_string("")
        assert result == []

    def test_with_newlines(self):
        """正常: 改行を含む座標"""
        coords = "141.0,43.0,0\n141.001,43.001,0"
        result = parse_coordinates_string(coords)
        assert len(result) >= 1


class TestParseKmlContent:
    """parse_kml_content のテスト"""

    def test_valid_kml(self):
        """正常: 有効なKML"""
        result = parse_kml_content(SAMPLE_KML)
        assert len(result) >= 1
        assert result[0].get("name") == "テストほ場"

    def test_empty_kml(self):
        """境界値: Placemarkなし"""
        result = parse_kml_content(EMPTY_KML)
        assert result == []

    def test_invalid_xml(self):
        """異常系: 不正なXML"""
        with pytest.raises(Exception):
            parse_kml_content("<invalid>xml</broken>")


class TestParseKmlFile:
    """parse_kml_file のテスト"""

    def test_valid_file(self, temp_dir):
        """正常: 有効なKMLファイル"""
        kml_path = os.path.join(temp_dir, "test.kml")
        with open(kml_path, "w", encoding="utf-8") as f:
            f.write(SAMPLE_KML)

        result = parse_kml_file(kml_path)
        assert len(result) >= 1

    def test_file_not_found(self):
        """異常系: 存在しないファイル"""
        with pytest.raises(FileNotFoundError):
            parse_kml_file("/nonexistent/path.kml")


class TestGenerateKmlContent:
    """generate_kml_content のテスト"""

    def test_generate_from_fields(self):
        """正常: fields -> KML生成"""
        fields = [{
            "name": "テスト",
            "coordinates": [[43.0, 141.0], [43.0, 141.001],
                           [43.001, 141.001], [43.001, 141.0]],
        }]
        result = generate_kml_content(fields, "テスト出力")
        assert "<?xml" in result
        assert "テスト" in result

    def test_empty_fields(self):
        """境界値: 空リスト"""
        result = generate_kml_content([], "空テスト")
        assert "<?xml" in result
```

### 4.5 ヒューリスティック最適化テスト例

```python
# tests/test_optimizer_unit.py
"""
輪作最適化（optimizer.py）の単体テスト
"""
import pytest

from rotation_planner.app.optimizer import (
    RotationPlannerHeuristic,
)


# ============================================================
# テストデータ
# ============================================================

@pytest.fixture
def minimal_optimizer():
    """最小構成のオプティマイザ"""
    fields = [
        {"field_code": "F001", "name": "ほ場1", "area_ha": 2.0,
         "beet_forbidden": False},
        {"field_code": "F002", "name": "ほ場2", "area_ha": 3.0,
         "beet_forbidden": False},
    ]
    past_years = {"R5": {0: "大豆", 1: "てんさい"},
                  "R6": {0: "てんさい", 1: "春小麦"},
                  "R7": {0: "春小麦", 1: "大豆"}}
    future_years = ["R8", "R9"]
    crops = ["てんさい", "大豆", "春小麦"]
    constraints = {
        "crop_mins": {},
        "crop_caps": {},
        "min_gap_years": {"てんさい": 4},
        "min_fields": {},
        "max_fields": {},
        "forbidden_transitions": set(),
        "preferred_transitions": {},
        "main_crops": crops,
        "unknown_mode": "skip",
    }
    return RotationPlannerHeuristic(
        fields, past_years, future_years, crops, constraints
    )


class TestHeuristicGapConstraint:
    """間隔制約テスト"""

    def test_gap_satisfied(self, minimal_optimizer):
        """間隔制約を満たす場合"""
        opt = minimal_optimizer
        plan = {}
        # 春小麦にはgap制約がないのでTrue
        result = opt.check_gap_constraint(
            field_idx=0, year="R8", crop="春小麦", plan=plan
        )
        assert result is True

    def test_gap_violated(self, minimal_optimizer):
        """間隔制約に違反する場合"""
        opt = minimal_optimizer
        plan = {}
        # F001はR6にてんさいを作付 -> R8は間隔2年で不足(min_gap=4)
        result = opt.check_gap_constraint(
            field_idx=0, year="R8", crop="てんさい", plan=plan
        )
        assert result is False


class TestHeuristicSolve:
    """solve テスト"""

    def test_minimal_solve(self, minimal_optimizer):
        """最小問題で解が得られること"""
        plan, score, violations = minimal_optimizer.solve()

        # 結果が返ること
        assert isinstance(plan, dict)
        assert isinstance(score, (int, float))
        assert isinstance(violations, list)
```

### 4.6 面積計算テスト例

```python
# tests/test_map_unit.py
"""
地図・面積計算（map.py）の単体テスト
"""
import pytest

from rotation_planner.field.map import (
    calculate_area_from_coords,
    m2_to_ha,
    m2_to_a,
)


class TestAreaCalculation:
    """面積計算のテスト"""

    def test_known_area(self):
        """既知の面積: 約100m四方 = 約1ha"""
        # 北海道の約100m四方（概算）
        coords = [
            [43.0, 141.0],
            [43.0, 141.00125],   # 約100m東
            [43.0009, 141.00125], # 約100m北
            [43.0009, 141.0],
        ]
        area_m2 = calculate_area_from_coords(coords)
        area_ha = m2_to_ha(area_m2)

        # 1haの+-50%以内（座標精度による誤差を許容）
        assert 0.5 < area_ha < 1.5

    def test_triangle(self):
        """三角形の面積"""
        coords = [
            [43.0, 141.0],
            [43.001, 141.0],
            [43.0, 141.001],
        ]
        area_m2 = calculate_area_from_coords(coords)
        assert area_m2 > 0

    def test_zero_area(self):
        """境界値: 点（面積0）"""
        coords = [[43.0, 141.0]]
        area_m2 = calculate_area_from_coords(coords)
        assert area_m2 == 0 or area_m2 is None


class TestUnitConversion:
    """単位変換テスト"""

    @pytest.mark.parametrize("m2, ha", [
        (10000, 1.0),
        (0, 0.0),
        (50000, 5.0),
    ])
    def test_m2_to_ha(self, m2, ha):
        assert abs(m2_to_ha(m2) - ha) < 0.001

    @pytest.mark.parametrize("m2, a", [
        (100, 1.0),
        (0, 0.0),
        (500, 5.0),
    ])
    def test_m2_to_a(self, m2, a):
        assert abs(m2_to_a(m2) - a) < 0.001
```

---

## 5. モックパターン集

### 5.1 DB接続モック

```python
from unittest.mock import patch, MagicMock
import sqlite3

def test_with_mock_db():
    """DB接続をモックしてリポジトリをテスト"""
    mock_conn = MagicMock(spec=sqlite3.Connection)
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    mock_conn.execute.return_value = mock_cursor

    # fetchone のモック
    mock_cursor.fetchone.return_value = {
        "id": 1, "name": "テスト", "area_ha": 2.5
    }

    # fetchall のモック
    mock_cursor.fetchall.return_value = [
        {"id": 1, "name": "ほ場1"},
        {"id": 2, "name": "ほ場2"},
    ]

    with patch('rotation_planner.common.db.get_connection',
               return_value=mock_conn):
        # テスト対象関数を呼び出し
        pass
```

### 5.2 コンテキストマネージャDBモック

```python
from unittest.mock import patch, MagicMock
from contextlib import contextmanager

def test_with_context_manager_mock():
    """get_db()コンテキストマネージャのモック"""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.execute.return_value = mock_cursor

    @contextmanager
    def mock_get_db():
        yield mock_conn

    with patch('rotation_planner.common.db.get_db', mock_get_db):
        # テスト対象関数を呼び出し
        pass
```

### 5.3 外部APIモック（Nominatim）

```python
from unittest.mock import patch, MagicMock

def test_search_address_success():
    """住所検索のモックテスト"""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = [{
        "lat": "43.06417",
        "lon": "141.34694",
        "display_name": "北海道札幌市"
    }]

    with patch('requests.get', return_value=mock_response):
        from rotation_planner.field.map import search_address
        lat, lng, msg = search_address("札幌市")
        assert lat is not None
        assert lng is not None


def test_search_address_timeout():
    """住所検索タイムアウト"""
    import requests

    with patch('requests.get', side_effect=requests.Timeout):
        from rotation_planner.field.map import search_address
        lat, lng, msg = search_address("札幌市")
        assert lat is None
        assert "タイムアウト" in msg or "エラー" in msg
```

### 5.4 Anthropic APIモック（画像解析）

```python
from unittest.mock import patch, MagicMock

def test_recognize_pesticide_name():
    """Claude Vision APIのモック"""
    mock_message = MagicMock()
    mock_message.content = [MagicMock(
        text="農薬名: トップジンM水和剤\n確信度: high"
    )]

    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_message

    with patch.dict('os.environ', {"ANTHROPIC_API_KEY": "test-key"}):
        with patch('anthropic.Anthropic', return_value=mock_client):
            from rotation_planner.pesticide_record.image_analyzer import (
                recognize_pesticide_name
            )
            result = recognize_pesticide_name("/path/to/image.jpg")
            assert result["pesticide_name"] == "トップジンM水和剤"
```

### 5.5 ファイルシステムモック

```python
import tempfile
import os

def test_with_temp_csv():
    """一時CSVファイルでテスト"""
    content = "ほ場ID,地区,ほ場名,面積\nF001,A地区,テスト,100"

    with tempfile.NamedTemporaryFile(
        mode='w', suffix='.csv', delete=False,
        encoding='utf-8-sig'
    ) as f:
        f.write(content)
        csv_path = f.name

    try:
        # テスト対象関数を呼び出し
        pass
    finally:
        os.remove(csv_path)


def test_with_temp_kml():
    """一時KMLファイルでテスト"""
    kml_content = '<?xml version="1.0" encoding="UTF-8"?>...'

    with tempfile.NamedTemporaryFile(
        mode='w', suffix='.kml', delete=False,
        encoding='utf-8'
    ) as f:
        f.write(kml_content)
        kml_path = f.name

    try:
        from rotation_planner.field.kml_parser import parse_kml_file
        result = parse_kml_file(kml_path)
        assert isinstance(result, list)
    finally:
        os.remove(kml_path)
```

### 5.6 Gradio状態モック

```python
def test_with_user_state():
    """Gradioユーザー状態のモック"""
    # 農家ユーザー
    farmer_state = {
        "user_id": 3,
        "username": "farmer_demo",
        "display_name": "デモ農家",
        "role": "farmer",
        "org_id": 1,
    }

    # 管理者ユーザー
    admin_state = {
        "user_id": 1,
        "username": "admin",
        "display_name": "管理者",
        "role": "admin",
        "org_id": 1,
    }

    # 未ログイン
    empty_state = {}

    # テスト対象関数を各状態で呼び出し
    pass
```

---

## 6. テスト実行ガイド

### 6.1 環境準備

```bash
# 依存パッケージ
pip install pytest pytest-cov pytest-mock

# カバレッジ計測付き実行
pytest tests/ --cov=rotation_planner --cov-report=html

# 特定テストのみ
pytest tests/test_constraints.py -v

# 特定クラスのみ
pytest tests/test_constraints.py::TestParseForbiddenTransitions -v

# マーカーでフィルタ
pytest tests/ -m "not slow" -v
```

### 6.2 推奨マーカー

```python
# conftest.py に追加
def pytest_configure(config):
    config.addinivalue_line("markers", "slow: 実行に時間がかかるテスト")
    config.addinivalue_line("markers", "db: DB操作を伴うテスト")
    config.addinivalue_line("markers", "api: 外部API呼び出しを伴うテスト")
    config.addinivalue_line("markers", "security: セキュリティテスト")
```

### 6.3 テスト実装の優先順

| Phase | 対象 | テスト数目安 | 工数目安 |
|-------|------|-----------|---------|
| 1 | conftest.py + 制約処理 (P0) | ~20 | 4h |
| 2 | CRUDリポジトリ (P0) | ~30 | 6h |
| 3 | 認証追加テスト (P0) | ~15 | 3h |
| 4 | 農薬計算 + KMLパーサー (P1) | ~25 | 5h |
| 5 | 最適化エンジン (P1) | ~15 | 4h |
| 6 | エクスポート + ほ場管理 (P1-P2) | ~15 | 3h |
| 7 | 面積計算 + UI + CSV (P2) | ~15 | 3h |
| **合計** | | **~135** | **~28h** |

---

## 7. テスト品質基準

### 7.1 カバレッジ目標

| レベル | カバレッジ | 対象 |
|--------|----------|------|
| 最低限 | 40% | 全体（Phase 1-3 完了後） |
| 推奨 | 60% | 全体（Phase 1-5 完了後） |
| 理想 | 80% | コアロジック（optimizer, constraints, calculator） |

### 7.2 テストの原則

1. **Arrange-Act-Assert**: テストは「準備-実行-検証」の3段階
2. **1テスト1検証**: 1つのテストメソッドで1つの振る舞いを検証
3. **独立性**: テスト間に依存関係を作らない
4. **再現性**: 実行順序やタイミングに依存しない
5. **命名規則**: `test_{対象}_{条件}_{期待結果}` の形式

### 7.3 テストコードのアンチパターン（避けるべき）

| パターン | 問題 | 改善策 |
|---------|------|--------|
| `if data:` でテストスキップ | テストが実行されない可能性 | fixtureでデータを保証 |
| 実DB依存 | 環境差異で失敗 | モック or テスト用DB |
| `pass` のみのテスト | 検証なし | 必ずassertを含める |
| ハードコードされたID | 環境依存 | fixtureで動的生成 |

---

## 付録A: テストケースID規則

| プレフィックス | 対象モジュール |
|-------------|-------------|
| F-xx | FieldRepository |
| CH-xx | CropHistoryRepository |
| PL-xx | PlanRepository |
| UR-xx | UserRepository |
| PM-xx | PesticideMasterRepository |
| UC-xx | UserCropRepository |
| CO-xx | UserConstraintsRepository |
| AU-xx | auth.py |
| CN-xx | constraints.py |
| OH-xx | optimizer (Heuristic) |
| OO-xx | optimizer (OR-Tools) |
| PC-xx | pesticide/calculator |
| KM-xx | kml_parser |
| EX-xx | export |
| FC-xx | field/crud |
| MA-xx | field/map |
| UI-xx | ui_utils |
| CI-xx | csv_io |

## 付録B: 全テスト対象関数の棚卸し

### B.1 テスト未対応関数一覧（優先度順）

**P0 (計44関数)**:
- FieldRepository: create_field, update_field, delete_field, get_field, get_field_with_history (5)
- CropHistoryRepository: add_history, get_history, delete_history, bulk_update_history, get_all_history_for_user, bulk_add_history (6)
- PlanRepository: create_plan, get_plan, update_plan, delete_plan (4)
- UserRepository: create_user, get_user, authenticate (3)
- UserCropRepository: set_user_crops, add_user_crop, remove_user_crop, get_parent_crop_id_by_name (4)
- UserConstraintsRepository: save_constraints, get_constraints, delete_constraints (3)
- PesticideMasterRepository: bulk_import, get_by_crop, get_all, get_by_id, create, update, delete, delete_all (8)
- auth.py: add_user, update_password, delete_user, get_admin_count, get_user_role, get_accessible_user_ids, load_users (7)
- constraints.py: get_default_crops, build_constraints_table, parse_constraints_table, parse_forbidden_transitions (4)

**P1 (計30関数)**:
- optimizer.py: check_gap_constraint, check_transition_constraint, get_valid_crops, check_cap_constraint, check_field_count_constraint, evaluate_solution, solve (Heuristic + OR-Tools) (12)
- calculator.py: convert_to_base_unit, convert_from_base_unit, normalize_crop, load_rotation_plan, load_inventory_csv, calculate_requirements (6)
- kml_parser.py: parse_coordinates_string, parse_kml_content, parse_kml_file, parse_kmz_file, generate_kml_content, export_fields_to_kml (6)
- export.py: can_access_all_data, export_rotation_plan_csv, export_fields_csv, export_all_plans_csv, export_pesticide_order_csv, export_ja_aggregate_pesticide_csv (6)

**P2 (計20関数)**:
- field/crud.py: get_next_field_id, fields_to_dataframe, register_field_with_state, delete_field_with_state, get_field_history_with_state (5)
- field/map.py: calculate_area_from_coords, m2_to_ha, m2_to_a, search_address (4)
- ui_utils.py: format_alert, format_success, format_error, format_warning, format_info (5)
- csv_io.py: export_order_csv, import_order_csv, merge_with_calculated (3)
- db.py: init_db, check_db_exists, get_db_info (3)

**合計: ~94関数（テストケース合計: ~135件）**

---

**作成日**: 2026-02-06
**作成者**: 足軽5号（QAエンジニアペルソナ）
**参考**: ERROR_HANDLING_DESIGN.md, ERROR_ANALYSIS.md
