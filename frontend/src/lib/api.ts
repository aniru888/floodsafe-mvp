import axios from 'axios';

// Use relative path so requests go through the same origin (Nginx/Vite proxy)
// This avoids CORS issues completely as the browser sees it as a same-origin request
const API_URL = '/api/v1';

console.log('FloodSafe API URL:', API_URL); // Debugging

export const api = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});
