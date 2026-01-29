"""
農薬発注アプリ - Gradio Application（複数農家対応版）
輪作計画CSVから年間の農薬必要量を算出
在庫管理機能付き（在庫差し引き発注量計算）
JA職員向け集計機能付き
"""

import gradio as gr
import pandas as pd
import numpy as np
import os
import re
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass

# 認証・DB関連
from auth import authenticate, get_user_info, is_admin_role, get_user_role
from db_access import PesticideMasterRepository, UserRepository, get_db, rows_to_list

os.environ["GRADIO_ANALYTICS_ENABLED"] = "False"

# =============================================================================
# 定数
# =============================================================================

APP_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_MASTER_PATH = os.path.join(APP_DIR, "pesticide_master.csv")

# 単位変換係数（基準単位への変換）
UNIT_CONVERSION = {
    'L': 1000,      # L -> mL
    'l': 1000,
    'mL': 1,        # mL (基準)
    'ml': 1,
    'kg': 1000,     # kg -> g
    'g': 1,         # g (基準)
}

# 散布基準: 10a あたり 100L
SPRAY_VOLUME_PER_10A = 100  # L

# 作物名の正規化マッピング
CROP_NORMALIZE = {
    "てんさい": "てんさい",
    "ビート": "てんさい",
    "甜菜": "てんさい",
    "大豆": "大豆",
    "春小麦": "春小麦",
    "秋小麦": "秋小麦",
    "デントコーン": "デントコーン",
    "コーン": "デントコーン",
    "WCS": "WCS",
    "馬鈴薯": "馬鈴薯",
    "ばれいしょ": "馬鈴薯",
}

# =============================================================================
# データ読み込み
# =============================================================================

def load_pesticide_master_from_db(org_id: int = None) -> pd.DataFrame:
    """防除マスタをDBから読み込み"""
    try:
        rows = PesticideMasterRepository.get_all(org_id)
        if rows:
            return pd.DataFrame(rows)
    except Exception:
        pass

    # DBにデータがない場合はCSVからフォールバック
    return load_pesticide_master_csv()


def load_pesticide_master_csv(master_path: str = None) -> pd.DataFrame:
    """防除マスタCSVを読み込み（フォールバック用）"""
    if master_path is None:
        master_path = DEFAULT_MASTER_PATH

    if not os.path.exists(master_path):
        return pd.DataFrame()

    df = pd.read_csv(master_path, encoding='utf-8')
    return df


def load_inventory_csv(csv_path: str) -> Tuple[Dict[str, Tuple[float, str]], str]:
    """
    在庫CSVを読み込み

    形式: 農薬名,在庫量,単位

    Returns:
        inventory_dict: {農薬名: (在庫量(基準単位), 元の単位)}
        message: 警告メッセージ（エラー時）
    """
    inventory = {}
    warnings = []

    try:
        try:
            df = pd.read_csv(csv_path, encoding='utf-8-sig')
        except:
            df = pd.read_csv(csv_path, encoding='utf-8')

        # 列名を正規化
        df.columns = df.columns.str.strip()

        # 必要な列をチェック
        required_cols = ['農薬名', '在庫量', '単位']
        missing_cols = [c for c in required_cols if c not in df.columns]
        if missing_cols:
            return {}, f"警告: 在庫CSVに必要な列がありません: {', '.join(missing_cols)}"

        for _, row in df.iterrows():
            name = str(row['農薬名']).strip()
            if not name or name == 'nan':
                continue

            try:
                amount = float(row['在庫量'])
            except (ValueError, TypeError):
                warnings.append(f"在庫量が不正: {name}")
                continue

            unit = str(row['単位']).strip()

            # 基準単位（mL または g）に変換
            conversion = UNIT_CONVERSION.get(unit, 1)
            amount_base = amount * conversion

            inventory[name] = (amount_base, unit)

    except Exception as e:
        return {}, f"警告: 在庫CSVの読み込みに失敗しました: {str(e)}"

    warning_msg = ""
    if warnings:
        warning_msg = "在庫CSV警告: " + "; ".join(warnings[:3])
        if len(warnings) > 3:
            warning_msg += f" 他{len(warnings)-3}件"

    return inventory, warning_msg


