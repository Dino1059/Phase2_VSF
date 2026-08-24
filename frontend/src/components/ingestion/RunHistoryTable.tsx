import React from 'react';
import { CheckCircle, Clock, AlertTriangle, Play, RotateCcw } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import type { IngestionRun } from '../../services/api';

interface RunHistoryTableProps {
  runs: IngestionRun[];
  loading?: boolean;
}

function fmtDuration(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
  return `${(ms / 60000).toFixed(1)}m`;
}

function fmtTime(ts: string): string {
  try {
    return new Date(ts).toLocaleTimeString();
  } catch {
    return ts;
  }
}

const KIND_LABEL: Record<string, { vi: string; en: string; color: string }> = {
  WARMUP_10D: { vi: 'Warmup 10D', en: 'Warmup 10D', color: 'var(--royal-purple)' },
  WARMUP_INGEST: { vi: 'Ingest', en: 'Ingest', color: 'var(--soft-lavender)' },
  WARMUP_BASELINE: { vi: 'Baseline', en: 'Baseline', color: 'var(--royal-purple)' },
  DAILY_PLUS1: { vi: 'Daily +1', en: 'Daily +1', color: 'var(--neon-cyan)' },
  REALTIME_DAILY: { vi: 'Realtime', en: 'Realtime', color: 'var(--electric-green)' },
};

const STATUS_ICON: Record<string, React.ReactNode> = {
  completed: <CheckCircle size={12} color="var(--electric-green)" />,
  running: <Clock size={12} color="var(--warning-amber)" />,
  error: <AlertTriangle size={12} color="var(--alert-magenta)" />,
};

export const RunHistoryTable: React.FC<RunHistoryTableProps> = ({ runs, loading }) => {
  const { i18n } = useTranslation();
  const isVi = i18n.language === 'vi';

  if (loading) {
    return (
      <div className="run-history-loading">
        {[1, 2, 3].map((i) => (
          <div key={i} className="run-history-skeleton" />
        ))}
      </div>
    );
  }

  if (runs.length === 0) {
    return (
      <div className="run-history-empty">
        <Play size={18} color="var(--text-muted)" />
        <span>{isVi ? 'Chưa có lần chạy nào. Kích hoạt ngày đầu tiên!' : 'No runs yet. Activate the first day!'}</span>
      </div>
    );
  }

  return (
    <div className="run-history-table">
      <div className="run-history-header">
        <div className="rh-col rh-col-run-id">{isVi ? 'Run ID' : 'Run ID'}</div>
        <div className="rh-col rh-col-day">{isVi ? 'Ngày' : 'Day'}</div>
        <div className="rh-col rh-col-kind">{isVi ? 'Loại' : 'Kind'}</div>
        <div className="rh-col rh-col-status">{isVi ? 'Trạng thái' : 'Status'}</div>
        <div className="rh-col rh-col-rows">{isVi ? 'Rows' : 'Rows'}</div>
        <div className="rh-col rh-col-viol">{isVi ? 'Vi phạm' : 'Violations'}</div>
        <div className="rh-col rh-col-time">{isVi ? 'Thời gian' : 'Duration'}</div>
        <div className="rh-col rh-col-start">{isVi ? 'Bắt đầu' : 'Started'}</div>
      </div>

      {runs.map((run) => {
        const kind = KIND_LABEL[run.run_type] || { vi: run.run_type, en: run.run_type, color: 'var(--text-muted)' };
        return (
          <div key={run.run_id} className={`run-history-row ${run.status}`}>
            <div className="rh-col rh-col-run-id" title={run.run_id}>
              <code>{run.run_id.slice(0, 12)}…</code>
            </div>
            <div className="rh-col rh-col-day">
              <span className="day-chip">
                {run.day_idx >= 0 ? `D${run.day_idx}` : '—'}
              </span>
            </div>
            <div className="rh-col rh-col-kind">
              <span className="kind-badge" style={{ color: kind.color }}>
                {isVi ? kind.vi : kind.en}
              </span>
            </div>
            <div className="rh-col rh-col-status">
              <span className="status-cell">
                {STATUS_ICON[run.status] || <RotateCcw size={12} color="var(--text-muted)" />}
                <span>{run.status}</span>
              </span>
            </div>
            <div className="rh-col rh-col-rows">{run.rows_ingested.toLocaleString()}</div>
            <div className="rh-col rh-col-viol">
              {run.violations_detected > 0 ? (
                <span className="viol-badge">{run.violations_detected}</span>
              ) : (
                <span className="no-viol">0</span>
              )}
            </div>
            <div className="rh-col rh-col-time">{fmtDuration(run.duration_ms)}</div>
            <div className="rh-col rh-col-start">{fmtTime(run.started_at)}</div>
          </div>
        );
      })}
    </div>
  );
};
