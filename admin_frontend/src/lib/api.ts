import axios from 'axios';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

const api = axios.create({
  baseURL: API_URL,
});

// Добавляем перехватчик для вставки API ключа
api.interceptors.request.use((config) => {
  const token = typeof window !== 'undefined' ? localStorage.getItem('admin_api_key') : '';
  if (token) {
    config.headers['X-API-Key'] = token;
  }
  return config;
});

export default api;