def convert_to_base_unit(amount: float, unit: str) -> float:
    """指定単位から基準単位（mL or g）に変換"""
    conversion = UNIT_CONVERSION.get(unit, 1)
    return amount * conversion


def convert_from_base_unit(amount_base: float, target_unit: str) -> float:
    """基準単位から指定単位に変換"""
    conversion = UNIT_CONVERSION.get(target_unit, 1)
    return amount_base / conversion


def load_rotation_plan(csv_path: str) -> Tuple[pd.DataFrame, List[str], str]:
    """輪作計画CSVを読み込み、ほ場情報と年列を抽出"""
    try:
        df = pd.read_csv(csv_path, encoding='utf-8-sig')
    except:
        df = pd.read_csv(csv_path, encoding='utf-8')

    # 年列を特定（R + 数字、または 📍R + 数字）
    year_pattern = re.compile(r'^📍?R\d+$')
    year_cols = [c for c in df.columns if year_pattern.match(c)]

    if not year_cols:
        return None, [], "エラー: 年列（R5, R6, ...）が見つかりません"

    # 📍を除去して正規化
    year_cols_clean = [c.replace('📍', '') for c in year_cols]

    return df, year_cols, None


def normalize_crop(crop: str) -> str:
    """作物名を正規化"""
    if pd.isna(crop) or str(crop).strip() == '':
        return ''
    crop_str = str(crop).strip()
    return CROP_NORMALIZE.get(crop_str, crop_str)


# =============================================================================
# 農薬必要量計算
# =============================================================================

