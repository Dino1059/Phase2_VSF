const API_BASE = '/api/v1';

export function getRoleHeader(): string {
  const role = localStorage.getItem('datatrust-role');
  if (!role) return 'Admin';
  return role.charAt(0).toUpperCase() + role.slice(1);
}

async function request<T = any>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const customHeaders = (options.headers as Record<string, string>) || {};
  const headers: Record<string, string> = {
    'X-User-Role': getRoleHeader(),
    ...customHeaders,
  };

  if (options.body && !(options.body instanceof FormData) && !headers['Content-Type']) {
    headers['Content-Type'] = 'application/json';
  }

  const res = await fetch(`${API_BASE}${endpoint}`, {
    ...options,
    headers,
  });

  if (!res.ok) {
    let errorDetail = '';
    try {
      const json = await res.json();
      errorDetail = json.detail || json.message || JSON.stringify(json);
    } catch {
      errorDetail = await res.text().catch(() => '');
    }
    throw new Error(`HTTP ${res.status}${errorDetail ? `: ${errorDetail}` : ''}`);
  }

  return res.json();
}

// Typed API clients
export const authApi = {
  login: (credentials: { username: string; password: string }) =>
    request<{ access_token: string; token_type: string; role: string; user: string }>('/auth/login', {
      method: 'POST',
      body: JSON.stringify(credentials),
    }),
  getMe: () =>
    request<{ user_id: string; username: string; role: string; permissions: string[] }>('/auth/me'),
  logout: () =>
    request<{ status: string; message: string }>('/auth/logout', {
      method: 'POST',
    }),
};

export const datasetsApi = {
  list: () =>
    request<{ datasets: Array<{ key: string; path: string; exists: boolean; size_mb: number }> }>('/datasets'),
  get: (key: string) =>
    request<{ key: string; path: string; exists: boolean; size_mb: number }>(`/datasets/${key}`),
  profile: (key: string, sampleSize: number = 100000) =>
    request<{ dataset: string; sample_size: number; profile: any }>(`/datasets/${key}/profile?sample_size=${sampleSize}`, {
      method: 'POST',
    }),
  proposeRules: (key: string, variant: string = 'A1', sampleSize: number = 100000) =>
    request<{ dataset: string; variant: string; rules_count: number; rules: any[]; generation_time_seconds: number }>(
      `/datasets/${key}/propose?variant=${variant}&sample_size=${sampleSize}`,
      { method: 'POST' }
    ),
  executeRules: (key: string, sampleSize?: number) =>
    request<{ dataset: string; input_rows: number; clean_rows: number; quarantine_rows: number; rules_applied: number; execution_result: any }>(
      `/datasets/${key}/execute${sampleSize ? `?sample_size=${sampleSize}` : ''}`,
      { method: 'POST' }
    ),
  benchmark: (key: string, sampleSize: number = 50000) =>
    request<{ dataset: string; sample_size: number; results: any }>(`/datasets/${key}/benchmark?sample_size=${sampleSize}`, {
      method: 'POST',
    }),
  upload: (file: File) => uploadDatasetFile(file),
};

export const approvalsApi = {
  list: () =>
    request<Array<{ id: string; rule_type: string; rule_name: string; status: string; description: string }>>('/approvals'),
  approve: (ruleId: string) =>
    request<{ status: string; rule_id: string }>(`/approvals/${ruleId}/approve`, {
      method: 'POST',
    }),
  reject: (ruleId: string) =>
    request<{ status: string; rule_id: string }>(`/approvals/${ruleId}/reject`, {
      method: 'POST',
    }),
  batchApprove: (ruleIds: string[], action: 'approve' | 'reject' = 'approve') =>
    request<{ status: string; processed_count: number; new_status: string }>('/approvals/batch', {
      method: 'POST',
      body: JSON.stringify({ rule_ids: ruleIds, action }),
    }),
};

export const schedulesApi = {
  list: () =>
    request<Array<{
      schedule_id: string;
      id: string;
      name: string;
      dataset_name: string;
      schedule_type: string;
      interval_seconds?: number;
      cron_expression?: string;
      action: string;
      status: string;
      created_at: string;
      last_run?: string;
      next_run?: string;
      run_count: number;
    }>>('/schedules'),
  create: (data: {
    name: string;
    dataset_name?: string;
    schedule_type?: string;
    interval_seconds?: number;
    cron_expression?: string;
    action?: string;
  }) =>
    request<any>('/schedules', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  delete: (id: string) =>
    request<{ status: string; message: string }>(`/schedules/${id}`, {
      method: 'DELETE',
    }),
};

export const benchmarksApi = {
  list: () =>
    request<{ status: string; available_baselines: string[]; description: string }>('/benchmarks'),
  run: (params?: { dataset_key?: string; sample_size?: number }) =>
    request<{ dataset: string; sample_size: number; results: any }>('/benchmarks/run', {
      method: 'POST',
      body: JSON.stringify({
        dataset_key: params?.dataset_key ?? 'vietnam_trips_dirty',
        sample_size: params?.sample_size ?? 50000,
      }),
    }),
};

// Legacy exported standalone helpers
export async function sendChatMessage(message: string, sessionId: string = 'default') {
  return request('/chat/send', {
    method: 'POST',
    body: JSON.stringify({ message, session_id: sessionId }),
  });
}

export async function fetchChatHistory(sessionId: string = 'default') {
  return request(`/chat/history?session_id=${sessionId}`);
}

export async function fetchChatSessions() {
  try {
    return await request('/chat/sessions');
  } catch {
    return { sessions: [] };
  }
}

export async function clearChatDatabase(sessionId?: string) {
  return request('/chat/clear', {
    method: 'POST',
    body: JSON.stringify({ session_id: sessionId }),
  });
}

export async function uploadDatasetFile(file: File) {
  const formData = new FormData();
  formData.append('file', file);
  return request('/datasets/upload', {
    method: 'POST',
    body: formData,
  });
}
