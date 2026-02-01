/**
 * ほ場ストア（Zustand）
 */

import { create } from 'zustand';
import { fieldApi } from '../lib/api';

export const useFieldStore = create((set, get) => ({
  fields: [],
  isLoading: false,
  error: null,

  fetchFields: async () => {
    set({ isLoading: true, error: null });
    try {
      const fields = await fieldApi.list();
      set({ fields, isLoading: false });
    } catch (err) {
      set({
        error: err.response?.data?.detail || 'ほ場の取得に失敗しました',
        isLoading: false,
      });
    }
  },

  createField: async (data) => {
    try {
      const field = await fieldApi.create(data);
      set((state) => ({ fields: [...state.fields, field] }));
      return field;
    } catch (err) {
      throw new Error(err.response?.data?.detail || 'ほ場の作成に失敗しました');
    }
  },

  updateField: async (id, data) => {
    try {
      const field = await fieldApi.update(id, data);
      set((state) => ({
        fields: state.fields.map((f) => (f.id === id ? field : f)),
      }));
      return field;
    } catch (err) {
      throw new Error(err.response?.data?.detail || 'ほ場の更新に失敗しました');
    }
  },

  deleteField: async (id) => {
    try {
      await fieldApi.delete(id);
      set((state) => ({
        fields: state.fields.filter((f) => f.id !== id),
      }));
    } catch (err) {
      throw new Error(err.response?.data?.detail || 'ほ場の削除に失敗しました');
    }
  },

  getFieldWithHistory: async (id) => {
    const field = get().fields.find((f) => f.id === id);
    if (!field) return null;
    const history = await fieldApi.getHistory(id);
    return { ...field, history };
  },
}));
