/**
 * 輪作計画ソルバー (JavaScript版)
 *
 * OR-Tools CP-SAT の代替として、ブラウザ/Web Worker で動作する軽量ソルバー。
 * ヒューリスティック（貪欲法 + 局所探索）で高速に解を求める。
 *
 * @version 1.0.0
 */

// =============================================================================
// 定数
// =============================================================================

const UNKNOWN_MARKER = '?';

// =============================================================================
// 制約クラス
// =============================================================================

/**
 * 制約設定
 * @typedef {Object} Constraints
 * @property {Object<string, number|null>} cropMins - 作物ごとの最小面積(ha)
 * @property {Object<string, number|null>} cropCaps - 作物ごとの最大面積(ha)
 * @property {Object<string, number>} minGapYears - 作物ごとの最小間隔年数
 * @property {Object<string, number>} minFields - 作物ごとの最小ほ場数
 * @property {Object<string, number|null>} maxFields - 作物ごとの最大ほ場数
 * @property {Array<[string, string]>} forbiddenTransitions - 禁止遷移リスト
 * @property {Object<string, number>} preferredTransitions - 優先遷移（キー: "from->to", 値: スコア）
 * @property {string[]} mainCrops - 主作物リスト（面積変動を抑えたい作物）
 * @property {string} unknownMode - 空欄の扱い ("ignore" | "safe")
 */

/**
 * ほ場データ
 * @typedef {Object} Field
 * @property {string} fieldId - ほ場ID
 * @property {string} fieldCode - ほ場コード
 * @property {string} district - 地区
 * @property {number} areaHa - 面積(ha)
 * @property {Object<string, string>} history - 過去の作付履歴 {年: 作物}
 * @property {boolean} beetForbidden - てんさい/馬鈴薯禁止フラグ
 */

/**
 * デフォルト制約を作成
 * @returns {Constraints}
 */
function createDefaultConstraints() {
  return {
    cropMins: {},
    cropCaps: {},
    minGapYears: {},
    minFields: {},
    maxFields: {},
    forbiddenTransitions: [],
    preferredTransitions: {},
    mainCrops: [],
    unknownMode: 'ignore'
  };
}

// =============================================================================
// ユーティリティ関数
// =============================================================================

/**
 * 配列をシャッフル（Fisher-Yates）
 * @param {Array} array
 * @returns {Array}
 */
function shuffle(array) {
  const result = [...array];
  for (let i = result.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [result[i], result[j]] = [result[j], result[i]];
  }
  return result;
}

/**
 * 分散を計算
 * @param {number[]} arr
 * @returns {number}
 */
function variance(arr) {
  if (arr.length === 0) return 0;
  const mean = arr.reduce((a, b) => a + b, 0) / arr.length;
  return arr.reduce((acc, val) => acc + Math.pow(val - mean, 2), 0) / arr.length;
}

// =============================================================================
// RotationSolver クラス
// =============================================================================

class RotationSolver {
  /**
   * @param {Field[]} fields - ほ場リスト
   * @param {string[]} pastYears - 過去年リスト（例: ['R4', 'R5', 'R6']）
   * @param {string[]} futureYears - 将来年リスト（例: ['R7', 'R8', 'R9']）
   * @param {string[]} crops - 作物リスト
   * @param {Constraints} constraints - 制約設定
   */
  constructor(fields, pastYears, futureYears, crops, constraints) {
    this.fields = fields;
    this.pastYears = pastYears;
    this.futureYears = futureYears;
    this.allYears = [...pastYears, ...futureYears];
    this.crops = crops;
    this.constraints = constraints;
    this.errors = [];

    // 禁止遷移をSetに変換（高速ルックアップ用）
    this.forbiddenSet = new Set(
      constraints.forbiddenTransitions.map(([from, to]) => `${from}->${to}`)
    );
  }

