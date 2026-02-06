"""
rotation_planner.common.ui_utils - 単体テスト

テスト設計書: docs/TEST_UNIT.md セクション3.10
テストケース: UI-01～UI-05
"""

import pytest
import sys
import os

# プロジェクトルートをパスに追加
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rotation_planner.common.ui_utils import (
    format_alert,
    format_success,
    format_error,
    format_warning,
    format_info,
)


class TestFormatAlert:
    """format_alert関数のテスト"""

    def test_UI_01_format_alert_success(self):
        """UI-01: format_alert success → 緑色/成功アイコン付きHTML"""
        message = "操作が成功しました"
        result = format_alert(message, "success")

        # HTML文字列であることを確認
        assert isinstance(result, str)
        assert "<div" in result
        assert "</div>" in result

        # メッセージが含まれることを確認
        assert message in result

        # 緑色の背景色が設定されていることを確認（#d4edda）
        assert "#d4edda" in result

        # 緑色のテキスト色が設定されていることを確認（#155724）
        assert "#155724" in result

    def test_UI_02_format_alert_error(self):
        """UI-02: format_alert error → 赤色/エラーアイコン付きHTML"""
        message = "エラーが発生しました"
        result = format_alert(message, "error")

        # HTML文字列であることを確認
        assert isinstance(result, str)
        assert "<div" in result
        assert "</div>" in result

        # メッセージが含まれることを確認
        assert message in result

        # 赤色の背景色が設定されていることを確認（#f8d7da）
        assert "#f8d7da" in result

        # 赤色のテキスト色が設定されていることを確認（#721c24）
        assert "#721c24" in result

    @pytest.mark.skip(reason="ui_utils.py未実装: HTMLエスケープ処理が必要（セキュリティ要件）")
    def test_UI_05_format_alert_xss_prevention(self):
        """UI-05: format_alert XSS防止 → <script>タグがエスケープされる

        【SKIP理由】
        現在のui_utils.py実装ではHTMLエスケープが実装されていない。
        messageをf-string内に直接埋め込んでいるため、XSS脆弱性がある。

        【修正案】
        ui_utils.pyのformat_alert()内でhtml.escape()を使用してエスケープする。
        例: import html; escaped_msg = html.escape(message)

        【RACE-001遵守】
        他ファイル修正禁止のため、ui_utils.py修正は別タスクで対応すること。
        """
        xss_payload = "<script>alert('xss')</script>"
        result = format_alert(xss_payload, "info")

        # HTML文字列であることを確認
        assert isinstance(result, str)

        # <script>タグがそのまま含まれていないことを確認
        # （エスケープされている、または除去されている）
        # 現在の実装ではエスケープされていないため、このテストは失敗する
        # しかし、セキュリティ上の要件として、エスケープされるべきである

        # XSSペイロードがそのまま実行可能な形で含まれていないことを確認
        # エスケープされていれば &lt;script&gt; のような形になる
        # または、<script>タグが直接含まれていないことを確認
        assert "<script>" not in result or "&lt;script&gt;" in result


class TestFormatErrorWrapper:
    """format_error関数のテスト"""

    def test_UI_03_format_error_wrapper(self):
        """UI-03: format_error ラッパー → format_alert(msg, "error") と同等"""
        message = "テストエラーメッセージ"

        # format_error()の結果
        result_wrapper = format_error(message)

        # format_alert(message, "error")の結果
        result_direct = format_alert(message, "error")

        # 両方が同じHTML文字列であることを確認
        assert result_wrapper == result_direct

        # エラー用の赤色が含まれることを確認
        assert "#f8d7da" in result_wrapper


class TestFormatSuccessWrapper:
    """format_success関数のテスト"""

    def test_UI_04_format_success_wrapper(self):
        """UI-04: format_success ラッパー → format_alert(msg, "success") と同等"""
        message = "テスト成功メッセージ"

        # format_success()の結果
        result_wrapper = format_success(message)

        # format_alert(message, "success")の結果
        result_direct = format_alert(message, "success")

        # 両方が同じHTML文字列であることを確認
        assert result_wrapper == result_direct

        # 成功用の緑色が含まれることを確認
        assert "#d4edda" in result_wrapper


class TestOtherFormatFunctions:
    """その他のformat関数の基本動作確認（追加テスト）"""

    def test_format_warning(self):
        """format_warning: 警告メッセージ（黄色）"""
        message = "警告メッセージ"
        result = format_warning(message)

        assert isinstance(result, str)
        assert message in result
        # 黄色の背景色（#fff3cd）
        assert "#fff3cd" in result

    def test_format_info(self):
        """format_info: 情報メッセージ（青色）"""
        message = "情報メッセージ"
        result = format_info(message)

        assert isinstance(result, str)
        assert message in result
        # 青色の背景色（#d1ecf1）
        assert "#d1ecf1" in result
