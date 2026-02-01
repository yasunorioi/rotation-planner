/**
 * API クライアント
 */

import axios from 'axios';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

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
};

export default api;
