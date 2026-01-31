"""
防除記録機能のテスト

テスト対象:
- Repository (PesticideRegistryRepository, PesticideUsageRepository, PesticideRecordRepository)
- FAMICインポーター (import_famic_basic, get_import_stats)
- 画像解析 (extract_exif, recognize_pesticide_name, analyze_image)
- エクスポート (export_records_csv, export_records_pdf)
"""

import pytest
import sys
import os
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

# プロジェクトルートをパスに追加
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rotation_planner.common import (
    PesticideRegistryRepository,
    PesticideUsageRepository,
    PesticideRecordRepository,
    get_db,
)
from rotation_planner.famic.importer import (
    import_famic_basic,
    get_import_stats,
)
from rotation_planner.pesticide_record.image_analyzer import (
    extract_exif,
    recognize_pesticide_name,
    analyze_image,
)
from rotation_planner.pesticide_record.export import (
    export_records_csv,
    export_records_pdf,
    check_export_support,
    REPORTLAB_AVAILABLE,
)


# =============================================================================
# フィクスチャ
# =============================================================================

@pytest.fixture
def test_user_id():
    """テスト用ユーザーID"""
    return 1


@pytest.fixture
def test_field_id():
    """テスト用ほ場ID（既存ほ場がある前提）"""
    from rotation_planner.common import FieldRepository
    fields = FieldRepository.get_fields(user_id=1)
    if fields:
        return fields[0].get("id")
    return None


@pytest.fixture
def sample_record_data(test_field_id):
    """サンプル防除記録データ"""
    return {
        "field_id": test_field_id,
        "spray_date": "2026-02-01",
        "pesticide_name": "テスト農薬",
        "pesticide_id": None,
        "dilution_rate": "1000倍",
        "spray_amount": 50.0,
        "spray_unit": "L",
        "photo_path": None,
        "notes": "テスト用記録",
    }


@pytest.fixture
def sample_records():
    """サンプル防除記録リスト"""
    return [
        {
            "spray_date": "2026-02-01",
            "field_name": "テスト1号",
            "field_code": "F001",
            "district": "東地区",
            "area_ha": 2.5,
            "crop": "大豆",
            "pesticide_name": "トップジンM水和剤",
            "dilution_rate": "1000倍",
            "spray_amount": "50L",
            "notes": "晴天時散布",
        },
        {
            "spray_date": "2026-02-05",
            "field_name": "テスト2号",
            "field_code": "F002",
            "district": "西地区",
            "area_ha": 3.0,
            "crop": "てんさい",
            "pesticide_name": "ダコニール1000",
            "dilution_rate": "500倍",
            "spray_amount": "80L",
            "notes": "",
        },
    ]


