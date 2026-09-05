import type { TimeFilter } from '../types';

export const ACTOR_LABELS: Record<string, { en: string; vi: string }> = {
  ORCHESTRATOR: { en: 'Orchestrator', vi: 'Điều phối' },
  L1_DETECTOR: { en: 'L1 Detector', vi: 'Bộ phát hiện L1' },
  L2_DETECTOR: { en: 'L2 Detector', vi: 'Bộ phát hiện L2' },
  L3_DETECTOR: { en: 'L3 Detector', vi: 'Bộ phát hiện L3' },
  L4_DETECTOR: { en: 'L4 Detector', vi: 'Bộ phát hiện L4' },
  R0: { en: 'R0', vi: 'R0' },
  C1_AI: { en: 'C1 AI', vi: 'C1 AI' },
  A1_AI: { en: 'A1 AI', vi: 'A1 AI' },
  PROFILER: { en: 'Profiler', vi: 'Khảo sát' },
  PROPOSER: { en: 'Proposer', vi: 'Đề xuất' },
  REPAIR: { en: 'Repair', vi: 'Sửa chữa' },
  DATA_STEWARD: { en: 'Data Steward', vi: 'Data Steward' },
  EXECUTOR: { en: 'Executor', vi: 'Thực thi' },
  SYSTEM: { en: 'System', vi: 'Hệ thống' },
};

export const DEMO_TZ = 'Asia/Saigon';

/** Catalog fallback titles/abouts when the API omits tool_title / tool_about. */
export const TOOL_CATALOG: Record<string, { title: string; about: string }> = {
  list_datasets: { title: 'List datasets', about: 'Lists registered datasets in the repository' },
  profile_dataset: { title: 'Profile dataset', about: 'scans nulls, types, health' },
  propose_quality_rules: { title: 'Propose quality rules', about: 'Generates quality rules for HITL review' },
  clean_database: { title: 'Clean database', about: 'Applies approved rules and quarantines bad rows' },
  data_profiler: { title: 'Data profiler', about: 'Column stats: types, nulls, cardinality, min/max' },
  anomaly_detector: { title: 'Anomaly detector', about: 'Flags statistical outliers in a column' },
  telemetry_query: { title: 'Telemetry query', about: 'Queries V-GREEN and VinFast BMS telemetry' },
  quality_rule_proposer: { title: 'Quality rule proposer', about: 'Proposes rules from profile and anomaly findings' },
  rule_executor: { title: 'Rule executor', about: 'Runs an approved rule; can dry-run quarantine' },
  algolia_search: { title: 'Algolia search', about: 'Searches datasets, rules, alerts, and audit logs' },
  vietnamese_nlp_extractor: { title: 'Vietnamese NLP extractor', about: 'Normalizes teen-code and extracts feedback aspects' },
};

const ACTOR_ALIASES: Record<string, string> = {
  C1: 'C1_AI',
  A1: 'A1_AI',
  L1: 'L1_DETECTOR',
  L2: 'L2_DETECTOR',
  L3: 'L3_DETECTOR',
  L4: 'L4_DETECTOR',
  DATASTEWARD: 'DATA_STEWARD',
  'DATA STEWARD': 'DATA_STEWARD',
  'DATA_STEWARD': 'DATA_STEWARD',
};

const EXPLICIT_ACTOR_NEEDLES = [
  'DATA_STEWARD',
  'DATA STEWARD',
  'EXECUTOR',
  'L4',
  'L3',
  'L2',
  'L1',
  'C1',
  'A1',
  'R0',
] as const;

export function formatSaigonTime(iso?: string | null): string {
  const opts = { hour12: false, timeZone: DEMO_TZ, hour: '2-digit', minute: '2-digit', second: '2-digit' } as const;
  if (!iso) return new Date().toLocaleTimeString('en-GB', opts);
  const trimmed = iso.trim();
  const hasZone = /[zZ]|[+-]\d{2}:?\d{2}$/.test(trimmed);
  const d = new Date(hasZone ? trimmed : trimmed.includes('T') ? `${trimmed}+07:00` : trimmed);
  if (Number.isNaN(d.getTime())) return '';
  return d.toLocaleTimeString('en-GB', opts);
}

