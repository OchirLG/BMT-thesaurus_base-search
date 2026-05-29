// api.js
import axios from 'axios';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 300000,
});

export const searchMedical = async (query, threshold = 0.8) => {
  try {
    const response = await api.post('/api/search', 
      { query },                      // тело запроса
      { params: { threshold } }       // query-параметр threshold
    );
    return response.data;
  } catch (error) {
    if (error.response) {
      throw new Error(error.response.data?.detail || 'Ошибка сервера');
    } else if (error.request) {
      throw new Error('Нет ответа от сервера. Проверьте соединение.');
    } else {
      throw new Error(error.message || 'Произошла ошибка');
    }
  }
};

export const healthCheck = async () => {
  try {
    const response = await api.get('/');
    return response.data;
  } catch (error) {
    console.error('Health check error:', error);
    throw error;
  }
};

export default api;