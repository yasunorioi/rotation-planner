"""
rotation_planner.field.crop_settings - 作物設定UIモジュール

農家が自分の作る作物を設定するUI。
- マスタからの選択（チェックボックス）
- カスタム作物の追加（例: ブロッコリー（2作目））

選択した作物はほ場登録時の作物プルダウンに表示される。

Usage:
    from rotation_planner.field.crop_settings import create_crop_settings_ui

    with gr.Tab("作物設定"):
        create_crop_settings_ui(user_state)
"""

import gradio as gr
import pandas as pd
from typing import Dict, Any, List, Tuple

from rotation_planner.common import CropMasterRepository, UserCropRepository


# =============================================================================
# データ取得
# =============================================================================

def get_all_crops() -> List[Dict[str, Any]]:
    """全作物マスタを取得"""
    return CropMasterRepository.get_all(active_only=True)


def get_user_crop_ids(user_id: int) -> List[int]:
    """ユーザーの選択済み親作物IDを取得"""
    if not user_id:
        return []
    return UserCropRepository.get_user_crop_ids(user_id)


def get_user_crops(user_id: int) -> List[Dict[str, Any]]:
    """ユーザーの選択済み作物を取得"""
    if not user_id:
        return []
    return UserCropRepository.get_user_crops(user_id)


# =============================================================================
# UI操作関数
# =============================================================================

def load_crop_settings(user_state: Dict[str, Any]) -> Tuple[List[str], pd.DataFrame, str]:
    """
    作物設定を読み込む

    Returns:
        (選択済みマスタ作物名リスト, カスタム作物DataFrame, メッセージ)
    """
    user_id = user_state.get("user_id") if user_state else None
    if not user_id:
        return [], pd.DataFrame(columns=["ID", "作物名", "親作物"]), "ログインしてください"

    user_crops = get_user_crops(user_id)

    # マスタ作物（custom_name=NULL）とカスタム作物を分離
    master_crops = []
    custom_crops = []

    for c in user_crops:
        if c.get("custom_name"):
            custom_crops.append({
                "ID": c["id"],
                "作物名": c["name"],
                "親作物": c["parent_name"],
            })
        else:
            master_crops.append(c["name"])

    custom_df = pd.DataFrame(custom_crops) if custom_crops else pd.DataFrame(columns=["ID", "作物名", "親作物"])

    total = len(master_crops) + len(custom_crops)
    if total > 0:
        msg = f"✅ {total}種類の作物が設定されています（マスタ: {len(master_crops)}, カスタム: {len(custom_crops)}）"
    else:
        msg = "作物を選択してください（ほ場登録時に使用します）"

    return master_crops, custom_df, msg


def save_master_crops(selected_crops: List[str], user_state: Dict[str, Any]) -> str:
    """
    マスタ作物の選択を保存

    Args:
        selected_crops: 選択された作物名のリスト
        user_state: ユーザー状態

    Returns:
        メッセージ
    """
    user_id = user_state.get("user_id") if user_state else None
    if not user_id:
        return "エラー: ログインしてください"

    # 作物名からIDに変換
    all_crops = get_all_crops()
    name_to_id = {c["name"]: c["id"] for c in all_crops}

    crop_ids = []
    for name in selected_crops:
        if name in name_to_id:
            crop_ids.append(name_to_id[name])

    # 保存（カスタム作物は削除しない）
    UserCropRepository.set_user_crops(user_id, crop_ids)

    return f"✅ マスタから{len(crop_ids)}種類の作物を設定しました"


def add_custom_crop(
    parent_crop_name: str,
    custom_name: str,
    user_state: Dict[str, Any]
) -> Tuple[pd.DataFrame, str]:
    """
    カスタム作物を追加

    Args:
        parent_crop_name: 親作物名（マスタから選択）
        custom_name: カスタム名（例: ブロッコリー（2作目））
        user_state: ユーザー状態

    Returns:
        (更新後のカスタム作物DataFrame, メッセージ)
    """
    user_id = user_state.get("user_id") if user_state else None
    if not user_id:
        return pd.DataFrame(columns=["ID", "作物名", "親作物"]), "エラー: ログインしてください"

    if not parent_crop_name:
        return _get_custom_crops_df(user_id), "エラー: 親作物を選択してください"

    if not custom_name or not custom_name.strip():
        return _get_custom_crops_df(user_id), "エラー: カスタム名を入力してください"

    custom_name = custom_name.strip()

    # 親作物IDを取得
    all_crops = get_all_crops()
    parent_crop = next((c for c in all_crops if c["name"] == parent_crop_name), None)
    if not parent_crop:
        return _get_custom_crops_df(user_id), f"エラー: 親作物 '{parent_crop_name}' が見つかりません"

    # 追加
    try:
        UserCropRepository.add_user_crop(user_id, parent_crop["id"], custom_name)
        return _get_custom_crops_df(user_id), f"✅ '{custom_name}' を追加しました（親: {parent_crop_name}）"
    except Exception as e:
        return _get_custom_crops_df(user_id), f"エラー: {str(e)}"