  /**
   * 指定年から過去n年の作付を取得
   * @param {number} fieldIdx - ほ場インデックス
   * @param {string} year - 対象年
   * @param {number} n - 取得する年数
   * @param {Object} plan - 計画 {`${fieldIdx},${year}`: crop}
   * @returns {string[]}
   */
  getLastNCrops(fieldIdx, year, n, plan) {
    const yearIdx = this.allYears.indexOf(year);
    const cropsList = [];

    for (let i = 1; i <= n; i++) {
      if (yearIdx - i >= 0) {
        const prevYear = this.allYears[yearIdx - i];
        if (this.pastYears.includes(prevYear)) {
          cropsList.push(this.fields[fieldIdx].history[prevYear] || UNKNOWN_MARKER);
        } else {
          cropsList.push(plan[`${fieldIdx},${prevYear}`] || UNKNOWN_MARKER);
        }
      }
    }
    return cropsList;
  }

  /**
   * 間隔制約をチェック
   * @param {number} fieldIdx
   * @param {string} year
   * @param {string} crop
   * @param {Object} plan
   * @returns {boolean}
   */
  checkGapConstraint(fieldIdx, year, crop, plan) {
    const minGap = this.constraints.minGapYears[crop] || 0;
    if (minGap <= 0) return true;

    const pastCrops = this.getLastNCrops(fieldIdx, year, minGap, plan);

    for (const pc of pastCrops) {
      if (pc === crop) return false;
      if (pc === UNKNOWN_MARKER && this.constraints.unknownMode === 'safe') {
        return false;
      }
    }
    return true;
  }

  /**
   * 遷移制約をチェック（連作禁止含む）
   * @param {number} fieldIdx
   * @param {string} year
   * @param {string} crop
   * @param {Object} plan
   * @returns {boolean}
   */
  checkTransitionConstraint(fieldIdx, year, crop, plan) {
    const prevCrops = this.getLastNCrops(fieldIdx, year, 1, plan);
    if (prevCrops.length === 0) return true;

    const prevCrop = prevCrops[0];

    if (prevCrop === UNKNOWN_MARKER) {
      if (this.constraints.unknownMode === 'safe') {
        // safeモード: 禁止遷移のto側なら拒否
        for (const [from, to] of this.constraints.forbiddenTransitions) {
          if (to === crop) return false;
        }
      }
      return true;
    }

    // 連作禁止
    if (prevCrop === crop) return false;

    // 禁止遷移
    if (this.forbiddenSet.has(`${prevCrop}->${crop}`)) return false;

    return true;
  }

  /**
   * てんさい/馬鈴薯禁止ほ場チェック
   * @param {number} fieldIdx
   * @param {string} crop
   * @returns {boolean}
   */
  checkBeetForbidden(fieldIdx, crop) {
    if (!this.fields[fieldIdx].beetForbidden) return true;
    if (crop === 'てんさい' || crop === '馬鈴薯') return false;
    return true;
  }

  /**
   * 有効な作物リストを取得
   * @param {number} fieldIdx
   * @param {string} year
   * @param {Object} plan
   * @returns {string[]}
   */
  getValidCrops(fieldIdx, year, plan) {
    const valid = [];
    for (const crop of this.crops) {
      if (!this.checkBeetForbidden(fieldIdx, crop)) continue;
      if (!this.checkGapConstraint(fieldIdx, year, crop, plan)) continue;
      if (!this.checkTransitionConstraint(fieldIdx, year, crop, plan)) continue;
      valid.push(crop);
    }
    return valid;
  }

  /**
   * 年の作物統計を計算
   * @param {string} year
   * @param {Object} plan
   * @returns {Object<string, {totalHa: number, fieldCount: number}>}
   */
  calculateYearStats(year, plan) {
    const stats = {};
    for (const crop of this.crops) {
      stats[crop] = { totalHa: 0, fieldCount: 0 };
    }

    for (let i = 0; i < this.fields.length; i++) {
      let crop;
      if (this.pastYears.includes(year)) {
        crop = this.fields[i].history[year] || UNKNOWN_MARKER;
      } else {
        crop = plan[`${i},${year}`] || null;
      }

      if (crop && crop !== UNKNOWN_MARKER && stats[crop]) {
        stats[crop].totalHa += this.fields[i].areaHa;
        stats[crop].fieldCount += 1;
      }
    }
    return stats;
  }

