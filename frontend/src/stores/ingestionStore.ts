import { create } from 'zustand';
import { ingestionApi } from '../services/api';
import type {
  IngestionDemoState,
  IngestionDayTimeline,
  IngestionRun,
  RealtimeStatus,
} from '../services/api';

// ── WebSocket event constants ──────────────────────────────────────────────────
const WS_TICK = 'datatrust:realtime-tick';
const WS_DAY_ADVANCE = 'datatrust:realtime-day-advanced';
const WS_ERROR = 'datatrust:realtime-error';

export interface RealtimeSample {
  vin: string;
  battery_temp: number;
  soc: number;
  status: string;
}

export interface RealtimeTick {
  day_idx: number;
  tick_count: number;
  rows_processed?: number;
  read_cursor?: number;
  total_day_rows?: number;
  clean_count?: number;
  quarantined_count?: number;
  clean_total?: number;
  quarantined_total?: number;
  l1_count?: number;
  l2_count?: number;
  l3_count?: number;
  l4_count?: number;
  l1_total?: number;
  l2_total?: number;
  l3_total?: number;
  l4_total?: number;
  throughput_eps?: number;
  recent_samples?: RealtimeSample[];
  timestamp: string;
}

export type E2EStage = 'idle' | 'ingesting' | 'batch_analyzing' | 'evaluating_rules' | 'starting_realtime' | 'completed' | 'failed';

export interface IngestionStateStore {
  demoState: IngestionDemoState | null;
  timeline: IngestionDayTimeline | null;
  runs: IngestionRun[];
  realtimeStatus: RealtimeStatus | null;
  latestTick: RealtimeTick | null;
  loading: boolean;
  error: string | null;
  executionStage: E2EStage;
  activeDayIdx: number | null;

  // Actions
  refetchAll: () => Promise<void>;
  activateDay: (dayIdx: number, forceReplay?: boolean) => Promise<void>;
  runWarmup: () => Promise<void>;
  reset: () => Promise<void>;
  startRealtime: () => Promise<void>;
  stopRealtime: () => Promise<void>;
  fetchTimeline: () => Promise<void>;
  fetchRuns: () => Promise<void>;
  fetchRealtimeStatus: () => Promise<void>;
  fetchDemoState: () => Promise<void>;
  setExecutionStage: (stage: E2EStage) => void;
  setActiveDayIdx: (dayIdx: number | null) => void;
  initWebSocketAndPolling: () => () => void;
}

let isWsInitialized = false;

