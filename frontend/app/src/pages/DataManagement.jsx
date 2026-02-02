/**
 * データ管理ページ
 * CSVエクスポート・インポート機能、バックアップ、在庫管理
 */

import { useState, useEffect, useRef } from 'react';
import { Link } from 'react-router-dom';
import { fieldApi, planApi, pesticideRecordApi, cropApi, rotationApi, constraintApi, inventoryApi, adminApi } from '../lib/api';
import { Spinner } from '../components/Loading';
import { EmptyState } from '../components/ErrorMessage';

export default function DataManagement() {
  // タブ管理
  const [activeTab, setActiveTab] = useState('csv');

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

  // 在庫管理関連
  const [inventoryList, setInventoryList] = useState([]);
  const [inventoryLoading, setInventoryLoading] = useState(false);
  const [inventorySearch, setInventorySearch] = useState('');
  const [inventorySortBy, setInventorySortBy] = useState('pesticide_name');
  const [inventorySortOrder, setInventorySortOrder] = useState('asc');
  const [showInventoryModal, setShowInventoryModal] = useState(false);
  const [editingInventory, setEditingInventory] = useState(null);
  const [inventoryForm, setInventoryForm] = useState({
    pesticide_name: '',
    quantity: '',
    unit: 'L',
    storage_location: '',
    expiry_date: '',
    notes: '',
  });
  const [inventoryImportFile, setInventoryImportFile] = useState(null);
  const [inventoryImportResult, setInventoryImportResult] = useState(null);
  const [isInventoryImporting, setIsInventoryImporting] = useState(false);
  const inventoryCsvInputRef = useRef(null);

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

  // =============================================================================
  // 在庫管理機能
  // =============================================================================

  const loadInventory = async () => {
    setInventoryLoading(true);
    try {
      const data = await inventoryApi.list({
        search: inventorySearch,
        sort_by: inventorySortBy,
        sort_order: inventorySortOrder,
      });
      setInventoryList(Array.isArray(data) ? data : data.items || []);
    } catch (err) {
      console.error('Failed to load inventory:', err);
      // APIが未実装の場合はモックデータを使用
      setInventoryList([]);
    } finally {
      setInventoryLoading(false);
    }
  };

  // タブが在庫に切り替わったら読み込み
  useEffect(() => {
    if (activeTab === 'inventory') {
      loadInventory();
    }
  }, [activeTab, inventorySearch, inventorySortBy, inventorySortOrder]);

  const resetInventoryForm = () => {
    setInventoryForm({
      pesticide_name: '',
      quantity: '',
      unit: 'L',
      storage_location: '',
      expiry_date: '',
      notes: '',
    });
    setEditingInventory(null);
    setShowInventoryModal(false);
  };

  const handleInventoryEdit = (item) => {
    setInventoryForm({
      pesticide_name: item.pesticide_name || '',
      quantity: item.quantity?.toString() || '',
      unit: item.unit || 'L',
      storage_location: item.storage_location || '',
      expiry_date: item.expiry_date || '',
      notes: item.notes || '',
    });
    setEditingInventory(item);
    setShowInventoryModal(true);
  };

  const handleInventorySubmit = async (e) => {
    e.preventDefault();
    const data = {
      ...inventoryForm,
      quantity: parseFloat(inventoryForm.quantity) || 0,
    };

    try {
      if (editingInventory) {
        await inventoryApi.update(editingInventory.id, data);
      } else {
        await inventoryApi.create(data);
      }
      resetInventoryForm();
      loadInventory();
    } catch (err) {
      alert(err.response?.data?.detail || (editingInventory ? '更新に失敗しました' : '登録に失敗しました'));
    }
  };

  const handleInventoryDelete = async (id) => {
    if (!confirm('この在庫を削除しますか？')) return;
    try {
      await inventoryApi.delete(id);
      loadInventory();
    } catch (err) {
      alert('削除に失敗しました');
    }
  };

  const handleInventorySort = (column) => {
    if (inventorySortBy === column) {
      setInventorySortOrder(inventorySortOrder === 'asc' ? 'desc' : 'asc');
    } else {
      setInventorySortBy(column);
      setInventorySortOrder('asc');
    }
  };

  const getSortIcon = (column) => {
    if (inventorySortBy !== column) return '↕️';
    return inventorySortOrder === 'asc' ? '↑' : '↓';
  };

  // 在庫CSVインポート
  const handleInventoryCsvSelect = (e) => {
    const file = e.target.files?.[0];
    if (file) {
      setInventoryImportFile(file);
      setInventoryImportResult(null);
    }
  };

  const handleInventoryCsvImport = async () => {
    if (!inventoryImportFile) {
      setInventoryImportResult({ type: 'error', message: 'ファイルを選択してください' });
      return;
    }

    setIsInventoryImporting(true);
    setInventoryImportResult(null);

    try {
      const result = await inventoryApi.importCsv(inventoryImportFile);
      setInventoryImportResult({
        type: 'success',
        message: `インポート完了: ${result.imported || 0}件登録, ${result.skipped || 0}件スキップ`,
      });
      setInventoryImportFile(null);
      if (inventoryCsvInputRef.current) {
        inventoryCsvInputRef.current.value = '';
      }
      loadInventory();
    } catch (err) {
      setInventoryImportResult({
        type: 'error',
        message: err.response?.data?.detail || 'インポートに失敗しました',
      });
    } finally {
      setIsInventoryImporting(false);
    }
  };

  // 在庫CSVエクスポート
  const handleInventoryCsvExport = () => {
    const token = localStorage.getItem('token');
    const url = inventoryApi.exportCsv();
    // 認証付きでダウンロード
    fetch(url, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((res) => {
        if (!res.ok) throw new Error('ダウンロード失敗');
        return res.blob();
      })
      .then((blob) => {
        const link = document.createElement('a');
        link.href = URL.createObjectURL(blob);
        link.download = `inventory_${new Date().toISOString().slice(0, 10).replace(/-/g, '')}.csv`;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(link.href);
      })
      .catch((err) => {
        alert(err.message || 'CSVエクスポートに失敗しました');
      });
  };

  // フィルタリングされた在庫リスト（クライアント側フィルタリング）
  const filteredInventory = inventoryList.filter((item) =>
    !inventorySearch || item.pesticide_name?.toLowerCase().includes(inventorySearch.toLowerCase())
  );

  return (
    <div className="data-management-page">
      <div className="page-header">
        <h1>💾 データ管理</h1>
      </div>

      {/* タブナビゲーション */}
      <div className="tabs">
        <button
          className={`tab ${activeTab === 'csv' ? 'active' : ''}`}
          onClick={() => setActiveTab('csv')}
        >
          📁 CSV操作
        </button>
        <button
          className={`tab ${activeTab === 'backup' ? 'active' : ''}`}
          onClick={() => setActiveTab('backup')}
        >
          💾 バックアップ
        </button>
        <button
          className={`tab ${activeTab === 'inventory' ? 'active' : ''}`}
          onClick={() => setActiveTab('inventory')}
        >
          📦 在庫管理
        </button>
      </div>

      {/* CSV操作タブ */}
      {activeTab === 'csv' && (
        <>
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
        </>
      )}

      {/* バックアップタブ */}
      {activeTab === 'backup' && (
        <div className="section">
          <h2>💾 データバックアップ</h2>
          <p className="section-description">
            データベース全体のバックアップをダウンロードできます。
          </p>
          <div className="backup-actions">
            <button
              onClick={async () => {
                try {
                  const { blob, filename } = await adminApi.downloadBackup();
                  const url = URL.createObjectURL(blob);
                  const a = document.createElement('a');
                  a.href = url;
                  a.download = filename;
                  a.click();
                  URL.revokeObjectURL(url);
                } catch (err) {
                  alert('バックアップのダウンロードに失敗しました');
                }
              }}
              className="btn-primary"
            >
              📥 バックアップをダウンロード
            </button>
          </div>
          <div className="backup-info" style={{ marginTop: '20px', padding: '15px', background: '#f5f5f5', borderRadius: '8px' }}>
            <h4>バックアップについて</h4>
            <ul>
              <li>バックアップファイルはSQLite形式（.db）です</li>
              <li>すべてのユーザーデータ、ほ場情報、計画、履歴が含まれます</li>
              <li>定期的にバックアップを取得することを推奨します</li>
            </ul>
          </div>
        </div>
      )}

      {/* 在庫管理タブ */}
      {activeTab === 'inventory' && (
        <>
          {/* 在庫編集モーダル */}
          {showInventoryModal && (
            <div className="modal-overlay">
              <div className="modal">
                <h2>{editingInventory ? '在庫編集' : '在庫追加'}</h2>
                <form onSubmit={handleInventorySubmit}>
                  <div className="form-group">
                    <label>農薬名 <span style={{ color: 'red' }}>*</span></label>
                    <input
                      type="text"
                      value={inventoryForm.pesticide_name}
                      onChange={(e) => setInventoryForm({ ...inventoryForm, pesticide_name: e.target.value })}
                      required
                    />
                  </div>
                  <div className="form-row" style={{ display: 'flex', gap: '15px' }}>
                    <div className="form-group" style={{ flex: 1 }}>
                      <label>在庫量 <span style={{ color: 'red' }}>*</span></label>
                      <input
                        type="number"
                        step="0.01"
                        min="0"
                        value={inventoryForm.quantity}
                        onChange={(e) => setInventoryForm({ ...inventoryForm, quantity: e.target.value })}
                        required
                      />
                    </div>
                    <div className="form-group" style={{ width: '100px' }}>
                      <label>単位</label>
                      <select
                        value={inventoryForm.unit}
                        onChange={(e) => setInventoryForm({ ...inventoryForm, unit: e.target.value })}
                      >
                        <option value="L">L</option>
                        <option value="mL">mL</option>
                        <option value="kg">kg</option>
                        <option value="g">g</option>
                        <option value="本">本</option>
                        <option value="袋">袋</option>
                      </select>
                    </div>
                  </div>
                  <div className="form-group">
                    <label>保管場所</label>
                    <input
                      type="text"
                      value={inventoryForm.storage_location}
                      onChange={(e) => setInventoryForm({ ...inventoryForm, storage_location: e.target.value })}
                      placeholder="例: 倉庫A棚1"
                    />
                  </div>
                  <div className="form-group">
                    <label>有効期限</label>
                    <input
                      type="date"
                      value={inventoryForm.expiry_date}
                      onChange={(e) => setInventoryForm({ ...inventoryForm, expiry_date: e.target.value })}
                    />
                  </div>
                  <div className="form-group">
                    <label>備考</label>
                    <textarea
                      value={inventoryForm.notes}
                      onChange={(e) => setInventoryForm({ ...inventoryForm, notes: e.target.value })}
                      rows={2}
                    />
                  </div>
                  <div className="form-actions">
                    {editingInventory && (
                      <button
                        type="button"
                        onClick={() => handleInventoryDelete(editingInventory.id)}
                        className="btn-danger"
                        style={{ marginRight: 'auto' }}
                      >
                        🗑️ 削除
                      </button>
                    )}
                    <button type="button" onClick={resetInventoryForm} className="btn-secondary">
                      キャンセル
                    </button>
                    <button type="submit" className="btn-primary">
                      {editingInventory ? '更新' : '追加'}
                    </button>
                  </div>
                </form>
              </div>
            </div>
          )}

          <div className="section">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '15px' }}>
              <h2>📦 在庫一覧</h2>
              <div style={{ display: 'flex', gap: '10px' }}>
                <button onClick={() => setShowInventoryModal(true)} className="btn-primary">
                  ＋ 新規追加
                </button>
              </div>
            </div>

            {/* 検索・フィルタ */}
            <div className="inventory-controls" style={{ marginBottom: '15px', display: 'flex', gap: '15px', alignItems: 'center' }}>
              <div style={{ flex: 1 }}>
                <input
                  type="text"
                  placeholder="🔍 農薬名で検索..."
                  value={inventorySearch}
                  onChange={(e) => setInventorySearch(e.target.value)}
                  style={{ width: '100%', padding: '8px 12px' }}
                />
              </div>
            </div>

            {/* 在庫テーブル */}
            {inventoryLoading ? (
              <Spinner text="在庫データを読み込み中..." />
            ) : filteredInventory.length === 0 ? (
              <EmptyState
                message={inventorySearch ? '検索条件に一致する在庫がありません' : '在庫が登録されていません'}
                icon="📦"
              />
            ) : (
              <div className="table-wrapper">
                <table className="data-table inventory-table">
                  <thead>
                    <tr>
                      <th onClick={() => handleInventorySort('pesticide_name')} style={{ cursor: 'pointer' }}>
                        農薬名 {getSortIcon('pesticide_name')}
                      </th>
                      <th onClick={() => handleInventorySort('quantity')} style={{ cursor: 'pointer' }}>
                        在庫量 {getSortIcon('quantity')}
                      </th>
                      <th>単位</th>
                      <th onClick={() => handleInventorySort('storage_location')} style={{ cursor: 'pointer' }}>
                        保管場所 {getSortIcon('storage_location')}
                      </th>
                      <th onClick={() => handleInventorySort('expiry_date')} style={{ cursor: 'pointer' }}>
                        有効期限 {getSortIcon('expiry_date')}
                      </th>
                      <th>操作</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredInventory.map((item) => {
                      const isExpiringSoon = item.expiry_date && new Date(item.expiry_date) < new Date(Date.now() + 30 * 24 * 60 * 60 * 1000);
                      const isExpired = item.expiry_date && new Date(item.expiry_date) < new Date();
                      return (
                        <tr key={item.id} className={isExpired ? 'expired' : isExpiringSoon ? 'expiring-soon' : ''}>
                          <td>{item.pesticide_name}</td>
                          <td style={{ textAlign: 'right' }}>{item.quantity}</td>
                          <td>{item.unit}</td>
                          <td>{item.storage_location || '-'}</td>
                          <td>
                            {item.expiry_date ? (
                              <span style={{ color: isExpired ? '#d32f2f' : isExpiringSoon ? '#f57c00' : 'inherit' }}>
                                {item.expiry_date}
                                {isExpired && ' ⚠️期限切れ'}
                                {!isExpired && isExpiringSoon && ' ⚠️'}
                              </span>
                            ) : '-'}
                          </td>
                          <td>
                            <button onClick={() => handleInventoryEdit(item)} className="btn-icon" title="編集">
                              ✏️
                            </button>
                            <button onClick={() => handleInventoryDelete(item.id)} className="btn-icon btn-danger" title="削除">
                              🗑️
                            </button>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {/* CSV操作セクション */}
          <div className="section">
            <h2>📁 在庫CSV操作</h2>
            <div className="inventory-csv-actions" style={{ display: 'flex', gap: '20px', flexWrap: 'wrap' }}>
              {/* エクスポート */}
              <div className="csv-card" style={{ flex: '1', minWidth: '250px', padding: '20px', background: '#f9f9f9', borderRadius: '8px' }}>
                <h3>📤 CSVエクスポート</h3>
                <p style={{ fontSize: '0.9em', color: '#666', marginBottom: '15px' }}>
                  現在の在庫データをCSV形式でダウンロード
                </p>
                <button onClick={handleInventoryCsvExport} className="btn-primary">
                  ダウンロード
                </button>
              </div>

              {/* インポート */}
              <div className="csv-card" style={{ flex: '1', minWidth: '250px', padding: '20px', background: '#f9f9f9', borderRadius: '8px' }}>
                <h3>📥 CSVインポート</h3>
                <p style={{ fontSize: '0.9em', color: '#666', marginBottom: '15px' }}>
                  CSVファイルから在庫データを一括登録
                </p>
                <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
                  <input
                    ref={inventoryCsvInputRef}
                    type="file"
                    accept=".csv"
                    onChange={handleInventoryCsvSelect}
                    style={{ flex: 1 }}
                  />
                  <button
                    onClick={handleInventoryCsvImport}
                    className="btn-primary"
                    disabled={!inventoryImportFile || isInventoryImporting}
                  >
                    {isInventoryImporting ? '処理中...' : 'インポート'}
                  </button>
                </div>
                {inventoryImportResult && (
                  <div className={`message ${inventoryImportResult.type}`} style={{ marginTop: '10px' }}>
                    {inventoryImportResult.message}
                  </div>
                )}
              </div>
            </div>

            <div className="csv-format-info" style={{ marginTop: '20px', padding: '15px', background: '#e3f2fd', borderRadius: '8px' }}>
              <h4>CSVフォーマット</h4>
              <p style={{ fontSize: '0.9em', color: '#1565c0' }}>
                カラム: 農薬名, 在庫量, 単位, 保管場所, 有効期限, 備考
              </p>
            </div>
          </div>
        </>
      )}

      <style>{`
        .tabs {
          display: flex;
          gap: 5px;
          margin-bottom: 20px;
          border-bottom: 2px solid #e0e0e0;
          padding-bottom: 0;
        }
        .tab {
          padding: 12px 24px;
          border: none;
          background: transparent;
          cursor: pointer;
          font-size: 1rem;
          color: #666;
          border-bottom: 3px solid transparent;
          margin-bottom: -2px;
          transition: all 0.2s;
        }
        .tab:hover {
          color: #1976d2;
          background: #f5f5f5;
        }
        .tab.active {
          color: #1976d2;
          border-bottom-color: #1976d2;
          font-weight: 500;
        }
        .inventory-table tr.expired {
          background-color: #ffebee;
        }
        .inventory-table tr.expiring-soon {
          background-color: #fff3e0;
        }
        .backup-actions {
          margin-top: 20px;
        }
      `}</style>
    </div>
  );
}
