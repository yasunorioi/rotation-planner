/**
 * ほ場ミニ地図コンポーネント（表示専用）
 * 指定座標のポリゴンをズームして表示する軽量コンポーネント
 */

import { useEffect, useRef, useState } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';

export default function FieldMiniMap({ coordinates, height = '200px' }) {
  const mapRef = useRef(null);
  const mapInstanceRef = useRef(null);
  const [zoomLevel, setZoomLevel] = useState(null);

  useEffect(() => {
    if (!mapRef.current || !coordinates || coordinates.length < 3) return;

    // 既存マップがあれば破棄
    if (mapInstanceRef.current) {
      mapInstanceRef.current.remove();
      mapInstanceRef.current = null;
    }

    const map = L.map(mapRef.current, {
      zoomControl: true,
      attributionControl: false,
      dragging: true,
      scrollWheelZoom: false,
    });
    mapInstanceRef.current = map;

    map.on('zoomend', () => setZoomLevel(map.getZoom()));

    // 衛星写真
    L.tileLayer(
      'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
      { maxZoom: 19 }
    ).addTo(map);

    // ポリゴン描画
    const polygon = L.polygon(coordinates, {
      color: '#ff4444',
      fillColor: '#ff4444',
      fillOpacity: 0.3,
      weight: 2,
    }).addTo(map);

    // ポリゴンにフィット
    const bounds = polygon.getBounds();
    if (bounds.isValid()) {
      map.fitBounds(bounds, { padding: [20, 20], maxZoom: 16 });
    }

    return () => {
      if (mapInstanceRef.current) {
        mapInstanceRef.current.remove();
        mapInstanceRef.current = null;
      }
    };
  }, [coordinates]);

  if (!coordinates || coordinates.length < 3) {
    return null;
  }

  return (
    <div style={{ position: 'relative', marginBottom: '12px' }}>
      <div
        ref={mapRef}
        style={{
          height,
          width: '100%',
          borderRadius: '8px',
          border: '1px solid #ddd',
        }}
      />
      {zoomLevel !== null && (
        <div style={{
          position: 'absolute',
          bottom: '8px',
          right: '8px',
          background: 'rgba(0,0,0,0.6)',
          color: '#fff',
          padding: '4px 10px',
          borderRadius: '4px',
          fontSize: '1.1em',
          fontWeight: 'bold',
          zIndex: 1000,
          pointerEvents: 'none',
        }}>
          Zoom {zoomLevel}
        </div>
      )}
    </div>
  );
}
