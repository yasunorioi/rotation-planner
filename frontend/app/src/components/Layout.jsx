/**
 * レイアウトコンポーネント
 */

import { useState } from 'react';
import { Link, Outlet, useNavigate, useLocation } from 'react-router-dom';
import { useAuthStore } from '../store/authStore';

export default function Layout() {
  const { user, logout } = useAuthStore();
  const navigate = useNavigate();
  const location = useLocation();
  const [menuOpen, setMenuOpen] = useState(false);
  const [theme, setTheme] = useState(() => {
    const saved = localStorage.getItem('theme') || 'default';
    if (saved !== 'default') {
      document.documentElement.setAttribute('data-theme', saved);
    }
    return saved;
  });

  const handleThemeChange = (e) => {
    const val = e.target.value;
    setTheme(val);
    if (val === 'default') {
      document.documentElement.removeAttribute('data-theme');
      localStorage.removeItem('theme');
    } else {
      document.documentElement.setAttribute('data-theme', val);
      localStorage.setItem('theme', val);
    }
  };

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const isActive = (path) => location.pathname === path;

  const menuItems = [
    { path: '/', label: 'ホーム', icon: '🏠' },
    { path: '/crops', label: '作物設定', icon: '🌱' },
    { path: '/fields', label: 'ほ場一覧', icon: '🗺️' },
    { path: '/field-register', label: 'ほ場登録', icon: '📍' },
    { path: '/rotation', label: '輪作計画', icon: '📊' },
    { path: '/plans', label: '保存済み計画', icon: '📁' },
    { path: '/pesticide-masters', label: '防除マスタ', icon: '💊' },
    { path: '/pesticide-orders', label: '農薬発注', icon: '📦' },
    { path: '/pesticide-records', label: '防除記録', icon: '📋' },
    { path: '/data', label: 'データ管理', icon: '💾' },
  ];

  const adminMenuItems = [
    { path: '/ja', label: 'JA集計', icon: '🏛️' },
    { path: '/users', label: 'ユーザー管理', icon: '👥' },
    { path: '/system', label: 'システム情報', icon: '⚙️' },
  ];

  return (
    <div className="layout">
      <header className="header">
        <div className="header-left">
          <Link to="/" className="logo">
            🌾 農業管理
          </Link>
          <button className="menu-toggle" onClick={() => setMenuOpen(!menuOpen)}>
            ☰
          </button>
        </div>
        <div className="header-right">
          <span className="user-name">{user?.display_name || user?.username}</span>
          <button onClick={handleLogout} className="btn-logout">
            ログアウト
          </button>
        </div>
      </header>
      <div className="layout-body">
        <aside className={`sidebar ${menuOpen ? 'open' : ''}`}>
          <nav className="sidebar-nav">
            <div className="nav-section">
              {menuItems.map((item) => (
                <Link
                  key={item.path}
                  to={item.path}
                  className={`nav-item ${isActive(item.path) ? 'active' : ''}`}
                  onClick={() => setMenuOpen(false)}
                >
                  <span className="nav-icon">{item.icon}</span>
                  <span className="nav-label">{item.label}</span>
                </Link>
              ))}
            </div>
            {user?.role === 'admin' && (
              <div className="nav-section">
                <div className="nav-section-title">管理者メニュー</div>
                {adminMenuItems.map((item) => (
                  <Link
                    key={item.path}
                    to={item.path}
                    className={`nav-item ${isActive(item.path) ? 'active' : ''}`}
                    onClick={() => setMenuOpen(false)}
                  >
                    <span className="nav-icon">{item.icon}</span>
                    <span className="nav-label">{item.label}</span>
                  </Link>
                ))}
              </div>
            )}
            <div className="nav-section" style={{ marginTop: 'auto', padding: '16px' }}>
              <div className="nav-section-title">テーマ</div>
              <select
                value={theme}
                onChange={handleThemeChange}
                style={{
                  width: '100%',
                  padding: '6px 8px',
                  border: '1px solid var(--border)',
                  borderRadius: 'var(--radius)',
                  background: 'var(--bg-input)',
                  color: 'var(--text)',
                  fontSize: '13px',
                }}
              >
                <option value="default">Default</option>
                <option value="supabase">Supabase Dark</option>
                <option value="linear">Linear Dark</option>
              </select>
            </div>
          </nav>
        </aside>
        <main className="main">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
