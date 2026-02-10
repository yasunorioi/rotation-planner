/**
 * ほ場地図コンポーネント
 * Leaflet + leaflet-draw によるポリゴン描画・編集
 */

import { useEffect, useRef, useState, useCallback } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import 'leaflet-draw/dist/leaflet.draw.css';

// leaflet-draw は window.L を参照するため、グローバルに設定
// これはモジュールのトップレベルで実行される
window.L = L;

// デフォルトマーカーアイコンの修正
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon-2x.png',
  iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png',
});

// 北海道の初期位置
const DEFAULT_LAT = 42.919253;
const DEFAULT_LNG = 141.574635;
const DEFAULT_ZOOM = 14;

export default function FieldMap({
  fields = [],
  onPolygonCreated,
  onFieldClick,
  onFudePolygonClick,
  selectedFieldId = null,
  fudePolygons = [],
  showFudePolygons = false,
  previewPolygons = [],
}) {
  const mapRef = useRef(null);
  const mapInstanceRef = useRef(null);
  const drawnItemsRef = useRef(null);
  const existingFieldsRef = useRef(null);
  const fudePolygonsRef = useRef(null);
  const previewPolygonsRef = useRef(null);
  const [areaInfo, setAreaInfo] = useState(null);

  // 地図初期化
  useEffect(() => {
    if (mapInstanceRef.current) return;

    let map = null;

    // leaflet-draw を動的にインポート（window.L が設定された後に読み込む）
    const initMap = async () => {
      // leaflet-draw は window.L を参照するため、動的インポートで読み込む
      await import('leaflet-draw');

      // コンポーネントがアンマウントされた場合は初期化しない
      if (!mapRef.current) return;

      map = L.map(mapRef.current).setView([DEFAULT_LAT, DEFAULT_LNG], DEFAULT_ZOOM);
      mapInstanceRef.current = map;

      // ベースレイヤー
      const esriSatellite = L.tileLayer(
        'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
        { attribution: '&copy; Esri', maxZoom: 19 }
      );

      const gsiPhoto = L.tileLayer(
        'https://cyberjapandata.gsi.go.jp/xyz/seamlessphoto/{z}/{x}/{y}.jpg',
        { attribution: '&copy; 国土地理院', maxZoom: 18 }
      );

      const gsiStd = L.tileLayer(
        'https://cyberjapandata.gsi.go.jp/xyz/std/{z}/{x}/{y}.png',
        { attribution: '&copy; 国土地理院', maxZoom: 18 }
      );

      const osm = L.tileLayer(
        'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
        { attribution: '&copy; OpenStreetMap', maxZoom: 19 }
      );

      esriSatellite.addTo(map);

      L.control.layers({
        '衛星写真（Esri）': esriSatellite,
        '航空写真（国土地理院）': gsiPhoto,
        '地図（国土地理院）': gsiStd,
        'OpenStreetMap': osm,
      }).addTo(map);

      // 描画レイヤー
      const drawnItems = new L.FeatureGroup();
      map.addLayer(drawnItems);
      drawnItemsRef.current = drawnItems;

      // 既存ほ場レイヤー
      const existingFields = new L.FeatureGroup();
      map.addLayer(existingFields);
      existingFieldsRef.current = existingFields;

      // 筆ポリゴンレイヤー
      const fudePolygonsLayer = new L.FeatureGroup();
      map.addLayer(fudePolygonsLayer);
      fudePolygonsRef.current = fudePolygonsLayer;

      // KMLプレビューレイヤー
      const previewPolygonsLayer = new L.FeatureGroup();
      map.addLayer(previewPolygonsLayer);
      previewPolygonsRef.current = previewPolygonsLayer;

      // 描画コントロール
      const drawControl = new L.Control.Draw({
        position: 'topright',
        draw: {
          polygon: {
            allowIntersection: false,
            showArea: true,
            shapeOptions: {
              color: '#3388ff',
              fillColor: '#3388ff',
              fillOpacity: 0.3,
            },
          },
          polyline: false,
          circle: false,
          rectangle: false,
          marker: false,
          circlemarker: false,
        },
        edit: {
          featureGroup: drawnItems,
          remove: true,
          edit: true,
        },
      });
      map.addControl(drawControl);

      // ポリゴン作成イベント
      map.on(L.Draw.Event.CREATED, (e) => {
        drawnItems.clearLayers();
        drawnItems.addLayer(e.layer);

        const latlngs = e.layer.getLatLngs()[0];
        const coords = latlngs.map((ll) => [ll.lat, ll.lng]);
        const area = L.GeometryUtil.geodesicArea(latlngs);

        setAreaInfo({
          area_m2: area,
          area_a: (area / 100).toFixed(2),
          area_ha: (area / 10000).toFixed(4),
        });

        if (onPolygonCreated) {
          onPolygonCreated(coords, area);
        }
      });

      // ポリゴン編集イベント
      map.on(L.Draw.Event.EDITED, (e) => {
        e.layers.eachLayer((layer) => {
          const latlngs = layer.getLatLngs()[0];
          const coords = latlngs.map((ll) => [ll.lat, ll.lng]);
          const area = L.GeometryUtil.geodesicArea(latlngs);

          setAreaInfo({
            area_m2: area,
            area_a: (area / 100).toFixed(2),
            area_ha: (area / 10000).toFixed(4),
          });

          if (onPolygonCreated) {
            onPolygonCreated(coords, area);
          }
        });
      });

      // ポリゴン削除イベント
      map.on(L.Draw.Event.DELETED, () => {
        setAreaInfo(null);
        if (onPolygonCreated) {
          onPolygonCreated(null, 0);
        }
      });
    };

    initMap();

    return () => {
      if (mapInstanceRef.current) {
        mapInstanceRef.current.remove();
        mapInstanceRef.current = null;
      }
    };
  }, []);

  // 既存ほ場の表示更新
  useEffect(() => {
    if (!existingFieldsRef.current) return;

    existingFieldsRef.current.clearLayers();

    fields.forEach((field) => {
      if (!field.coordinates_json) return;

      let coords;
      try {
        coords = typeof field.coordinates_json === 'string'
          ? JSON.parse(field.coordinates_json)
          : field.coordinates_json;
      } catch {
        return;
      }

      if (!coords || coords.length < 3) return;

      const isSelected = field.id === selectedFieldId;
      const polygon = L.polygon(coords, {
        color: isSelected ? '#ff0000' : '#28a745',
        fillColor: isSelected ? '#ff0000' : '#28a745',
        fillOpacity: isSelected ? 0.5 : 0.3,
        weight: isSelected ? 3 : 2,
      });

      polygon.bindPopup(`
        <div>
          <b>${field.field_code}</b><br>
          ${field.field_name || ''}<br>
          ${field.area_ha?.toFixed(2) || ''} ha
        </div>
      `);

      polygon.on('click', () => {
        if (onFieldClick) {
          onFieldClick(field);
        }
      });

      existingFieldsRef.current.addLayer(polygon);
    });
  }, [fields, selectedFieldId, onFieldClick]);

  // 筆ポリゴンの表示更新
  useEffect(() => {
    if (!fudePolygonsRef.current) return;

    fudePolygonsRef.current.clearLayers();

    if (!showFudePolygons || !fudePolygons.length) return;

    fudePolygons.forEach((fude) => {
      if (!fude.coordinates || fude.coordinates.length < 3) return;

      const polygon = L.polygon(fude.coordinates, {
        color: '#ff8c00',
        fillColor: '#ffa500',
        fillOpacity: 0.2,
        weight: 1,
        dashArray: '3, 3',
      });

      // 土地種別の表示名
      const landTypeNames = { '100': '田', '200': '畑' };
      const landTypeName = landTypeNames[fude.land_type] || fude.land_type || '-';

      polygon.bindPopup(`
        <div>
          <b>筆ポリゴン</b><br>
          種別: ${landTypeName}<br>
          面積: ${fude.area_ha?.toFixed(2) || '-'} ha<br>
          <button onclick="window.__selectFudePolygon && window.__selectFudePolygon('${fude.fude_id}')" style="margin-top:8px;padding:4px 8px;cursor:pointer;">
            選択してほ場に取り込み
          </button>
        </div>
      `);

      polygon.on('click', () => {
        if (onFudePolygonClick) {
          onFudePolygonClick(fude);
        }
      });

      fudePolygonsRef.current.addLayer(polygon);
    });
  }, [fudePolygons, showFudePolygons, onFudePolygonClick]);

  // KMLプレビューポリゴンの表示
  useEffect(() => {
    if (!previewPolygonsRef.current) return;

    previewPolygonsRef.current.clearLayers();

    if (!previewPolygons.length) return;

    previewPolygons.forEach((item) => {
      const coords = item.coordinates;
      if (!coords || coords.length < 3) return;

      const polygon = L.polygon(coords, {
        color: '#1976d2',
        fillColor: '#42a5f5',
        fillOpacity: 0.25,
        weight: 2,
        dashArray: '5, 5',
      });

      polygon.bindPopup(`
        <div>
          <b>${item.field_name || item.field_id || 'プレビュー'}</b><br>
          ${item.area_ha ? item.area_ha.toFixed(2) + ' ha' : ''}
        </div>
      `);

      previewPolygonsRef.current.addLayer(polygon);
    });

    // プレビューポリゴンが存在する場合、地図をフィット
    if (mapInstanceRef.current && previewPolygonsRef.current.getLayers().length > 0) {
      const bounds = previewPolygonsRef.current.getBounds();
      if (bounds.isValid()) {
        mapInstanceRef.current.fitBounds(bounds, { padding: [50, 50] });
      }
    }
  }, [previewPolygons]);

  // 住所検索で地図移動
  const moveToLocation = useCallback((lat, lng, zoom = 16) => {
    if (mapInstanceRef.current) {
      mapInstanceRef.current.setView([lat, lng], zoom);
    }
  }, []);

  // 描画クリア
  const clearDrawing = useCallback(() => {
    if (drawnItemsRef.current) {
      drawnItemsRef.current.clearLayers();
      setAreaInfo(null);
      if (onPolygonCreated) {
        onPolygonCreated(null, 0);
      }
    }
  }, [onPolygonCreated]);

  // 外部からのポリゴン設定（筆ポリゴン選択時など）
  const setPolygon = useCallback((coords) => {
    if (!drawnItemsRef.current || !coords || coords.length < 3) return;

    drawnItemsRef.current.clearLayers();

    const polygon = L.polygon(coords, {
      color: '#3388ff',
      fillColor: '#3388ff',
      fillOpacity: 0.3,
    });

    drawnItemsRef.current.addLayer(polygon);

    const latlngs = polygon.getLatLngs()[0];
    const area = L.GeometryUtil.geodesicArea(latlngs);

    setAreaInfo({
      area_m2: area,
      area_a: (area / 100).toFixed(2),
      area_ha: (area / 10000).toFixed(4),
    });

    if (onPolygonCreated) {
      onPolygonCreated(coords, area);
    }
  }, [onPolygonCreated]);

  // 現在の地図範囲を取得
  const getBounds = useCallback(() => {
    if (!mapInstanceRef.current) return null;
    const bounds = mapInstanceRef.current.getBounds();
    return {
      min_lat: bounds.getSouth(),
      max_lat: bounds.getNorth(),
      min_lng: bounds.getWest(),
      max_lng: bounds.getEast(),
    };
  }, []);

  // 現在のズームレベルを取得
  const getZoom = useCallback(() => {
    if (!mapInstanceRef.current) return 14;
    return mapInstanceRef.current.getZoom();
  }, []);

  // ref経由でメソッドを公開
  useEffect(() => {
    if (mapRef.current) {
      mapRef.current.moveToLocation = moveToLocation;
      mapRef.current.clearDrawing = clearDrawing;
      mapRef.current.setPolygon = setPolygon;
      mapRef.current.getBounds = getBounds;
      mapRef.current.getZoom = getZoom;
    }
  }, [moveToLocation, clearDrawing, setPolygon, getBounds, getZoom]);

  return (
    <div className="field-map-container">
      <div ref={mapRef} className="field-map" />
      {areaInfo && (
        <div className="area-info">
          <strong>描画中の面積</strong><br />
          {areaInfo.area_a} a<br />
          {areaInfo.area_ha} ha
        </div>
      )}
    </div>
  );
}