def calculate_pesticide_requirements(
    rotation_df: pd.DataFrame,
    year_cols: List[str],
    target_year: str,
    master_df: pd.DataFrame,
    area_unit: str = 'a',
    inventory: Dict[str, Tuple[float, str]] = None
) -> Tuple[pd.DataFrame, pd.DataFrame, str]:
    """
    指定年の農薬必要量を計算

    Args:
        inventory: 在庫データ {農薬名: (在庫量(基準単位), 元の単位)}

    Returns:
        summary_df: 農薬別の必要量サマリ
        detail_df: 月別・農薬別の詳細
        message: 処理メッセージ
    """
    has_inventory = inventory is not None and len(inventory) > 0

    # 対象年の列を特定
    target_col = None
    for col in rotation_df.columns:
        if col.replace('📍', '') == target_year or col == target_year:
            target_col = col
            break

    if target_col is None:
        return None, None, f"エラー: {target_year} が見つかりません"

    # 面積列を特定
    area_col = None
    for col in ['面積(ha)', 'area', '面積']:
        if col in rotation_df.columns:
            area_col = col
            break

    if area_col is None:
        return None, None, "エラー: 面積列が見つかりません"

    # 作物ごとの面積を集計
    crop_areas = {}  # crop -> total_ha

    for _, row in rotation_df.iterrows():
        crop = normalize_crop(row[target_col])
        if not crop:
            continue

        area = row[area_col]
        if pd.isna(area):
            continue

        # 面積を数値化
        area_str = str(area).replace('ha', '').replace('a', '').strip()
        try:
            area_val = float(area_str)
        except:
            continue

        # haに変換
        if area_unit == 'a':
            area_ha = area_val / 100
        else:
            area_ha = area_val

        if crop not in crop_areas:
            crop_areas[crop] = 0
        crop_areas[crop] += area_ha

    if not crop_areas:
        return None, None, "エラー: 作付データがありません"

    # 農薬必要量を計算
    pesticide_totals = {}  # pesticide_name -> {amount, unit, crops, targets}
    monthly_details = []  # [{month, crop, target, pesticide, amount, unit}, ...]

    for crop, area_ha in crop_areas.items():
        # マスタから該当作物の農薬を取得
        crop_master = master_df[master_df['crop'] == crop]

        if crop_master.empty:
            continue

        area_10a = area_ha * 10  # haを10a単位に変換

        for _, prow in crop_master.iterrows():
            pesticide = prow['pesticide_name']
            dilution = prow['dilution_rate']
            amount_per_10a = prow['amount_per_10a']
            unit = prow['unit']
            month = prow['month']
            target = prow['target']

            # 必要量を計算
            if pd.notna(amount_per_10a) and str(amount_per_10a).strip() != '':
                # 直接指定（mL/10a, g/10a など）
                try:
                    # 複数値の場合は最初の値を使用（例: 400+100）
                    amount_str = str(amount_per_10a).split('+')[0].split('/')[0].split('〜')[0]
                    amount = float(amount_str) * area_10a
                    final_unit = str(unit) if pd.notna(unit) else 'mL'
                except:
                    continue
            elif pd.notna(dilution) and str(dilution).strip() != '':
                # 希釈倍率指定 → 100L/10a 基準で計算
                try:
                    dilution_str = str(dilution).split('/')[0].split('〜')[0].replace(',', '')
                    dilution_rate = float(dilution_str)
                    # 100L/10a ÷ 希釈倍率 × 面積(10a)
                    amount = (SPRAY_VOLUME_PER_10A / dilution_rate) * area_10a * 1000  # mL
                    final_unit = 'mL'
                except:
                    continue
            else:
                continue

            # 集計
            if pesticide not in pesticide_totals:
                pesticide_totals[pesticide] = {
                    'amount': 0,
                    'unit': final_unit,
                    'crops': set(),
                    'targets': set()
                }
            pesticide_totals[pesticide]['amount'] += amount
            pesticide_totals[pesticide]['crops'].add(crop)
            if pd.notna(target):
                pesticide_totals[pesticide]['targets'].add(str(target))

            # 月別詳細
            monthly_details.append({
                'month': int(month) if pd.notna(month) else 0,
                'crop': crop,
                'target': target if pd.notna(target) else '',
                'pesticide': pesticide,
                'amount': amount,
                'unit': final_unit,
                'area_ha': area_ha
            })

    if not pesticide_totals:
        return None, None, f"警告: {target_year}の作物に対応する農薬データがありません"

    # サマリDataFrame作成
    summary_rows = []
    for pesticide, data in sorted(pesticide_totals.items()):
        amount = data['amount']  # 基準単位（mL or g）
        unit = data['unit']

        # 単位変換（1000mL以上はL、1000g以上はkg）
        if unit == 'mL' and amount >= 1000:
            amount_disp = amount / 1000
            unit_disp = 'L'
        elif unit == 'g' and amount >= 1000:
            amount_disp = amount / 1000
            unit_disp = 'kg'
        else:
            amount_disp = amount
            unit_disp = unit

        row = {
            '農薬名': pesticide,
            '必要量': f"{amount_disp:.2f}",
        }

        # 在庫・発注量の計算（在庫データがある場合のみ）
        if has_inventory:
            inv_amount_base = 0.0
            inv_unit = unit_disp

            if pesticide in inventory:
                inv_amount_base, inv_unit_orig = inventory[pesticide]
                # 表示用単位に変換
                if unit_disp == 'L':
                    inv_amount_disp = inv_amount_base / 1000  # mL -> L
                elif unit_disp == 'kg':
                    inv_amount_disp = inv_amount_base / 1000  # g -> kg
                else:
                    inv_amount_disp = inv_amount_base
            else:
                inv_amount_disp = 0.0

            # 発注量 = max(0, 必要量 - 在庫)
            order_amount = max(0, amount_disp - inv_amount_disp)

            row['在庫量'] = f"{inv_amount_disp:.2f}"
            row['発注量'] = f"{order_amount:.2f}"

        row['単位'] = unit_disp
        row['対象作物'] = ', '.join(sorted(data['crops']))
        row['対象病害虫'] = ', '.join(sorted(data['targets']))[:50]

        summary_rows.append(row)

    summary_df = pd.DataFrame(summary_rows)

    # 月別詳細DataFrame作成
    detail_df = pd.DataFrame(monthly_details)
    if not detail_df.empty:
        detail_df = detail_df.sort_values(['month', 'crop', 'pesticide'])

        # 表示用に整形
        detail_df['amount_disp'] = detail_df.apply(
            lambda r: f"{r['amount']/1000:.2f}L" if r['unit'] == 'mL' and r['amount'] >= 1000
                     else f"{r['amount']:.1f}{r['unit']}", axis=1
        )
        detail_df = detail_df[['month', 'crop', 'target', 'pesticide', 'amount_disp', 'area_ha']]
        detail_df.columns = ['月', '作物', '対象', '農薬名', '必要量', '面積(ha)']

    # メッセージ
    message = f"✅ {target_year}の農薬発注リスト作成完了\n"
    message += f"・対象作物: {', '.join(f'{c}({a:.2f}ha)' for c, a in sorted(crop_areas.items()))}\n"
    message += f"・農薬品目数: {len(summary_df)}\n"

    return summary_df, detail_df, message


