/**
 * ほ場一覧ページ
 * 作付履歴表示・追加機能付き
 */

import { useEffect, useState } from 'react';
import { useFieldStore } from '../store/fieldStore';
import { fieldApi } from '../lib/api';

export default function Fields() {
  const { fields, fetchFields, createField, updateField, deleteField, isLoading } = useFieldStore();
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [formData, setFormData] = useState({
    field_code: '',
    field_name: '',
    district: '',
    area_ha: '',
    beet_forbidden: false,
  });

  // 作付履歴関連
  const [showHistoryModal, setShowHistoryModal] = useState(false);
  const [selectedFieldId, setSelectedFieldId] = useState(null);
  const [history, setHistory] = useState([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyForm, setHistoryForm] = useState({ year: new Date().getFullYear() - 1, crop: '' });

  useEffect(() => {
    fetchFields();
  }, [fetchFields]);

  const resetForm = () => {
    setFormData({
      field_code: '',
      field_name: '',
      district: '',
      area_ha: '',
      beet_forbidden: false,
    });
    setEditingId(null);
    setShowForm(false);
  };

  const handleEdit = (field) => {
    setFormData({
      field_code: field.field_code,
      field_name: field.field_name || '',
      district: field.district || '',
      area_ha: field.area_ha.toString(),
      beet_forbidden: field.beet_forbidden || false,
    });
    setEditingId(field.id);
    setShowForm(true);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    const data = {
      ...formData,
      area_ha: parseFloat(formData.area_ha),
    };

    try {
      if (editingId) {
        await updateField(editingId, data);
      } else {
        await createField(data);
      }
      resetForm();
    } catch (err) {
      alert(err.message);
    }
  };

  const handleDelete = async (id) => {
    if (confirm('このほ場を削除しますか？')) {
      try {
        await deleteField(id);
      } catch (err) {
        alert(err.message);
      }
    }
  };

  // 作付履歴関連
  const handleShowHistory = async (fieldId) => {
    setSelectedFieldId(fieldId);
    setShowHistoryModal(true);
    setHistoryLoading(true);
    try {
      const data = await fieldApi.getHistory(fieldId);
      setHistory(data);
    } catch (err) {
      console.error('Failed to load history:', err);
    } finally {
      setHistoryLoading(false);
    }
  };

  const handleAddHistory = async (e) => {
    e.preventDefault();
    try {
      await fieldApi.addHistory(selectedFieldId, historyForm.year, historyForm.crop);
      const data = await fieldApi.getHistory(selectedFieldId);
      setHistory(data);
      setHistoryForm({ year: new Date().getFullYear() - 1, crop: '' });
    } catch (err) {
      alert('追加に失敗しました');
    }
  };

  const closeHistoryModal = () => {
    setShowHistoryModal(false);
    setSelectedFieldId(null);
    setHistory([]);
  };

  const getFieldName = (fieldId) => {
    const field = fields.find((f) => f.id === fieldId);
    return field ? (field.field_name || field.field_code) : '';
  };

  const years = Array.from({ length: 10 }, (_, i) => new Date().getFullYear() - 1 - i);

  return (
    <div className="fields-page">
      <div className="page-header">
        <h1>🗺️ ほ場一覧</h1>
        <button onClick={() => setShowForm(true)} className="btn-primary">
          + 新規ほ場
        </button>
      </div>

      {showForm && (
        <div className="modal-overlay">
          <div className="modal">
            <h2>{editingId ? 'ほ場編集' : '新規ほ場'}</h2>
            <form onSubmit={handleSubmit}>
              <div className="form-group">
                <label>ほ場コード *</label>
                <input
                  type="text"
                  value={formData.field_code}
                  onChange={(e) => setFormData({ ...formData, field_code: e.target.value })}
                  required
                />
              </div>
              <div className="form-group">
                <label>ほ場名</label>
                <input
                  type="text"
                  value={formData.field_name}
                  onChange={(e) => setFormData({ ...formData, field_name: e.target.value })}
                />
              </div>
              <div className="form-group">
                <label>地区</label>
                <input
                  type="text"
                  value={formData.district}
                  onChange={(e) => setFormData({ ...formData, district: e.target.value })}
                />
              </div>
              <div className="form-group">
                <label>面積 (ha) *</label>
                <input
                  type="number"
                  step="0.01"
                  min="0.01"
                  value={formData.area_ha}
                  onChange={(e) => setFormData({ ...formData, area_ha: e.target.value })}
                  required
                />
              </div>
              <div className="form-group checkbox">
                <label>
                  <input
                    type="checkbox"
                    checked={formData.beet_forbidden}
                    onChange={(e) => setFormData({ ...formData, beet_forbidden: e.target.checked })}
                  />
                  てんさい・馬鈴薯禁止
                </label>
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

      {/* 作付履歴モーダル */}
      {showHistoryModal && (
        <div className="modal-overlay">
          <div className="modal modal-lg">
            <h2>📅 作付履歴 - {getFieldName(selectedFieldId)}</h2>

            <form onSubmit={handleAddHistory} className="history-form">
              <div className="form-row">
                <div className="form-group">
                  <label>年</label>
                  <select
                    value={historyForm.year}
                    onChange={(e) => setHistoryForm({ ...historyForm, year: parseInt(e.target.value) })}
                  >
                    {years.map((y) => (
                      <option key={y} value={y}>{y}年</option>
                    ))}
                  </select>
                </div>
                <div className="form-group">
                  <label>作物</label>
                  <input
                    type="text"
                    value={historyForm.crop}
                    onChange={(e) => setHistoryForm({ ...historyForm, crop: e.target.value })}
                    placeholder="例: 馬鈴薯"
                    required
                  />
                </div>
                <button type="submit" className="btn-primary">
                  追加
                </button>
              </div>
            </form>

            {historyLoading ? (
              <p>読み込み中...</p>
            ) : history.length === 0 ? (
              <p className="empty-message">作付履歴がありません</p>
            ) : (
              <table className="data-table">
                <thead>
                  <tr>
                    <th>年</th>
                    <th>作物</th>
                  </tr>
                </thead>
                <tbody>
                  {history.sort((a, b) => b.year - a.year).map((h) => (
                    <tr key={h.id}>
                      <td>{h.year}年</td>
                      <td>{h.crop}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}

            <div className="form-actions">
              <button type="button" onClick={closeHistoryModal} className="btn-secondary">
                閉じる
              </button>
            </div>
          </div>
        </div>
      )}

      {isLoading ? (
        <p>読み込み中...</p>
      ) : fields.length === 0 ? (
        <p className="empty-message">ほ場が登録されていません</p>
      ) : (
        <table className="data-table">
          <thead>
            <tr>
              <th>コード</th>
              <th>名前</th>
              <th>地区</th>
              <th>面積(ha)</th>
              <th>制限</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            {fields.map((field) => (
              <tr key={field.id}>
                <td>{field.field_code}</td>
                <td>{field.field_name || '-'}</td>
                <td>{field.district || '-'}</td>
                <td>{field.area_ha.toFixed(2)}</td>
                <td>{field.beet_forbidden ? '🚫てんさい/馬鈴薯' : '-'}</td>
                <td>
                  <button onClick={() => handleShowHistory(field.id)} className="btn-icon" title="作付履歴">
                    📅
                  </button>
                  <button onClick={() => handleEdit(field)} className="btn-icon" title="編集">
                    ✏️
                  </button>
                  <button onClick={() => handleDelete(field.id)} className="btn-icon btn-danger" title="削除">
                    🗑️
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
