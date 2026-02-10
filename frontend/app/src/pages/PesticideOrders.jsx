/**
 * 農薬発注ページ
 * APIのPesticideOrderCreateモデルに合わせたフォーム
 * items: [{pesticide_id, crop, area_ha, quantity, ...}] 形式
 *
 * 機能:
 * - 手動発注入力
 * - 輪作計画から自動計算
 */

import { useEffect, useState } from 'react';
import { pesticideOrderApi, pesticideMasterApi, cropApi, planApi } from '../lib/api';
import { Spinner } from '../components/Loading';
import { EmptyState } from '../components/ErrorMessage';

export default function PesticideOrders() {
  const [orders, setOrders] = useState([]);
  const [masters, setMasters] = useState([]);
  const [crops, setCrops] = useState([]);
  const [plans, setPlans] = useState([]);
  const [selectedYear, setSelectedYear] = useState(new Date().getFullYear());
  const [showForm, setShowForm] = useState(false);
  const [formData, setFormData] = useState({
    year: new Date().getFullYear(),
    items: [{ pesticide_name: '', crop: '', quantity: '', unit: '本' }],
  });
  const [isLoading, setIsLoading] = useState(true);

  // 自動計算用の状態
  const [showCalculator, setShowCalculator] = useState(false);
  const [selectedPlanId, setSelectedPlanId] = useState('');
  const [calcYear, setCalcYear] = useState(new Date().getFullYear());
  const [calculatedItems, setCalculatedItems] = useState([]);
  const [calcMessage, setCalcMessage] = useState('');
  const [isCalculating, setIsCalculating] = useState(false);

  // 編集用の状態
  const [editingOrder, setEditingOrder] = useState(null);
  const [showEditForm, setShowEditForm] = useState(false);
  const [editFormData, setEditFormData] = useState({
    items: [],
  });

  const years = Array.from({ length: 5 }, (_, i) => new Date().getFullYear() - 2 + i);

  useEffect(() => {
    loadMasters();
    loadCrops();
    loadPlans();
  }, []);

  useEffect(() => {
    loadOrders();
  }, [selectedYear]);

  const loadOrders = async () => {
    setIsLoading(true);
    try {
      const data = await pesticideOrderApi.list(selectedYear);
      setOrders(data);
    } catch (err) {
      console.error('Failed to load orders:', err);
    } finally {
      setIsLoading(false);
    }
  };

  const loadMasters = async () => {
    try {
      const data = await pesticideMasterApi.list();
      setMasters(data);
    } catch (err) {
      console.error('Failed to load masters:', err);
    }
  };

  const loadCrops = async () => {
    try {
      const data = await cropApi.listUserCrops();
      setCrops(data);
    } catch (err) {
      console.error('Failed to load crops:', err);
    }
  };

  const loadPlans = async () => {
    try {
      const data = await planApi.list();
      setPlans(data);
    } catch (err) {
      console.error('Failed to load plans:', err);
    }
  };

  const resetForm = () => {
    setFormData({
      year: selectedYear,
      items: [{ pesticide_name: '', crop: '', quantity: '', unit: '本' }],
    });
    setShowForm(false);
  };

  const handleAddItem = () => {
    setFormData({
      ...formData,
      items: [...formData.items, { pesticide_name: '', crop: '', quantity: '', unit: '本' }],
    });
  };

  const handleRemoveItem = (index) => {
    if (formData.items.length > 1) {
      setFormData({
        ...formData,
        items: formData.items.filter((_, i) => i !== index),
      });
    }
  };

  const handleItemChange = (index, field, value) => {
    const newItems = [...formData.items];
    newItems[index] = { ...newItems[index], [field]: value };
    setFormData({ ...formData, items: newItems });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      const items = formData.items.map((item) => ({
        pesticide_name: item.pesticide_name,
        crop: item.crop,
        quantity: parseFloat(item.quantity),
        unit: item.unit,
      }));
      await pesticideOrderApi.create({
        year: formData.year,
        items,
      });
      resetForm();
      loadOrders();
    } catch (err) {
      alert('作成に失敗しました');
    }
  };

  const handleDelete = async (id) => {
    if (confirm('この発注を削除しますか？')) {
      try {
        await pesticideOrderApi.delete(id);
        loadOrders();
      } catch (err) {
        alert('削除に失敗しました');
      }
    }
  };

  // =========================================================================
  // 編集機能
  // =========================================================================

  const openEditForm = (order) => {
    setEditingOrder(order);
    setEditFormData({
      items: (order.items || []).map((item) => ({
        pesticide_name: item.pesticide_name || '',
        crop: item.crop || '',
        quantity: item.quantity?.toString() || '',
        unit: item.unit || '本',
      })),
    });
    setShowEditForm(true);
  };

  const resetEditForm = () => {
    setEditingOrder(null);
    setEditFormData({ items: [] });
    setShowEditForm(false);
  };

  const handleEditItemChange = (index, field, value) => {
    const newItems = [...editFormData.items];
    newItems[index] = { ...newItems[index], [field]: value };
    setEditFormData({ ...editFormData, items: newItems });
  };

  const handleEditSubmit = async (e) => {
    e.preventDefault();
    if (!editingOrder) return;

    try {
      const items = editFormData.items.map((item) => ({
        pesticide_name: item.pesticide_name,
        crop: item.crop,
        quantity: parseFloat(item.quantity),
        unit: item.unit,
      }));
      await pesticideOrderApi.update(editingOrder.id, { items });
      resetEditForm();
      loadOrders();
    } catch (err) {
      alert('更新に失敗しました');
    }
  };

  // =========================================================================
  // 自動計算機能
  // =========================================================================

  const resetCalculator = () => {
    setShowCalculator(false);
    setSelectedPlanId('');
    setCalculatedItems([]);
    setCalcMessage('');
  };

  const handleCalculate = async () => {
    if (!selectedPlanId) {
      alert('計画を選択してください');
      return;
    }

    setIsCalculating(true);
    setCalculatedItems([]);
    setCalcMessage('');

    try {
      const result = await pesticideOrderApi.calculateFromPlan(
        parseInt(selectedPlanId),
        calcYear
      );
      setCalculatedItems(result.items || []);
      setCalcMessage(result.message || '計算完了');
    } catch (err) {
      const errorMsg = err.response?.data?.detail || '計算に失敗しました';
      setCalcMessage(`エラー: ${errorMsg}`);
    } finally {
      setIsCalculating(false);
    }
  };

  const handleRegisterCalculated = async () => {
    if (calculatedItems.length === 0) {
      alert('計算結果がありません');
      return;
    }

    try {
      const items = calculatedItems.map((item) => ({
        pesticide_name: item.pesticide_name,
        crop: item.crop,
        quantity: item.quantity,
        unit: item.unit,
        area_ha: item.area_ha,
        target_pest: item.target_pest,
        dilution_rate: item.dilution_rate,
      }));

      await pesticideOrderApi.create({
        plan_id: parseInt(selectedPlanId),
        year: calcYear,
        items,
      });

      alert('発注を登録しました');
      resetCalculator();
      setSelectedYear(calcYear);
      loadOrders();
    } catch (err) {
      alert('登録に失敗しました');
    }
  };

  return (
    <div className="pesticide-orders-page">
      <div className="page-header">
        <h1>📦 農薬発注</h1>
        <div className="header-actions">
          <select
            value={selectedYear}
            onChange={(e) => setSelectedYear(parseInt(e.target.value))}
            className="year-select"
          >
            {years.map((y) => (
              <option key={y} value={y}>{y}年</option>
            ))}
          </select>
          <button onClick={() => setShowCalculator(true)} className="btn-secondary">
            🧮 計画から自動計算
          </button>
          <a
            href={`http://localhost:8000/api/pesticide-orders/export/csv?year=${selectedYear}`}
            className="btn-secondary"
            download
          >
            📄 CSV出力
          </a>
          <a
            href={`http://localhost:8000/api/pesticide-orders/export/pdf?year=${selectedYear}`}
            className="btn-secondary"
            download
          >
            📑 PDF出力
          </a>
          <button onClick={() => setShowForm(true)} className="btn-primary">
            + 新規発注
          </button>
        </div>
      </div>

      {/* 自動計算モーダル */}
      {showCalculator && (
        <div className="modal-overlay">
          <div className="modal modal-lg">
            <h2>🧮 輪作計画から農薬必要量を計算</h2>

            <div className="calculator-form">
              <div className="form-row">
                <div className="form-group">
                  <label>輪作計画 *</label>
                  <select
                    value={selectedPlanId}
                    onChange={(e) => setSelectedPlanId(e.target.value)}
                  >
                    <option value="">計画を選択してください</option>
                    {plans.map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.name} ({p.start_year}年〜)
                      </option>
                    ))}
                  </select>
                </div>
                <div className="form-group">
                  <label>対象年度 *</label>
                  <select
                    value={calcYear}
                    onChange={(e) => setCalcYear(parseInt(e.target.value))}
                  >
                    {years.map((y) => (
                      <option key={y} value={y}>{y}年</option>
                    ))}
                  </select>
                </div>
                <div className="form-group" style={{ alignSelf: 'flex-end' }}>
                  <button
                    onClick={handleCalculate}
                    className="btn-primary"
                    disabled={isCalculating || !selectedPlanId}
                  >
                    {isCalculating ? '計算中...' : '計算実行'}
                  </button>
                </div>
              </div>
            </div>

            {calcMessage && (
              <div className={`calc-message ${calcMessage.startsWith('エラー') ? 'error' : 'success'}`}>
                {calcMessage}
              </div>
            )}

            {calculatedItems.length > 0 && (
              <div className="calculated-results">
                <h3>計算結果プレビュー ({calculatedItems.length}件)</h3>
                <div className="table-container">
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>農薬名</th>
                        <th>対象作物</th>
                        <th>面積(ha)</th>
                        <th>必要量</th>
                        <th>単位</th>
                        <th>対象病害虫</th>
                      </tr>
                    </thead>
                    <tbody>
                      {calculatedItems.map((item, idx) => (
                        <tr key={idx}>
                          <td>{item.pesticide_name}</td>
                          <td>{item.crop}</td>
                          <td>{item.area_ha.toFixed(2)}</td>
                          <td>{item.quantity.toFixed(2)}</td>
                          <td>{item.unit}</td>
                          <td>{item.target_pest || '-'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            <div className="form-actions">
              <button type="button" onClick={resetCalculator} className="btn-secondary">
                閉じる
              </button>
              {calculatedItems.length > 0 && (
                <button
                  type="button"
                  onClick={handleRegisterCalculated}
                  className="btn-primary"
                >
                  📝 この内容で発注登録
                </button>
              )}
            </div>
          </div>
        </div>
      )}

      {/* 手動入力モーダル */}
      {showForm && (
        <div className="modal-overlay">
          <div className="modal modal-lg">
            <h2>新規農薬発注</h2>
            <form onSubmit={handleSubmit}>
              <div className="form-group">
                <label>年度 *</label>
                <select
                  value={formData.year}
                  onChange={(e) => setFormData({ ...formData, year: parseInt(e.target.value) })}
                  required
                >
                  {years.map((y) => (
                    <option key={y} value={y}>{y}年</option>
                  ))}
                </select>
              </div>

              <div className="order-items-section">
                <h3>発注明細</h3>
                {formData.items.map((item, index) => (
                  <div key={index} className="order-item-row">
                    <div className="form-row">
                      <div className="form-group">
                        <label>農薬名 *</label>
                        <input
                          type="text"
                          value={item.pesticide_name}
                          onChange={(e) => handleItemChange(index, 'pesticide_name', e.target.value)}
                          placeholder="例: ダコニール1000"
                          required
                          list="pesticide-suggestions"
                        />
                      </div>
                      <div className="form-group">
                        <label>対象作物</label>
                        <select
                          value={item.crop}
                          onChange={(e) => handleItemChange(index, 'crop', e.target.value)}
                        >
                          <option value="">選択してください</option>
                          {crops.map((c) => (
                            <option key={c.id || c.crop_id} value={c.name || c.crop_name}>
                              {c.custom_name || c.name || c.crop_name}
                            </option>
                          ))}
                        </select>
                      </div>
                      <div className="form-group">
                        <label>数量 *</label>
                        <input
                          type="number"
                          step="0.1"
                          min="0.1"
                          value={item.quantity}
                          onChange={(e) => handleItemChange(index, 'quantity', e.target.value)}
                          required
                        />
                      </div>
                      <div className="form-group">
                        <label>単位</label>
                        <select
                          value={item.unit}
                          onChange={(e) => handleItemChange(index, 'unit', e.target.value)}
                        >
                          <option value="本">本</option>
                          <option value="袋">袋</option>
                          <option value="kg">kg</option>
                          <option value="L">L</option>
                        </select>
                      </div>
                      {formData.items.length > 1 && (
                        <button
                          type="button"
                          onClick={() => handleRemoveItem(index)}
                          className="btn-icon btn-danger"
                        >
                          ✕
                        </button>
                      )}
                    </div>
                  </div>
                ))}
                <button type="button" onClick={handleAddItem} className="btn-secondary btn-sm">
                  + 明細追加
                </button>
              </div>

              {/* 農薬名候補 */}
              <datalist id="pesticide-suggestions">
                {masters.map((m) => (
                  <option key={m.id} value={m.name} />
                ))}
              </datalist>

              <div className="form-actions">
                <button type="button" onClick={resetForm} className="btn-secondary">
                  キャンセル
                </button>
                <button type="submit" className="btn-primary">
                  作成
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* 編集モーダル */}
      {showEditForm && editingOrder && (
        <div className="modal-overlay">
          <div className="modal modal-lg">
            <h2>発注内容を編集</h2>
            <form onSubmit={handleEditSubmit}>
              <div className="order-items-section">
                <h3>発注明細</h3>
                {editFormData.items.map((item, index) => (
                  <div key={index} className="order-item-row">
                    <div className="form-row">
                      <div className="form-group">
                        <label>農薬名 *</label>
                        <input
                          type="text"
                          value={item.pesticide_name}
                          onChange={(e) => handleEditItemChange(index, 'pesticide_name', e.target.value)}
                          required
                          list="pesticide-suggestions-edit"
                        />
                      </div>
                      <div className="form-group">
                        <label>対象作物</label>
                        <select
                          value={item.crop}
                          onChange={(e) => handleEditItemChange(index, 'crop', e.target.value)}
                        >
                          <option value="">選択してください</option>
                          {crops.map((c) => (
                            <option key={c.id || c.crop_id} value={c.name || c.crop_name}>
                              {c.custom_name || c.name || c.crop_name}
                            </option>
                          ))}
                        </select>
                      </div>
                      <div className="form-group">
                        <label>数量 *</label>
                        <input
                          type="number"
                          step="0.1"
                          min="0.1"
                          value={item.quantity}
                          onChange={(e) => handleEditItemChange(index, 'quantity', e.target.value)}
                          required
                        />
                      </div>
                      <div className="form-group">
                        <label>単位</label>
                        <select
                          value={item.unit}
                          onChange={(e) => handleEditItemChange(index, 'unit', e.target.value)}
                        >
                          <option value="本">本</option>
                          <option value="袋">袋</option>
                          <option value="kg">kg</option>
                          <option value="L">L</option>
                        </select>
                      </div>
                    </div>
                  </div>
                ))}
              </div>

              <datalist id="pesticide-suggestions-edit">
                {masters.map((m) => (
                  <option key={m.id} value={m.name} />
                ))}
              </datalist>

              <div className="form-actions">
                <button type="button" onClick={resetEditForm} className="btn-secondary">
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

      {isLoading ? (
        <Spinner text="発注データを読み込み中..." />
      ) : orders.length === 0 ? (
        <EmptyState message={`${selectedYear}年の発注がありません`} icon="📦" />
      ) : (
        <div className="orders-list">
          {orders.map((order) => (
            <div key={order.id} className="order-card">
              <div className="order-header">
                <span className="order-date">
                  作成: {order.created_at ? new Date(order.created_at).toLocaleDateString() : '-'}
                </span>
                <div style={{ display: 'flex', gap: '4px' }}>
                  <button onClick={() => openEditForm(order)} className="btn-icon">
                    ✏️
                  </button>
                  <button onClick={() => handleDelete(order.id)} className="btn-icon btn-danger">
                    🗑️
                  </button>
                </div>
              </div>
              <table className="data-table">
                <thead>
                  <tr>
                    <th>農薬名</th>
                    <th>対象作物</th>
                    <th>数量</th>
                    <th>単位</th>
                  </tr>
                </thead>
                <tbody>
                  {(order.items || []).map((item, idx) => (
                    <tr key={idx}>
                      <td>{item.pesticide_name || '-'}</td>
                      <td>{item.crop || '-'}</td>
                      <td>{item.quantity}</td>
                      <td>{item.unit || '-'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
