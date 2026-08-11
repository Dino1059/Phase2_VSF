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

export const dashboardApi = {
  getStats: () =>
    request<{
      tables?: Record<string, number>;
      quality_score?: number;
      rule_stats?: Record<string, number>;
      total_data_records?: number;
      quarantined?: number;
      metrics?: any;
      insights?: any[];
      activityFeed?: any[];
    }>('/dashboard/stats'),
  getActivity: (limit: number = 20) =>
    request<{ activity: Array<{ id: string; action: string; actor: string; target_table: string; details: string; timestamp: string }> }>(`/dashboard/activity?limit=${limit}`),
};

export interface ProjectInfo {
  project_id: string;
  name: string;
  status: string;
  provenance: string;
  entities_count: number;
  stations_count: number;
  datasets: string[];
}

export const projectsApi = {
  list: () => request<ProjectInfo[]>('/projects'),
};

export interface SummaryInfo {
  projects_count: number;
  active_project_id: string;
  provenance: string;
  total_data_records: number;
  clean_records: number;
  quarantined_records: number;
  pass_validation_rate: string;
  system_status: string;
}

export const summaryApi = {
  get: () => request<SummaryInfo>('/summary'),
};

export interface IncidentInfo {
  incident_id: string;
  project_id: string;
  status: 'OPEN' | 'INVESTIGATING' | 'RESOLVED' | 'CLOSED' | 'DISMISSED' | string;
  entity_ids: string[];
  signal_ids: string[];
  admission_reason: string;
  supporting_layers?: string[];
  severity: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL' | string;
  time_window?: Record<string, string>;
  confirmed_facts?: string[];
  evidence_refs?: string[];
  owner?: string | null;
  created_at?: string;
  updated_at?: string;
}

export const incidentsApi = {
  list: (projectId: string = 'proj-vingroup-pilot') =>
    request<IncidentInfo[]>(`/incidents?project_id=${encodeURIComponent(projectId)}`),
  get: (incidentId: string) =>
    request<IncidentInfo>(`/incidents/${encodeURIComponent(incidentId)}`),
  investigate: (incidentId: string, mode: 'R0' | 'C1' | 'A1' = 'C1') =>
    request<any>(`/incidents/${encodeURIComponent(incidentId)}/investigate?mode=${mode}`, { method: 'POST' }),
};

export async function fetchIncident(incidentId: string): Promise<IncidentInfo> {
  return incidentsApi.get(incidentId);
}

export interface SignalInfo {
  signal_id: string;
  project_id: string;
  entity_ids: string[];
  layer: string;
  signal_type: string;
  metric_or_relationship: string;
  score: number;
  severity: string;
  detector: string;
  provenance: string;
  timestamp?: string;
}

export const signalsApi = {
  list: (projectId: string = 'proj-vingroup-pilot', layer?: string, entityId?: string) => {
    const params = new URLSearchParams();
    if (projectId) params.append('project_id', projectId);
    if (layer) params.append('layer', layer);
    if (entityId) params.append('entity_id', entityId);
    const qs = params.toString();
    return request<SignalInfo[]>(`/signals${qs ? `?${qs}` : ''}`);
  },
};

export interface PreventiveControlInfo {
  control_id: string;
  rule_type: string;
  rule_expression: string;
  target_table: string;
  target_column: string;
  proposed_by: string;
  version: number;
  status: 'PROPOSED' | 'REVIEWED' | 'COMPILED' | 'SANDBOX_VALIDATED' | 'APPROVED' | 'REJECTED' | 'EXECUTED' | string;
  approval_hash?: string | null;
  created_at?: string;
  reviewed_by?: string | null;
  reviewed_at?: string | null;
  compiled_expression?: string | null;
  compiled_at?: string | null;
  sandbox_passed?: boolean | null;
  sandbox_details?: Record<string, any> | null;
  sandbox_validated_at?: string | null;
}

export const controlsApi = {
  list: () => request<PreventiveControlInfo[]>('/controls'),
  get: (controlId: string) => request<PreventiveControlInfo>(`/controls/${encodeURIComponent(controlId)}`),
  propose: (payload: {
    control_id: string;
    rule_type?: string;
    rule_expression: string;
    target_table: string;
    target_column: string;
  }) =>
    request<PreventiveControlInfo>('/controls/propose', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  approve: (controlId: string, actor: string) =>
    request<AuthorizationInfo>(`/controls/${encodeURIComponent(controlId)}/approve`, {
      method: 'POST',
      body: JSON.stringify({ actor }),
    }),
};

export interface AuthorizationInfo {
  authorization_id: string;
  control_id: string;
  version: number;
  authorized_actor: string;
  payload_hash: string;
  authorized_at?: string;
  expires_at?: string | null;
  status: 'VALID' | 'EXPIRED' | 'REVOKED' | 'EXECUTED' | string;
}

export const authorizationsApi = {
  list: () => request<AuthorizationInfo[]>('/authorizations'),
  get: (authorizationId: string) =>
    request<AuthorizationInfo>(`/authorizations/${encodeURIComponent(authorizationId)}`),
  pipeline: (payload: {
    control_id: string;
    rule_type?: string;
    rule_expression: string;
    target_table: string;
    target_column: string;
    reviewer?: string;
    actor?: string;
    dry_run?: boolean;
    expires_in_seconds?: number;
  }) =>
    request<{ proposal: PreventiveControlInfo; authorization: AuthorizationInfo; execution: any }>('/authorizations/pipeline', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  issue: (payload: { control_id: string; actor?: string; expires_in_seconds?: number }) =>
    request<AuthorizationInfo>('/authorizations/issue', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  verify: (payload: { authorization_id: string; control_id?: string; version?: number }) =>
    request<{ authorization_id: string; is_valid: boolean; status: string }>('/authorizations/verify', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  execute: (payload: { control_id: string; authorization_id: string; dry_run?: boolean }) =>
    request<any>('/authorizations/execute', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  revoke: (authorizationId: string) =>
    request<AuthorizationInfo>(`/authorizations/revoke/${encodeURIComponent(authorizationId)}`, {
      method: 'POST',
    }),
};

export interface AuditEntry {
  id: string;
  action: string;
  actor: string;
  target_table: string;
  target_id?: string;
  details: any;
  timestamp: string;
  previous_event_hash?: string;
  event_hash?: string;
}

export const auditApi = {
  list: (limit: number = 50) =>
    request<AuditEntry[]>(`/audit?limit=${limit}`),
};

export interface EvaluationBenchmarkItem {
  baseline: string;
  precision_pct: number;
  recall_pct: number;
  f1_pct: number;
  cost_tokens: number;
  latency_sec: number;
  faults_detected: number;
  faults_total: number;
}

export interface EvaluationMetricsInfo {
  benchmarks: EvaluationBenchmarkItem[];
  winner: string;
  time_saved_vs_c0_pct: number;
  precision_gain_vs_c1_pct: number;
}

export const evaluationApi = {
  get: () => request<EvaluationMetricsInfo>('/evaluation'),
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
