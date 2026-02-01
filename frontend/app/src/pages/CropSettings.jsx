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
  const [customNames, setCustomNames] = useState({});
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [message, setMessage] = useState(null);

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
      setSelectedCropIds(userCropsData.map((uc) => uc.crop_id));

      const names = {};
      userCropsData.forEach((uc) => {
        if (uc.custom_name) {
          names[uc.crop_id] = uc.custom_name;
        }
      });
      setCustomNames(names);
    } catch (err) {
      setMessage({ type: 'error', text: '読み込みに失敗しました' });
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

  const handleCustomNameChange = (cropId, value) => {
    setCustomNames((prev) => ({
      ...prev,
      [cropId]: value,
    }));
  };

  const handleSave = async () => {
    setIsSaving(true);
    setMessage(null);
    try {
      await cropApi.updateUserCrops(selectedCropIds);

      for (const cropId of selectedCropIds) {
        const customName = customNames[cropId] || '';
        await cropApi.setCustomName(cropId, customName);
      }

      setMessage({ type: 'success', text: '保存しました' });
      await loadData();
    } catch (err) {
      setMessage({ type: 'error', text: '保存に失敗しました' });
    } finally {
      setIsSaving(false);
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
              {isSelected && (
                <div className="custom-name-input">
                  <input
                    type="text"
                    placeholder="カスタム名（任意）"
                    value={customNames[crop.id] || ''}
                    onChange={(e) => handleCustomNameChange(crop.id, e.target.value)}
                  />
                </div>
              )}
              {crop.category && (
                <span className="crop-category">{crop.category}</span>
              )}
            </div>
          );
        })}
      </div>

      <div className="selected-count">
        選択中: {selectedCropIds.length} / {allCrops.length} 作物
      </div>
    </div>
  );
}
