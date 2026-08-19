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
  DATA_STEWARD: { en: 'Data Steward', vi: 'Data Steward' },
  EXECUTOR: { en: 'Executor', vi: 'Thực thi' },
  SYSTEM: { en: 'System', vi: 'Hệ thống' },
};

export function actorLabel(kind: string | undefined, isVi: boolean): string {
  const key = (kind || 'ORCHESTRATOR').toUpperCase();
  const row = ACTOR_LABELS[key] || ACTOR_LABELS.ORCHESTRATOR;
  return isVi ? row.vi : row.en;
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

export function mapTraceStep(raw: Record<string, any>, index: number) {
  const tool = raw.tool || raw.tool_name || raw.action || '';
  const output = raw.output ?? raw.tool_output;
  const observation = raw.observation || raw.summary_done || '';
  return {
    step: raw.step ?? raw.step_index ?? index + 1,
    action: raw.action || tool,
    tool,
    input: raw.input ?? raw.tool_input,
    output,
    observation,
    summary_done: raw.summary_done || observation || (tool ? `${tool} completed` : ''),
    tokens: raw.tokens ?? raw.tokens_used ?? null,
    duration_ms: raw.duration_ms ?? null,
    timestamp: raw.timestamp || null,
    actor_kind: raw.actor_kind || 'ORCHESTRATOR',
    status: raw.status || 'COMPLETED',
    thought: raw.thought || '',
    msgId: raw.msgId,
  };
}
