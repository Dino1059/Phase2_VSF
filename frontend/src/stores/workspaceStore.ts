import { create } from 'zustand';

/** Measured steward beat. msgId / tool_name are how a click jumps back to chat. */
export type WorkspaceTraceBeat = {
  step: number;
  action: string;
  tool?: string;
  tool_name?: string;
  tool_title?: string;
  tool_about?: string;
  input?: unknown;
  output?: unknown;
  observation?: string;
  summary_done?: string;
  tokens?: number | null;
  duration_ms?: number | null;
  timestamp?: string | null;
  actor_kind?: string;
  status?: string;
  thought?: string;
  msgId?: string;
};

export type SplitRows = {
  cleanRows: unknown[];
  quarantineRows: unknown[];
  totalClean: number;
  totalQuarantine: number;
  cleanRan: boolean;
};

const EMPTY_SPLIT: SplitRows = {
  cleanRows: [],
  quarantineRows: [],
  totalClean: 0,
  totalQuarantine: 0,
  cleanRan: false,
};

function beatKey(b: WorkspaceTraceBeat): string {
  return `${b.tool_name || b.tool || b.action || ''}#${b.step}`;
}

export function datasetStoreKey(datasetKey?: string | null, sessionId?: string | null): string {
  if (datasetKey) return datasetKey;
  if (sessionId?.startsWith('dataset:')) return sessionId.slice('dataset:'.length);
  return sessionId || '_';
}

/** sessionStorage / localStorage keys that remember HITL / split / warehouse steward state. */
export const STEWARD_STORAGE_PREFIXES = ['dt-hitl', 'dt-warehouse', 'dt-split', 'dt-snap'] as const;

export function wipeStewardBrowserKeys(): void {
  if (typeof window === 'undefined') return;
  const stores: Storage[] = [];
  try { stores.push(window.sessionStorage); } catch { /* ignore */ }
  try { stores.push(window.localStorage); } catch { /* ignore */ }
  for (const store of stores) {
    const keys: string[] = [];
    for (let i = 0; i < store.length; i += 1) {
      const k = store.key(i);
      if (k) keys.push(k);
    }
    for (const k of keys) {
      if (STEWARD_STORAGE_PREFIXES.some((p) => k === p || k.startsWith(`${p}-`) || k.startsWith(`${p}:`))) {
        store.removeItem(k);
      }
    }
  }
}

interface WorkspaceState {
  tracesByDataset: Record<string, WorkspaceTraceBeat[]>;
  splitRowsByDataset: Record<string, SplitRows>;
  mergeTraces: (datasetKey: string, incoming: WorkspaceTraceBeat[]) => void;
  mergeSplitRows: (datasetKey: string, patch: Partial<SplitRows>) => void;
  resetStewardState: () => void;
}

export const useWorkspaceStore = create<WorkspaceState>((set) => ({
  tracesByDataset: {},
  splitRowsByDataset: {},

  // Empty GET / hidden remount must never replace measured beats.
  mergeTraces: (datasetKey, incoming) =>
    set((state) => {
      const key = datasetKey || '_';
      const prev = state.tracesByDataset[key] || [];
      if (!incoming.length) return state;
      const map = new Map<string, WorkspaceTraceBeat>();
      for (const b of prev) map.set(beatKey(b), b);
      for (const b of incoming) {
        const k = beatKey(b);
        const old = map.get(k);
        map.set(k, old ? { ...old, ...b, msgId: b.msgId || old.msgId } : b);
      }
      const merged = Array.from(map.values()).sort(
        (a, c) => (Number(a.step) || 0) - (Number(c.step) || 0),
      );
      return { tracesByDataset: { ...state.tracesByDataset, [key]: merged } };
    }),

  // Empty GET must never clobber populated clean/quarantine rows.
  mergeSplitRows: (datasetKey, patch) =>
    set((state) => {
      const key = datasetKey || '_';
      const prev = state.splitRowsByDataset[key] || EMPTY_SPLIT;
      const next: SplitRows = { ...prev };
      if (patch.cleanRan) next.cleanRan = true;
      if (Array.isArray(patch.quarantineRows) && patch.quarantineRows.length > 0) {
        next.quarantineRows = patch.quarantineRows;
        next.totalQuarantine = patch.totalQuarantine ?? patch.quarantineRows.length;
        next.cleanRan = true;
      }
      if (Array.isArray(patch.cleanRows) && patch.cleanRows.length > 0) {
        // Only accept clean rows when a clean actually ran — never invent from a raw sample.
        if (patch.cleanRan || next.cleanRan) {
          next.cleanRows = patch.cleanRows;
          next.totalClean = patch.totalClean ?? patch.cleanRows.length;
          next.cleanRan = true;
        }
      }
      if (typeof patch.totalQuarantine === 'number' && patch.totalQuarantine > next.totalQuarantine) {
        next.totalQuarantine = patch.totalQuarantine;
      }
      if (typeof patch.totalClean === 'number' && patch.totalClean > next.totalClean && next.cleanRan) {
        next.totalClean = patch.totalClean;
      }
      return { splitRowsByDataset: { ...state.splitRowsByDataset, [key]: next } };
    }),

  resetStewardState: () => {
    wipeStewardBrowserKeys();
    set({ tracesByDataset: {}, splitRowsByDataset: {} });
  },
}));
