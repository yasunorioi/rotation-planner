/**
 * 農薬発注ページ
 * APIのPesticideOrderCreateモデルに合わせたフォーム
 * items: [{pesticide_id, crop, area_ha, quantity, ...}] 形式
 */

import { useEffect, useState } from 'react';
import { pesticideOrderApi, pesticideMasterApi, cropApi } from '../lib/api';

export default function PesticideOrders() {
  const [orders, setOrders] = useState([]);
  const [masters, setMasters] = useState([]);
  const [crops, setCrops] = useState([]);
  const [selectedYear, setSelectedYear] = useState(new Date().getFullYear());
  const [showForm, setShowForm] = useState(false);
  const [formData, setFormData] = useState({
    year: new Date().getFullYear(),
    items: [{ pesticide_name: '', crop: '', quantity: '', unit: '本' }],
  });
  const [isLoading, setIsLoading] = useState(true);

  const years = Array.from({ length: 5 }, (_, i) => new Date().getFullYear() - 2 + i);

  useEffect(() => {
    loadMasters();
    loadCrops();
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
          <button onClick={() => setShowForm(true)} className="btn-primary">
            + 新規発注
          </button>
        </div>
      </div>

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
                            <option key={c.crop_id} value={c.crop_name}>
                              {c.custom_name || c.crop_name}
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

      {isLoading ? (
        <p>読み込み中...</p>
      ) : orders.length === 0 ? (
        <p className="empty-message">{selectedYear}年の発注がありません</p>
      ) : (
        <div className="orders-list">
          {orders.map((order) => (
            <div key={order.id} className="order-card">
              <div className="order-header">
                <span className="order-date">
                  作成: {order.created_at ? new Date(order.created_at).toLocaleDateString() : '-'}
                </span>
                <button onClick={() => handleDelete(order.id)} className="btn-icon btn-danger">
                  🗑️
                </button>
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
