# Security Audit Report

> **Audit Date**: 2026-01-29
> **Auditor**: ashigaru5 (Senior Security Engineer)
> **Scope**: rotation_planner_ui - Multi-user data isolation

---

## Executive Summary

| Category | Status | Details |
|----------|--------|---------|
| **Overall Risk** | **MEDIUM** | DB層に脆弱性あり、UI層で保護 |
| **Immediate Action** | 不要 | 現在のUI経由では問題なし |
| **Recommended** | 要対応 | DB層の強化を推奨 |

**結論**: 現状のアプリケーションは**安全に動作**している。ただし、将来の拡張に備えてDB層の強化を推奨。

---

## 1. Audit Scope

### Target Files
- `db_access.py` - DBアクセス層
- `field_ui.py` - ほ場登録UI
- `app_ui.py` - 輪作計画UI
- `pesticide_ui.py` - 農薬発注UI
- `portal.py` - 統合ポータル
- `auth.py` - 認証モジュール

### Check Items
1. SELECT文に user_id / org_id フィルタがあるか
2. farmer ロールで他農家のデータにアクセスできないか
3. CSVダウンロード時に権限チェックがあるか
4. JA職員は全農家データを見れるが、農家は自分のみか

---

## 2. Findings

### 2.1 db_access.py - DBアクセス層

#### SAFE - user_id フィルタあり

| Repository | Method | Filter | Status |
|------------|--------|--------|--------|
| FieldRepository | `get_fields(user_id)` | WHERE user_id = ? | **OK** |
| FieldRepository | `get_field_by_code(user_id, code)` | WHERE user_id = ? AND field_code = ? | **OK** |
| FieldRepository | `create_field(user_id, data)` | INSERT with user_id | **OK** |
| PlanRepository | `get_plans(user_id)` | WHERE user_id = ? | **OK** |
| PlanRepository | `create_plan(user_id, data)` | INSERT with user_id | **OK** |
| JAStaffRepository | `get_all_fields(org_id)` | WHERE u.org_id = ? | **OK** |
| JAStaffRepository | `get_all_farmers(org_id)` | WHERE u.org_id = ? | **OK** |
| JAStaffRepository | `get_aggregate_stats(org_id)` | WHERE u.org_id = ? | **OK** |

#### WARNING - 所有権チェックなし

| Repository | Method | Issue | Severity |
|------------|--------|-------|----------|
| FieldRepository | `get_field(field_id)` | user_id チェックなし | **HIGH** |
| FieldRepository | `update_field(field_id, data)` | 所有権チェックなし | **HIGH** |
| FieldRepository | `delete_field(field_id)` | 所有権チェックなし | **HIGH** |
| FieldRepository | `get_field_with_history(field_id)` | user_id チェックなし | **HIGH** |
| CropHistoryRepository | `get_history(field_id)` | ほ場所有権チェックなし | **MEDIUM** |
| CropHistoryRepository | `add_history(field_id, ...)` | ほ場所有権チェックなし | **MEDIUM** |
| PlanRepository | `get_plan(plan_id)` | user_id チェックなし | **HIGH** |
| PlanRepository | `update_plan(plan_id, data)` | 所有権チェックなし | **HIGH** |
| PlanRepository | `delete_plan(plan_id)` | 所有権チェックなし | **HIGH** |

**Note**: これらの脆弱性は**UI層で保護されている**ため、現在のアプリケーション経由では悪用不可。

---

### 2.2 field_ui.py - ほ場登録UI

| Function | Protection | Status |
|----------|------------|--------|
| `register_field_with_state` | user_id でDB登録 | **OK** |
| `delete_field_with_state` | `get_field_by_code(user_id, ...)` で所有権確認後削除 | **OK** |
| `export_csv_with_state` | user_id でフィルタしたデータのみ出力 | **OK** |
| `get_field_history_with_state` | `get_field_by_code(user_id, ...)` で所有権確認 | **OK** |
| `load_initial_data_with_state` | user_id でフィルタ | **OK** |

**評価**: UI層で適切に所有権チェックを実装。**問題なし**。

---

### 2.3 portal.py - 統合ポータル

| Feature | Protection | Status |
|---------|------------|--------|
| タブ可視性制御 | role チェック | **OK** |
| 農家一覧タブ | `role in ["admin", "ja_staff"]` で制御 | **OK** |
| 管理者タブ | `role == "admin"` で制御 | **OK** |
| ほ場登録機能 | user_state 経由で user_id 使用 | **OK** |

**軽微な問題**:
```python
# portal.py:90, 374
JAStaffRepository.get_aggregate_stats(org_id=1)  # org_id ハードコード
JAStaffRepository.get_all_farmers(org_id=1)      # org_id ハードコード
```
→ 複数組織対応時に修正必要。現状は1組織のみで問題なし。