def delete_custom_crop(
    selected_rows: List[List],
    user_state: Dict[str, Any]
) -> Tuple[pd.DataFrame, str]:
    """
    カスタム作物を削除

    Args:
        selected_rows: 選択された行
        user_state: ユーザー状態

    Returns:
        (更新後のカスタム作物DataFrame, メッセージ)
    """
    user_id = user_state.get("user_id") if user_state else None
    if not user_id:
        return pd.DataFrame(columns=["ID", "作物名", "親作物"]), "エラー: ログインしてください"

    if not selected_rows or len(selected_rows) == 0:
        return _get_custom_crops_df(user_id), "削除する作物を選択してください"

    deleted = 0
    for row in selected_rows:
        if len(row) >= 1:
            crop_id = row[0]  # ID列
            try:
                UserCropRepository.remove_user_crop(user_id, int(crop_id))
                deleted += 1
            except Exception:
                pass

    return _get_custom_crops_df(user_id), f"✅ {deleted}件のカスタム作物を削除しました"


def _get_custom_crops_df(user_id: int) -> pd.DataFrame:
    """カスタム作物のDataFrameを取得"""
    user_crops = get_user_crops(user_id)
    custom_crops = [
        {"ID": c["id"], "作物名": c["name"], "親作物": c["parent_name"]}
        for c in user_crops if c.get("custom_name")
    ]
    if custom_crops:
        return pd.DataFrame(custom_crops)
    return pd.DataFrame(columns=["ID", "作物名", "親作物"])


# =============================================================================
# UIコンポーネント
# =============================================================================

def create_crop_settings_ui(user_state: gr.State) -> Dict[str, Any]:
    """
    作物設定UIを作成

    Args:
        user_state: ユーザー状態を保持するgr.State

    Returns:
        コンポーネント辞書
    """
    gr.Markdown("""
    ## 🌾 作付作物の設定

    あなたが作付けする作物を設定してください。
    ここで設定した作物が、ほ場登録時の作物プルダウンに表示されます。
    """)

    # ============= マスタ作物の選択 =============
    gr.Markdown("### 📋 マスタから選択")

    all_crops = get_all_crops()
    crop_choices = [c["name"] for c in all_crops]

    crop_checkboxes = gr.CheckboxGroup(
        choices=crop_choices,
        label="作付作物（複数選択可）",
        value=[],
    )

    with gr.Row():
        save_master_btn = gr.Button("💾 マスタ作物を保存", variant="primary")

    # ============= カスタム作物の追加 =============
    gr.Markdown("---")
    gr.Markdown("""
    ### ➕ カスタム作物の追加

    同じ作物でも作期や回数で区別したい場合に使用します。
    例: 「ブロッコリー（2作目）」「キャベツ（春）」
    """)

    with gr.Row():
        parent_crop_dropdown = gr.Dropdown(
            choices=crop_choices,
            label="親作物（防除連携用）",
            value=None,
        )
        custom_name_input = gr.Textbox(
            label="カスタム名",
            placeholder="例: ブロッコリー（2作目）",
        )
        add_custom_btn = gr.Button("➕ 追加")

    # ============= カスタム作物一覧 =============
    gr.Markdown("### 📝 登録済みカスタム作物")

    custom_crops_table = gr.Dataframe(
        value=pd.DataFrame(columns=["ID", "作物名", "親作物"]),
        label="カスタム作物一覧",
        interactive=False,
    )

    with gr.Row():
        delete_custom_btn = gr.Button("🗑️ 選択した作物を削除", variant="stop")
        refresh_btn = gr.Button("🔄 再読込")

    message = gr.Textbox(label="", interactive=False)

    gr.Markdown("""
    ---
    ### 💡 ヒント
    - **マスタ作物**: JAが管理する標準的な作物名。防除マスタと連携します。
    - **カスタム作物**: あなた独自の呼び名。親作物を選ぶことで防除マスタとも連携できます。
    - 野菜の多作体系（2作目、3作目など）はカスタム作物で管理してください。
    """)

    # ============= イベントハンドラ =============

    # マスタ作物保存
    save_master_btn.click(
        fn=save_master_crops,
        inputs=[crop_checkboxes, user_state],
        outputs=[message]
    )

    # カスタム作物追加
    add_custom_btn.click(
        fn=add_custom_crop,
        inputs=[parent_crop_dropdown, custom_name_input, user_state],
        outputs=[custom_crops_table, message]
    )

    # カスタム作物削除（DataFrameから選択）
    # Note: Gradioの制約で、DataFrameの選択行取得は難しいので、
    # 代替として「ID入力して削除」方式も検討

    # 再読込
    def reload_all(user_state_dict):
        return load_crop_settings(user_state_dict)

    refresh_btn.click(
        fn=reload_all,
        inputs=[user_state],
        outputs=[crop_checkboxes, custom_crops_table, message]
    )

    return {
        "crop_checkboxes": crop_checkboxes,
        "custom_crops_table": custom_crops_table,
        "message": message,
        "load_fn": load_crop_settings,
    }


# =============================================================================
# 公開API
# =============================================================================

__all__ = [
    "create_crop_settings_ui",
    "get_all_crops",
    "get_user_crop_ids",
    "get_user_crops",
    "load_crop_settings",
    "save_master_crops",
    "add_custom_crop",
    "delete_custom_crop",
]
