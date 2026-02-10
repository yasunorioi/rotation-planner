# 農業管理アプリ（Rotation Planner）

北海道畑作農家向けの統合農業管理アプリケーション。
ほ場管理・輪作計画・農薬発注・防除記録を一元管理し、OR-Toolsによる最適化で科学的な輪作計画を自動生成する。

## 主な機能

| 機能 | 説明 |
|------|------|
| 🌱 作物設定 | 作付する作物を選択・カスタム作物追加 |
| 🗺️ ほ場登録 | 地図上でほ場を登録（筆ポリゴン対応・KML/KMZインポート） |
| 🗺️ ほ場一覧 | 年度別作物をマトリックス形式で表示・編集 |
| 🌾 作付けポリゴン管理 | 同一ほ場内の作物別ポリゴン登録・前年コピー・KMLインポート |
| 🌾 水田ポリゴン管理 | 水田ポリゴン登録・畑地化フラグ管理・KMLインポート |
| 📊 地目別集計 | 作物×地目（畑/畑地化済/水田）クロス集計・畑地化年度別面積集計 |
| 🌾 輪作計画 | OR-Tools CP-SATソルバーによる最適な輪作計画自動生成・PDF出力 |
| 💊 農薬発注 | 輪作計画から年間の農薬必要量を算出・PDF出力 |
| 💊 FAMIC農薬インポーター | 農薬検査所（FAMIC）公式XLSデータの一括取込 |
| 🧪 防除記録 | 農薬散布記録の管理・画像解析によるラベル読取 |
| 📥 データ管理 | CSV一括インポート/エクスポート・テンプレート提供 |
| ⚙️ 管理 | ユーザー管理・バックアップ・筆ポリゴンアップロード |

## 技術スタック

| 種別 | 技術 |
|------|------|
| UI | Gradio 4.0+（Webアプリフレームワーク） |
| 言語 | Python 3.11+ |
| DB | SQLite（12テーブル） |
| 最適化 | Google OR-Tools CP-SAT ソルバー |
| 地理空間 | Shapely 2.0+ / Pyproj 3.0+ / Leaflet.js |
| PDF出力 | ReportLab 4.0+ |
| データ処理 | Pandas 2.0+ / NumPy 1.24+ |

## クイックスタート

### React版（推奨）

```bash
git clone https://github.com/yasunorioi/rotation-planner.git
cd rotation-planner
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install -r api/requirements.txt

# フロントエンド依存インストール
cd frontend/app && npm install && cd ../..

# DB初期化
python3 -c "from rotation_planner.common.db import init_db; init_db()"

# 開発サーバー起動（API + React）
bash start-dev.sh
# → API:   http://localhost:8000
# → React: http://localhost:5173
```

### Gradio版（レガシー）

```bash
git clone https://github.com/yasunorioi/rotation-planner.git
cd rotation-planner
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# DB初期化
python3 -c "from rotation_planner.common.db import init_db; init_db()"

# 起動
python3 portal.py
# → http://127.0.0.1:7863
```

### 初期ユーザー

| ユーザー名 | パスワード | ロール |
|-----------|-----------|--------|
| admin | admin123 | 管理者 |
| ja_staff | ja123 | JA職員 |
| farmer_demo | demo123 | 農家（デモ用） |

> ⚠️ **本番環境では必ず初期パスワードを変更してください**

## ユーザーロール

| ロール | 権限 |
|--------|------|
| admin | 全機能 + ユーザー管理 + システム設定 |
| ja_staff | 全機能 + 農家一覧 + 防除マスタ管理 + 農薬集約発注 |
| farmer | 基本機能（作物設定〜農薬発注） |

## 機能詳細

### 🌱 作物設定

- マスタから作付する作物を選択
- カスタム作物の追加（例: ブロッコリー（2作目））
- 選択した作物がほ場登録や輪作計画で使用可能に
- **自動保存**: チェックボックス変更時に即座にDB保存

### 🗺️ ほ場登録

