---
title: 輪作計画メーカー
emoji: 🌾
colorFrom: green
colorTo: yellow
sdk: gradio
sdk_version: 5.11.0
python_version: "3.10"
app_file: demo/app.py
pinned: false
license: mit
---

# 農業管理アプリ

北海道畑作農家向けの農業管理アプリ群です。

## アプリ一覧

| アプリ | ファイル | ポート | 説明 |
|--------|----------|--------|------|
| 統合ポータル | portal.py | 7863 | 各アプリへのランチャー画面 |
| 輪作計画メーカー | app.py | 7860 | CSVから将来の輪作計画を自動生成 |
| 農薬発注アプリ | pesticide_order.py | 7861 | 輪作計画から年間の農薬必要量を算出 |
| ほ場登録アプリ | field_register.py | 7862 | 地図上でほ場を登録しCSV出力 |

## 起動方法

```bash
cd /home/yasu/multi-agent-shogun/docs/rotation_planner_ui
source .venv/bin/activate

# 輪作計画メーカー
python app.py  # http://127.0.0.1:7860

# 農薬発注アプリ
python pesticide_order.py  # http://127.0.0.1:7861

# ほ場登録アプリ
python field_register.py  # http://127.0.0.1:7862

# 統合ポータル（全アプリへのランチャー）
python portal.py  # http://127.0.0.1:7863
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
├── portal.py                   # 統合ポータル（ランチャー）
├── app.py                      # 輪作計画メーカー
├── pesticide_order.py          # 農薬発注アプリ
├── field_register.py           # ほ場登録アプリ
├── pesticide_master.csv        # 防除マスタ（使用中）
├── pesticide_template.csv      # 防除マスタテンプレート
├── inventory_template.csv      # 在庫テンプレート
├── template_example.csv        # 輪作計画テンプレート（サンプル付き）
├── template_empty.csv          # 輪作計画テンプレート（空）
├── 作付け履歴_converted.csv    # 変換済み作付データ
├── 202601221419.pdf            # JAマニュアル（参考資料）
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
