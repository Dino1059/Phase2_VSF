const API_BASE = '/api/v1';

export function getRoleHeader(): string {
  const role = localStorage.getItem('datatrust-role');
  if (!role) return 'Steward';
  return role.charAt(0).toUpperCase() + role.slice(1);
}

const TOKEN_KEYS = ['datatrust-token', 'datatrust_jwt_token'] as const;

export function readAuthToken(): string | null {
  for (const key of TOKEN_KEYS) {
    const value = localStorage.getItem(key);
    if (value) return value;
  }
  return null;
}

export function persistAuthToken(token: string, role?: string) {
  localStorage.setItem('datatrust-token', token);
  localStorage.setItem('datatrust_jwt_token', token);
  if (role) localStorage.setItem('datatrust-role', role);
}

async function request<T = any>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const customHeaders = (options.headers as Record<string, string>) || {};
  const token = readAuthToken();
  const headers: Record<string, string> = {
    'X-User-Role': getRoleHeader(),
    ...customHeaders,
  };
  if (token) headers.Authorization = `Bearer ${token}`;

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
  login: (credentials: { username: string; password?: string; role?: string }) =>
    request<{ access_token: string; token_type: string; user: { user_id: string; username: string; role: string } }>('/auth/login', {
      method: 'POST',
      body: JSON.stringify(credentials),
    }),
  quickSwitch: (role: string) =>
    request<{ access_token: string; token_type: string; user: { user_id: string; username: string; role: string } }>('/auth/quick-switch', {
      method: 'POST',
      body: JSON.stringify({ role }),
    }),
  getMe: () =>
    request<{ user_id: string; username: string; role: string }>('/auth/me'),
  logout: () =>
    request<{ status: string; message: string }>('/auth/logout', {
      method: 'POST',
    }),
};

export async function ensureDemoAuth(): Promise<void> {
  const role = (localStorage.getItem('datatrust-role') || '').toLowerCase();
  if (readAuthToken() && role === 'steward') return;
  const res = await authApi.login({ username: 'steward', role: 'steward' });
  if (res?.access_token) {
    persistAuthToken(res.access_token, 'steward');
    const profile = (res as { user_profile?: { user_id: string; username: string; role: string } }).user_profile
      || (res.user && typeof res.user === 'object' ? res.user : null)
      || { user_id: 'usr_steward_01', username: 'steward', role: 'Steward' };
    localStorage.setItem('datatrust_user_profile', JSON.stringify(profile));
  }
}


export const systemApi = {
  resetAll: () =>
    request<{ status: string; message: string; cleared_tables: string[]; reloaded_records: Record<string, number> }>('/system/reset-all', {
      method: 'POST',
    }),
  loadSnapshot: (mode: 'happy' | 'unhappy') =>
    request<{
      mode: string;
      source: string;
      fault_injected: boolean;
      telemetry: number;
      charging_sessions: number;
      trips: number;
      soc_below_zero: number;
      open_incidents: number;
      window_end: string;
      ingress: string;
    }>(`/system/demo-snapshot?mode=${mode}`, { method: 'POST' }),
};


export function normalizeDatasetKey(k: string): string {
  // Keep uploaded_* keys intact so the profiler hits the registered file,
  // not the bundled vingroup_pilot DuckDB (wrong table, e.g. vgreen).
  const cleaned = (k || '').trim();
  return cleaned || 'vingroup_pilot';
}

