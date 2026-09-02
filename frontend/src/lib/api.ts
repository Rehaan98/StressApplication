import axios, { AxiosError } from 'axios';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: { 'Content-Type': 'application/json' },
  timeout: 30000,
});

// Attach bearer token from localStorage on every request
apiClient.interceptors.request.use((config) => {
  if (typeof window !== 'undefined') {
    const token = localStorage.getItem('token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
  }
  return config;
});

// On 401, clear token (session expired)
apiClient.interceptors.response.use(
  (res) => res,
  (err: AxiosError) => {
    if (err.response?.status === 401 && typeof window !== 'undefined') {
      localStorage.removeItem('token');
    }
    return Promise.reject(err);
  }
);

// ─── Type Definitions ────────────────────────────────────────────────────────

export interface AssessmentData {
  pss_q1: number; pss_q2: number; pss_q3: number; pss_q4: number; pss_q5: number;
  pss_q6: number; pss_q7: number; pss_q8: number; pss_q9: number; pss_q10: number;
  heart_rate: number; hrv_sdnn: number; sleep_hours: number; sleep_efficiency: number;
  physical_activity_min: number; work_hours: number; screen_time_hours: number;
  breaks_per_day: number; sentiment_score: number; anxiety_score: number;
  notes?: string;
}

export interface UserResponse {
  id: string;
  email: string;
  full_name: string;
  role: string;
  is_active: boolean;
  is_verified: boolean;
  avatar_url?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  user: UserResponse;
}

// ─── API Methods ─────────────────────────────────────────────────────────────

export const api = {
  // Auth
  login: async (email: string, password: string): Promise<TokenResponse> => {
    const res = await apiClient.post('/auth/login', { email, password });
    return res.data;
  },

  register: async (email: string, full_name: string, password: string): Promise<TokenResponse> => {
    const res = await apiClient.post('/auth/register', { email, full_name, password });
    return res.data;
  },

  getMe: async (): Promise<UserResponse> => {
    const res = await apiClient.get('/auth/me');
    return res.data;
  },

  // Profile
  updateProfile: async (data: { full_name?: string; avatar_url?: string }): Promise<UserResponse> => {
    const res = await apiClient.put('/users/me', data);
    return res.data;
  },

  changePassword: async (current_password: string, new_password: string) => {
    const res = await apiClient.post('/users/me/password', { current_password, new_password });
    return res.data;
  },

  // Assessments
  createAssessment: async (data: AssessmentData) => {
    const res = await apiClient.post('/assessments/', data);
    return res.data;
  },

  listAssessments: async () => {
    const res = await apiClient.get('/assessments/');
    return res.data;
  },

  getAssessment: async (id: string) => {
    const res = await apiClient.get(`/assessments/${id}`);
    return res.data;
  },

  // Predictions
  runPrediction: async (assessment_id: string) => {
    const res = await apiClient.post('/predictions/', { assessment_id });
    return res.data;
  },

  listPredictions: async (limit = 10) => {
    const res = await apiClient.get(`/predictions/?limit=${limit}`);
    return res.data;
  },

  getPrediction: async (id: string) => {
    const res = await apiClient.get(`/predictions/${id}`);
    return res.data;
  },

  // XAI
  getExplainability: async (prediction_id: string) => {
    const res = await apiClient.get(`/explainability/${prediction_id}`);
    return res.data;
  },

  // RAG
  queryRAG: async (prediction_id?: string, query_text?: string, top_k = 3, emotion?: string) => {
    const res = await apiClient.post('/rag/', { prediction_id, query_text, top_k, emotion });
    return res.data;
  },

  // Facial Expression Analysis
  analyzeFacial: async (image: string, source = 'webcam') => {
    const res = await apiClient.post('/facial/analyze', { image, source });
    return res.data;
  },

  getFacialHistory: async (limit = 100) => {
    const res = await apiClient.get(`/facial/history?limit=${limit}`);
    return res.data;
  },

  // Analytics
  getUserAnalytics: async () => {
    const res = await apiClient.get('/analytics/user');
    return res.data;
  },

  getAdminAnalytics: async () => {
    const res = await apiClient.get('/analytics/admin');
    return res.data;
  },

  // Admin
  adminListUsers: async (skip = 0, limit = 100) => {
    const res = await apiClient.get(`/admin/users?skip=${skip}&limit=${limit}`);
    return res.data;
  },

  // Reports
  downloadCSVReport: async (): Promise<Blob> => {
    const res = await apiClient.get('/reports/csv', { responseType: 'blob' });
    return res.data;
  },
};
