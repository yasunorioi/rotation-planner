#!/bin/bash
# rotation-planner インストールスクリプト
# 使い方: curl -sL https://raw.githubusercontent.com/yasunorioi/rotation-planner/main/scripts/install.sh | sudo bash

set -e

APP_DIR="/var/www/rotation-planner"
APP_USER="webapp"
REPO_URL="https://github.com/yasunorioi/rotation-planner.git"

echo "=============================================="
echo "  rotation-planner インストーラー"
echo "=============================================="
echo ""

# root権限チェック
if [ "$EUID" -ne 0 ]; then
    echo "エラー: root権限で実行してください（sudo bash）"
    exit 1
fi

# 1. 必要パッケージ
echo "[1/7] 必要パッケージをインストール中..."
apt update -qq
apt install -y -qq git python3 python3-pip python3-venv nginx sqlite3 > /dev/null

# 2. アプリユーザー作成
echo "[2/7] アプリユーザーを作成中..."
if ! id "$APP_USER" &>/dev/null; then
    useradd -m -s /bin/bash "$APP_USER"
fi

# 3. ディレクトリ作成
echo "[3/7] ディレクトリを作成中..."
mkdir -p "$APP_DIR"
chown "$APP_USER:$APP_USER" "$APP_DIR"

# 4. リポジトリクローン
echo "[4/7] リポジトリをクローン中..."
if [ -d "$APP_DIR/app/.git" ]; then
    sudo -u "$APP_USER" git -C "$APP_DIR/app" pull origin main
else
    sudo -u "$APP_USER" git clone "$REPO_URL" "$APP_DIR/app"
fi

# 5. Python環境構築
echo "[5/7] Python環境を構築中..."
sudo -u "$APP_USER" bash -c "cd $APP_DIR/app && python3 -m venv venv && source venv/bin/activate && pip install -q -r requirements.txt"

# 6. DB初期化
echo "[6/7] データベースを初期化中..."
sudo -u "$APP_USER" bash -c "cd $APP_DIR/app && source venv/bin/activate && python -c 'from rotation_planner.common import init_db; init_db()'" 2>/dev/null || true

# 7. systemdサービス設定
echo "[7/7] サービスを設定中..."
cat > /etc/systemd/system/rotation-planner.service << 'EOF'
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

systemctl daemon-reload
systemctl enable rotation-planner
systemctl restart rotation-planner

# nginx設定
cat > /etc/nginx/sites-available/rotation-planner << 'EOF'
server {
    listen 80;
    server_name _;

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

ln -sf /etc/nginx/sites-available/rotation-planner /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl restart nginx

echo ""
echo "=============================================="
echo "  インストール完了！"
echo "=============================================="
echo ""
echo "アクセス URL: http://$(hostname -I | awk '{print $1}')"
echo ""
echo "初期ユーザー:"
echo "  admin / admin123 (管理者)"
echo "  farmer_demo / demo123 (農家デモ)"
echo ""
echo "⚠️  本番運用前に必ず初期パスワードを変更してください"
echo ""
