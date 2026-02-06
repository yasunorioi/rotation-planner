"""
pesticide/csv_io.py 単体テスト（CI-01 ~ CI-05）

対象: rotation_planner/pesticide/csv_io.py
テストID: CI-01 ~ CI-05
"""

import pytest
import os
import sys
import tempfile
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rotation_planner.pesticide.csv_io import (
    export_order_csv,
    import_order_csv,
    merge_with_calculated,
)


# =============================================================================
# TestExportOrderCsv（CI-01 ~ CI-02）
# =============================================================================

class TestExportOrderCsv:
    """export_order_csv のテスト"""

    def test_ci01_normal_export(self):
        """CI-01: 正常出力 → (filename, csv_bytes)"""
        summary_data = [
            {"農薬名": "トップジンM水和剤", "必要量": 5.0, "単位": "L", "対象作物": "てんさい"},
            {"農薬名": "スミチオン乳剤", "必要量": 3.5, "単位": "L", "対象作物": "大豆"},
        ]

        filename, csv_bytes = export_order_csv(summary_data, year="R8")

        # filenameの形式
        assert filename == "pesticide_order_R8.csv"

        # csv_bytesが非空のbytes
        assert isinstance(csv_bytes, bytes)
        assert len(csv_bytes) > 0

        # CSVとして読み込めること
        csv_text = csv_bytes.decode("utf-8-sig")
        assert "農薬名" in csv_text
        assert "トップジンM水和剤" in csv_text
        assert "スミチオン乳剤" in csv_text

    def test_ci01_export_to_file(self):
        """CI-01b: ファイル出力 → ファイルが作成される"""
        summary_data = [
            {"農薬名": "ダコニール1000", "必要量": 2.0, "単位": "L", "対象作物": "春小麦"},
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "test_export.csv")
            filename, csv_bytes = export_order_csv(summary_data, year="R9", output_path=output_path)

            assert os.path.exists(output_path)
            assert os.path.getsize(output_path) > 0
            assert filename == "pesticide_order_R9.csv"

    def test_ci02_empty_data(self):
        """CI-02: 空データ → ヘッダーのみのCSV"""
        summary_data = []

        filename, csv_bytes = export_order_csv(summary_data, year="R8")

        assert isinstance(filename, str)
        assert isinstance(csv_bytes, bytes)

        # ヘッダーのみでも出力される
        csv_text = csv_bytes.decode("utf-8-sig")
        assert "農薬名" in csv_text


# =============================================================================
# TestImportOrderCsv（CI-03 ~ CI-04）
# =============================================================================

