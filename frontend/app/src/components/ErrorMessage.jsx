/**
 * 共通エラーメッセージコンポーネント
 * - エラータイプ別の表示（error/warning/info）
 * - リトライボタン付き
 * - API エラーのユーザーフレンドリーな変換
 */

import React from 'react';

/**
 * HTTPステータスコードをユーザーフレンドリーなメッセージに変換
 * @param {number} status - HTTPステータスコード
 * @returns {string} ユーザーフレンドリーなメッセージ
 */
export function getErrorMessage(status) {
  const messages = {
    400: '入力内容に問題があります',
    401: 'ログインが必要です',
    403: '権限がありません',
    404: 'データが見つかりません',
    409: 'データが競合しています',
    422: '入力内容を確認してください',
    429: 'リクエストが多すぎます。しばらく待ってから再試行してください',
    500: 'サーバーエラーが発生しました',
    502: 'サーバーに接続できません',
    503: 'サービスが一時的に利用できません',
    504: 'サーバーの応答がタイムアウトしました',
  };
  return messages[status] || 'エラーが発生しました';
}

/**
 * APIエラーオブジェクトからメッセージを抽出
 * @param {Error} error - エラーオブジェクト
 * @returns {string} エラーメッセージ
 */
export function parseApiError(error) {
  // Axiosエラー
  if (error.response) {
    const status = error.response.status;
    const data = error.response.data;

    // サーバーからの詳細メッセージがある場合
    if (data?.detail) {
      return data.detail;
    }
    if (data?.message) {
      return data.message;
    }

    return getErrorMessage(status);
  }

  // ネットワークエラー
  if (error.request) {
    return 'ネットワークエラーが発生しました。接続を確認してください';
  }

  // その他のエラー
  return error.message || 'エラーが発生しました';
}

/**
 * エラーメッセージコンポーネント
 * @param {Object} props
 * @param {string} props.message - 表示メッセージ
 * @param {string} props.type - タイプ（'error' | 'warning' | 'info'）
 * @param {Function} props.onRetry - リトライコールバック
 * @param {Function} props.onDismiss - 閉じるコールバック
 * @param {string} props.title - タイトル（オプション）
 */
export function ErrorMessage({
  message,
  type = 'error',
  onRetry,
  onDismiss,
  title,
}) {
  const styles = {
    error: {
      background: '#f8d7da',
      border: '1px solid #f5c6cb',
      color: '#721c24',
      icon: '❌',
      defaultTitle: 'エラー',
    },
    warning: {
      background: '#fff3cd',
      border: '1px solid #ffeeba',
      color: '#856404',
      icon: '⚠️',
      defaultTitle: '警告',
    },
    info: {
      background: '#d1ecf1',
      border: '1px solid #bee5eb',
      color: '#0c5460',
      icon: 'ℹ️',
      defaultTitle: 'お知らせ',
    },
  };

  const style = styles[type] || styles.error;

  return (
    <div
      style={{
        padding: '12px 16px',
        borderRadius: '6px',
        marginBottom: '16px',
        background: style.background,
        border: style.border,
        color: style.color,
      }}
    >
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: '12px' }}>
        <span style={{ fontSize: '1.2em' }}>{style.icon}</span>
        <div style={{ flex: 1 }}>
          {title && (
            <div style={{ fontWeight: 'bold', marginBottom: '4px' }}>
              {title}
            </div>
          )}
          <div>{message}</div>
          {(onRetry || onDismiss) && (
            <div style={{ marginTop: '12px', display: 'flex', gap: '8px' }}>
              {onRetry && (
                <button
                  onClick={onRetry}
                  style={{
                    padding: '6px 12px',
                    background: style.color,
                    color: 'white',
                    border: 'none',
                    borderRadius: '4px',
                    cursor: 'pointer',
                    fontSize: '0.9em',
                  }}
                >
                  再試行
                </button>
              )}
              {onDismiss && (
                <button
                  onClick={onDismiss}
                  style={{
                    padding: '6px 12px',
                    background: 'transparent',
                    color: style.color,
                    border: `1px solid ${style.color}`,
                    borderRadius: '4px',
                    cursor: 'pointer',
                    fontSize: '0.9em',
                  }}
                >
                  閉じる
                </button>
              )}
            </div>
          )}
        </div>
        {onDismiss && !onRetry && (
          <button
            onClick={onDismiss}
            style={{
              background: 'transparent',
              border: 'none',
              color: style.color,
              cursor: 'pointer',
              fontSize: '1.2em',
              padding: '0',
              lineHeight: 1,
            }}
            aria-label="閉じる"
          >
            ×
          </button>
        )}
      </div>
    </div>
  );
}

/**
 * インラインエラー（フォームフィールド用）
 * @param {Object} props
 * @param {string} props.message - エラーメッセージ
 */
export function InlineError({ message }) {
  if (!message) return null;

  return (
    <span style={{
      display: 'block',
      color: '#dc3545',
      fontSize: '0.85em',
      marginTop: '4px',
    }}>
      {message}
    </span>
  );
}

/**
 * 空状態コンポーネント
 * @param {Object} props
 * @param {string} props.message - 表示メッセージ
 * @param {string} props.icon - アイコン
 * @param {Function} props.onAction - アクションコールバック
 * @param {string} props.actionLabel - アクションボタンラベル
 */
export function EmptyState({
  message = 'データがありません',
  icon = '📭',
  onAction,
  actionLabel = '作成',
}) {
  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      padding: '48px 24px',
      color: '#666',
    }}>
      <span style={{ fontSize: '3em', marginBottom: '16px' }}>{icon}</span>
      <p style={{ margin: 0, fontSize: '1.1em' }}>{message}</p>
      {onAction && (
        <button
          onClick={onAction}
          style={{
            marginTop: '16px',
            padding: '8px 20px',
            background: '#4CAF50',
            color: 'white',
            border: 'none',
            borderRadius: '4px',
            cursor: 'pointer',
          }}
        >
          {actionLabel}
        </button>
      )}
    </div>
  );
}

/**
 * APIエラー用ラッパーコンポーネント
 * @param {Object} props
 * @param {Error} props.error - APIエラーオブジェクト
 * @param {Function} props.onRetry - リトライコールバック
 */
export function ApiError({ error, onRetry }) {
  const message = parseApiError(error);
  const status = error?.response?.status;

  // 401の場合はログイン画面にリダイレクトされるため表示しない
  if (status === 401) {
    return null;
  }

  return (
    <ErrorMessage
      message={message}
      type={status >= 500 ? 'error' : 'warning'}
      onRetry={onRetry}
    />
  );
}

// デフォルトエクスポート
export default ErrorMessage;
