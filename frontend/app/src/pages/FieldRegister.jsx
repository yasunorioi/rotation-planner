/**
 * ほ場登録ページ
 * 地図上でポリゴン描画、住所検索、KMLインポート/エクスポート
 */

import { useEffect, useState, useRef, useCallback } from 'react';
import { fieldApi } from '../lib/api';
import FieldMap from '../components/FieldMap';

export default function FieldRegister() {
  const [fields, setFields] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [message, setMessage] = useState(null);

  // フォーム状態
  const [formData, setFormData] = useState({
    field_code: '',
    field_name: '',
    district: '',
    beet_forbidden: false,
  });
  const [drawnCoords, setDrawnCoords] = useState(null);
  const [drawnArea, setDrawnArea] = useState(0);

  // 住所検索
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResult, setSearchResult] = useState('');

  // 削除
  const [deleteId, setDeleteId] = useState('');

  // 選択中のほ場
  const [selectedField, setSelectedField] = useState(null);

  const mapRef = useRef(null);

  useEffect(() => {
    loadFields();
  }, []);

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
      field_code: field.field_code,
      field_name: field.field_name || '',
      district: field.district || '',
      beet_forbidden: field.beet_forbidden || false,
    });
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

  // ほ場登録
  const handleRegister = async (e) => {
    e.preventDefault();

    if (!formData.field_code.trim()) {
      setMessage({ type: 'error', text: 'ほ場IDを入力してください' });
      return;
    }

    if (!drawnCoords || drawnCoords.length < 3) {
      setMessage({ type: 'error', text: '地図上でポリゴンを描画してください' });
      return;
    }

    try {
      await fieldApi.create({
        field_code: formData.field_code.trim(),
        field_name: formData.field_name.trim() || null,
        district: formData.district.trim() || null,
        area_ha: drawnArea / 10000,
        beet_forbidden: formData.beet_forbidden,
        coordinates_json: JSON.stringify(drawnCoords),
      });

      setMessage({ type: 'success', text: `ほ場「${formData.field_code}」を登録しました` });
      setFormData({ field_code: '', field_name: '', district: '', beet_forbidden: false });
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

          {/* 地図 */}
          <div ref={mapRef}>
            <FieldMap
              fields={fields}
              onPolygonCreated={handlePolygonCreated}
              onFieldClick={handleFieldClick}
              selectedFieldId={selectedField?.id}
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
            <h3>📝 ほ場情報</h3>
            <form onSubmit={handleRegister}>
              <div className="form-group">
                <label>ほ場ID *</label>
                <input
                  type="text"
                  value={formData.field_code}
                  onChange={(e) => setFormData({ ...formData, field_code: e.target.value })}
                  placeholder="例: F001"
                  required
                />
              </div>
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