# =============================================================================
# JA職員向け集計機能
# =============================================================================

def get_all_farmers_orders() -> pd.DataFrame:
    """全農家の発注状況を取得（JA職員用）"""
    # 実装: DBから全ユーザーの発注履歴を取得
    # 現時点では空のDataFrameを返す（将来の拡張用）
    return pd.DataFrame(columns=['農家名', '発注日', '農薬名', '数量', '単位', '状態'])


def get_aggregate_pesticide_orders(org_id: int = None) -> pd.DataFrame:
    """組織全体の農薬発注集計（JA職員用）"""
    # 実装: 全農家の発注を農薬ごとに集計
    return pd.DataFrame(columns=['農薬名', '総必要量', '単位', '発注農家数'])


# =============================================================================
# Gradio UI
# =============================================================================

def process_order(csv_file, target_year, area_unit, master_file, inventory_file, user_state):
    """発注処理を実行"""

    if csv_file is None:
        return None, None, None, "エラー: 輪作計画CSVをアップロードしてください"

    user_info = user_state or {}
    org_id = user_info.get('org_id')

    # マスタ読み込み（DB優先、なければCSV）
    if master_file is not None:
        master_df = pd.read_csv(master_file.name, encoding='utf-8')
    else:
        master_df = load_pesticide_master_from_db(org_id)

    if master_df.empty:
        # フォールバック: CSVから読み込み
        master_df = load_pesticide_master_csv()

    if master_df.empty:
        return None, None, None, "エラー: 防除マスタが見つかりません"

    # 在庫CSV読み込み（オプション）
    inventory = None
    inventory_warning = ""
    if inventory_file is not None:
        inventory, inventory_warning = load_inventory_csv(inventory_file.name)

    # 輪作計画読み込み
    rotation_df, year_cols, error = load_rotation_plan(csv_file.name)
    if error:
        return None, None, None, error

    # 計算実行
    summary_df, detail_df, message = calculate_pesticide_requirements(
        rotation_df, year_cols, target_year, master_df, area_unit, inventory
    )

    if summary_df is None:
        return None, None, None, message

    # 在庫警告をメッセージに追加
    if inventory_warning:
        message += f"\n{inventory_warning}"

    if inventory:
        message += f"\n・在庫データ: {len(inventory)}品目読み込み済み"

    # CSV出力
    csv_path = "/tmp/pesticide_order.csv"
    summary_df.to_csv(csv_path, index=False, encoding='utf-8-sig')

    return summary_df, detail_df, csv_path, message