---

### 2.4 pesticide_ui.py - 農薬発注UI

| Feature | Protection | Status |
|---------|------------|--------|
| 発注計算 | ユーザーアップロードCSV使用 | **OK** |
| 防除マスタ読込 | org_id でフィルタ | **OK** |
| JA集計タブ | 現在はスタブ実装 | **N/A** |

**注意**: `get_all_farmers_orders()` と `get_aggregate_pesticide_orders()` は現在スタブ実装。将来の実装時に org_id フィルタが必要。

---

### 2.5 app_ui.py - 輪作計画UI

| Feature | Protection | Status |
|---------|------------|--------|
| 輪作計画生成 | CSVアップロード型、DB直接アクセスなし | **OK** |

**評価**: DBアクセスなしのため**問題なし**。

---

### 2.6 auth.py - 認証モジュール

| Function | Purpose | Status |
|----------|---------|--------|
| `authenticate()` | Gradio認証 | **OK** |
| `can_access_farmer()` | アクセス権限チェック | **OK** |
| `is_admin_role()` | 管理者ロールチェック | **OK** |
| `get_accessible_farmers()` | アクセス可能な農家リスト | **OK** |

**評価**: 適切なアクセス制御ロジック。**問題なし**。

---

## 3. Risk Assessment

### 現在のリスク: **LOW**

UI層で適切に保護されているため、通常の使用では他農家のデータにアクセス不可。

### 潜在的リスク: **MEDIUM**

- db_access.py を直接使用する新規コードで脆弱性が発生する可能性
- APIエンドポイント追加時に保護漏れの可能性

---

## 4. Recommendations

### 4.1 推奨（将来の拡張に備えて）

**db_access.py に所有権チェック付きメソッドを追加**:

```python
class FieldRepository:
    @staticmethod
    def get_field_safe(user_id: int, field_id: int) -> Optional[Dict]:
        """所有権チェック付きでほ場を取得"""
        with get_db() as conn:
            cursor = conn.execute("""
                SELECT * FROM fields WHERE id = ? AND user_id = ?
            """, (field_id, user_id))
            return row_to_dict(cursor.fetchone())

    @staticmethod
    def update_field_safe(user_id: int, field_id: int, data: Dict) -> bool:
        """所有権チェック付きで更新"""
        # まず所有権確認
        field = FieldRepository.get_field_safe(user_id, field_id)
        if not field:
            return False
        return FieldRepository.update_field(field_id, data)

    @staticmethod
    def delete_field_safe(user_id: int, field_id: int) -> bool:
        """所有権チェック付きで削除"""
        field = FieldRepository.get_field_safe(user_id, field_id)
        if not field:
            return False
        return FieldRepository.delete_field(field_id)
```

### 4.2 優先度: 低

portal.py の org_id ハードコードを user_state から取得するよう修正:

```python
# Before
stats = JAStaffRepository.get_aggregate_stats(org_id=1)

# After
org_id = user_state.get('org_id', 1)
stats = JAStaffRepository.get_aggregate_stats(org_id=org_id)
```

---

## 5. Test Scenarios

### 5.1 実施済み確認

| Scenario | Expected | Result |
|----------|----------|--------|
| 農家Aでログイン → ほ場一覧表示 | 自分のほ場のみ | **PASS** |
| 農家Aでログイン → 他農家のほ場削除試行 | 削除不可 | **PASS** |
| 農家Aでログイン → CSVエクスポート | 自分のデータのみ | **PASS** |
| JA職員でログイン → 農家一覧タブ | 表示される | **PASS** |
| 農家でログイン → 農家一覧タブ | 非表示 | **PASS** |

### 5.2 推奨追加テスト

```python
def test_cross_user_access():
    """異なるユーザー間のデータアクセス不可を確認"""
    # 農家Aのほ場を作成
    field_id = FieldRepository.create_field(user_id=1, data={...})

    # 農家Bで削除を試みる（UI経由）
    result = delete_field_with_state("F001", {"user_id": 2})
    assert "見つかりません" in result[1]  # エラーメッセージ
```

---

## 6. Conclusion

### 総合評価: **SAFE（条件付き）**

- **現在のアプリケーション**: 安全に動作
- **UI層**: 適切な所有権チェックを実装
- **DB層**: 脆弱性あり（UI層で保護）

### 必要アクション

| Priority | Action | Deadline |
|----------|--------|----------|
| **推奨** | db_access.py に _safe メソッド追加 | 次回リリース |
| **低** | org_id ハードコード修正 | 複数組織対応時 |

---

**Auditor**: ashigaru5
**Date**: 2026-01-29T17:55:16
