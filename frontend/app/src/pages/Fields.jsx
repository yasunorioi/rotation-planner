/**
 * ほ場一覧ページ
 */

import { useEffect, useState } from 'react';
import { useFieldStore } from '../store/fieldStore';

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
                  <button onClick={() => handleEdit(field)} className="btn-icon">
                    ✏️
                  </button>
                  <button onClick={() => handleDelete(field.id)} className="btn-icon btn-danger">
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