def get_available_years(csv_file):
    """CSVから選択可能な年を取得"""
    if csv_file is None:
        return gr.update(choices=[], value=None)

    try:
        rotation_df, year_cols, error = load_rotation_plan(csv_file.name)
        if error or not year_cols:
            return gr.update(choices=[], value=None)

        # 📍を除去して年リストを作成
        years = [c.replace('📍', '') for c in year_cols]
        return gr.update(choices=years, value=years[-1] if years else None)
    except:
        return gr.update(choices=[], value=None)


def create_app():
    """Gradioアプリを作成"""

    with gr.Blocks(title="農薬発注アプリ") as app:
        # ユーザー状態管理
        user_state = gr.State({})

        # ヘッダー
        with gr.Row():
            gr.Markdown("# 💊 農薬発注アプリ")
            user_display = gr.Markdown("")

        # ユーザー情報取得・表示更新
        def on_load(request: gr.Request):
            if request and request.username:
                user_info = get_user_info(request.username)
                if user_info:
                    role = user_info.get('role', 'farmer')
                    display_name = user_info.get('display_name', request.username)
                    role_label = {'admin': '管理者', 'ja_staff': 'JA職員', 'farmer': '農家'}.get(role, role)

                    # DB からユーザーID取得
                    db_user = UserRepository.get_user_by_username(request.username)
                    user_data = {
                        'username': request.username,
                        'user_id': db_user.get('id') if db_user else None,
                        'role': role,
                        'display_name': display_name,
                        'org_id': db_user.get('org_id') if db_user else None
                    }

                    return (
                        user_data,
                        f"👤 {display_name}（{role_label}）",
                        gr.update(visible=(role in ['admin', 'ja_staff'])),
                        gr.update(visible=(role in ['admin', 'ja_staff']))
                    )
            return {}, "", gr.update(visible=False), gr.update(visible=False)

        gr.Markdown("""
        輪作計画CSVから年間の農薬必要量を算出します。

        ## 使い方
        1. 輪作計画メーカーで作成したCSVをアップロード
        2. 対象年を選択
        3. 「発注リスト作成」ボタンをクリック
        """)

        with gr.Accordion("📥 テンプレートダウンロード", open=False):
            template_path = os.path.join(APP_DIR, 'pesticide_template.csv')
            if os.path.exists(template_path):
                gr.File(value=template_path, label="防除マスタテンプレート（編集して作物・農薬を追加可能）")
            inventory_template_path = os.path.join(APP_DIR, 'inventory_template.csv')
            if os.path.exists(inventory_template_path):
                gr.File(value=inventory_template_path, label="在庫テンプレート")

        # メインコンテンツ
        with gr.Tabs():
            # === 発注計算タブ（全ユーザー共通） ===
            with gr.Tab("📋 発注計算"):
                with gr.Row():
                    with gr.Column(scale=1):
                        csv_input = gr.File(
                            label="輪作計画CSV",
                            file_types=[".csv"]
                        )

                        target_year = gr.Dropdown(
                            label="対象年",
                            choices=[],
                            value=None
                        )

                        area_unit = gr.Radio(
                            choices=["ha", "a"],
                            value="ha",
                            label="面積単位（輪作計画CSVの単位）"
                        )

                        master_input = gr.File(
                            label="防除マスタCSV（オプション：カスタムマスタを使用する場合）",
                            file_types=[".csv"]
                        )

                        inventory_input = gr.File(
                            label="在庫CSV（オプション：在庫を差し引いて発注量を算出）",
                            file_types=[".csv"]
                        )

                        gr.Markdown("""
                        **在庫CSV形式:**
                        ```
                        農薬名,在庫量,単位
                        トップジンM水和剤,5,L
                        ゲッター水和剤,2,kg
                        ```
                        """)

                        submit_btn = gr.Button("発注リスト作成", variant="primary")

                    with gr.Column(scale=2):
                        message_output = gr.Textbox(
                            label="処理結果",
                            lines=5
                        )

                        csv_output = gr.File(
                            label="発注リストCSVダウンロード"
                        )

                gr.Markdown("## 📋 農薬発注リスト（サマリ）")
                summary_table = gr.Dataframe(
                    label="農薬別必要量",
                    headers=["農薬名", "必要量", "単位", "対象作物", "対象病害虫"],
                    wrap=True
                )

                gr.Markdown("## 📅 月別詳細")
                detail_table = gr.Dataframe(
                    label="月別・作物別の農薬使用計画",
                    headers=["月", "作物", "対象", "農薬名", "必要量", "面積(ha)"],
                    wrap=True
                )

            # === JA職員向けタブ ===
            with gr.Tab("🏢 JA集計", visible=False) as ja_tab:
                gr.Markdown("""
                ## 組織内農家の発注集計

                ※ この機能はJA職員・管理者のみ利用可能です。
                """)

                with gr.Row():
                    refresh_btn = gr.Button("集計を更新", variant="secondary")

                gr.Markdown("### 農家別発注状況")
                farmer_orders_table = gr.Dataframe(
                    label="農家別発注一覧",
                    headers=["農家名", "発注日", "農薬名", "数量", "単位", "状態"],
                    wrap=True
                )

                gr.Markdown("### 農薬別集計")
                aggregate_table = gr.Dataframe(
                    label="農薬別集計",
                    headers=["農薬名", "総必要量", "単位", "発注農家数"],
                    wrap=True
                )

                def refresh_ja_data(user_state):
                    """JA集計データを更新"""
                    org_id = user_state.get('org_id') if user_state else None
                    farmer_orders = get_all_farmers_orders()
                    aggregate = get_aggregate_pesticide_orders(org_id)
                    return farmer_orders, aggregate

                refresh_btn.click(
                    fn=refresh_ja_data,
                    inputs=[user_state],
                    outputs=[farmer_orders_table, aggregate_table]
                )

            # === 防除マスタ管理タブ（JA職員向け） ===
            with gr.Tab("📚 防除マスタ", visible=False) as master_tab:
                gr.Markdown("""
                ## 防除マスタ管理

                組織の防除マスタを管理します。
                """)

                def load_master_table(user_state):
                    """防除マスタをロード"""
                    org_id = user_state.get('org_id') if user_state else None
                    df = load_pesticide_master_from_db(org_id)
                    if df.empty:
                        return pd.DataFrame(columns=['crop', 'month', 'target', 'pesticide_name', 'dilution_rate', 'amount_per_10a', 'unit'])
                    return df[['crop', 'month', 'target', 'pesticide_name', 'dilution_rate', 'amount_per_10a', 'unit']]

                master_table = gr.Dataframe(
                    label="防除マスタ一覧",
                    headers=['作物', '月', '対象', '農薬名', '希釈倍率', '10aあたり使用量', '単位'],
                    wrap=True
                )

                load_master_btn = gr.Button("マスタを読み込み")
                load_master_btn.click(
                    fn=load_master_table,
                    inputs=[user_state],
                    outputs=[master_table]
                )

        gr.Markdown("""
        ---
        ## 📝 注意事項

        - 散布基準: **10a あたり 100L** で計算
        - 希釈倍率の農薬は、散布量から逆算して必要量を算出
        - 防除マスタは `pesticide_master.csv` を編集して作物・農薬を追加可能
        - 対応作物: てんさい、大豆、春小麦、秋小麦（デフォルト）
        """)

        # イベント
        csv_input.change(
            fn=get_available_years,
            inputs=[csv_input],
            outputs=[target_year]
        )

        submit_btn.click(
            fn=process_order,
            inputs=[csv_input, target_year, area_unit, master_input, inventory_input, user_state],
            outputs=[summary_table, detail_table, csv_output, message_output]
        )

        # ページロード時にユーザー情報取得
        app.load(
            fn=on_load,
            outputs=[user_state, user_display, ja_tab, master_tab]
        )

    return app


if __name__ == "__main__":
    app = create_app()
    app.launch(server_port=7861, auth=authenticate)