class TestImportOrderCsv:
    """import_order_csv のテスト"""

    def test_ci03_valid_csv(self):
        """CI-03: 有効CSV → items リスト"""
        csv_content = "農薬名,必要量,単位,対象作物\nトップジンM水和剤,5.00,L,てんさい\nスミチオン乳剤,3.50,L,大豆\n"

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, encoding="utf-8-sig"
        ) as f:
            f.write(csv_content)
            f.flush()
            tmp_path = f.name

        try:
            items, warnings = import_order_csv(tmp_path)

            assert isinstance(items, list)
            assert len(items) == 2

            # 最初のアイテム
            assert items[0]["農薬名"] == "トップジンM水和剤"
            assert items[0]["必要量"] == 5.0
            assert items[0]["単位"] == "L"
            assert items[0]["対象作物"] == "てんさい"
            assert items[0]["編集可"] is True

            # 2番目のアイテム
            assert items[1]["農薬名"] == "スミチオン乳剤"
            assert items[1]["必要量"] == 3.5
        finally:
            os.remove(tmp_path)

    def test_ci03_alternative_column_names(self):
        """CI-03b: 代替カラム名のCSV → 正規化されたitems"""
        csv_content = "pesticide_name,amount,unit,crop\nダコニール1000,2.00,L,春小麦\n"

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, encoding="utf-8-sig"
        ) as f:
            f.write(csv_content)
            f.flush()
            tmp_path = f.name

        try:
            items, warnings = import_order_csv(tmp_path)

            assert len(items) == 1
            assert items[0]["農薬名"] == "ダコニール1000"
        finally:
            os.remove(tmp_path)

    def test_ci04_invalid_csv_missing_column(self):
        """CI-04: 不正CSV（農薬名カラムなし） → エラー"""
        csv_content = "name_x,amount_x\nfoo,1\nbar,2\n"

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, encoding="utf-8-sig"
        ) as f:
            f.write(csv_content)
            f.flush()
            tmp_path = f.name

        try:
            items, warnings = import_order_csv(tmp_path)

            # 農薬名カラムがない → 空リスト + 警告
            assert items == []
            assert len(warnings) > 0
            assert any("必須カラム" in w for w in warnings)
        finally:
            os.remove(tmp_path)

    def test_ci04_corrupted_file(self):
        """CI-04b: 壊れたファイル → エラー"""
        with tempfile.NamedTemporaryFile(
            mode="wb", suffix=".csv", delete=False
        ) as f:
            f.write(b"\x00\x01\x02\xff\xfe binary garbage")
            f.flush()
            tmp_path = f.name

        try:
            items, warnings = import_order_csv(tmp_path)

            assert items == []
            assert len(warnings) > 0
        finally:
            os.remove(tmp_path)


# =============================================================================
# TestMergeWithCalculated（CI-05）
# =============================================================================

class TestMergeWithCalculated:
    """merge_with_calculated のテスト"""

    def test_ci05_merge(self):
        """CI-05: マージ → インポート優先、不足分は計算から補完"""
        imported_items = [
            {"農薬名": "トップジンM水和剤", "必要量": 5.0, "単位": "L", "対象作物": "てんさい", "編集可": True},
            {"農薬名": "スミチオン乳剤", "必要量": 3.5, "単位": "L", "対象作物": "大豆", "編集可": True},
        ]
        calculated_items = [
            {"農薬名": "トップジンM水和剤", "必要量": 6.0, "単位": "L", "対象作物": "てんさい"},  # 重複
            {"農薬名": "ダコニール1000", "必要量": 2.0, "単位": "L", "対象作物": "春小麦"},  # 新規
        ]

        result = merge_with_calculated(imported_items, calculated_items)

        assert isinstance(result, list)
        assert len(result) == 3  # 2 imported + 1 new from calculated

        # インポートデータが優先（トップジンは5.0のまま、6.0ではない）
        topjin = [r for r in result if r["農薬名"] == "トップジンM水和剤"][0]
        assert topjin["必要量"] == 5.0
        assert topjin["ソース"] == "インポート"

        # 計算データで補完（ダコニールはcalculatedから追加）
        daconil = [r for r in result if r["農薬名"] == "ダコニール1000"][0]
        assert daconil["必要量"] == 2.0
        assert daconil["ソース"] == "計算"

    def test_ci05_empty_import(self):
        """CI-05b: インポート空 → 計算データのみ"""
        imported_items = []
        calculated_items = [
            {"農薬名": "ダコニール1000", "必要量": 2.0, "単位": "L", "対象作物": "春小麦"},
        ]

        result = merge_with_calculated(imported_items, calculated_items)

        assert len(result) == 1
        assert result[0]["農薬名"] == "ダコニール1000"
        assert result[0]["ソース"] == "計算"

    def test_ci05_empty_calculated(self):
        """CI-05c: 計算データ空 → インポートデータのみ"""
        imported_items = [
            {"農薬名": "トップジンM水和剤", "必要量": 5.0, "単位": "L", "対象作物": "てんさい", "編集可": True},
        ]
        calculated_items = []

        result = merge_with_calculated(imported_items, calculated_items)

        assert len(result) == 1
        assert result[0]["農薬名"] == "トップジンM水和剤"
        assert result[0]["ソース"] == "インポート"
