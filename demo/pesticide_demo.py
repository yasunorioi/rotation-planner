"""
農薬発注デモ - 認証なし・サンプルデータ版

農薬必要量計算のデモンストレーション用モジュール。
DB接続なし、在庫管理なし、発注機能なし（計算結果表示のみ）。

Usage:
    from demo.pesticide_demo import create_pesticide_demo_ui
    demo = create_pesticide_demo_ui()
    demo.launch()

または直接起動:
    python -m demo.pesticide_demo
"""

import gradio as gr
import pandas as pd
from typing import Tuple, Optional
import io


# =============================================================================
# 定数
# =============================================================================

# 散布基準: 10a あたり 100L
SPRAY_VOLUME_PER_10A = 100  # L


# =============================================================================
# サンプル防除マスタデータ
# =============================================================================

SAMPLE_PESTICIDE_MASTER = """crop,month,target,pesticide_name,dilution_rate,amount_per_10a,unit
てんさい,4,苗立枯病,トップジンM水和剤,1000,,mL
てんさい,5,褐斑病,ポリオキシンAL水和剤,2000,,mL
てんさい,6,根腐病,ベンレート水和剤,1000,,mL
てんさい,7,アブラムシ類,モスピラン水溶剤,4000,,mL
大豆,5,アブラムシ類,スミチオン乳剤,1000,,mL
大豆,6,紫斑病,トップジンM水和剤,1000,,mL
大豆,7,カメムシ類,スタークル粒剤,,30,g
春小麦,4,赤かび病,トリフミン水和剤,2000,,mL
春小麦,5,うどんこ病,パンチョTF顆粒水和剤,3000,,mL
秋小麦,5,赤さび病,アミスター20フロアブル,2000,,mL
秋小麦,6,赤かび病,シルバキュアフロアブル,2000,,mL
"""


# =============================================================================
# サンプル輪作計画データ
# =============================================================================

SAMPLE_ROTATION_PLAN = """ほ場ID,地区,ほ場名,面積(ha),R5,R6,R7,R8
F001,北地区,北1号,5.2,てんさい,大豆,春小麦,てんさい
F002,北地区,北2号,3.8,大豆,春小麦,てんさい,大豆
F003,南地区,南1号,4.5,春小麦,てんさい,大豆,春小麦
F004,南地区,南2号,6.1,秋小麦,大豆,てんさい,秋小麦
F005,東地区,東1号,2.9,てんさい,春小麦,大豆,てんさい
"""


# =============================================================================
# 作物名正規化
# =============================================================================

CROP_NORMALIZE = {
    "てんさい": "てんさい",
    "ビート": "てんさい",
    "甜菜": "てんさい",
    "大豆": "大豆",
    "春小麦": "春小麦",
    "秋小麦": "秋小麦",
}


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
    target_year: str,
    master_df: pd.DataFrame,
    area_unit: str = 'ha'
) -> Tuple[Optional[pd.DataFrame], Optional[pd.DataFrame], str]:
    """
    指定年の農薬必要量を計算

    Args:
        rotation_df: 輪作計画DataFrame
        target_year: 対象年（R5, R6, ...）
        master_df: 防除マスタDataFrame
        area_unit: 面積単位（'ha' or 'a'）

    Returns:
        summary_df: 農薬別の必要量サマリ
        detail_df: 月別・農薬別の詳細
        message: 処理メッセージ
    """
    # 対象年の列を特定
    target_col = None
    for col in rotation_df.columns:
        if col == target_year or col.replace('📍', '') == target_year:
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
                    # 100L/10a ÷ 希釈倍率 × 面積(10a) × 1000(mL)
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
            '単位': unit_disp,
            '対象作物': ', '.join(sorted(data['crops'])),
            '対象病害虫': ', '.join(sorted(data['targets']))[:50]
        }
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
    message = f"計算完了: {target_year}の農薬必要量\n"
    message += f"対象作物: {', '.join(f'{c}({a:.2f}ha)' for c, a in sorted(crop_areas.items()))}\n"
    message += f"農薬品目数: {len(summary_df)}"

    return summary_df, detail_df, message


# =============================================================================
# データ読み込み
# =============================================================================

def load_sample_master() -> pd.DataFrame:
    """サンプル防除マスタを読み込み"""
    return pd.read_csv(io.StringIO(SAMPLE_PESTICIDE_MASTER))


def load_sample_rotation() -> pd.DataFrame:
    """サンプル輪作計画を読み込み"""
    return pd.read_csv(io.StringIO(SAMPLE_ROTATION_PLAN))


def get_available_years(df: pd.DataFrame) -> list:
    """利用可能な年を取得"""
    year_cols = [c for c in df.columns if c.startswith('R') and c[1:].isdigit()]
    return year_cols


# =============================================================================
# Gradio UIコンポーネント
# =============================================================================

