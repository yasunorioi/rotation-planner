/**
 * 保存済み計画ページ
 */

import { useEffect, useState } from 'react';
import { planApi } from '../lib/api';

export default function Plans() {
  const [plans, setPlans] = useState([]);
  const [selectedPlan, setSelectedPlan] = useState(null);
  const [isLoading, setIsLoading] = useState(true);

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

      <div className="plans-layout">
        <div className="plans-list">
          <h2>計画一覧</h2>
          {isLoading ? (
            <p>読み込み中...</p>
          ) : plans.length === 0 ? (
            <p className="empty-message">保存済みの計画がありません</p>
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
              <h2>{selectedPlan.name}</h2>
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
            <p className="empty-message">計画を選択してください</p>
          )}
        </div>
      </div>
    </div>
  );
}
