/**
 * データ管理ページ
 * CSVエクスポート・インポート機能
 */

import { useState, useEffect, useRef } from 'react';
import { Link } from 'react-router-dom';
import { fieldApi, planApi, pesticideRecordApi, cropApi, rotationApi, constraintApi } from '../lib/api';

export default function DataManagement() {
  // エクスポート関連
  const [exportYear, setExportYear] = useState(new Date().getFullYear());
  const [plans, setPlans] = useState([]);
  const [selectedPlanId, setSelectedPlanId] = useState('');
  const [fields, setFields] = useState([]);
  const [isExporting, setIsExporting] = useState(false);
  const [exportMessage, setExportMessage] = useState(null);

  // インポート関連
  const [importType, setImportType] = useState('fields');
  const [importFile, setImportFile] = useState(null);
  const [isImporting, setIsImporting] = useState(false);
  const [importResult, setImportResult] = useState(null);
  const fileInputRef = useRef(null);

  // 輪作計画インポート用
  const [rotationPlanName, setRotationPlanName] = useState('');

  // ユーザー作物（バリデーション用）
  const [userCrops, setUserCrops] = useState([]);

  // 制約設定（連作間隔チェック用）
  const [constraints, setConstraints] = useState([]);

  const years = Array.from({ length: 5 }, (_, i) => new Date().getFullYear() - 2 + i);

  useEffect(() => {
    loadPlans();
    loadFields();
    loadUserCrops();
    loadConstraints();
  }, []);

  const loadPlans = async () => {
    try {
      const data = await planApi.list();
      setPlans(data);
    } catch (err) {
      console.error('Failed to load plans:', err);
    }
  };

  const loadFields = async () => {
    try {
      const data = await fieldApi.list();
      setFields(data);
    } catch (err) {
      console.error('Failed to load fields:', err);
    }
  };

  const loadUserCrops = async () => {
    try {
      const data = await cropApi.listUserCrops();
      setUserCrops(data);
    } catch (err) {
      console.error('Failed to load user crops:', err);
    }
  };

  const loadConstraints = async () => {
    try {
      const data = await constraintApi.get();
      setConstraints(data.constraints || []);
    } catch (err) {
      console.error('Failed to load constraints:', err);
    }
  };

  // =============================================================================
  // エクスポート機能
  // =============================================================================

  const handleExportFields = () => {
    window.open(fieldApi.exportCsv(), '_blank');
    setExportMessage({ type: 'success', text: 'ほ場データのダウンロードを開始しました' });
  };

  const handleExportRecords = () => {
    window.open(pesticideRecordApi.exportCsv(exportYear), '_blank');
    setExportMessage({ type: 'success', text: `${exportYear}年の防除記録のダウンロードを開始しました` });
  };

  const handleExportPlan = () => {
    if (!selectedPlanId) {
      setExportMessage({ type: 'error', text: '計画を選択してください' });
      return;
    }
    window.open(planApi.exportCsv(selectedPlanId), '_blank');
    setExportMessage({ type: 'success', text: '輪作計画のダウンロードを開始しました' });
  };

  const handleExportHistory = async () => {
    if (fields.length === 0) {
      setExportMessage({ type: 'error', text: 'ほ場が登録されていません' });
      return;
    }

    setIsExporting(true);
    setExportMessage(null);

    try {
      // 全フィールドの履歴を取得
      const allHistory = [];
      for (const field of fields) {
        const history = await fieldApi.getHistory(field.id);
        for (const h of history) {
          allHistory.push({
            field_code: field.field_code,
            field_name: field.field_name || '',
            year: h.year,
            crop: h.crop,
          });
        }
      }

      if (allHistory.length === 0) {
        setExportMessage({ type: 'error', text: '作付履歴がありません' });
        setIsExporting(false);
        return;
      }

      // CSV生成
      const headers = ['ほ場ID', 'ほ場名', '年', '作物'];
      const rows = allHistory.map(h => [h.field_code, h.field_name, h.year, h.crop]);
      const csvContent = [headers, ...rows]
        .map(row => row.map(cell => `"${String(cell).replace(/"/g, '""')}"`).join(','))
        .join('\n');

      // BOM付きUTF-8でダウンロード
      const bom = '\uFEFF';
      const blob = new Blob([bom + csvContent], { type: 'text/csv;charset=utf-8' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `crop_history_${new Date().toISOString().slice(0, 10)}.csv`;
      a.click();
      URL.revokeObjectURL(url);

      setExportMessage({ type: 'success', text: `${allHistory.length}件の作付履歴をエクスポートしました` });
    } catch (err) {
      setExportMessage({ type: 'error', text: 'エクスポートに失敗しました' });
    } finally {
      setIsExporting(false);
    }
  };

  // =============================================================================
  // インポート機能
  // =============================================================================

  const handleFileSelect = (e) => {
    const file = e.target.files?.[0];
    if (file) {
      setImportFile(file);
      setImportResult(null);
    }
  };

  const parseCSV = (text) => {
    const lines = text.split(/\r?\n/).filter(line => line.trim());
    if (lines.length === 0) return { headers: [], rows: [] };

    const parseRow = (line) => {
      const result = [];
      let current = '';
      let inQuotes = false;

      for (let i = 0; i < line.length; i++) {
        const char = line[i];
        if (char === '"') {
          if (inQuotes && line[i + 1] === '"') {
            current += '"';
            i++;
          } else {
            inQuotes = !inQuotes;
          }
        } else if (char === ',' && !inQuotes) {
          result.push(current.trim());
          current = '';
        } else {
          current += char;
        }
      }
      result.push(current.trim());
      return result;
    };

    const headers = parseRow(lines[0]);
    const rows = lines.slice(1).map(parseRow);

    return { headers, rows };
  };

  const normalizeColumnName = (name) => {
    const map = {
      'ほ場ID': 'field_code',
      'field_id': 'field_code',
      'ほ場コード': 'field_code',
      'ほ場名': 'field_name',
      '名前': 'field_name',
      'name': 'field_name',
      '地区': 'district',
      '面積': 'area_ha',
      'area': 'area_ha',
      '面積(ha)': 'area_ha',
      '禁止': 'beet_forbidden',
      'beet_forbidden': 'beet_forbidden',
      '年': 'year',
      'year': 'year',
      '作物': 'crop',
      'crop': 'crop',
    };
    return map[name] || name;
  };

  const handleImport = async () => {
    if (!importFile) {
      setImportResult({ type: 'error', message: 'ファイルを選択してください', logs: [] });
      return;
    }

    setIsImporting(true);
    setImportResult(null);

    try {
      const text = await importFile.text();
      const { headers, rows } = parseCSV(text);

      if (rows.length === 0) {
        setImportResult({ type: 'error', message: 'データがありません', logs: [] });
        setIsImporting(false);
        return;
      }

      const normalizedHeaders = headers.map(normalizeColumnName);
      const logs = [];
      let successCount = 0;
      let errorCount = 0;

      if (importType === 'fields') {
        // ほ場インポート
        const fieldCodeIdx = normalizedHeaders.indexOf('field_code');
        if (fieldCodeIdx === -1) {
          setImportResult({ type: 'error', message: '「ほ場ID」カラムが見つかりません', logs: [] });
          setIsImporting(false);
          return;
        }

        const nameIdx = normalizedHeaders.indexOf('field_name');
        const districtIdx = normalizedHeaders.indexOf('district');
        const areaIdx = normalizedHeaders.indexOf('area_ha');
        const forbiddenIdx = normalizedHeaders.indexOf('beet_forbidden');

        for (const row of rows) {
          const fieldCode = row[fieldCodeIdx]?.trim();
          if (!fieldCode) continue;

          // 重複チェック
          const existing = fields.find(f => f.field_code === fieldCode);
          if (existing) {
            logs.push(`スキップ: ${fieldCode} (既存)`);
            errorCount++;
            continue;
          }

          let areaHa = parseFloat(row[areaIdx]) || 0;
          // 100以上ならアールと判断してヘクタールに変換
          if (areaHa > 10) areaHa = areaHa / 100;

          const forbidden = ['1', 'true', 'yes', 'Yes', 'TRUE'].includes(String(row[forbiddenIdx]));

          try {
            await fieldApi.create({
              field_code: fieldCode,
              field_name: nameIdx >= 0 ? row[nameIdx]?.trim() || fieldCode : fieldCode,
              district: districtIdx >= 0 ? row[districtIdx]?.trim() || '' : '',
              area_ha: areaHa,
              beet_forbidden: forbidden,
            });
            logs.push(`登録: ${fieldCode}`);
            successCount++;
          } catch (err) {
            logs.push(`エラー: ${fieldCode} - ${err.response?.data?.detail || err.message}`);
            errorCount++;
          }
        }

        // フィールド一覧を更新
        await loadFields();

        setImportResult({
          type: successCount > 0 ? 'success' : 'error',
          message: `インポート完了: ${successCount}件登録, ${errorCount}件スキップ/エラー`,
          logs,
        });

      } else if (importType === 'history') {
        // 作付履歴インポート
        const fieldCodeIdx = normalizedHeaders.indexOf('field_code');
        const yearIdx = normalizedHeaders.indexOf('year');
        const cropIdx = normalizedHeaders.indexOf('crop');

        if (fieldCodeIdx === -1 || yearIdx === -1 || cropIdx === -1) {
          setImportResult({
            type: 'error',
            message: '必須カラム（ほ場ID、年、作物）が見つかりません',
            logs: []
          });
          setIsImporting(false);
          return;
        }

        // ========================================================
        // 作物バリデーション: ユーザー作物設定との照合
        // ========================================================
        const userCropNames = new Set(userCrops.map(c => c.name || c.custom_name).filter(Boolean));
        const validationErrors = [];
        const unknownCrops = new Set();

        for (let i = 0; i < rows.length; i++) {
          const row = rows[i];
          const rowNum = i + 2; // ヘッダー行を考慮
          const crop = row[cropIdx]?.trim();

          // 空欄チェック
          if (!crop) {
            validationErrors.push(`行${rowNum}: 作物が空欄です`);
            continue;
          }

          // ユーザー作物に存在するかチェック
          if (userCropNames.size > 0 && !userCropNames.has(crop)) {
            unknownCrops.add(crop);
          }
        }

        // 未登録作物があればエラー
        if (unknownCrops.size > 0) {
          const unknownList = Array.from(unknownCrops);
          validationErrors.push(
            `以下の作物が「作物設定」に登録されていません:\n  ・${unknownList.join('\n  ・')}`
          );
        }

        // バリデーションエラーがあればインポート中断
        if (validationErrors.length > 0) {
          setImportResult({
            type: 'error',
            message: `バリデーションエラー: ${validationErrors.length}件の問題があります`,
            logs: validationErrors,
            showCropSettingsLink: unknownCrops.size > 0,
          });
          setIsImporting(false);
          return;
        }
        // ========================================================
        // 連作間隔チェック（警告のみ、インポートは継続）
        // ========================================================
        const rotationWarnings = [];

        // min_gap_years > 0 の作物を抽出（連作間隔が必要な作物）
        const rotationCrops = {};
        for (const c of constraints) {
          const gapYears = c.min_gap_years || 0;
          if (gapYears > 0 && c.crop) {
            rotationCrops[c.crop] = gapYears;
          }
        }

        // 連作間隔チェックが必要な作物がある場合
        if (Object.keys(rotationCrops).length > 0) {
          // インポートデータをほ場ごとにグループ化
          const importByField = {};
          for (const row of rows) {
            const fieldCode = row[fieldCodeIdx]?.trim();
            const yearStr = row[yearIdx]?.trim();
            const crop = row[cropIdx]?.trim();
            if (!fieldCode || !yearStr || !crop) continue;

            // 年度を数値に変換（R7→2025, 2025→2025）
            let year = parseInt(yearStr);
            if (isNaN(year) && yearStr.toUpperCase().startsWith('R')) {
              const reiwa = parseInt(yearStr.substring(1));
              if (!isNaN(reiwa)) year = 2018 + reiwa;
            }
            if (isNaN(year)) continue;

            if (!importByField[fieldCode]) {
              importByField[fieldCode] = [];
            }
            importByField[fieldCode].push({ year, crop });
          }

          // 各ほ場について連作チェック
          for (const fieldCode of Object.keys(importByField)) {
            const field = fields.find(f => f.field_code === fieldCode);
            if (!field) continue;

            // ほ場の過去履歴を取得
            let existingHistory = [];
            try {
              existingHistory = await fieldApi.getHistory(field.id);
            } catch (err) {
              console.error(`Failed to get history for ${fieldCode}:`, err);
            }

            // 過去履歴を年度→作物のマップに変換
            const historyByYear = {};
            for (const h of existingHistory) {
              historyByYear[h.year] = h.crop;
            }

            // インポートデータの連作チェック
            for (const { year, crop } of importByField[fieldCode]) {
              const gapYears = rotationCrops[crop];
              if (!gapYears) continue;

              // 過去N年間に同じ作物があるかチェック
              for (let i = 1; i <= gapYears; i++) {
                const checkYear = year - i;
                const pastCrop = historyByYear[checkYear];

                if (pastCrop === crop) {
                  rotationWarnings.push(
                    `⚠️ ${fieldCode} (${year}年): ${crop}は${checkYear}年にも作付されています（連作間隔${gapYears}年以上必要）`
                  );
                  break;
                }
              }
            }
          }
        }

        // ========================================================
        // バリデーション終了、インポート実行
        // ========================================================

        for (const row of rows) {
          const fieldCode = row[fieldCodeIdx]?.trim();
          const year = row[yearIdx]?.trim();
          const crop = row[cropIdx]?.trim();

          if (!fieldCode || !year || !crop) continue;

          // ほ場IDからフィールドを探す
          const field = fields.find(f => f.field_code === fieldCode);
          if (!field) {
            logs.push(`スキップ: ${fieldCode} (ほ場が見つかりません)`);
            errorCount++;
            continue;
          }

          try {
            await fieldApi.addHistory(field.id, year, crop);
            logs.push(`登録: ${fieldCode} / ${year} / ${crop}`);
            successCount++;
          } catch (err) {
            logs.push(`エラー: ${fieldCode} - ${err.response?.data?.detail || err.message}`);
            errorCount++;
          }
        }

        // 連作警告とログを結合
        const allLogs = [];
        if (rotationWarnings.length > 0) {
          allLogs.push('=== 連作間隔警告 ===');
          allLogs.push(...rotationWarnings);
          allLogs.push('');
          allLogs.push('=== インポートログ ===');
        }
        allLogs.push(...logs);

        const warningMsg = rotationWarnings.length > 0
          ? ` (⚠️ 連作警告${rotationWarnings.length}件)`
          : '';

        setImportResult({
          type: successCount > 0 ? (rotationWarnings.length > 0 ? 'warning' : 'success') : 'error',
          message: `インポート完了: ${successCount}件登録, ${errorCount}件スキップ/エラー${warningMsg}`,
          logs: allLogs,
          hasRotationWarnings: rotationWarnings.length > 0,
        });

      } else if (importType === 'rotation') {
        // 輪作計画インポート
        if (!rotationPlanName.trim()) {
          setImportResult({
            type: 'error',
            message: '計画名を入力してください',
            logs: [],
          });
          setIsImporting(false);
          return;
        }

        const fieldCodeIdx = normalizedHeaders.indexOf('field_code');
        const yearIdx = normalizedHeaders.indexOf('year');
        const cropIdx = normalizedHeaders.indexOf('crop');

        if (fieldCodeIdx === -1 || yearIdx === -1 || cropIdx === -1) {
          setImportResult({
            type: 'error',
            message: '必須カラム（ほ場ID、年、作物）が見つかりません',
            logs: [],
          });
          setIsImporting(false);
          return;
        }

        // CSVデータをオブジェクト配列に変換
        const csvData = rows.map((row) => ({
          field_code: row[fieldCodeIdx]?.trim() || '',
          year: row[yearIdx]?.trim() || '',
          crop: row[cropIdx]?.trim() || '',
        })).filter((r) => r.field_code && r.year && r.crop);

        if (csvData.length === 0) {
          setImportResult({
            type: 'error',
            message: '有効なデータがありません',
            logs: [],
          });
          setIsImporting(false);
          return;
        }

        // APIでインポート実行
        try {
          const result = await rotationApi.importCsv(rotationPlanName.trim(), csvData);

          if (result.success) {
            setImportResult({
              type: 'success',
              message: `計画「${rotationPlanName}」を登録しました（${result.import_count}行）`,
              logs: result.warnings || [],
            });
            setRotationPlanName('');
            // 計画一覧を更新
            await loadPlans();
          } else {
            setImportResult({
              type: 'error',
              message: `インポートエラー: ${result.error_count}件のエラー`,
              logs: result.errors || [],
              showCropSettingsLink: result.errors?.some((e) => e.includes('作物設定')),
            });
          }
        } catch (err) {
          setImportResult({
            type: 'error',
            message: `インポートエラー: ${err.response?.data?.detail || err.message}`,
            logs: [],
          });
        }
      }

      // ファイルをクリア
      setImportFile(null);
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }

    } catch (err) {
      setImportResult({
        type: 'error',
        message: `ファイル読み込みエラー: ${err.message}`,
        logs: [],
      });
    } finally {
      setIsImporting(false);
    }
  };

  return (
    <div className="data-management-page">
      <div className="page-header">
        <h1>💾 データ管理</h1>
      </div>

      {/* エクスポートセクション */}
      <div className="section">
        <h2>📥 データエクスポート</h2>
        <p className="section-description">
          各種データをCSV形式でダウンロードできます。
        </p>

        {exportMessage && (
          <div className={`message ${exportMessage.type}`}>
            {exportMessage.text}
          </div>
        )}

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
            <div className="export-icon">📅</div>
            <h3>作付履歴</h3>
            <p>全ほ場の作付履歴をエクスポート</p>
            <button
              onClick={handleExportHistory}
              className="btn-primary"
              disabled={isExporting}
            >
              {isExporting ? 'エクスポート中...' : 'ダウンロード'}
            </button>
          </div>

          <div className="export-card">
            <div className="export-icon">🧪</div>
            <h3>防除記録</h3>
            <p>指定年度の防除記録をエクスポート</p>
            <div className="export-options">
              <select
                value={exportYear}
                onChange={(e) => setExportYear(parseInt(e.target.value))}
              >
                {years.map(y => (
                  <option key={y} value={y}>{y}年</option>
                ))}
              </select>
              <button onClick={handleExportRecords} className="btn-primary">
                ダウンロード
              </button>
            </div>
          </div>

          <div className="export-card">
            <div className="export-icon">📋</div>
            <h3>輪作計画</h3>
            <p>保存済みの計画をエクスポート</p>
            <div className="export-options">
              <select
                value={selectedPlanId}
                onChange={(e) => setSelectedPlanId(e.target.value)}
              >
                <option value="">-- 計画を選択 --</option>
                {plans.map(p => (
                  <option key={p.id} value={p.id}>{p.name}</option>
                ))}
              </select>
              <button
                onClick={handleExportPlan}
                className="btn-primary"
                disabled={!selectedPlanId}
              >
                ダウンロード
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* インポートセクション */}
      <div className="section">
        <h2>📤 データインポート</h2>
        <p className="section-description">
          CSVファイルからデータをインポートできます。
        </p>

        <div className="import-form">
          <div className="form-group">
            <label>インポート種類</label>
            <select
              value={importType}
              onChange={(e) => {
                setImportType(e.target.value);
                setImportResult(null);
              }}
            >
              <option value="fields">ほ場データ</option>
              <option value="history">作付履歴</option>
              <option value="rotation">輪作計画</option>
            </select>
          </div>

          {importType === 'rotation' && (
            <div className="form-group">
              <label>計画名 <span style={{ color: 'red' }}>*</span></label>
              <input
                type="text"
                value={rotationPlanName}
                onChange={(e) => setRotationPlanName(e.target.value)}
                placeholder="例: 2026年度輪作計画"
                style={{ width: '100%', padding: '8px', marginTop: '4px' }}
              />
            </div>
          )}

          <div className="import-instructions">
            {importType === 'fields' ? (
              <>
                <h4>ほ場データCSVフォーマット</h4>
                <p>以下のカラムを含むCSVファイルを用意してください：</p>
                <ul>
                  <li><strong>ほ場ID</strong>（必須）: ほ場のコード</li>
                  <li><strong>ほ場名</strong>: 表示名</li>
                  <li><strong>地区</strong>: 地区名</li>
                  <li><strong>面積</strong>: 面積（ha。10以上の場合はアールと判断）</li>
                  <li><strong>禁止</strong>: てんさい・馬鈴薯禁止フラグ（1/true/yes）</li>
                </ul>
              </>
            ) : importType === 'history' ? (
              <>
                <h4>作付履歴CSVフォーマット</h4>
                <p>以下のカラムを含むCSVファイルを用意してください：</p>
                <ul>
                  <li><strong>ほ場ID</strong>（必須）: 既存ほ場のコード</li>
                  <li><strong>年</strong>（必須）: 年度（例: 2024, R6）</li>
                  <li><strong>作物</strong>（必須）: 作物名</li>
                </ul>
              </>
            ) : (
              <>
                <h4>輪作計画CSVフォーマット</h4>
                <p>以下のカラムを含むCSVファイルを用意してください：</p>
                <ul>
                  <li><strong>ほ場ID</strong>（必須）: 既存ほ場のコード（field_code, field_id, ほ場ID）</li>
                  <li><strong>年</strong>（必須）: 西暦年度（例: 2026）</li>
                  <li><strong>作物</strong>（必須）: 作物名（作物設定に登録済みの作物）</li>
                </ul>
                <p style={{ color: '#666', fontSize: '0.9em', marginTop: '10px' }}>
                  ※ 作物は「作物設定」に登録された作物のみインポート可能です
                </p>
              </>
            )}
          </div>

          <div className="form-group">
            <label>CSVファイル</label>
            <input
              ref={fileInputRef}
              type="file"
              accept=".csv"
              onChange={handleFileSelect}
            />
            {importFile && (
              <span className="file-name">{importFile.name}</span>
            )}
          </div>

          <button
            onClick={handleImport}
            className="btn-primary"
            disabled={!importFile || isImporting || (importType === 'rotation' && !rotationPlanName.trim())}
          >
            {isImporting ? 'インポート中...' : 'インポート実行'}
          </button>
        </div>

        {importResult && (
          <div className={`import-result ${importResult.type}`}>
            <div className="result-message">{importResult.message}</div>
            {importResult.logs.length > 0 && (
              <div className="result-logs">
                <h4>詳細ログ</h4>
                <pre>{importResult.logs.join('\n')}</pre>
              </div>
            )}
            {importResult.showCropSettingsLink && (
              <div className="crop-settings-link">
                <p>
                  未登録の作物は <Link to="/crop-settings">作物設定ページ</Link> で登録してからインポートしてください。
                </p>
              </div>
            )}
            {importResult.hasRotationWarnings && (
              <div className="rotation-warning-info" style={{
                marginTop: '12px',
                padding: '12px',
                background: '#fff3cd',
                border: '1px solid #ffc107',
                borderRadius: '6px',
              }}>
                <strong>⚠️ 連作間隔について</strong>
                <p style={{ margin: '8px 0 0', fontSize: '0.9em', color: '#856404' }}>
                  連作間隔の制約を超えた作付が検出されました。
                  てんさい・馬鈴薯などは連作障害を避けるため、一定年数の間隔が推奨されています。
                  データはインポートされましたが、輪作計画を確認してください。
                </p>
              </div>
            )}
          </div>
        )}
      </div>

      {/* 注意事項 */}
      <div className="section info-section">
        <h2>ℹ️ 注意事項</h2>
        <ul>
          <li>CSVファイルはUTF-8エンコードで保存してください</li>
          <li>Excelで作成したCSVは「CSV UTF-8」形式で保存してください</li>
          <li>既存のほ場IDと重複する場合はスキップされます</li>
          <li>インポート前にバックアップ（エクスポート）を取ることを推奨します</li>
        </ul>
      </div>
    </div>
  );
}
