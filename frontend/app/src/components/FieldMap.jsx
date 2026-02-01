/**
 * ほ場地図コンポーネント
 * Leaflet + leaflet-draw によるポリゴン描画・編集
 */

import { useEffect, useRef, useState, useCallback } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import 'leaflet-draw';
import 'leaflet-draw/dist/leaflet.draw.css';

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
  selectedFieldId = null
}) {
  const mapRef = useRef(null);
  const mapInstanceRef = useRef(null);
  const drawnItemsRef = useRef(null);
  const existingFieldsRef = useRef(null);
  const [areaInfo, setAreaInfo] = useState(null);

  // 地図初期化
  useEffect(() => {
    if (mapInstanceRef.current) return;

    const map = L.map(mapRef.current).setView([DEFAULT_LAT, DEFAULT_LNG], DEFAULT_ZOOM);
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

    return () => {
      map.remove();
      mapInstanceRef.current = null;
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

  // ref経由でメソッドを公開
  useEffect(() => {
    if (mapRef.current) {
      mapRef.current.moveToLocation = moveToLocation;
      mapRef.current.clearDrawing = clearDrawing;
      mapRef.current.setPolygon = setPolygon;
    }
  }, [moveToLocation, clearDrawing, setPolygon]);

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