- OpenStreetMap + Leaflet.jsによる地図表示（Leaflet.drawプラグインでポリゴン描画）
- WGS84楕円体による正確な測地面積計算（Shapely + Pyproj）
- ほ場登録時に作付年度・作物を同時設定可能

#### 対応インポート形式

| 形式 | 説明 |
|------|------|
| KML/KMZ | Google Earth形式。Placemark/Polygon、Placemark/LineStringに対応 |
| CSV | テンプレートによる一括登録 |
| 筆ポリゴン | 農水省公開データ（GeoJSON形式、手動ダウンロード） |

#### 筆ポリゴン連携

農林水産省「筆ポリゴンデータ」（https://open.fude.maff.go.jp/）から農地区画情報を取り込み可能。

- バウンディングボックス指定で該当範囲の筆ポリゴンを検索
- 地方公共団体コードによる逆ジオコーディング（北海道全市町村対応）
- GeoJSONファイルの `data/fude_cache/` へのローカルキャッシュ

> **注意**: 筆ポリゴンデータの利用には農水省の利用規約への同意が必要。自動ダウンロードは非対応のため、手動で `data/fude_cache/` にGeoJSONファイルを配置する。

### 🗺️ ほ場一覧

- ほ場×年度のマトリックス形式で作物を表示・編集
- 令和年度形式（R5〜R9など）で年度範囲を指定
- ほ場情報（ID、名前、地区、面積、禁止フラグ）のインライン編集
- 輪作計画結果の微調整が可能

### 🌾 作付けポリゴン管理

同一ほ場内で複数の作物が混在する場合に、作物別の区画を管理する機能。

- **年度別ポリゴン登録**: ほ場ごとに年度・作物を指定してポリゴンを描画
- **KML/KMZインポート**: Google Earth等で作成した区画図を取込
- **前年コピー**: 前年の作付けポリゴンを今年度にコピー
- **面積自動計算**: 測地面積（ha）を自動算出
- 対応テーブル: `crop_polygons`（field_id, year, crop_name, geometry, area_ha）

### 🌾 輪作計画

#### 最適化エンジン

2つのソルバーを搭載:

| ソルバー | 特徴 |
|---------|------|
| OR-Tools CP-SAT（デフォルト） | Google制約プログラミングソルバー。厳密解を探索 |
| ヒューリスティック（フォールバック） | 貪欲法 + ローカルサーチ。高速だが近似解 |

#### 制約設定

**ハード制約（必ず満たす）:**

| 制約 | 説明 | 設定場所 |
|------|------|---------|
| 連作禁止 | 同一作物の連続作付を禁止 | 固定（常に有効） |
| 禁止遷移（固定） | てんさい→秋小麦（作期重複）、春小麦→秋小麦（病害対策） | 固定 |
| 禁止遷移（ユーザー定義） | 任意の作物ペアの遷移を禁止 | `forbidden_transitions` |
| 作付間隔 | 作物ごとの最小間隔年数（例: てんさい・馬鈴薯は4年） | `min_gap_years` |
| てんさい禁止フラグ | `beet_forbidden=1` のほ場でてんさい・馬鈴薯を禁止 | ほ場登録時に設定 |

**ソフト制約（ペナルティ付き最適化）:**

| 制約 | 説明 | 設定場所 |
|------|------|---------|
| 面積上限 | 作物ごとの年間最大ha数 | `cap_ha` |
| 面積下限 | 作物ごとの年間最小ha数 | `min_ha` |
| ほ場数制限 | 作物ごとの最小・最大ほ場数 | `min_fields` / `max_fields` |
| 優先遷移 | 望ましい作物遷移にボーナス（例: てんさい→大豆:10） | `preferred_transitions` |
| 主作物安定 | 主要作物の年間面積変動を抑制 | `main_crops` |
| 地区まとめ | 同一地区に同一作物を集約 | UI チェックボックス |
| 隣接筆同一科制約 | 隣接ほ場での同一科作物を抑制（空間演算で隣接判定） | UI チェックボックス（PRO機能） |

#### 不明年の取扱モード

