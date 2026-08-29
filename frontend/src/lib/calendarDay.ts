/** ICT calendar day = jury run_id. Demo epoch 2026-01-01 + day_idx. */

export const DEMO_EPOCH = '2026-01-01';

export function dayIdxToCalendarDay(dayIdx: number | null | undefined): string | null {
  if (dayIdx === null || dayIdx === undefined || Number.isNaN(Number(dayIdx))) return null;
  const idx = Number(dayIdx);
  if (idx === -10) return '2026-01-01';
  const base = new Date(Date.UTC(2026, 0, 1));
  base.setUTCDate(base.getUTCDate() + idx);
  return base.toISOString().slice(0, 10);
}

export function calendarDayToDayIdx(calendarDay: string | null | undefined): number | null {
  const raw = (calendarDay || '').trim().slice(0, 10);
  if (!raw || raw.split('-').length !== 3) return null;
  const [y, m, d] = raw.split('-').map(Number);
  const target = Date.UTC(y, m - 1, d);
  const epoch = Date.UTC(2026, 0, 1);
  return Math.round((target - epoch) / 86400000);
}

export function workspaceHref(datasetKey: string, calendarDay?: string | null, tab?: string, extra?: Record<string, string>): string {
  const q = new URLSearchParams();
  if (datasetKey) q.set('dataset_key', datasetKey);
  if (calendarDay) {
    q.set('day', calendarDay);
    q.set('run_id', calendarDay);
  }
  if (tab) q.set('tab', tab);
  if (extra) {
    for (const [k, v] of Object.entries(extra)) {
      if (v) q.set(k, v);
    }
  }
  return `/workspace?${q.toString()}`;
}

const RULE_PREFIX_TABLE: Record<string, string> = {
  ev_telemetry: 'ev_telemetry',
  vinfast: 'ev_telemetry',
  charging: 'charging_sessions',
  vgreen: 'charging_sessions',
  trip: 'trips',
  xanh: 'trips',
  nlp: 'nlp_feedback',
  vingroup_pilot: 'ev_telemetry',
};

export function tableFromRuleId(ruleId?: string | null, fallback = 'ev_telemetry'): string {
  const raw = String(ruleId || '').toLowerCase();
  for (const [k, table] of Object.entries(RULE_PREFIX_TABLE)) {
    if (raw.includes(k)) return table;
  }
  if (raw.includes('__')) return raw.split('__')[0] || fallback;
  return fallback;
}

export function searchHitWorkspacePath(hit: {
  entity_type?: string;
  key?: string;
  rule_id?: string;
  dataset_key?: string;
  source_table?: string;
  entity_id?: string;
  calendar_day?: string;
}, calendarDay?: string | null): string {
  const day = hit.calendar_day || calendarDay || undefined;
  const typ = String(hit.entity_type || '').toLowerCase();
  const table = hit.dataset_key || hit.source_table || hit.key || tableFromRuleId(hit.rule_id);
  if (typ === 'rule') return workspaceHref(table, day, 'tab-rules', { rule_id: hit.rule_id || '' });
  if (typ === 'quarantine' || typ === 'split') return workspaceHref(table, day, 'tab-split', { rule_id: hit.rule_id || '' });
  if (typ === 'trace' || typ === 'traces') return workspaceHref(table, day, 'tab-traces');
  if (typ === 'incident' || typ === 'alert' || typ === 'vehicle' || typ === 'station') {
    return workspaceHref(table, day, 'tab-split', { entity_id: hit.entity_id || hit.key || '' });
  }
  if (typ === 'dataset') return workspaceHref(hit.key || table, day, 'tab-profiler');
  return workspaceHref(table, day, 'tab-profiler');
}
