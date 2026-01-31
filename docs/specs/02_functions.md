# 機能仕様書

> **文書バージョン**: 1.0.0
> **最終更新日**: 2026-02-01
> **対象システム**: rotation_planner_ui (北海道畑作農家向け農業管理アプリ)

---

## 目次

1. [作物設定（crop_settings）](#1-作物設定crop_settings)
2. [ほ場登録（field）](#2-ほ場登録field)
3. [作付履歴（crop_history）](#3-作付履歴crop_history)
4. [輪作計画（app/rotation）](#4-輪作計画approtation)
5. [農薬発注（pesticide）](#5-農薬発注pesticide)
6. [データ管理（data_management）](#6-データ管理data_management)
7. [管理機能（admin_ui）](#7-管理機能admin_ui)

---

## 1. 作物設定（crop_settings）

### 1.1 機能概要

農家が自分が作付けする作物を設定する機能。マスタ作物からの選択と、カスタム作物（同一作物の2作目など）の追加が可能。設定した作物はほ場登録時の作物プルダウンに表示される。

### 1.2 入力項目

#### マスタ作物選択

| 項目名 | 必須 | 型 | バリデーション |
|--------|------|-----|----------------|
| 選択作物 | 任意 | List[str] | 有効なマスタ作物名のリスト |

#### カスタム作物追加

| 項目名 | 必須 | 型 | バリデーション |
|--------|------|-----|----------------|
| 親作物名 | 必須 | str | マスタに存在する作物名 |
| カスタム名 | 必須 | str | 空白でない、strip後に1文字以上 |

### 1.3 出力

- **マスタ作物**: 選択済みマスタ作物名のリスト
- **カスタム作物テーブル**: ID、作物名、親作物名を含むDataFrame
- **アラートメッセージ**: 操作結果のHTML形式メッセージ

### 1.4 処理フロー

```
1. 画面初期化
   └─> CropMasterRepository.get_all() で全マスタ作物取得
   └─> UserCropRepository.get_user_crops(user_id) でユーザー選択済み作物取得
   └─> マスタ作物とカスタム作物を分離して表示

2. マスタ作物選択（チェックボックス変更時）
   └─> 選択された作物名リストを取得
   └─> 作物名からIDに変換
   └─> UserCropRepository.set_user_crops() で保存（自動保存）

3. カスタム作物追加
   └─> 入力バリデーション（親作物、カスタム名）
   └─> 親作物IDを取得
   └─> UserCropRepository.add_user_crop(user_id, parent_crop_id, custom_name)
   └─> 一覧を再取得して表示更新

4. カスタム作物削除
   └─> 選択行からIDを取得
   └─> UserCropRepository.remove_user_crop(user_id, user_crop_id)
   └─> 一覧を再取得して表示更新
```

### 1.5 エラーケース

| エラー | 条件 | メッセージ |
|--------|------|------------|
| 未ログイン | user_id が None | 「エラー: ログインしてください」 |
| 親作物未選択 | parent_crop_name が空 | 「エラー: 親作物を選択してください」 |
| カスタム名未入力 | custom_name が空白のみ | 「エラー: カスタム名を入力してください」 |
| 親作物不存在 | マスタに該当作物なし | 「エラー: 親作物 '{name}' が見つかりません」 |

### 1.6 使用するRepository/DB操作

- `CropMasterRepository.get_all(active_only=True)`: 有効な全マスタ作物取得
- `UserCropRepository.get_user_crops(user_id)`: ユーザーの選択作物取得
- `UserCropRepository.get_user_crop_ids(user_id)`: ユーザーの選択作物ID取得
- `UserCropRepository.set_user_crops(user_id, crop_ids)`: マスタ作物選択を設定
- `UserCropRepository.add_user_crop(user_id, parent_crop_id, custom_name)`: カスタム作物追加
- `UserCropRepository.remove_user_crop(user_id, user_crop_id)`: カスタム作物削除

---

## 2. ほ場登録（field）

### 2.1 機能概要

地図上でポリゴンを描画してほ場を登録する機能。住所検索、筆ポリゴン表示、KML/KMZインポート/エクスポートに対応。

### 2.2 入力項目

#### ほ場登録

| 項目名 | 必須 | 型 | バリデーション |
|--------|------|-----|----------------|
| ほ場ID | 必須 | str | 空白でない、重複不可 |
| 地区 | 任意 | str | - |
| ほ場名 | 任意 | str | 空の場合はほ場IDを使用 |
| 今年の作物 | 任意 | str | ユーザーの設定作物から選択 |
| 馬鈴薯・てんさい禁止 | 任意 | bool | デフォルト: False |
| 座標データ | 必須 | str (JSON) | 3点以上の座標、有効なJSON |

#### KML/KMZインポート

| 項目名 | 必須 | 型 | バリデーション |
|--------|------|-----|----------------|
| ファイル | 必須 | File | .kml または .kmz 拡張子 |

#### 住所検索

| 項目名 | 必須 | 型 | バリデーション |
|--------|------|-----|----------------|
| 検索クエリ | 必須 | str | 空白でない |

### 2.3 出力

- **ほ場一覧テーブル**: ID、ほ場ID、地区、ほ場名、面積(ha)、面積(a)、禁止フラグを含むDataFrame
- **地図HTML**: Leaflet地図（ほ場ポリゴン、筆ポリゴン表示）
- **KML/KMZファイル**: エクスポート時のダウンロードファイル
- **次のほ場ID**: 自動採番された次のほ場ID（例: F003）

### 2.4 処理フロー

```
1. 画面初期化
   └─> FieldRepository.get_fields(user_id) でほ場一覧取得
   └─> get_next_field_id(user_id) で次のほ場ID生成
   └─> 筆ポリゴンを取得してLeaflet地図を生成

2. 住所検索
   └─> Nominatim APIで住所検索
   └─> 緯度・経度を取得
   └─> 地図を検索位置に移動

3. ほ場登録
   └─> 入力バリデーション
   └─> 座標JSONをパース
   └─> 面積を座標から計算（calculate_area_from_coords）
   └─> FieldRepository.get_field_by_code() で重複チェック
   └─> FieldRepository.create_field() で登録
   └─> 作物が設定されていればCropHistoryRepository.add_history()

4. ほ場削除
   └─> FieldRepository.get_field_by_code() でほ場取得
   └─> FieldRepository.delete_field() で削除

5. KML/KMZインポート
   └─> ファイルを読み込み（parse_kml_or_kmz_bytes）
   └─> ポリゴンを抽出してプレビュー表示
   └─> 一括登録ボタンで全ほ場を登録

6. KML/KMZエクスポート
   └─> FieldRepository.get_fields() でほ場取得
   └─> 座標データをKML形式に変換
   └─> export_fields_to_kml/kmz() でファイル生成
```

### 2.5 エラーケース

| エラー | 条件 | メッセージ |
|--------|------|------------|
| 未ログイン | user_id が None | 「エラー: ログインが必要です」 |
| ほ場ID未入力 | field_id が空白 | 「エラー: ほ場IDを入力してください」 |
| 座標未入力 | coords_json が空白 | 「エラー: 地図上でポリゴンを描画してください」 |
| 座標不足 | 座標が3点未満 | 「エラー: 3点以上の頂点が必要です」 |
| 座標形式エラー | JSONパースエラー | 「エラー: 座標データが不正です」 |
| 重複ID | 同一IDが既存 | 「エラー: ほ場ID '{id}' は既に登録されています」 |
| KMLエラー | ポリゴンなし | 「ポリゴンが見つかりませんでした」 |

### 2.6 使用するRepository/DB操作

- `FieldRepository.get_fields(user_id)`: ほ場一覧取得
- `FieldRepository.get_field_by_code(user_id, field_code)`: ほ場コードで取得
- `FieldRepository.create_field(user_id, data)`: ほ場作成
- `FieldRepository.delete_field(field_id)`: ほ場削除
- `CropHistoryRepository.add_history(field_id, year, crop, is_inferred)`: 作付履歴追加
- `UserCropRepository.get_user_crops(user_id)`: ユーザー作物取得（プルダウン用）

---

## 3. 作付履歴（crop_history）

### 3.1 機能概要

ほ場×年度のマトリックス形式で作付履歴を表示・編集する機能。連作障害作物の間隔チェックを自動で実施し、警告を表示する。

### 3.2 入力項目

#### 表示設定

| 項目名 | 必須 | 型 | バリデーション |
|--------|------|-----|----------------|
| 表示モード | 必須 | str | 「全ほ場」または「ほ場選択」 |
| ほ場選択 | 条件付き | List[str] | 表示モード=「ほ場選択」時に必須 |
| 開始年 | 必須 | str | R1〜R20 |
| 終了年 | 必須 | str | R1〜R20、開始年以上 |

#### マトリックス編集

| 項目名 | 必須 | 型 | バリデーション |
|--------|------|-----|----------------|
| セル値 | 任意 | str | 作物名（空白=削除） |

### 3.3 出力

- **履歴マトリックステーブル**: ほ場×年度のDataFrame（直接編集可能）
- **警告メッセージ**: 連作障害警告のHTML
- **CSVファイル**: エクスポート時のダウンロードファイル

### 3.4 処理フロー

```
1. 画面初期化/再読込
   └─> FieldRepository.get_fields(user_id) でほ場一覧取得
   └─> CropHistoryRepository.get_all_history_for_user(user_id) で全履歴取得
   └─> build_history_matrix() でマトリックス構築
   └─> check_rotation_warnings() で連作警告チェック
   └─> 推論補完された値には*マークを付与

2. マトリックス編集（ユーザー操作）
   └─> テーブルのセルを直接編集

3. 保存
   └─> DataFrameから更新データを構築
   └─> *マークを除去
   └─> CropHistoryRepository.bulk_update_history() で一括更新

4. CSVエクスポート
   └─> DataFrameをCSVに変換
   └─> *マークを除去して出力
```

### 3.5 連作警告チェックロジック

```python
# 連作障害作物のデフォルト間隔（DEFAULT_CONSTRAINTS参照）
# - てんさい: 4年
# - 馬鈴薯: 4年

for 各ほ場:
    for 各年度:
        crop = 当該年度の作物
        if crop in 連作障害作物:
            required_gap = 必要間隔年数
            for 過去の年度:
                if 同じ作物が作付けされていた:
                    actual_gap = 実際の間隔
                    if actual_gap < required_gap:
                        警告追加
```

### 3.6 エラーケース

| エラー | 条件 | メッセージ |
|--------|------|------------|
| 未ログイン | user_id が None | 「ログインが必要です」 |
| ほ場未登録 | ほ場リストが空 | 「ほ場が登録されていません」 |
| 保存データなし | DataFrame が空 | 「保存するデータがありません」 |

### 3.7 使用するRepository/DB操作

- `FieldRepository.get_fields(user_id)`: ほ場一覧取得
- `CropHistoryRepository.get_all_history_for_user(user_id)`: 全履歴取得
- `CropHistoryRepository.bulk_update_history(updates)`: 履歴一括更新
- `UserCropRepository.get_user_crops(user_id)`: ユーザー作物取得（連作警告用）

---

## 4. 輪作計画（app/rotation）

### 4.1 機能概要

過去の作付データから、OR-Tools（CP-SAT）を使用して将来の輪作計画を自動生成する機能。各種制約（面積上限、間隔年数、禁止遷移など）を考慮した最適化を行う。

### 4.2 入力項目

#### 基本設定

| 項目名 | 必須 | 型 | バリデーション |
|--------|------|-----|----------------|
| CSVファイル | 必須 | File | .csv形式、必須カラムあり |
| 面積単位 | 必須 | str | 「a (アール)」または「ha (ヘクタール)」 |
| 将来年数 | 必須 | int | 1〜10 |
| 空欄の扱い | 必須 | str | 「制約をかけない」or「安全側」 |
| 計算精度 | 必須 | str | 「標準（10秒）」or「高精度（60秒）」 |
| てんさい必須 | 任意 | bool | 毎年1ほ場以上 |
| 空欄を推論で補完 | 任意 | bool | デフォルト: True |
| 地区まとめ優先 | 任意 | bool | デフォルト: True |

#### 作物マスター

| 項目名 | 必須 | 型 | バリデーション |
|--------|------|-----|----------------|
| 作物リスト | 必須 | str | 改行区切り、1つ以上 |

#### 制約設定テーブル

| カラム | 型 | 説明 |
|--------|-----|------|
| 作物 | str | 作物名 |
| 最小(ha) | float | 年間面積下限（0=なし） |
| 最大(ha) | float | 年間面積上限（0=無制限） |
| 間隔(年) | int | 最小作付間隔 |
| 最小筆数 | int | 年間最小ほ場数 |
| 最大筆数 | int | 年間最大ほ場数（0=無制限） |

#### 追加設定

| 項目名 | 必須 | 型 | バリデーション |
|--------|------|-----|----------------|
| 追加禁止遷移 | 任意 | str | 「from->to, from->to, ...」形式 |
| 優先遷移 | 任意 | str | 「from->to:weight, ...」形式 |
| 主作物 | 任意 | str | カンマ区切り |

### 4.3 固定の禁止遷移

以下の遷移は常に禁止される：

| 遷移 | 理由 |
|------|------|
| てんさい→秋小麦 | 作期重複（ビート5-11月、秋小麦9月播種） |
| 春小麦→秋小麦 | 病害対策 |
| 同一作物→同一作物 | 連作禁止 |

### 4.4 出力

- **ほ場×年計画表**: ほ場ごとの年別作物割当DataFrame
- **年別面積合計**: 作物別年間面積の集計DataFrame
- **計画CSV**: ダウンロード用ファイル
- **実行結果メッセージ**: スコア、警告、ボトルネック分析

### 4.5 処理フロー

```
1. データ読み込み
   └─> CSVファイルをパース（load_csv）
   └─> ほ場データと過去年を抽出
   └─> 将来年を生成（generate_future_years）

2. 制約パース
   └─> 制約テーブルをパース（parse_constraints_table）
   └─> 禁止遷移をパース（parse_forbidden_transitions）
   └─> 優先遷移をパース（parse_preferred_transitions）
   └─> 固定禁止遷移を追加

3. 空欄推論（オプション）
   └─> infer_unknown_crops() で過去履歴から推論

4. 最適化実行（RotationPlannerORTools.solve）
   a. 決定変数定義: x[f,y,c] = ほ場f・年y・作物cの割当
   b. 制約追加:
      - 各ほ場・各年に1作物のみ
      - 連作禁止（将来年同士、過去→将来）
      - 禁止遷移
      - 間隔制約
      - 馬鈴薯・てんさい禁止ほ場
   c. 目的関数:
      - 面積上限/下限違反ペナルティ
      - ほ場数上限/下限違反ペナルティ
      - 年間面積変動最小化
      - 地区まとめボーナス
   d. ソルバー実行（タイムアウト: 10秒 or 60秒）

5. 結果生成
   └─> generate_result_tables() で表形式に変換
   └─> generate_csv_content() でCSV生成
   └─> run_sensitivity_analysis() でボトルネック分析

6. フォールバック
   └─> OR-Tools失敗時はヒューリスティック版で再計算
```

### 4.6 エラーケース

| エラー | 条件 | メッセージ |
|--------|------|------------|
| ファイル未指定 | csv_file が None | 「エラー: CSVファイルを指定してください」 |
| ほ場なし | ほ場データが空 | 「エラー: ほ場データがありません」 |
| 作物なし | 作物リストが空 | 「エラー: 作物マスターが空です」 |
| 年列なし | R数字列が見つからない | 「エラー: 年列が見つかりません」 |

### 4.7 警告（ソフト制約違反）

- 「{year}の{crop}が面積上限を{ha}ha超過」
- 「{year}の{crop}が面積下限を{ha}ha不足」
- 「{year}の{crop}がほ場数上限を{n}超過」
- 「{year}の{crop}がほ場数下限を{n}不足」

### 4.8 使用するRepository/DB操作

CSV入力の場合は直接DBアクセスなし。DB対応時は以下を使用：

- `FieldRepository.get_fields(user_id)`: ほ場取得
- `CropHistoryRepository.get_history(field_id)`: 作付履歴取得
- `PlanRepository.create_plan(user_id, data)`: 計画保存

---

## 5. 農薬発注（pesticide）

### 5.1 機能概要

輪作計画から年間の農薬必要量を算出する機能。防除マスタと連携し、作物×面積から農薬必要量を計算。PDF出力、DB保存に対応。

### 5.2 入力項目

#### 計算パラメータ

| 項目名 | 必須 | 型 | バリデーション |
|--------|------|-----|----------------|
| 登録済み輪作計画 | 必須 | int | 有効な計画ID |
| 対象年 | 必須 | str | 計画に含まれる年度 |
| 面積単位 | 必須 | str | 「ha」または「a」 |

#### 保存パラメータ

| 項目名 | 必須 | 型 | バリデーション |
|--------|------|-----|----------------|
| 発注名 | 必須 | str | 空白でない |

### 5.3 散布基準

- **10aあたり散布量**: 100L
- **希釈倍率指定の場合**: 100L ÷ 希釈倍率 × 面積(10a) × 1000 = 必要量(mL)
- **直接指定の場合**: 指定量 × 面積(10a) = 必要量

### 5.4 出力

- **サマリテーブル**: 農薬名、必要量、単位、対象作物、対象病害虫
- **月別詳細テーブル**: 月、作物、対象、農薬名、必要量、面積(ha)
- **CSVファイル**: サマリのダウンロード
- **PDFファイル**: 発注リストのPDF

### 5.5 処理フロー

```
1. 輪作計画読み込み
   └─> PlanRepository.get_plan(plan_id) で計画取得
   └─> 対象年の作物×面積を集計

2. 防除マスタ読み込み
   └─> PesticideMasterRepository.get_all(org_id) でDB取得
   └─> なければCSVからフォールバック読み込み

3. 必要量計算（calculate_pesticide_requirements）
   a. 作物ごとに面積を集計
   b. 各作物に対してマスタから農薬を取得
   c. 希釈倍率または直接指定から必要量を計算
   d. 農薬別に集計
   e. 単位変換（1000mL以上→L、1000g以上→kg）

4. 結果生成
   └─> サマリDataFrame作成
   └─> 月別詳細DataFrame作成
   └─> CSV出力

5. PDF生成（オプション）
   └─> generate_pesticide_order_pdf()

6. DB保存（オプション）
   └─> PesticideOrderRepository.create_order()
```

### 5.6 エラーケース

| エラー | 条件 | メッセージ |
|--------|------|------------|
| 未ログイン | user_id が None | 「エラー: ログインしてください」 |
| 計画未選択 | plan_id が None | 「エラー: 輪作計画を選択してください」 |
| マスタなし | 防除マスタが空 | 「エラー: 防除マスタが見つかりません」 |
| 対象年なし | 年列に該当なし | 「エラー: {year} が見つかりません」 |
| 面積列なし | 面積カラムなし | 「エラー: 面積列が見つかりません」 |
| 作付なし | 対象年のデータなし | 「エラー: 作付データがありません」 |
| 発注名未入力 | 保存時にnameが空 | 「エラー: 発注名を入力してください」 |

### 5.7 使用するRepository/DB操作

- `PlanRepository.get_plan(plan_id)`: 輪作計画取得
- `PesticideMasterRepository.get_all(org_id)`: 防除マスタ取得
- `PesticideOrderRepository.get_orders(user_id)`: 発注一覧取得
- `PesticideOrderRepository.get_order(order_id)`: 発注詳細取得
- `PesticideOrderRepository.create_order(user_id, data)`: 発注作成
- `PesticideOrderRepository.delete_order(order_id)`: 発注削除

---

## 6. データ管理（data_management）

### 6.1 機能概要

CSV形式でのデータ入出力（エクスポート/インポート）を行う機能。ほ場一覧、輪作計画のインポート/エクスポートに対応。

### 6.2 エクスポート機能

#### ほ場一覧エクスポート

出力形式：
```csv
ほ場ID,地区,ほ場名,area,beet_forbidden
F001,北地区,北1号,150.00,0
```

#### 輪作計画エクスポート

出力形式：
```csv
ほ場ID,地区,ほ場名,R5,R6,R7,...
F001,北地区,北1号,大豆,小麦,てんさい,...
```

### 6.3 インポート機能

#### ほ場CSVインポート

入力形式：

| カラム名 | 必須 | 説明 |
|----------|------|------|
| ほ場ID / field_id | 必須 | ほ場識別子 |
| 地区 | 任意 | 地区名 |
| ほ場名 | 任意 | ほ場名称 |
| 面積 / area | 任意 | 面積（自動判定: 100以上ならa、それ以下ならha） |
| 禁止 / beet_forbidden | 任意 | 1/Yes=禁止 |

処理：
```
1. CSVを読み込み
2. カラム名を正規化
3. 必須カラムチェック
4. 各行を処理:
   - 重複チェック（既存はスキップ）
   - 面積をhaに変換
   - FieldRepository.create_field() で登録
```

#### 輪作計画CSVインポート

入力形式：

| カラム名 | 必須 | 説明 |
|----------|------|------|
| ほ場ID / field_code | 必須 | ほ場識別子 |
| 年度 / year | 必須 | 年度（R7形式または西暦） |
| 作物 / crop | 必須 | 作物名 |

バリデーション：
```
1. 作物の空欄チェック → エラー
2. 作物がユーザーの設定作物に存在するかチェック → エラー
3. 連作障害作物の過去履歴チェック → 警告
```

### 6.4 処理フロー

```
エクスポート:
1. FieldRepository/PlanRepository からデータ取得
2. DataFrameに変換
3. CSV出力（UTF-8-BOM）

インポート:
1. CSVを読み込み
2. カラム名正規化
3. バリデーション
4. DB登録
5. 結果ログ出力
```

### 6.5 エラーケース

| エラー | 条件 | メッセージ |
|--------|------|------------|
| 未ログイン | user_id が None | 「エラー: ログインが必要です」 |
| ファイル未選択 | csv_file が None | 「エラー: CSVファイルを選択してください」 |
| 必須カラムなし | 必須カラム欠如 | 「エラー: 必須カラムがありません: [...]」 |
| 計画名未入力 | plan_name が空 | 「エラー: 計画名を入力してください」 |
| 作物空欄 | crop が空 | 「行{n}の作物が空欄です」 |
| 作物未登録 | 設定作物に存在しない | 「作物「{name}」は作物設定に登録されていません」 |

### 6.6 使用するRepository/DB操作

- `FieldRepository.get_fields(user_id)`: ほ場取得（エクスポート）
- `FieldRepository.get_field_by_code(user_id, code)`: 重複チェック
- `FieldRepository.create_field(user_id, data)`: ほ場作成
- `PlanRepository.get_plans(user_id)`: 計画一覧取得
- `PlanRepository.create_plan(user_id, data)`: 計画作成
- `UserCropRepository.get_user_crops(user_id)`: ユーザー作物取得（バリデーション）
- `CropHistoryRepository.get_history(field_id)`: 履歴取得（連作チェック）

---

## 7. 管理機能（admin_ui）

### 7.1 機能概要

管理者向けのシステム管理機能。ユーザー管理、システム情報表示、バックアップ、システム設定、筆ポリゴン管理を提供。

### 7.2 アクセス権限

- **admin（管理者）**: 全機能にアクセス可能
- **ja_staff（JA職員）**: 参照のみ
- **farmer（農家）**: アクセス不可

### 7.3 ユーザー管理機能

#### ユーザー一覧表示

表示項目：#、ユーザー名、ロール、表示名、農家ID、パスワード（非表示）

#### ユーザー追加

入力項目：

| 項目名 | 必須 | 型 | バリデーション |
|--------|------|-----|----------------|
| ユーザー名 | 必須 | str | 空白でない、重複不可 |
| パスワード | 必須 | str | 4文字以上 |
| ロール | 必須 | str | admin/ja_staff/farmer |
| 表示名 | 任意 | str | 空ならユーザー名を使用 |
| 農家ID | 条件付き | str | ロール=farmerの場合 |

#### パスワードリセット

入力項目：

| 項目名 | 必須 | 型 | バリデーション |
|--------|------|-----|----------------|
| 行番号 | 必須 | int | 有効な行番号 |
| 新パスワード | 必須 | str | 4文字以上 |

#### ロール変更

制約：
- 自分自身のロールは変更不可
- 最後の管理者のロールは変更不可

#### ユーザー削除

制約：
- 自分自身は削除不可
- 最後の管理者は削除不可

### 7.4 システム情報

表示項目：
- ユーザー数（ロール別）
- データファイル情報（サイズ、更新日時）
- 環境情報（Python、Gradioバージョン）
- DBテーブル一覧（レコード数）

### 7.5 バックアップ

ダウンロード可能ファイル：
- `users.json`: ユーザー情報
- `rotation_planner.db`: SQLiteデータベース

### 7.6 システム設定

#### デバッグモード

| 設定値 | 動作 |
|--------|------|
| ON | ログイン画面にユーザー切り替えラジオボタン表示 |
| OFF | 通常のログイン画面 |

### 7.7 筆ポリゴン管理

#### アップロード

入力項目：

| 項目名 | 必須 | 型 | バリデーション |
|--------|------|-----|----------------|
| ファイル | 必須 | File[] | .geojson または .json |

バリデーション：
- JSON形式チェック
- GeoJSON形式チェック（type: FeatureCollection/Feature/GeometryCollection）

#### ファイル削除

入力項目：

| 項目名 | 必須 | 型 | バリデーション |
|--------|------|-----|----------------|
| ファイル名 | 必須 | str | 空白でない、存在するファイル |

セキュリティ：ディレクトリトラバーサル防止チェック

### 7.8 処理フロー

```
ユーザー追加:
1. 入力バリデーション
2. 重複チェック
3. パスワードハッシュ化（hash_password）
4. users.jsonに追加（save_users）

筆ポリゴンアップロード:
1. ファイルを読み込み
2. JSON/GeoJSON形式検証
3. Feature数をカウント
4. data/fude_cache/ に保存
```

### 7.9 エラーケース

| エラー | 条件 | メッセージ |
|--------|------|------------|
| ユーザー名未入力 | username が空 | 「エラー: ユーザー名は必須です」 |
| パスワード未入力 | password が空 | 「エラー: パスワードは必須です」 |
| パスワード短い | 4文字未満 | 「エラー: パスワードは4文字以上必要です」 |
| ユーザー名重複 | 既存ユーザー | 「エラー: ユーザー名 '{name}' は既に存在します」 |
| 自己削除 | 自分自身を削除 | 「エラー: 自分自身は削除できません」 |
| 最後の管理者削除 | 管理者が1人のみ | 「エラー: 最後の管理者は削除できません」 |
| ファイル未選択 | files が空 | 「エラー: ファイルを選択してください」 |
| JSON形式エラー | パースエラー | 「JSONパースエラー」 |
| GeoJSON形式エラー | type不正 | 「GeoJSON形式ではありません」 |

### 7.10 使用するRepository/DB操作

- `load_users()`: ユーザー一覧取得（JSONファイル）
- `save_users(users)`: ユーザー保存（JSONファイル）
- `hash_password(password)`: パスワードハッシュ化
- DBテーブル情報はSQLite直接アクセス

---

## 付録A: 共通Repository一覧

| Repository | 用途 | 主要メソッド |
|------------|------|--------------|
| FieldRepository | ほ場管理 | get_fields, create_field, delete_field |
| CropHistoryRepository | 作付履歴 | get_history, add_history, bulk_update_history |
| PlanRepository | 輪作計画 | get_plans, get_plan, create_plan, delete_plan |
| CropMasterRepository | 作物マスタ | get_all, get_by_id, get_by_name |
| UserCropRepository | ユーザー作物 | get_user_crops, set_user_crops, add_user_crop |
| PesticideMasterRepository | 防除マスタ | get_by_crop, get_all |
| PesticideOrderRepository | 農薬発注 | get_orders, create_order, delete_order |
| UserRepository | ユーザー | get_user, get_user_by_username |
| JAStaffRepository | JA職員用 | get_all_fields, get_all_farmers |

---

## 付録B: DBテーブル構造

| テーブル名 | 説明 | 主キー |
|------------|------|--------|
| users | ユーザー情報 | id |
| organizations | 組織情報 | id |
| fields | ほ場情報 | id |
| crop_history | 作付履歴 | id |
| rotation_plans | 輪作計画 | id |
| plan_details | 計画詳細 | id |
| crop_master | 作物マスタ | id |
| user_crops | ユーザー作物 | id |
| pesticide_masters | 防除マスタ | id |
| pesticide_orders | 農薬発注 | id |

---

## 付録C: アラート形式

全機能で共通のアラート形式を使用：

```python
format_success(message)  # 成功メッセージ（緑）
format_error(message)    # エラーメッセージ（赤）
format_warning(message)  # 警告メッセージ（黄）
format_info(message)     # 情報メッセージ（青）
format_alert(message, type)  # 汎用（type: success/error/warning/info）
```
