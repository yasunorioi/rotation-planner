/**
 * 防除記録ページ
 * APIのPesticideRecordCreateモデルに合わせたフォーム
 * 画像アップロード時にEXIF GPSを読み取りほ場を自動マッチング
 */

import { useEffect, useState, useRef } from 'react';
import { pesticideRecordApi, fieldApi, cropApi, gpsApi, pesticideMasterApi } from '../lib/api';

/**
 * 画像ファイルからEXIF GPS情報を抽出
 * @param {File} file - 画像ファイル
 * @returns {Promise<{lat: number, lon: number} | null>}
 */
async function extractGpsFromImage(file) {
  return new Promise((resolve) => {
    const reader = new FileReader();
    reader.onload = (e) => {
      try {
        const view = new DataView(e.target.result);

        // JPEG check
        if (view.getUint16(0, false) !== 0xFFD8) {
          resolve(null);
          return;
        }

        let offset = 2;
        while (offset < view.byteLength) {
          if (view.getUint16(offset, false) === 0xFFE1) {
            // EXIF marker found
            const exifData = parseExif(view, offset + 4);
            resolve(exifData);
            return;
          }
          offset += 2 + view.getUint16(offset + 2, false);
        }
        resolve(null);
      } catch {
        resolve(null);
      }
    };
    reader.onerror = () => resolve(null);
    reader.readAsArrayBuffer(file);
  });
}

/**
 * EXIF データからGPS座標を抽出
 */
function parseExif(view, start) {
  try {
    // Check for "Exif\0\0"
    const exifStr = String.fromCharCode(
      view.getUint8(start), view.getUint8(start + 1),
      view.getUint8(start + 2), view.getUint8(start + 3)
    );
    if (exifStr !== 'Exif') return null;

    const tiffStart = start + 6;
    const littleEndian = view.getUint16(tiffStart, false) === 0x4949;

    const ifdOffset = view.getUint32(tiffStart + 4, littleEndian);
    const numEntries = view.getUint16(tiffStart + ifdOffset, littleEndian);

    let gpsOffset = null;

    // Find GPS IFD pointer
    for (let i = 0; i < numEntries; i++) {
      const entryOffset = tiffStart + ifdOffset + 2 + i * 12;
      const tag = view.getUint16(entryOffset, littleEndian);
      if (tag === 0x8825) { // GPSInfo tag
        gpsOffset = view.getUint32(entryOffset + 8, littleEndian);
        break;
      }
    }

    if (!gpsOffset) return null;

    // Parse GPS IFD
    const gpsIfdOffset = tiffStart + gpsOffset;
    const gpsEntries = view.getUint16(gpsIfdOffset, littleEndian);

    let latRef = null, lat = null, lonRef = null, lon = null;

    for (let i = 0; i < gpsEntries; i++) {
      const entryOffset = gpsIfdOffset + 2 + i * 12;
      const tag = view.getUint16(entryOffset, littleEndian);
      const valueOffset = tiffStart + view.getUint32(entryOffset + 8, littleEndian);

      switch (tag) {
        case 1: // GPSLatitudeRef
          latRef = String.fromCharCode(view.getUint8(entryOffset + 8));
          break;
        case 2: // GPSLatitude
          lat = readGpsCoord(view, valueOffset, littleEndian);
          break;
        case 3: // GPSLongitudeRef
          lonRef = String.fromCharCode(view.getUint8(entryOffset + 8));
          break;
        case 4: // GPSLongitude
          lon = readGpsCoord(view, valueOffset, littleEndian);
          break;
      }
    }

    if (lat !== null && lon !== null) {
      const latitude = latRef === 'S' ? -lat : lat;
      const longitude = lonRef === 'W' ? -lon : lon;
      return { lat: latitude, lon: longitude };
    }
    return null;
  } catch {
    return null;
  }
}

/**
 * GPS座標（度分秒）を十進数に変換
 */
