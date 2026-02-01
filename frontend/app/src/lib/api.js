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
  exportCsv: () => `${API_BASE}/api/export/fields/csv`,
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
  delete: async (id) => {
    await api.delete(`/api/plans/${id}`);
  },
  exportCsv: (id) => `${API_BASE}/api/export/plans/${id}/csv`,
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
  delete: async (id) => {
    await api.delete(`/api/pesticide-orders/${id}`);
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
};

export default api;