export const datasetsApi = {
  list: () =>
    request<{ datasets: Array<{ key: string; path: string; exists: boolean; size_mb: number }> }>('/datasets'),
  get: (key: string) =>
    request<{ key: string; path: string; exists: boolean; size_mb: number }>(`/datasets/${encodeURIComponent(normalizeDatasetKey(key))}`),
  profile: (key: string, sampleSize: number = 100000) =>
    request<{ dataset: string; sample_size: number; profile: any }>(`/datasets/${encodeURIComponent(normalizeDatasetKey(key))}/profile?sample_size=${sampleSize}`, {
      method: 'POST',
    }),
  proposeRules: (key: string, variant: string = 'A1', sampleSize: number = 100000) =>
    request<{ dataset: string; variant: string; rules_count: number; rules: any[]; generation_time_seconds: number }>(
      `/datasets/${encodeURIComponent(normalizeDatasetKey(key))}/propose?variant=${variant}&sample_size=${sampleSize}`,
      { method: 'POST' }
    ),
  executeRules: (key: string, sampleSize?: number) =>
    request<{ dataset: string; input_rows: number; clean_rows: number; quarantine_rows: number; rules_applied: number; execution_result: any }>(
      `/datasets/${encodeURIComponent(normalizeDatasetKey(key))}/execute${sampleSize ? `?sample_size=${sampleSize}` : ''}`,
      { method: 'POST' }
    ),
  sample: (key: string, limit: number = 50, offset: number = 0) =>
    request<{ dataset: string; total_rows: number; limit: number; offset: number; columns: string[]; rows: any[] }>(
      `/datasets/${encodeURIComponent(normalizeDatasetKey(key))}/sample?limit=${limit}&offset=${offset}`
    ),
  benchmark: (key: string, sampleSize: number = 50000) =>
    request<{ dataset: string; sample_size: number; results: any }>(`/datasets/${encodeURIComponent(normalizeDatasetKey(key))}/benchmark?sample_size=${sampleSize}`, {
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
  authorize: (datasetKey: string, ruleIds: string[]) =>
    request<{ authorization_id: string; payload_hash: string; status: string; rule_ids: string[] }>('/approvals/authorize', {
      method: 'POST',
      body: JSON.stringify({ dataset_key: datasetKey, rule_ids: ruleIds }),
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

export interface TrendInfo {
  range: string;
  labels: string[];
  voltage_spikes: number[];
  thermal_flags: number[];
}

export const summaryApi = {
  get: () => request<SummaryInfo>('/summary'),
  getTrend: (range: string = '24h') => request<TrendInfo>(`/summary/trend?range=${encodeURIComponent(range)}`),
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
  chat: (incidentId: string, payload: any) =>
    request<{ reply: string; reasoning?: string; tokens_used?: number }>(`/incidents/${encodeURIComponent(incidentId)}/chat`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
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

export interface TraceSession {
  session_id: string;
  agent_type?: string;
  steps: number;
  total_tokens?: number;
  started?: string | null;
}

export const tracesApi = {
  list: (limit: number = 20) =>
    request<{ sessions: TraceSession[] }>(`/traces/?limit=${limit}`),
  get: (sessionId: string, since?: string) =>
    request<{ session_id: string; steps: Array<Record<string, any>> }>(
      `/traces/${encodeURIComponent(sessionId)}${since ? `?since=${encodeURIComponent(since)}` : ''}`
    ),
};

export const executionsApi = {
  list: () => request<Array<Record<string, any>>>('/executions'),
};

export interface SnapshotInfo {
  id: string;
  source_file?: string;
  sha256_hash?: string;
  row_count?: number;
  column_count?: number;
  ingested_at?: string | null;
}

export const snapshotsApi = {
  list: () => request<{ snapshots: SnapshotInfo[] }>('/snapshots/'),
  get: (snapshotId: string) => request<SnapshotInfo>(`/snapshots/${encodeURIComponent(snapshotId)}`),
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

export interface SearchHit {
  objectID?: string;
  entity_type?: string;
  key?: string;
  name?: string;
  title?: string;
  path?: string;
  description?: string;
  rule_expression?: string;
  severity?: string;
  [key: string]: any;
}

export interface SearchResponse {
  status: string;
  query: string;
  entity_type?: string | null;
  count: number;
  results: SearchHit[];
}

export const searchApi = {
  search: (query: string, entityType?: string, limit: number = 10) =>
    request<SearchResponse>(
      `/search?q=${encodeURIComponent(query)}${entityType ? `&entity_type=${encodeURIComponent(entityType)}` : ''}&limit=${limit}`
    ),
};

export const evaluationApi = {
  get: () => request<EvaluationMetricsInfo>('/evaluation'),
};

// Legacy exported standalone helpers
export async function sendChatMessage(message: string, sessionId: string = 'default', datasetKey?: string, lang?: string) {
  const currentLang = lang || localStorage.getItem('datatrust-lang') || 'vi';
  return request('/chat/send', {
    method: 'POST',
    body: JSON.stringify({
      message,
      session_id: sessionId,
      lang: currentLang,
      ...(datasetKey ? { dataset_key: datasetKey } : {}),
    }),
  });
}


export async function fetchChatHistory(sessionId: string = 'default') {
  return request(`/chat/history?session_id=${encodeURIComponent(sessionId)}`);
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

export const DEMO_SESSION_ID = 'dataset:vingroup_pilot';

export async function resetDemoSession(): Promise<void> {
  try {
    await clearChatDatabase(DEMO_SESSION_ID);
  } catch {
    /* snapshot already wiped traces/chat */
  }
  try {
    window.dispatchEvent(new CustomEvent('datatrust:agent-trace'));
  } catch {
    /* ignore */
  }
}

export async function uploadDatasetFile(file: File, lang?: string) {
  const currentLang = lang || localStorage.getItem('datatrust-lang') || 'vi';
  const formData = new FormData();
  formData.append('file', file);
  return request(`/datasets/upload?lang=${encodeURIComponent(currentLang)}`, {
    method: 'POST',
    body: formData,
  });
}

// ── Pipeline / HITL / Quarantine / Anomaly clients (ui_temp port) ─────────

export interface HITLProposal {
  rule_id: string;
  rule_name: string;
  rule_type: string;
  rule_expression: string;
  confidence?: number;
  status?: string;
  proposed_by?: string;
  proposed_at?: string | null;
}

export const hitlApi = {
  queue: (datasetKey?: string) =>
    request<{ proposals: HITLProposal[] }>(
      `/hitl/queue${datasetKey ? `?dataset_key=${encodeURIComponent(datasetKey)}` : ''}`
    ),
  approve: (ruleId: string, approvedBy: string = 'human') =>
    request<{ status: string; rule_id: string }>(`/hitl/approve/${encodeURIComponent(ruleId)}`, {
      method: 'POST',
      body: JSON.stringify({ approved_by: approvedBy }),
    }),
  reject: (ruleId: string, rejectedBy: string = 'human', reason: string = '') =>
    request<{ status: string; rule_id: string }>(`/hitl/reject/${encodeURIComponent(ruleId)}`, {
      method: 'POST',
      body: JSON.stringify({ rejected_by: rejectedBy, reason }),
    }),
  edit: (ruleId: string, ruleExpression: string, editedBy: string = 'human') =>
    request<{ status: string; rule_id: string }>(`/hitl/edit/${encodeURIComponent(ruleId)}`, {
      method: 'POST',
      body: JSON.stringify({ rule_expression: ruleExpression, edited_by: editedBy }),
    }),
  execute: (ruleId: string) =>
    request<{ status: string; rule_id: string }>(`/hitl/execute/${encodeURIComponent(ruleId)}`, {
      method: 'POST',
    }),
  history: () =>
    request<{ history: Array<{ event_hash?: string; previous_event_hash?: string; action?: string; timestamp?: string }> }>('/hitl/history'),
};

export const pipelineApi = {
  trigger: (tableName: string = 'vgreen_telemetry', ruleId?: string) =>
    request<{ run_id: string; status: string; table: string }>(
      `/pipeline/trigger?table_name=${encodeURIComponent(tableName)}${ruleId ? `&rule_id=${encodeURIComponent(ruleId)}` : ''}`,
      { method: 'POST' }
    ),
  execute: (tableName: string = 'vgreen_telemetry', ruleId?: string) =>
    request<{ run_id: string; status: string; table: string }>(
      `/pipeline/execute?table_name=${encodeURIComponent(tableName)}${ruleId ? `&rule_id=${encodeURIComponent(ruleId)}` : ''}`,
      { method: 'POST' }
    ),
  status: (runId: string) =>
    request<{ run_id: string; status: string; steps: Array<{ agent?: string; step?: number; action?: string; timestamp?: string | null }> }>(
      `/pipeline/status/${encodeURIComponent(runId)}`
    ),
  result: (runId: string) =>
    request<{
      run_id: string;
      project_id?: string;
      dataset_key?: string;
      status: string;
      error?: string | null;
      rca?: { nodes?: any[]; edges?: any[]; incidents?: any[] };
      telemetry?: { table?: string; metric?: string | null; series?: Array<{ timestamp: string; value: number }> };
      split?: { clean_rows?: number | null; quarantine_rows?: number | null; clean?: any[]; quarantine?: any[] };
      manifest?: { hash?: string; algorithm?: string; status?: string };
    }>(`/pipeline/result/${encodeURIComponent(runId)}`),
};

export const quarantineApi = {
  list: (limit: number = 50) =>
    request<{ quarantine: Array<{
      id: string;
      source_table: string;
      source_row_id: string;
      rule_id: string;
      reason: string;
      quarantined_at?: string | null;
      lineage_hash?: string | null;
    }> }>(`/quarantine/?limit=${limit}`),
  count: () =>
    request<{ counts: Record<string, number> }>('/quarantine/count'),
};

export const anomaliesApi = {
  detect: (payload: { current_profile?: any; historical_profiles?: any[]; detector?: string }) =>
    request<{
      report_id: string;
      dataset_name: string;
      detected_anomalies: any[];
      anomaly_score: number;
      summary: string;
      status: string;
    }>('/anomalies/detect', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
};
