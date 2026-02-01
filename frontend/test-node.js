#!/usr/bin/env node
/**
 * 輪作計画ソルバー Node.js テスト
 *
 * Usage:
 *   node test-node.js
 */

const {
  RotationSolver,
  createDefaultConstraints,
  generateResultTables,
  UNKNOWN_MARKER
} = require('./src/rotationSolver.js');

// テストデータ
const fields = [
  {
    fieldId: '1',
    fieldCode: 'A-1',
    district: '北',
    areaHa: 2.5,
    history: { 'R5': '大豆', 'R6': '春小麦' },
    beetForbidden: false
  },
  {
    fieldId: '2',
    fieldCode: 'A-2',
    district: '北',
    areaHa: 3.0,
    history: { 'R5': 'てんさい', 'R6': '大豆' },
    beetForbidden: false
  },
  {
    fieldId: '3',
    fieldCode: 'B-1',
    district: '南',
    areaHa: 2.0,
    history: { 'R5': '春小麦', 'R6': 'デントコーン' },
    beetForbidden: false
  },
  {
    fieldId: '4',
    fieldCode: 'B-2',
    district: '南',
    areaHa: 2.5,
    history: { 'R5': '馬鈴薯', 'R6': '春小麦' },
    beetForbidden: false
  },
  {
    fieldId: '5',
    fieldCode: 'C-1',
    district: '東',
    areaHa: 3.5,
    history: { 'R5': '秋小麦', 'R6': '大豆' },
    beetForbidden: true
  },
  {
    fieldId: '6',
    fieldCode: 'C-2',
    district: '東',
    areaHa: 2.8,
    history: { 'R5': 'デントコーン', 'R6': '秋小麦' },
    beetForbidden: false
  },
  {
    fieldId: '7',
    fieldCode: 'D-1',
    district: '西',
    areaHa: 4.0,
    history: { 'R5': '大豆', 'R6': 'てんさい' },
    beetForbidden: false
  },
  {
    fieldId: '8',
    fieldCode: 'D-2',
    district: '西',
    areaHa: 3.2,
    history: { 'R5': '春小麦', 'R6': '大豆' },
    beetForbidden: false
  }
];

const pastYears = ['R5', 'R6'];
const futureYears = ['R7', 'R8', 'R9', 'R10'];
const crops = ['春小麦', '秋小麦', '大豆', 'デントコーン', 'てんさい', '馬鈴薯'];

const constraints = {
  cropMins: {},
  cropCaps: {
    '春小麦': 10,
    '秋小麦': 10,
    '大豆': 12,
    'デントコーン': 8
  },
  minGapYears: {
    'てんさい': 4,
    '馬鈴薯': 4
  },
  minFields: {
    'てんさい': 1
  },
  maxFields: {
    'てんさい': 2
  },
  forbiddenTransitions: [
    ['てんさい', '秋小麦'],
    ['春小麦', '秋小麦']
  ],
  preferredTransitions: {
    'てんさい->大豆': 10,
    'てんさい->春小麦': 5,
    'デントコーン->秋小麦': 8
  },
  mainCrops: ['春小麦', '秋小麦', '大豆'],
  unknownMode: 'ignore'
};

console.log('========================================');
console.log('輪作計画ソルバー テスト (JavaScript版)');
console.log('========================================\n');

console.log(`ほ場数: ${fields.length}`);
console.log(`作物数: ${crops.length}`);
console.log(`過去年: ${pastYears.join(', ')}`);
console.log(`将来年: ${futureYears.join(', ')}`);
console.log('');

// ソルバー実行
console.log('最適化を実行中...\n');
const startTime = Date.now();

const solver = new RotationSolver(fields, pastYears, futureYears, crops, constraints);
const { plan, score, errors } = solver.solve({ maxIterations: 3000 });

const elapsedMs = Date.now() - startTime;

console.log(`完了！ (${elapsedMs}ms)\n`);
console.log(`スコア: ${score.toFixed(2)}`);

// エラー・警告
if (errors.length > 0) {
  console.log('\n⚠️ 警告/違反:');
  errors.forEach(e => console.log(`  - ${e}`));
}

// 結果テーブル生成
const { fieldTable, summaryTable } = generateResultTables(
  fields, pastYears, futureYears, plan, crops
);

// ほ場×年テーブル表示
console.log('\n========================================');
console.log('ほ場×年 計画表');
console.log('========================================');

// ヘッダー
const allYears = [...pastYears, ...futureYears];
const header = ['ほ場', '地区', '面積', ...allYears];
console.log(header.map(h => h.padEnd(10)).join(''));
console.log('-'.repeat(header.length * 10));

// データ行
for (const row of fieldTable) {
  const line = [
    row.field_code.padEnd(10),
    (row.district || '-').padEnd(10),
    row.area_ha.toFixed(1).padEnd(10),
    ...allYears.map(y => (row[y] || '-').padEnd(10))
  ];
  console.log(line.join(''));
}

// 年別サマリー
console.log('\n========================================');
console.log('年別 作物面積(ha)');
console.log('========================================');

const summaryHeader = ['年', ...crops];
console.log(summaryHeader.map(h => h.padEnd(12)).join(''));
console.log('-'.repeat(summaryHeader.length * 12));

for (const row of summaryTable) {
  const line = [
    row.year.padEnd(12),
    ...crops.map(c => parseFloat(row[c]).toFixed(1).padEnd(12))
  ];
  console.log(line.join(''));
}

console.log('\n========================================');
console.log('テスト完了');
console.log('========================================');