export const useIngestionStore = create<IngestionStateStore>((set, get) => ({
  demoState: null,
  timeline: null,
  runs: [],
  realtimeStatus: null,
  latestTick: null,
  loading: false,
  error: null,
  executionStage: 'idle',
  activeDayIdx: null,

  setExecutionStage: (stage) => set({ executionStage: stage }),
  setActiveDayIdx: (activeDayIdx) => set({ activeDayIdx }),

  fetchTimeline: async () => {
    try {
      const res = await ingestionApi.getDays();
      set({ timeline: res });
    } catch {
      /* ignore */
    }
  },

  fetchRuns: async () => {
    try {
      const res = await ingestionApi.getRuns();
      set({ runs: res.runs || [] });
    } catch {
      /* ignore */
    }
  },

  fetchRealtimeStatus: async () => {
    try {
      const res = await ingestionApi.getRealtimeStatus();
      set({ realtimeStatus: res });
    } catch {
      /* ignore */
    }
  },

  fetchDemoState: async () => {
    try {
      const res = await ingestionApi.getStatus();
      set({ demoState: res });
    } catch {
      /* ignore */
    }
  },

  refetchAll: async () => {
    set({ loading: true, error: null });
    try {
      const { fetchDemoState, fetchTimeline, fetchRuns, fetchRealtimeStatus } = get();
      await Promise.all([fetchDemoState(), fetchTimeline(), fetchRuns(), fetchRealtimeStatus()]);
    } catch (e) {
      set({ error: e instanceof Error ? e.message : String(e) });
    } finally {
      set({ loading: false });
    }
  },

  activateDay: async (dayIdx: number, forceReplay = false) => {
    set({ error: null, activeDayIdx: dayIdx, executionStage: 'ingesting' });
    try {
      await ingestionApi.activateDay(dayIdx, forceReplay);
      await get().refetchAll();
      set({ executionStage: 'completed' });
      window.dispatchEvent(new CustomEvent('datatrust:day-activated', { detail: { dayIdx } }));
    } catch (e) {
      set({ executionStage: 'failed', error: e instanceof Error ? e.message : String(e) });
    } finally {
      setTimeout(() => {
        set({ executionStage: 'idle', activeDayIdx: null });
      }, 4000);
    }
  },

  runWarmup: async () => {
    set({ error: null, activeDayIdx: 9, executionStage: 'ingesting' });
    try {
      await ingestionApi.activateWarmup();
      await get().refetchAll();
      set({ executionStage: 'completed' });
      window.dispatchEvent(new CustomEvent('datatrust:day-activated', { detail: { dayIdx: 9 } }));
    } catch (e) {
      set({ executionStage: 'failed', error: e instanceof Error ? e.message : String(e) });
    } finally {
      setTimeout(() => {
        set({ executionStage: 'idle', activeDayIdx: null });
      }, 4000);
    }
  },

  reset: async () => {
    set({ error: null });
    try {
      await ingestionApi.reset();
      set({ latestTick: null });
      await get().refetchAll();
    } catch (e) {
      set({ error: e instanceof Error ? e.message : String(e) });
    }
  },

  startRealtime: async () => {
    try {
      await ingestionApi.startRealtime();
      await get().fetchRealtimeStatus();
    } catch (e) {
      set({ error: e instanceof Error ? e.message : String(e) });
    }
  },

  stopRealtime: async () => {
    try {
      await ingestionApi.stopRealtime();
      await get().fetchRealtimeStatus();
    } catch (e) {
      set({ error: e instanceof Error ? e.message : String(e) });
    }
  },

  initWebSocketAndPolling: () => {
    if (isWsInitialized) return () => {};
    isWsInitialized = true;

    void get().refetchAll();

    const handleTick = (event: Event) => {
      const detail = (event as CustomEvent<RealtimeTick>).detail;
      if (detail) {
        set((state) => ({
          latestTick: detail,
          realtimeStatus: state.realtimeStatus
            ? {
                ...state.realtimeStatus,
                active: true,
                current_day_idx: detail.day_idx ?? state.realtimeStatus.current_day_idx,
                tick_count: detail.tick_count ?? state.realtimeStatus.tick_count + 1,
                last_tick_at: detail.timestamp || new Date().toISOString(),
                status: 'running',
                message: 'Realtime streaming active',
                total_day_rows: detail.total_day_rows ?? state.realtimeStatus.total_day_rows,
                read_cursor: detail.read_cursor ?? state.realtimeStatus.read_cursor,
                clean_total: detail.clean_total ?? state.realtimeStatus.clean_total,
                quarantined_total: detail.quarantined_total ?? state.realtimeStatus.quarantined_total,
                l1_total: detail.l1_total ?? state.realtimeStatus.l1_total,
                l2_total: detail.l2_total ?? state.realtimeStatus.l2_total,
                l3_total: detail.l3_total ?? state.realtimeStatus.l3_total,
                l4_total: detail.l4_total ?? state.realtimeStatus.l4_total,
              }
            : null,
        }));
      }
    };

    const handleDayAdvance = (event: Event) => {
      const detail = (event as CustomEvent<{ new_day: number }>).detail;
      if (detail && detail.new_day !== undefined) {
        set((state) => ({
          demoState: state.demoState
            ? { ...state.demoState, realtime_active: true, current_day_idx: detail.new_day }
            : state.demoState,
          realtimeStatus: state.realtimeStatus
            ? { ...state.realtimeStatus, current_day_idx: detail.new_day, read_cursor: 0, tick_count: 0 }
            : state.realtimeStatus,
        }));
        void get().fetchTimeline();
        void get().fetchRealtimeStatus();
      }
    };

    const handleError = (event: Event) => {
      const detail = (event as CustomEvent<{ message: string }>).detail;
      set({ error: detail?.message || 'Realtime error' });
    };

    const handleAgentTrace = (event: Event) => {
      const detail = (event as CustomEvent<any>).detail;
      const thought = String(detail?.thought || detail?.data?.thought || '');
      if (thought.includes('Stage 1: Profiling') || thought.includes('Day Ingest') || thought.includes('Ingest Snapshot')) {
        set({ executionStage: 'ingesting' });
      } else if (thought.includes('Stage 2: Anomaly') || thought.includes('Anomaly Detect') || thought.includes('Orchestrator Run') || thought.includes('Incident Fusion')) {
        set({ executionStage: 'batch_analyzing' });
      } else if (thought.includes('Stage 4: Rule Proposal') || thought.includes('Rule Proposal') || thought.includes('quality rule')) {
        set({ executionStage: 'evaluating_rules' });
      } else if (thought.includes('Analysis Complete') || thought.includes('Batch End') || thought.includes('Realtime Stream') || thought.includes('warmup_completed')) {
        set({ executionStage: 'starting_realtime' });
      }
    };

    const handlePipelineCompleted = (event: Event) => {
      const detail = (event as CustomEvent<any>).detail;
      void get().refetchAll();
      set({ executionStage: 'completed' });
      window.dispatchEvent(new CustomEvent('datatrust:pipeline-completed-toast', { detail }));
    };

    window.addEventListener(WS_TICK, handleTick);
    window.addEventListener(WS_DAY_ADVANCE, handleDayAdvance);
    window.addEventListener(WS_ERROR, handleError);
    window.addEventListener('datatrust:agent-trace', handleAgentTrace);
    window.addEventListener('datatrust:pipeline-completed', handlePipelineCompleted);

    const pollTimer = setInterval(() => {
      const { fetchTimeline, fetchRuns, fetchRealtimeStatus, fetchDemoState } = get();
      void Promise.all([fetchTimeline(), fetchRuns(), fetchRealtimeStatus(), fetchDemoState()]);
    }, 3000);

    return () => {
      window.removeEventListener(WS_TICK, handleTick);
      window.removeEventListener(WS_DAY_ADVANCE, handleDayAdvance);
      window.removeEventListener(WS_ERROR, handleError);
      window.removeEventListener('datatrust:agent-trace', handleAgentTrace);
      window.removeEventListener('datatrust:pipeline-completed', handlePipelineCompleted);
      clearInterval(pollTimer);
      isWsInitialized = false;
    };
  },
}));
