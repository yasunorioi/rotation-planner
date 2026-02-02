/**
 * 共通ローディングコンポーネント
 * - スピナー + テキスト表示
 * - スケルトンローディング対応（テーブル用）
 */

import React from 'react';

/**
 * スピナーローディング
 * @param {Object} props
 * @param {string} props.text - 表示テキスト
 * @param {string} props.size - サイズ（'sm' | 'md' | 'lg'）
 */
export function Spinner({ text = '読み込み中...', size = 'md' }) {
  const sizes = {
    sm: { spinner: 20, fontSize: '0.85em' },
    md: { spinner: 32, fontSize: '1em' },
    lg: { spinner: 48, fontSize: '1.2em' },
  };

  const s = sizes[size] || sizes.md;

  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      padding: '24px',
      gap: '12px',
    }}>
      <div
        style={{
          width: s.spinner,
          height: s.spinner,
          border: '3px solid #e0e0e0',
          borderTopColor: '#4CAF50',
          borderRadius: '50%',
          animation: 'spin 1s linear infinite',
        }}
      />
      {text && (
        <span style={{ color: '#666', fontSize: s.fontSize }}>
          {text}
        </span>
      )}
      <style>{`
        @keyframes spin {
          to { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  );
}

/**
 * インラインスピナー（ボタン内など）
 */
export function InlineSpinner({ size = 16 }) {
  return (
    <span
      style={{
        display: 'inline-block',
        width: size,
        height: size,
        border: '2px solid #e0e0e0',
        borderTopColor: '#4CAF50',
        borderRadius: '50%',
        animation: 'spin 1s linear infinite',
        verticalAlign: 'middle',
        marginRight: '6px',
      }}
    />
  );
}

/**
 * スケルトンローディング（単一行）
 * @param {Object} props
 * @param {number} props.width - 幅（%またはpx）
 * @param {number} props.height - 高さ
 */
export function Skeleton({ width = '100%', height = 20 }) {
  return (
    <div
      style={{
        width: typeof width === 'number' ? `${width}px` : width,
        height,
        backgroundColor: '#e0e0e0',
        borderRadius: '4px',
        animation: 'pulse 1.5s ease-in-out infinite',
      }}
    >
      <style>{`
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.5; }
        }
      `}</style>
    </div>
  );
}

/**
 * テーブルスケルトン
 * @param {Object} props
 * @param {number} props.rows - 行数
 * @param {number} props.cols - 列数
 */
export function TableSkeleton({ rows = 5, cols = 5 }) {
  return (
    <div style={{ width: '100%' }}>
      {/* ヘッダー */}
      <div style={{ display: 'flex', gap: '8px', marginBottom: '12px', padding: '8px 0', borderBottom: '2px solid #e0e0e0' }}>
        {Array.from({ length: cols }).map((_, i) => (
          <Skeleton key={`header-${i}`} width={`${100 / cols}%`} height={16} />
        ))}
      </div>
      {/* 行 */}
      {Array.from({ length: rows }).map((_, rowIdx) => (
        <div key={`row-${rowIdx}`} style={{ display: 'flex', gap: '8px', marginBottom: '12px', padding: '8px 0' }}>
          {Array.from({ length: cols }).map((_, colIdx) => (
            <Skeleton key={`cell-${rowIdx}-${colIdx}`} width={`${100 / cols}%`} height={14} />
          ))}
        </div>
      ))}
    </div>
  );
}

/**
 * カードスケルトン
 * @param {Object} props
 * @param {number} props.count - カード数
 */
export function CardSkeleton({ count = 3 }) {
  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '16px' }}>
      {Array.from({ length: count }).map((_, i) => (
        <div
          key={i}
          style={{
            width: '280px',
            padding: '16px',
            border: '1px solid #e0e0e0',
            borderRadius: '8px',
          }}
        >
          <Skeleton width="60%" height={20} />
          <div style={{ marginTop: '12px' }}>
            <Skeleton width="100%" height={14} />
          </div>
          <div style={{ marginTop: '8px' }}>
            <Skeleton width="80%" height={14} />
          </div>
          <div style={{ marginTop: '16px', display: 'flex', gap: '8px' }}>
            <Skeleton width={60} height={28} />
            <Skeleton width={60} height={28} />
          </div>
        </div>
      ))}
    </div>
  );
}

/**
 * ページローディング（全画面）
 */
export function PageLoading({ text = 'ページを読み込み中...' }) {
  return (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      minHeight: '400px',
    }}>
      <Spinner text={text} size="lg" />
    </div>
  );
}

// デフォルトエクスポート
export default Spinner;
