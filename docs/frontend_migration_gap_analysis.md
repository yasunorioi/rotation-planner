# Gradio版 vs React+FastAPI版 機能差分レポート

> **作成日**: 2026-02-10
> **情報源**: Wave1調査 subtask_334（機能網羅性）, subtask_335（DB/テスト）, subtask_336（個別機能分析）
> **対象リポジトリ**: /home/yasu/rotation-planner
> **ブランチ**: main（Gradio版） vs feature/frontend-migration（React+FastAPI版）

---

## Executive Summary

**判定: Conditional Go（条件付きマージ可）**

React+FastAPI版は全36機能中26機能が移植済みで、基盤として十分な完成度にある。しかし**マージ前に移植が必要なP1機能が4件**（水田ポリゴン、作付けポリゴン、面積集計、crop_family+隣接筆制約）存在し、推定工数は**4〜5日**。これらはGIS系コア機能であり、欠落したままマージすると畑作農業管理としての基幹機能が失われる。

一方、React版のほうが進んでいる機能も4件あり（JS版ソルバー、在庫管理拡張、在庫連動警告、FAMIC管理UI）、マージは双方に利益がある。テストカバレッジはGradio版32ファイル/414関数に対しReact版8ファイル/148関数と大きな差があり、P1移植時にテストも同時移植すべきである。

---

## 1. 機能対応表

全36機能のGradio版 vs React+FastAPI版対応状況。

| 凡例 | 意味 |
|------|------|
| ✅ | 両版で実装済み |
| 🔴 | Gradio版のみ（React版に欠落） |
| 🟢 | React版のみ（Gradio版にない新機能） |
| 🟡 | 部分的（片方が拡張 or 不完全） |