export function actorLabel(kind: string | undefined, isVi: boolean): string {
  if (!kind) return isVi ? 'Không rõ' : 'Unknown';
  const key = kind.toUpperCase().replace(/\s+/g, '_');
  const mapped = ACTOR_ALIASES[kind.toUpperCase()] || ACTOR_ALIASES[key] || key;
  const row = ACTOR_LABELS[mapped];
  if (row) return isVi ? row.vi : row.en;
  return kind;
}

export const TRACE_ACTOR_BY_TOOL: Record<string, 'Profiler' | 'Proposer' | 'Repair' | 'Benchmark'> = {
  profile_dataset: 'Profiler',
  data_profiler: 'Profiler',
  list_tables: 'Profiler',
  propose_quality_rules: 'Proposer',
  quality_rule_proposer: 'Proposer',
  propose_patches: 'Repair',
  apply_patches: 'Repair',
  benchmark_dataset: 'Benchmark',
};
const ZONE_NOT_CHIP = new Set(['quarantine']);
export function lastToolSegment(name?: string | null): string {
  if (!name) return '';
  const raw = String(name).trim();
  if (!raw) return '';
  const parts = raw.split(/[/\\.]/).filter(Boolean);
  return (parts[parts.length - 1] || raw).toLowerCase();
}
function chipForToolSegment(seg: string): string | undefined {
  if (!seg || seg === 'clean_database') return undefined;
  if (ZONE_NOT_CHIP.has(seg)) return undefined;
  return TRACE_ACTOR_BY_TOOL[seg];
}
/** Chip from tool_name, then action, then actor_kind. Quarantine is a zone unless nothing else to name. */
export function actorChipFromTrace(
  raw: { tool_name?: string | null; tool?: string | null; action?: string | null; actor_kind?: string | null },
  isVi: boolean,
): string {
  const fromTool = chipForToolSegment(lastToolSegment(raw.tool_name || raw.tool));
  if (fromTool) return fromTool;
  const fromAction = chipForToolSegment(lastToolSegment(raw.action));
  if (fromAction) return fromAction;
  if (raw.actor_kind) {
    const kindSeg = lastToolSegment(raw.actor_kind);
    const fromKind = chipForToolSegment(kindSeg);
    if (fromKind) return fromKind;
    if (ZONE_NOT_CHIP.has(kindSeg)) return 'Quarantine';
    return actorLabel(String(raw.actor_kind), isVi);
  }
  const leftover = lastToolSegment(raw.tool_name || raw.tool || raw.action);
  if (ZONE_NOT_CHIP.has(leftover)) return 'Quarantine';
  return actorLabel(undefined, isVi);
}

export function preferActorKind(raw: Record<string, any>): string | undefined {
  const blob = [raw.actor_kind, raw.agent_type, raw.action, raw.tool, raw.tool_name]
    .filter(Boolean)
    .join(' ')
    .toUpperCase();
  for (const needle of EXPLICIT_ACTOR_NEEDLES) {
    if (blob.includes(needle)) {
      return ACTOR_ALIASES[needle] || needle.replace(' ', '_');
    }
  }
  if (raw.actor_kind) return String(raw.actor_kind);
  if (raw.agent_type && !['canonical_react_engine', 'unknown', ''].includes(String(raw.agent_type).toLowerCase())) {
    return String(raw.agent_type);
  }
  return undefined;
}

export function rangeStart(filter: TimeFilter, now = Date.now()): Date {
  const d = new Date(now);
  switch (filter) {
    case '3d':
      return new Date(now - 3 * 86400000);
    case '7d':
      return new Date(now - 7 * 86400000);
    case 'This Week': {
      const day = d.getDay();
      const offset = day === 0 ? 6 : day - 1;
      return new Date(d.getFullYear(), d.getMonth(), d.getDate() - offset);
    }
    case 'This Month':
      return new Date(d.getFullYear(), d.getMonth(), 1);
    case 'Today':
    default:
      return new Date(d.getFullYear(), d.getMonth(), d.getDate());
  }
}

export function inTimeRange(iso: string | null | undefined, filter: TimeFilter, now = Date.now()): boolean {
  if (!iso) return true;
  const ts = Date.parse(iso);
  if (Number.isNaN(ts)) return true;
  return ts >= rangeStart(filter, now).getTime();
}