| モード | 動作 |
|--------|------|
| ignore（推奨） | 不明年は制約なしとして扱う |
| safe | 不明年はワーストケース（全禁止作物の可能性あり）として扱う |

#### 推論モード

- 作付履歴の不明年を制約ベースの推論で自動補完
- 推論された履歴は `is_inferred=1` フラグで区別

#### ボトルネック分析

- 各制約を個別に緩和して改善ポテンシャルを分析
- どの制約が最適化の品質を最も制限しているかを特定

#### 出力

- **PDF/CSV出力**: 計画をダウンロード
- **作付履歴に保存**: 生成した計画を直接作付履歴に反映

### 💊 農薬発注

- 輪作計画から対象年の農薬必要量を自動計算
- 月別詳細スケジュール表示
- 在庫控除: `inventory` テーブルの手持ち在庫を差し引き
- **DB保存**: 発注リストを名前を付けて保存（`order_templates` テーブル）
- **PDF出力**: 印刷用フォーマットでダウンロード
- **保存済み一覧**: 過去の発注リストを読み込み/削除

#### JA職員向け集約機能

- JA管内の全農家の農薬発注を集約
- 農薬名ごとの合計数量を算出
- 農家別内訳の確認
- 一括発注CSVのエクスポート

### 💊 FAMIC農薬インポーター

農薬検査所（FAMIC）が公開する農薬登録情報XLSファイルをDBに一括取込する機能。

- **データソース**: https://www.acis.famic.go.jp/ddownload/index.htm
- **依存ライブラリ**: `xlrd`（XLS読み込み）

| インポート関数 | 対象ファイル | 取込先テーブル |
|---------------|-------------|---------------|
| `import_famic_basic()` | 登録基本部.xls | `pesticide_registry`（登録番号、名称、製造者、有効成分、剤型） |
| `import_famic_usage()` | 登録適用部一/二.xls | `pesticide_usage`（作物名、適用病害虫、希釈倍数、使用時期、使用回数） |

- インポート履歴は `famic_import_log` テーブルに記録
- `get_import_stats()` で現在のインポート状況を確認可能

### 🧪 防除記録

- ほ場ごとの農薬散布記録管理
- 散布日、農薬名、希釈倍率、散布量を記録
- 履歴の編集・削除
- CSV/PDFエクスポート（農薬取締法準拠フォーマット）

#### 画像解析機能

- 農薬ラベルの画像から情報を抽出（`image_analyzer.py`）
- Tesseract OCR + OpenCV による前処理
- 農薬名、登録番号、有効成分、希釈倍率を自動認識

### 🌾 水田・畑地化管理

- **水田ポリゴン登録**: 地図上で水田境界を描画・登録（KML/KMZインポート対応）
- **畑地化フラグ管理**: 水田ポリゴンごとに畑地化フラグ（`is_converted`）と開始年度を設定
- **データソース**: `maff`（農水省筆ポリゴン）/ `kml`（Google Earth）/ `manual`（手動描画）
- **地目自動判定**: 作付けポリゴンと水田ポリゴンの空間演算（Shapely）で地目を自動分類
  - **畑**: 作付けポリゴンのうち水田ポリゴンに重ならない部分
  - **畑地化済**: 畑地化フラグ（`is_converted=true`）の水田ポリゴンと重なる部分
  - **水田**: 畑地化フラグ（`is_converted=false`）の水田ポリゴンと重なる部分
- **地目×作物クロス集計**: 作物を行、地目を列としたクロス集計表を生成
- **畑地化開始年度別面積集計**: 畑地化の開始年度別に面積を集計（補助金申請用）

#### データフロー

```
1. 水田ポリゴン登録（paddy_crud.py）
2. 作付けポリゴン登録（crop_polygon_crud.py）
3. 空間演算で地目判定（spatial.py）
4. 集計処理（aggregation.py → aggregation_service.py）
5. UI表示（aggregation_ui.py）
```

### 📥 データ管理

