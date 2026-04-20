/**
 * レイアウトコンポーネント
 */

import { useState } from 'react';
import { Link, Outlet, useNavigate, useLocation } from 'react-router-dom';
import { useAuthStore } from '../store/authStore';

// --- Theme Constants ---
const CUSTOMIZABLE_VARS = [
  { key: '--primary', label: 'メイン' },
  { key: '--bg', label: '背景' },
  { key: '--card', label: 'カード' },
  { key: '--text', label: 'テキスト' },
  { key: '--text-muted', label: '薄文字' },
  { key: '--border', label: 'ボーダー' },
  { key: '--success', label: '成功' },
  { key: '--warning', label: '警告' },
  { key: '--danger', label: 'エラー' },
];

const BASE_THEME_IDS = ['default', 'supabase', 'linear'];

// --- Theme Helpers ---
function rgbToHex(color) {
  if (!color) return '#000000';
  if (color.startsWith('#')) return color.length >= 7 ? color.slice(0, 7) : color;
  const m = color.match(/(\d+)/g);
  if (!m || m.length < 3) return '#000000';
  return '#' + m.slice(0, 3).map(c => Number(c).toString(16).padStart(2, '0')).join('');
}

function getComputedVar(key) {
  return rgbToHex(getComputedStyle(document.documentElement).getPropertyValue(key).trim());
}

function loadCustomThemes() {
  try { return JSON.parse(localStorage.getItem('customThemes') || '[]'); }
  catch { return []; }
}

function applyBase(id) {
  if (id === 'default') document.documentElement.removeAttribute('data-theme');
  else document.documentElement.setAttribute('data-theme', id);
}

function applyOverrides(vars) {
  Object.entries(vars).forEach(([k, v]) => document.documentElement.style.setProperty(k, v));
}

function clearOverrides() {
  CUSTOMIZABLE_VARS.forEach(({ key }) => document.documentElement.style.removeProperty(key));
}

export default function Layout() {
  const { user, logout } = useAuthStore();
  const navigate = useNavigate();
  const location = useLocation();
  const [menuOpen, setMenuOpen] = useState(false);
  const [customThemes, setCustomThemes] = useState(loadCustomThemes);
  const [customizing, setCustomizing] = useState(false);
  const [editVars, setEditVars] = useState({});
  const [saveName, setSaveName] = useState('');

  const [theme, setTheme] = useState(() => {
    const saved = localStorage.getItem('theme') || 'default';
    if (BASE_THEME_IDS.includes(saved)) {
      if (saved !== 'default') applyBase(saved);
    } else {
      const custom = loadCustomThemes().find(t => t.id === saved);
      if (custom) { applyBase(custom.base); applyOverrides(custom.vars); }
      else return 'default';
    }
    return saved;
  });

  const handleThemeChange = (e) => {
    const val = e.target.value;
    setTheme(val);
    clearOverrides();
    setCustomizing(false);
    if (BASE_THEME_IDS.includes(val)) {
      applyBase(val);
      if (val === 'default') localStorage.removeItem('theme');
      else localStorage.setItem('theme', val);
    } else {
      const custom = customThemes.find(t => t.id === val);
      if (custom) {
        applyBase(custom.base);
        applyOverrides(custom.vars);
        localStorage.setItem('theme', val);
      }
    }
  };

  const handleStartCustomize = () => {
    const vars = {};
    CUSTOMIZABLE_VARS.forEach(({ key }) => { vars[key] = getComputedVar(key); });
    setEditVars(vars);
    setSaveName('');
    setCustomizing(true);
  };

  const handleColorChange = (key, value) => {
    setEditVars(prev => ({ ...prev, [key]: value }));
    document.documentElement.style.setProperty(key, value);
  };

  const handleSaveCustomTheme = () => {
    if (!saveName.trim()) return;
    let base = theme;
    if (!BASE_THEME_IDS.includes(base)) {
      const existing = customThemes.find(t => t.id === base);
      base = existing?.base || 'default';
    }
    clearOverrides();
    const baseVars = {};
    CUSTOMIZABLE_VARS.forEach(({ key }) => { baseVars[key] = getComputedVar(key); });
    const diffVars = {};
    Object.entries(editVars).forEach(([key, val]) => {
      if (val !== baseVars[key]) diffVars[key] = val;
    });
    applyOverrides(editVars);

    const newTheme = { id: 'custom_' + Date.now(), name: saveName.trim(), base, vars: diffVars };
    const updated = [...customThemes, newTheme];
    setCustomThemes(updated);
    localStorage.setItem('customThemes', JSON.stringify(updated));
    setTheme(newTheme.id);
    localStorage.setItem('theme', newTheme.id);
    setCustomizing(false);
  };

  const handleDeleteCustomTheme = () => {
    if (BASE_THEME_IDS.includes(theme)) return;
    const updated = customThemes.filter(t => t.id !== theme);
    setCustomThemes(updated);
    localStorage.setItem('customThemes', JSON.stringify(updated));
    clearOverrides();
    applyBase('default');
    setTheme('default');
    localStorage.removeItem('theme');
  };

  const handleCancelCustomize = () => {
    setCustomizing(false);
    clearOverrides();
    if (BASE_THEME_IDS.includes(theme)) {
      applyBase(theme);
    } else {
      const custom = customThemes.find(t => t.id === theme);
      if (custom) { applyBase(custom.base); applyOverrides(custom.vars); }
    }
  };

  const handleLogout = () => { logout(); navigate('/login'); };
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
                className="theme-select"
              >
                <option value="default">Default</option>
                <option value="supabase">Supabase Dark</option>
                <option value="linear">Linear Dark</option>
                {customThemes.length > 0 && <option disabled>───</option>}
                {customThemes.map(t => (
                  <option key={t.id} value={t.id}>★ {t.name}</option>
                ))}
              </select>
              <div className="theme-actions">
                {!customizing && (
                  <button className="btn-customize" onClick={handleStartCustomize}>
                    カスタマイズ
                  </button>
                )}
                {!BASE_THEME_IDS.includes(theme) && !customizing && (
                  <button className="btn-delete-theme" onClick={handleDeleteCustomTheme}>
                    削除
                  </button>
                )}
              </div>
              {customizing && (
                <div className="theme-customizer">
                  {CUSTOMIZABLE_VARS.map(({ key, label }) => (
                    <div key={key} className="customizer-row">
                      <label>{label}</label>
                      <input
                        type="color"
                        value={editVars[key] || '#000000'}
                        onChange={e => handleColorChange(key, e.target.value)}
                      />
                    </div>
                  ))}
                  <input
                    className="customizer-name"
                    type="text"
                    placeholder="テーマ名を入力"
                    value={saveName}
                    onChange={e => setSaveName(e.target.value)}
                  />
                  <div className="customizer-actions">
                    <button
                      className="btn-save-theme"
                      onClick={handleSaveCustomTheme}
                      disabled={!saveName.trim()}
                    >
                      保存
                    </button>
                    <button className="btn-cancel-theme" onClick={handleCancelCustomize}>
                      戻す
                    </button>
                  </div>
                </div>
              )}
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
