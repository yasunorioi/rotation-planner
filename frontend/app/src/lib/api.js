/**
 * API クライアント
 */

import axios from 'axios';

const API_BASE = import.meta.env.VITE_API_URL || '';

const api = axios.create({
  baseURL: API_BASE,
  headers: {
    'Content-Type': 'application/json',
  },
});

// リクエストインターセプター（トークン付与）
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// レスポンスインターセプター（認証エラー処理）
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('token');
      localStorage.removeItem('user');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

// =============================================================================
// 認証付きダウンロードヘルパー
// =============================================================================

export const downloadWithAuth = async (url, filename) => {
  const token = localStorage.getItem('token');
  const response = await fetch(url, {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });
  if (!response.ok) {
    throw new Error(`Download failed: ${response.status}`);
  }
  const blob = await response.blob();
  const downloadUrl = window.URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = downloadUrl;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  window.URL.revokeObjectURL(downloadUrl);
  a.remove();
};

// =============================================================================
// ダッシュボード統計
// =============================================================================

export const dashboardApi = {
  getStats: async () => {
    const res = await api.get('/api/dashboard/stats');
    return res.data;
  },
};

// =============================================================================
// 認証
// =============================================================================

export const authApi = {
  login: async (username, password) => {
    const res = await api.post('/api/auth/login', { username, password });
    return res.data;
  },
  getMe: async () => {
    const res = await api.get('/api/auth/me');
    return res.data;
  },
};

// =============================================================================
// GPSマッチング
// =============================================================================

export const gpsApi = {
  matchField: async (lat, lon) => {
    const res = await api.post('/api/gps/match-field', { lat, lon });
    return res.data;
  },
};

// =============================================================================
// ほ場
// =============================================================================

