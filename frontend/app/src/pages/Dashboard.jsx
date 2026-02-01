/**
 * ダッシュボード
 */

import { useEffect } from 'react';
import { Link } from 'react-router-dom';
import { useAuthStore } from '../store/authStore';
import { useFieldStore } from '../store/fieldStore';

export default function Dashboard() {
  const { user } = useAuthStore();
  const { fields, fetchFields, isLoading } = useFieldStore();

  useEffect(() => {
    fetchFields();
  }, [fetchFields]);

  const totalArea = fields.reduce((sum, f) => sum + (f.area_ha || 0), 0);

  return (
    <div className="dashboard">
      <h1>ダッシュボード</h1>
      <p className="welcome">ようこそ、{user?.display_name || user?.username} さん</p>

      <div className="stats-grid">
        <div className="stat-card">
          <div className="stat-value">{fields.length}</div>
          <div className="stat-label">登録ほ場数</div>
        </div>
        <div className="stat-card">
          <div className="stat-value">{totalArea.toFixed(1)} ha</div>
          <div className="stat-label">総面積</div>
        </div>
      </div>

      <div className="quick-links">
        <h2>クイックアクセス</h2>
        <div className="link-grid">
          <Link to="/fields" className="link-card">
            <span className="icon">🗺️</span>
            <span className="label">ほ場一覧</span>
          </Link>
          <Link to="/rotation" className="link-card">
            <span className="icon">🔄</span>
            <span className="label">輪作計画</span>
          </Link>
          <Link to="/plans" className="link-card">
            <span className="icon">📋</span>
            <span className="label">保存済み計画</span>
          </Link>
        </div>
      </div>

      {isLoading && <p>読み込み中...</p>}
    </div>
  );
}
