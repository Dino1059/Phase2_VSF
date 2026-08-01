import axios from 'axios';
import {
  ProfileReport,
  RuleSchema,
  ProposeRulesResponse,
  ExecuteTransformResponse,
  AuditRecord,
  UserRole,
} from '../types';

let currentRole: UserRole = 'Admin';

export const setCurrentApiRole = (role: UserRole) => {
  currentRole = role;
};

const apiClient = axios.create({
  baseURL: '/api',
  headers: {
    'Content-Type': 'application/json',
  },
});

apiClient.interceptors.request.use((config) => {
  config.headers['X-User-Role'] = currentRole;
  return config;
});

export const apiService = {
  async profileDataset(data: Record<string, any>[]): Promise<ProfileReport> {
    try {
      const response = await apiClient.post<ProfileReport>('/profile', { data });
      return response.data;
    } catch (err) {
      console.error('API /profile failed:', err);
      throw err;
    }
  },

  async proposeRules(data: Record<string, any>[], variant: string = 'A1'): Promise<ProposeRulesResponse> {
    try {
      const response = await apiClient.post<ProposeRulesResponse>('/rules/propose', { data, variant });
      return response.data;
    } catch (err) {
      console.error('API /rules/propose failed:', err);
      throw err;
    }
  },

  async executeTransform(data: Record<string, any>[], rules: RuleSchema[]): Promise<ExecuteTransformResponse> {
    try {
      const response = await apiClient.post<ExecuteTransformResponse>('/transform/execute', { data, rules });
      return response.data;
    } catch (err) {
      console.error('API /transform/execute failed:', err);
      throw err;
    }
  },

  async getAuditStore(): Promise<AuditRecord[]> {
    try {
      const response = await apiClient.get<AuditRecord[]>('/audit/store');
      return response.data;
    } catch (err) {
      console.error('API /audit/store failed:', err);
      throw err;
    }
  },

  async resetSystem(): Promise<{ status: string; message: string; reset_time_sec: number }> {
    try {
      const response = await apiClient.post('/reset');
      return response.data;
    } catch (err) {
      console.error('API /reset failed:', err);
      throw err;
    }
  },

  // Schedules
  async createSchedule(data: any): Promise<any> {
    const response = await apiClient.post('/v1/schedules', data);
    return response.data;
  },

  async getSchedules(): Promise<any> {
    const response = await apiClient.get('/v1/schedules');
    return response.data;
  },

  async deleteSchedule(id: string): Promise<any> {
    const response = await apiClient.delete(`/v1/schedules/${id}`);
    return response.data;
  },

  // Anomaly Detection
  async detectAnomalies(data: any): Promise<any> {
    const response = await apiClient.post('/v1/anomalies/detect', data);
    return response.data;
  },

  // Alerts
  async getAlerts(severity?: string): Promise<any> {
    const response = await apiClient.get('/v1/alerts', {
      params: severity ? { severity } : undefined,
    });
    return response.data;
  },

  async createAlert(data: any): Promise<any> {
    const response = await apiClient.post('/v1/alerts', data);
    return response.data;
  },

  async acknowledgeAlert(id: string): Promise<any> {
    const response = await apiClient.post(`/v1/alerts/${id}/acknowledge`);
    return response.data;
  },

  async resolveAlert(id: string): Promise<any> {
    const response = await apiClient.post(`/v1/alerts/${id}/resolve`);
    return response.data;
  },

  async dispatchWebhook(data: any): Promise<any> {
    const response = await apiClient.post('/v1/alerts/dispatch-webhook', data);
    return response.data;
  },
};
