/**
 * ユーザー管理ページ (管理者用)
 */

import { useEffect, useState } from 'react';
import { adminApi } from '../lib/api';
import { useAuthStore } from '../store/authStore';

export default function UserManagement() {
  const { user } = useAuthStore();
  const [users, setUsers] = useState([]);
  const [showForm, setShowForm] = useState(false);
  const [editingUsername, setEditingUsername] = useState(null);
  const [formData, setFormData] = useState({
    username: '',
    password: '',
    display_name: '',
    role: 'farmer',
  });
  const [isLoading, setIsLoading] = useState(true);
  const [isDownloading, setIsDownloading] = useState(false);

  useEffect(() => {
    if (user?.role === 'admin') {
      loadUsers();
    }
  }, [user]);

  const loadUsers = async () => {
    setIsLoading(true);
    try {
      const data = await adminApi.listUsers();
      setUsers(data);
    } catch (err) {
      console.error('Failed to load users:', err);
    } finally {
      setIsLoading(false);
    }
  };

  const resetForm = () => {
    setFormData({
      username: '',
      password: '',
      display_name: '',
      role: 'farmer',
    });
    setEditingUsername(null);
    setShowForm(false);
  };

  const handleEdit = (u) => {
    setFormData({
      username: u.username,
      password: '',
      display_name: u.display_name || '',
      role: u.role,
    });
    setEditingUsername(u.username);
    setShowForm(true);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      if (editingUsername) {
        const updateData = {
          display_name: formData.display_name,
          role: formData.role,
        };
        if (formData.password) {
          updateData.password = formData.password;
        }
        await adminApi.updateUser(editingUsername, updateData);
      } else {
        if (!formData.password) {
          alert('パスワードを入力してください');
          return;
        }
        await adminApi.createUser(formData);
      }
      resetForm();
      loadUsers();
    } catch (err) {
      alert(editingUsername ? '更新に失敗しました' : '作成に失敗しました');
    }
  };

  const handleDelete = async (username) => {
    if (username === user?.username) {
      alert('自分自身は削除できません');
      return;
    }
    if (confirm(`ユーザー "${username}" を削除しますか？\n関連するデータも全て削除されます。`)) {
      try {
        await adminApi.deleteUser(username);
        loadUsers();
      } catch (err) {
        alert('削除に失敗しました');
      }
    }
  };

  const handleResetPassword = async (username) => {
    const newPassword = prompt(`ユーザー "${username}" の新しいパスワードを入力してください：`);
    if (!newPassword) return;
    if (newPassword.length < 4) {
      alert('パスワードは4文字以上で入力してください');
      return;
    }
    try {
      await adminApi.updateUser(username, { password: newPassword });
      alert(`ユーザー "${username}" のパスワードをリセットしました`);
    } catch (err) {
      alert('パスワードリセットに失敗しました');
    }
  };

  const handleDownloadBackup = async () => {
    setIsDownloading(true);
    try {
      const { blob, filename } = await adminApi.downloadBackup();
      // ダウンロードリンクを作成
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (err) {
      console.error('Backup download failed:', err);
      alert('バックアップのダウンロードに失敗しました');
    } finally {
      setIsDownloading(false);
    }
  };

  if (user?.role !== 'admin') {
    return (
      <div className="user-management-page">
        <div className="access-denied">
          <h1>⛔ アクセス権限がありません</h1>
          <p>このページは管理者のみ閲覧できます。</p>
        </div>
      </div>
    );
  }

  return (
    <div className="user-management-page">
      <div className="page-header">
        <h1>👥 ユーザー管理</h1>
        <div className="header-actions">
          <button
            onClick={handleDownloadBackup}
            disabled={isDownloading}
            className="btn-secondary"
          >
            {isDownloading ? '⏳ ダウンロード中...' : '💾 DBバックアップ'}
          </button>
          <button onClick={() => setShowForm(true)} className="btn-primary">
            + 新規ユーザー
          </button>
        </div>
      </div>

      {showForm && (
        <div className="modal-overlay">
          <div className="modal">
            <h2>{editingUsername ? 'ユーザー編集' : '新規ユーザー'}</h2>
            <form onSubmit={handleSubmit}>
              <div className="form-group">
                <label>ユーザー名 *</label>
                <input
                  type="text"
                  value={formData.username}
                  onChange={(e) => setFormData({ ...formData, username: e.target.value })}
                  disabled={!!editingUsername}
                  required
                />
              </div>
              <div className="form-group">
                <label>{editingUsername ? 'パスワード（変更する場合のみ）' : 'パスワード *'}</label>
                <input
                  type="password"
                  value={formData.password}
                  onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                  required={!editingUsername}
                />
              </div>
              <div className="form-group">
                <label>表示名</label>
                <input
                  type="text"
                  value={formData.display_name}
                  onChange={(e) => setFormData({ ...formData, display_name: e.target.value })}
                />
              </div>
              <div className="form-group">
                <label>役割 *</label>
                <select
                  value={formData.role}
                  onChange={(e) => setFormData({ ...formData, role: e.target.value })}
                  required
                >
                  <option value="farmer">農家</option>
                  <option value="ja_staff">JA職員</option>
                  <option value="admin">管理者</option>
                </select>
              </div>
              <div className="form-actions">
                <button type="button" onClick={resetForm} className="btn-secondary">
                  キャンセル
                </button>
                <button type="submit" className="btn-primary">
                  {editingUsername ? '更新' : '作成'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {isLoading ? (
        <p>読み込み中...</p>
      ) : users.length === 0 ? (
        <p className="empty-message">ユーザーが登録されていません</p>
      ) : (
        <table className="data-table">
          <thead>
            <tr>
              <th>ユーザー名</th>
              <th>表示名</th>
              <th>役割</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            {users.map((u) => (
              <tr key={u.username}>
                <td>{u.username}</td>
                <td>{u.display_name || '-'}</td>
                <td>
                  <span className={`role-badge ${u.role}`}>
                    {u.role === 'admin' ? '管理者' : u.role === 'ja_staff' ? 'JA職員' : '農家'}
                  </span>
                </td>
                <td>
                  <button onClick={() => handleEdit(u)} className="btn-icon" title="編集">
                    ✏️
                  </button>
                  {u.username !== user?.username && (
                    <>
                      <button
                        onClick={() => handleResetPassword(u.username)}
                        className="btn-icon"
                        title="パスワードリセット"
                      >
                        🔑
                      </button>
                      <button onClick={() => handleDelete(u.username)} className="btn-icon btn-danger" title="削除">
                        🗑️
                      </button>
                    </>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
