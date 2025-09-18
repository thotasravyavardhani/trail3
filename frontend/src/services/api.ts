import axios from 'axios';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000/api';

export const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor to add auth token
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('access_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Response interceptor to handle auth errors
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('access_token');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

// Email API functions
export const emailAPI = {
  getInbox: () => api.get('/emails/inbox'),
  getSent: () => api.get('/emails/sent'),
  getOutbox: () => api.get('/emails/outbox'),
  
  composeEmail: (emailData: FormData) => api.post('/emails/compose', emailData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  }),
  
  retryOutbox: () => api.post('/emails/retry-outbox'),
};

// Settings API functions
export const settingsAPI = {
  getSettings: () => api.get('/settings'),
  updateSettings: (settings: FormData) => api.post('/settings', settings, {
    headers: { 'Content-Type': 'multipart/form-data' }
  }),
};

// Health check
export const healthAPI = {
  check: () => api.get('/health'),
};