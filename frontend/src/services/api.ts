const API_BASE = '/api/v1';

export function getRoleHeader(): string {
  const role = localStorage.getItem('datatrust-role');
  if (!role) return 'Steward';
  return role.charAt(0).toUpperCase() + role.slice(1);
}

const TOKEN_KEYS = ['datatrust-token', 'datatrust_jwt_token'] as const;

export function getGlobalUseLlm(): boolean {
  return true;
}

export function setGlobalUseLlm(_useLlm: boolean) {
  localStorage.setItem('datatrust-use-llm', 'true');
  window.dispatchEvent(new CustomEvent('datatrust:llm-mode-changed', { detail: { useLlm: true } }));
}


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
  let profileRole = '';
  try {
    const raw = localStorage.getItem('datatrust_user_profile');
    const parsed = raw ? JSON.parse(raw) : null;
    profileRole = String(parsed?.role || '').toLowerCase();
  } catch {
    profileRole = '';
  }
  const actor = role || profileRole;
  // Keep an existing steward OR admin JWT. Re-login as steward would clobber Reset DB.
  if (readAuthToken() && (role === 'steward' || role === 'admin' || actor === 'admin' || actor === 'administrator')) return;
  if (actor === 'admin' || actor === 'administrator') return;
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
    request<{ status: string; message: string; cleared_tables: string[]; reloaded_records: Record<string, number> }>('/system/reset-all?reload_warehouse=false', {
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
  getLlmStatus: () =>
    request<{
      status: string;
      model: string;
      provider: string;
      has_api_key: boolean;
      description: string;
    }>('/system/llm-status'),
};



export function normalizeDatasetKey(k: string): string {
  // Keep uploaded_* keys intact so the profiler hits the registered file,
  // not the bundled vingroup_pilot DuckDB (wrong table, e.g. vgreen).
  const cleaned = (k || '').trim();
  return cleaned || 'ev_telemetry';
}

export const datasetsApi = {
  list: () =>
    request<{ datasets: Array<{ key: string; path: string; exists: boolean; size_mb: number }> }>('/datasets'),
  get: (key: string) =>
    request<{ key: string; path: string; exists: boolean; size_mb: number }>(`/datasets/${encodeURIComponent(normalizeDatasetKey(key))}`),
  profile: (key: string, sampleSize?: number, dayIdx?: number | null) => {
    const params = new URLSearchParams();
    if (sampleSize !== undefined && sampleSize !== null) params.append('sample_size', String(sampleSize));
    if (dayIdx !== undefined && dayIdx !== null) params.append('day_idx', String(dayIdx));
    const qs = params.toString();
    return request<{ dataset: string; sample_size: number; profile: any }>(
      `/datasets/${encodeURIComponent(normalizeDatasetKey(key))}/profile${qs ? `?${qs}` : ''}`,
      { method: 'POST' }
    );
  },
  proposeRules: (key: string, variant: string = 'A1', sampleSize?: number) =>
    request<{ dataset: string; variant: string; rules_count: number; rules: any[]; generation_time_seconds: number }>(
      `/datasets/${encodeURIComponent(normalizeDatasetKey(key))}/propose?variant=${variant}${sampleSize !== undefined ? `&sample_size=${sampleSize}` : ''}`,
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
  benchmark: (key: string, sampleSize?: number) =>
    request<{ dataset: string; sample_size: number; results: any }>(
      `/datasets/${encodeURIComponent(normalizeDatasetKey(key))}/benchmark${sampleSize !== undefined ? `?sample_size=${sampleSize}` : ''}`,
      { method: 'POST' }
    ),
  upload: (file: File) => uploadDatasetFile(file),
};


export interface QualityRuleItem {
  id: string;
  rule_id: string;
  rule_type: string;
  rule_name: string;
  status: 'approved' | 'proposed' | 'pending' | 'rejected' | string;
  rule_expression: string;
  description?: string;
  confidence: number;
  proposed_by?: string;
  incident_id?: string;
  approved_by?: string;
  created_at?: string;
  approved_at?: string;
  dataset_key: string;
  dataset_name: string;
  target_table: string;
  dataset_category?: string;
  dataset_icon?: string;
  dataset_color?: string;
  layer: string;
  target_column: string;
  severity: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW' | string;
  quarantined_count?: number;
}

export const rulesApi = {
  list: (params?: { dataset_key?: string; status?: string }) => {
    const query = new URLSearchParams();
    if (params?.dataset_key) query.append('dataset_key', params.dataset_key);
    if (params?.status) query.append('status', params.status);
    const qs = query.toString();
    return request<QualityRuleItem[]>(`/rules${qs ? `?${qs}` : ''}`);
  },
  approve: (ruleId: string) =>
    request<{ status: string; rule_id: string; rule_name?: string; dataset_key?: string; quarantined_count: number; message: string }>(
      `/rules/${encodeURIComponent(ruleId)}/approve`,
      { method: 'POST' }
    ),
  reject: (ruleId: string) =>
    request<{ status: string; rule_id: string }>(`/rules/${encodeURIComponent(ruleId)}/reject`, { method: 'POST' }),
  batchApprove: (ruleIds: string[]) =>
    request<{ status: string; processed_count: number; total_quarantined: number; results: any[] }>('/rules/batch-approve', {
      method: 'POST',
      body: JSON.stringify({ rule_ids: ruleIds }),
    }),
  seedDefaults: () =>
    request<{ status: string; count: number }>('/rules/seed-defaults', { method: 'POST' }),
  create: (data: { rule_type: string; target_column: string; description?: string; dataset_key?: string }) =>
    request<{ status: string; rule_id: string; dataset_key: string }>('/rules', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
};

export const approvalsApi = {
  list: () =>
    request<Array<{ id: string; rule_type: string; rule_name: string; status: string; description: string }>>('/approvals'),
  approve: (ruleId: string) =>
    request<{ status: string; rule_id: string; quarantined_count?: number }>(`/approvals/${ruleId}/approve`, {
      method: 'POST',
    }),
  reject: (ruleId: string) =>
    request<{ status: string; rule_id: string }>(`/approvals/${ruleId}/reject`, {
      method: 'POST',
    }),
  batchApprove: (ruleIds: string[], action: 'approve' | 'reject' = 'approve') =>
    request<{ status: string; processed_count: number; new_status: string; total_quarantined?: number }>('/approvals/batch', {
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
  this_run_quarantined?: number;
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

export interface ToolTraceStep {
  tool_name: string;
  args?: Record<string, any>;
  success?: boolean;
  evidence_ref?: string;
  tokens_used?: number;
  wall_clock_sec?: number;
  data?: any;
}

export interface IncidentMeta {
  tokens_spent?: number;
  tool_calls_made?: number;
  tool_execution_trace?: ToolTraceStep[];
  hypothesis_revisions?: number;
  budget_remaining?: number;
  target_domain?: string;
  domain_allowlist?: string[];
  resolved_entity_scope?: string[];
  resolved_time_scope?: Record<string, any>;
  bounded_stop?: boolean;
  wall_clock_elapsed_sec?: number;
  stop_reason?: string;
  tool_trace?: string[];
}

export interface IncidentEvidence {
  evidence_id: string;
  source_type: string;
  source_id: string;
  time_range?: Record<string, any>;
  entity_ids?: string[];
  content_hash?: string;
  summary: string;
  provenance?: string;
}

export interface IncidentHypothesis {
  hypothesis_id?: string;
  incident_id?: string;
  claim: string;
  classification?: string;
  supporting_evidence?: string[];
  contradicting_evidence?: string[];
  missing_evidence?: string[];
  confidence?: number;
  status?: string;
}

export interface IncidentRecommendation {
  recommendation_id?: string;
  incident_id?: string;
  cause_type?: string;
  action_type?: string;
  summary?: string;
  details?: Record<string, any>;
  requires_hitl_approval?: boolean;
}

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

  // Enriched A1 Dynamic RCA fields
  target_entity?: string;
  domain?: string;
  fault_family?: string;
  layer?: string;
  llm_claim?: string;
  llm_classification?: string;
  confidence?: number;
  benchmark_score?: number;
  verdict?: string;
  tokens_spent?: number;
  tool_calls_count?: number;
  tool_trace?: string[];
  expected_action?: string;
  ground_truth_cause?: string;
  meta?: IncidentMeta;
  evidence?: IncidentEvidence[];
  hypotheses?: IncidentHypothesis[];
  recommendations?: IncidentRecommendation[];
  benchmark_eval?: any;

  // User feedback fields
  feedback_type?: string; // "TRUE_POSITIVE" | "FALSE_POSITIVE"
  feedback_reason?: string;
  feedback_by?: string;
  feedback_at?: string;
}

export const incidentsApi = {
  list: (projectId: string = 'proj-vingroup-pilot') =>
    request<IncidentInfo[]>(`/incidents?project_id=${encodeURIComponent(projectId)}`),
  get: (incidentId: string) =>
    request<IncidentInfo>(`/incidents/${encodeURIComponent(incidentId)}`),
  investigate: (incidentId: string, mode: 'R0' | 'C1' | 'A1' | string = 'A1', useLlm?: boolean) =>
    request<any>(`/incidents/${encodeURIComponent(incidentId)}/investigate?mode=${mode}&use_llm=${useLlm !== undefined ? useLlm : getGlobalUseLlm()}`, { method: 'POST' }),

  chat: (incidentId: string, payload: any) =>
    request<{ reply: string; reasoning?: string; tokens_used?: number }>(`/incidents/${encodeURIComponent(incidentId)}/chat`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  submitFeedback: (incidentId: string, feedbackType: 'TRUE_POSITIVE' | 'FALSE_POSITIVE', reason: string = '', user: string = 'human') =>
    request<{ status: string; incident_id: string; feedback_type: string; feedback_reason: string; feedback_by: string; feedback_at: string; incident_status: string }>(
      `/incidents/${encodeURIComponent(incidentId)}/feedback`,
      {
        method: 'POST',
        body: JSON.stringify({ feedback_type: feedbackType, reason, user }),
      }
    ),
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
  timeline: (sessionId: string, since?: string) =>
    request<{ session_id: string; events: Array<Record<string, any>>; cot: boolean; execute: string }>(
      `/traces/${encodeURIComponent(sessionId)}/timeline${since ? `?since=${encodeURIComponent(since)}` : ''}`
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
  getGt: (signal?: AbortSignal) => request<Record<string, any>>('/evaluation/gt', { signal }),
};

// Legacy exported standalone helpers
export function isPongPing(message: string): boolean {
  const m = (message || '').trim().toLowerCase();
  return m.includes('pong') && (m.includes('reply') || m.includes('only') || m.includes('one word') || m.includes('ping'));
}

export async function sendChatMessage(message: string, sessionId: string = 'default', datasetKey?: string, lang?: string, useLlm?: boolean, activeDay?: number | null, signal?: AbortSignal) {
  const currentLang = lang || localStorage.getItem('datatrust-lang') || 'vi';
  const effectiveUseLlm = useLlm !== undefined ? useLlm : getGlobalUseLlm();
  const ping = isPongPing(message);
  const result = await request('/chat/send', {
    method: 'POST',
    signal,
    body: JSON.stringify({
      message,
      session_id: sessionId,
      lang: currentLang,
      use_llm: effectiveUseLlm,
      ...(!ping && datasetKey ? { dataset_key: datasetKey } : {}),
      ...(activeDay !== undefined && activeDay !== null ? { active_day: activeDay } : {}),
    }),
  });
  try {
    window.dispatchEvent(new CustomEvent('datatrust:agent-trace'));
    const proposals = result?.proposals || result?.output_data?.proposals || result?.data?.proposals;
    if (Array.isArray(proposals) && proposals.length) {
      window.dispatchEvent(new CustomEvent('datatrust:hitl-proposed', {
        detail: { proposals, dataset_key: datasetKey || result?.dataset_key, count: proposals.length },
      }));
    }
  } catch { /* ignore */ }
  return result;
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
  layer?: string;
  problem_discovered?: string;
  why_proposed?: string;
  quality_impact?: string;
  reject_reason?: string;
  feedback_by?: string;
  feedback_at?: string | null;
  source_ingestion_run_id?: string;
  created_at?: string | null;
}

export const hitlApi = {
  queue: (datasetKey?: string) =>
    request<{ proposals: HITLProposal[] }>(`/hitl/queue${datasetKey ? `?dataset_key=${encodeURIComponent(datasetKey)}` : ''}`),
  synthesizeLlm: (datasetKey?: string, tableName?: string, useLlm?: boolean) =>
    request<{ status: string; count: number; dataset_key?: string; proposals: HITLProposal[]; llm_powered?: boolean; model_used?: string }>('/hitl/synthesize-llm', {
      method: 'POST',
      body: JSON.stringify({ dataset_key: datasetKey, table_name: tableName, use_llm: useLlm !== undefined ? useLlm : getGlobalUseLlm() }),
    }),


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
  sandbox: (datasetKey: string, ruleIds: string[]) =>
    request<{
      dataset_key: string;
      sandbox?: boolean;
      clean?: any[];
      quarantine?: any[];
      clean_rows?: number;
      quarantine_rows?: number;
      manifest_hash?: string;
      snapshot_id?: string;
      this_run?: boolean;
      sampled_rows?: number;
      cell_diffs?: any[];
      execute?: string;
      run_id?: string;
      per_rule_counts?: Record<string, number>;
      tables?: string[];
    }>('/hitl/sandbox', {
      method: 'POST',
      body: JSON.stringify({ dataset_key: datasetKey, rule_ids: ruleIds }),
    }),
  getSandbox: (runId: string) =>
    request<{
      run_id: string;
      dataset_key?: string;
      quarantine_rows?: number;
      quarantine?: any[];
      cell_diffs?: any[];
      execute?: string;
    }>(`/hitl/sandbox/${encodeURIComponent(runId)}`),
  history: () =>
    request<{ history: Array<{ event_hash?: string; previous_event_hash?: string; action?: string; timestamp?: string }> }>('/hitl/history'),
};

export const pipelineApi = {
  trigger: (tableName: string = 'charging_sessions', ruleId?: string) =>
    request<{ run_id: string; status: string; table: string }>(
      `/pipeline/trigger?table_name=${encodeURIComponent(tableName)}${ruleId ? `&rule_id=${encodeURIComponent(ruleId)}` : ''}`,
      { method: 'POST' }
    ),
  execute: (tableName: string = 'charging_sessions', ruleId?: string) =>
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

export interface QuarantineSampleRecord {
  id: string;
  source_row_id: number | string;
  reason: string;
  original_data?: any;
  quarantined_at?: string | null;
  lineage_hash?: string | null;
}

export interface QuarantineGroup {
  group_id: string;
  rule_id: string;
  rule_name: string;
  source_table: string;
  severity: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW' | string;
  total_rows: number;
  reason_summary: string;
  ai_suggested_sql: string;
  remediation_strategy: string;
  sample_records: QuarantineSampleRecord[];
  earliest_time?: string | null;
  latest_time?: string | null;
  status?: string;
}

export const quarantineApi = {
  list: (limit: number = 100, offset: number = 0, sourceTable?: string, ruleId?: string, search?: string) => {
    let url = `/quarantine/?limit=${limit}&offset=${offset}`;
    if (sourceTable && sourceTable !== 'all') url += `&source_table=${encodeURIComponent(sourceTable)}`;
    if (ruleId && ruleId !== 'all') url += `&rule_id=${encodeURIComponent(ruleId)}`;
    if (search) url += `&search=${encodeURIComponent(search)}`;
    return request<{
      quarantine: Array<{
        id: string;
        source_table: string;
        source_row_id: string | number;
        rule_id: string;
        reason: string;
        original_data?: any;
        quarantined_at?: string | null;
        lineage_hash?: string | null;
        status?: string;
      }>;
      total_count: number;
      limit: number;
      offset: number;
    }>(url);
  },
  groups: (sourceTable?: string, status?: string) => {
    let url = '/quarantine/groups';
    const params: string[] = [];
    if (sourceTable && sourceTable !== 'all') params.push(`source_table=${encodeURIComponent(sourceTable)}`);
    if (status && status !== 'all') params.push(`status=${encodeURIComponent(status)}`);
    if (params.length > 0) url += `?${params.join('&')}`;
    return request<{
      groups: QuarantineGroup[];
      total_quarantined: number;
      groups_count: number;
    }>(url);
  },
  remediate: (payload: { rule_id: string; source_table: string; sql_query?: string; group_id?: string; action_by?: string }) =>
    request<{ status: string; remediated_count: number; rule_id: string; source_table: string; applied_sql: string; message: string }>(
      '/quarantine/remediate',
      {
        method: 'POST',
        body: JSON.stringify(payload),
      }
    ),
  reject: (payload: { rule_id: string; source_table: string; group_id?: string; reason?: string; action_by?: string }) =>
    request<{ status: string; rejected_count: number; rule_id: string; source_table: string; group_status: string; message: string }>(
      '/quarantine/reject',
      {
        method: 'POST',
        body: JSON.stringify(payload),
      }
    ),
  block: (payload: { rule_id: string; source_table: string; group_id?: string; reason?: string; action_by?: string }) =>
    request<{ status: string; blocked_count: number; rule_id: string; source_table: string; message: string }>(
      '/quarantine/block',
      {
        method: 'POST',
        body: JSON.stringify(payload),
      }
    ),
  count: () =>
    request<{ counts: Record<string, number>; this_run?: number }>('/quarantine/count'),
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

// ── Ingestion / Demo Landing API clients ─────────────────────────────────────

export interface IngestionDaySnapshot {
  day_idx: number;
  snapshot_id: string;
  day_date: string;
  is_activated: boolean;
  is_ingested: boolean;
  ingested_rows: number;
  status?: 'completed' | 'running' | 'idle' | 'failed';
  alerts_count?: number;
  l1_alerts?: number;
  l2_alerts?: number;
  l3_alerts?: number;
  l4_alerts?: number;
  duration_ms?: number;
  realtime_active?: boolean;
}

export interface IngestionDayTimeline {
  days: IngestionDaySnapshot[];
  total_days: number;
  activated_days: number;
}

export interface IngestionDemoState {
  current_day_idx: number;
  warmup_completed: boolean;
  realtime_active: boolean;
  last_activated_at: string | null;
}

export interface IngestionRun {
  run_id: string;
  run_type: string; // "WARMUP_10D" | "DAILY_PLUS1"
  day_idx: number;
  started_at: string;
  completed_at: string | null;
  status: string; // "running" | "completed" | "error"
  rows_ingested: number;
  violations_detected: number;
  duration_ms: number;
}

export interface IngestionRunsResponse {
  runs: IngestionRun[];
  total: number;
}

export interface RealtimeStatus {
  active: boolean;
  current_day_idx: number;
  tick_count: number;
  last_tick_at: string | null;
  status: string; // "idle" | "running" | "error"
  message: string;
  total_day_rows?: number;
  read_cursor?: number;
  clean_total?: number;
  quarantined_total?: number;
  l1_total?: number;
  l2_total?: number;
  l3_total?: number;
  l4_total?: number;
}

export interface QuarantineSummaryRule {
  rule_id: string;
  rule_layer: string;
  rule_name: string;
  status: string;
  detected_via: string;
  total_records: number;
  affected_days: number;
  affected_entities: number;
  first_seen: string;
  last_seen: string;
  sample_reason: string;
}

export interface QuarantineDetailRecord {
  quarantine_id: string;
  source_ingestion_run_id: string;
  day_idx: number;
  vehicle_vin: string | null;
  rule_id: string;
  rule_layer: string;
  rule_name: string;
  reason: string;
  raw_row: any;
  detected_at: string;
  detected_via: string;
  status: string;
  resolved_at: string | null;
  resolved_by: string | null;
  resolution_action: string | null;
}

export const ingestionApi = {
  getStatus: () => request<IngestionDemoState>('/ingestion/status'),
  getDays: () => request<IngestionDayTimeline>('/ingestion/days'),
  getDay: (dayIdx: number) => request<IngestionDaySnapshot>(`/ingestion/days/${dayIdx}`),
  activateWarmup: () =>
    request<{
      day_idx: number;
      status: string;
      message: string;
      ingestion_run_id: string | null;
    }>('/ingestion/warmup', { method: 'POST' }),
  activateDay: (dayIdx: number, forceReplay = false) =>
    request<{
      day_idx: number;
      status: string;
      message: string;
      ingestion_run_id: string | null;
    }>(`/ingestion/days/${dayIdx}/activate`, {
      method: 'POST',
      body: JSON.stringify({ force_replay: forceReplay }),
    }),
  getRuns: (limit = 50) => request<IngestionRunsResponse>(`/ingestion/runs?limit=${limit}`),
  reset: () => request<{ status: string; message: string }>('/ingestion/reset', { method: 'POST' }),
  getRealtimeStatus: () => request<RealtimeStatus>('/ingestion/realtime/status'),
  startRealtime: () => request<{ action: string; status: string; message: string }>('/ingestion/realtime/start', { method: 'POST' }),
  stopRealtime: () => request<{ action: string; status: string; message: string }>('/ingestion/realtime/stop', { method: 'POST' }),
  health: () => request<{ status: string; service: string }>('/ingestion/health'),
  getQuarantineSummary: (table = 'ev_telemetry') =>
    request<{ rules: QuarantineSummaryRule[] }>(`/ingestion/quarantine/summary?table=${encodeURIComponent(table)}`),
  getQuarantineDetail: (ruleId: string, table = 'ev_telemetry', detectedVia?: string) => {
    let url = `/ingestion/quarantine/detail?rule_id=${encodeURIComponent(ruleId)}&table=${encodeURIComponent(table)}`;
    if (detectedVia) url += `&detected_via=${encodeURIComponent(detectedVia)}`;
    return request<{ records: QuarantineDetailRecord[] }>(url);
  },
  resolveQuarantine: (quarantineId: string, action: string, resolvedBy = 'human') =>
    request<{ status: string; message: string }>('/ingestion/quarantine/resolve', {
      method: 'POST',
      body: JSON.stringify({ quarantine_id: quarantineId, action, resolved_by: resolvedBy }),
    }),
};
