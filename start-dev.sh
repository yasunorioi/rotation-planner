#!/bin/bash
# 開発サーバー起動スクリプト

echo "🌾 農業管理アプリ 開発サーバー起動"
echo "=================================="

# ディレクトリ設定
BASE_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$BASE_DIR"

# 仮想環境アクティベート
source venv/bin/activate

# API サーバー起動（バックグラウンド）
echo "📡 API サーバー起動中 (port 8000)..."
cd api
python main.py &
API_PID=$!
cd ..

sleep 2

# React 開発サーバー起動（バックグラウンド）
echo "⚛️  React 開発サーバー起動中 (port 5173)..."
cd frontend/app
npm run dev &
REACT_PID=$!
cd ../..

echo ""
echo "=================================="
echo "✅ 起動完了"
echo ""
echo "📡 API:   http://localhost:8000"
echo "⚛️  React: http://localhost:5173"
echo ""
echo "終了するには Ctrl+C を押してください"
echo "=================================="

# 終了時のクリーンアップ
cleanup() {
    echo ""
    echo "🛑 サーバー停止中..."
    kill $API_PID 2>/dev/null
    kill $REACT_PID 2>/dev/null
    exit 0
}

trap cleanup SIGINT SIGTERM

# 待機
wait
