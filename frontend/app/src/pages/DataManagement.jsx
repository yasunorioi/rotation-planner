/**
 * データ管理ページ
 * CSVエクスポート機能
 */

import { fieldApi, planApi, pesticideRecordApi } from '../lib/api';

export default function DataManagement() {
  const handleExportFields = () => {
    window.open(fieldApi.exportCsv(), '_blank');
  };

  const handleExportRecords = () => {
    const year = new Date().getFullYear();
    window.open(pesticideRecordApi.exportCsv(year), '_blank');
  };

  return (
    <div className="data-management-page">
      <div className="page-header">
        <h1>💾 データ管理</h1>
      </div>

      <div className="export-section">
        <h2>📥 データエクスポート</h2>
        <p className="section-description">
          各種データをCSV形式でダウンロードできます。
        </p>

        <div className="export-cards">
          <div className="export-card">
            <div className="export-icon">🗺️</div>
            <h3>ほ場データ</h3>
            <p>登録済みのほ場情報をエクスポート</p>
            <button onClick={handleExportFields} className="btn-primary">
              ダウンロード
            </button>
          </div>

          <div className="export-card">
            <div className="export-icon">📋</div>
            <h3>防除記録</h3>
            <p>今年度の防除記録をエクスポート</p>
            <button onClick={handleExportRecords} className="btn-primary">
              ダウンロード
            </button>
          </div>
        </div>
      </div>

      <div className="info-section">
        <h2>ℹ️ データについて</h2>
        <ul>
          <li>輪作計画のエクスポートは「保存済み計画」ページから行えます</li>
          <li>CSVファイルはExcelなどの表計算ソフトで開けます</li>
          <li>エクスポートしたデータはバックアップとしてご利用いただけます</li>
        </ul>
      </div>
    </div>
  );
}
