/**
 * 輪作計画ソルバー (ES Modules版)
 *
 * ES Modules として import する場合はこちらを使用。
 * Web Worker で使用する場合は rotationSolver.js を importScripts で読み込む。
 *
 * @version 1.0.0
 */

// =============================================================================
// 定数
// =============================================================================

export const UNKNOWN_MARKER = '?';

// =============================================================================
// ユーティリティ関数
// =============================================================================

function shuffle(array) {
  const result = [...array];
  for (let i = result.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [result[i], result[j]] = [result[j], result[i]];
  }
  return result;
}

function variance(arr) {
  if (arr.length === 0) return 0;
  const mean = arr.reduce((a, b) => a + b, 0) / arr.length;
  return arr.reduce((acc, val) => acc + Math.pow(val - mean, 2), 0) / arr.length;
}

// =============================================================================
// 制約クラス
// =============================================================================

export function createDefaultConstraints() {
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
// RotationSolver クラス
// =============================================================================

export class RotationSolver {
  constructor(fields, pastYears, futureYears, crops, constraints, pinnedAssignments = []) {
    this.fields = fields;
    this.pastYears = pastYears;
    this.futureYears = futureYears;
    this.allYears = [...pastYears, ...futureYears];
    this.crops = crops;
    this.constraints = constraints;
    this.pinnedAssignments = pinnedAssignments;
    this.errors = [];
    this.forbiddenSet = new Set(
      constraints.forbiddenTransitions.map(([from, to]) => `${from}->${to}`)
    );
    // pinned lookup を事前構築 (cmd_584 subtask_1255 ソルバー組込み)
    this.pinnedMap = new Map();
    for (const pin of pinnedAssignments) {
      const fieldIdx = fields.findIndex((f) => f.id === pin.field_id);
      if (fieldIdx >= 0) {
        this.pinnedMap.set(`${fieldIdx},${pin.year}`, pin.crop);
      }
    }
  }

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

  checkGapConstraint(fieldIdx, year, crop, plan) {
    const minGap = this.constraints.minGapYears[crop] || 0;
    if (minGap <= 0) return true;
    const pastCrops = this.getLastNCrops(fieldIdx, year, minGap, plan);
    for (const pc of pastCrops) {
      if (pc === crop) return false;
      if (pc === UNKNOWN_MARKER && this.constraints.unknownMode === 'safe') return false;
    }
    return true;
  }

  checkTransitionConstraint(fieldIdx, year, crop, plan) {
    const prevCrops = this.getLastNCrops(fieldIdx, year, 1, plan);
    if (prevCrops.length === 0) return true;
    const prevCrop = prevCrops[0];
    if (prevCrop === UNKNOWN_MARKER) {
      if (this.constraints.unknownMode === 'safe') {
        for (const [from, to] of this.constraints.forbiddenTransitions) {
          if (to === crop) return false;
        }
      }
      return true;
    }
    if (prevCrop === crop) return false;
    if (this.forbiddenSet.has(`${prevCrop}->${crop}`)) return false;
    return true;
  }

  checkBeetForbidden(fieldIdx, crop) {
    if (!this.fields[fieldIdx].beetForbidden) return true;
    if (crop === 'てんさい' || crop === '馬鈴薯') return false;
    return true;
  }

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

  checkCapConstraint(year, crop, plan, additionalHa = 0) {
    const cap = this.constraints.cropCaps[crop];
    if (cap == null || cap === 0) return true;
    const stats = this.calculateYearStats(year, plan);
    const currentHa = stats[crop]?.totalHa || 0;
    return currentHa + additionalHa <= cap;
  }

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

  calculateTransitionScore(fieldIdx, year, crop, plan) {
    const prevCrops = this.getLastNCrops(fieldIdx, year, 1, plan);
    if (prevCrops.length === 0 || prevCrops[0] === UNKNOWN_MARKER) return 0;
    const prevCrop = prevCrops[0];
    const key = `${prevCrop}->${crop}`;
    return this.constraints.preferredTransitions[key] || 0;
  }

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

  evaluateSolution(plan) {
    let score = 0;
    const violations = [];
    const yearStats = {};
    for (const year of this.futureYears) {
      yearStats[year] = this.calculateYearStats(year, plan);
    }

    for (const crop of this.constraints.mainCrops) {
      const areas = this.futureYears.map(y => yearStats[y][crop]?.totalHa || 0);
      const v = variance(areas);
      score -= v * 10;
    }

    for (let i = 0; i < this.fields.length; i++) {
      for (const year of this.futureYears) {
        const crop = plan[`${i},${year}`];
        if (crop) {
          score += this.calculateTransitionScore(i, year, crop, plan);
          score += this.calculateGapBonus(i, year, crop, plan);
        }
      }
    }

    for (const year of this.futureYears) {
      const stats = yearStats[year];
      for (const crop of this.crops) {
        const cap = this.constraints.cropCaps[crop];
        if (cap != null && cap > 0) {
          const ha = stats[crop]?.totalHa || 0;
          if (ha > cap) {
            violations.push(`${year}: ${crop}の面積(${ha.toFixed(2)}ha)が上限(${cap}ha)を超過`);
            score -= 100;
          }
        }
        const min = this.constraints.cropMins[crop];
        if (min != null && min > 0) {
          const ha = stats[crop]?.totalHa || 0;
          if (ha < min) {
            violations.push(`${year}: ${crop}の面積(${ha.toFixed(2)}ha)が下限(${min}ha)未満`);
            score -= 100;
          }
        }
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

  generateInitialSolution() {
    const plan = {};
    // cmd_584 subtask_1255: pinned を plan に pre-fill (殿手動R9計画を最優先)
    for (const [key, crop] of this.pinnedMap) {
      plan[key] = crop;
    }
    for (const year of this.futureYears) {
      const fieldIndices = shuffle([...Array(this.fields.length).keys()]);
      for (const fieldIdx of fieldIndices) {
        // pinned はスキップ (既に plan に格納済・cmd_584 subtask_1255)
        if (this.pinnedMap.has(`${fieldIdx},${year}`)) continue;
        let validCrops = this.getValidCrops(fieldIdx, year, plan);
        if (validCrops.length === 0) {
          validCrops = [...this.crops];
          this.errors.push(`警告: ほ場${this.fields[fieldIdx].fieldId}の${year}で制約を満たす作物がありません`);
        }
        let bestCrop = null;
        let bestScore = -Infinity;
        for (const crop of validCrops) {
          if (!this.checkCapConstraint(year, crop, plan, this.fields[fieldIdx].areaHa)) continue;
          const { ok } = this.checkFieldCountConstraint(year, crop, plan, true);
          if (!ok) continue;
          let s = this.calculateTransitionScore(fieldIdx, year, crop, plan);
          s += this.calculateGapBonus(fieldIdx, year, crop, plan);
          s += Math.random() * 0.1;
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
      currentPlan[key] = newCrop;
      if (!this.checkCapConstraint(year, newCrop, currentPlan)) {
        currentPlan[key] = oldCrop;
        continue;
      }
      const { ok } = this.checkFieldCountConstraint(year, newCrop, currentPlan);
      if (!ok) {
        currentPlan[key] = oldCrop;
        continue;
      }
      const { score: newScore } = this.evaluateSolution(currentPlan);
      if (newScore > currentScore) {
        currentScore = newScore;
      } else {
        currentPlan[key] = oldCrop;
      }
    }
    return currentPlan;
  }

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
            if (!this.checkGapConstraint(i, year, crop, plan)) continue;
            if (!this.checkTransitionConstraint(i, year, crop, plan)) continue;
            if (!this.checkBeetForbidden(i, crop)) continue;
            if (currentCrop) {
              const otherMin = this.constraints.minFields[currentCrop] || 0;
              const otherStats = this.calculateYearStats(year, plan);
              if ((otherStats[currentCrop]?.fieldCount || 0) <= otherMin) continue;
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

  solve(options = {}) {
    const { maxIterations = 2000 } = options;
    this.errors = [];
    let plan = this.generateInitialSolution();
    plan = this.localSearch(plan, maxIterations);
    plan = this.ensureMinFields(plan);
    const { score, violations } = this.evaluateSolution(plan);
    const allErrors = [...this.errors, ...violations];
    return { plan, score, errors: allErrors };
  }
}

// =============================================================================
// 結果変換
// =============================================================================

export function generateResultTables(fields, pastYears, futureYears, plan, crops) {
  const allYears = [...pastYears, ...futureYears];
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
        row[year] = plan[`${i},${year}`] || field.history[year] || '';
      }
    }
    return row;
  });

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
          c = plan[`${i},${year}`] || fields[i].history[year];
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