export function catalogFor(toolName?: string | null): { name: string; title: string; about: string } | null {
  if (!toolName) return null;
  const row = TOOL_CATALOG[toolName] || TOOL_CATALOG[lastToolSegment(toolName)] || null;
  if (!row) return null;
  return { name: lastToolSegment(toolName) || toolName, title: row.title, about: row.about };
}


const WAREHOUSE_KEY = 'dt-warehouse';

export function readWarehouseOverlay(): { soc: number; open: number } | null {
  try {
    const raw = sessionStorage.getItem(WAREHOUSE_KEY);
    if (!raw) return null;
    const o = JSON.parse(raw);
    const soc = Number(o?.soc);
    const open = Number(o?.open);
    if (!Number.isFinite(soc) || !Number.isFinite(open)) return null;
    return { soc, open };
  } catch {
    return null;
  }
}

export function writeWarehouseOverlay(soc: number, open: number) {
  try { sessionStorage.setItem(WAREHOUSE_KEY, JSON.stringify({ soc, open })); } catch { /* ignore */ }
}

export function clearWarehouseOverlay() {
  try { sessionStorage.removeItem(WAREHOUSE_KEY); } catch { /* ignore */ }
}

function asRecord(value: unknown): Record<string, any> | null {
  return value && typeof value === 'object' && !Array.isArray(value) ? (value as Record<string, any>) : null;
}

function measuredFromOutput(tool: string, output: unknown, fallbackTitle: string): string {
  const data = asRecord(output) || {};
  const prof = asRecord(data.profile) || {};
  const execRes = asRecord(data.execution_result) || {};
  const merged = { ...prof, ...data, ...execRes };
  const parts: string[] = [];
  const n = (...keys: string[]) => {
    for (const k of keys) {
      const v = merged[k];
      if (typeof v === 'number' && !Number.isNaN(v)) return v;
    }
    return null;
  };
  const live = readWarehouseOverlay();
  const rows = n('total_rows', 'sample_size', 'row_count', 'total_processed');
  const soc = n('warehouse_soc_below_zero') || live?.soc || 0;
  const openN = n('warehouse_open_incidents') || live?.open || 0;
  const cols = n('columns_count');
  const health = n('health_score', 'data_health_score');
  if (rows != null) parts.push(`${rows.toLocaleString()} rows`);
  if (soc) parts.push(`${soc} SoC<0`);
  if (openN) parts.push(`${openN} OPEN`);
  if (soc || openN) parts.push('Critical');
  if (cols != null) parts.push(`${cols} columns`);
  if (health != null && !soc && !openN) parts.push(`health ${health}`);
  if (Array.isArray(data.proposals)) parts.push(`${data.proposals.length} rules`);
  if (execRes.quarantine_count != null) parts.push(`${execRes.quarantine_count} quarantined`);
  if (execRes.clean_count != null) parts.push(`${execRes.clean_count} clean`);
  if (parts.length) return parts.join(' · ');
  return fallbackTitle ? `${fallbackTitle} finished` : tool ? `${tool} finished` : '';
}

export function normalizeStatus(raw?: string | null): string {
  const s = (raw || '').toLowerCase();
  if (s === 'running' || s === 'in_progress') return 'running';
  if (s === 'failed' || s === 'error') return 'failed';
  if (s === 'done' || s === 'completed' || s === 'success' || s === 'finish') return 'done';
  return s;
}

