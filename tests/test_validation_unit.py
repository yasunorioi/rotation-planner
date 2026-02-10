"""
入力バリデーション（validation.py）の単体テスト

テスト設計書: docs/ERROR_HANDLING_DESIGN.md セクション6（Phase 3）
テストケース: VR-01～VR-04, VQ-01～VQ-03, VS-01～VS-03,
              VN-01～VN-03, VF-01～VF-03, VC-01～VC-02, VU-01～VU-02
合計: 20テスト
"""
import pytest

from rotation_planner.common.validation import (
    ValidationResult,
    validate_required,
    validate_string_length,
    validate_range,
    validate_field,
    validate_crop,
    validate_user,
)


# ============================================================
# VR-01～VR-04: ValidationResult クラステスト
# ============================================================

class TestValidationResult:
    """ValidationResult クラスのテスト"""

    def test_vr01_initial_state_is_valid(self):
        """VR-01: 初期状態 → is_valid() == True"""
        result = ValidationResult()
        assert result.is_valid() is True
        assert result.errors == []

    def test_vr02_after_add_error_is_invalid(self):
        """VR-02: add_error後 → is_valid() == False"""
        result = ValidationResult()
        result.add_error("圃場名", "入力してください")
        assert result.is_valid() is False
        assert len(result.errors) == 1

    def test_vr03_get_error_messages_format(self):
        """VR-03: get_error_messages → 'フィールド名: メッセージ' 形式のリスト"""
        result = ValidationResult()
        result.add_error("圃場名", "入力してください")
        result.add_error("面積", "0.01以上を入力してください")

        messages = result.get_error_messages()
        assert len(messages) == 2
        assert messages[0] == "圃場名: 入力してください"
        assert messages[1] == "面積: 0.01以上を入力してください"

    def test_vr04_get_first_error(self):
        """VR-04: get_first_error → 最初のエラーメッセージ"""
        result = ValidationResult()
        result.add_error("圃場名", "入力してください")
        result.add_error("面積", "範囲外です")

        first = result.get_first_error()
        assert first is not None
        assert "入力してください" in first

    def test_vr04_get_first_error_no_errors(self):
        """VR-04補足: エラーなし → None"""
        result = ValidationResult()
        assert result.get_first_error() is None


# ============================================================
# VQ-01～VQ-03: validate_required テスト
# ============================================================

class TestValidateRequired:
    """validate_required のテスト"""

    def test_vq01_valid_value(self):
        """VQ-01: 有効値 → エラーなし"""
        result = ValidationResult()
        ret = validate_required("テスト圃場", "圃場名", result)
        assert ret is True
        assert result.is_valid() is True

    def test_vq02_none_value(self):
        """VQ-02: None → エラーあり"""
        result = ValidationResult()
        ret = validate_required(None, "圃場名", result)
        assert ret is False
        assert result.is_valid() is False
        assert len(result.errors) == 1

    def test_vq03_empty_string(self):
        """VQ-03: 空文字列 → エラーあり"""
        result = ValidationResult()
        ret = validate_required("", "圃場名", result)
        assert ret is False
        assert result.is_valid() is False


# ============================================================
# VS-01～VS-03: validate_string_length テスト
# ============================================================

class TestValidateStringLength:
    """validate_string_length のテスト"""

    def test_vs01_within_range(self):
        """VS-01: 範囲内 → エラーなし"""
        result = ValidationResult()
        ret = validate_string_length("テスト圃場", "圃場名", result, min_len=1, max_len=50)
        assert ret is True
        assert result.is_valid() is True

    def test_vs02_too_long(self):
        """VS-02: 長すぎ → エラーあり"""
        result = ValidationResult()
        long_name = "あ" * 51
        ret = validate_string_length(long_name, "圃場名", result, min_len=1, max_len=50)
        assert ret is False
        assert result.is_valid() is False

    def test_vs03_too_short(self):
        """VS-03: 短すぎ → エラーあり"""
        result = ValidationResult()
        ret = validate_string_length("", "圃場名", result, min_len=1, max_len=50)
        assert ret is False
        assert result.is_valid() is False


# ============================================================
# VN-01～VN-03: validate_range テスト
# ============================================================

class TestValidateRange:
    """validate_range のテスト"""

    def test_vn01_within_range(self):
        """VN-01: 範囲内 → エラーなし"""
        result = ValidationResult()
        ret = validate_range(5.0, "面積", result, min_val=0.01, max_val=1000)
        assert ret is True
        assert result.is_valid() is True

    def test_vn02_below_min(self):
        """VN-02: 下限未満 → エラーあり"""
        result = ValidationResult()
        ret = validate_range(0.001, "面積", result, min_val=0.01, max_val=1000)
        assert ret is False
        assert result.is_valid() is False

    def test_vn03_above_max(self):
        """VN-03: 上限超過 → エラーあり"""
        result = ValidationResult()
        ret = validate_range(1500, "面積", result, min_val=0.01, max_val=1000)
        assert ret is False
        assert result.is_valid() is False


# ============================================================
# VF-01～VF-03: validate_field テスト
# ============================================================

class TestValidateField:
    """validate_field のテスト"""

    def test_vf01_valid_data(self):
        """VF-01: 正常データ → is_valid()"""
        data = {"field_code": "F001", "name": "テスト圃場", "area_ha": 2.5}
        result = validate_field(data)
        assert result.is_valid() is True

    def test_vf02_missing_required(self):
        """VF-02: 必須項目欠落（nameなし）→ エラーあり"""
        data = {"field_code": "F001", "area_ha": 2.5}
        result = validate_field(data)
        assert result.is_valid() is False

    def test_vf03_area_out_of_range(self):
        """VF-03: 面積範囲外 → エラーあり"""
        data = {"field_code": "F001", "name": "テスト圃場", "area_ha": 5000}
        result = validate_field(data)
        assert result.is_valid() is False


# ============================================================
# VC-01～VC-02: validate_crop テスト
# ============================================================

class TestValidateCrop:
    """validate_crop のテスト"""

    def test_vc01_valid_data(self):
        """VC-01: 正常データ → is_valid()"""
        data = {"name": "大豆", "family": "マメ科", "interval_years": 2}
        result = validate_crop(data)
        assert result.is_valid() is True

    def test_vc02_missing_required(self):
        """VC-02: 必須項目欠落（作物名なし）→ エラーあり"""
        data = {"family": "マメ科", "interval_years": 2}
        result = validate_crop(data)
        assert result.is_valid() is False


# ============================================================
# VU-01～VU-02: validate_user テスト
# ============================================================

class TestValidateUser:
    """validate_user のテスト"""

    def test_vu01_valid_data(self):
        """VU-01: 正常データ → is_valid()"""
        data = {"username": "test_user", "display_name": "テストユーザー"}
        result = validate_user(data)
        assert result.is_valid() is True

    def test_vu02_username_too_short(self):
        """VU-02: ユーザー名短すぎ → エラーあり"""
        data = {"username": "ab", "display_name": "テストユーザー"}
        result = validate_user(data)
        assert result.is_valid() is False
