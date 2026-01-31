# 農業管理アプリ

北海道畑作農家向けの統合農業管理アプリです。

## 主な機能

| 機能 | 説明 |
|------|------|
| 🌱 作物設定 | 作付する作物を選択・カスタム作物追加 |
| 🗺️ ほ場登録 | 地図上でほ場を登録（筆ポリゴン対応） |
| 📜 作付履歴 | 過去の作付け履歴を管理・連作警告 |
| 🌾 輪作計画 | OR-Toolsによる最適な輪作計画自動生成 |
| 💊 農薬発注 | 輪作計画から年間の農薬必要量を算出・PDF出力 |
| 📥 データ管理 | CSV一括インポート/エクスポート |

## クイックスタート

### ローカル起動

```bash
cd rotation_planner_ui
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 起動
python portal.py
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
| ja_staff | 全機能 + 農家一覧 + 防除マスタ管理 |
| farmer | 基本機能（作物設定〜農薬発注） |

## 機能詳細

### 🌱 作物設定

- マスタから作付する作物を選択
- カスタム作物の追加（例: ブロッコリー（2作目））
- 選択した作物がほ場登録や輪作計画で使用可能に
- **自動保存**: チェックボックス変更時に即座にDB保存

### 🗺️ ほ場登録

- OpenStreetMap + Leaflet.jsによる地図表示
- ポリゴン描画によるほ場境界登録
- 筆ポリゴン（農水省公開データ）からの自動取り込み
- WGS84楕円体による正確な面積計算
- KML/KMZエクスポート対応

### 📜 作付履歴

- ほ場×年度のマトリックス形式で表示・編集
- 連作障害の自動警告（てんさい4年、馬鈴薯4年など）
- ログイン時に全ほ場を自動ロード
- CSV一括インポート/エクスポート

### 🌾 輪作計画

- OR-Tools CP-SATソルバーによる最適化
- 作物ごとの制約設定（面積上限/下限、作付間隔、ほ場数制限）
- 禁止遷移・優先遷移の設定
- 計画のDB保存・読み込み

#### 固定の禁止遷移
- てんさい→秋小麦（作期重複）
- 春小麦→秋小麦（病害対策）
- 同一作物の連作禁止

### 💊 農薬発注

- 輪作計画から対象年の農薬必要量を自動計算
- 月別詳細スケジュール表示
- **DB保存**: 発注リストを名前を付けて保存
- **PDF出力**: 印刷用フォーマットでダウンロード
- **保存済み一覧**: 過去の発注リストを読み込み/削除

### 📥 データ管理

- ほ場データのCSVインポート/エクスポート
- 輪作計画のCSVインポート/エクスポート
- バリデーション機能（空欄チェック、未登録作物チェック）

### ⚙️ 管理（admin専用）

- ユーザー管理（追加/削除/パスワードリセット/ロール変更）
- システム情報表示
- データバックアップ
- 筆ポリゴンアップロード
- **デバッグモード切り替え**

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
sudo -u webapp git clone https://github.com/YOUR_USER/rotation-planner.git /var/www/rotation-planner/app
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
sudo ./deploy_rotation_planner.sh
```

## ファイル構成

```
rotation_planner_ui/
├── portal.py                   # 統合ポータル（メインエントリポイント）
├── admin_ui.py                 # 管理機能UI
├── auth.py                     # 認証モジュール
├── rotation_planner/           # メインパッケージ
│   ├── field/                  # ほ場登録・作物設定
│   ├── app/                    # 輪作計画（制約・最適化）
│   ├── pesticide/              # 農薬発注・PDF出力
│   ├── crop_history/           # 作付履歴
│   ├── data_management/        # CSVインポート/エクスポート
│   └── common/                 # 共通モジュール（DB・認証・ユーティリティ）
├── data/                       # データディレクトリ
│   ├── rotation_planner.db     # SQLiteデータベース（ユーザー情報含む）
│   ├── settings.json           # システム設定
│   └── fude_cache/             # 筆ポリゴンキャッシュ
├── scripts/                    # マイグレーションスクリプト
├── tests/                      # 自動テスト
├── pesticide_master.csv        # 防除マスタ
├── requirements.txt            # 依存ライブラリ
└── README.md                   # このファイル
```

## データベーステーブル

| テーブル | 説明 |
|----------|------|
| users | ユーザー情報 |
| organizations | 組織（JA等） |
| fields | ほ場情報 |
| crop_history | 作付履歴 |
| rotation_plans | 輪作計画 |
| plan_details | 輪作計画詳細 |
| pesticide_orders | 農薬発注リスト |
| pesticide_masters | 防除マスタ |
| crop_master | 作物マスタ |
| user_crops | ユーザー作物設定 |
| inventory | 在庫情報 |

## 依存ライブラリ

```
gradio>=4.0.0
pandas
numpy
ortools
shapely
pyproj
requests
reportlab
```

## テスト

```bash
source venv/bin/activate
pytest tests/ -v
```

## セキュリティ注意事項

本番環境では以下を必ず実施してください：

1. **デバッグモードをOFFにする**（管理 → システム設定）
2. **adminパスワードを変更する**（初期値: admin123）
3. **テストユーザーを削除する**（farmer_demo, ja_staff）
4. **HTTPS化する**（certbot使用）

## ライセンス

MIT License

## データ出典

- 筆ポリゴン: 農林水産省「筆ポリゴンデータ」
- 地図: OpenStreetMap contributors
