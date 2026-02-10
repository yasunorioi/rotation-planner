"""
APIロギング設定

RotatingFileHandler で logs/api.log に出力 + stderr に WARNING 以上を出力。
"""

import logging
import os
from logging.handlers import RotatingFileHandler


def setup_api_logging() -> None:
    """APIロガーを設定する。lifespan起動時に呼び出す。"""
    log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
    os.makedirs(log_dir, exist_ok=True)

    log_file = os.path.join(log_dir, "api.log")

    # ファイルハンドラ（DEBUG以上、5MB x 5ローテーション）
    file_handler = RotatingFileHandler(
        log_file, maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))

    # stderrハンドラ（WARNING以上）
    stderr_handler = logging.StreamHandler()
    stderr_handler.setLevel(logging.WARNING)
    stderr_handler.setFormatter(logging.Formatter(
        "%(levelname)s %(name)s %(message)s",
    ))

    # rotation_planner名前空間のルートロガーに設定
    api_logger = logging.getLogger("rotation_planner")
    api_logger.setLevel(logging.DEBUG)
    api_logger.addHandler(file_handler)
    api_logger.addHandler(stderr_handler)
