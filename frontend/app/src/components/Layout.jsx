/**
 * レイアウトコンポーネント
 */

import { Link, Outlet, useNavigate } from 'react-router-dom';
import { useAuthStore } from '../store/authStore';

export default function Layout() {
  const { user, logout } = useAuthStore();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  return (
    <div className="layout">
      <header className="header">
        <div className="header-left">
          <Link to="/" className="logo">
            🌾 農業管理
          </Link>
          <nav className="nav">
            <Link to="/">ホーム</Link>
            <Link to="/fields">ほ場</Link>
            <Link to="/rotation">輪作計画</Link>
            <Link to="/plans">保存済み計画</Link>
          </nav>
        </div>
        <div className="header-right">
          <span className="user-name">{user?.display_name || user?.username}</span>
          <button onClick={handleLogout} className="btn-logout">
            ログアウト
          </button>
        </div>
      </header>
      <main className="main">
        <Outlet />
      </main>
    </div>
  );
}
