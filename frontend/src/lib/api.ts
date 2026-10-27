import axios, { AxiosError } from 'axios';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';
export { API_BASE_URL };

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

  // Natural conversation bot (text + voice; stress detection stays separate)
  conversationStart: async (user_name?: string) => {
    const res = await apiClient.post('/conversation/start', { user_name });
    return res.data;
  },

  conversationMessage: async (args: {
    session_id: string; message: string;
    stress_context?: {
      stress_score?: number; stress_level?: string; confidence?: number;
      trend?: string; voice_indicators?: Record<string, unknown>; webcam_indicators?: Record<string, unknown>;
    };
    use_llm?: boolean;
  }) => {
    const res = await apiClient.post('/conversation/message', {
      session_id: args.session_id,
      message: args.message,
      ...(args.stress_context ? { stress_context: args.stress_context } : {}),
      ...(args.use_llm !== undefined ? { use_llm: args.use_llm } : {}),
    });
    return res.data;
  },

  conversationHistory: async (session_id: string) => {
    const res = await apiClient.get(`/conversation/${session_id}`);
    return res.data;
  },

  conversationEnd: async (session_id: string) => {
    const res = await apiClient.delete(`/conversation/${session_id}`);
    return res.data;
  },

  // Unified multimodal assessment (questionnaire + voice + facial → one result)
  multimodalAssess: async (args: {
    assessment_id?: string; voice_audio_base64?: string; voice_transcript?: string;
    facial_image?: string; facial_reading_id?: string;
  }) => {
    const res = await apiClient.post('/multimodal/assess', {
      ...(args.assessment_id ? { assessment_id: args.assessment_id } : {}),
      ...(args.voice_audio_base64 ? { voice_audio_base64: args.voice_audio_base64 } : {}),
      ...(args.voice_transcript ? { voice_transcript: args.voice_transcript } : {}),
      ...(args.facial_image ? { facial_image: args.facial_image } : {}),
      ...(args.facial_reading_id ? { facial_reading_id: args.facial_reading_id } : {}),
    });
    return res.data;
  },

  multimodalHistory: async (limit = 10) => {
    const res = await apiClient.get(`/multimodal/?limit=${limit}`);
    return res.data;
  },

  multimodalGet: async (id: string) => {
    const res = await apiClient.get(`/multimodal/${id}`);
    return res.data;
  },

  // Synchronized assessment sessions (voice + face + questionnaire in parallel)
  mmSessionStart: async () => {
    const res = await apiClient.post('/multimodal/sessions', {});
    return res.data;
  },

  mmSessionState: async (session_id: string) => {
    const res = await apiClient.get(`/multimodal/sessions/${session_id}`);
    return res.data;
  },

  mmSessionVoice: async (session_id: string, args: { audio_base64?: string; transcript?: string }) => {
    const res = await apiClient.post(`/multimodal/sessions/${session_id}/voice`, {
      ...(args.audio_base64 ? { audio_base64: args.audio_base64 } : {}),
      ...(args.transcript ? { transcript: args.transcript } : {}),
    });
    return res.data;
  },

  mmSessionFace: async (session_id: string, args: { image_base64?: string; reading_id?: string }) => {
    const res = await apiClient.post(`/multimodal/sessions/${session_id}/face`, {
      ...(args.image_base64 ? { image_base64: args.image_base64 } : {}),
      ...(args.reading_id ? { reading_id: args.reading_id } : {}),
    });
    return res.data;
  },

  mmSessionQuestionnaire: async (session_id: string, assessment_id: string) => {
    const res = await apiClient.post(`/multimodal/sessions/${session_id}/questionnaire`, { assessment_id });
    return res.data;
  },

  mmSessionLive: async (session_id: string) => {
    const res = await apiClient.get(`/multimodal/sessions/${session_id}/live`);
    return res.data;
  },

  mmSessionFinalize: async (session_id: string) => {
    const res = await apiClient.post(`/multimodal/sessions/${session_id}/finalize`, {});
    return res.data;
  },

  mmSessionCancel: async (session_id: string) => {
    const res = await apiClient.delete(`/multimodal/sessions/${session_id}`);
    return res.data;
  },

  // Server-side speech-to-text fallback (multipart upload; keys stay server-side)
  transcribeStatus: async () => {
    const res = await apiClient.get('/voice/transcribe/status');
    return res.data as { provider: string; configured: boolean; max_mb: number; note: string };
  },

  transcribeVoice: async (blob: Blob): Promise<{
    transcript: string; provider: string; duration_seconds: number; warning?: string;
  }> => {
    const token = typeof window !== 'undefined' ? localStorage.getItem('token') : null;
    const form = new FormData();
    const ext = blob.type.includes('mp4') ? 'm4a'
      : blob.type.includes('ogg') ? 'ogg'
      : blob.type.includes('wav') ? 'wav' : 'webm';
    form.append('audio', blob, `voice.${ext}`);
    // fetch (not axios): lets the browser set the multipart boundary itself.
    const res = await fetch(`${API_BASE_URL}/voice/transcribe`, {
      method: 'POST',
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      body: form,
    });
    if (!res.ok) {
      let detail = '';
      try { detail = (await res.json())?.detail || ''; } catch { /* ignore */ }
      const err: any = new Error(detail || `Transcription failed (HTTP ${res.status})`);
      err.status = res.status;
      throw err;
    }
    return res.json();
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

  // Voice Analysis
  analyzeVoice: async (audioBase64: string, sampleRate = 16000, duration?: number, transcript?: string, sessionId?: string) => {
    const res = await apiClient.post('/voice/analyze', {
      audio_base64: audioBase64,
      sample_rate: sampleRate,
      ...(duration !== undefined ? { duration: Math.min(Math.max(duration, 0.1), 180) } : {}),
      ...(transcript ? { transcript } : {}),
      ...(sessionId ? { session_id: sessionId } : {}),
    });
    return res.data;
  },
};