export const fieldApi = {
  list: async () => {
    const res = await api.get('/api/fields');
    return res.data;
  },
  get: async (id) => {
    const res = await api.get(`/api/fields/${id}`);
    return res.data;
  },
  create: async (data) => {
    const res = await api.post('/api/fields', data);
    return res.data;
  },
  update: async (id, data) => {
    const res = await api.put(`/api/fields/${id}`, data);
    return res.data;
  },
  delete: async (id) => {
    await api.delete(`/api/fields/${id}`);
  },
  getHistory: async (fieldId) => {
    const res = await api.get(`/api/fields/${fieldId}/history`);
    return res.data;
  },
  addHistory: async (fieldId, year, crop) => {
    const res = await api.post(`/api/fields/${fieldId}/history`, { field_id: fieldId, year, crop });
    return res.data;
  },
  /**
   * ほ場の当年作物を輪作計画または作付履歴から取得
   * @param {number} fieldId - ほ場ID
   * @param {number} year - 年（省略時は当年）
   * @returns {Promise<{crop: string|null, source: 'plan'|'history'|null, plan_id: number|null, plan_name: string|null}>}
   */
  getCurrentCrop: async (fieldId, year = null) => {
    const params = year ? { year } : {};
    const res = await api.get(`/api/fields/${fieldId}/current-crop`, { params });
    return res.data;
  },
  exportCsv: () => `${API_BASE}/api/export/fields/csv`,
  exportKmz: () => `${API_BASE}/api/export/fields/kmz`,
  importKml: async (formData) => {
    const res = await api.post('/api/fields/import-kml', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return res.data;
  },
  previewKml: async (formData) => {
    const res = await api.post('/api/fields/preview-kml', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return res.data;
  },
  getDistricts: async () => {
    const res = await api.get('/api/fields/districts');
    return res.data.districts;
  },
};

// =============================================================================
// 筆ポリゴン
// =============================================================================

export const fudePolygonApi = {
  /**
   * 指定範囲内の筆ポリゴンを取得
   * @param {Object} bounds - {min_lat, min_lng, max_lat, max_lng}
   * @param {number} maxResults - 最大取得件数
   */
  getByBounds: async (bounds, maxResults = 200) => {
    const params = {
      min_lat: bounds.min_lat,
      min_lng: bounds.min_lng,
      max_lat: bounds.max_lat,
      max_lng: bounds.max_lng,
      max_results: maxResults,
    };
    const res = await api.get('/api/fude-polygon/geojson', { params });
    return res.data;
  },
};

// =============================================================================
// 輪作計画
// =============================================================================

export const planApi = {
  list: async () => {
    const res = await api.get('/api/plans');
    return res.data;
  },
  get: async (id) => {
    const res = await api.get(`/api/plans/${id}`);
    return res.data;
  },
  create: async (data) => {
    const res = await api.post('/api/plans', data);
    return res.data;
  },
  update: async (id, data) => {
    const res = await api.put(`/api/plans/${id}`, data);
    return res.data;
  },
  delete: async (id) => {
    await api.delete(`/api/plans/${id}`);
  },
  exportCsv: (id) => `${API_BASE}/api/export/plans/${id}/csv`,
  /**
   * 輪作計画を作付履歴に反映
   * @param {number} id - 計画ID
   * @returns {Promise<{success: boolean, applied_count: number, message: string}>}
   */
  applyToHistory: async (id) => {
    const res = await api.post(`/api/plans/${id}/apply-to-history`, { confirm_overwrite: true });
    return res.data;
  },
};

// =============================================================================
// 制約設定
// =============================================================================

export const constraintApi = {
  get: async () => {
    const res = await api.get('/api/constraints');
    return res.data;
  },
  update: async (data) => {
    const res = await api.put('/api/constraints', data);
    return res.data;
  },
};

// =============================================================================
// 作物
// =============================================================================

export const cropApi = {
  list: async () => {
    const res = await api.get('/api/crops');
    return res.data;
  },
  listUserCrops: async () => {
    const res = await api.get('/api/user-crops');
    return res.data;
  },
  updateUserCrops: async (cropIds) => {
    const res = await api.put('/api/user-crops', { crop_ids: cropIds });
    return res.data;
  },
  setCustomName: async (cropId, customName) => {
    const res = await api.put('/api/user-crops/custom-name', { crop_id: cropId, custom_name: customName });
    return res.data;
  },
  addCustomCrop: async (parentCropId, customName) => {
    const res = await api.post('/api/user-crops/custom', {
      parent_crop_id: parentCropId,
      custom_name: customName,
    });
    return res.data;
  },
  deleteCustomCrop: async (userCropId) => {
    await api.delete(`/api/user-crops/${userCropId}`);
  },
  /**
   * FAMIC登録適用情報から作物名を検索
   * @param {string} keyword - 検索キーワード（部分一致）
   * @param {number} limit - 最大件数（デフォルト50）
   * @returns {Promise<string[]>} 作物名の配列
   */
  searchFamicCrops: async (keyword = null, limit = 50) => {
    const params = { limit };
    if (keyword) params.q = keyword;
    const res = await api.get('/api/famic/crops', { params });
    return res.data;
  },
  /**
   * FAMIC作物名をマスタ作物として追加（管理者のみ）
   * @param {string} name - 作物名
   * @returns {Promise<{status: string, id: number, name: string}>}
   */
  addCropFromFamic: async (name) => {
    const res = await api.post('/api/crops/from-famic', null, { params: { name } });
    return res.data;
  },
};

// =============================================================================
// 農薬マスタ
// =============================================================================

export const pesticideMasterApi = {
  list: async (crop = null) => {
    const params = crop ? { crop } : {};
    const res = await api.get('/api/pesticide-masters', { params });
    return res.data;
  },
  create: async (data) => {
    const res = await api.post('/api/pesticide-masters', data);
    return res.data;
  },
  update: async (id, data) => {
    const res = await api.put(`/api/pesticide-masters/${id}`, data);
    return res.data;
  },
  delete: async (id) => {
    await api.delete(`/api/pesticide-masters/${id}`);
  },
  getDilutionRates: async (name) => {
    const res = await api.get(`/api/pesticide-masters/by-name/${encodeURIComponent(name)}/dilution-rates`);
    return res.data;
  },
  /**
   * CSVファイルから防除マスタを一括インポート
   * @param {FormData} formData - CSVファイルを含むFormData
   * @returns {Promise<{imported: number, skipped: number, errors: string[]}>}
   */
  importCsv: async (formData) => {
    const res = await api.post('/api/pesticide-masters/import-csv', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return res.data;
  },
};

// =============================================================================
// 農薬発注
// =============================================================================

export const pesticideOrderApi = {
  list: async (year = null) => {
    const params = year ? { year } : {};
    const res = await api.get('/api/pesticide-orders', { params });
    return res.data;
  },
  get: async (id) => {
    const res = await api.get(`/api/pesticide-orders/${id}`);
    return res.data;
  },
  create: async (data) => {
    const res = await api.post('/api/pesticide-orders', data);
    return res.data;
  },
  update: async (id, data) => {
    const res = await api.put(`/api/pesticide-orders/${id}`, data);
    return res.data;
  },
  delete: async (id) => {
    await api.delete(`/api/pesticide-orders/${id}`);
  },
  calculateFromPlan: async (planId, year) => {
    const res = await api.post('/api/pesticide-orders/calculate-from-plan', {
      plan_id: planId,
      year: year,
    });
    return res.data;
  },
  exportCsv: (year = null) => {
    const params = year ? `?year=${year}` : '';
    return `${api.defaults.baseURL}/api/pesticide-orders/export/csv${params}`;
  },
  exportPdf: (year = null) => {
    const params = year ? `?year=${year}` : '';
    return `${api.defaults.baseURL}/api/pesticide-orders/export/pdf${params}`;
  },
};

// =============================================================================
// 防除記録
// =============================================================================

export const pesticideRecordApi = {
  list: async (year = null, fieldId = null) => {
    const params = {};
    if (year) params.year = year;
    if (fieldId) params.field_id = fieldId;
    const res = await api.get('/api/pesticide-records', { params });
    return res.data;
  },
  get: async (id) => {
    const res = await api.get(`/api/pesticide-records/${id}`);
    return res.data;
  },
  create: async (data) => {
    const res = await api.post('/api/pesticide-records', data);
    return res.data;
  },
  update: async (id, data) => {
    const res = await api.put(`/api/pesticide-records/${id}`, data);
    return res.data;
  },
  delete: async (id) => {
    await api.delete(`/api/pesticide-records/${id}`);
  },
  exportCsv: (year = null) => `${API_BASE}/api/pesticide-records/export/csv${year ? `?year=${year}` : ''}`,
  /**
   * 画像から農薬名を解析（Claude Vision API）
   * @param {File} imageFile - 画像ファイル
   * @returns {Promise<{pesticide_name: string|null, confidence: number|null, raw_text: string|null, error: string|null}>}
   */
  analyzeImage: async (imageFile) => {
    const formData = new FormData();
    formData.append('image', imageFile);
    const res = await api.post('/api/pesticide-records/analyze-image', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return res.data;
  },
  // 画像保存・取得
  uploadImage: async (recordId, imageFile) => {
    const formData = new FormData();
    formData.append('image', imageFile);
    const res = await api.post(`/api/pesticide-records/${recordId}/images`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return res.data;
  },
  listImages: async (recordId) => {
    const res = await api.get(`/api/pesticide-records/${recordId}/images`);
    return res.data;
  },
  deleteImage: async (recordId, imageId) => {
    await api.delete(`/api/pesticide-records/${recordId}/images/${imageId}`);
  },
  getImageUrl: (recordId, imageId) => `${API_BASE}/api/pesticide-records/${recordId}/images/${imageId}`,
};

// =============================================================================
// JA集計 (管理者用)
// =============================================================================

export const jaApi = {
  listFarmers: async () => {
    const res = await api.get('/api/ja/farmers');
    return res.data;
  },
  getFarmerFields: async (farmerId) => {
    const res = await api.get(`/api/ja/farmers/${farmerId}/fields`);
    return res.data;
  },
  getFarmerPlans: async (farmerId) => {
    const res = await api.get(`/api/ja/farmers/${farmerId}/plans`);
    return res.data;
  },
  aggregatePesticideOrders: async (year) => {
    const res = await api.get('/api/ja/aggregate/pesticide-orders', { params: { year } });
    return res.data;
  },
  aggregateDetail: async (year, groupBy = 'farmer') => {
    const res = await api.get('/api/ja/aggregate/pesticide-orders/detail', {
      params: { year, group_by: groupBy },
    });
    return res.data;
  },
};

// =============================================================================
// 輪作計画最適化 (OR-Tools)
// =============================================================================

export const rotationApi = {
  optimize: async (data) => {
    const res = await api.post('/api/rotation/optimize', data);
    return res.data;
  },
  importCsv: async (planName, csvData) => {
    const res = await api.post('/api/rotation/import-csv', {
      plan_name: planName,
      csv_data: csvData,
    });
    return res.data;
  },
};

// =============================================================================
// ユーザー管理 (管理者用)
// =============================================================================

export const adminApi = {
  listUsers: async () => {
    const res = await api.get('/api/admin/users');
    return res.data;
  },
  createUser: async (data) => {
    const res = await api.post('/api/admin/users', data);
    return res.data;
  },
  updateUser: async (username, data) => {
    const res = await api.put(`/api/admin/users/${username}`, data);
    return res.data;
  },
  deleteUser: async (username) => {
    await api.delete(`/api/admin/users/${username}`);
  },
  downloadBackup: async () => {
    const token = localStorage.getItem('token');
    const response = await fetch(`${API_BASE}/api/admin/backup`, {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    });
    if (!response.ok) {
      throw new Error('Backup download failed');
    }
    const blob = await response.blob();
    const contentDisposition = response.headers.get('Content-Disposition');
    let filename = 'rotation_planner_backup.db';
    if (contentDisposition) {
      const match = contentDisposition.match(/filename="?([^"]+)"?/);
      if (match) filename = match[1];
    }
    return { blob, filename };
  },
  getSystemInfo: async () => {
    const res = await api.get('/api/admin/system-info');
    return res.data;
  },
  // デバッグモード
  getDebugMode: async () => {
    const res = await api.get('/api/admin/settings/debug');
    return res.data;
  },
  setDebugMode: async (enabled) => {
    const res = await api.put('/api/admin/settings/debug', { enabled });
    return res.data;
  },
  // 筆ポリゴン
  listFudePolygons: async () => {
    const res = await api.get('/api/admin/fude-polygon');
    return res.data;
  },
  uploadFudePolygon: async (file) => {
    const formData = new FormData();
    formData.append('file', file);
    const res = await api.post('/api/admin/fude-polygon', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return res.data;
  },
  deleteFudePolygon: async (filename) => {
    await api.delete(`/api/admin/fude-polygon/${encodeURIComponent(filename)}`);
  },
  // FAMIC
  getFamicStatus: async () => {
    const res = await api.get('/api/admin/famic/status');
    return res.data;
  },
  updateFamic: async () => {
    const res = await api.post('/api/admin/famic/update');
    return res.data;
  },
  setFamicAutoUpdate: async (enabled) => {
    const res = await api.put('/api/admin/famic/auto-update', null, { params: { enabled } });
    return res.data;
  },
  acceptFamicTerms: async () => {
    const res = await api.post('/api/admin/famic/accept-terms');
    return res.data;
  },
};

// =============================================================================
// 在庫管理
// =============================================================================

export const inventoryApi = {
  /**
   * 在庫一覧取得
   * @param {Object} params - { search, sort_by, sort_order, page, per_page }
   */
  list: async (params = {}) => {
    const res = await api.get('/api/inventory', { params });
    return res.data;
  },
  /**
   * 農薬名で在庫情報を取得
   * @param {string} pesticideName - 農薬名
   */
  getByPesticide: async (pesticideName) => {
    const res = await api.get('/api/inventory/by-pesticide', { params: { pesticide_name: pesticideName } });
    return res.data;
  },
  /**
   * 在庫詳細取得
   */
  get: async (id) => {
    const res = await api.get(`/api/inventory/${id}`);
    return res.data;
  },
  /**
   * 在庫新規登録
   */
  create: async (data) => {
    const res = await api.post('/api/inventory', data);
    return res.data;
  },
  /**
   * 在庫更新
   */
  update: async (id, data) => {
    const res = await api.put(`/api/inventory/${id}`, data);
    return res.data;
  },
  /**
   * 在庫削除
   */
  delete: async (id) => {
    await api.delete(`/api/inventory/${id}`);
  },
  /**
   * CSVインポート
   * @param {File} file - CSVファイル
   */
  importCsv: async (file) => {
    const formData = new FormData();
    formData.append('file', file);
    const res = await api.post('/api/inventory/import-csv', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return res.data;
  },
  /**
   * CSVエクスポートURL
   */
  exportCsv: () => `${API_BASE}/api/inventory/export-csv`,
  /**
   * 在庫履歴（入出庫記録）取得
   * @param {Object} params - { inventory_id, type, start_date, end_date }
   */
  getTransactions: async (params = {}) => {
    const res = await api.get('/api/inventory/transactions', { params });
    return res.data;
  },
};

export default api;
