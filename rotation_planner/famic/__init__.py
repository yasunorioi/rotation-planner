"""
rotation_planner.famic - FAMICデータインポートモジュール

農林水産消費安全技術センター（FAMIC）の農薬登録情報をDBにインポート。

Usage:
    from rotation_planner.famic import import_famic_basic, import_famic_usage

    # 登録基本部をインポート
    count = import_famic_basic("data/famic/登録基本部.xls")

    # 登録適用部をインポート
    count = import_famic_usage("data/famic/登録適用部一.xls")
"""

from .importer import (
    import_famic_basic,
    import_famic_usage,
    get_import_stats,
)

__all__ = [
    "import_famic_basic",
    "import_famic_usage",
    "get_import_stats",
]
