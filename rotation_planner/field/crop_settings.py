"""
rotation_planner.field.crop_settings - 作物設定UIモジュール

農家が自分の作る作物をチェックボックスで選択するUI。
選択した作物はほ場登録時の作物プルダウンに表示される。

Usage:
    from rotation_planner.field.crop_settings import create_crop_settings_ui

    with gr.Tab("作物設定"):
        create_crop_settings_ui(user_state)
"""

import gradio as gr
from typing import Dict, Any, List, Tuple

from rotation_planner.common import CropMasterRepository, UserCropRepository


# =============================================================================
# データ取得
# =============================================================================

def get_all_crops() -> List[Dict[str, Any]]:
    """全作物マスタを取得"""
    return CropMasterRepository.get_all(active_only=True)


def get_user_crop_ids(user_id: int) -> List[int]:
    """ユーザーの選択済み作物IDを取得"""
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

def load_crop_settings(user_state: Dict[str, Any]) -> Tuple[List[str], str]:
    """
    作物設定を読み込む

    Returns:
        (選択済み作物名リスト, メッセージ)
    """
    user_id = user_state.get("user_id") if user_state else None
    if not user_id:
        return [], "ログインしてください"

    user_crops = get_user_crops(user_id)
    selected_names = [c["name"] for c in user_crops]

    if selected_names:
        return selected_names, f"✅ {len(selected_names)}種類の作物が設定されています"
    else:
        return [], "作物を選択してください（ほ場登録時に使用します）"


def save_crop_settings(selected_crops: List[str], user_state: Dict[str, Any]) -> str:
    """
    作物設定を保存

    Args:
        selected_crops: 選択された作物名のリスト
        user_state: ユーザー状態

    Returns:
        メッセージ
    """
    user_id = user_state.get("user_id") if user_state else None
    if not user_id:
        return "エラー: ログインしてください"

    if not selected_crops:
        return "⚠️ 少なくとも1つの作物を選択してください"

    # 作物名からIDに変換
    all_crops = get_all_crops()
    name_to_id = {c["name"]: c["id"] for c in all_crops}

    crop_ids = []
    for name in selected_crops:
        if name in name_to_id:
            crop_ids.append(name_to_id[name])

    if not crop_ids:
        return "エラー: 有効な作物が選択されていません"

    # 保存
    UserCropRepository.set_user_crops(user_id, crop_ids)

    return f"✅ {len(crop_ids)}種類の作物を設定しました"


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

    あなたが作付けする作物を選択してください。
    選択した作物は、ほ場登録時の作物プルダウンに表示されます。
    """)

    # 全作物の選択肢を取得
    all_crops = get_all_crops()
    crop_choices = [c["name"] for c in all_crops]

    crop_checkboxes = gr.CheckboxGroup(
        choices=crop_choices,
        label="作付作物（複数選択可）",
        value=[],
    )

    with gr.Row():
        save_btn = gr.Button("💾 保存", variant="primary")
        refresh_btn = gr.Button("🔄 再読込")

    message = gr.Textbox(label="", interactive=False)

    gr.Markdown("""
    ---
    ### 💡 ヒント
    - ここで選択した作物だけが、ほ場登録時の作物選択に表示されます
    - 新しい作物が必要な場合は、JA職員に連絡してください
    """)

    # イベントハンドラ
    save_btn.click(
        fn=save_crop_settings,
        inputs=[crop_checkboxes, user_state],
        outputs=[message]
    )

    refresh_btn.click(
        fn=load_crop_settings,
        inputs=[user_state],
        outputs=[crop_checkboxes, message]
    )

    return {
        "crop_checkboxes": crop_checkboxes,
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
    "save_crop_settings",
]
