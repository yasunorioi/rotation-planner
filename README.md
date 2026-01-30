# 農業管理アプリ

北海道畑作農家向けの農業管理アプリ群です。

## アプリ一覧

| アプリ | ファイル | ポート | 説明 |
|--------|----------|--------|------|
| 統合ポータル | portal.py | 7863 | 各アプリへのランチャー画面 |
| 輪作計画メーカー | app.py | 7860 | CSVから将来の輪作計画を自動生成 |
| 農薬発注アプリ | pesticide_order.py | 7861 | 輪作計画から年間の農薬必要量を算出 |
| ほ場登録アプリ | field_register.py | 7862 | 地図上でほ場を登録しCSV出力 |

## ローカル起動方法

```bash
cd /path/to/rotation_planner_ui
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 統合ポータル（推奨）
python portal.py  # http://127.0.0.1:7863
```

## サーバーデプロイ（VPS）

Debian/Ubuntu VPSへのデプロイ手順。

### 動作確認済み環境

- Debian 12 (bookworm)
- Python 3.11
- メモリ 512MB以上

### 1. 必要パッケージのインストール

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y git python3 python3-pip python3-venv nginx
```

### 2. アプリ用ユーザーとディレクトリ作成

```bash
sudo useradd -m -s /bin/bash webapp
sudo mkdir -p /var/www/rotation-planner
sudo chown webapp:webapp /var/www/rotation-planner
```

### 3. リポジトリをクローン

```bash
# パブリックリポジトリの場合
sudo -u webapp git clone https://github.com/YOUR_USER/rotation-planner.git /var/www/rotation-planner/app

# プライベートリポジトリの場合（Personal Access Token使用）
sudo -u webapp git clone https://YOUR_TOKEN@github.com/YOUR_USER/rotation-planner.git /var/www/rotation-planner/app
```

### 4. Python仮想環境と依存関係

```bash
sudo -u webapp bash -c "cd /var/www/rotation-planner/app && python3 -m venv venv && source venv/bin/activate && pip install gradio pandas numpy ortools requests shapely pyproj"
```

### 5. データベース初期化

```bash
sudo -u webapp bash -c "cd /var/www/rotation-planner/app && source venv/bin/activate && python -c 'from rotation_planner.common import init_db; init_db()'"
```

### 6. 初期ユーザー作成

```bash
# パスワードのハッシュ値を生成
echo -n "YOUR_PASSWORD" | sha256sum

# users.jsonを作成
sudo -u webapp mkdir -p /var/www/rotation-planner/app/data
sudo -u webapp tee /var/www/rotation-planner/app/data/users.json << 'EOF'
{
  "version": "1.0",
  "updated_at": "2026-01-31T00:00:00",
  "users": [
    {
      "username": "admin",
      "password_hash": "ここにsha256ハッシュ値を入れる",
      "role": "admin",
      "farmer_id": null,
      "display_name": "管理者"
    }
  ]
}
EOF
```

### 7. systemdサービス設定

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

### 8. nginx設定

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

### 9. HTTPS化（オプション）

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d YOUR_DOMAIN
```

## 運用コマンド

```bash
# サービス状態確認
sudo systemctl status rotation-planner

# ログ確認
sudo journalctl -u rotation-planner -f

# 再起動
sudo systemctl restart rotation-planner

# コード更新
sudo -u webapp bash -c "cd /var/www/rotation-planner/app && git pull"
sudo systemctl restart rotation-planner
```

## 1. 輪作計画メーカー

### 機能
- 過去4年分の作付データ（CSV）から将来N年の輪作計画を自動生成
- OR-Tools CP-SATソルバーによる最適化
- ボトルネック分析（感度分析）機能

### 入力CSV形式
| 列名 | 説明 |
|------|------|
| ほ場ID | ほ場の識別子（必須） |
| 地区 | 地区名（任意） |
| ほ場名 | ほ場の名前（任意） |
| area | 面積（単位はUIで選択: a または ha） |
| beet_forbidden | 馬鈴薯・てんさい禁止（0=許可, 1=禁止） |
| R5, R6, ... | 過去の作付（年列はR+数字の形式） |

### 制約設定
- `cap_ha`: 年間面積上限（空欄or0=無制限）
- `min_ha`: 年間面積下限（空欄or0=下限なし）
- `min_gap_years`: 最小作付間隔（年）
- `min_fields`: 最小ほ場数
- `max_fields`: 最大ほ場数（空欄or0=無制限）

### 固定の禁止遷移
- てんさい→秋小麦 禁止（作期重複）
- 春小麦→秋小麦 禁止（病害対策）
- 同一作物の連作禁止

## 2. 農薬発注アプリ

### 機能
- 輪作計画CSVから対象年の作付を読み取り
- 防除マスタに基づいて年間の農薬必要量を算出
- 月別詳細スケジュール表示

### 散布基準
- 10a あたり 100L で計算
- 希釈倍率の農薬は散布量から逆算

### 対応作物（デフォルト）
- てんさい（甜菜直播）
- 大豆
- 春小麦（春播き小麦）
- 秋小麦（秋播き小麦）

### 防除マスタ
`pesticide_master.csv` を編集して作物・農薬を追加可能

## 3. ほ場登録アプリ

### 機能
- OpenStreetMap + Leaflet.jsによる地図表示
- ポリゴン描画によるほ場の境界登録
- WGS84楕円体による正確な面積計算
- Nominatim APIによる住所・地名検索
- 輪作計画メーカー形式でのCSV出力

### 使い方
1. 住所または地名を入力して検索（例: 札幌市、十勝、美瑛町）
2. 地図上で多角形ツールをクリック
3. ほ場の境界をクリックしてポリゴンを描画
4. ほ場ID、地区、ほ場名を入力して登録
5. CSVダウンロードで輪作計画メーカーに読み込み可能

### 出力CSV形式
| 列名 | 説明 |
|------|------|
| ほ場ID | ほ場の識別子 |
| 地区 | 地区名 |
| ほ場名 | ほ場の名前 |
| area | 面積（アール単位） |
| beet_forbidden | 馬鈴薯・てんさい禁止（0=許可, 1=禁止） |

## ファイル構成

```
rotation_planner_ui/
├── portal.py                   # 統合ポータル（メインエントリポイント）
├── app.py                      # 輪作計画メーカー
├── pesticide_order.py          # 農薬発注アプリ
├── field_register.py           # ほ場登録アプリ
├── auth.py                     # 認証モジュール
├── db_access.py                # データベースアクセス
├── db_schema.sql               # DBスキーマ定義
├── rotation_planner/           # リファクタリング済みパッケージ
│   ├── field/                  # ほ場登録関連
│   ├── app/                    # 輪作計画関連
│   ├── pesticide/              # 農薬発注関連
│   └── common/                 # 共通モジュール
├── data/                       # データディレクトリ
│   └── users.json              # ユーザーマスタ
├── pesticide_master.csv        # 防除マスタ
├── requirements.txt            # 依存ライブラリ
└── README.md                   # このファイル
```

## 依存ライブラリ

```
gradio
pandas
numpy
ortools
shapely
pyproj
requests
```

## ライセンス

MIT License