- ほ場データのCSVインポート/エクスポート
- 作付履歴のCSVインポート/エクスポート
- 防除マスタのCSVインポート/エクスポート
- バリデーション機能（空欄チェック、未登録作物チェック）
- **テンプレート提供**: ほ場・制約・在庫・輪作計画のCSVテンプレートをダウンロード可能
- **DBバックアップ**: SQLiteデータベースのダンプ

### ⚙️ 管理（admin専用）

- ユーザー管理（追加/削除/パスワードリセット/ロール変更）
- システム情報表示
- データバックアップ
- 筆ポリゴンアップロード
- デバッグモード切り替え

## サーバーデプロイ（VPS）

### ワンライナーインストール（推奨）

```bash
curl -sL https://raw.githubusercontent.com/yasunorioi/rotation-planner/main/scripts/install.sh | sudo bash
```

これだけで以下が自動実行されます：
- 必要パッケージのインストール
- アプリユーザー作成
- リポジトリクローン
- Python環境構築
- DB初期化
- systemd/nginx設定

### 動作確認済み環境

- Debian 12 / Ubuntu 22.04
- Python 3.11+
- メモリ 512MB以上

### 手動インストール（詳細）

<details>
<summary>クリックで展開</summary>

### 1. 必要パッケージのインストール

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y git python3 python3-pip python3-venv nginx sqlite3
```

### 2. アプリ用ユーザーとディレクトリ作成

```bash
sudo useradd -m -s /bin/bash webapp
sudo mkdir -p /var/www/rotation-planner
sudo chown webapp:webapp /var/www/rotation-planner
```

### 3. リポジトリをクローン

```bash
sudo -u webapp git clone https://github.com/yasunorioi/rotation-planner.git /var/www/rotation-planner/app
```

### 4. Python仮想環境と依存関係

```bash
sudo -u webapp bash -c "cd /var/www/rotation-planner/app && python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt"
```

### 5. データベース初期化

```bash
sudo -u webapp bash -c "cd /var/www/rotation-planner/app && source venv/bin/activate && python -c 'from rotation_planner.common import init_db; init_db()'"
```

### 6. systemdサービス設定

```bash
sudo tee /etc/systemd/system/rotation-planner.service << 'EOF'
[Unit]
Description=Rotation Planner Gradio App
After=network.target

[Service]
Type=simple
User=webapp
WorkingDirectory=/var/www/rotation-planner/app
ExecStart=/var/www/rotation-planner/app/venv/bin/python portal.py
Restart=always
RestartSec=3
Environment=GRADIO_SERVER_NAME=127.0.0.1
Environment=GRADIO_SERVER_PORT=7863

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable rotation-planner
sudo systemctl start rotation-planner
```

### 7. nginx設定

```bash
sudo tee /etc/nginx/sites-available/rotation-planner << 'EOF'
server {
    listen 80;
    server_name YOUR_DOMAIN_OR_IP;

    location / {
        proxy_pass http://127.0.0.1:7863;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 86400;
    }
}
EOF

sudo ln -sf /etc/nginx/sites-available/rotation-planner /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl restart nginx
```

### 8. HTTPS化（推奨）

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d YOUR_DOMAIN
```

</details>

## 運用コマンド

```bash
# サービス状態確認
sudo systemctl status rotation-planner

# ログ確認
sudo journalctl -u rotation-planner -f

# 再起動
sudo systemctl restart rotation-planner

# コード更新（デプロイスクリプト使用）
sudo ./deploy_demo.sh
```

## ファイル構成

