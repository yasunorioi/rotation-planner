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
import FieldMiniMap from '../components/FieldMiniMap';

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

  // ほ場選択（一括削除用）
  const [selectedFieldIds, setSelectedFieldIds] = useState(new Set());

  // 作付履歴関連
  const [showHistoryModal, setShowHistoryModal] = useState(false);
  const [selectedFieldId, setSelectedFieldId] = useState(null);
  const [history, setHistory] = useState([]);
  const [historyLoading, setHistoryLoading] = useState(false);


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
    const { area_ha, ...rest } = formData;
    const data = editingId
      ? rest  // 編集時は面積を送らない（ポリゴンから自動算出のため）
      : { ...formData, area_ha: parseFloat(area_ha) };

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

  const handleFieldSelect = (fieldId) => {
    setSelectedFieldIds((prev) => {
      const next = new Set(prev);
      if (next.has(fieldId)) next.delete(fieldId);
      else next.add(fieldId);
      return next;
    });
  };

  const handleSelectAll = () => {
    if (selectedFieldIds.size === fields.length) {
      setSelectedFieldIds(new Set());
    } else {
      setSelectedFieldIds(new Set(fields.map((f) => f.id)));
    }
  };

  const handleBulkDelete = async () => {
    if (selectedFieldIds.size === 0) return;
    if (!confirm(`選択した${selectedFieldIds.size}件のほ場を削除しますか？`)) return;
    let ok = 0;
    let ng = 0;
    for (const id of selectedFieldIds) {
      try {
        await deleteField(id);
        ok++;
      } catch {
        ng++;
      }
    }
    setSelectedFieldIds(new Set());
    if (ng > 0) alert(`${ok}件削除、${ng}件失敗`);
  };

  // 作付履歴関連
  const handleShowHistory = async (fieldId) => {
    setSelectedFieldId(fieldId);
    setShowHistoryModal(true);
    setHistoryLoading(true);
    try {
      const data = await fieldApi.getHistory(fieldId);
      setHistory(data);
      initBulkHistory(data);
    } catch (err) {
      console.error('Failed to load history:', err);
      initBulkHistory([]);
    } finally {
      setHistoryLoading(false);
    }
  };

  // 一括登録用（4年分）
  const currentFiscalYear = new Date().getMonth() < 3 ? new Date().getFullYear() - 1 : new Date().getFullYear();
  const bulkHistoryYears = [currentFiscalYear - 3, currentFiscalYear - 2, currentFiscalYear - 1, currentFiscalYear];
  const [bulkHistory, setBulkHistory] = useState({});

  const initBulkHistory = (existingHistory) => {
    const map = {};
    bulkHistoryYears.forEach((y) => {
      const existing = existingHistory.find((h) => h.year === y);
      map[y] = existing ? existing.crop : '';
    });
    setBulkHistory(map);
  };

  const handleBulkHistorySubmit = async () => {
    const entries = Object.entries(bulkHistory).filter(([, crop]) => crop);
    if (entries.length === 0) {
      alert('作物を1件以上入力してください');
      return;
    }
    let ok = 0;
    for (const [year, crop] of entries) {
      try {
        await fieldApi.addHistory(selectedFieldId, parseInt(year), crop);
        ok++;
      } catch {
        // 既存年は上書きされる前提（APIの仕様による）
      }
    }
    const data = await fieldApi.getHistory(selectedFieldId);
    setHistory(data);
    alert(`${ok}件登録しました`);
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
            <button onClick={handleBulkDelete} className="btn-danger">
              🗑️ {selectedFieldIds.size}件削除
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
                <label>面積 (ha)</label>
                <input
                  type="text"
                  value={`${parseFloat(formData.area_ha || 0).toFixed(4)} ha`}
                  disabled
                  style={{ background: '#f0f0f0', color: '#666' }}
                />
                <small style={{ color: '#888' }}>ポリゴンから自動算出（変更はほ場登録で再描画）</small>
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

            {/* ほ場ミニ地図 */}
            {(() => {
              const field = fields.find((f) => f.id === selectedFieldId);
              if (!field?.coordinates_json) return null;
              let coords;
              try {
                coords = typeof field.coordinates_json === 'string'
                  ? JSON.parse(field.coordinates_json)
                  : field.coordinates_json;
              } catch { return null; }
              if (!coords || coords.length < 3) return null;
              return <FieldMiniMap coordinates={coords} height="300px" />;
            })()}

            {/* 一括登録テーブル（4年分） */}
            <div style={{ marginBottom: '16px' }}>
              <h3 style={{ fontSize: '1em', marginBottom: '8px' }}>一括登録</h3>
              <table className="data-table" style={{ fontSize: '0.9em' }}>
                <thead>
                  <tr>
                    {bulkHistoryYears.map((y) => (
                      <th key={y}>{y}年</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    {bulkHistoryYears.map((y) => (
                      <td key={y}>
                        <select
                          value={bulkHistory[y] || ''}
                          onChange={(e) => setBulkHistory((prev) => ({ ...prev, [y]: e.target.value }))}
                          style={{ width: '100%', padding: '4px' }}
                        >
                          <option value="">--</option>
                          {userCrops.map((c) => (
                            <option key={c.id || c.crop_id} value={c.name || c.crop_name}>
                              {c.custom_name || c.name || c.crop_name}
                            </option>
                          ))}
                        </select>
                      </td>
                    ))}
                  </tr>
                </tbody>
              </table>
              <button onClick={handleBulkHistorySubmit} className="btn-primary" style={{ marginTop: '8px' }}>
                一括登録
              </button>
            </div>

            {historyLoading ? (
              <Spinner text="履歴を読み込み中..." size="sm" />
            ) : history.length === 0 ? (
              <p style={{ color: '#888', textAlign: 'center', padding: '12px 0' }}>作付履歴がありません</p>
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