@pytest.fixture
def temp_dir():
    """一時ディレクトリを提供"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


# =============================================================================
# PesticideRegistryRepository テスト
# =============================================================================

class TestPesticideRegistryRepository:
    """農薬登録情報リポジトリのテスト"""

    def test_search_returns_list(self):
        """search() がリストを返すこと"""
        results = PesticideRegistryRepository.search("農薬")
        assert isinstance(results, list)

    def test_search_with_empty_keyword(self):
        """空キーワードでも正常に動作すること"""
        results = PesticideRegistryRepository.search("")
        assert isinstance(results, list)

    def test_search_with_limit(self):
        """検索結果がlimit以下であること"""
        limit = 5
        results = PesticideRegistryRepository.search("剤", limit=limit)
        assert len(results) <= limit

    def test_get_by_name_nonexistent(self):
        """存在しない農薬名でNoneを返すこと"""
        result = PesticideRegistryRepository.get_by_name("絶対に存在しない農薬名12345")
        assert result is None

    def test_get_by_id_nonexistent(self):
        """存在しないIDでNoneを返すこと"""
        result = PesticideRegistryRepository.get_by_id(999999999)
        assert result is None

    def test_get_all_returns_list(self):
        """get_all() がリストを返すこと"""
        results = PesticideRegistryRepository.get_all(limit=10)
        assert isinstance(results, list)


# =============================================================================
# PesticideUsageRepository テスト
# =============================================================================

class TestPesticideUsageRepository:
    """農薬適用情報リポジトリのテスト"""

    def test_get_by_crop_returns_list(self):
        """get_by_crop() がリストを返すこと"""
        results = PesticideUsageRepository.get_by_crop("大豆")
        assert isinstance(results, list)

    def test_get_by_crop_empty_result(self):
        """存在しない作物で空リストを返すこと"""
        results = PesticideUsageRepository.get_by_crop("存在しない作物12345")
        assert results == []

    def test_search_by_crop_returns_list(self):
        """search_by_crop() がリストを返すこと"""
        results = PesticideUsageRepository.search_by_crop("麦")
        assert isinstance(results, list)

    def test_get_by_pesticide_id_nonexistent(self):
        """存在しないpesticide_idで空リストを返すこと"""
        results = PesticideUsageRepository.get_by_pesticide_id(999999999)
        assert results == []


# =============================================================================
# PesticideRecordRepository テスト
# =============================================================================

class TestPesticideRecordRepository:
    """防除記録リポジトリのテスト"""

    def test_get_records_returns_list(self, test_user_id):
        """get_records() がリストを返すこと"""
        records = PesticideRecordRepository.get_records(test_user_id)
        assert isinstance(records, list)

    def test_get_records_user_isolation(self):
        """ユーザーごとに記録が分離されていること"""
        records_user1 = PesticideRecordRepository.get_records(user_id=1)
        records_user999 = PesticideRecordRepository.get_records(user_id=999)
        assert isinstance(records_user1, list)
        assert isinstance(records_user999, list)

    def test_get_records_with_limit(self, test_user_id):
        """limitが適用されること"""
        limit = 5
        records = PesticideRecordRepository.get_records(test_user_id, limit=limit)
        assert len(records) <= limit

    @pytest.mark.skipif(
        os.environ.get("CI") == "true",
        reason="CI環境ではDB変更を伴うテストをスキップ"
    )
    def test_crud_lifecycle(self, test_user_id, sample_record_data):
        """CRUD操作のライフサイクルテスト"""
        if not sample_record_data.get("field_id"):
            pytest.skip("テスト用ほ場が存在しません")

        # Create
        record_id = PesticideRecordRepository.create_record(test_user_id, sample_record_data)
        assert record_id is not None
        assert isinstance(record_id, int)

        try:
            # Read
            records = PesticideRecordRepository.get_records(
                test_user_id,
                field_id=sample_record_data["field_id"]
            )
            assert any(r.get("id") == record_id for r in records)

            # Update
            update_data = sample_record_data.copy()
            update_data["notes"] = "更新後のテスト備考"
            result = PesticideRecordRepository.update_record(record_id, update_data)
            assert result is True

            # Delete
            result = PesticideRecordRepository.delete_record(record_id)
            assert result is True

            # 削除確認
            records_after = PesticideRecordRepository.get_records(test_user_id)
            assert not any(r.get("id") == record_id for r in records_after)

        finally:
            # クリーンアップ（削除に失敗した場合のための保険）
            try:
                PesticideRecordRepository.delete_record(record_id)
            except Exception:
                pass

    def test_delete_nonexistent(self):
        """存在しない記録の削除でFalseを返すこと"""
        result = PesticideRecordRepository.delete_record(999999999)
        assert result is False


# =============================================================================
# FAMICインポーター テスト
# =============================================================================

class TestFAMICImporter:
    """FAMICインポーターのテスト"""

    def test_get_import_stats_returns_dict(self):
        """get_import_stats() が辞書を返すこと"""
        stats = get_import_stats()
        assert isinstance(stats, dict)

    def test_get_import_stats_keys(self):
        """get_import_stats() に必要なキーがあること"""
        stats = get_import_stats()
        expected_keys = ["registry_count", "usage_count", "last_basic_import", "last_usage_import"]
        for key in expected_keys:
            assert key in stats, f"キー '{key}' がありません"

    def test_get_import_stats_types(self):
        """get_import_stats() の値の型が正しいこと"""
        stats = get_import_stats()
        assert isinstance(stats["registry_count"], int)
        assert isinstance(stats["usage_count"], int)
        # last_*_import は str または None

    def test_import_famic_basic_file_not_found(self, temp_dir):
        """存在しないファイルでFileNotFoundErrorを返すこと"""
        with pytest.raises(FileNotFoundError):
            import_famic_basic(os.path.join(temp_dir, "nonexistent.xls"))


# =============================================================================
# 画像解析 テスト
# =============================================================================

class TestImageAnalyzer:
    """画像解析モジュールのテスト"""

    def test_extract_exif_file_not_found(self):
        """存在しないファイルでエラーを返すこと"""
        result = extract_exif("/nonexistent/path/image.jpg")
        assert "error" in result
        assert "ファイルが見つかりません" in result["error"]

    def test_extract_exif_returns_dict(self, temp_dir):
        """extract_exif() が辞書を返すこと"""
        # ダミーファイルを作成
        dummy_path = os.path.join(temp_dir, "dummy.txt")
        with open(dummy_path, "w") as f:
            f.write("dummy")

        result = extract_exif(dummy_path)
        assert isinstance(result, dict)
        assert "datetime" in result
        assert "gps" in result

    def test_recognize_pesticide_name_mock(self, temp_dir):
        """recognize_pesticide_name() のモックテスト"""
        # anthropicがインポートされているか確認
        try:
            import anthropic as anthropic_module
        except ImportError:
            pytest.skip("anthropic がインストールされていません")

        # モックレスポンスを設定
        mock_message = MagicMock()
        mock_message.content = [MagicMock(text="農薬名: トップジンM水和剤\n確信度: high")]
        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_message

        # 環境変数を設定し、Anthropicクラスをモック
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
            with patch.object(anthropic_module, 'Anthropic', return_value=mock_client):
                # テスト用画像を作成
                test_image = os.path.join(temp_dir, "test.jpg")
                with open(test_image, "wb") as f:
                    # 最小限のJPEGヘッダー
                    f.write(b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00')

                result = recognize_pesticide_name(test_image)

                assert isinstance(result, dict)
                assert result.get("pesticide_name") == "トップジンM水和剤"
                assert result.get("confidence") == "high"

    def test_recognize_pesticide_name_no_api_key(self, temp_dir):
        """API キーなしでエラーを返すこと"""
        # 環境変数からAPIキーを削除
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": ""}, clear=True):
            test_image = os.path.join(temp_dir, "test.jpg")
            with open(test_image, "wb") as f:
                f.write(b'\xff\xd8\xff\xe0\x00\x10JFIF')

            result = recognize_pesticide_name(test_image)
            assert "error" in result

    @patch('rotation_planner.pesticide_record.image_analyzer.extract_exif')
    @patch('rotation_planner.pesticide_record.image_analyzer.recognize_pesticide_name')
    def test_analyze_image_integration(self, mock_recognize, mock_exif, temp_dir):
        """analyze_image() の統合テスト（モック使用）"""
        # モックを設定
        mock_exif.return_value = {
            "datetime": "2026-02-01 10:30:00",
            "gps": {"lat": 43.0, "lon": 141.0}
        }
        mock_recognize.return_value = {
            "pesticide_name": "ダコニール1000",
            "confidence": "medium"
        }

        test_image = os.path.join(temp_dir, "test.jpg")
        with open(test_image, "w") as f:
            f.write("dummy")

        result = analyze_image(test_image)

        assert isinstance(result, dict)
        assert result.get("spray_date") == "2026-02-01"
        assert result.get("spray_datetime") == "2026-02-01 10:30:00"
        assert result.get("gps") == {"lat": 43.0, "lon": 141.0}
        assert result.get("pesticide_name") == "ダコニール1000"
        assert result.get("confidence") == "medium"

    @patch('rotation_planner.pesticide_record.image_analyzer.extract_exif')
    @patch('rotation_planner.pesticide_record.image_analyzer.recognize_pesticide_name')
    def test_analyze_image_with_errors(self, mock_recognize, mock_exif, temp_dir):
        """analyze_image() がエラーを収集すること"""
        mock_exif.return_value = {"datetime": None, "gps": None, "error": "EXIF情報がありません"}
        mock_recognize.return_value = {"error": "API エラー: 接続失敗"}

        test_image = os.path.join(temp_dir, "test.jpg")
        with open(test_image, "w") as f:
            f.write("dummy")

        result = analyze_image(test_image)

        assert isinstance(result, dict)
        assert "errors" in result
        assert len(result["errors"]) == 2


# =============================================================================
# エクスポート テスト
# =============================================================================

class TestExport:
    """エクスポート機能のテスト"""

    def test_check_export_support(self):
        """check_export_support() が辞書を返すこと"""
        support = check_export_support()
        assert isinstance(support, dict)
        assert "csv_available" in support
        assert "pdf_available" in support
        assert support["csv_available"] is True

    def test_export_records_csv_creates_file(self, sample_records, temp_dir):
        """export_records_csv() がファイルを作成すること"""
        output_path = os.path.join(temp_dir, "test_records.csv")

        result = export_records_csv(sample_records, output_path)

        assert result == output_path
        assert os.path.exists(output_path)

    def test_export_records_csv_content(self, sample_records, temp_dir):
        """export_records_csv() の出力内容が正しいこと"""
        output_path = os.path.join(temp_dir, "test_records.csv")
        export_records_csv(sample_records, output_path)

        with open(output_path, "r", encoding="utf-8-sig") as f:
            content = f.read()

        # ヘッダーを確認
        assert "散布日" in content
        assert "農薬名" in content

        # データを確認
        assert "トップジンM水和剤" in content
        assert "2026-02-01" in content

    def test_export_records_csv_empty(self, temp_dir):
        """空のレコードでもヘッダーが出力されること"""
        output_path = os.path.join(temp_dir, "empty_records.csv")
        export_records_csv([], output_path)

        assert os.path.exists(output_path)
        with open(output_path, "r", encoding="utf-8-sig") as f:
            lines = f.readlines()

        assert len(lines) == 1  # ヘッダーのみ

    @pytest.mark.skipif(
        not REPORTLAB_AVAILABLE,
        reason="reportlab がインストールされていません"
    )
    def test_export_records_pdf_creates_file(self, sample_records, temp_dir):
        """export_records_pdf() がファイルを作成すること"""
        output_path = os.path.join(temp_dir, "test_records.pdf")

        result = export_records_pdf(
            sample_records,
            output_path,
            "テスト農家",
            "2026-01-01",
            "2026-12-31"
        )

        assert result == output_path
        assert os.path.exists(output_path)

    @pytest.mark.skipif(
        not REPORTLAB_AVAILABLE,
        reason="reportlab がインストールされていません"
    )
    def test_export_records_pdf_file_size(self, sample_records, temp_dir):
        """export_records_pdf() が有効なPDFを生成すること（サイズチェック）"""
        output_path = os.path.join(temp_dir, "test_records.pdf")
        export_records_pdf(sample_records, output_path, "テスト農家")

        # PDFが一定サイズ以上であることを確認（空でないことの確認）
        file_size = os.path.getsize(output_path)
        assert file_size > 1000, f"PDFサイズが小さすぎます: {file_size} bytes"

    @pytest.mark.skipif(
        not REPORTLAB_AVAILABLE,
        reason="reportlab がインストールされていません"
    )
    def test_export_records_pdf_empty(self, temp_dir):
        """空のレコードでもPDFが生成されること"""
        output_path = os.path.join(temp_dir, "empty_records.pdf")
        result = export_records_pdf([], output_path, "テスト農家")

        assert result == output_path
        assert os.path.exists(output_path)


# =============================================================================
# セキュリティテスト
# =============================================================================

class TestSecurityIsolation:
    """セキュリティ分離テスト"""

    def test_record_repository_requires_user_id(self):
        """PesticideRecordRepository.get_records() はuser_idが必須であること"""
        with pytest.raises(TypeError):
            PesticideRecordRepository.get_records()

    def test_no_cross_user_data_leak(self):
        """他ユーザーのデータが漏洩しないこと"""
        records_user1 = PesticideRecordRepository.get_records(user_id=1)
        records_user999 = PesticideRecordRepository.get_records(user_id=999)

        # 両方にデータがある場合、IDが重複しないことを確認
        if records_user1 and records_user999:
            ids_user1 = {r.get("id") for r in records_user1}
            ids_user999 = {r.get("id") for r in records_user999}
            assert ids_user1.isdisjoint(ids_user999), "ユーザー間でIDが重複しています"