```
rotation-planner/
├── portal.py                          # 統合ポータル（メインエントリポイント）
├── admin_ui.py                        # 管理機能UI
├── pesticide_master_ui.py             # 防除マスタ管理UI
├── db_schema.sql                      # DBスキーマ定義（12テーブル）
├── requirements.txt                   # 依存ライブラリ
├── SECURITY_AUDIT.md                  # セキュリティ監査レポート
├── pesticide_master.csv               # 防除マスタ初期データ
├── サンプルほ場.csv                     # ほ場登録サンプルデータ
├── ほ場テンプレート.csv                  # CSVインポート用テンプレート
├── 制約サンプル.csv / 制約テンプレート.csv  # 制約設定テンプレート
├── 在庫テンプレート.csv                  # 在庫インポート用テンプレート
├── 輪作計画テンプレート.csv              # 輪作計画インポート用テンプレート
│
├── rotation_planner/                  # メインパッケージ
│   ├── __init__.py
│   │
│   ├── field/                         # ほ場管理・ポリゴン・集計
│   │   ├── crud.py                    # ほ場CRUD操作
│   │   ├── ui.py                      # ほ場登録UI
│   │   ├── field_list_ui.py           # ほ場一覧UI（マトリックス表示）
│   │   ├── map.py                     # Leaflet.js地図統合
│   │   ├── kml_parser.py             # KML/KMZパーサー（Google Earth連携）
│   │   ├── fude_polygon.py           # 筆ポリゴン連携（農水省公開データ）
│   │   ├── crop_settings.py          # 作物マスタ管理
│   │   ├── crop_polygon_crud.py      # 作付けポリゴンCRUD
│   │   ├── crop_polygon_ui.py        # 作付けポリゴンUI
│   │   ├── paddy_crud.py             # 水田ポリゴンCRUD
│   │   ├── paddy_ui.py               # 水田ポリゴンUI
│   │   ├── spatial.py                # 空間演算（測地面積計算・隣接判定）
│   │   ├── aggregation.py            # 集計ロジック（作物×地目）
│   │   ├── aggregation_service.py    # 集計サービス（補助金計算）
│   │   └── aggregation_ui.py         # 集計UI（クロス集計表表示）
│   │
│   ├── app/                           # 輪作計画（制約・最適化）
│   │   ├── constraints.py            # 制約定義・パース・テーブル管理
│   │   ├── optimizer.py              # OR-Tools CP-SAT / ヒューリスティック最適化
│   │   ├── ui.py                      # 輪作計画UI
│   │   └── utils.py                   # ヘルパー関数（Field, CSV生成等）
│   │
│   ├── pesticide/                     # 農薬発注
│   │   ├── calculator.py             # 農薬必要量計算
│   │   ├── ui.py                      # 農薬発注UI
│   │   ├── master.py                  # 防除マスタリポジトリ
│   │   ├── rotation.py               # 輪作計画連携
│   │   ├── csv_io.py                 # CSV入出力
│   │   ├── pdf_export.py             # PDF出力（ReportLab）
│   │   └── ja_staff_ui.py            # JA職員向け集約UI
│   │
│   ├── pesticide_record/             # 防除記録
│   │   ├── ui.py                      # 記録入力UI
│   │   ├── export.py                 # CSV/PDFエクスポート
│   │   └── image_analyzer.py         # 農薬ラベル画像解析（OCR）
│   │
│   ├── famic/                         # FAMIC農薬データインポーター
│   │   └── importer.py               # XLS→DB取込（基本部・適用部）
│   │
│   ├── crop_history/                  # 作付履歴
│   │   └── ui.py                      # 作付履歴UI
│   │
│   ├── data_management/              # データ管理
│   │   └── ui.py                      # CSVインポート/エクスポートUI
│   │
│   └── common/                        # 共通モジュール
│       ├── db.py                      # DB接続ユーティリティ
│       ├── db_access.py              # リポジトリパターン（全テーブルのCRUD）
│       ├── auth.py                    # 認証・認可（BCryptハッシュ、RBAC）
│       ├── models.py                  # データモデル（User, Field等）
│       ├── exceptions.py             # カスタム例外クラス（11種）
│       ├── handlers.py               # エラーハンドラー
│       ├── validation.py             # 入力バリデーション
│       ├── export.py                 # CSV/PDFエクスポート共通
│       ├── file_utils.py             # ファイル操作ユーティリティ
│       ├── ui_utils.py               # UIフォーマットヘルパー
│       └── year_utils.py             # 和暦（令和）⇔西暦変換
│
├── tests/                             # テストスイート（32ファイル）
│   ├── conftest.py                    # Pytest設定・フィクスチャ
│   ├── test_optimizer_unit.py         # 最適化ロジック
│   ├── test_constraints_unit.py       # 制約パース
│   ├── test_optimizer_adjacency.py    # 隣接筆制約
│   ├── test_field_crud_unit.py        # ほ場CRUD
│   ├── test_kml_parser_unit.py        # KMLパーサー
│   ├── test_spatial_unit.py           # 空間演算
│   ├── test_aggregation_unit.py       # 集計ロジック
│   ├── test_aggregation_service_unit.py # 集計サービス
│   ├── test_calculator_unit.py        # 農薬計算
│   ├── test_csv_io_unit.py            # CSV入出力
│   ├── test_csv_validation.py         # CSVバリデーション
│   ├── test_validation_unit.py        # 入力バリデーション
│   ├── test_map_unit.py               # 地図機能
│   ├── test_ui_utils_unit.py          # UIユーティリティ
│   ├── test_auth.py                   # 認証
│   ├── test_auth_extended.py          # 認証（拡張）
│   ├── test_security.py              # セキュリティ（SQLi, XSS防止）
│   ├── test_db_access.py             # DB操作
│   ├── test_field_repository.py       # ほ場リポジトリ
│   ├── test_crop_history_repository.py # 作付履歴リポジトリ
│   ├── test_plan_repository.py        # 輪作計画リポジトリ
│   ├── test_user_repository.py        # ユーザーリポジトリ
│   ├── test_user_crop_repository.py   # ユーザー作物リポジトリ
│   ├── test_user_constraints_repository.py # ユーザー制約リポジトリ
│   ├── test_pesticide_master_repository.py # 防除マスタリポジトリ
│   ├── test_polygon_repository_unit.py # ポリゴンリポジトリ
│   ├── test_pesticide_order.py        # 農薬発注ワークフロー
│   ├── test_pesticide_record.py       # 防除記録ワークフロー
│   ├── test_ja_staff.py              # JA職員機能
│   ├── test_export.py                # エクスポート機能
│   ├── test_adjacency.py             # 隣接判定
│   └── test_crop_family.py           # 作物科分類
│
├── scripts/                           # ユーティリティスクリプト
│   ├── install.sh                    # ワンライナーインストーラー
│   ├── backup_db.py                  # DBバックアップ
│   ├── sync_users_to_db.py           # ユーザー同期
│   ├── migrate_crop_family.sql       # マイグレーション: 作物科
│   ├── migrate_crop_schema.sql       # マイグレーション: 作物スキーマ
│   ├── migrate_field_polygons.sql    # マイグレーション: ほ場ポリゴン
│   ├── migrate_order_templates.sql   # マイグレーション: 発注テンプレート
│   ├── migrate_pesticide_orders.sql  # マイグレーション: 農薬発注
│   ├── migrate_pesticide_record.sql  # マイグレーション: 防除記録
│   └── drop_crop_constraints.sql     # マイグレーション: 制約テーブル削除
│
├── docs/                              # ドキュメント
│   ├── manuals/                      # ユーザーマニュアル
│   │   ├── farmer_manual.md          # 農家向けマニュアル
│   │   └── ja_staff_manual.md        # JA職員向けマニュアル
│   ├── ERROR_HANDLING_DESIGN.md      # エラー処理設計
│   ├── TEST_DESIGN.md                # テスト設計
│   ├── TEST_UNIT.md                  # ユニットテスト一覧
│   ├── TEST_INTEGRATION.md           # 統合テスト
│   ├── TEST_EDGE_CI.md               # エッジケース・CI
│   ├── MIGRATION_STATUS.md           # マイグレーション状況
│   ├── ERROR_ANALYSIS.md             # エラー分析
│   ├── ERROR_DB_VALIDATION.md        # DBバリデーション
│   └── ERROR_FILE_UI.md              # ファイル・UIエラー
│
└── data/                              # データディレクトリ
    ├── rotation_planner.db           # SQLiteデータベース
    ├── settings.json                 # システム設定
    └── fude_cache/                   # 筆ポリゴンキャッシュ
```

