/**
 * 防除記録ページ
 * APIのPesticideRecordCreateモデルに合わせたフォーム
 */

import { useEffect, useState } from 'react';
import { pesticideRecordApi, fieldApi, cropApi } from '../lib/api';

export default function PesticideRecords() {
  const [records, setRecords] = useState([]);
  const [fields, setFields] = useState([]);
  const [crops, setCrops] = useState([]);
  const [selectedYear, setSelectedYear] = useState(new Date().getFullYear());
  const [selectedFieldId, setSelectedFieldId] = useState(null);
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [formData, setFormData] = useState({
    field_id: '',
    date: '',
    pesticide_name: '',
    crop: '',
    target_pest: '',
    dilution_rate: '',
    area_ha: '',
    quantity: '',
    unit: 'L',
    weather: '',
    temperature: '',
    operator: '',
    notes: '',
  });
  const [isLoading, setIsLoading] = useState(true);

  const years = Array.from({ length: 5 }, (_, i) => new Date().getFullYear() - 2 + i);

  useEffect(() => {
    loadFields();
    loadCrops();
  }, []);

  useEffect(() => {
    loadRecords();
  }, [selectedYear, selectedFieldId]);

  const loadRecords = async () => {
    setIsLoading(true);
    try {
      const data = await pesticideRecordApi.list(selectedYear, selectedFieldId);
      setRecords(data);
    } catch (err) {
      console.error('Failed to load records:', err);
    } finally {
      setIsLoading(false);
    }
  };

  const loadFields = async () => {
    try {
      const data = await fieldApi.list();
      setFields(data);
    } catch (err) {
      console.error('Failed to load fields:', err);
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
      field_id: '',
      date: '',
      pesticide_name: '',
      crop: '',
      target_pest: '',
      dilution_rate: '',
      area_ha: '',
      quantity: '',
      unit: 'L',
      weather: '',
      temperature: '',
      operator: '',
      notes: '',
    });
    setEditingId(null);
    setShowForm(false);
  };

  const handleEdit = (record) => {
    setFormData({
      field_id: record.field_id.toString(),
      date: record.date,
      pesticide_name: record.pesticide_name || '',
      crop: record.crop || '',
      target_pest: record.target_pest || '',
      dilution_rate: record.dilution_rate || '',
      area_ha: record.area_ha?.toString() || '',
      quantity: record.quantity?.toString() || '',
      unit: record.unit || 'L',
      weather: record.weather || '',
      temperature: record.temperature?.toString() || '',
      operator: record.operator || '',
      notes: record.notes || '',
    });
    setEditingId(record.id);
    setShowForm(true);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    const data = {
      field_id: parseInt(formData.field_id),
      date: formData.date,
      pesticide_name: formData.pesticide_name,
      crop: formData.crop,
      target_pest: formData.target_pest || null,
      dilution_rate: formData.dilution_rate || null,
      area_ha: formData.area_ha ? parseFloat(formData.area_ha) : null,
      quantity: formData.quantity ? parseFloat(formData.quantity) : null,
      unit: formData.unit || null,
      weather: formData.weather || null,
      temperature: formData.temperature ? parseFloat(formData.temperature) : null,
      operator: formData.operator || null,
      notes: formData.notes || null,
    };
    try {
      if (editingId) {
        await pesticideRecordApi.update(editingId, data);
      } else {
        await pesticideRecordApi.create(data);
      }
      resetForm();
      loadRecords();
    } catch (err) {
      alert(editingId ? '更新に失敗しました' : '作成に失敗しました');
    }
  };

  const handleDelete = async (id) => {
    if (confirm('この記録を削除しますか？')) {
      try {
        await pesticideRecordApi.delete(id);
        loadRecords();
      } catch (err) {
        alert('削除に失敗しました');
      }
    }
  };

  const handleExportCsv = () => {
    window.open(pesticideRecordApi.exportCsv(selectedYear), '_blank');
  };

  const getFieldName = (fieldId) => {
    const field = fields.find((f) => f.id === fieldId);
    return field ? (field.field_name || field.field_code) : '不明';
  };

  return (
    <div className="pesticide-records-page">
      <div className="page-header">
        <h1>📋 防除記録</h1>
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
          <select
            value={selectedFieldId || ''}
            onChange={(e) => setSelectedFieldId(e.target.value ? parseInt(e.target.value) : null)}
            className="field-select"
          >
            <option value="">全てのほ場</option>
            {fields.map((f) => (
              <option key={f.id} value={f.id}>{f.field_name || f.field_code}</option>
            ))}
          </select>
          <button onClick={handleExportCsv} className="btn-secondary">
            📥 CSV出力
          </button>
          <button onClick={() => setShowForm(true)} className="btn-primary">
            + 新規記録
          </button>
        </div>
      </div>

      {showForm && (
        <div className="modal-overlay">
          <div className="modal modal-lg">
            <h2>{editingId ? '防除記録編集' : '新規防除記録'}</h2>
            <form onSubmit={handleSubmit}>
              <div className="form-row">
                <div className="form-group">
                  <label>ほ場 *</label>
                  <select
                    value={formData.field_id}
                    onChange={(e) => setFormData({ ...formData, field_id: e.target.value })}
                    required
                  >
                    <option value="">選択してください</option>
                    {fields.map((f) => (
                      <option key={f.id} value={f.id}>{f.field_name || f.field_code}</option>
                    ))}
                  </select>
                </div>
                <div className="form-group">
                  <label>散布日 *</label>
                  <input
                    type="date"
                    value={formData.date}
                    onChange={(e) => setFormData({ ...formData, date: e.target.value })}
                    required
                  />
                </div>
              </div>
              <div className="form-row">
                <div className="form-group">
                  <label>農薬名 *</label>
                  <input
                    type="text"
                    value={formData.pesticide_name}
                    onChange={(e) => setFormData({ ...formData, pesticide_name: e.target.value })}
                    placeholder="例: ダコニール1000"
                    required
                  />
                </div>
                <div className="form-group">
                  <label>作物 *</label>
                  <select
                    value={formData.crop}
                    onChange={(e) => setFormData({ ...formData, crop: e.target.value })}
                    required
                  >
                    <option value="">選択してください</option>
                    {crops.map((c) => (
                      <option key={c.crop_id} value={c.crop_name}>
                        {c.custom_name || c.crop_name}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
              <div className="form-row">
                <div className="form-group">
                  <label>対象病害虫</label>
                  <input
                    type="text"
                    value={formData.target_pest}
                    onChange={(e) => setFormData({ ...formData, target_pest: e.target.value })}
                    placeholder="例: 疫病"
                  />
                </div>
                <div className="form-group">
                  <label>希釈倍率</label>
                  <input
                    type="text"
                    value={formData.dilution_rate}
                    onChange={(e) => setFormData({ ...formData, dilution_rate: e.target.value })}
                    placeholder="例: 1000倍"
                  />
                </div>
              </div>
              <div className="form-row">
                <div className="form-group">
                  <label>面積 (ha)</label>
                  <input
                    type="number"
                    step="0.01"
                    min="0"
                    value={formData.area_ha}
                    onChange={(e) => setFormData({ ...formData, area_ha: e.target.value })}
                  />
                </div>
                <div className="form-group">
                  <label>使用量</label>
                  <input
                    type="number"
                    step="0.1"
                    min="0"
                    value={formData.quantity}
                    onChange={(e) => setFormData({ ...formData, quantity: e.target.value })}
                  />
                </div>
                <div className="form-group">
                  <label>単位</label>
                  <select
                    value={formData.unit}
                    onChange={(e) => setFormData({ ...formData, unit: e.target.value })}
                  >
                    <option value="L">L</option>
                    <option value="kg">kg</option>
                    <option value="ml">ml</option>
                    <option value="g">g</option>
                  </select>
                </div>
              </div>
              <div className="form-row">
                <div className="form-group">
                  <label>天候</label>
                  <select
                    value={formData.weather}
                    onChange={(e) => setFormData({ ...formData, weather: e.target.value })}
                  >
                    <option value="">選択してください</option>
                    <option value="晴れ">晴れ</option>
                    <option value="曇り">曇り</option>
                    <option value="雨">雨</option>
                  </select>
                </div>
                <div className="form-group">
                  <label>気温 (℃)</label>
                  <input
                    type="number"
                    step="0.1"
                    value={formData.temperature}
                    onChange={(e) => setFormData({ ...formData, temperature: e.target.value })}
                    placeholder="例: 25.5"
                  />
                </div>
                <div className="form-group">
                  <label>作業者</label>
                  <input
                    type="text"
                    value={formData.operator}
                    onChange={(e) => setFormData({ ...formData, operator: e.target.value })}
                  />
                </div>
              </div>
              <div className="form-group">
                <label>備考</label>
                <textarea
                  value={formData.notes}
                  onChange={(e) => setFormData({ ...formData, notes: e.target.value })}
                  rows={3}
                />
              </div>
              <div className="form-actions">
                <button type="button" onClick={resetForm} className="btn-secondary">
                  キャンセル
                </button>
                <button type="submit" className="btn-primary">
                  {editingId ? '更新' : '作成'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {isLoading ? (
        <p>読み込み中...</p>
      ) : records.length === 0 ? (
        <p className="empty-message">防除記録がありません</p>
      ) : (
        <div className="table-wrapper">
          <table className="data-table">
            <thead>
              <tr>
                <th>日付</th>
                <th>ほ場</th>
                <th>作物</th>
                <th>農薬名</th>
                <th>対象</th>
                <th>使用量</th>
                <th>天候</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {records.map((record) => (
                <tr key={record.id}>
                  <td>{record.date}</td>
                  <td>{getFieldName(record.field_id)}</td>
                  <td>{record.crop}</td>
                  <td>{record.pesticide_name}</td>
                  <td>{record.target_pest || '-'}</td>
                  <td>{record.quantity ? `${record.quantity} ${record.unit || ''}` : '-'}</td>
                  <td>{record.weather || '-'}</td>
                  <td>
                    <button onClick={() => handleEdit(record)} className="btn-icon">
                      ✏️
                    </button>
                    <button onClick={() => handleDelete(record.id)} className="btn-icon btn-danger">
                      🗑️
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
