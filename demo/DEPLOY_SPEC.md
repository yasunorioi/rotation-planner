# Hugging Face Spaces デプロイ仕様書

## 概要
輪作計画メーカーのデモ版を Hugging Face Spaces にデプロイするための仕様。

## 現在の問題
- HF Spaces で `ImportError: cannot import name 'HfFolder' from 'huggingface_hub'` エラー
- gradio と huggingface_hub のバージョン互換性問題

## ローカル環境（動作確認済み）
```
Python: 3.12.3
gradio: 6.5.0
huggingface_hub: 1.3.4
pandas: 3.0.0
numpy: 2.4.1
```

## HF Spaces 推奨構成

### Option 1: 最新版で統一（推奨）
```txt
# requirements.txt
gradio>=5.0.0
huggingface_hub>=1.0.0
pandas
numpy
```

README.md のヘッダー:
```yaml
---
title: 輪作計画メーカー デモ
emoji: 🌾
colorFrom: green
colorTo: yellow
sdk: gradio
sdk_version: 5.0.0
python_version: "3.12"
app_file: app.py
pinned: false
license: mit
---
```

### Option 2: 安定版（互換性重視）
```txt
# requirements.txt
gradio==4.44.0
huggingface_hub==0.23.0
pandas
numpy
```

README.md のヘッダー:
```yaml
---
title: 輪作計画メーカー デモ
emoji: 🌾
colorFrom: green
colorTo: yellow
sdk: gradio
sdk_version: 4.44.0
python_version: "3.10"
app_file: app.py
pinned: false
license: mit
---
```

## デモアプリ構成

### ファイル一覧
```
demo/
├── app.py              # rotation_demo.py をコピー
├── requirements.txt    # 依存関係
├── README.md           # HF Space メタデータ
└── sample_data/        # （オプション）モックデータ
```

### app.py（rotation_demo.py）の依存
- gradio
- pandas
- numpy
- 標準ライブラリ（random, typing, dataclasses, copy, os）

**注意**: OR-Tools, shapely, pyproj, requests は rotation_demo.py では使用していない

## デモ機能
- 輪作計画の自動生成（ヒューリスティック）
- モックデータ（4ほ場、過去5年分）
- パラメータ調整UI
- 認証なし

## 手動デプロイ手順

1. HF Space を Factory Reboot
   - Settings → Factory reboot

2. requirements.txt を更新
   ```bash
   cd demo
   echo "gradio>=5.0.0" > requirements.txt
   echo "pandas" >> requirements.txt
   echo "numpy" >> requirements.txt
   ```

3. README.md のヘッダーを更新（sdk_version, python_version）

4. git push で反映
   ```bash
   cd /tmp/rotation-planner-demo
   git pull
   cp /path/to/demo/requirements.txt .
   cp /path/to/demo/rotation_demo.py app.py
   # README.md を手動編集
   git add -A
   git commit -m "Update dependencies"
   git push
   ```

5. ビルド完了を待つ（3-5分）

## トラブルシューティング

### HfFolder ImportError
- huggingface_hub のバージョンが gradio と不一致
- 解決: sdk_version と requirements.txt を同期させる

### pyaudioop ModuleNotFoundError
- Python 3.13 で audioop が削除された
- 解決: python_version を 3.11 or 3.12 に指定

### ビルドが終わらない
- Factory Reboot を実行
- 大きいパッケージ（OR-Tools等）を削除

## 参考URL
- HF Spaces: https://huggingface.co/spaces/bbfolf/rotation-planner-demo
- Gradio Docs: https://www.gradio.app/docs
- HF Spaces Config: https://huggingface.co/docs/hub/spaces-config-reference