/** Follow course AI LOG redaction (scripts/ai_log_redact.py) for expanded tool I/O. */
export function redactSecrets(value: unknown): string {
  let text = typeof value === 'string' ? value : JSON.stringify(value, null, 2);
  if (!text) return '';
  text = text.replace(/-----BEGIN(?:[A-Z ]+)?PRIVATE KEY-----[\s\S]*?-----END(?:[A-Z ]+)?PRIVATE KEY-----/g, '[REDACTED:pem]');
  text = text.replace(/\bBearer\s+[A-Za-z0-9._\-+/=]{8,}/gi, '[REDACTED:token]');
  text = text.replace(/\bsk-[A-Za-z0-9_-]{20,}/g, '[REDACTED:api_key]');
  text = text.replace(/\b(?:ghp_[A-Za-z0-9]{20,}|gho_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})/g, '[REDACTED:token]');
  text = text.replace(/\bAKIA[0-9A-Z]{16}\b/g, '[REDACTED:api_key]');
  text = text.replace(/\bxox[baprs]-[A-Za-z0-9-]{10,}/g, '[REDACTED:token]');
  text = text.replace(/\beyJhIjoi[A-Za-z0-9+/=_-]{20,}/g, '[REDACTED:token]');
  text = text.replace(/\beyJ[A-Za-z0-9_-]+\.eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+/g, '[REDACTED:jwt]');
  text = text.replace(
    /(\b(?:export\s+)?[A-Za-z_][A-Za-z0-9_]*(?:KEY|TOKEN|SECRET|PASSWORD|PASSWD|CREDENTIAL)[A-Za-z0-9_]*)(\s*[=:]\s*)(["']?)([^\s"']+)(\3)/gi,
    '$1$2$3[REDACTED:secret]$5'
  );
  text = text.replace(/\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b/g, '[REDACTED:email]');
  return text;
}

export function mapTraceStep(raw: Record<string, any>, index: number) {
  const tool_name = raw.tool_name || raw.tool || raw.action || '';
  const catalog = TOOL_CATALOG[tool_name] || null;
  const tool_title = raw.tool_title || catalog?.title || (tool_name ? String(tool_name).replace(/_/g, ' ') : '');
  const tool_about = raw.tool_about || catalog?.about || '';
  const output = raw.output ?? raw.tool_output;
  const storedSummary = typeof raw.summary_done === 'string' ? raw.summary_done.trim() : '';
  const theater = /completed$/i.test(storedSummary) && !/SoC|rows|rules|health/i.test(storedSummary);
  const live = readWarehouseOverlay();
  const liveFaults = !!(live && (live.soc > 0 || live.open > 0));
  const storedHasSampleHealth = /health\s+\d/.test(storedSummary);
  const reuseStored = !theater && !!storedSummary && !(storedHasSampleHealth && liveFaults);
  const summary_done = reuseStored ? storedSummary : measuredFromOutput(tool_name, output, tool_title);
  const thoughtRaw = typeof (raw as any).safe_summary === 'string' && (raw as any).safe_summary.trim()
    ? (raw as any).safe_summary.trim()
    : (typeof raw.thought === 'string' ? raw.thought.trim() : '');
  const status = normalizeStatus(raw.status) || (output == null && !summary_done ? 'running' : 'done');
  return {
    step: raw.step ?? raw.step_index ?? index + 1,
    action: raw.action || tool_name,
    tool: tool_name,
    tool_name,
    tool_title,
    tool_about,
    input: raw.input ?? raw.tool_input,
    output,
    observation: raw.observation || '',
    summary_done,
    tokens: Number(raw.tokens ?? raw.tokens_used) > 0 ? Number(raw.tokens ?? raw.tokens_used) : null,
    duration_ms: Number(raw.duration_ms) > 0 ? Number(raw.duration_ms) : null,
    timestamp: raw.timestamp || null,
    actor_kind: preferActorKind(raw),
    status,
    safe_summary: thoughtRaw || undefined,
    thought: thoughtRaw || undefined,
    msgId: raw.msgId || raw.msg_id || raw.message_id || undefined,
  };
}

export function formatRelativeTime(timestamp?: string | number | null, isVi: boolean = false): string {
  if (!timestamp) return '';
  let timeMs = typeof timestamp === 'number' ? timestamp : Date.parse(String(timestamp));
  if (isNaN(timeMs)) {
    if (typeof timestamp === 'string' && /^\d{2}:\d{2}(:\d{2})?$/.test(timestamp.trim())) {
      const today = new Date();
      const parts = timestamp.trim().split(':').map(Number);
      today.setHours(parts[0] || 0, parts[1] || 0, parts[2] || 0, 0);
      timeMs = today.getTime();
    } else {
      return String(timestamp);
    }
  }
  const diffSec = Math.max(0, Math.floor((Date.now() - timeMs) / 1000));
  if (diffSec < 45) {
    return isVi ? 'vừa xong' : 'just now';
  }
  if (diffSec < 3600) {
    const m = Math.floor(diffSec / 60);
    return isVi ? `${m} phút trước` : `${m} min ago`;
  }
  if (diffSec < 86400) {
    const h = Math.floor(diffSec / 3600);
    return isVi ? `${h} giờ trước` : `${h}h ago`;
  }
  const d = Math.floor(diffSec / 86400);
  return isVi ? `${d} ngày trước` : `${d} days ago`;
}