  /**
   * 面積上限をチェック
   * @param {string} year
   * @param {string} crop
   * @param {Object} plan
   * @param {number} additionalHa
   * @returns {boolean}
   */
  checkCapConstraint(year, crop, plan, additionalHa = 0) {
    const cap = this.constraints.cropCaps[crop];
    if (cap == null || cap === 0) return true;

    const stats = this.calculateYearStats(year, plan);
    const currentHa = stats[crop]?.totalHa || 0;
    return currentHa + additionalHa <= cap;
  }

  /**
   * ほ場数制約をチェック
   * @param {string} year
   * @param {string} crop
   * @param {Object} plan
   * @param {boolean} adding
   * @returns {{ok: boolean, message: string}}
   */
  checkFieldCountConstraint(year, crop, plan, adding = false) {
    const minF = this.constraints.minFields[crop] || 0;
    const maxF = this.constraints.maxFields[crop];

    const stats = this.calculateYearStats(year, plan);
    let currentCount = stats[crop]?.fieldCount || 0;
    if (adding) currentCount += 1;

    if (maxF != null && currentCount > maxF) {
      return { ok: false, message: `${crop}のほ場数が上限(${maxF})を超えます` };
    }
    return { ok: true, message: '' };
  }

  /**
   * 遷移スコアを計算
   * @param {number} fieldIdx
   * @param {string} year
   * @param {string} crop
   * @param {Object} plan
   * @returns {number}
   */
  calculateTransitionScore(fieldIdx, year, crop, plan) {
    const prevCrops = this.getLastNCrops(fieldIdx, year, 1, plan);
    if (prevCrops.length === 0 || prevCrops[0] === UNKNOWN_MARKER) return 0;

    const prevCrop = prevCrops[0];
    const key = `${prevCrop}->${crop}`;
    return this.constraints.preferredTransitions[key] || 0;
  }

  /**
   * 間隔ボーナス（間隔制約の作物で余裕があるほどボーナス）
   * @param {number} fieldIdx
   * @param {string} year
   * @param {string} crop
   * @param {Object} plan
   * @returns {number}
   */
  calculateGapBonus(fieldIdx, year, crop, plan) {
    const minGap = this.constraints.minGapYears[crop] || 0;
    if (minGap <= 0) return 0;

    const yearIdx = this.allYears.indexOf(year);
    let actualGap = 0;

    for (let i = 1; i < this.allYears.length; i++) {
      if (yearIdx - i < 0) break;
      const prevYear = this.allYears[yearIdx - i];
      let prevCrop;
      if (this.pastYears.includes(prevYear)) {
        prevCrop = this.fields[fieldIdx].history[prevYear];
      } else {
        prevCrop = plan[`${fieldIdx},${prevYear}`];
      }
      if (prevCrop === crop) break;
      actualGap += 1;
    }

    return Math.max(0, actualGap - minGap) * 0.5;
  }

  /**
   * 解の評価
   * @param {Object} plan
   * @returns {{score: number, violations: string[]}}
   */
  evaluateSolution(plan) {
    let score = 0;
    const violations = [];

    // 各年の統計
    const yearStats = {};
    for (const year of this.futureYears) {
      yearStats[year] = this.calculateYearStats(year, plan);
    }

    // 1. 主作物の面積変動を評価（分散を最小化）
    for (const crop of this.constraints.mainCrops) {
      const areas = this.futureYears.map(y => yearStats[y][crop]?.totalHa || 0);
      const v = variance(areas);
      score -= v * 10;
    }

    // 2. 優先遷移スコア + 間隔ボーナス
    for (let i = 0; i < this.fields.length; i++) {
      for (const year of this.futureYears) {
        const crop = plan[`${i},${year}`];
        if (crop) {
          score += this.calculateTransitionScore(i, year, crop, plan);
          score += this.calculateGapBonus(i, year, crop, plan);
        }
      }
    }

    // 3. 制約違反チェック
    for (const year of this.futureYears) {
      const stats = yearStats[year];

      for (const crop of this.crops) {
        // 面積上限
        const cap = this.constraints.cropCaps[crop];
        if (cap != null && cap > 0) {
          const ha = stats[crop]?.totalHa || 0;
          if (ha > cap) {
            violations.push(`${year}: ${crop}の面積(${ha.toFixed(2)}ha)が上限(${cap}ha)を超過`);
            score -= 100;
          }
        }

        // 面積下限
        const min = this.constraints.cropMins[crop];
        if (min != null && min > 0) {
          const ha = stats[crop]?.totalHa || 0;
          if (ha < min) {
            violations.push(`${year}: ${crop}の面積(${ha.toFixed(2)}ha)が下限(${min}ha)未満`);
            score -= 100;
          }
        }

        // ほ場数制約
        const minF = this.constraints.minFields[crop] || 0;
        const maxF = this.constraints.maxFields[crop];
        const cnt = stats[crop]?.fieldCount || 0;

        if (cnt < minF) {
          violations.push(`${year}: ${crop}のほ場数(${cnt})が下限(${minF})未満`);
          score -= 50;
        }
        if (maxF != null && cnt > maxF) {
          violations.push(`${year}: ${crop}のほ場数(${cnt})が上限(${maxF})超過`);
          score -= 50;
        }
      }
    }

    return { score, violations };
  }