function readGpsCoord(view, offset, littleEndian) {
  try {
    const deg = view.getUint32(offset, littleEndian) / view.getUint32(offset + 4, littleEndian);
    const min = view.getUint32(offset + 8, littleEndian) / view.getUint32(offset + 12, littleEndian);
    const sec = view.getUint32(offset + 16, littleEndian) / view.getUint32(offset + 20, littleEndian);
    return deg + min / 60 + sec / 3600;
  } catch {
    return null;
  }
}

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

  // GPS マッチング用の状態
  const [gpsInfo, setGpsInfo] = useState(null); // { lat, lon }
  const [fieldCandidates, setFieldCandidates] = useState([]); // GPSマッチング候補
  const [isMatchingGps, setIsMatchingGps] = useState(false);
  const [gpsMessage, setGpsMessage] = useState('');
  const [uploadedImage, setUploadedImage] = useState(null);
  const [uploadedFile, setUploadedFile] = useState(null); // 解析用にファイルを保持
  const fileInputRef = useRef(null);

  // Vision API 解析用の状態
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [analyzeResult, setAnalyzeResult] = useState(null); // { pesticide_name, confidence, raw_text, error }

  // 画像表示モーダル用の状態
  const [showImageModal, setShowImageModal] = useState(false);
  const [imageModalRecordId, setImageModalRecordId] = useState(null);
  const [recordImages, setRecordImages] = useState([]);
  const [isLoadingImages, setIsLoadingImages] = useState(false);

  // 希釈倍率候補用の状態
  const [dilutionCandidates, setDilutionCandidates] = useState([]);
  const [isLoadingDilution, setIsLoadingDilution] = useState(false);

  const years = Array.from({ length: 5 }, (_, i) => new Date().getFullYear() - 2 + i);

  /**
   * 画像アップロード時のGPSマッチング処理
   */
  const handleImageUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setUploadedImage(URL.createObjectURL(file));
    setUploadedFile(file); // 解析用にファイルを保持
    setGpsMessage('GPS情報を読み取り中...');
    setIsMatchingGps(true);
    setFieldCandidates([]);
    setGpsInfo(null);
    setAnalyzeResult(null); // 解析結果をリセット

    try {
      // EXIF からGPS情報を抽出
      const gps = await extractGpsFromImage(file);

      if (!gps) {
        setGpsMessage('📍 GPS情報がありません');
        setIsMatchingGps(false);
        return;
      }

      setGpsInfo(gps);
      setGpsMessage(`📍 GPS: ${gps.lat.toFixed(6)}, ${gps.lon.toFixed(6)} - ほ場をマッチング中...`);

      // APIでほ場マッチング
      const result = await gpsApi.matchField(gps.lat, gps.lon);

      if (result.candidates && result.candidates.length > 0) {
        setFieldCandidates(result.candidates);

        if (result.matched_field) {
          // マッチしたほ場を自動選択
          setFormData((prev) => ({ ...prev, field_id: result.matched_field.id.toString() }));
          setGpsMessage(`✅ ほ場「${result.matched_field.field_code}」に一致しました（現在地）`);
        } else {
          // 候補から最寄りを表示
          const nearest = result.candidates[0];
          setGpsMessage(`📍 GPS: ${gps.lat.toFixed(5)}, ${gps.lon.toFixed(5)} - ${result.candidates.length}件の候補ほ場`);
        }
      } else {
        setGpsMessage('⚠️ 近くにほ場が見つかりません');
      }
    } catch (err) {
      console.error('GPS matching failed:', err);
      setGpsMessage('⚠️ GPSマッチングに失敗しました');
    } finally {
      setIsMatchingGps(false);
    }
  };

  /**
   * 候補ほ場の表示名を生成
   */
  const formatCandidateLabel = (candidate) => {
    const name = candidate.field_name || candidate.field_code;
    if (candidate.is_inside) {
      return `📍 ${candidate.field_code} ${candidate.field_name || ''} (現在地)`.trim();
    }
    const dist = candidate.distance_m < 1000
      ? `${Math.round(candidate.distance_m)}m`
      : `${(candidate.distance_m / 1000).toFixed(1)}km`;
    return `${candidate.field_code} ${candidate.field_name || ''} (${dist})`.trim();
  };

  /**
   * GPSマッチング候補をクリア
   */
  const clearGpsMatch = () => {
    setGpsInfo(null);
    setFieldCandidates([]);
    setGpsMessage('');
    setUploadedImage(null);
    setUploadedFile(null);
    setAnalyzeResult(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  /**
   * 画像から農薬名を解析（Claude Vision API）
   */
  const handleAnalyzeImage = async () => {
    if (!uploadedFile) {
      alert('画像をアップロードしてください');
      return;
    }

    setIsAnalyzing(true);
    setAnalyzeResult(null);

    try {
      const result = await pesticideRecordApi.analyzeImage(uploadedFile);
      setAnalyzeResult(result);

      if (result.pesticide_name) {
        // 農薬名を自動入力し、希釈倍率候補も取得
        handlePesticideNameChange(result.pesticide_name);
      }
    } catch (err) {
      console.error('Image analysis failed:', err);
      setAnalyzeResult({ error: '画像解析に失敗しました' });
    } finally {
      setIsAnalyzing(false);
    }
  };

  /**
   * 農薬名変更時に希釈倍率候補を取得
   */
  const handlePesticideNameChange = async (name) => {
    setFormData((prev) => ({ ...prev, pesticide_name: name }));
    setDilutionCandidates([]);

    if (!name || name.length < 2) {
      return;
    }

    setIsLoadingDilution(true);
    try {
      const candidates = await pesticideMasterApi.getDilutionRates(name);
      setDilutionCandidates(candidates || []);
    } catch (err) {
      console.error('Failed to load dilution rates:', err);
    } finally {
      setIsLoadingDilution(false);
    }
  };

  /**
   * 希釈倍率候補を選択
   */
  const handleSelectDilution = (candidate) => {
    setFormData((prev) => ({
      ...prev,
      dilution_rate: candidate.dilution_rate,
      target_pest: candidate.target_pest || prev.target_pest,
    }));
  };

  /**
   * 解析結果の信頼度に応じたスタイルを取得
   */
  const getConfidenceStyle = (confidence) => {
    if (confidence >= 0.7) {
      return { background: '#d4edda', color: '#155724' }; // 緑（高信頼度）
    } else if (confidence >= 0.4) {
      return { background: '#fff3cd', color: '#856404' }; // 黄（中信頼度）
    } else {
      return { background: '#f8d7da', color: '#721c24' }; // 赤（低信頼度）
    }
  };

  /**
   * 画像一覧モーダルを開く
   */
  const handleShowImages = async (recordId) => {
    setImageModalRecordId(recordId);
    setShowImageModal(true);
    setIsLoadingImages(true);
    try {
      const images = await pesticideRecordApi.listImages(recordId);
      setRecordImages(images);
    } catch (err) {
      console.error('Failed to load images:', err);
      setRecordImages([]);
    } finally {
      setIsLoadingImages(false);
    }
  };

  /**
   * 画像モーダルを閉じる
   */
  const closeImageModal = () => {
    setShowImageModal(false);
    setImageModalRecordId(null);
    setRecordImages([]);
  };

  /**
   * 画像をアップロード（既存の記録に追加）
   */
  const handleUploadRecordImage = async (e) => {
    const file = e.target.files?.[0];
    if (!file || !imageModalRecordId) return;
    try {
      await pesticideRecordApi.uploadImage(imageModalRecordId, file);
      const images = await pesticideRecordApi.listImages(imageModalRecordId);
      setRecordImages(images);
    } catch (err) {
      alert('画像のアップロードに失敗しました');
    }
  };

  /**
   * 画像を削除
   */
  const handleDeleteRecordImage = async (imageId) => {
    if (!confirm('この画像を削除しますか？')) return;
    try {
      await pesticideRecordApi.deleteImage(imageModalRecordId, imageId);
      setRecordImages(recordImages.filter(img => img.id !== imageId));
    } catch (err) {
      alert('画像の削除に失敗しました');
    }
  };

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
    // GPSマッチング状態もクリア
    clearGpsMatch();
    // 希釈倍率候補もクリア
    setDilutionCandidates([]);
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
              {/* GPSマッチング: 画像アップロードセクション */}
              {!editingId && (
                <div className="gps-match-section" style={{
                  background: '#f0f7ff',
                  padding: '12px',
                  borderRadius: '8px',
                  marginBottom: '16px',
                  border: '1px solid #cce0ff'
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '8px' }}>
                    <label style={{ fontWeight: 'bold', margin: 0 }}>📷 画像からほ場を自動判定</label>
                    <input
                      ref={fileInputRef}
                      type="file"
                      accept="image/jpeg,image/jpg"
                      onChange={handleImageUpload}
                      style={{ flex: 1 }}
                    />
                    {(gpsInfo || uploadedImage) && (
                      <button type="button" onClick={clearGpsMatch} className="btn-secondary btn-sm">
                        クリア
                      </button>
                    )}
                  </div>
                  {gpsMessage && (
                    <div style={{
                      padding: '8px',
                      background: gpsMessage.includes('✅') ? '#d4edda' :
                                  gpsMessage.includes('⚠️') ? '#fff3cd' : '#e2e3e5',
                      borderRadius: '4px',
                      fontSize: '0.9em'
                    }}>
                      {isMatchingGps ? '🔄 ' : ''}{gpsMessage}
                    </div>
                  )}
                  {/* GPS候補ほ場ドロップダウン */}
                  {fieldCandidates.length > 0 && (
                    <div style={{ marginTop: '8px' }}>
                      <label style={{ fontSize: '0.85em', color: '#666' }}>候補ほ場（GPSマッチング）:</label>
                      <select
                        value={formData.field_id}
                        onChange={(e) => setFormData({ ...formData, field_id: e.target.value })}
                        style={{ width: '100%', marginTop: '4px' }}
                      >
                        <option value="">-- 候補から選択 --</option>
                        {fieldCandidates.map((c) => (
                          <option key={c.id} value={c.id}>
                            {formatCandidateLabel(c)}
                          </option>
                        ))}
                      </select>
                    </div>
                  )}
                  {uploadedImage && (
                    <div style={{ marginTop: '8px', display: 'flex', alignItems: 'flex-start', gap: '12px' }}>
                      <img
                        src={uploadedImage}
                        alt="アップロード画像"
                        style={{ maxWidth: '200px', maxHeight: '150px', borderRadius: '4px' }}
                      />
                      <div style={{ flex: 1 }}>
                        <button
                          type="button"
                          onClick={handleAnalyzeImage}
                          disabled={isAnalyzing}
                          className="btn-primary"
                          style={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: '4px',
                            marginBottom: '8px'
                          }}
                        >
                          {isAnalyzing ? '🔄 解析中...' : '🔬 農薬名を画像解析'}
                        </button>
                        {/* 解析結果表示 */}
                        {analyzeResult && (
                          <div style={{
                            padding: '8px',
                            borderRadius: '4px',
                            fontSize: '0.9em',
                            ...(analyzeResult.error
                              ? { background: '#f8d7da', color: '#721c24' }
                              : analyzeResult.pesticide_name
                                ? getConfidenceStyle(analyzeResult.confidence || 0)
                                : { background: '#e2e3e5', color: '#383d41' })
                          }}>
                            {analyzeResult.error ? (
                              <>⚠️ {analyzeResult.error}</>
                            ) : analyzeResult.pesticide_name ? (
                              <>
                                <div style={{ fontWeight: 'bold' }}>
                                  📋 農薬名: {analyzeResult.pesticide_name}
                                </div>
                                <div style={{ fontSize: '0.85em', marginTop: '4px' }}>
                                  信頼度: {((analyzeResult.confidence || 0) * 100).toFixed(0)}%
                                  {analyzeResult.confidence < 0.4 && (
                                    <span style={{ marginLeft: '8px', color: '#721c24' }}>
                                      ⚠️ 信頼度が低いため確認してください
                                    </span>
                                  )}
                                </div>
                              </>
                            ) : (
                              <>📍 農薬名を認識できませんでした</>
                            )}
                          </div>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              )}

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
                    onChange={(e) => handlePesticideNameChange(e.target.value)}
                    onBlur={(e) => handlePesticideNameChange(e.target.value)}
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
                  {/* 希釈倍率候補表示 */}
                  {isLoadingDilution && (
                    <div style={{ fontSize: '0.85em', color: '#666', marginTop: '4px' }}>
                      候補を読み込み中...
                    </div>
                  )}
                  {dilutionCandidates.length > 0 && (
                    <div style={{
                      marginTop: '8px',
                      padding: '8px',
                      background: '#f0f7ff',
                      borderRadius: '4px',
                      border: '1px solid #cce0ff'
                    }}>
                      <div style={{ fontSize: '0.85em', color: '#666', marginBottom: '4px' }}>
                        💊 希釈倍率候補（クリックで適用）:
                      </div>
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
                        {dilutionCandidates.map((c, idx) => (
                          <button
                            key={idx}
                            type="button"
                            onClick={() => handleSelectDilution(c)}
                            style={{
                              padding: '4px 8px',
                              fontSize: '0.85em',
                              background: '#fff',
                              border: '1px solid #ddd',
                              borderRadius: '4px',
                              cursor: 'pointer'
                            }}
                            title={`${c.crop || '全作物'} / ${c.target_pest || '-'}`}
                          >
                            {c.dilution_rate}
                            {c.target_pest && <span style={{ color: '#888', marginLeft: '4px' }}>({c.target_pest})</span>}
                          </button>
                        ))}
                      </div>
                    </div>
                  )}
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
                    <button onClick={() => handleEdit(record)} className="btn-icon" title="編集">
                      ✏️
                    </button>
                    <button onClick={() => handleShowImages(record.id)} className="btn-icon" title="画像">
                      📷
                    </button>
                    <button onClick={() => handleDelete(record.id)} className="btn-icon btn-danger" title="削除">
                      🗑️
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* 画像モーダル */}
      {showImageModal && (
        <div className="modal-overlay">
          <div className="modal">
            <h2>📷 記録画像</h2>
            <div style={{ marginBottom: '16px' }}>
              <label style={{ display: 'block', marginBottom: '8px' }}>画像を追加:</label>
              <input
                type="file"
                accept="image/*"
                onChange={handleUploadRecordImage}
              />
            </div>
            {isLoadingImages ? (
              <p>読み込み中...</p>
            ) : recordImages.length === 0 ? (
              <p style={{ color: '#666' }}>画像がありません</p>
            ) : (
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '12px' }}>
                {recordImages.map((img) => (
                  <div key={img.id} style={{ position: 'relative' }}>
                    <img
                      src={pesticideRecordApi.getImageUrl(imageModalRecordId, img.id)}
                      alt={img.original_name}
                      style={{ width: '150px', height: '100px', objectFit: 'cover', borderRadius: '4px' }}
                    />
                    <button
                      onClick={() => handleDeleteRecordImage(img.id)}
                      style={{
                        position: 'absolute',
                        top: '4px',
                        right: '4px',
                        background: 'rgba(255,0,0,0.8)',
                        color: 'white',
                        border: 'none',
                        borderRadius: '50%',
                        width: '24px',
                        height: '24px',
                        cursor: 'pointer',
                        fontSize: '12px'
                      }}
                      title="削除"
                    >
                      ✕
                    </button>
                    <div style={{ fontSize: '0.8em', color: '#666', marginTop: '4px' }}>
                      {img.original_name}
                    </div>
                  </div>
                ))}
              </div>
            )}
            <div className="form-actions" style={{ marginTop: '16px' }}>
              <button onClick={closeImageModal} className="btn-secondary">
                閉じる
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
