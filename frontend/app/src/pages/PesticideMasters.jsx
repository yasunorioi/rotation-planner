/**
 * 防除マスタページ
 */

import { useEffect, useState } from 'react';
import { pesticideMasterApi, cropApi } from '../lib/api';

export default function PesticideMasters() {
  const [masters, setMasters] = useState([]);
  const [crops, setCrops] = useState([]);
  const [selectedCrop, setSelectedCrop] = useState('');
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [formData, setFormData] = useState({
    name: '',
    crop: '',
    category: '',
    manufacturer: '',
    active_ingredient: '',
    usage_timing: '',
    dilution_rate: '',
    application_method: '',
    safety_interval: '',
    notes: '',
  });
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    loadCrops();
  }, []);

  useEffect(() => {
    loadMasters();
  }, [selectedCrop]);

  const loadMasters = async () => {
    setIsLoading(true);
    try {
      const data = await pesticideMasterApi.list(selectedCrop || null);
      setMasters(data);
    } catch (err) {
      console.error('Failed to load masters:', err);
    } finally {
      setIsLoading(false);
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
      name: '',
      crop: '',
      category: '',
      manufacturer: '',
      active_ingredient: '',
      usage_timing: '',
      dilution_rate: '',
      application_method: '',
      safety_interval: '',
      notes: '',
    });
    setEditingId(null);
    setShowForm(false);
  };

  const handleEdit = (master) => {
    setFormData({
      name: master.name,
      crop: master.crop || '',
      category: master.category || '',
      manufacturer: master.manufacturer || '',
      active_ingredient: master.active_ingredient || '',
      usage_timing: master.usage_timing || '',
      dilution_rate: master.dilution_rate?.toString() || '',
      application_method: master.application_method || '',
      safety_interval: master.safety_interval?.toString() || '',
      notes: master.notes || '',
    });
    setEditingId(master.id);
    setShowForm(true);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    const data = {
      ...formData,
      dilution_rate: formData.dilution_rate ? parseInt(formData.dilution_rate) : null,
      safety_interval: formData.safety_interval ? parseInt(formData.safety_interval) : null,
    };
    try {
      if (editingId) {
        await pesticideMasterApi.update(editingId, data);
      } else {
        await pesticideMasterApi.create(data);
      }
      resetForm();
      loadMasters();
    } catch (err) {
      alert(editingId ? '更新に失敗しました' : '作成に失敗しました');
    }
  };

  const handleDelete = async (id) => {
    if (confirm('この農薬を削除しますか？関連する発注・記録も影響を受ける可能性があります。')) {
      try {
        await pesticideMasterApi.delete(id);
        loadMasters();
      } catch (err) {
        alert('削除に失敗しました');
      }
    }
  };

  const categories = ['殺虫剤', '殺菌剤', '除草剤', '殺虫殺菌剤', 'その他'];

  return (
    <div className="pesticide-masters-page">
      <div className="page-header">
        <h1>💊 防除マスタ</h1>
        <div className="header-actions">
          <select
            value={selectedCrop}
            onChange={(e) => setSelectedCrop(e.target.value)}
            className="crop-select"
          >
            <option value="">全ての作物</option>
            {crops.map((c) => (
              <option key={c.crop_id} value={c.crop_name}>
                {c.custom_name || c.crop_name}
              </option>
            ))}
          </select>
          <button onClick={() => setShowForm(true)} className="btn-primary">
            + 新規農薬
          </button>
        </div>
      </div>

      {showForm && (
        <div className="modal-overlay">
          <div className="modal modal-lg">
            <h2>{editingId ? '農薬編集' : '新規農薬'}</h2>
            <form onSubmit={handleSubmit}>
              <div className="form-row">
                <div className="form-group">
                  <label>農薬名 *</label>
                  <input
                    type="text"
                    value={formData.name}
                    onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                    required
                  />
                </div>
                <div className="form-group">
                  <label>対象作物</label>
                  <input
                    type="text"
                    value={formData.crop}
                    onChange={(e) => setFormData({ ...formData, crop: e.target.value })}
                    placeholder="例: 馬鈴薯"
                  />
                </div>
              </div>
              <div className="form-row">
                <div className="form-group">
                  <label>カテゴリ</label>
                  <select
                    value={formData.category}
                    onChange={(e) => setFormData({ ...formData, category: e.target.value })}
                  >
                    <option value="">選択してください</option>
                    {categories.map((c) => (
                      <option key={c} value={c}>{c}</option>
                    ))}
                  </select>
                </div>
                <div className="form-group">
                  <label>メーカー</label>
                  <input
                    type="text"
                    value={formData.manufacturer}
                    onChange={(e) => setFormData({ ...formData, manufacturer: e.target.value })}
                  />
                </div>
              </div>
              <div className="form-group">
                <label>有効成分</label>
                <input
                  type="text"
                  value={formData.active_ingredient}
                  onChange={(e) => setFormData({ ...formData, active_ingredient: e.target.value })}
                />
              </div>
              <div className="form-row">
                <div className="form-group">
                  <label>使用時期</label>
                  <input
                    type="text"
                    value={formData.usage_timing}
                    onChange={(e) => setFormData({ ...formData, usage_timing: e.target.value })}
                    placeholder="例: 萌芽前"
                  />
                </div>
                <div className="form-group">
                  <label>散布方法</label>
                  <input
                    type="text"
                    value={formData.application_method}
                    onChange={(e) => setFormData({ ...formData, application_method: e.target.value })}
                    placeholder="例: 茎葉散布"
                  />
                </div>
              </div>
              <div className="form-row">
                <div className="form-group">
                  <label>希釈倍率</label>
                  <input
                    type="number"
                    value={formData.dilution_rate}
                    onChange={(e) => setFormData({ ...formData, dilution_rate: e.target.value })}
                    placeholder="例: 1000"
                  />
                </div>
                <div className="form-group">
                  <label>安全使用基準（日）</label>
                  <input
                    type="number"
                    value={formData.safety_interval}
                    onChange={(e) => setFormData({ ...formData, safety_interval: e.target.value })}
                    placeholder="例: 14"
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
      ) : masters.length === 0 ? (
        <p className="empty-message">農薬が登録されていません</p>
      ) : (
        <table className="data-table">
          <thead>
            <tr>
              <th>農薬名</th>
              <th>対象作物</th>
              <th>カテゴリ</th>
              <th>メーカー</th>
              <th>希釈倍率</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            {masters.map((master) => (
              <tr key={master.id}>
                <td>{master.name}</td>
                <td>{master.crop || '-'}</td>
                <td>{master.category || '-'}</td>
                <td>{master.manufacturer || '-'}</td>
                <td>{master.dilution_rate ? `${master.dilution_rate}倍` : '-'}</td>
                <td>
                  <button onClick={() => handleEdit(master)} className="btn-icon">
                    ✏️
                  </button>
                  <button onClick={() => handleDelete(master.id)} className="btn-icon btn-danger">
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