  /**
   * 初期解を生成（貪欲法）
   * @returns {Object}
   */
  generateInitialSolution() {
    const plan = {};

    for (const year of this.futureYears) {
      const fieldIndices = shuffle([...Array(this.fields.length).keys()]);

      for (const fieldIdx of fieldIndices) {
        let validCrops = this.getValidCrops(fieldIdx, year, plan);

        if (validCrops.length === 0) {
          validCrops = [...this.crops];
          this.errors.push(`警告: ほ場${this.fields[fieldIdx].fieldId}の${year}で制約を満たす作物がありません`);
        }

        let bestCrop = null;
        let bestScore = -Infinity;

        for (const crop of validCrops) {
          // 面積上限チェック
          if (!this.checkCapConstraint(year, crop, plan, this.fields[fieldIdx].areaHa)) {
            continue;
          }

          // ほ場数上限チェック
          const { ok } = this.checkFieldCountConstraint(year, crop, plan, true);
          if (!ok) continue;

          // スコア計算
          let s = this.calculateTransitionScore(fieldIdx, year, crop, plan);
          s += this.calculateGapBonus(fieldIdx, year, crop, plan);
          s += Math.random() * 0.1; // タイブレーク用

          if (s > bestScore) {
            bestScore = s;
            bestCrop = crop;
          }
        }

        if (bestCrop === null) {
          bestCrop = validCrops.length > 0 ? validCrops[0] : this.crops[0];
        }

        plan[`${fieldIdx},${year}`] = bestCrop;
      }
    }

    return plan;
  }

  /**
   * 局所探索で解を改善
   * @param {Object} plan
   * @param {number} maxIterations
   * @returns {Object}
   */
  localSearch(plan, maxIterations = 1000) {
    let currentPlan = { ...plan };
    let { score: currentScore } = this.evaluateSolution(currentPlan);

    for (let iter = 0; iter < maxIterations; iter++) {
      const fieldIdx = Math.floor(Math.random() * this.fields.length);
      const year = this.futureYears[Math.floor(Math.random() * this.futureYears.length)];
      const key = `${fieldIdx},${year}`;

      const validCrops = this.getValidCrops(fieldIdx, year, currentPlan);
      if (validCrops.length === 0) continue;

      const oldCrop = currentPlan[key];
      const newCrop = validCrops[Math.floor(Math.random() * validCrops.length)];

      if (newCrop === oldCrop) continue;

      // 仮に変更
      currentPlan[key] = newCrop;

      // 制約チェック
      if (!this.checkCapConstraint(year, newCrop, currentPlan)) {
        currentPlan[key] = oldCrop;
        continue;
      }

      const { ok } = this.checkFieldCountConstraint(year, newCrop, currentPlan);
      if (!ok) {
        currentPlan[key] = oldCrop;
        continue;
      }

      // スコア評価
      const { score: newScore } = this.evaluateSolution(currentPlan);

      if (newScore > currentScore) {
        currentScore = newScore;
      } else {
        currentPlan[key] = oldCrop;
      }
    }

    return currentPlan;
  }

