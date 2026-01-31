"""
rotation_planner.crop_history - 作付履歴管理モジュール

ほ場×年度のマトリックス形式で作付履歴を表示・編集するUI。

Usage:
    from rotation_planner.crop_history import create_crop_history_ui

    with gr.Tab("📜 作付履歴"):
        components = create_crop_history_ui(user_state)
"""

from .ui import create_crop_history_ui

__all__ = ["create_crop_history_ui"]
