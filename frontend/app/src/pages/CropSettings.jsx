/**
 * 作物設定ページ
 * ユーザーが使用する作物の選択とカスタム名設定
 *
 * - 北海道の主要作物はデフォルト表示（チェックボックス）
 * - その他の作物はFAMIC検索から追加
 */

import { useEffect, useState, useRef } from 'react';
import { cropApi } from '../lib/api';
import { PageLoading } from '../components/Loading';

// 北海道でよく使われるデフォルト作物（FAMIC表記に準拠）
const DEFAULT_CROP_NAMES = ['小麦(春播)', '小麦(秋播)', 'だいず', 'あずき', 'てんさい', 'ばれいしょ'];

export default function CropSettings() {
  const [allCrops, setAllCrops] = useState([]);
  const [userCrops, setUserCrops] = useState([]);
  const [selectedCropIds, setSelectedCropIds] = useState([]);
  const [customCrops, setCustomCrops] = useState([]); // カスタム作物リスト
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false);
  const [message, setMessage] = useState(null);

  // カスタム作物追加用
  const [newCustomParentId, setNewCustomParentId] = useState('');
  const [newCustomName, setNewCustomName] = useState('');
  const [isAddingCustom, setIsAddingCustom] = useState(false);

  // FAMIC検索用
  const [famicSearchKeyword, setFamicSearchKeyword] = useState('');
  const [famicSearchResults, setFamicSearchResults] = useState([]);
  const [isSearchingFamic, setIsSearchingFamic] = useState(false);
  const [selectedFamicCrop, setSelectedFamicCrop] = useState('');

  const searchTimerRef = useRef(null);

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

  // FAMIC検索（デバウンス300ms）
  const debouncedFamicSearch = useCallback((keyword) => {
    if (searchTimerRef.current) {
      clearTimeout(searchTimerRef.current);
    }

    if (!keyword || keyword.length < 2) {
      setFamicSearchResults([]);
      return;
    }

    setIsSearchingFamic(true);
    searchTimerRef.current = setTimeout(async () => {
      try {
        const results = await cropApi.searchFamicCrops(keyword, 30);
        // 既にマスタにある作物は除外
        const existingNames = new Set(allCrops.map(c => c.name));
        const filtered = results.filter(name => !existingNames.has(name));
        setFamicSearchResults(filtered);
      } catch (err) {
        console.error('FAMIC search error:', err);
        setFamicSearchResults([]);
      } finally {
        setIsSearchingFamic(false);
      }
    }, 300);
  }, [allCrops]);

  // コンポーネントアンマウント時にタイマーをクリア
  useEffect(() => {
    return () => {
      if (searchTimerRef.current) {
        clearTimeout(searchTimerRef.current);
      }
    };
  }, []);

  const handleCropToggle = (cropId) => {
    setSelectedCropIds((prev) => {
      const newIds = prev.includes(cropId) ? prev.filter((id) => id !== cropId) : [...prev, cropId];
      return newIds;
    });
    setHasUnsavedChanges(true);
  };

  const handleSave = async () => {
    setIsSaving(true);
    setMessage(null);
    try {
      await cropApi.updateUserCrops(selectedCropIds);
      setHasUnsavedChanges(false);
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

  // FAMIC検索入力
  const handleFamicSearchChange = (e) => {
    const value = e.target.value;
    setFamicSearchKeyword(value);
    debouncedFamicSearch(value);
  };

  // FAMIC作物選択
  const handleFamicCropSelect = (cropName) => {
    setSelectedFamicCrop(cropName);
    setFamicSearchResults([]);
    setFamicSearchKeyword(cropName);
  };

  // 選択した作物をマスタ追加してユーザー作物に追加
  const handleAddFamicCropToUser = async () => {
    if (!selectedFamicCrop) {
      setMessage({ type: 'error', text: '作物を選択してください' });
      return;
    }

    setIsSaving(true);
    setMessage(null);
    try {
      // まず既にマスタにあるか確認
      let crop = allCrops.find(c => c.name === selectedFamicCrop);

      if (!crop) {
        // マスタに追加（管理者権限がない場合はエラーになる）
        try {
          const result = await cropApi.addCropFromFamic(selectedFamicCrop);
          // マスタリストを再読み込み
          const newCrops = await cropApi.list();
          setAllCrops(newCrops);
          crop = newCrops.find(c => c.id === result.id);
        } catch (err) {
          if (err.response?.status === 403) {
            setMessage({ type: 'error', text: '新規作物の追加には管理者権限が必要です' });
          } else {
            throw err;
          }
          return;
        }
      }

      if (crop) {
        // ユーザー作物に追加
        const newIds = [...selectedCropIds, crop.id];
        setSelectedCropIds(newIds);
        await cropApi.updateUserCrops(newIds);
        setMessage({ type: 'success', text: `「${selectedFamicCrop}」を追加しました` });
        setSelectedFamicCrop('');
        setFamicSearchKeyword('');
        await loadData();
      }
    } catch (err) {
      const detail = err.response?.data?.detail || err.message || '不明なエラー';
      setMessage({ type: 'error', text: `追加に失敗しました: ${detail}` });
    } finally {
      setIsSaving(false);
    }
  };

  if (isLoading) {
    return <PageLoading text="作物設定を読み込み中..." />;
  }

  // デフォルト作物とその他の作物を分離
  const defaultCrops = allCrops.filter(c => DEFAULT_CROP_NAMES.includes(c.name));
  const otherCrops = allCrops.filter(c => !DEFAULT_CROP_NAMES.includes(c.name));

  return (
    <div className="crop-settings-page">
      <div className="page-header">
        <h1>作物設定</h1>
        <div className="header-actions">
          {hasUnsavedChanges && (
            <span style={{ color: '#e65100', fontSize: '0.9em' }}>
              未保存の変更があります
            </span>
          )}
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
        輪作計画で使用する作物を選択してください。FAMIC登録農薬の適用作物と連携します。
      </p>

      {/* デフォルト作物（北海道主要作物） */}
      <section style={{ marginBottom: '30px' }}>
        <h2>主要作物（北海道）</h2>
        <p style={{ color: '#666', fontSize: '0.9em', marginBottom: '15px' }}>
          北海道でよく栽培される作物です。チェックを入れて使用する作物を選択してください。
        </p>
        <div className="crop-grid">
          {defaultCrops.map((crop) => {
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
              </div>
            );
          })}
        </div>
      </section>

      {/* 登録済みのその他作物 */}
      {otherCrops.length > 0 && (
        <section style={{ marginBottom: '30px' }}>
          <h2>その他の登録済み作物</h2>
          <div className="crop-grid">
            {otherCrops.map((crop) => {
              const isSelected = selectedCropIds.includes(crop.id);
              // ユーザーが登録済みならユーザー側の表示名（子）を使う
              const uc = userCrops.find((u) => u.parent_crop_id === crop.id && !u.custom_name);
              const displayName = uc ? uc.name : crop.name;
              return (
                <div key={crop.id} className={`crop-card ${isSelected ? 'selected' : ''}`}>
                  <label className="crop-checkbox">
                    <input
                      type="checkbox"
                      checked={isSelected}
                      onChange={() => handleCropToggle(crop.id)}
                    />
                    <span className="crop-name">{displayName}</span>
                  </label>
                </div>
              );
            })}
          </div>
        </section>
      )}

      <hr style={{ margin: '30px 0' }} />

      {/* FAMIC作物検索・追加 */}
      <section style={{ marginBottom: '30px' }}>
        <h2>作物を追加（FAMIC検索）</h2>
        <p style={{ color: '#666', fontSize: '0.9em', marginBottom: '15px' }}>
          FAMIC（農林水産消費安全技術センター）の登録農薬適用情報から作物名を検索して追加できます。
          登録農薬との連携が可能になります。
        </p>

        <div style={{ display: 'flex', gap: '10px', marginBottom: '10px', flexWrap: 'wrap' }}>
          <div style={{ flex: 1, minWidth: '250px', position: 'relative' }}>
            <input
              type="text"
              placeholder="作物名を検索（例: キャベツ、ブロッコリー）"
              value={famicSearchKeyword}
              onChange={handleFamicSearchChange}
              style={{ padding: '8px', width: '100%' }}
            />
            {isSearchingFamic && (
              <span style={{ position: 'absolute', right: '10px', top: '10px', color: '#666' }}>
                検索中...
              </span>
            )}
            {/* 検索結果ドロップダウン */}
            {famicSearchResults.length > 0 && (
              <div style={{
                position: 'absolute',
                top: '100%',
                left: 0,
                right: 0,
                background: 'white',
                border: '1px solid #ddd',
                borderRadius: '4px',
                maxHeight: '200px',
                overflowY: 'auto',
                zIndex: 100,
                boxShadow: '0 2px 8px rgba(0,0,0,0.15)'
              }}>
                {famicSearchResults.map((cropName, idx) => (
                  <div
                    key={idx}
                    onClick={() => handleFamicCropSelect(cropName)}
                    style={{
                      padding: '8px 12px',
                      cursor: 'pointer',
                      borderBottom: '1px solid #eee',
                      background: selectedFamicCrop === cropName ? '#e3f2fd' : 'transparent'
                    }}
                    onMouseEnter={(e) => e.target.style.background = '#f5f5f5'}
                    onMouseLeave={(e) => e.target.style.background = selectedFamicCrop === cropName ? '#e3f2fd' : 'transparent'}
                  >
                    {cropName}
                  </div>
                ))}
              </div>
            )}
          </div>
          <button
            onClick={handleAddFamicCropToUser}
            disabled={!selectedFamicCrop || isSaving}
            className="btn-primary"
            style={{ padding: '8px 16px' }}
          >
            {isSaving ? '追加中...' : '追加'}
          </button>
        </div>
        {selectedFamicCrop && (
          <p style={{ color: '#1976d2', fontSize: '0.9em' }}>
            選択中: <strong>{selectedFamicCrop}</strong>
          </p>
        )}
      </section>

      <hr style={{ margin: '30px 0' }} />

      {/* カスタム作物追加 */}
      <section>
        <h2>カスタム作物の追加</h2>
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
      </section>

      <div className="selected-count" style={{ marginTop: '30px', padding: '15px', background: '#f5f5f5', borderRadius: '4px' }}>
        選択中: {selectedCropIds.length + customCrops.length} 作物（マスタ: {selectedCropIds.length}、カスタム: {customCrops.length}）
      </div>
    </div>
  );
}
