import { useEffect, useState, useCallback, useRef } from 'react';
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

export interface RealtimeTick {
  day_idx: number;
  tick_count: number;
  clean_count: number;
  quarantined_count: number;
  l1_count: number;
  l2_count: number;
  l3_count: number;
  l4_count: number;
  timestamp: string;
}

export interface IngestionState {
  demoState: IngestionDemoState | null;
  timeline: IngestionDayTimeline | null;
  runs: IngestionRun[];
  realtimeStatus: RealtimeStatus | null;
  latestTick: RealtimeTick | null;
  loading: boolean;
  error: string | null;
  // Actions
  refetchAll: () => Promise<void>;
  activateDay: (dayIdx: number, forceReplay?: boolean) => Promise<void>;
  reset: () => Promise<void>;
  startRealtime: () => Promise<void>;
  stopRealtime: () => Promise<void>;
  // Raw fetchers
  fetchTimeline: () => Promise<void>;
  fetchRuns: () => Promise<void>;
  fetchRealtimeStatus: () => Promise<void>;
}

const POLL_INTERVAL_MS = 3000; // 3s REST fallback

export function useIngestionState(): IngestionState {
  const [demoState, setDemoState] = useState<IngestionDemoState | null>(null);
  const [timeline, setTimeline] = useState<IngestionDayTimeline | null>(null);
  const [runs, setRuns] = useState<IngestionRun[]>([]);
  const [realtimeStatus, setRealtimeStatus] = useState<RealtimeStatus | null>(null);
  const [latestTick, setLatestTick] = useState<RealtimeTick | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const pollTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // ── Individual fetchers ───────────────────────────────────────────────────
  const fetchTimeline = useCallback(async () => {
    try {
      const res = await ingestionApi.getDays();
      setTimeline(res);
    } catch {
      /* ignore poll errors silently */
    }
  }, []);

  const fetchRuns = useCallback(async () => {
    try {
      const res = await ingestionApi.getRuns();
      setRuns(res.runs || []);
    } catch {
      /* ignore */
    }
  }, []);

  const fetchRealtimeStatus = useCallback(async () => {
    try {
      const res = await ingestionApi.getRealtimeStatus();
      setRealtimeStatus(res);
    } catch {
      /* ignore */
    }
  }, []);

  const fetchDemoState = useCallback(async () => {
    try {
      const res = await ingestionApi.getStatus();
      setDemoState(res);
    } catch {
      /* ignore */
    }
  }, []);

  const refetchAll = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      await Promise.all([fetchDemoState(), fetchTimeline(), fetchRuns(), fetchRealtimeStatus()]);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [fetchDemoState, fetchTimeline, fetchRuns, fetchRealtimeStatus]);

  // ── Actions ───────────────────────────────────────────────────────────────
  const activateDay = useCallback(async (dayIdx: number, forceReplay = false) => {
    setError(null);
    try {
      await ingestionApi.activateDay(dayIdx, forceReplay);
      await refetchAll();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, [refetchAll]);

  const reset = useCallback(async () => {
    setError(null);
    try {
      await ingestionApi.reset();
      setLatestTick(null);
      await refetchAll();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, [refetchAll]);

  const startRealtime = useCallback(async () => {
    try {
      await ingestionApi.startRealtime();
      await fetchRealtimeStatus();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, [fetchRealtimeStatus]);

  const stopRealtime = useCallback(async () => {
    try {
      await ingestionApi.stopRealtime();
      await fetchRealtimeStatus();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, [fetchRealtimeStatus]);

  // ── WebSocket handler ─────────────────────────────────────────────────────
  const handleTick = useCallback((event: Event) => {
    const detail = (event as CustomEvent<RealtimeTick>).detail;
    if (detail) {
      setLatestTick(detail);
    }
  }, []);

  const handleDayAdvance = useCallback((event: Event) => {
    const detail = (event as CustomEvent<{ new_day: number }>).detail;
    if (detail) {
      setDemoState((prev) =>
        prev ? { ...prev, realtime_active: true, current_day_idx: detail.new_day } : prev
      );
      void fetchTimeline();
    }
  }, [fetchTimeline]);

  const handleError = useCallback((event: Event) => {
    const detail = (event as CustomEvent<{ message: string }>).detail;
    setError(detail?.message || 'Realtime error');
  }, []);

  // ── Setup: initial load + WebSocket + REST poll ───────────────────────────
  useEffect(() => {
    void refetchAll();

    // WebSocket listeners
    window.addEventListener(WS_TICK, handleTick);
    window.addEventListener(WS_DAY_ADVANCE, handleDayAdvance);
    window.addEventListener(WS_ERROR, handleError);

    // REST fallback poll
    pollTimerRef.current = setInterval(async () => {
      await Promise.all([fetchTimeline(), fetchRuns(), fetchRealtimeStatus(), fetchDemoState()]);
    }, POLL_INTERVAL_MS);

    return () => {
      window.removeEventListener(WS_TICK, handleTick);
      window.removeEventListener(WS_DAY_ADVANCE, handleDayAdvance);
      window.removeEventListener(WS_ERROR, handleError);
      if (pollTimerRef.current) clearInterval(pollTimerRef.current);
    };
  }, [refetchAll, handleTick, handleDayAdvance, handleError, fetchTimeline, fetchRuns, fetchRealtimeStatus, fetchDemoState]);

  return {
    demoState,
    timeline,
    runs,
    realtimeStatus,
    latestTick,
    loading,
    error,
    refetchAll,
    activateDay,
    reset,
    startRealtime,
    stopRealtime,
    fetchTimeline,
    fetchRuns,
    fetchRealtimeStatus,
  };
}