## データベーステーブル

SQLiteデータベースに12テーブルを定義（`db_schema.sql`）。

| # | テーブル | 説明 | 主要カラム |
|---|----------|------|-----------|
| 1 | organizations | 組織（JA、個人農家グループ） | name, type(JA/cooperative/individual) |
| 2 | users | ユーザー | username, password_hash, role(farmer/ja_staff/admin), org_id |
| 3 | fields | ほ場 | field_code, district, area_ha, area_a(自動計算), beet_forbidden, coordinates_json |
| 4 | crop_history | 作付履歴 | field_id, year, crop, is_inferred |
| 5 | rotation_plans | 輪作計画 | user_id, name, start_year, end_year, constraints_json |
| 6 | plan_details | 輪作計画詳細 | plan_id, field_id, year, crop |
| 7 | pesticide_masters | 防除マスタ | org_id, crop, pesticide_name, dilution_rate, amount_per_10a |
| 8 | user_constraints | ユーザー輪作制約 | user_id, constraints_json, forbidden_transitions, preferred_transitions, main_crops |
| 9 | order_templates | 発注テンプレート | user_id, name, type(default/history/custom), items_json |
| 10 | inventory | 在庫 | user_id, pesticide_name, amount, unit |
| 11 | paddy_polygons | 水田ポリゴン | field_id, geometry, is_converted, conversion_start_year, source |
| 12 | crop_polygons | 作付けポリゴン | field_id, year, crop_name, geometry, area_ha |