  /**
   * 最小ほ場数制約を満たすように調整
   * @param {Object} plan
   * @returns {Object}
   */
  ensureMinFields(plan) {
    for (const year of this.futureYears) {
      const stats = this.calculateYearStats(year, plan);

      for (const crop of this.crops) {
        const minF = this.constraints.minFields[crop] || 0;
        if (minF <= 0) continue;

        let currentCount = stats[crop]?.fieldCount || 0;

        while (currentCount < minF) {
          let changed = false;

          for (let i = 0; i < this.fields.length; i++) {
            const key = `${i},${year}`;
            const currentCrop = plan[key];
            if (currentCrop === crop) continue;

            // 制約チェック
            if (!this.checkGapConstraint(i, year, crop, plan)) continue;
            if (!this.checkTransitionConstraint(i, year, crop, plan)) continue;
            if (!this.checkBeetForbidden(i, crop)) continue;

            // 既存の作物の最小ほ場数を下回らないか
            if (currentCrop) {
              const otherMin = this.constraints.minFields[currentCrop] || 0;
              const otherStats = this.calculateYearStats(year, plan);
              if ((otherStats[currentCrop]?.fieldCount || 0) <= otherMin) {
                continue;
              }
            }

            plan[key] = crop;
            changed = true;
            currentCount += 1;
            break;
          }

          if (!changed) {
            this.errors.push(`警告: ${year}の${crop}最小ほ場数(${minF})を満たせません`);
            break;
          }
        }
      }
    }

    return plan;
  }

  /**
   * 最適化を実行
   * @param {Object} options
   * @param {number} options.maxIterations - 局所探索の最大反復回数
   * @returns {{plan: Object, score: number, errors: string[]}}
   */
  solve(options = {}) {
    const { maxIterations = 2000 } = options;

    this.errors = [];

    // 1. 初期解生成
    let plan = this.generateInitialSolution();

    // 2. 局所探索
    plan = this.localSearch(plan, maxIterations);

    // 3. 最小ほ場数調整
    plan = this.ensureMinFields(plan);

    // 4. 最終評価
    const { score, violations } = this.evaluateSolution(plan);
    const allErrors = [...this.errors, ...violations];

    return { plan, score, errors: allErrors };
  }
}

// =============================================================================
// 結果変換
// =============================================================================

/**
 * 計画結果をテーブル形式に変換
 * @param {Field[]} fields
 * @param {string[]} pastYears
 * @param {string[]} futureYears
 * @param {Object} plan
 * @param {string[]} crops
 * @returns {{fieldTable: Array, summaryTable: Array}}
 */
function generateResultTables(fields, pastYears, futureYears, plan, crops) {
  const allYears = [...pastYears, ...futureYears];

  // ほ場×年テーブル
  const fieldTable = fields.map((field, i) => {
    const row = {
      field_code: field.fieldCode,
      district: field.district || '',
      area_ha: field.areaHa
    };

    for (const year of allYears) {
      if (pastYears.includes(year)) {
        row[year] = field.history[year] || '';
      } else {
        row[year] = plan[`${i},${year}`] || '';
      }
    }

    return row;
  });

  // 年別作物面積サマリー
  const summaryTable = [];
  for (const year of allYears) {
    const row = { year };
    for (const crop of crops) {
      let totalHa = 0;
      for (let i = 0; i < fields.length; i++) {
        let c;
        if (pastYears.includes(year)) {
          c = fields[i].history[year];
        } else {
          c = plan[`${i},${year}`];
        }
        if (c === crop) {
          totalHa += fields[i].areaHa;
        }
      }
      row[crop] = totalHa.toFixed(2);
    }
    summaryTable.push(row);
  }

  return { fieldTable, summaryTable };
}

// =============================================================================
// エクスポート（CommonJS / ES Modules / Web Worker 対応）
// =============================================================================

// グローバルスコープに公開（Web Worker / Browser用）
if (typeof self !== 'undefined') {
  self.RotationSolver = RotationSolver;
  self.createDefaultConstraints = createDefaultConstraints;
  self.generateResultTables = generateResultTables;
  self.UNKNOWN_MARKER = UNKNOWN_MARKER;
}

// Node.js / CommonJS 用
if (typeof module !== 'undefined' && module.exports) {
  module.exports = {
    RotationSolver,
    createDefaultConstraints,
    generateResultTables,
    UNKNOWN_MARKER
  };
}
