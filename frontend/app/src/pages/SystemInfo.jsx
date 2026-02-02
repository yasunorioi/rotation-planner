/**
 * システム情報・管理機能ページ (管理者用)
 */

import { useEffect, useState, useRef } from 'react';
import { adminApi } from '../lib/api';
import { useAuthStore } from '../store/authStore';

export default function SystemInfo() {
  const { user } = useAuthStore();
  const [activeTab, setActiveTab] = useState('system');
  const [systemInfo, setSystemInfo] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);

  // デバッグモード
  const [debugMode, setDebugMode] = useState(false);
  const [debugMessage, setDebugMessage] = useState('');

  // 筆ポリゴン
  const [fudeFiles, setFudeFiles] = useState([]);
  const [fudeUploading, setFudeUploading] = useState(false);
  const [fudeMessage, setFudeMessage] = useState(null);
  const fudeFileInputRef = useRef(null);

  // FAMIC
  const [famicStatus, setFamicStatus] = useState(null);
  const [famicUpdating, setFamicUpdating] = useState(false);
  const [famicMessage, setFamicMessage] = useState(null);

  useEffect(() => {
    if (user?.role === 'admin') {
      loadSystemInfo();
      loadDebugMode();
      loadFudeFiles();
      loadFamicStatus();
    }
  }, [user]);

  const loadSystemInfo = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await adminApi.getSystemInfo();
      setSystemInfo(data);
    } catch (err) {
      console.error('Failed to load system info:', err);
      setError('システム情報の取得に失敗しました');
    } finally {
      setIsLoading(false);
    }
  };

  const handleDownloadBackup = async () => {
    try {
      const { blob, filename } = await adminApi.downloadBackup();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (err) {
      alert('バックアップのダウンロードに失敗しました');
    }
  };

  // デバッグモード
  const loadDebugMode = async () => {
    try {
      const data = await adminApi.getDebugMode();
      setDebugMode(data.debug_mode);
    } catch (err) {
      console.error('Failed to load debug mode:', err);
    }
  };

  const handleDebugModeChange = async (enabled) => {
    try {
      const data = await adminApi.setDebugMode(enabled);
      setDebugMode(data.debug_mode);
      setDebugMessage(data.message);
      setTimeout(() => setDebugMessage(''), 3000);
    } catch (err) {
      setDebugMessage('設定の変更に失敗しました');
    }
  };

  // 筆ポリゴン
  const loadFudeFiles = async () => {
    try {
      const data = await adminApi.listFudePolygons();
      setFudeFiles(data.files || []);
    } catch (err) {
      console.error('Failed to load fude files:', err);
    }
  };

  const handleFudeUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setFudeUploading(true);
    setFudeMessage(null);
    try {
      const result = await adminApi.uploadFudePolygon(file);
      setFudeMessage({ type: 'success', text: result.message });
      loadFudeFiles();
    } catch (err) {
      setFudeMessage({ type: 'error', text: err.response?.data?.detail || 'アップロードに失敗しました' });
    } finally {
      setFudeUploading(false);
      if (fudeFileInputRef.current) {
        fudeFileInputRef.current.value = '';
      }
    }
  };

  const handleFudeDelete = async (filename) => {
    if (!window.confirm(`"${filename}" を削除しますか？`)) return;

    try {
      await adminApi.deleteFudePolygon(filename);
      setFudeMessage({ type: 'success', text: `"${filename}" を削除しました` });
      loadFudeFiles();
    } catch (err) {
      setFudeMessage({ type: 'error', text: '削除に失敗しました' });
    }
  };

  // FAMIC
  const loadFamicStatus = async () => {
    try {
      const data = await adminApi.getFamicStatus();
      setFamicStatus(data);
    } catch (err) {
      console.error('Failed to load FAMIC status:', err);
    }
  };

  const handleFamicUpdate = async () => {
    setFamicUpdating(true);
    setFamicMessage(null);
    try {
      const result = await adminApi.updateFamic();
      if (result.success) {
        setFamicMessage({ type: 'success', text: `更新完了: 登録農薬 ${result.basic_count.toLocaleString()}件, 適用基準 ${result.usage_count.toLocaleString()}件` });
        loadFamicStatus();
      } else {
        setFamicMessage({ type: 'error', text: result.message });
      }
    } catch (err) {
      setFamicMessage({ type: 'error', text: '更新に失敗しました' });
    } finally {
      setFamicUpdating(false);
    }
  };

  const handleFamicAutoUpdateChange = async (enabled) => {
    try {
      await adminApi.setFamicAutoUpdate(enabled);
      loadFamicStatus();
    } catch (err) {
      alert('設定の変更に失敗しました');
    }
  };

  if (user?.role !== 'admin') {
    return (
      <div className="system-info-page">
        <div className="access-denied">
          <h1>アクセス権限がありません</h1>
          <p>このページは管理者のみ閲覧できます。</p>
        </div>
      </div>
    );
  }

  return (
    <div className="system-info-page">
      <div className="page-header">
        <h1>システム管理</h1>
      </div>

      {/* タブナビゲーション */}
      <div className="tab-nav" style={{ display: 'flex', gap: '8px', marginBottom: '20px', borderBottom: '1px solid #ddd', paddingBottom: '10px' }}>
        <button
          className={`tab-btn ${activeTab === 'system' ? 'active' : ''}`}
          onClick={() => setActiveTab('system')}
          style={{ padding: '8px 16px', border: activeTab === 'system' ? '1px solid #007bff' : '1px solid #ddd', background: activeTab === 'system' ? '#007bff' : 'white', color: activeTab === 'system' ? 'white' : '#333', borderRadius: '4px', cursor: 'pointer' }}
        >
          システム情報
        </button>
        <button
          className={`tab-btn ${activeTab === 'debug' ? 'active' : ''}`}
          onClick={() => setActiveTab('debug')}
          style={{ padding: '8px 16px', border: activeTab === 'debug' ? '1px solid #007bff' : '1px solid #ddd', background: activeTab === 'debug' ? '#007bff' : 'white', color: activeTab === 'debug' ? 'white' : '#333', borderRadius: '4px', cursor: 'pointer' }}
        >
          デバッグ設定
        </button>
        <button
          className={`tab-btn ${activeTab === 'fude' ? 'active' : ''}`}
          onClick={() => setActiveTab('fude')}
          style={{ padding: '8px 16px', border: activeTab === 'fude' ? '1px solid #007bff' : '1px solid #ddd', background: activeTab === 'fude' ? '#007bff' : 'white', color: activeTab === 'fude' ? 'white' : '#333', borderRadius: '4px', cursor: 'pointer' }}
        >
          筆ポリゴン
        </button>
        <button
          className={`tab-btn ${activeTab === 'famic' ? 'active' : ''}`}
          onClick={() => setActiveTab('famic')}
          style={{ padding: '8px 16px', border: activeTab === 'famic' ? '1px solid #007bff' : '1px solid #ddd', background: activeTab === 'famic' ? '#007bff' : 'white', color: activeTab === 'famic' ? 'white' : '#333', borderRadius: '4px', cursor: 'pointer' }}
        >
          農薬情報(FAMIC)
        </button>
      </div>

      {/* システム情報タブ */}
      {activeTab === 'system' && (
        <div className="tab-content">
          <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: '10px' }}>
            <button onClick={loadSystemInfo} className="btn-secondary" disabled={isLoading}>
              更新
            </button>
          </div>

          {error && <div className="error-message">{error}</div>}

          {isLoading ? (
            <p>読み込み中...</p>
          ) : systemInfo ? (
            <div className="system-info-grid">
              <div className="info-card">
                <h3>アプリケーション</h3>
                <dl>
                  <dt>バージョン</dt>
                  <dd>{systemInfo.app_version}</dd>
                </dl>
              </div>

              <div className="info-card">
                <h3>環境</h3>
                <dl>
                  {Object.entries(systemInfo.environment).map(([key, value]) => (
                    <div key={key}>
                      <dt>{key}</dt>
                      <dd>{value}</dd>
                    </div>
                  ))}
                </dl>
              </div>

              <div className="info-card">
                <h3>データベース</h3>
                <dl>
                  <dt>ファイルサイズ</dt>
                  <dd>{systemInfo.db_size_kb.toFixed(1)} KB</dd>
                  <dt>最終更新</dt>
                  <dd>{systemInfo.db_last_modified || '-'}</dd>
                  <dt>ユーザー数</dt>
                  <dd>{systemInfo.user_count}</dd>
                </dl>
                <button onClick={handleDownloadBackup} className="btn-primary btn-small">
                  バックアップをダウンロード
                </button>
              </div>

              <div className="info-card">
                <h3>バックアップ</h3>
                <dl>
                  <dt>最終バックアップ</dt>
                  <dd>{systemInfo.last_backup || '未実行'}</dd>
                </dl>
              </div>

              <div className="info-card wide">
                <h3>テーブル別レコード数</h3>
                {systemInfo.tables.length > 0 ? (
                  <table className="data-table compact">
                    <thead>
                      <tr>
                        <th>テーブル名</th>
                        <th>レコード数</th>
                      </tr>
                    </thead>
                    <tbody>
                      {systemInfo.tables.map((table) => (
                        <tr key={table.name}>
                          <td>{table.name}</td>
                          <td className="number">{table.count.toLocaleString()}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                ) : (
                  <p>テーブル情報がありません</p>
                )}
              </div>
            </div>
          ) : null}
        </div>
      )}

      {/* デバッグ設定タブ */}
      {activeTab === 'debug' && (
        <div className="tab-content">
          <div className="section">
            <h2>デバッグモード</h2>
            <p style={{ color: '#666', marginBottom: '15px' }}>
              有効時: ログイン画面にユーザー切り替えラジオボタンが表示されます
            </p>

            <label style={{ display: 'flex', alignItems: 'center', gap: '10px', cursor: 'pointer' }}>
              <input
                type="checkbox"
                checked={debugMode}
                onChange={(e) => handleDebugModeChange(e.target.checked)}
                style={{ width: '20px', height: '20px' }}
              />
              <span>デバッグモードを有効にする</span>
            </label>

            {debugMessage && (
              <div className="message success" style={{ marginTop: '10px' }}>
                {debugMessage}
              </div>
            )}

            <div style={{ marginTop: '20px', padding: '15px', background: '#fff3cd', borderRadius: '4px' }}>
              <h4 style={{ margin: '0 0 10px 0' }}>セキュリティに関する注意</h4>
              <ul style={{ margin: 0, paddingLeft: '20px' }}>
                <li>本番環境ではデバッグモードをOFFにしてください</li>
                <li>adminのパスワードを初期値から変更してください</li>
                <li>テストユーザーは削除してください</li>
              </ul>
            </div>
          </div>
        </div>
      )}

      {/* 筆ポリゴンタブ */}
      {activeTab === 'fude' && (
        <div className="tab-content">
          <div className="section">
            <h2>筆ポリゴン管理</h2>
            <p style={{ color: '#666', marginBottom: '15px' }}>
              農水省の筆ポリゴン公開サイトからダウンロードしたGeoJSONファイルをアップロードできます。
              <br />
              <a href="https://open.fude.maff.go.jp/" target="_blank" rel="noopener noreferrer">
                筆ポリゴン公開サイト
              </a>
            </p>

            <div style={{ marginBottom: '20px' }}>
              <input
                ref={fudeFileInputRef}
                type="file"
                accept=".geojson,.json"
                onChange={handleFudeUpload}
                disabled={fudeUploading}
              />
              {fudeUploading && <span style={{ marginLeft: '10px' }}>アップロード中...</span>}
            </div>

            {fudeMessage && (
              <div className={`message ${fudeMessage.type}`} style={{ marginBottom: '15px' }}>
                {fudeMessage.text}
              </div>
            )}

            <h3>アップロード済みファイル</h3>
            {fudeFiles.length > 0 ? (
              <table className="data-table">
                <thead>
                  <tr>
                    <th>ファイル名</th>
                    <th>サイズ</th>
                    <th>筆数</th>
                    <th>更新日時</th>
                    <th>操作</th>
                  </tr>
                </thead>
                <tbody>
                  {fudeFiles.map((file) => (
                    <tr key={file.id}>
                      <td>{file.filename}</td>
                      <td>{file.size_kb} KB</td>
                      <td>{file.feature_count.toLocaleString()}</td>
                      <td>{file.updated_at}</td>
                      <td>
                        <button
                          onClick={() => handleFudeDelete(file.filename)}
                          className="btn-danger btn-small"
                        >
                          削除
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <p>アップロードされたファイルはありません</p>
            )}
          </div>
        </div>
      )}

      {/* FAMICタブ */}
      {activeTab === 'famic' && (
        <div className="tab-content">
          <div className="section">
            <h2>農薬登録情報（FAMIC）</h2>
            <p style={{ color: '#666', marginBottom: '15px' }}>
              <a href="https://www.acis.famic.go.jp/ddata/index.htm" target="_blank" rel="noopener noreferrer">
                農林水産消費安全技術センター（FAMIC）
              </a>
              の農薬登録情報をダウンロードしてDBに取り込みます。
            </p>

            {famicStatus && (
              <div className="info-card" style={{ marginBottom: '20px' }}>
                <h3>現在の状態</h3>
                <dl>
                  <dt>登録農薬数</dt>
                  <dd>{famicStatus.registry_count.toLocaleString()} 件</dd>
                  <dt>適用基準数</dt>
                  <dd>{famicStatus.usage_count.toLocaleString()} 件</dd>
                  <dt>最終更新</dt>
                  <dd>{famicStatus.last_update || '未実行'}</dd>
                  <dt>自動更新</dt>
                  <dd>{famicStatus.auto_update_enabled ? '有効' : '無効'}</dd>
                  {famicStatus.next_update && (
                    <>
                      <dt>次回更新予定</dt>
                      <dd>{famicStatus.next_update}</dd>
                    </>
                  )}
                </dl>
              </div>
            )}

            <div style={{ marginBottom: '20px' }}>
              <label style={{ display: 'flex', alignItems: 'center', gap: '10px', cursor: 'pointer' }}>
                <input
                  type="checkbox"
                  checked={famicStatus?.auto_update_enabled || false}
                  onChange={(e) => handleFamicAutoUpdateChange(e.target.checked)}
                  style={{ width: '20px', height: '20px' }}
                />
                <span>自動更新を有効にする（半年ごと）</span>
              </label>
            </div>

            <div>
              <button
                onClick={handleFamicUpdate}
                disabled={famicUpdating}
                className="btn-primary"
              >
                {famicUpdating ? '更新中...' : '今すぐ更新'}
              </button>
              <p style={{ color: '#666', fontSize: '0.9em', marginTop: '5px' }}>
                ※ 数分かかる場合があります
              </p>
            </div>

            {famicMessage && (
              <div className={`message ${famicMessage.type}`} style={{ marginTop: '15px' }}>
                {famicMessage.text}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