FAMICインポート使用時は追加テーブル（`pesticide_registry`, `pesticide_usage`, `famic_import_log`）が作成される。

## 依存ライブラリ

```
gradio>=4.0.0          # WebアプリUIフレームワーク
pandas>=2.0.0          # データ操作・DataFrameベースのUI表示
numpy>=1.24.0          # 数値計算
ortools>=9.0           # 制約最適化ソルバー（CP-SAT）
shapely>=2.0.0         # 地理空間ジオメトリ演算
pyproj>=3.0.0          # 座標投影（WGS84→平面座標）
requests>=2.28.0       # HTTP通信（筆ポリゴン取得等）
reportlab>=4.0.0       # PDF生成
```

オプション依存:
- `xlrd` — FAMICインポーター使用時（XLSファイル読み込み）

## テスト

```bash
source venv/bin/activate

# 全テスト実行（32ファイル）
pytest tests/ -v

# 特定ファイルのみ
pytest tests/test_optimizer_unit.py -v

# パターンマッチ
pytest tests/ -k "optimizer" -v

# カバレッジ付き
pytest tests/ --cov=rotation_planner --cov-report=term-missing
```

### テスト分類

| 分類 | ファイル数 | 対象 |
|------|----------|------|
| ユニットテスト | 15 | 制約パース、最適化ロジック、農薬計算、空間演算、バリデーション等 |
| リポジトリテスト | 10 | DB操作（ほ場、作付履歴、計画、ユーザー、制約、防除マスタ等） |
| 統合テスト | 4 | 農薬発注ワークフロー、防除記録、JA職員機能、エクスポート |
| セキュリティテスト | 2 | 認証、SQLインジェクション・XSS防止 |
| その他 | 1 | CSV入出力 |

## セキュリティ

本番環境では以下を必ず実施してください：

1. **デバッグモードをOFFにする**（管理 → システム設定）
2. **adminパスワードを変更する**（初期値: admin123）
3. **テストユーザーを削除する**（farmer_demo, ja_staff）
4. **HTTPS化する**（certbot使用）

### セキュリティ対策

- BCryptパスワードハッシュ
- パラメタライズドクエリ（SQLインジェクション防止）
- HTMLエスケープ（XSS防止）
- ロールベースアクセス制御（RBAC）
- Gradio組み込みセッション管理

## ライセンス

MIT License

## データ出典

- 筆ポリゴン: 農林水産省「筆ポリゴンデータ」（https://open.fude.maff.go.jp/）
- 農薬登録情報: 農薬検査所（FAMIC）（https://www.acis.famic.go.jp/ddownload/index.htm）
- 地図: OpenStreetMap contributors
