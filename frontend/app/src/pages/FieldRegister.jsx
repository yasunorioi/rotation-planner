/**
 * ほ場登録ページ
 * 地図上でポリゴン描画、住所検索、KMLインポート/エクスポート
 */

import { useEffect, useState, useRef, useCallback } from 'react';
import { fieldApi, cropApi, fudePolygonApi } from '../lib/api';
import FieldMap from '../components/FieldMap';

/**
 * 年度選択肢を生成（令和形式）
 * 現在の年度を基準に前後の年度を生成
 */
function generateYearChoices() {
  const now = new Date();
  // 4月始まりの年度計算: 1-3月は前年度
  const fiscalYear = now.getMonth() < 3 ? now.getFullYear() - 1 : now.getFullYear();
  const currentReiwa = fiscalYear - 2018; // 2019年 = 令和1年

  const choices = [];
  for (let i = -2; i <= 5; i++) {
    const reiwa = currentReiwa + i;
    if (reiwa > 0) {
      choices.push({ value: `R${reiwa}`, label: `令和${reiwa}年` });
    }
  }
  return choices;
}

/**
 * 現在の年度を取得（令和形式）
 */
function getCurrentFiscalYear() {
  const now = new Date();
  const fiscalYear = now.getMonth() < 3 ? now.getFullYear() - 1 : now.getFullYear();
  const reiwa = fiscalYear - 2018;
  return `R${reiwa}`;
}

