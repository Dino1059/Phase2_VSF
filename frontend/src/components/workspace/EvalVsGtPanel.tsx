import React, { useEffect, useState } from 'react';
import { FlaskConical, RefreshCw } from 'lucide-react';
import { evaluationApi } from '../../services/api';

function Metric({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div style={{
      background: 'var(--bg-darker)',
      border: '1px solid var(--glass-border)',
      borderRadius: 8,
      padding: '10px 12px',
      minWidth: 140,
    }}>
      <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--text-muted)', letterSpacing: 0.4 }}>{label}</div>
      <div style={{ fontSize: 18, fontWeight: 800, color: 'var(--text-main)', marginTop: 4 }}>{value}</div>
    </div>
  );
}

const pct = (n: number | undefined) => (n == null || Number.isNaN(Number(n)) ? '—' : `${(Number(n) * 100).toFixed(1)}%`);

/** Bind `/evaluation/gt` whether scores live under `batch` or at the top level. */
export function normalizeGtResponse(raw: any): Record<string, any> | null {
  if (!raw || typeof raw !== 'object') return null;
  const batch = raw.batch && typeof raw.batch === 'object'
    ? raw.batch
    : (raw.detection ? raw : null);
  return {
    ...raw,
    pack: raw.pack,
    batch,
    realtime: raw.realtime,
    unanswerable: raw.unanswerable,
    rca_frozen_cases: raw.rca_frozen_cases,
    blockers: raw.blockers,
  };
}

let lastGt: Record<string, any> | null = null;

export const EvalVsGtPanel: React.FC = () => {
  const [data, setData] = useState<any>(lastGt);
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(!lastGt);

  const load = async () => {
    setLoading(true);
    setErr(null);
    const ac = new AbortController();
    const timer = window.setTimeout(() => ac.abort(), 45000);
    try {
      const raw = await evaluationApi.getGt(ac.signal);
      const normalized = normalizeGtResponse(raw);
      if (!normalized) throw new Error('Empty GT response');
      lastGt = normalized;
      setData(normalized);
    } catch (e: any) {
      if (e?.name === 'AbortError') {
        setErr('GT scoring timed out. Retry Refresh.');
      } else {
        setErr(String(e?.message || e));
      }
      if (!lastGt) setData(null);
    } finally {
      window.clearTimeout(timer);
      setLoading(false);
    }
  };

  useEffect(() => { void load(); }, []);

  const batch = data?.batch;
  const rt = data?.realtime;
  const unans = data?.unanswerable;
  const frozen = data?.rca_frozen_cases;
  const incidents = data?.pack?.incidents ?? batch?.detection?.tp ?? '—';
  const hasScores = !!(batch?.detection || batch?.location);

  return (
    <div style={{ padding: 16 }} data-testid="eval-vs-gt">
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <FlaskConical size={16} color="#0284c7" />
          <strong>Eval vs GT</strong>
          <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>
            Ngan pack · LLM-judge off · {incidents} incidents
          </span>
        </div>
        <button type="button" onClick={() => void load()} disabled={loading} style={{
          background: 'none', border: '1px solid var(--glass-border)', borderRadius: 6,
          color: 'var(--text-main)', padding: '4px 8px', cursor: 'pointer',
        }}>
          <RefreshCw size={13} className={loading ? 'spinning' : ''} />
        </button>
      </div>
      {err && <div role="alert" style={{ color: '#dc2626', fontSize: 12, marginBottom: 8 }}>{err}</div>}
      {loading && !hasScores && <div style={{ color: 'var(--text-muted)', fontSize: 12 }}>Scoring GT pack…</div>}
      {!loading && data && !hasScores && (
        <div role="status" style={{ color: 'var(--text-muted)', fontSize: 12 }}>
          GT response had no detection scores.
        </div>
      )}
      {hasScores && (
        <>
          <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', margin: '8px 0 6px' }}>BATCH</div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }} data-testid="eval-gt-metrics">
            <Metric label="DETECTION P" value={pct(batch.detection?.precision)} />
            <Metric label="DETECTION R" value={pct(batch.detection?.recall)} />
            <Metric label="DETECTION F1" value={pct(batch.detection?.f1)} />
            <Metric label="LOCATION" value={pct(batch.location?.accuracy)} />
            <Metric label="TIME (day_idx)" value={pct(batch.time_window?.accuracy)} />
            <Metric label="RCA TOP-1" value={pct(batch.rca?.top1)} />
            <Metric label="RCA TOP-3" value={pct(batch.rca?.top3)} />
            <Metric label="HALLUCINATION FA" value={batch.hallucination?.false_alarms ?? '—'} />
          </div>
          <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', margin: '14px 0 6px' }}>REALTIME</div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
            <Metric label="DETECTION F1" value={pct(rt?.detection?.f1)} />
            <Metric label="LOCATION" value={pct(rt?.location?.accuracy)} />
            <Metric label="RCA TOP-1" value={pct(rt?.rca?.top1)} />
            <Metric label="UNANSWERABLE" value={pct(unans?.accuracy)} />
            <Metric label="FROZEN RCA TOP-1" value={pct(frozen?.top1)} />
          </div>
        </>
      )}
      {(data?.blockers || []).length > 0 && (
        <div style={{ marginTop: 12, fontSize: 11, color: '#d97706' }}>
          {(data.blockers as any[]).map((b) => (
            <div key={b.incident_id}>⚠ {b.incident_id}: {b.reason}</div>
          ))}
        </div>
      )}
    </div>
  );
};
