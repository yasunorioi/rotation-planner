/**
 * 作物設定ページ
 * ユーザーが使用する作物の選択とカスタム名設定
 */

import { useEffect, useState } from 'react';
import { cropApi } from '../lib/api';

export default function CropSettings() {
  const [allCrops, setAllCrops] = useState([]);
  const [userCrops, setUserCrops] = useState([]);
  const [selectedCropIds, setSelectedCropIds] = useState([]);
  const [customCrops, setCustomCrops] = useState([]); // カスタム作物リスト
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [message, setMessage] = useState(null);

  // カスタム作物追加用
  const [newCustomParentId, setNewCustomParentId] = useState('');
  const [newCustomName, setNewCustomName] = useState('');
  const [isAddingCustom, setIsAddingCustom] = useState(false);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setIsLoading(true);
    try {
      const [crops, userCropsData] = await Promise.all([
        cropApi.list(),
        cropApi.listUserCrops(),
      ]);
      setAllCrops(crops);
      setUserCrops(userCropsData);

      // マスタ作物（custom_name がない）とカスタム作物を分離
      const masterCropIds = [];
      const customList = [];
      userCropsData.forEach((uc) => {
        if (uc.custom_name) {
          customList.push(uc);
        } else {
          masterCropIds.push(uc.parent_crop_id);
        }
      });
      setSelectedCropIds(masterCropIds);
      setCustomCrops(customList);
    } catch (err) {
      console.error('CropSettings load error:', err);
      const detail = err.response?.data?.detail || err.message || '不明なエラー';
      setMessage({ type: 'error', text: `読み込みに失敗しました: ${detail}` });
    } finally {
      setIsLoading(false);
    }
  };

  const handleCropToggle = (cropId) => {
    setSelectedCropIds((prev) =>
      prev.includes(cropId) ? prev.filter((id) => id !== cropId) : [...prev, cropId]
    );
  };

  const handleSelectAll = () => {
    setSelectedCropIds(allCrops.map((c) => c.id));
  };

  const handleDeselectAll = () => {
    setSelectedCropIds([]);
  };

  const handleSave = async () => {
    setIsSaving(true);
    setMessage(null);
    try {
      await cropApi.updateUserCrops(selectedCropIds);
      setMessage({ type: 'success', text: '保存しました' });
      await loadData();
    } catch (err) {
      setMessage({ type: 'error', text: '保存に失敗しました' });
    } finally {
      setIsSaving(false);
    }
  };

  // カスタム作物追加
  const handleAddCustomCrop = async () => {
    if (!newCustomParentId) {
      setMessage({ type: 'error', text: '親作物を選択してください' });
      return;
    }
    if (!newCustomName.trim()) {
      setMessage({ type: 'error', text: 'カスタム名を入力してください' });
      return;
    }
    setIsAddingCustom(true);
    setMessage(null);
    try {
      await cropApi.addCustomCrop(parseInt(newCustomParentId), newCustomName.trim());
      setMessage({ type: 'success', text: `「${newCustomName}」を追加しました` });
      setNewCustomParentId('');
      setNewCustomName('');
      await loadData();
    } catch (err) {
      const detail = err.response?.data?.detail || err.message || '不明なエラー';
      setMessage({ type: 'error', text: `追加に失敗しました: ${detail}` });
    } finally {
      setIsAddingCustom(false);
    }
  };

  // カスタム作物削除
  const handleDeleteCustomCrop = async (userCropId) => {
    if (!window.confirm('このカスタム作物を削除しますか？')) return;
    setMessage(null);
    try {
      await cropApi.deleteCustomCrop(userCropId);
      setMessage({ type: 'success', text: '削除しました' });
      await loadData();
    } catch (err) {
      setMessage({ type: 'error', text: '削除に失敗しました' });
    }
  };

  if (isLoading) {
    return <div className="loading">読み込み中...</div>;
  }

  return (
    <div className="crop-settings-page">
      <div className="page-header">
        <h1>🌱 作物設定</h1>
        <div className="header-actions">
          <button onClick={handleSelectAll} className="btn-secondary">
            全て選択
          </button>
          <button onClick={handleDeselectAll} className="btn-secondary">
            全て解除
          </button>
          <button onClick={handleSave} className="btn-primary" disabled={isSaving}>
            {isSaving ? '保存中...' : '保存'}
          </button>
        </div>
      </div>

      {message && (
        <div className={`message ${message.type}`}>
          {message.text}
        </div>
      )}

      <p className="page-description">
        輪作計画で使用する作物を選択してください。カスタム名を設定すると、表示名をカスタマイズできます。
      </p>

      <div className="crop-grid">
        {allCrops.map((crop) => {
          const isSelected = selectedCropIds.includes(crop.id);
          return (
            <div key={crop.id} className={`crop-card ${isSelected ? 'selected' : ''}`}>
              <label className="crop-checkbox">
                <input
                  type="checkbox"
                  checked={isSelected}
                  onChange={() => handleCropToggle(crop.id)}
                />
                <span className="crop-name">{crop.name}</span>
              </label>
              {crop.category && (
                <span className="crop-category">{crop.category}</span>
              )}
            </div>
          );
        })}
      </div>

      <div className="selected-count">
        選択中: {selectedCropIds.length + customCrops.length} / {allCrops.length} 作物（カスタム: {customCrops.length}）
      </div>

      <hr style={{ margin: '30px 0' }} />

      <h2>➕ カスタム作物の追加</h2>
      <p style={{ color: '#666', marginBottom: '15px' }}>
        同じ作物でも作期や回数で区別したい場合に使用します。例: 「ブロッコリー（2作目）」「キャベツ（春）」
      </p>

      <div className="custom-crop-form" style={{ display: 'flex', gap: '10px', marginBottom: '20px', flexWrap: 'wrap' }}>
        <select
          value={newCustomParentId}
          onChange={(e) => setNewCustomParentId(e.target.value)}
          style={{ padding: '8px', minWidth: '150px' }}
        >
          <option value="">親作物を選択</option>
          {allCrops.map((c) => (
            <option key={c.id} value={c.id}>{c.name}</option>
          ))}
        </select>
        <input
          type="text"
          placeholder="カスタム名（例: ブロッコリー（2作目））"
          value={newCustomName}
          onChange={(e) => setNewCustomName(e.target.value)}
          style={{ padding: '8px', flex: 1, minWidth: '200px' }}
        />
        <button
          onClick={handleAddCustomCrop}
          disabled={isAddingCustom}
          className="btn-primary"
          style={{ padding: '8px 16px' }}
        >
          {isAddingCustom ? '追加中...' : '追加'}
        </button>
      </div>

      {customCrops.length > 0 && (
        <div className="custom-crops-list">
          <h3>登録済みカスタム作物</h3>
          <table style={{ width: '100%', borderCollapse: 'collapse', marginTop: '10px' }}>
            <thead>
              <tr style={{ background: '#f5f5f5' }}>
                <th style={{ padding: '10px', textAlign: 'left', borderBottom: '1px solid #ddd' }}>カスタム名</th>
                <th style={{ padding: '10px', textAlign: 'left', borderBottom: '1px solid #ddd' }}>親作物</th>
                <th style={{ padding: '10px', textAlign: 'center', borderBottom: '1px solid #ddd', width: '80px' }}>操作</th>
              </tr>
            </thead>
            <tbody>
              {customCrops.map((c) => (
                <tr key={c.id}>
                  <td style={{ padding: '10px', borderBottom: '1px solid #eee' }}>{c.name}</td>
                  <td style={{ padding: '10px', borderBottom: '1px solid #eee' }}>{c.parent_name}</td>
                  <td style={{ padding: '10px', borderBottom: '1px solid #eee', textAlign: 'center' }}>
                    <button
                      onClick={() => handleDeleteCustomCrop(c.id)}
                      className="btn-danger"
                      style={{ padding: '4px 8px', fontSize: '12px' }}
                    >
                      削除
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