| #  | 機能名 | Gradio版 | React版 | 状態 |
|----|--------|---------|---------|------|
| 1  | ホーム/ダッシュボード | portal.py:Tab("ホーム") | Dashboard.jsx | ✅ |
| 2  | 作物設定 | crop_settings.py | CropSettings.jsx | ✅ |
| 3  | ほ場登録 | portal.py:Tab("ほ場登録") | FieldRegister.jsx | ✅ |
| 4  | ほ場一覧 | portal.py:Tab("ほ場一覧") | Fields.jsx | ✅ |
| 5  | **水田ポリゴン** | paddy_ui.py + paddy_crud.py | **なし** | **🔴** |
| 6  | **作付けポリゴン** | crop_polygon_ui.py + crop_polygon_crud.py | **なし** | **🔴** |
| 7  | **面積集計** | aggregation_ui.py + aggregation_service.py | **なし** | **🔴** |
| 8  | 輪作計画 | portal.py:Tab("輪作計画") | Rotation.jsx + Plans.jsx | ✅ |
| 9  | 農薬発注 | portal.py:Tab("農薬発注") | PesticideOrders.jsx | ✅ |
| 10 | 防除記録 | portal.py:Tab("防除記録") | PesticideRecords.jsx | ✅ |
| 11 | データ管理 | data_management/ | DataManagement.jsx | ✅ |
| 12 | JA集計 | ja_staff_ui.py | JAAggregation.jsx | ✅ |
| 13 | 防除マスタ | portal.py:Tab("防除マスタ") | PesticideMasters.jsx | ✅ |
| 14 | 管理 | portal.py:Tab("管理") | UserManagement.jsx + SystemInfo.jsx | ✅ |
| 15 | ユーザー認証 | Gradio auth=(user, pw) | JWT (login/register/token) | ✅ |
| 16 | **隣接筆制約(PRO)** | spatial.py + optimizer.py + constraints.py | **なし** | **🔴** |
| 17 | 筆ポリゴンUI | folium地図 | FudePolygon (API有/UI限定的) | 🟡 |
| 18 | FAMIC連携 | famic/importer.py | /api/famic/* (6エンドポイント) | ✅ |
| 19 | Claude Vision画像解析 | image_analyzer.py | /api/pesticide-records/analyze-image | ✅ |
| 20 | GPS座標マッチング | analyze_image内 | /api/gps/match-field (分離API) | ✅ |
| 21 | 希釈倍率計算 | pesticide_record/ui.py | /api/pesticide-masters/.../dilution-rates | ✅ |
| 22 | KMLインポート | portal.py内 | /api/kml/import | ✅ |
| 23 | KMLエクスポート | portal.py内 | /api/kml/export | ✅ |
| 24 | CSVインポート | data_management/ | /api/rotation/import-csv | ✅ |
| 25 | CSVエクスポート | data_management/ | /api/pesticide-orders/export/csv | ✅ |
| 26 | 輪作CSV出力 | 基本CSV | 拡張CSV (JSON→CSV変換) | 🟡 |
| 27 | DBバックアップ | backup_db.py (245行, 世代管理) | /api/admin/backup (DLのみ) | 🟡 |
| 28 | 輪作最適化 | optimizer.py (Python/OR-Tools) | /api/rotation/optimize + JS solver | ✅ |
| 29 | JS版ソルバー | なし | /api/rotation/optimize-js | 🟢 |
| 30 | 在庫管理拡張 | 基本5カラム | 13カラム + 入出庫履歴 + 操作ログ | 🟢 |
| 31 | 在庫連動警告 | なし | /api/inventory/warnings | 🟢 |
| 32 | FAMIC管理UI | CLI的操作 | 自動更新トグル + 利用規約フロー | 🟢 |
| 33 | ロール管理 | Gradio auth | /api/admin/users + role-based access | ✅ |
| 34 | crop_master / user_crops | db_access.py Repository | /api/crops + /api/user-crops | ✅ |
| 35 | **crop_family(作物科)** | migrate_crop_family.sql + get_family_map() | **なし** | **🔴** |
| 36 | テスト | 32ファイル / 414関数 | 8ファイル / 148関数 | 🟡 |

### 集計

| 状態 | 件数 | 内容 |
|------|------|------|
| ✅ 共通 | 23 | 両版で実装済み |
| 🔴 Gradio版のみ | 5 | 水田ポリゴン, 作付けポリゴン, 面積集計, 隣接筆制約, crop_family |
| 🟢 React版のみ | 4 | JS版ソルバー, 在庫管理拡張, 在庫連動警告, FAMIC管理UI |
| 🟡 部分的 | 4 | 筆ポリゴンUI, 輪作CSV, DBバックアップ, テスト |

---

## 2. DB/データモデル差分

### 2.1 スキーマ差分表

スキーマバージョン: Gradio版 v1.1 (2026-02-01) / React版 v1.2 (2026-02-02)

| # | テーブル名 | Gradio版 | React版 | 差分 |
|---|-----------|---------|---------|------|
| 1 | organizations | ✅ | ✅ | 同一 |
| 2 | users | ✅ | ✅ | 同一 |
| 3 | fields | ✅ 11カラム | ✅ 10カラム | Gradio版に `land_category` カラム追加 |
| 4 | crop_history | ✅ | ✅ | 同一 |
| 5 | rotation_plans | ✅ | ✅ | 同一 |
| 6 | plan_details | ✅ | ✅ | 同一 |
| 7 | pesticide_masters | ✅ | ✅ | 同一 |
| 8 | user_constraints | ✅ | ✅ | 同一 |
| 9 | order_templates | ✅ | ✅ | 同一 |
| 10 | inventory | ✅ 5カラム(基本) | ✅ 13カラム(拡張) | **React版が拡張** |
| 11 | inventory_transactions | なし | ✅ | React版のみ（入出庫履歴） |
| 12 | inventory_csv_operations | なし | ✅ | React版のみ（操作ログ） |
| 13 | **paddy_polygons** | **✅** | **なし** | **Gradio版のみ** |
| 14 | **crop_polygons** | **✅** | **なし** | **Gradio版のみ** |
| 15 | crop_master | マイグレーション | マイグレーション | 同一SQL（db_schema未統合） |
| 16 | user_crops | マイグレーション | マイグレーション | 同一SQL（db_schema未統合） |
| 17 | pesticide_orders | マイグレーション | マイグレーション | 同一SQL |
| 18 | pesticide_registry | マイグレーション | マイグレーション | 同一SQL |
| 19 | pesticide_usage | マイグレーション | マイグレーション | 同一SQL |
| 20 | pesticide_records | マイグレーション | マイグレーション | 同一SQL |
| 21 | famic_import_log | マイグレーション | マイグレーション | 同一SQL |

**主要な差分:**

1. **fields.land_category**: Gradio版で追加（地目: 畑/畑地化済/水田）。React版になし
2. **inventory**: React版が migrate_inventory.sql で8カラム追加（保管場所, 有効期限, 仕入先等）
3. **inventory_transactions / inventory_csv_operations**: React版のみ（在庫管理の拡張テーブル）
4. **paddy_polygons / crop_polygons**: Gradio版のみ（GIS系コア機能のテーブル）

### 2.2 models.py 差分

| データクラス | Gradio版 | React版 | 差分 |
|------------|---------|---------|------|
| Role (Enum) | ✅ | ✅ | 同一 |
| User | ✅ | ✅ | 同一 |
| Field | ✅ | ✅ | 同一 |
| CropHistory | ✅ | ✅ | 同一 |
| PlanDetail | ✅ | ✅ | 同一 |
| RotationPlan | ✅ | ✅ | 同一 |
| PesticideMaster | ✅ | ✅ | 同一 |
| PesticideOrder | ✅ | ✅ | 同一 |
| **LandCategory (Enum)** | **✅** | **なし** | Gradio版のみ |
| **PaddyPolygon** | **✅** | **なし** | Gradio版のみ |
| **CropPolygon** | **✅** | **なし** | Gradio版のみ |
| **AggregationRow** | **✅** | **なし** | Gradio版のみ |

Gradio版で追加された4クラスはいずれも「ほ場ポリゴン・面積集計」関連。

### 2.3 マイグレーション状況

以下のテーブルは db_schema.sql に含まれず、別途マイグレーションSQLで作成される:

| テーブル | マイグレーションSQL | 備考 |
|---------|-------------------|------|
| crop_master | migrate_crop_schema.sql | 5作物シードデータ含む |
| user_crops | migrate_crop_schema.sql | ユーザー別作物選択 |
| pesticide_orders | migrate_pesticide_orders.sql | 農薬発注 |
| pesticide_registry | migrate_pesticide_record.sql | FAMIC登録情報 |
| pesticide_usage | migrate_pesticide_record.sql | FAMIC適用情報 |
| pesticide_records | migrate_pesticide_record.sql | 防除記録 |
| famic_import_log | migrate_pesticide_record.sql | FAMICインポート履歴 |

**注意**: crop_family はテーブルではなく、crop_master テーブルへの `family` カラム追加（migrate_crop_family.sql）。get_family_map() メソッドで動的マッピング。隣接筆制約（adjacency_constraints）もテーブルではなく user_constraints.constraints_json 内にJSONで保存。

**課題**: マイグレーションSQLが db_schema.sql に未統合。新規セットアップ時は db_schema.sql + 全マイグレーションSQLの実行が必要。

---

## 3. 移植が必要な機能リスト

### 3.1 P1(高): コア機能欠損 — 推定合計 4〜5日

#### (a) 水田ポリゴン + 作付けポリゴン + 面積集計 — 推定 2〜3日

React版に完全に欠落しているGIS系コア機能。

**Gradio版の実装:**
- `field/paddy_crud.py`: 水田ポリゴンCRUD（register, delete, update_conversion, import_kml）
- `field/crop_polygon_crud.py`: 作付けポリゴンCRUD（register, delete, import_kml, copy_previous_year）
- `field/aggregation.py`: クロス集計（作物×地目の面積マトリクス）
- `field/aggregation_service.py`: get_cross_tabulation_for_user, export_csv, subsidy_summary
- `field/spatial.py`: Shapely空間演算（面積計算, 地目判定, ポリゴン合併）
- DBテーブル: `paddy_polygons`（畑地化フラグ+開始年度）, `crop_polygons`（年別作物ポリゴン）
- テスト: test_polygon_repository_unit.py, test_aggregation_*.py, test_spatial_unit.py

**React版の現状:**
- FieldRegister.jsx + FieldMap.jsx でポリゴン描画・編集はUI側で実装済み（Leaflet + leaflet-draw）
- しかし paddy_polygons / crop_polygons テーブルなし
- 集計機能なし

**移植作業:**
- DB: 2テーブル + マイグレーションSQL
- Backend: 2 Repository + aggregation service (~600行)
- API: 8〜10 新規エンドポイント
- Frontend: PaddyPolygonUI, CropPolygonUI, AggregationUI (~3コンポーネント)

#### (b) 隣接筆制約(PRO) + crop_family — 推定 1.5日

**Gradio版の実装:**
- `field/spatial.py` L291-382: build_adjacency_graph() — Shapely buffer(1m) + intersectsで隣接判定
- `app/optimizer.py` L91-110: check_adjacency_constraint() — crop_family_mapで同科判定
- `app/constraints.py` L109-112: Constraintsデータクラス（adjacent_family_enabled, adjacency_pairs, crop_family_map）
- `scripts/migrate_crop_family.sql`: crop_masterにfamilyカラム追加 + 9科シードデータ
- `CropMasterRepository.get_family_map()`: {作物名: 科名} 辞書
- テスト: test_adjacency.py, test_optimizer_adjacency.py, test_crop_family.py

**React版の現状:**
- /api/rotation/optimize エンドポイントは存在するが、adjacency制約パラメータなし
- ConstraintEditor.jsx に隣接筆オプションなし
- crop_master テーブルにfamilyカラムなし

**移植作業:**
- DB: migrate_crop_family.sql 適用（カラム追加 + 9科シード）
- Backend: spatial.py 隣接グラフ関数 + optimizer.py 制約追加 + get_family_map()
- API: constraints エンドポイントに adjacency パラメータ追加
- Frontend: ConstraintEditor.jsx にPROチェックボックス追加
- 推奨手順: family移植 → 隣接筆の順

### 3.2 P2(中): 便利機能 — 推定合計 0.5〜1日

#### (c) DBバックアップ拡張 — 推定 0.5〜1日

**Gradio版:** scripts/backup_db.py (245行)
- `do_backup()`: SQLite .backup() でatomicバックアップ
- `should_backup()`: スマート判定（活動期12-3月=毎日、休閑期4-11月=差分10KB以上のみ）
- `cleanup_old_backups()`: 世代管理（最新7件保持、年次バックアップ保護）
- cron推奨設定付き

**React版:** GET /api/admin/backup（DBファイルダウンロードのみ）

**欠落箇所:**
- リストアAPI（POST /api/admin/restore）
- スマート判定ロジック（季節ベース）
- 世代管理（自動クリーンアップ）
- 年次バックアップ保護
- cron設定ガイド

**移植方法:** scripts/backup_db.py はそのまま流用可能。API追加のみ。

### 3.3 P3(低): nice-to-have

#### (d) テストカバレッジ移植

Gradio版にのみ存在するテスト: **24ファイル / 266関数**

P1機能の移植時に関連テストも同時移植すべき。対象:
- test_adjacency.py — 隣接筆制約
- test_aggregation_unit.py, test_aggregation_service_unit.py — 面積集計
- test_crop_family.py — 作物科
- test_polygon_repository_unit.py — ポリゴンリポジトリ
- test_spatial_unit.py — 空間演算
- test_optimizer_adjacency.py — 最適化+隣接

その他のテスト（test_field_crud_unit.py, test_calculator_unit.py, test_validation_unit.py 等）は機能が共通のため、テストだけの移植で対応可能。

#### (e) db.py エラー処理強化

Gradio版の db.py に追加された改善:
- logging, timeout=30.0, WALモード
- transaction() コンテキストマネージャ
- 例外分類（DuplicateKeyError等）

React版にはこれらがない。直接的な機能影響はないが、運用品質に影響。

---

## 4. React版のほうが進んでいる機能

以下4機能はReact版のみに存在、またはReact版が大幅に拡張している。Gradio版への逆移植候補。

| # | 機能 | React版の実装 | Gradio版との差 |
|---|------|-------------|--------------|
| 1 | **JS版ソルバー** | /api/rotation/optimize-js | クライアント側で即座に最適化可能。OR-Toolsが不要な軽量版 |
| 2 | **在庫管理拡張** | inventory 13カラム + inventory_transactions + inventory_csv_operations | 保管場所, 有効期限, 仕入先, 入出庫履歴, 操作ログを追加。Gradio版は基本5カラムのみ |
| 3 | **在庫連動警告** | /api/inventory/warnings | 在庫残量に基づく発注警告。Gradio版にはなし |
| 4 | **FAMIC管理UI** | 自動更新トグル + 利用規約同意フロー | Gradio版はCLI的操作のみ |

**補足:**
- 画像管理API（/api/pesticide-records/{id}/images）もReact版で構造化が進んでいる
- GPS座標マッチングが分離API化（/api/gps/match-field）されている
- ロール管理がJWT + role-based accessで強化されている

---

## 5. テストカバレッジ比較

### 概要

| 項目 | Gradio版 (main) | React版 (feature/frontend-migration) |
|------|-----------------|--------------------------------------|
| テストファイル数 | **32** | 8 |
| テスト関数数 | **414** | 148 |
| フレームワーク | pytest | pytest |
| フロントエンドテスト | — | test-node.js, test.html |

### Gradio版テストファイル一覧（32ファイル）

| カテゴリ | ファイル | 概要 |
|---------|---------|------|
| 認証 | test_auth.py, test_auth_extended.py | 認証・認可 |
| DB | test_db_access.py | DBアクセス層 |
| ほ場 | test_field_crud_unit.py, test_field_repository.py | ほ場CRUD |
| 作付 | test_crop_history_repository.py, test_crop_family.py | 作付履歴・作物科 |
| 計画 | test_plan_repository.py | 輪作計画 |
| 最適化 | test_optimizer_unit.py, test_optimizer_adjacency.py, test_constraints_unit.py | OR-Tools |
| 隣接 | test_adjacency.py, test_spatial_unit.py | 隣接筆制約・空間演算 |
| 農薬 | test_pesticide_master_repository.py, test_pesticide_order.py, test_pesticide_record.py | 防除関連 |
| CSV | test_csv_validation.py, test_csv_io_unit.py | CSV入出力 |
| GPS | test_gps_matcher.py | GPS位置マッチング |
| KML | test_kml_parser_unit.py | KMLパーサー |
| ポリゴン | test_polygon_repository_unit.py | ポリゴンリポジトリ |
| 集計 | test_aggregation_unit.py, test_aggregation_service_unit.py | 面積集計 |
| UI | test_ui_utils_unit.py, test_map_unit.py | UI/地図ユーティリティ |
| 制約 | test_user_constraints_repository.py, test_user_crop_repository.py | ユーザー制約・作物 |
| ユーザー | test_user_repository.py | ユーザーリポジトリ |
| セキュリティ | test_security.py | セキュリティ |
| バリデーション | test_validation_unit.py | バリデーション |
| エクスポート | test_export.py | データエクスポート |
| JA | test_ja_staff.py | JA職員機能 |
| 計算 | test_calculator_unit.py | 農薬計算 |

### React版テストファイル一覧（8ファイル）

| ファイル | テスト数 | 概要 |
|---------|---------|------|
| test_auth.py | 17 | 認証 |
| test_csv_validation.py | 18 | CSVバリデーション |
| test_db_access.py | 16 | DBアクセス |
| test_gps_matcher.py | 13 | GPS |
| test_ja_staff.py | 23 | JA職員 |
| test_pesticide_order.py | 15 | 農薬発注 |
| test_pesticide_record.py | 36 | 防除記録 |
| test_security.py | 10 | セキュリティ |

### React版にのみ存在するテスト

| ファイル | 概要 |
|---------|------|
| frontend/test-node.js | Node.js rotationSolverテスト |
| frontend/test.html | ブラウザテスト |

### Gradio版にのみ存在するテスト（24ファイル / 266関数）

P1移植時に同時移植すべきテスト（太字）:

- **test_adjacency.py** — 隣接筆制約
- **test_aggregation_unit.py** — 面積集計
- **test_aggregation_service_unit.py** — 面積集計サービス
- **test_crop_family.py** — 作物科
- **test_optimizer_adjacency.py** — 最適化+隣接
- **test_polygon_repository_unit.py** — ポリゴンリポジトリ
- **test_spatial_unit.py** — 空間演算
- test_auth_extended.py — 認証拡張
- test_calculator_unit.py — 農薬計算
- test_constraints_unit.py — 制約
- test_crop_history_repository.py — 作付履歴
- test_csv_io_unit.py — CSV入出力
- test_export.py — エクスポート
- test_field_crud_unit.py — ほ場CRUD
- test_field_repository.py — ほ場リポジトリ
- test_kml_parser_unit.py — KMLパーサー
- test_map_unit.py — 地図
- test_optimizer_unit.py — 最適化
- test_pesticide_master_repository.py — 防除マスタ
- test_plan_repository.py — 計画リポジトリ
- test_ui_utils_unit.py — UIユーティリティ
- test_user_constraints_repository.py — ユーザー制約
- test_user_crop_repository.py — ユーザー作物
- test_user_repository.py — ユーザーリポジトリ
- test_validation_unit.py — バリデーション

---

## 6. 推奨

### 6.1 推奨案: Conditional Go（条件付きマージ可）

React+FastAPI版は基盤として十分な完成度（36機能中23機能が完全移植）にあり、P1移植を完了すればマージ可能。マージを推奨する。

**理由:**
- 共通基盤（db_access.py, models.py）がほぼ同一であり、移植の互換性が高い
- React版のAPI層（73エンドポイント）は構造化されており、Gradio版より保守性が高い
- React版にしかない機能（在庫管理拡張、JS版ソルバー等）の価値がある
- バックエンドは共通Repository層を使用しており、P1移植はdb_access.pyへの追記で済む

### 6.2 マージ前に必須の条件

| # | 条件 | 優先度 | 推定工数 |
|---|------|--------|---------|
| 1 | 水田ポリゴン + 作付けポリゴン + 面積集計の移植 | P1 | 2〜3日 |
| 2 | crop_family (作物科) カラム + シードデータ移植 | P1 | 0.5日 |
| 3 | 隣接筆制約(PRO) の移植 | P1 | 1日 |
| 4 | P1関連テスト7ファイルの移植 | P1 | P1と同時 |
| **合計** | | | **4〜5日** |

### 6.3 推定工数

| フェーズ | 作業 | 工数 |
|---------|------|------|
| Phase 1 | crop_family移植（DB + Repository） | 0.5日 |
| Phase 2 | ポリゴン2テーブル + Repository + API + Frontend | 2〜3日 |
| Phase 3 | 隣接筆制約（spatial.py + optimizer.py + UI） | 1日 |
| Phase 4 | DBバックアップ拡張（P2、マージ後でも可） | 0.5〜1日 |
| Phase 5 | テストカバレッジ拡充（P3、段階的） | 1〜2日 |
| **P1合計** | **Phases 1〜3** | **3.5〜4.5日** |
| **全体合計** | **Phases 1〜5** | **5〜7日** |

### 6.4 推奨マージ手順

```
1. feature/frontend-migration ブランチでP1移植を実施
   (a) migrate_crop_family.sql 適用 + get_family_map() 追加
   (b) paddy_polygons / crop_polygons テーブル + Repository 追加
   (c) 面積集計API + Frontend コンポーネント追加
   (d) 隣接筆制約 (spatial.py + optimizer.py + ConstraintEditor.jsx)
   (e) 関連テスト7ファイル移植

2. P1移植完了後、全テスト実行で回帰確認
   pytest tests/ （バックエンド）
   node frontend/test-node.js （フロントエンド）

3. main ブランチにマージ（squash merge推奨）

4. マージ後にP2/P3を段階的に実施
   (f) DBバックアップ拡張
   (g) テストカバレッジ拡充（残り17ファイル）
   (h) db.py エラー処理強化の逆移植検討
```

---

> **注記**: 本レポートはWave1の3名の調査結果（subtask_334: 機能網羅性, subtask_335: DB/テスト, subtask_336: 個別機能分析）を統合したものである。各調査は `git show origin/feature/frontend-migration:path` による参照で実施し、ブランチ切り替え（git checkout）は行っていない。