export default function FieldRegister() {
  const [fields, setFields] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [message, setMessage] = useState(null);

  // フォーム状態（ほ場IDは自動生成のため不要）
  const [formData, setFormData] = useState({
    field_name: '',
    district: '',
    beet_forbidden: false,
    // 初期作付情報
    crop_year: '',
    crop_name: '',
  });

  // 作物一覧（ユーザー作物）
  const [crops, setCrops] = useState([]);
  const yearChoices = generateYearChoices();
  const [drawnCoords, setDrawnCoords] = useState(null);
  const [drawnArea, setDrawnArea] = useState(0);

  // 住所検索
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResult, setSearchResult] = useState('');

  // 削除
  const [deleteId, setDeleteId] = useState('');

  // 選択中のほ場
  const [selectedField, setSelectedField] = useState(null);

  // KMLインポート
  const [importFile, setImportFile] = useState(null);
  const [importedFields, setImportedFields] = useState([]);
  const [isImporting, setIsImporting] = useState(false);

  // KMLプレビュー編集用（2段階インポート）
  const [kmlPreviewData, setKmlPreviewData] = useState([]); // 編集可能なプレビューデータ
  const [kmlCoordsData, setKmlCoordsData] = useState([]);   // 座標データ（登録時に使用）
  const [bulkCrop, setBulkCrop] = useState('');             // 一括設定用作物
  const [bulkBeetForbidden, setBulkBeetForbidden] = useState(false); // 一括設定用てんさい禁止
  const [kmlYear, setKmlYear] = useState(getCurrentFiscalYear()); // KML登録用年度
  const [isParsing, setIsParsing] = useState(false);        // KML解析中フラグ
  const [isRegistering, setIsRegistering] = useState(false); // 一括登録中フラグ

  // 筆ポリゴン
  const [showFudePolygons, setShowFudePolygons] = useState(false);
  const [fudePolygons, setFudePolygons] = useState([]);
  const [isFudeLoading, setIsFudeLoading] = useState(false);

  const mapRef = useRef(null);
  const fileInputRef = useRef(null);

  useEffect(() => {
    loadFields();
    loadCrops();
  }, []);

  const loadCrops = async () => {
    try {
      const data = await cropApi.listUserCrops();
      setCrops(data);
    } catch (err) {
      console.error('Failed to load crops:', err);
    }
  };

  const loadFields = async () => {
    setIsLoading(true);
    try {
      const data = await fieldApi.list();
      setFields(data);
    } catch (err) {
      console.error('Failed to load fields:', err);
    } finally {
      setIsLoading(false);
    }
  };

  // ポリゴン描画完了
  const handlePolygonCreated = useCallback((coords, area) => {
    setDrawnCoords(coords);
    setDrawnArea(area);
  }, []);

  // ほ場クリック
  const handleFieldClick = useCallback((field) => {
    setSelectedField(field);
    setFormData({
      field_name: field.field_name || '',
      district: field.district || '',
      beet_forbidden: field.beet_forbidden || false,
      crop_year: '',
      crop_name: '',
    });
  }, []);

  // 筆ポリゴン読み込み
  const loadFudePolygons = useCallback(async () => {
    if (!mapRef.current?.getBounds || !mapRef.current?.getZoom) return;

    const zoom = mapRef.current.getZoom();
    if (zoom < 14) {
      setMessage({ type: 'info', text: '筆ポリゴンを表示するにはズームレベル14以上に拡大してください' });
      setFudePolygons([]);
      return;
    }

    const bounds = mapRef.current.getBounds();
    if (!bounds) return;

    setIsFudeLoading(true);
    try {
      const data = await fudePolygonApi.getByBounds(bounds, 300);
      setFudePolygons(data.polygons || []);
      if (data.count === 0) {
        setMessage({ type: 'info', text: 'この範囲に筆ポリゴンデータがありません（data/fude_cacheにGeoJSONを配置してください）' });
      }
    } catch (err) {
      console.error('Failed to load fude polygons:', err);
      setMessage({ type: 'error', text: '筆ポリゴンの読み込みに失敗しました' });
    } finally {
      setIsFudeLoading(false);
    }
  }, []);

  // 筆ポリゴン表示切替
  const handleToggleFudePolygons = useCallback(async () => {
    const newValue = !showFudePolygons;
    setShowFudePolygons(newValue);
    if (newValue) {
      await loadFudePolygons();
    } else {
      setFudePolygons([]);
    }
  }, [showFudePolygons, loadFudePolygons]);

  // 筆ポリゴンクリック（ほ場に取り込み）
  const handleFudePolygonClick = useCallback((fude) => {
    if (!fude.coordinates || fude.coordinates.length < 3) return;

    // 座標をフォームに反映
    if (mapRef.current?.setPolygon) {
      mapRef.current.setPolygon(fude.coordinates);
    }

    // 面積とIDを自動設定
    const area = fude.area_ha || 0;
    const landTypeNames = { '100': '田', '200': '畑' };
    const landType = landTypeNames[fude.land_type] || '';

    setFormData(prev => ({
      ...prev,
      field_name: landType ? `${landType}（筆ポリゴン）` : '筆ポリゴン取込',
    }));

    setDrawnCoords(fude.coordinates);
    setDrawnArea(area * 10000); // ha → m²

    setMessage({ type: 'success', text: `筆ポリゴンを取り込みました（${area.toFixed(2)} ha）` });
  }, []);

  // 住所検索
  const handleSearch = async () => {
    if (!searchQuery.trim()) {
      setSearchResult('検索語を入力してください');
      return;
    }

    try {
      const response = await fetch(
        `https://nominatim.openstreetmap.org/search?q=${encodeURIComponent(searchQuery)}&format=json&limit=1&countrycodes=jp`,
        { headers: { 'User-Agent': 'FieldRegisterApp/1.0' } }
      );
      const results = await response.json();

      if (results.length > 0) {
        const { lat, lon, display_name } = results[0];
        setSearchResult(`検索結果: ${display_name}`);
        if (mapRef.current?.moveToLocation) {
          mapRef.current.moveToLocation(parseFloat(lat), parseFloat(lon), 16);
        }
      } else {
        setSearchResult(`「${searchQuery}」の検索結果が見つかりません`);
      }
    } catch (err) {
      setSearchResult(`検索エラー: ${err.message}`);
    }
  };

  // ほ場ID自動生成
  const generateFieldCode = () => {
    const existingIds = new Set(fields.map((f) => f.field_code));
    let num = fields.length + 1;
    let fieldCode = `F${String(num).padStart(3, '0')}`;
    while (existingIds.has(fieldCode)) {
      num++;
      fieldCode = `F${String(num).padStart(3, '0')}`;
    }
    return fieldCode;
  };

  // ほ場登録
  const handleRegister = async (e) => {
    e.preventDefault();

    if (!drawnCoords || drawnCoords.length < 3) {
      setMessage({ type: 'error', text: '地図上でポリゴンを描画してください' });
      return;
    }

    try {
      // ほ場IDを自動生成
      const fieldCode = generateFieldCode();

      const createData = {
        field_code: fieldCode,
        field_name: formData.field_name.trim() || null,
        district: formData.district.trim() || null,
        area_ha: drawnArea / 10000,
        beet_forbidden: formData.beet_forbidden,
        coordinates_json: JSON.stringify(drawnCoords),
      };

      // 初期作付情報（任意）
      if (formData.crop_year && formData.crop_name) {
        createData.crop_year = formData.crop_year;
        createData.crop_name = formData.crop_name;
      }

      await fieldApi.create(createData);

      const cropMsg = formData.crop_name ? `（${formData.crop_name}）` : '';
      setMessage({ type: 'success', text: `ほ場「${fieldCode}」${cropMsg}を登録しました` });
      setFormData({ field_name: '', district: '', beet_forbidden: false, crop_year: '', crop_name: '' });
      setDrawnCoords(null);
      setDrawnArea(0);

      if (mapRef.current?.clearDrawing) {
        mapRef.current.clearDrawing();
      }

      loadFields();
    } catch (err) {
      setMessage({ type: 'error', text: err.response?.data?.detail || '登録に失敗しました' });
    }
  };

  // ほ場削除
  const handleDelete = async () => {
    if (!deleteId.trim()) {
      setMessage({ type: 'error', text: '削除するほ場IDを入力してください' });
      return;
    }

    const field = fields.find((f) => f.field_code === deleteId.trim());
    if (!field) {
      setMessage({ type: 'error', text: `ほ場「${deleteId}」が見つかりません` });
      return;
    }

    if (!confirm(`ほ場「${deleteId}」を削除しますか？`)) {
      return;
    }

    try {
      await fieldApi.delete(field.id);
      setMessage({ type: 'success', text: `ほ場「${deleteId}」を削除しました` });
      setDeleteId('');
      loadFields();
    } catch (err) {
      setMessage({ type: 'error', text: '削除に失敗しました' });
    }
  };

  // KMLインポート - ファイル選択
  const handleFileSelect = (e) => {
    const file = e.target.files?.[0];
    if (file) {
      const ext = file.name.toLowerCase().split('.').pop();
      if (ext !== 'kml' && ext !== 'kmz') {
        setMessage({ type: 'error', text: 'KMLまたはKMZファイルを選択してください' });
        return;
      }
      setImportFile(file);
      setImportedFields([]);
      setMessage(null);
    }
  };

  // KMLインポート - 実行
  const handleImportKml = async () => {
    if (!importFile) {
      setMessage({ type: 'error', text: 'ファイルを選択してください' });
      return;
    }

    setIsImporting(true);
    setMessage(null);

    try {
      // KMLインポートAPI呼び出し
      const formData = new FormData();
      formData.append('file', importFile);
      const response = await fieldApi.importKml(formData);
      setImportedFields(response.imported_fields || []);

      // 結果メッセージ
      const importedCount = response.imported_fields?.length || 0;
      const errorCount = response.errors?.length || 0;

      if (importedCount > 0) {
        setMessage({
          type: 'success',
          text: `${importedCount}件のほ場をインポートしました。${errorCount > 0 ? `（${errorCount}件のエラー）` : ''}`,
        });
        // ほ場一覧を再読み込み
        loadFields();
      } else if (errorCount > 0) {
        setMessage({
          type: 'error',
          text: `インポートに失敗しました: ${response.errors.join(', ')}`,
        });
      } else {
        setMessage({
          type: 'info',
          text: 'KMLファイルからほ場データを抽出できませんでした。',
        });
      }
    } catch (err) {
      console.error('Import error:', err);
      setMessage({ type: 'error', text: err.response?.data?.detail || 'インポートに失敗しました' });
    } finally {
      setIsImporting(false);
    }
  };

  // KMLインポート - クリア
  const handleClearImport = () => {
    setImportFile(null);
    setImportedFields([]);
    setKmlPreviewData([]);
    setKmlCoordsData([]);
    setBulkCrop('');
    setBulkBeetForbidden(false);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  // ============================================
  // KMLプレビュー編集機能（2段階インポート）
  // ============================================

  /**
   * KML/KMZファイルをサーバーで解析してプレビューデータを生成
   */
  const handleParseKml = async () => {
    if (!importFile) {
      setMessage({ type: 'error', text: 'ファイルを選択してください' });
      return;
    }

    setIsParsing(true);
    setMessage(null);

    try {
      const formData = new FormData();
      formData.append('file', importFile);
      const response = await fieldApi.previewKml(formData);

      const parsedFields = response.fields || [];
      if (parsedFields.length === 0) {
        setMessage({ type: 'info', text: 'ファイルからほ場データを抽出できませんでした。' });
        setIsParsing(false);
        return;
      }

      const previewData = [];
      const coordsData = [];
      const existingIds = new Set(fields.map((f) => f.field_code));

      parsedFields.forEach((pf, idx) => {
        const name = pf.name || `ほ場${idx + 1}`;
        const coords = pf.coordinates || [];
        const areaHa = pf.area_ha || 0;

        // ほ場IDを生成（既存ほ場との重複回避）
        let fieldId = name.replace(/[^a-zA-Z0-9_-]/g, '_').substring(0, 20) || `KML${idx + 1}`;
        let suffix = 1;
        const baseId = fieldId;
        while (existingIds.has(fieldId) || previewData.some((p) => p.field_id === fieldId)) {
          fieldId = `${baseId}_${suffix++}`;
        }

        previewData.push({
          field_id: fieldId,
          field_name: name,
          area_ha: areaHa,
          area_a: areaHa * 100,
          crop: '',
          beet_forbidden: false,
        });

        coordsData.push({
          field_id: fieldId,
          coordinates: coords,
        });
      });

      setKmlPreviewData(previewData);
      setKmlCoordsData(coordsData);
      setMessage({ type: 'success', text: `${previewData.length}件のほ場を検出しました。作物・てんさい禁止を設定して登録してください。` });
    } catch (err) {
      console.error('KML parse error:', err);
      const detail = err.response?.data?.detail || err.message || '不明なエラー';
      setMessage({ type: 'error', text: `解析エラー: ${detail}` });
    } finally {
      setIsParsing(false);
    }
  };

  /**
   * プレビューデータの1行を更新
   */
  const handlePreviewRowChange = (idx, field, value) => {
    setKmlPreviewData((prev) => {
      const newData = [...prev];
      newData[idx] = { ...newData[idx], [field]: value };
      return newData;
    });
  };

  /**
   * 全行に作物を一括適用
   */
  const handleApplyBulkCrop = () => {
    if (!bulkCrop) {
      setMessage({ type: 'error', text: '一括適用する作物を選択してください' });
      return;
    }
    setKmlPreviewData((prev) =>
      prev.map((row) => ({ ...row, crop: bulkCrop }))
    );
    setMessage({ type: 'success', text: `全${kmlPreviewData.length}件に「${bulkCrop}」を適用しました` });
  };

  /**
   * 全行にてんさい禁止を一括適用
   */
  const handleApplyBulkBeetForbidden = () => {
    setKmlPreviewData((prev) =>
      prev.map((row) => ({ ...row, beet_forbidden: bulkBeetForbidden }))
    );
    setMessage({ type: 'success', text: `全${kmlPreviewData.length}件にてんさい禁止「${bulkBeetForbidden ? 'ON' : 'OFF'}」を適用しました` });
  };

  /**
   * プレビューから一括登録
   */
  const handleRegisterAllKml = async () => {
    if (kmlPreviewData.length === 0) {
      setMessage({ type: 'error', text: '登録するデータがありません' });
      return;
    }

    setIsRegistering(true);
    setMessage(null);

    let successCount = 0;
    const errors = [];

    for (let i = 0; i < kmlPreviewData.length; i++) {
      const preview = kmlPreviewData[i];
      const coords = kmlCoordsData.find((c) => c.field_id === preview.field_id);

      if (!coords) {
        errors.push(`${preview.field_id}: 座標データなし`);
        continue;
      }

      try {
        const createData = {
          field_code: preview.field_id,
          field_name: preview.field_name || null,
          district: null,
          area_ha: preview.area_ha,
          beet_forbidden: preview.beet_forbidden,
          coordinates_json: JSON.stringify(coords.coordinates),
        };

        // 作付情報（任意）
        if (kmlYear && preview.crop) {
          createData.crop_year = kmlYear;
          createData.crop_name = preview.crop;
        }

        await fieldApi.create(createData);
        successCount++;
      } catch (err) {
        const detail = err.response?.data?.detail || err.message;
        errors.push(`${preview.field_id}: ${detail}`);
      }
    }

    // 結果メッセージ
    if (errors.length === 0) {
      setMessage({ type: 'success', text: `${successCount}件のほ場を登録しました` });
      handleClearImport();
      loadFields();
    } else {
      setMessage({
        type: errors.length === kmlPreviewData.length ? 'error' : 'warning',
        text: `${successCount}件登録、${errors.length}件エラー: ${errors.slice(0, 3).join('; ')}${errors.length > 3 ? '...' : ''}`,
      });
      if (successCount > 0) {
        loadFields();
      }
    }

    setIsRegistering(false);
  };

  // KMLエクスポート
  const handleExportKml = () => {
    const fieldsWithCoords = fields.filter((f) => f.coordinates_json);
    if (fieldsWithCoords.length === 0) {
      setMessage({ type: 'error', text: 'エクスポートするほ場がありません' });
      return;
    }

    let kmlContent = `<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <name>ほ場一覧</name>`;

    fieldsWithCoords.forEach((field) => {
      let coords;
      try {
        coords = typeof field.coordinates_json === 'string'
          ? JSON.parse(field.coordinates_json)
          : field.coordinates_json;
      } catch {
        return;
      }

      if (!coords || coords.length < 3) return;

      const coordsStr = coords.map((c) => `${c[1]},${c[0]},0`).join(' ');

      kmlContent += `
    <Placemark>
      <name>${field.field_code}</name>
      <description>${field.field_name || ''}</description>
      <Polygon>
        <outerBoundaryIs>
          <LinearRing>
            <coordinates>${coordsStr}</coordinates>
          </LinearRing>
        </outerBoundaryIs>
      </Polygon>
    </Placemark>`;
    });

    kmlContent += `
  </Document>
</kml>`;

    const blob = new Blob([kmlContent], { type: 'application/vnd.google-earth.kml+xml' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'fields.kml';
    a.click();
    URL.revokeObjectURL(url);

    setMessage({ type: 'success', text: `${fieldsWithCoords.length}件のほ場をKMLでエクスポートしました` });
  };

  return (
    <div className="field-register-page">
      <div className="page-header">
        <h1>🗺️ ほ場登録</h1>
      </div>

      <p className="page-description">
        地図上でポリゴンを描画し、ほ場の位置と面積を登録します。
      </p>

      {message && (
        <div className={`message ${message.type}`}>
          {message.text}
        </div>
      )}

      <div className="field-register-layout">
        <div className="map-section">
          {/* 住所検索 */}
          <div className="search-bar">
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
              placeholder="住所・地名検索（例: 札幌市、十勝、美瑛町）"
            />
            <button onClick={handleSearch} className="btn-secondary">
              🔍 検索
            </button>
          </div>
          {searchResult && <p className="search-result">{searchResult}</p>}

          {/* 筆ポリゴン表示トグル */}
          <div className="fude-toggle">
            <label className="checkbox-label">
              <input
                type="checkbox"
                checked={showFudePolygons}
                onChange={handleToggleFudePolygons}
                disabled={isFudeLoading}
              />
              <span>筆ポリゴン表示{isFudeLoading ? '（読込中...）' : ''}</span>
            </label>
            {showFudePolygons && (
              <button onClick={loadFudePolygons} className="btn-secondary btn-small" disabled={isFudeLoading}>
                🔄 再読込
              </button>
            )}
            {fudePolygons.length > 0 && (
              <span className="fude-count">（{fudePolygons.length}件）</span>
            )}
          </div>

          {/* 地図 */}
          <div ref={mapRef}>
            <FieldMap
              fields={fields}
              onPolygonCreated={handlePolygonCreated}
              onFieldClick={handleFieldClick}
              onFudePolygonClick={handleFudePolygonClick}
              selectedFieldId={selectedField?.id}
              fudePolygons={fudePolygons}
              showFudePolygons={showFudePolygons}
            />
          </div>

          <div className="map-instructions">
            <strong>使い方:</strong>
            <ol>
              <li>右上の多角形ツール（六角形アイコン）をクリック</li>
              <li>地図上をクリックしてポリゴンの頂点を打つ</li>
              <li>最後にダブルクリックまたは最初の点をクリックして完了</li>
              <li>編集は鉛筆アイコン、削除はゴミ箱アイコン</li>
            </ol>
          </div>
        </div>

        <div className="form-section">
          {/* 登録フォーム */}
          <div className="form-card">
            <h3>ほ場情報</h3>
            <form onSubmit={handleRegister}>
              <div className="form-group">
                <label>ほ場名</label>
                <input
                  type="text"
                  value={formData.field_name}
                  onChange={(e) => setFormData({ ...formData, field_name: e.target.value })}
                  placeholder="例: 北1号"
                />
              </div>
              <div className="form-group">
                <label>地区</label>
                <input
                  type="text"
                  value={formData.district}
                  onChange={(e) => setFormData({ ...formData, district: e.target.value })}
                  placeholder="例: 北地区"
                />
              </div>
              <div className="form-group checkbox">
                <label>
                  <input
                    type="checkbox"
                    checked={formData.beet_forbidden}
                    onChange={(e) => setFormData({ ...formData, beet_forbidden: e.target.checked })}
                  />
                  馬鈴薯・てんさい禁止
                </label>
              </div>

              {/* 初期作付情報（任意） */}
              <div className="initial-crop-section" style={{
                marginTop: '16px',
                padding: '12px',
                background: '#f8f9fa',
                borderRadius: '8px',
                border: '1px solid #e9ecef'
              }}>
                <label style={{ fontWeight: 'bold', marginBottom: '8px', display: 'block' }}>
                  🌾 初期作付情報（任意）
                </label>
                <p style={{ fontSize: '0.85em', color: '#666', marginBottom: '12px' }}>
                  ほ場登録と同時に今年度の作付を設定できます
                </p>
                <div className="form-row" style={{ display: 'flex', gap: '12px' }}>
                  <div className="form-group" style={{ flex: 1 }}>
                    <label>作付年度</label>
                    <select
                      value={formData.crop_year}
                      onChange={(e) => setFormData({ ...formData, crop_year: e.target.value })}
                    >
                      <option value="">-- 選択しない --</option>
                      {yearChoices.map((y) => (
                        <option key={y.value} value={y.value}>{y.label}</option>
                      ))}
                    </select>
                  </div>
                  <div className="form-group" style={{ flex: 2 }}>
                    <label>作物</label>
                    <select
                      value={formData.crop_name}
                      onChange={(e) => setFormData({ ...formData, crop_name: e.target.value })}
                      disabled={!formData.crop_year}
                    >
                      <option value="">-- 選択しない --</option>
                      {crops.map((c) => (
                        <option key={c.crop_id} value={c.crop_name}>
                          {c.custom_name || c.crop_name}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>
              </div>

              {drawnArea > 0 && (
                <div className="drawn-area-info">
                  <strong>描画した面積:</strong> {(drawnArea / 10000).toFixed(4)} ha ({(drawnArea / 100).toFixed(2)} a)
                </div>
              )}

              <button type="submit" className="btn-primary btn-large">
                ✅ 登録
              </button>
            </form>
          </div>

          {/* 削除 */}
          <div className="form-card">
            <h3>🗑️ 削除</h3>
            <div className="form-group">
              <label>削除するほ場ID</label>
              <input
                type="text"
                value={deleteId}
                onChange={(e) => setDeleteId(e.target.value)}
                placeholder="削除したいほ場IDを入力"
              />
            </div>
            <button onClick={handleDelete} className="btn-danger">
              🗑️ 削除
            </button>
          </div>

          {/* KMLインポート（2段階：プレビュー編集→一括登録） */}
          <div className="form-card">
            <h3>📤 KML/KMZインポート</h3>
            <div className="form-group">
              <label>KML/KMZファイル選択</label>
              <input
                ref={fileInputRef}
                type="file"
                accept=".kml,.kmz"
                onChange={handleFileSelect}
                className="file-input"
              />
            </div>
            {importFile && (
              <div className="import-file-info">
                <span>📄 {importFile.name}</span>
                <span className="file-size">({(importFile.size / 1024).toFixed(1)} KB)</span>
              </div>
            )}
            <div className="button-group">
              <button
                onClick={handleParseKml}
                className="btn-primary"
                disabled={!importFile || isParsing}
                title="KML/KMZファイルを解析してプレビュー表示"
              >
                {isParsing ? '⏳ 解析中...' : '📋 プレビュー'}
              </button>
              <button
                onClick={handleImportKml}
                className="btn-secondary"
                disabled={!importFile || isImporting}
                title="プレビューなしで直接インポート"
              >
                {isImporting ? '⏳ 処理中...' : '📤 直接インポート'}
              </button>
              {importFile && (
                <button onClick={handleClearImport} className="btn-secondary">
                  ✖ クリア
                </button>
              )}
            </div>

            {/* KMLプレビュー編集テーブル */}
            {kmlPreviewData.length > 0 && (
              <div className="kml-preview-section" style={{ marginTop: '16px' }}>
                <h4>📋 プレビュー編集 ({kmlPreviewData.length}件)</h4>

                {/* 一括設定エリア */}
                <div className="bulk-settings" style={{
                  padding: '12px',
                  background: '#e8f4fd',
                  borderRadius: '8px',
                  marginBottom: '12px',
                  border: '1px solid #b8daff'
                }}>
                  <strong>一括設定</strong>
                  <div style={{ display: 'flex', gap: '8px', marginTop: '8px', flexWrap: 'wrap', alignItems: 'center' }}>
                    <select
                      value={kmlYear}
                      onChange={(e) => setKmlYear(e.target.value)}
                      style={{ padding: '4px 8px' }}
                    >
                      {yearChoices.map((y) => (
                        <option key={y.value} value={y.value}>{y.label}</option>
                      ))}
                    </select>
                    <select
                      value={bulkCrop}
                      onChange={(e) => setBulkCrop(e.target.value)}
                      style={{ padding: '4px 8px', minWidth: '120px' }}
                    >
                      <option value="">-- 作物選択 --</option>
                      {crops.map((c) => (
                        <option key={c.crop_id} value={c.crop_name}>
                          {c.custom_name || c.crop_name}
                        </option>
                      ))}
                    </select>
                    <button onClick={handleApplyBulkCrop} className="btn-secondary btn-small">
                      📋 作物を全ほ場に適用
                    </button>
                  </div>
                  <div style={{ display: 'flex', gap: '8px', marginTop: '8px', alignItems: 'center' }}>
                    <label style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                      <input
                        type="checkbox"
                        checked={bulkBeetForbidden}
                        onChange={(e) => setBulkBeetForbidden(e.target.checked)}
                      />
                      てんさい禁止
                    </label>
                    <button onClick={handleApplyBulkBeetForbidden} className="btn-secondary btn-small">
                      📋 禁止設定を全ほ場に適用
                    </button>
                  </div>
                </div>

                {/* プレビューテーブル */}
                <div style={{ maxHeight: '300px', overflowY: 'auto', border: '1px solid #ddd', borderRadius: '4px' }}>
                  <table className="data-table" style={{ fontSize: '0.85em' }}>
                    <thead style={{ position: 'sticky', top: 0, background: '#f8f9fa' }}>
                      <tr>
                        <th style={{ width: '15%' }}>ほ場ID</th>
                        <th style={{ width: '25%' }}>ほ場名</th>
                        <th style={{ width: '12%' }}>面積(ha)</th>
                        <th style={{ width: '25%' }}>作物</th>
                        <th style={{ width: '10%' }}>禁止</th>
                      </tr>
                    </thead>
                    <tbody>
                      {kmlPreviewData.map((row, idx) => (
                        <tr key={idx}>
                          <td>
                            <input
                              type="text"
                              value={row.field_id}
                              onChange={(e) => handlePreviewRowChange(idx, 'field_id', e.target.value)}
                              style={{ width: '100%', padding: '2px 4px' }}
                            />
                          </td>
                          <td>
                            <input
                              type="text"
                              value={row.field_name}
                              onChange={(e) => handlePreviewRowChange(idx, 'field_name', e.target.value)}
                              style={{ width: '100%', padding: '2px 4px' }}
                            />
                          </td>
                          <td style={{ textAlign: 'right' }}>{row.area_ha.toFixed(2)}</td>
                          <td>
                            <select
                              value={row.crop}
                              onChange={(e) => handlePreviewRowChange(idx, 'crop', e.target.value)}
                              style={{ width: '100%', padding: '2px 4px' }}
                            >
                              <option value="">-- 未設定 --</option>
                              {crops.map((c) => (
                                <option key={c.crop_id} value={c.crop_name}>
                                  {c.custom_name || c.crop_name}
                                </option>
                              ))}
                            </select>
                          </td>
                          <td style={{ textAlign: 'center' }}>
                            <input
                              type="checkbox"
                              checked={row.beet_forbidden}
                              onChange={(e) => handlePreviewRowChange(idx, 'beet_forbidden', e.target.checked)}
                            />
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                {/* 一括登録ボタン */}
                <div style={{ marginTop: '12px', textAlign: 'center' }}>
                  <button
                    onClick={handleRegisterAllKml}
                    className="btn-primary btn-large"
                    disabled={isRegistering || kmlPreviewData.length === 0}
                  >
                    {isRegistering ? '⏳ 登録中...' : `✅ ${kmlPreviewData.length}件を一括登録`}
                  </button>
                </div>
              </div>
            )}

            {/* 直接インポート結果（KMZ用） */}
            {importedFields.length > 0 && kmlPreviewData.length === 0 && (
              <div className="import-preview">
                <h4>インポート完了 ({importedFields.length}件)</h4>
                <ul>
                  {importedFields.slice(0, 5).map((f, idx) => (
                    <li key={idx}>
                      {f.name || `ほ場${idx + 1}`}
                      {f.area_ha > 0 && ` - ${f.area_ha.toFixed(2)} ha`}
                    </li>
                  ))}
                  {importedFields.length > 5 && (
                    <li>...他 {importedFields.length - 5} 件</li>
                  )}
                </ul>
              </div>
            )}
          </div>

          {/* エクスポート */}
          <div className="form-card">
            <h3>📥 エクスポート</h3>
            <button onClick={handleExportKml} className="btn-secondary">
              📥 KMLでエクスポート
            </button>
          </div>
        </div>
      </div>

      {/* 登録済みほ場一覧 */}
      <div className="fields-section">
        <h2>📋 登録済みほ場一覧</h2>
        {isLoading ? (
          <p>読み込み中...</p>
        ) : fields.length === 0 ? (
          <p className="empty-message">ほ場が登録されていません</p>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>ほ場ID</th>
                <th>ほ場名</th>
                <th>地区</th>
                <th>面積(ha)</th>
                <th>禁止</th>
              </tr>
            </thead>
            <tbody>
              {fields.map((field) => (
                <tr
                  key={field.id}
                  className={selectedField?.id === field.id ? 'selected' : ''}
                  onClick={() => handleFieldClick(field)}
                >
                  <td>{field.field_code}</td>
                  <td>{field.field_name || '-'}</td>
                  <td>{field.district || '-'}</td>
                  <td>{field.area_ha?.toFixed(2) || '-'}</td>
                  <td>{field.beet_forbidden ? '🚫' : '-'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
