import React from 'react';
import { Database, Play } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { useIngestionState } from '../hooks/useIngestionState';
import { DayTimelineBar } from '../components/ingestion/DayTimelineBar';
import { RealtimeTicker } from '../components/ingestion/RealtimeTicker';
import { RunHistoryTable } from '../components/ingestion/RunHistoryTable';
import { ResetDbButton } from '../components/ingestion/ResetDbButton';
import { QuarantinePanel } from '../components/ingestion/QuarantinePanel';

export const DataIngestionPage: React.FC = () => {
  const { i18n } = useTranslation();
  const isVi = i18n.language === 'vi';

  const {
    demoState,
    timeline,
    runs,
    realtimeStatus,
    latestTick,
    loading,
    error,
    activateDay,
    reset,
    startRealtime,
    stopRealtime,
  } = useIngestionState();

  const currentDay = demoState?.current_day_idx ?? -1;

  return (
    <div className="ingestion-page">
      {/* Page header */}
      <div className="ingestion-page-header">
        <div className="iph-title-group">
          <Database size={20} color="var(--neon-cyan)" />
          <h1 className="iph-title">{isVi ? 'Data Ingestion' : 'Data Ingestion'}</h1>
          <span className="iph-subtitle">
            {isVi
              ? 'Kích hoạt từng ngày · Batch + Realtime monitoring'
              : 'Activate days · Batch + Realtime monitoring'}
          </span>
        </div>
        <div className="iph-actions">
          <ResetDbButton onReset={reset} />
        </div>
      </div>

      {/* Error banner */}
      {error && (
        <div className="ingestion-error-banner">
          <span>{error}</span>
        </div>
      )}

      {/* Loading overlay */}
      {loading && (
        <div className="ingestion-loading-bar">
          <div className="ingestion-loading-progress" />
        </div>
      )}

      {/* Panel A: Day Timeline */}
      <div className="ingestion-panel ingestion-panel-a">
        <div className="panel-card-header">
          <Play size={16} color="var(--neon-cyan)" />
          <h2>{isVi ? 'Timeline 15 Ngày' : '15-Day Timeline'}</h2>
          <span className="panel-hint">
            {isVi
              ? 'Bấm ngày Demo (10–14) để kích hoạt batch + realtime'
              : 'Click Demo days (10–14) to activate batch + realtime'}
          </span>
        </div>
        <DayTimelineBar
          timeline={timeline}
          currentDayIdx={currentDay}
          onActivate={activateDay}
          loading={loading}
        />
      </div>

      {/* Panel C: Realtime Ticker */}
      <div className="ingestion-panel ingestion-panel-c">
        <div className="panel-card-header">
          <Play size={16} color="var(--electric-green)" />
          <h2>{isVi ? 'Realtime Live Ticker' : 'Realtime Live Ticker'}</h2>
        </div>
        <RealtimeTicker
          status={realtimeStatus}
          latestTick={latestTick}
          onStart={startRealtime}
          onStop={stopRealtime}
        />
      </div>

      {/* Panel B: Run History */}
      <div className="ingestion-panel ingestion-panel-b">
        <div className="panel-card-header">
          <Play size={16} color="var(--royal-purple)" />
          <h2>{isVi ? 'Lịch sử Ingestion Runs' : 'Ingestion Run History'}</h2>
        </div>
        <RunHistoryTable runs={runs} loading={loading} />
      </div>

      {/* Panel D: Quarantine */}
      <div className="ingestion-panel ingestion-panel-d">
        <div className="panel-card-header">
          <Play size={16} color="var(--alert-magenta)" />
          <h2>{isVi ? 'Quarantine Panel' : 'Quarantine Panel'}</h2>
        </div>
        <QuarantinePanel table="ev_telemetry" />
      </div>
    </div>
  );
};