def create_pesticide_demo_ui() -> gr.Blocks:
    """
    農薬発注デモUIを作成

    Returns:
        gr.Blocks: Gradioアプリケーション
    """

    # サンプルデータをロード
    sample_master_df = load_sample_master()
    sample_rotation_df = load_sample_rotation()
    available_years = get_available_years(sample_rotation_df)

    def process_calculation(
        use_sample: bool,
        csv_file,
        target_year: str,
        area_unit: str
    ) -> Tuple[Optional[pd.DataFrame], Optional[pd.DataFrame], str]:
        """計算処理"""

        # マスタは常にサンプルを使用
        master_df = sample_master_df

        # 輪作計画
        if use_sample or csv_file is None:
            rotation_df = sample_rotation_df
        else:
            try:
                try:
                    rotation_df = pd.read_csv(csv_file.name, encoding='utf-8-sig')
                except:
                    rotation_df = pd.read_csv(csv_file.name, encoding='utf-8')
            except Exception as e:
                return None, None, f"エラー: CSVの読み込みに失敗しました - {str(e)}"

        # 利用可能な年を確認
        years = get_available_years(rotation_df)
        if not years:
            return None, None, "エラー: 年列（R5, R6, ...）が見つかりません"

        if target_year not in years:
            return None, None, f"エラー: {target_year} が見つかりません。利用可能: {', '.join(years)}"

        # 計算実行
        return calculate_pesticide_requirements(rotation_df, target_year, master_df, area_unit)

    def update_years(use_sample: bool, csv_file):
        """年の選択肢を更新"""
        if use_sample or csv_file is None:
            years = available_years
        else:
            try:
                try:
                    df = pd.read_csv(csv_file.name, encoding='utf-8-sig')
                except:
                    df = pd.read_csv(csv_file.name, encoding='utf-8')
                years = get_available_years(df)
            except:
                years = available_years

        return gr.update(choices=years, value=years[0] if years else None)

    # UIの構築
    with gr.Blocks(
        title="農薬発注デモ",
        theme=gr.themes.Soft(),
        css=".gradio-container { max-width: 1200px; margin: auto; }"
    ) as demo:

        gr.Markdown("""
        # 農薬発注計算デモ

        輪作計画から年間の農薬必要量を算出します。

        **注意**: これはデモ版です。認証なし・サンプルデータで動作します。
        """)

        with gr.Row():
            with gr.Column(scale=1):
                gr.Markdown("## 入力")

                use_sample = gr.Checkbox(
                    label="サンプル輪作計画を使用",
                    value=True
                )

                csv_input = gr.File(
                    label="輪作計画CSV（オプション）",
                    file_types=[".csv"],
                    visible=False
                )

                target_year = gr.Dropdown(
                    label="対象年",
                    choices=available_years,
                    value=available_years[0] if available_years else None
                )

                area_unit = gr.Radio(
                    choices=["ha", "a"],
                    value="ha",
                    label="面積単位"
                )

                submit_btn = gr.Button("計算実行", variant="primary")

            with gr.Column(scale=2):
                gr.Markdown("## 計算結果")

                message_output = gr.Textbox(
                    label="処理結果",
                    lines=3,
                    interactive=False
                )

                gr.Markdown("### 農薬別必要量")
                summary_table = gr.Dataframe(
                    label="サマリ",
                    headers=["農薬名", "必要量", "単位", "対象作物", "対象病害虫"],
                    wrap=True
                )

                gr.Markdown("### 月別詳細")
                detail_table = gr.Dataframe(
                    label="月別詳細",
                    headers=["月", "作物", "対象", "農薬名", "必要量", "面積(ha)"],
                    wrap=True
                )

        # サンプルデータ表示
        with gr.Accordion("サンプルデータを表示", open=False):
            gr.Markdown("### サンプル輪作計画")
            gr.Dataframe(
                value=sample_rotation_df,
                label="輪作計画",
                wrap=True
            )

            gr.Markdown("### サンプル防除マスタ")
            gr.Dataframe(
                value=sample_master_df,
                label="防除マスタ",
                wrap=True
            )

        gr.Markdown("""
        ---
        ## 計算ロジック

        - **散布基準**: 10a あたり 100L
        - **希釈倍率指定**: 必要量 = (100L ÷ 希釈倍率) × 面積(10a) × 1000
        - **直接指定**: 必要量 = 10aあたり使用量 × 面積(10a)

        ### 対応作物
        てんさい、大豆、春小麦、秋小麦（サンプルマスタ）
        """)

        # イベント接続
        use_sample.change(
            fn=lambda x: gr.update(visible=not x),
            inputs=[use_sample],
            outputs=[csv_input]
        )

        use_sample.change(
            fn=update_years,
            inputs=[use_sample, csv_input],
            outputs=[target_year]
        )

        csv_input.change(
            fn=update_years,
            inputs=[use_sample, csv_input],
            outputs=[target_year]
        )

        submit_btn.click(
            fn=process_calculation,
            inputs=[use_sample, csv_input, target_year, area_unit],
            outputs=[summary_table, detail_table, message_output]
        )

    return demo


# =============================================================================
# メイン
# =============================================================================

if __name__ == "__main__":
    demo = create_pesticide_demo_ui()
    demo.launch(
        server_name="0.0.0.0",
        server_port=7870,
        share=False
    )
