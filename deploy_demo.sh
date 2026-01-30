#!/bin/bash
#
# 輪作計画メーカー デモ版 デプロイスクリプト
# Hugging Face Spaces へのデプロイを自動化
#
# HF_TOKEN は環境変数で設定: export HF_TOKEN=hf_xxxxx
set -e

# =============================================================================
# 設定
# =============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEMO_DIR="${SCRIPT_DIR}/demo"
HF_SPACE_URL="https://huggingface.co/spaces/bbfolf/rotation-planner-demo"
HF_REPO_URL="https://huggingface.co/spaces/bbfolf/rotation-planner-demo"
CLONE_DIR="/tmp/rotation-planner-demo"

# =============================================================================
# ユーティリティ関数
# =============================================================================

print_header() {
    echo ""
    echo "🚀 デモ版デプロイスクリプト"
    echo "================================"
}

print_success() {
    echo "✓ $1"
}

print_error() {
    echo "✗ エラー: $1" >&2
}

print_footer() {
    echo "================================"
    echo "✅ デプロイ完了！"
    echo "🔗 ${HF_SPACE_URL}"
    echo ""
}

# =============================================================================
# 事前チェック
# =============================================================================

check_prerequisites() {
    # HF_TOKEN チェック
    if [ -z "${HF_TOKEN}" ]; then
        print_error "HF_TOKEN が設定されていません"
        echo "設定方法: export HF_TOKEN=hf_xxxxxxxxxxxxx"
        echo "トークン取得: https://huggingface.co/settings/tokens"
        exit 1
    fi
    print_success "HF_TOKEN 確認OK"

    # デモディレクトリ確認
    if [ ! -d "${DEMO_DIR}" ]; then
        print_error "デモディレクトリが見つかりません: ${DEMO_DIR}"
        exit 1
    fi
    print_success "デモディレクトリ確認OK"
}

# =============================================================================
# クリーンアップ
# =============================================================================

cleanup() {
    # __pycache__ 削除
    find "${DEMO_DIR}" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    print_success "__pycache__ 削除完了"

    # .pyc ファイル削除
    find "${DEMO_DIR}" -type f -name "*.pyc" -delete 2>/dev/null || true
    print_success ".pyc ファイル削除完了"
}

# =============================================================================
# Hugging Face Space デプロイ
# =============================================================================

deploy_to_hf() {
    # クローン or プル
    if [ -d "${CLONE_DIR}/.git" ]; then
        print_success "既存リポジトリを更新中..."
        cd "${CLONE_DIR}"
        git pull origin main || git pull origin master || true
    else
        print_success "Hugging Face Space をクローン中..."
        rm -rf "${CLONE_DIR}"
        if [ -n "${HF_TOKEN}" ]; then
            git clone "https://user:${HF_TOKEN}@huggingface.co/spaces/bbfolf/rotation-planner-demo" "${CLONE_DIR}"
        else
            git clone "${HF_REPO_URL}" "${CLONE_DIR}"
        fi
        cd "${CLONE_DIR}"
    fi

    # デモファイルをコピー
    print_success "デモファイルをコピー中..."

    # rotation_demo.py を app.py としてコピー（HF Spaceの規約）
    cp "${DEMO_DIR}/rotation_demo.py" "${CLONE_DIR}/app.py"

    # requirements.txt をコピー
    cp "${DEMO_DIR}/requirements.txt" "${CLONE_DIR}/requirements.txt"

    # README.md を作成（HF Space用）
    cat > "${CLONE_DIR}/README.md" << 'EOF'
---
title: 輪作計画メーカー デモ
emoji: 🌾
colorFrom: green
colorTo: yellow
sdk: gradio
sdk_version: 5.9.1
python_version: "3.12"
app_file: app.py
pinned: false
license: mit
---

# 🌾 輪作計画メーカー デモ版

北海道畑作の輪作計画を自動生成するデモアプリケーションです。

## 対象作物
- てんさい（4年間隔）
- 大豆
- 春小麦
- 秋小麦

## 制約
- 連作禁止
- てんさい→秋小麦: 禁止（作期重複）
- 春小麦→秋小麦: 禁止（病害対策）

## 使い方
1. パラメータを設定
2. 「計画を生成」ボタンをクリック
3. 結果を確認

---
モックデータを使用したデモ版です。実際の農業データは使用していません。
EOF

    # コミット＆プッシュ
    print_success "コミット＆プッシュ中..."
    git add -A

    # 変更がある場合のみコミット
    if git diff --staged --quiet; then
        print_success "変更なし（最新状態）"
    else
        git commit -m "Update rotation planner demo - $(date '+%Y-%m-%d %H:%M:%S')"
        git push origin main || git push origin master
    fi

    cd "${SCRIPT_DIR}"
}

# =============================================================================
# メイン処理
# =============================================================================

main() {
    print_header

    # 事前チェック
    check_prerequisites

    # クリーンアップ
    cleanup

    # デプロイ
    deploy_to_hf

    print_footer
}

# 実行
main "$@"
