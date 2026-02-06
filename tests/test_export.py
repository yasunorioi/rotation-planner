"""
CSVエクスポート（common/export.py）の単体テスト

テストケース: EX-01 ~ EX-06（P1テスト設計書 3.7節）
"""
import os
import csv
import pytest
from unittest.mock import patch

from rotation_planner.common.export import (
    can_access_all_data,
    export_rotation_plan_csv,
    export_fields_csv,
)


# ============================================================
# EX-01, EX-02: can_access_all_data（純粋関数テスト）
# ============================================================

class TestCanAccessAllData:
    """can_access_all_data のテスト"""

    def test_ex01_admin_returns_true(self, admin_state):
        """EX-01: admin → True"""
        assert can_access_all_data(admin_state) is True

    def test_ex01_ja_staff_returns_true(self, ja_staff_state):
        """EX-01補足: ja_staff → True"""
        assert can_access_all_data(ja_staff_state) is True

    def test_ex02_farmer_returns_false(self, farmer_state):
        """EX-02: farmer → False"""
        assert can_access_all_data(farmer_state) is False

    def test_empty_state_returns_false(self):
        """補足: 空state → False"""
        assert can_access_all_data({}) is False

    def test_none_state_returns_false(self):
        """補足: None → False"""
        assert can_access_all_data(None) is False


# ============================================================
# EX-03, EX-04: export_rotation_plan_csv（DB依存テスト）
# ============================================================

class TestExportRotationPlanCsv:
    """export_rotation_plan_csv のテスト"""

    def test_ex03_normal_export(self, test_db, admin_state, temp_dir):
        """EX-03: 正常エクスポート → (path, msg)"""
        from rotation_planner.common.db_access import (
            FieldRepository, PlanRepository,
        )

        # テストデータ準備: ほ場作成
        field_id = FieldRepository.create_field(admin_state["user_id"], {
            "field_code": "EX_F001",
            "district": "テスト地区",
            "name": "エクスポートテスト圃場",
            "area_ha": 2.5,
        })

        # テストデータ準備: 計画作成（details付き）
        plan_id = PlanRepository.create_plan(admin_state["user_id"], {
            "name": "テスト輪作計画",
            "start_year": "R6",
            "end_year": "R8",
            "details": [
                {"field_id": field_id, "year": "R6", "crop": "大豆"},
                {"field_id": field_id, "year": "R7", "crop": "てんさい"},
                {"field_id": field_id, "year": "R8", "crop": "春小麦"},
            ],
        })

        # CSV出力先を一時ディレクトリに変更
        # get_accessible_user_idsはJAStaffRepositoryに依存するためモック
        with patch("rotation_planner.common.export.CSV_OUTPUT_DIR", temp_dir), \
             patch("rotation_planner.common.export.get_accessible_user_ids",
                   return_value=[admin_state["user_id"]]):
            filepath, msg = export_rotation_plan_csv(plan_id, admin_state)

        # 検証
        assert filepath is not None, f"ファイルパスがNone: {msg}"
        assert os.path.exists(filepath)
        assert "出力しました" in msg
        assert "3件" in msg

        # CSV内容を検証
        with open(filepath, encoding="utf-8-sig") as f:
            reader = csv.reader(f)
            rows = list(reader)

        # ヘッダー + 3データ行
        assert len(rows) == 4
        assert rows[0] == ["計画名", "ほ場コード", "ほ場名", "地区", "年度", "作物"]
        assert rows[1][0] == "テスト輪作計画"

    def test_ex04_no_permission(self, test_db, farmer_state, admin_state, temp_dir):
        """EX-04: 他人の計画へのアクセス → エラーメッセージ"""
        from rotation_planner.common.db_access import (
            FieldRepository, PlanRepository,
        )

        # admin所有のほ場と計画を作成
        field_id = FieldRepository.create_field(admin_state["user_id"], {
            "field_code": "EX_F002",
            "district": "テスト地区",
            "name": "管理者の圃場",
            "area_ha": 1.0,
        })
        plan_id = PlanRepository.create_plan(admin_state["user_id"], {
            "name": "管理者の計画",
            "start_year": "R6",
            "end_year": "R7",
            "details": [
                {"field_id": field_id, "year": "R6", "crop": "大豆"},
            ],
        })

        # farmerがadminの計画にアクセス → 権限エラー
        # farmerのget_accessible_user_idsは自分のIDのみ返す
        with patch("rotation_planner.common.export.CSV_OUTPUT_DIR", temp_dir), \
             patch("rotation_planner.common.export.get_accessible_user_ids",
                   return_value=[farmer_state["user_id"]]):
            filepath, msg = export_rotation_plan_csv(plan_id, farmer_state)

        assert filepath is None
        assert "エラー" in msg

    def test_not_logged_in(self, temp_dir):
        """補足: 未ログイン → エラー"""
        filepath, msg = export_rotation_plan_csv(1, {})
        assert filepath is None
        assert "ログイン" in msg

    def test_nonexistent_plan(self, test_db, admin_state, temp_dir):
        """補足: 存在しない計画ID → エラー"""
        with patch("rotation_planner.common.export.CSV_OUTPUT_DIR", temp_dir):
            filepath, msg = export_rotation_plan_csv(99999, admin_state)
        assert filepath is None
        assert "見つかりません" in msg


