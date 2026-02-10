/**
 * 制約設定エディタコンポーネント
 */

import { useState, useEffect } from 'react';
import { constraintApi } from '../lib/api';

const DEFAULT_CROPS = ['春小麦', '秋小麦', '大豆', 'デントコーン', 'てんさい', '馬鈴薯'];

export default function ConstraintEditor({ crops = DEFAULT_CROPS, onSave }) {
  const [constraints, setConstraints] = useState([]);
  const [forbiddenTransitions, setForbiddenTransitions] = useState('');
  const [preferredTransitions, setPreferredTransitions] = useState('');
  const [mainCrops, setMainCrops] = useState('');
  const [isSaving, setIsSaving] = useState(false);
  const [message, setMessage] = useState(null);
  const [isExpanded, setIsExpanded] = useState(false);
  const [adjacentFamilyEnabled, setAdjacentFamilyEnabled] = useState(false);
  const [adjacencyBufferMeters, setAdjacencyBufferMeters] = useState(1.0);

  // 初期データ読み込み
  useEffect(() => {
    loadConstraints();
  }, []);

  // 作物リスト変更時に制約テーブル更新
  useEffect(() => {
    if (constraints.length === 0) {
      initializeConstraints(crops);
    } else {
      // 新しい作物を追加
      const existingCrops = new Set(constraints.map(c => c.crop));
      const newConstraints = [...constraints];
      for (const crop of crops) {
        if (!existingCrops.has(crop)) {
          newConstraints.push(createEmptyConstraint(crop));
        }
      }
      setConstraints(newConstraints);
    }
  }, [crops]);

  const createEmptyConstraint = (crop) => ({
    crop,
    min_ha: 0,
    cap_ha: 0,
    min_gap_years: 0,
    min_fields: 0,
    max_fields: 0,
  });

  const initializeConstraints = (cropList) => {
    setConstraints(cropList.map(createEmptyConstraint));
  };

  const loadConstraints = async () => {
    try {
      const data = await constraintApi.get();
      if (data.constraints && data.constraints.length > 0) {
        setConstraints(data.constraints);
      } else {
        initializeConstraints(crops);
      }
      setForbiddenTransitions(data.forbidden_transitions || '');
      setPreferredTransitions(data.preferred_transitions || '');
      setMainCrops(data.main_crops || '');
      setAdjacentFamilyEnabled(data.adjacent_family_enabled || false);
      setAdjacencyBufferMeters(data.adjacency_buffer_meters || 1.0);
    } catch {
      initializeConstraints(crops);
    }
  };

  const handleConstraintChange = (index, field, value) => {
    const newConstraints = [...constraints];
    const numValue = parseFloat(value) || 0;
    newConstraints[index] = {
      ...newConstraints[index],
      [field]: numValue,
    };
    setConstraints(newConstraints);
  };

  const handleSave = async () => {
    setIsSaving(true);
    setMessage(null);

    try {
      await constraintApi.update({
        constraints,
        forbidden_transitions: forbiddenTransitions,
        preferred_transitions: preferredTransitions,
        main_crops: mainCrops,
        adjacent_family_enabled: adjacentFamilyEnabled,
        adjacency_buffer_meters: adjacencyBufferMeters,
      });
      setMessage({ type: 'success', text: '制約設定を保存しました' });
      if (onSave) onSave();
    } catch (err) {
      setMessage({ type: 'error', text: '保存に失敗しました: ' + (err.message || '不明なエラー') });
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="constraint-editor">
      <div
        className="constraint-header"
        onClick={() => setIsExpanded(!isExpanded)}
      >
        <h3>
          <span className={`expand-icon ${isExpanded ? 'expanded' : ''}`}>▶</span>
          ⚙️ 制約設定
        </h3>
        <span className="hint">クリックして{isExpanded ? '閉じる' : '開く'}</span>
      </div>

      {isExpanded && (
        <div className="constraint-content">
          {message && (
            <div className={`message ${message.type}`}>
              {message.text}
            </div>
          )}

          <div className="constraint-section">
            <h4>作物別制約</h4>
            <div className="table-wrapper">
              <table className="data-table constraint-table">
                <thead>
                  <tr>
                    <th>作物</th>
                    <th>最小面積(ha)</th>
                    <th>最大面積(ha)</th>
                    <th>間隔年数</th>
                    <th>最小筆数</th>
                    <th>最大筆数</th>
                  </tr>
                </thead>
                <tbody>
                  {constraints.map((c, idx) => (
                    <tr key={c.crop}>
                      <td className="crop-name">{c.crop}</td>
                      <td>
                        <input
                          type="number"
                          min="0"
                          step="0.1"
                          value={c.min_ha || ''}
                          onChange={(e) => handleConstraintChange(idx, 'min_ha', e.target.value)}
                          placeholder="0"
                        />
                      </td>
                      <td>
                        <input
                          type="number"
                          min="0"
                          step="0.1"
                          value={c.cap_ha || ''}
                          onChange={(e) => handleConstraintChange(idx, 'cap_ha', e.target.value)}
                          placeholder="0"
                        />
                      </td>
                      <td>
                        <input
                          type="number"
                          min="0"
                          step="1"
                          value={c.min_gap_years || ''}
                          onChange={(e) => handleConstraintChange(idx, 'min_gap_years', e.target.value)}
                          placeholder="0"
                        />
                      </td>
                      <td>
                        <input
                          type="number"
                          min="0"
                          step="1"
                          value={c.min_fields || ''}
                          onChange={(e) => handleConstraintChange(idx, 'min_fields', e.target.value)}
                          placeholder="0"
                        />
                      </td>
                      <td>
                        <input
                          type="number"
                          min="0"
                          step="1"
                          value={c.max_fields || ''}
                          onChange={(e) => handleConstraintChange(idx, 'max_fields', e.target.value)}
                          placeholder="0"
                        />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="help-text">
              0 = 制限なし。間隔年数は同じ作物を連続して植えられない年数です。
            </p>
          </div>

          <div className="constraint-section">
            <h4>遷移ルール</h4>

            <div className="form-group">
              <label>禁止遷移（前作→次作）</label>
              <input
                type="text"
                value={forbiddenTransitions}
                onChange={(e) => setForbiddenTransitions(e.target.value)}
                placeholder="例: てんさい->秋小麦, 春小麦->秋小麦"
              />
              <p className="help-text">カンマ区切りで指定。指定した遷移は計画から除外されます。</p>
            </div>

            <div className="form-group">
              <label>優先遷移（前作→次作:重み）</label>
              <input
                type="text"
                value={preferredTransitions}
                onChange={(e) => setPreferredTransitions(e.target.value)}
                placeholder="例: 大豆->秋小麦:10, てんさい->春小麦:8"
              />
              <p className="help-text">カンマ区切りで指定。重みが大きいほど優先されます。</p>
            </div>

            <div className="form-group">
              <label>主作物</label>
              <input
                type="text"
                value={mainCrops}
                onChange={(e) => setMainCrops(e.target.value)}
                placeholder="例: 春小麦, 秋小麦, 大豆"
              />
              <p className="help-text">カンマ区切りで指定。毎年必ず作付けされる作物です。</p>
            </div>
          </div>

          <div className="constraint-section">
            <h4>🔒 PRO: 隣接筆制約</h4>
            <div className="form-group">
              <label className="checkbox-label">
                <input
                  type="checkbox"
                  checked={adjacentFamilyEnabled}
                  onChange={(e) => setAdjacentFamilyEnabled(e.target.checked)}
                />
                隣接ほ場に同じ科の作物を配置しない
              </label>
              <p className="help-text">
                同じ「科」の作物が隣接するほ場に配置されないよう制約します（連作障害防止）。
              </p>
            </div>
            {adjacentFamilyEnabled && (
              <div className="form-group">
                <label>隣接判定バッファ距離（メートル）</label>
                <input
                  type="number"
                  min="0"
                  step="0.5"
                  value={adjacencyBufferMeters}
                  onChange={(e) => setAdjacencyBufferMeters(parseFloat(e.target.value) || 1.0)}
                  placeholder="1.0"
                  style={{ width: '100px' }}
                />
                <p className="help-text">
                  ほ場間の距離がこの値以内なら隣接と判定します。デフォルト: 1.0m
                </p>
              </div>
            )}
          </div>

          <div className="constraint-actions">
            <button
              onClick={handleSave}
              disabled={isSaving}
              className="btn-primary"
            >
              {isSaving ? '保存中...' : '💾 制約を保存'}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
