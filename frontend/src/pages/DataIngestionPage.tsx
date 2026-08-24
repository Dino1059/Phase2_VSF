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
    executionStage,
    activeDayIdx,
    activateDay,
    runWarmup,
    reset,
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
              ? 'Timeline 15 Ngày · Điều phối End-to-End Batch + Realtime Stream'
              : '15-Day Timeline · End-to-End Batch + Realtime Stream Orchestration'}
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
      {loading && executionStage === 'idle' && (
        <div className="ingestion-loading-bar">
          <div className="ingestion-loading-progress" />
        </div>
      )}

      {/* Panel A: Day Timeline (Batch Execution) */}
      <div className="ingestion-panel ingestion-panel-a">
        <div className="panel-card-header">
          <Database size={16} color="var(--neon-cyan)" />
          <h2>{isVi ? 'Batch Execution Controls' : 'Batch Execution Controls'}</h2>
        </div>
        <DayTimelineBar
          timeline={timeline}
          currentDayIdx={currentDay}
          onActivate={activateDay}
          onRunWarmup={runWarmup}
          loading={loading}
          executionStage={executionStage}
          activeDayIdx={activeDayIdx}
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
