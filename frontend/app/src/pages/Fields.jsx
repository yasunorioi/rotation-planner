/**
 * ほ場一覧ページ
 * 作付履歴表示・追加機能付き
 * 年度別作物マトリクス表示・編集機能
 */

import { useEffect, useState, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { useFieldStore } from '../store/fieldStore';
import { fieldApi, cropApi } from '../lib/api';
import { Spinner, TableSkeleton } from '../components/Loading';
import { EmptyState } from '../components/ErrorMessage';

// 認証付きファイルダウンロード
const downloadWithAuth = async (url, filename) => {
  const token = localStorage.getItem('token');
  const response = await fetch(url, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!response.ok) {
    throw new Error('ダウンロードに失敗しました');
  }
  const blob = await response.blob();
  const link = document.createElement('a');
  link.href = URL.createObjectURL(blob);
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(link.href);
};

export default function Fields() {
  const navigate = useNavigate();
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

  // ほ場選択（農薬発注用）
  const [selectedFieldIds, setSelectedFieldIds] = useState(new Set());

  // 作付履歴関連
  const [showHistoryModal, setShowHistoryModal] = useState(false);
  const [selectedFieldId, setSelectedFieldId] = useState(null);
  const [history, setHistory] = useState([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyForm, setHistoryForm] = useState({ year: new Date().getFullYear(), crop: '' });

  // 年度別表示関連
  const currentYear = new Date().getFullYear();
  const [startYear, setStartYear] = useState(currentYear - 2);
  const [endYear, setEndYear] = useState(currentYear + 2);
  const [showYearlyView, setShowYearlyView] = useState(false);
  const [allHistory, setAllHistory] = useState({}); // { fieldId: { year: crop } }
  const [isLoadingHistory, setIsLoadingHistory] = useState(false);

  // 年度別作物編集モーダル
  const [showCropEditModal, setShowCropEditModal] = useState(false);
  const [editingCell, setEditingCell] = useState(null); // { fieldId, year, fieldCode }
  const [editingCrop, setEditingCrop] = useState('');

  // ユーザー作物（ドロップダウン用）
  const [userCrops, setUserCrops] = useState([]);

  const yearOptions = Array.from({ length: 15 }, (_, i) => currentYear - 5 + i);
  const displayYears = useMemo(() => {
    const years = [];
    for (let y = startYear; y <= endYear; y++) {
      years.push(y);
    }
    return years;
  }, [startYear, endYear]);

  useEffect(() => {
    fetchFields();
    loadUserCrops();
  }, [fetchFields]);

  // 年度別表示切り替え時に履歴を一括取得
  useEffect(() => {
    if (showYearlyView && fields.length > 0) {
      loadAllHistory();
    }
  }, [showYearlyView, fields, startYear, endYear]);

  const loadUserCrops = async () => {
    try {
      const data = await cropApi.listUserCrops();
      setUserCrops(data);
    } catch (err) {
      console.error('Failed to load user crops:', err);
    }
  };

  const loadAllHistory = async () => {
    setIsLoadingHistory(true);
    const historyMap = {};

    try {
      // 全ほ場の履歴を並行取得
      const promises = fields.map(async (field) => {
        try {
          const history = await fieldApi.getHistory(field.id);
          historyMap[field.id] = {};
          for (const h of history) {
            // yearが文字列の場合（R7等）と数値の場合を考慮
            const yearStr = String(h.year);
            historyMap[field.id][yearStr] = h.crop;
            // 西暦変換も試みる
            if (yearStr.startsWith('R')) {
              const westernYear = 2018 + parseInt(yearStr.substring(1));
              historyMap[field.id][westernYear] = h.crop;
            }
          }
        } catch (err) {
          console.error(`Failed to load history for field ${field.id}:`, err);
        }
      });

      await Promise.all(promises);
      setAllHistory(historyMap);
    } finally {
      setIsLoadingHistory(false);
    }
  };

  const getCropForCell = (fieldId, year) => {
    if (!allHistory[fieldId]) return '';
    return allHistory[fieldId][year] || allHistory[fieldId][String(year)] || '';
  };

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

  // ほ場選択（チェックボックス）
  const handleFieldSelect = (fieldId) => {
    setSelectedFieldIds(prev => {
      const newSet = new Set(prev);
      if (newSet.has(fieldId)) {
        newSet.delete(fieldId);
      } else {
        newSet.add(fieldId);
      }
      return newSet;
    });
  };

  // 全選択/解除
  const handleSelectAll = () => {
    if (selectedFieldIds.size === fields.length) {
      setSelectedFieldIds(new Set());
    } else {
      setSelectedFieldIds(new Set(fields.map(f => f.id)));
    }
  };

  // 農薬発注画面へ遷移
  const handleGoToPesticideOrders = () => {
    if (selectedFieldIds.size === 0) {
      alert('ほ場を選択してください');
      return;
    }
    const ids = Array.from(selectedFieldIds).join(',');
    navigate(`/pesticide-orders?field_ids=${ids}`);
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
      setHistoryForm({ year: new Date().getFullYear(), crop: '' });
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

  const years = Array.from({ length: 11 }, (_, i) => new Date().getFullYear() - i);

  // ========== 年度別作物編集 ==========
  const handleCellClick = (field, year) => {
    setEditingCell({ fieldId: field.id, year, fieldCode: field.field_code });
    setEditingCrop(getCropForCell(field.id, year));
    setShowCropEditModal(true);
  };

  const handleSaveCrop = async () => {
    if (!editingCell) return;

    try {
      await fieldApi.addHistory(editingCell.fieldId, editingCell.year, editingCrop);
      // 履歴を更新
      setAllHistory((prev) => ({
        ...prev,
        [editingCell.fieldId]: {
          ...prev[editingCell.fieldId],
          [editingCell.year]: editingCrop,
        },
      }));
      setShowCropEditModal(false);
      setEditingCell(null);
      setEditingCrop('');
    } catch (err) {
      alert('保存に失敗しました');
    }
  };

  const closeCropEditModal = () => {
    setShowCropEditModal(false);
    setEditingCell(null);
    setEditingCrop('');
  };

  // KMZエクスポート
  const handleExportKmz = async () => {
    try {
      const today = new Date().toISOString().slice(0, 10).replace(/-/g, '');
      await downloadWithAuth(fieldApi.exportKmz(), `fields_export_${today}.kmz`);
    } catch (err) {
      alert(err.message || 'KMZエクスポートに失敗しました');
    }
  };

  return (
    <div className="fields-page">
      <div className="page-header">
        <h1>🗺️ ほ場一覧</h1>
        <div className="header-actions">
          <button
            onClick={() => setShowYearlyView(!showYearlyView)}
            className={`btn-secondary ${showYearlyView ? 'active' : ''}`}
          >
            {showYearlyView ? '📋 通常表示' : '📅 年度別表示'}
          </button>
          <button onClick={() => navigate('/field-register')} className="btn-primary">
            + ほ場登録
          </button>
          {selectedFieldIds.size > 0 && (
            <button onClick={handleGoToPesticideOrders} className="btn-primary">
              💊 発注画面へ ({selectedFieldIds.size})
            </button>
          )}
        </div>
      </div>

      {/* 年度別表示の年度選択 */}
      {showYearlyView && (
        <div className="year-range-selector">
          <label>表示年度: </label>
          <select value={startYear} onChange={(e) => setStartYear(parseInt(e.target.value))}>
            {yearOptions.map((y) => (
              <option key={y} value={y}>{y}年</option>
            ))}
          </select>
          <span> 〜 </span>
          <select value={endYear} onChange={(e) => setEndYear(parseInt(e.target.value))}>
            {yearOptions.map((y) => (
              <option key={y} value={y}>{y}年</option>
            ))}
          </select>
          <button onClick={loadAllHistory} className="btn-secondary btn-sm" style={{ marginLeft: '10px' }}>
            🔄 更新
          </button>
        </div>
      )}

      {showForm && (
        <div className="modal-overlay">
          <div className="modal">
            <h2>ほ場編集</h2>
            <form onSubmit={handleSubmit}>
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
              <Spinner text="履歴を読み込み中..." size="sm" />
            ) : history.length === 0 ? (
              <EmptyState message="作付履歴がありません" icon="📅" />
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

      {/* 年度別作物編集モーダル */}
      {showCropEditModal && editingCell && (
        <div className="modal-overlay">
          <div className="modal">
            <h2>🌾 作物編集</h2>
            <p>
              <strong>{editingCell.fieldCode}</strong> - {editingCell.year}年
            </p>
            <div className="form-group">
              <label>作物</label>
              {userCrops.length > 0 ? (
                <select
                  value={editingCrop}
                  onChange={(e) => setEditingCrop(e.target.value)}
                  style={{ width: '100%', padding: '8px' }}
                >
                  <option value="">（未設定）</option>
                  {userCrops.map((c) => (
                    <option key={c.id} value={c.name || c.custom_name}>
                      {c.name || c.custom_name}
                    </option>
                  ))}
                </select>
              ) : (
                <input
                  type="text"
                  value={editingCrop}
                  onChange={(e) => setEditingCrop(e.target.value)}
                  placeholder="作物名を入力"
                />
              )}
            </div>
            <div className="form-actions">
              <button type="button" onClick={closeCropEditModal} className="btn-secondary">
                キャンセル
              </button>
              <button type="button" onClick={handleSaveCrop} className="btn-primary">
                保存
              </button>
            </div>
          </div>
        </div>
      )}

      {isLoading || isLoadingHistory ? (
        <TableSkeleton rows={5} cols={7} />
      ) : fields.length === 0 ? (
        <EmptyState message="ほ場が登録されていません" icon="🗺️" />
      ) : showYearlyView ? (
        /* 年度別マトリクス表示 */
        <div className="yearly-table-wrapper">
          <table className="data-table yearly-table">
            <thead>
              <tr>
                <th>コード</th>
                <th>名前</th>
                <th>面積</th>
                {displayYears.map((year) => (
                  <th key={year} className="year-column">{year}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {fields.map((field) => (
                <tr key={field.id}>
                  <td>{field.field_code}</td>
                  <td>{field.field_name || '-'}</td>
                  <td>{field.area_ha.toFixed(2)}</td>
                  {displayYears.map((year) => {
                    const crop = getCropForCell(field.id, year);
                    return (
                      <td
                        key={year}
                        className="crop-cell clickable"
                        onClick={() => handleCellClick(field, year)}
                        title="クリックで編集"
                      >
                        {crop || <span className="empty-cell">-</span>}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        /* 通常表示 */
        <table className="data-table">
          <thead>
            <tr>
              <th style={{ width: '40px' }}>
                <input
                  type="checkbox"
                  checked={selectedFieldIds.size === fields.length && fields.length > 0}
                  onChange={handleSelectAll}
                  title="全選択/解除"
                />
              </th>
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
              <tr key={field.id} className={selectedFieldIds.has(field.id) ? 'selected' : ''}>
                <td>
                  <input
                    type="checkbox"
                    checked={selectedFieldIds.has(field.id)}
                    onChange={() => handleFieldSelect(field.id)}
                  />
                </td>
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

      <style>{`
        .header-actions {
          display: flex;
          gap: 10px;
        }
        .year-range-selector {
          margin-bottom: 15px;
          padding: 10px;
          background: #f5f5f5;
          border-radius: 5px;
          display: flex;
          align-items: center;
          gap: 8px;
        }
        .yearly-table-wrapper {
          overflow-x: auto;
        }
        .yearly-table .year-column {
          min-width: 80px;
          text-align: center;
        }
        .crop-cell {
          text-align: center;
          min-width: 80px;
        }
        .crop-cell.clickable {
          cursor: pointer;
          transition: background-color 0.2s;
        }
        .crop-cell.clickable:hover {
          background-color: #e3f2fd;
        }
        .empty-cell {
          color: #ccc;
        }
        .btn-sm {
          padding: 4px 8px;
          font-size: 12px;
        }
        .btn-secondary.active {
          background-color: #1976d2;
          color: white;
        }
      `}</style>
    </div>
  );
}