# ============================================================
# EX-05, EX-06: export_fields_csv（DB依存テスト）
# ============================================================

class TestExportFieldsCsv:
    """export_fields_csv のテスト"""

    def test_ex05_normal_export(self, test_db, admin_state, temp_dir):
        """EX-05: 正常出力 → (path, msg)"""
        from rotation_planner.common.db_access import FieldRepository

        # テストデータ準備: ほ場2件作成
        FieldRepository.create_field(admin_state["user_id"], {
            "field_code": "EX_F010",
            "district": "A地区",
            "name": "テスト圃場A",
            "area_ha": 3.0,
            "beet_forbidden": False,
        })
        FieldRepository.create_field(admin_state["user_id"], {
            "field_code": "EX_F011",
            "district": "B地区",
            "name": "テスト圃場B",
            "area_ha": 1.5,
            "beet_forbidden": True,
        })

        # CSV出力
        with patch("rotation_planner.common.export.CSV_OUTPUT_DIR", temp_dir):
            filepath, msg = export_fields_csv(admin_state)

        # 検証
        assert filepath is not None, f"ファイルパスがNone: {msg}"
        assert os.path.exists(filepath)
        assert "出力しました" in msg

        # CSV内容を検証
        with open(filepath, encoding="utf-8-sig") as f:
            reader = csv.reader(f)
            rows = list(reader)

        # ヘッダー + 2データ行以上
        assert len(rows) >= 3
        assert rows[0] == ["ほ場ID", "地区", "ほ場名", "area", "beet_forbidden"]

    def test_ex06_not_logged_in(self):
        """EX-06: 未ログイン → (None, error)"""
        filepath, msg = export_fields_csv({})
        assert filepath is None
        assert "ログイン" in msg

    def test_ex06_none_state(self):
        """EX-06補足: None state → (None, error)"""
        filepath, msg = export_fields_csv(None)
        assert filepath is None
        assert "ログイン" in msg

    def test_no_fields(self, test_db, temp_dir):
        """補足: ほ場データなし → エラー"""
        # ほ場が存在しないユーザー
        empty_user_state = {
            "user_id": 99999,
            "username": "nobody",
            "role": "farmer",
            "org_id": 1,
        }
        with patch("rotation_planner.common.export.CSV_OUTPUT_DIR", temp_dir):
            filepath, msg = export_fields_csv(empty_user_state)

        assert filepath is None
        assert "エラー" in msg
