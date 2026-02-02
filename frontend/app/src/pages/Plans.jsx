/**
 * 保存済み計画ページ
 */

import { useEffect, useState } from 'react';
import { planApi } from '../lib/api';
import { Spinner } from '../components/Loading';
import { EmptyState } from '../components/ErrorMessage';

export default function Plans() {
  const [plans, setPlans] = useState([]);
  const [selectedPlan, setSelectedPlan] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [showEditModal, setShowEditModal] = useState(false);
  const [editFormData, setEditFormData] = useState({ name: '' });
  const [showApplyHistoryModal, setShowApplyHistoryModal] = useState(false);
  const [isApplying, setIsApplying] = useState(false);

  useEffect(() => {
    loadPlans();
  }, []);

  const loadPlans = async () => {
    setIsLoading(true);
    try {
      const data = await planApi.list();
      setPlans(data);
    } catch (err) {
      console.error('Failed to load plans:', err);
    } finally {
      setIsLoading(false);
    }
  };

  const viewPlan = async (id) => {
    try {
      const plan = await planApi.get(id);
      setSelectedPlan(plan);
    } catch (err) {
      alert('計画の取得に失敗しました');
    }
  };

  const deletePlan = async (id) => {
    if (!confirm('この計画を削除しますか？')) return;
    try {
      await planApi.delete(id);
      setPlans(plans.filter((p) => p.id !== id));
      if (selectedPlan?.id === id) {
        setSelectedPlan(null);
      }
    } catch (err) {
      alert('削除に失敗しました');
    }
  };

  const openEditModal = (plan) => {
    setEditFormData({ name: plan.name });
    setShowEditModal(true);
  };

  const handleUpdatePlan = async (e) => {
    e.preventDefault();
    if (!selectedPlan) return;

    try {
      const updated = await planApi.update(selectedPlan.id, {
        name: editFormData.name,
      });
      setPlans(plans.map((p) => (p.id === updated.id ? { ...p, name: updated.name } : p)));
      setSelectedPlan({ ...selectedPlan, name: updated.name });
      setShowEditModal(false);
    } catch (err) {
      alert('更新に失敗しました');
    }
  };

  // 履歴に反映
  const handleApplyToHistory = async () => {
    if (!selectedPlan) return;
    setIsApplying(true);
    try {
      const result = await planApi.applyToHistory(selectedPlan.id);
      alert(result.message);
      setShowApplyHistoryModal(false);
    } catch (err) {
      alert(err.response?.data?.detail || '履歴への反映に失敗しました');
    } finally {
      setIsApplying(false);
    }
  };

  // 計画詳細をテーブル形式に変換
  const formatPlanDetails = (plan) => {
    if (!plan.details) return null;

    const fieldMap = {};
    const years = new Set();

    for (const d of plan.details) {
      const fieldId = d.field_id;
      const year = `R${d.year}`;
      years.add(year);

      if (!fieldMap[fieldId]) {
        fieldMap[fieldId] = {
          field_code: d.field_code || `F${fieldId}`,
          crops: {},
        };
      }
      fieldMap[fieldId].crops[year] = d.crop;
    }

    const sortedYears = [...years].sort();
    const rows = Object.values(fieldMap);

    return { rows, years: sortedYears };
  };

  const planDetails = selectedPlan ? formatPlanDetails(selectedPlan) : null;

  return (
    <div className="plans-page">
      <h1>📋 保存済み計画</h1>

      {/* 履歴反映確認モーダル */}
      {showApplyHistoryModal && (
        <div className="modal-overlay">
          <div className="modal">
            <h2>⚠️ 作付履歴に反映</h2>
            <p>
              計画「<strong>{selectedPlan?.name}</strong>」の内容を作付履歴に反映します。
            </p>
            <p style={{ color: '#d32f2f', fontSize: '14px' }}>
              既存の履歴がある年度・ほ場は上書きされます。この操作は取り消せません。
            </p>
            <div className="form-actions">
              <button
                type="button"
                onClick={() => setShowApplyHistoryModal(false)}
                className="btn-secondary"
                disabled={isApplying}
              >
                キャンセル
              </button>
              <button
                type="button"
                onClick={handleApplyToHistory}
                className="btn-primary"
                disabled={isApplying}
              >
                {isApplying ? '反映中...' : '反映する'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 編集モーダル */}
      {showEditModal && (
        <div className="modal-overlay">
          <div className="modal">
            <h2>計画名を編集</h2>
            <form onSubmit={handleUpdatePlan}>
              <div className="form-group">
                <label>計画名 *</label>
                <input
                  type="text"
                  value={editFormData.name}
                  onChange={(e) => setEditFormData({ ...editFormData, name: e.target.value })}
                  required
                  autoFocus
                />
              </div>
              <div className="form-actions">
                <button type="button" onClick={() => setShowEditModal(false)} className="btn-secondary">
                  キャンセル
                </button>
                <button type="submit" className="btn-primary">
                  更新
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      <div className="plans-layout">
        <div className="plans-list">
          <h2>計画一覧</h2>
          {isLoading ? (
            <Spinner text="計画を読み込み中..." size="sm" />
          ) : plans.length === 0 ? (
            <EmptyState message="保存済みの計画がありません" icon="📋" />
          ) : (
            <ul>
              {plans.map((plan) => (
                <li
                  key={plan.id}
                  className={selectedPlan?.id === plan.id ? 'selected' : ''}
                >
                  <div className="plan-info" onClick={() => viewPlan(plan.id)}>
                    <span className="plan-name">{plan.name}</span>
                    <span className="plan-years">
                      R{plan.start_year} - R{plan.end_year}
                    </span>
                  </div>
                  <button
                    onClick={() => deletePlan(plan.id)}
                    className="btn-icon btn-danger"
                  >
                    🗑️
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className="plan-detail">
          {selectedPlan ? (
            <>
              <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '8px' }}>
                <h2 style={{ margin: 0 }}>{selectedPlan.name}</h2>
                <button
                  onClick={() => openEditModal(selectedPlan)}
                  className="btn-secondary btn-sm"
                >
                  ✏️ 編集
                </button>
                <button
                  onClick={() => setShowApplyHistoryModal(true)}
                  className="btn-primary btn-sm"
                  title="計画の内容を作付履歴に登録"
                >
                  📅 履歴に反映
                </button>
              </div>
              <p>
                期間: R{selectedPlan.start_year} - R{selectedPlan.end_year}
              </p>

              {planDetails && (
                <div className="table-wrapper">
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>ほ場</th>
                        {planDetails.years.map((y) => (
                          <th key={y}>{y}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {planDetails.rows.map((row, i) => (
                        <tr key={i}>
                          <td>{row.field_code}</td>
                          {planDetails.years.map((y) => (
                            <td key={y}>
                              <span className="crop-badge">{row.crops[y] || '-'}</span>
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </>
          ) : (
            <EmptyState message="計画を選択してください" icon="👈" />
          )}
        </div>
      </div>
    </div>
  );
}
