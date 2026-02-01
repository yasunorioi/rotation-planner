/**
 * 輪作計画ページ
 */

import { useEffect, useState, useMemo } from 'react';
import { useFieldStore } from '../store/fieldStore';
import { fieldApi, constraintApi, planApi, cropApi } from '../lib/api';
import { RotationSolver, createDefaultConstraints, generateResultTables } from '../lib/rotationSolver';

const DEFAULT_CROPS = ['春小麦', '秋小麦', '大豆', 'デントコーン', 'てんさい', '馬鈴薯'];

export default function Rotation() {
  const { fields, fetchFields, isLoading: fieldsLoading } = useFieldStore();
  const [fieldHistories, setFieldHistories] = useState({});
  const [crops, setCrops] = useState(DEFAULT_CROPS);
  const [constraints, setConstraints] = useState(null);
  const [futureYears, setFutureYears] = useState(4);
  const [result, setResult] = useState(null);
  const [isCalculating, setIsCalculating] = useState(false);
  const [error, setError] = useState(null);
  const [saveName, setSaveName] = useState('');

  // 過去年を計算（現在の令和年から過去2年）
  const currentReiwaYear = new Date().getFullYear() - 2018;
  const pastYears = useMemo(() => {
    return [`R${currentReiwaYear - 1}`, `R${currentReiwaYear}`];
  }, [currentReiwaYear]);

  // 将来年を計算
  const futureYearsList = useMemo(() => {
    return Array.from({ length: futureYears }, (_, i) => `R${currentReiwaYear + 1 + i}`);
  }, [currentReiwaYear, futureYears]);

  // データ読み込み
  useEffect(() => {
    fetchFields();
    loadCrops();
    loadConstraints();
  }, [fetchFields]);

  // 作付履歴読み込み
  useEffect(() => {
    if (fields.length > 0) {
      loadHistories();
    }
  }, [fields]);

  const loadCrops = async () => {
    try {
      const userCrops = await cropApi.listUserCrops();
      if (userCrops.length > 0) {
        setCrops(userCrops.map((c) => c.custom_name || c.name));
      }
    } catch {
      // デフォルトを使用
    }
  };

  const loadConstraints = async () => {
    try {
      const data = await constraintApi.get();
      setConstraints(data);
    } catch {
      setConstraints(null);
    }
  };

  const loadHistories = async () => {
    const histories = {};
    for (const field of fields) {
      try {
        const history = await fieldApi.getHistory(field.id);
        histories[field.id] = {};
        for (const h of history) {
          histories[field.id][`R${h.year}`] = h.crop;
        }
      } catch {
        histories[field.id] = {};
      }
    }
    setFieldHistories(histories);
  };

  // ソルバー用データ準備
  const prepareFields = () => {
    return fields.map((f, i) => ({
      fieldId: String(f.id),
      fieldCode: f.field_code,
      district: f.district || '',
      areaHa: f.area_ha,
      history: fieldHistories[f.id] || {},
      beetForbidden: f.beet_forbidden || false,
    }));
  };

  // 制約データ準備
  const prepareConstraints = () => {
    if (!constraints || !constraints.constraints || constraints.constraints.length === 0) {
      return createDefaultConstraints();
    }

    const c = createDefaultConstraints();

    // 制約テーブルから
    for (const row of constraints.constraints) {
      const crop = row.crop;
      if (!crop) continue;

      if (row.min_ha && row.min_ha > 0) c.cropMins[crop] = row.min_ha;
      if (row.cap_ha && row.cap_ha > 0) c.cropCaps[crop] = row.cap_ha;
      if (row.min_gap_years && row.min_gap_years > 0) c.minGapYears[crop] = row.min_gap_years;
      if (row.min_fields && row.min_fields > 0) c.minFields[crop] = row.min_fields;
      if (row.max_fields && row.max_fields > 0) c.maxFields[crop] = row.max_fields;
    }

    // 禁止遷移
    if (constraints.forbidden_transitions) {
      const pairs = constraints.forbidden_transitions.split(',');
      for (const pair of pairs) {
        const match = pair.match(/(.+)->(.+)/);
        if (match) {
          c.forbiddenTransitions.push([match[1].trim(), match[2].trim()]);
        }
      }
    }
    // 固定の禁止遷移
    c.forbiddenTransitions.push(['てんさい', '秋小麦'], ['春小麦', '秋小麦']);

    // 優先遷移
    if (constraints.preferred_transitions) {
      const pairs = constraints.preferred_transitions.split(',');
      for (const pair of pairs) {
        const match = pair.match(/(.+)->(.+):(\d+)/);
        if (match) {
          c.preferredTransitions[`${match[1].trim()}->${match[2].trim()}`] = parseInt(match[3]);
        }
      }
    }

    // 主作物
    if (constraints.main_crops) {
      c.mainCrops = constraints.main_crops.split(',').map((s) => s.trim()).filter(Boolean);
    }

    return c;
  };

  // 最適化実行
  const runOptimization = async () => {
    if (fields.length === 0) {
      setError('ほ場が登録されていません');
      return;
    }

    setIsCalculating(true);
    setError(null);

    try {
      const solverFields = prepareFields();
      const solverConstraints = prepareConstraints();

      const startTime = performance.now();

      const solver = new RotationSolver(
        solverFields,
        pastYears,
        futureYearsList,
        crops,
        solverConstraints
      );

      const { plan, score, errors } = solver.solve({ maxIterations: 2000 });
      const { fieldTable, summaryTable } = generateResultTables(
        solverFields,
        pastYears,
        futureYearsList,
        plan,
        crops
      );

      const elapsedMs = Math.round(performance.now() - startTime);

      setResult({
        plan,
        score,
        errors,
        fieldTable,
        summaryTable,
        elapsedMs,
      });
    } catch (err) {
      setError(err.message || '計算エラーが発生しました');
    } finally {
      setIsCalculating(false);
    }
  };

  // 計画保存
  const savePlan = async () => {
    if (!result || !saveName.trim()) {
      alert('計画名を入力してください');
      return;
    }

    try {
      const details = [];
      for (const [key, crop] of Object.entries(result.plan)) {
        const [fieldIdx, year] = key.split(',');
        const yearNum = parseInt(year.replace('R', ''));
        details.push({
          field_id: fields[parseInt(fieldIdx)].id,
          year: yearNum,
          crop,
        });
      }

      await planApi.create({
        name: saveName,
        start_year: parseInt(futureYearsList[0].replace('R', '')),
        end_year: parseInt(futureYearsList[futureYearsList.length - 1].replace('R', '')),
        details,
      });

      alert('計画を保存しました');
      setSaveName('');
    } catch (err) {
      alert('保存に失敗しました: ' + (err.message || '不明なエラー'));
    }
  };

  const allYears = [...pastYears, ...futureYearsList];

  return (
    <div className="rotation-page">
      <h1>🔄 輪作計画</h1>

      <div className="settings-panel">
        <div className="setting-group">
          <label>将来年数</label>
          <select value={futureYears} onChange={(e) => setFutureYears(parseInt(e.target.value))}>
            <option value={3}>3年</option>
            <option value={4}>4年</option>
            <option value={5}>5年</option>
            <option value={6}>6年</option>
          </select>
        </div>

        <button
          onClick={runOptimization}
          disabled={isCalculating || fieldsLoading || fields.length === 0}
          className="btn-primary btn-large"
        >
          {isCalculating ? '計算中...' : '🔄 最適化実行'}
        </button>
      </div>

      {error && <div className="error-message">{error}</div>}

      {result && (
        <div className="result-section">
          <div className="result-header">
            <div className="score">
              スコア: {result.score.toFixed(1)}
              <span className="elapsed">({result.elapsedMs}ms)</span>
            </div>
            <div className="save-form">
              <input
                type="text"
                placeholder="計画名"
                value={saveName}
                onChange={(e) => setSaveName(e.target.value)}
              />
              <button onClick={savePlan} className="btn-secondary">
                💾 保存
              </button>
            </div>
          </div>

          {result.errors.length > 0 && (
            <div className="warnings">
              <h4>⚠️ 警告/違反</h4>
              <ul>
                {result.errors.map((e, i) => (
                  <li key={i}>{e}</li>
                ))}
              </ul>
            </div>
          )}

          <h3>ほ場×年 計画表</h3>
          <div className="table-wrapper">
            <table className="data-table rotation-table">
              <thead>
                <tr>
                  <th>コード</th>
                  <th>地区</th>
                  <th>面積</th>
                  {allYears.map((y) => (
                    <th key={y} className={pastYears.includes(y) ? 'past-year' : 'future-year'}>
                      {y}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {result.fieldTable.map((row, i) => (
                  <tr key={i}>
                    <td>{row.field_code}</td>
                    <td>{row.district || '-'}</td>
                    <td>{row.area_ha.toFixed(1)}</td>
                    {allYears.map((y) => (
                      <td key={y} className={`crop-cell ${pastYears.includes(y) ? 'past' : 'future'}`}>
                        <span className={`crop-badge crop-${row[y]?.replace(/[^\w]/g, '') || 'empty'}`}>
                          {row[y] || '-'}
                        </span>
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <h3>年別 作物面積(ha)</h3>
          <div className="table-wrapper">
            <table className="data-table summary-table">
              <thead>
                <tr>
                  <th>年</th>
                  {crops.map((c) => (
                    <th key={c}>{c}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {result.summaryTable.map((row, i) => (
                  <tr key={i}>
                    <td className={pastYears.includes(row.year) ? 'past-year' : 'future-year'}>
                      {row.year}
                    </td>
                    {crops.map((c) => (
                      <td key={c}>{parseFloat(row[c]).toFixed(1)}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
