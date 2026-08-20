import { useEffect, useRef, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { systemApi, resetDemoSession } from '../services/api';
import { useAuthStore } from '../stores/authStore';
import { useChatStore } from '../stores/chatStore';
import { PILOT_CLEAN, PILOT_FAULTY, PILOT_BATCH } from './pilotFacts';
import { clearWarehouseOverlay, writeWarehouseOverlay } from './stewardLabels';

function markSnapshotPending(mode: 'happy' | 'unhappy') {
  try { sessionStorage.setItem('dt-snap-pending', mode); } catch { /* ignore */ }
  clearWarehouseOverlay();
  window.dispatchEvent(new CustomEvent('datatrust:demo-snapshot-pending', { detail: { mode } }));
}

export function DemoStoryBar({ isVi }: { isVi: boolean }) {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const story = params.get('story') === 'unhappy' || params.get('demo') === 'live' ? 'unhappy' : 'happy';
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [measured, setMeasured] = useState<{ soc_below_zero: number; open_incidents: number } | null>(null);

  const loaded = useRef<string | null>(null);

  const go = async (mode: 'happy' | 'unhappy') => {
    setBusy(true);
    setErr(null);
    // Instant hold: fire before login/fetch/navigate so leftover Happy 99.1 cannot paint.
    markSnapshotPending(mode);
    try {
      if (!useAuthStore.getState().isAdmin()) {
        await useAuthStore.getState().login('steward', undefined, 'steward');
      }
      const res = await systemApi.loadSnapshot(mode);
      try { sessionStorage.setItem('dt-snap', mode); } catch { /* ignore */ }
      loaded.current = mode;
      await resetDemoSession();
      useChatStore.getState().clearMessages();
      setMeasured({ soc_below_zero: res.soc_below_zero, open_incidents: res.open_incidents });
      writeWarehouseOverlay(res.soc_below_zero, res.open_incidents);
      if (mode === 'happy') {
        navigate('/workspace?dataset_key=vingroup_pilot&story=happy');
      } else {
        navigate('/workspace?dataset_key=vingroup_pilot&demo=live&story=unhappy');
      }
      window.dispatchEvent(new CustomEvent('datatrust:demo-snapshot', {
        detail: { mode, soc_below_zero: res.soc_below_zero, open_incidents: res.open_incidents },
      }));
    } catch (e) {
      setErr(e instanceof Error ? e.message : 'snapshot failed');
    } finally {
      setBusy(false);
    }
  };

  useEffect(() => {
    if (story !== 'happy') {
      loaded.current = null;
      try { sessionStorage.setItem('dt-snap', 'unhappy'); } catch { /* ignore */ }
      return;
    }
    // Reload Happy unless this mount already started go('happy').
    // Do not skip just because leftover dt-snap === 'happy' after Unhappy.
    if (loaded.current === 'happy') return;
    loaded.current = 'happy';
    void go('happy');
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [story]);

  const facts = story === 'happy' ? PILOT_CLEAN : PILOT_FAULTY;
  const soc = measured?.soc_below_zero ?? facts.socBelowZero;
  const open = measured?.open_incidents ?? ('openIncidents' in facts ? facts.openIncidents : 0);

  return (
    <div
      role="group"
      aria-label="Demo story"
      style={{
        margin: '8px 16px 0',
        padding: '10px 12px',
        borderRadius: 8,
        border: '1px solid var(--glass-border)',
        background: 'var(--bg-card)',
        display: 'flex',
        flexWrap: 'wrap',
        gap: 8,
        alignItems: 'center',
        fontSize: 12,
      }}
    >
      <button type="button" className="hud-btn" disabled={busy || story === 'happy'} onClick={() => void go('happy')}>
        {isVi ? 'HAPPY — bản sạch' : 'HAPPY — clean CSVs'}
      </button>
      <button type="button" className="hud-btn" disabled={busy || story === 'unhappy'} onClick={() => void go('unhappy')}>
        {isVi ? 'UNHAPPY — 172 / 8 OPEN' : 'UNHAPPY — 172 SoC / 8 OPEN'}
      </button>
      <span style={{ color: 'var(--text-muted)' }}>
        {busy
          ? (isVi ? 'Đang nạp snapshot…' : 'Loading snapshot…')
          : story === 'happy'
            ? (isVi
              ? `60 VIN · 15 ngày · ${PILOT_CLEAN.telemetry} / ${PILOT_CLEAN.chargingSessions} / ${PILOT_CLEAN.trips} · SoC<0 = ${soc} · OPEN = ${open} · joins OK`
              : `60 VIN · 15 days · ${PILOT_CLEAN.telemetry} / ${PILOT_CLEAN.chargingSessions} / ${PILOT_CLEAN.trips} · SoC<0 = ${soc} · OPEN = ${open} · joins OK`)
            : (isVi
              ? `Faulty: ${PILOT_FAULTY.chargingRows} phiên · SoC<0 = ${soc} · V>1000 = ${PILOT_FAULTY.voltageOver1000} · GPS = ${PILOT_FAULTY.gpsOutsideHanoi} · OPEN = ${open} · ${PILOT_FAULTY.focusIncident}`
              : `Faulty: ${PILOT_FAULTY.chargingRows} sessions · SoC<0 = ${soc} · V>1000 = ${PILOT_FAULTY.voltageOver1000} · GPS = ${PILOT_FAULTY.gpsOutsideHanoi} · OPEN = ${open} · ${PILOT_FAULTY.focusIncident}`)}
      </span>
      <span style={{ color: 'var(--text-muted)' }}>
        {isVi
          ? `Cửa sổ batch ${PILOT_BATCH.windowStart} → ${PILOT_BATCH.windowEnd} · không phải Kafka/live stream`
          : `Batch window ${PILOT_BATCH.windowStart} → ${PILOT_BATCH.windowEnd} · not a live Kafka stream`}
      </span>
      {err && <span role="alert" style={{ color: '#dc2626' }}>{err}</span>}
    </div>
  );
}
