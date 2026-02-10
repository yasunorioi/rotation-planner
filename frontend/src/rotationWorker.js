/**
 * 輪作計画ソルバー Web Worker
 *
 * メインスレッドをブロックせずに輪作計画を計算する。
 * postMessage で入力を受け取り、結果を返す。
 *
 * @version 1.0.0
 */

// ソルバーをインポート（同じディレクトリにある想定）
importScripts('./rotationSolver.js');

/**
 * メッセージハンドラ
 *
 * 入力形式:
 * {
 *   type: 'solve',
 *   data: {
 *     fields: Field[],
 *     pastYears: string[],
 *     futureYears: string[],
 *     crops: string[],
 *     constraints: Constraints,
 *     options: { maxIterations?: number }
 *   }
 * }
 *
 * 出力形式:
 * {
 *   type: 'result',
 *   data: {
 *     plan: Object,
 *     score: number,
 *     errors: string[],
 *     fieldTable: Array,
 *     summaryTable: Array,
 *     elapsedMs: number
 *   }
 * }
 *
 * エラー時:
 * {
 *   type: 'error',
 *   message: string
 * }
 *
 * 進捗通知:
 * {
 *   type: 'progress',
 *   phase: string,
 *   progress: number (0-100)
 * }
 */
self.onmessage = function(e) {
  const { type, data } = e.data;

  if (type === 'solve') {
    try {
      const startTime = performance.now();

      // 進捗通知: 開始
      self.postMessage({
        type: 'progress',
        phase: '初期化',
        progress: 0
      });

      const {
        fields,
        pastYears,
        futureYears,
        crops,
        constraints,
        options = {}
      } = data;

      // 入力検証
      if (!fields || fields.length === 0) {
        throw new Error('ほ場データがありません');
      }
      if (!crops || crops.length === 0) {
        throw new Error('作物リストがありません');
      }
      if (!futureYears || futureYears.length === 0) {
        throw new Error('将来年が指定されていません');
      }

      // 進捗通知: ソルバー初期化
      self.postMessage({
        type: 'progress',
        phase: 'ソルバー初期化',
        progress: 10
      });

      // ソルバー作成
      const solver = new RotationSolver(
        fields,
        pastYears || [],
        futureYears,
        crops,
        constraints || createDefaultConstraints()
      );

      // 進捗通知: 計算中
      self.postMessage({
        type: 'progress',
        phase: '最適化計算中',
        progress: 20
      });

      // 最適化実行
      const { plan, score, errors } = solver.solve(options);

      // 進捗通知: 結果生成
      self.postMessage({
        type: 'progress',
        phase: '結果生成中',
        progress: 80
      });

      // 結果テーブル生成
      const { fieldTable, summaryTable } = generateResultTables(
        fields,
        pastYears || [],
        futureYears,
        plan,
        crops
      );

      const elapsedMs = performance.now() - startTime;

      // 進捗通知: 完了
      self.postMessage({
        type: 'progress',
        phase: '完了',
        progress: 100
      });

      // 結果を返す
      self.postMessage({
        type: 'result',
        data: {
          plan,
          score,
          errors,
          fieldTable,
          summaryTable,
          elapsedMs: Math.round(elapsedMs)
        }
      });

    } catch (error) {
      self.postMessage({
        type: 'error',
        message: error.message || '不明なエラーが発生しました'
      });
    }
  }
};

// Worker 準備完了を通知
self.postMessage({ type: 'ready' });
