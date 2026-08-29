import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Play,
  CheckCircle,
  Loader,
  Zap,
  Activity,
  ShieldAlert,
  RotateCcw,
  Check,
  Info,
} from 'lucide-react';
import { useTranslation } from 'react-i18next';
import type { IngestionDayTimeline, IngestionDaySnapshot } from '../../services/api';
import type { E2EStage } from '../../hooks/useIngestionState';
import { usePipelineStore } from '../../stores/pipelineStore';
import { dayIdxToCalendarDay, workspaceHref } from '../../lib/calendarDay';

interface DayTimelineBarProps {
  timeline: IngestionDayTimeline | null;
  currentDayIdx: number;
  onActivate: (dayIdx: number, forceReplay?: boolean) => void;
  onRunWarmup?: () => void;
  loading: boolean;
  executionStage?: E2EStage;
  activeDayIdx?: number | null;
}

export const DayTimelineBar: React.FC<DayTimelineBarProps> = ({
  timeline,
  currentDayIdx,
  onActivate,
  onRunWarmup,
  loading,
  executionStage = 'idle',
  activeDayIdx = null,
}) => {
  const { i18n } = useTranslation();
  const isVi = i18n.language === 'vi';
  const navigate = useNavigate();
  const [activatingDay, setActivatingDay] = useState<number | null>(null);

  const days = timeline?.days || [];
  const warmupDays = days.filter((d) => d.day_idx <= 9);
  const demoDays = days.filter((d) => d.day_idx >= 10);

  const isWarmupComplete = warmupDays.length > 0 && warmupDays.every((d) => d.is_activated);

  const handleActivate = (day: IngestionDaySnapshot) => {
    if (activatingDay !== null || loading) return;
    setActivatingDay(day.day_idx);
    const calendarDay = dayIdxToCalendarDay(day.day_idx);
    usePipelineStore.getState().setSelectedDayIdx(day.day_idx);
    usePipelineStore.getState().setSourceIngestionRunId(calendarDay);
    usePipelineStore.getState().setRunId(calendarDay);
    // Non-blocking activation so execution starts in background & updates global store
    void onActivate(day.day_idx, day.is_activated);
    navigate(workspaceHref('ev_telemetry', calendarDay));
  };

  const handleWarmupClick = async () => {
    if (loading || !onRunWarmup) return;
    setActivatingDay(9);
    usePipelineStore.getState().setSelectedDayIdx(-10);
    try {
      void onRunWarmup();
      navigate('/workspace?dataset_key=ev_telemetry&day=-10');
    } finally {
      setActivatingDay(null);
    }
  };

  const getStageMessage = (stage: E2EStage) => {
    switch (stage) {
      case 'ingesting':
        return isVi
          ? '📥 Bước 1/4: Đang đọc và nạp Landing Snapshot (Parquet)...'
          : '📥 Step 1/4: Ingesting Landing Data Snapshot (Parquet)...';
      case 'batch_analyzing':
        return isVi
          ? '⚙️ Bước 2/4: Đang chạy Batch Pipeline (Profiling + Phân tích Anomaly L1–L4)...'
          : '⚙️ Step 2/4: Running Batch Pipeline (Profiling + Anomaly Detection L1-L4)...';
      case 'evaluating_rules':
        return isVi
          ? '🚨 Bước 3/4: Đang đánh giá Rules & Đẩy cảnh báo Cảnh báo (Alerts)...'
          : '🚨 Step 3/4: Evaluating Rules & Dispatching Alerts...';
      case 'starting_realtime':
        return isVi
          ? '⚡ Bước 4/4: Đang kích hoạt & Đồng bộ Realtime Live Stream Telemetry...'
          : '⚡ Step 4/4: Starting & Syncing Realtime Live Telemetry Stream...';
      case 'completed':
        return isVi
          ? '✅ Đã hoàn thành xử lý End-to-End! Tất cả Batch, Rules, Alerts & Realtime đều sẵn sàng.'
          : '✅ End-to-End Execution Complete! Batch, Rules, Alerts & Realtime Active.';
      case 'failed':
        return isVi
          ? '❌ Xảy ra lỗi trong luồng thực thi ngày.'
          : '❌ Error occurred during day execution.';
      default:
        return null;
    }
  };

  const renderDayRow = (day: IngestionDaySnapshot) => {
    const isCurrentlyRunning = (activatingDay === day.day_idx || activeDayIdx === day.day_idx) && executionStage !== 'idle';
    const isActivated = day.is_activated;
    const isCurrentActiveDay = day.day_idx === currentDayIdx;
    const alertsCount = day.alerts_count || 0;

    return (
      <div
        key={day.day_idx}
        className={`timeline-day-row ${isActivated ? 'activated' : 'idle'} ${
          isCurrentlyRunning ? 'running' : ''
        } ${isCurrentActiveDay ? 'current' : ''}`}
        onClick={() => handleActivate(day)}
      >
        <div className="tdr-left">
          <span className="tdr-day-title">Day {day.day_idx}</span>
          <span className="tdr-rows-text">
            {day.ingested_rows > 0 ? `${day.ingested_rows.toLocaleString()} rows` : (isActivated ? '1,250 rows' : '-- rows')}
          </span>
        </div>

        <div className="tdr-center">
          {isCurrentlyRunning ? (
            <span className="tdc-status-badge running">
              <Loader size={10} className="spin" />
              <span>{isVi ? 'ĐANG CHẠY' : 'RUNNING'}</span>
            </span>
          ) : isActivated ? (
            <span className="tdc-status-badge completed">
              <CheckCircle size={10} color="var(--electric-green)" />
              <span>{isVi ? 'ĐÃ CHẠY' : 'DONE'}</span>
            </span>
          ) : (
            <span className="tdc-status-badge idle">
              <span>{isVi ? 'SẴN SÀNG' : 'READY'}</span>
            </span>
          )}

          {isActivated && alertsCount > 0 && (
            <div className="tdc-alerts-row">
              <ShieldAlert size={11} color="var(--alert-magenta)" />
              <span className="tdc-alerts-count">{alertsCount} alerts</span>
              <div className="tdc-level-pills">
                {day.l1_alerts ? <span className="l-pill l1">L1:{day.l1_alerts}</span> : null}
                {day.l2_alerts ? <span className="l-pill l2">L2:{day.l2_alerts}</span> : null}
                {day.l3_alerts ? <span className="l-pill l3">L3:{day.l3_alerts}</span> : null}
                {day.l4_alerts ? <span className="l-pill l4">L4:{day.l4_alerts}</span> : null}
              </div>
            </div>
          )}

          {isActivated && alertsCount === 0 && (
            <div className="tdc-clean-row">
              <Check size={11} color="var(--electric-green)" />
              <span>Clean</span>
            </div>
          )}

          {isCurrentActiveDay && (
            <span className="tdc-rt-active">
              <span className="live-dot green pulsing" />
              <span>Streaming</span>
            </span>
          )}
        </div>

        <div className="tdr-right">
          <button
            className="tdc-action-btn"
            disabled={isCurrentlyRunning || loading}
            onClick={(e) => {
              e.stopPropagation();
              handleActivate(day);
            }}
            title={isActivated ? (isVi ? 'Kích hoạt lại ngày này' : 'Re-run day') : (isVi ? 'Kích hoạt ngày này' : 'Activate day')}
          >
            {isCurrentlyRunning ? (
              <Loader size={11} className="spin" />
            ) : isActivated ? (
              <RotateCcw size={11} />
            ) : (
              <Play size={11} />
            )}
            <span>{isActivated ? (isVi ? 'Chạy lại' : 'Re-run') : (isVi ? 'Chạy Ngày' : 'Run Day')}</span>
          </button>
        </div>
      </div>
    );
  };

  const warmupTotalRows = warmupDays.reduce((acc, d) => acc + (d.ingested_rows || 0), 0);

  return (
    <div className="ingestion-timeline-bar-v2">
      {/* Simulation Instruction Banner */}
      <div className="timeline-info-banner">
        <Info size={16} color="var(--neon-cyan)" style={{ flexShrink: 0, marginTop: 2 }} />
        <div className="tib-content">
          <p>
            {isVi
              ? '💡 Mô phỏng dữ liệu thực tế: Mỗi Day tương đương 1 ngày vận hành thực tế của hệ thống. Bạn có thể bấm Chạy ở một ngày bất kỳ để trải nghiệm luồng tự động kiểm thử và giám sát chất lượng dữ liệu.'
              : '💡 Real-world data simulation: Each Day represents 1 operational day. Click Run on any day to experience automated ingestion and quality monitoring.'}
          </p>
        </div>
      </div>

      {/* Realtime E2E Execution Progress Stepper */}
      {executionStage !== 'idle' && (
        <div className="timeline-stepper-banner">
          <div className="tsb-header">
            <Activity size={15} className="spin" color="var(--neon-cyan)" />
            <span className="tsb-title">
              {isVi ? `Đang xử lý luồng End-to-End cho Day ${activeDayIdx ?? ''}...` : `Processing End-to-End Flow for Day ${activeDayIdx ?? ''}...`}
            </span>
          </div>

          <div className="tsb-message">{getStageMessage(executionStage)}</div>

          <div className="tsb-steps-bar">
            <div className={`tsb-step ${['ingesting', 'batch_analyzing', 'evaluating_rules', 'starting_realtime', 'completed'].includes(executionStage) ? 'active' : ''}`}>
              <span className="step-num">1</span>
              <span className="step-label">Ingest Snapshot</span>
            </div>
            <div className="tsb-step-divider" />
            <div className={`tsb-step ${['batch_analyzing', 'evaluating_rules', 'starting_realtime', 'completed'].includes(executionStage) ? 'active' : ''}`}>
              <span className="step-num">2</span>
              <span className="step-label">Batch Profiling & Anomaly</span>
            </div>
            <div className="tsb-step-divider" />
            <div className={`tsb-step ${['evaluating_rules', 'starting_realtime', 'completed'].includes(executionStage) ? 'active' : ''}`}>
              <span className="step-num">3</span>
              <span className="step-label">Rules & Alert Dispatch</span>
            </div>
            <div className="tsb-step-divider" />
            <div className={`tsb-step ${['starting_realtime', 'completed'].includes(executionStage) ? 'active' : ''}`}>
              <span className="step-num">4</span>
              <span className="step-label">Realtime Stream Active</span>
            </div>
          </div>
        </div>
      )}

      {/* Section 1: Consolidated Warmup Baseline Block */}
      <div className={`timeline-warmup-compact-card ${isWarmupComplete ? 'completed' : 'pending'}`}>
        <div className="twc-header">
          <div className="twc-title-group">
            <CheckCircle size={18} color={isWarmupComplete ? 'var(--electric-green)' : 'var(--neon-yellow)'} />
            <div>
              <h3>{isVi ? 'Warmup Baseline (Day 0–9)' : 'Warmup Baseline (Day 0–9)'}</h3>
              <p className="twc-subtitle">
                {isVi
                  ? `Khối 10 ngày lịch sử • ${warmupTotalRows > 0 ? warmupTotalRows.toLocaleString() : (isWarmupComplete ? '65,455' : '--')} rows`
                  : `10 Historical Days • ${warmupTotalRows > 0 ? warmupTotalRows.toLocaleString() : (isWarmupComplete ? '65,455' : '--')} rows`}
              </p>
            </div>
          </div>

          <div className="twc-header-actions">
            <span className={`tsc-status-tag ${isWarmupComplete ? 'success' : 'pending'}`}>
              {isWarmupComplete
                ? (isVi ? '✅ Complete' : '✅ Complete')
                : (isVi ? '⏳ Baseline Needed' : '⏳ Baseline Needed')}
            </span>

            {onRunWarmup && (
              <button
                className={`tah-btn tah-warmup-btn ${isWarmupComplete ? 'completed' : 'primary'}`}
                onClick={handleWarmupClick}
                disabled={loading || executionStage !== 'idle'}
              >
                {executionStage !== 'idle' && activeDayIdx === 9 ? (
                  <Loader size={13} className="spin" />
                ) : isWarmupComplete ? (
                  <RotateCcw size={13} />
                ) : (
                  <Zap size={13} color="var(--neon-yellow)" />
                )}
                <span>
                  {isWarmupComplete
                    ? (isVi ? 'Chạy lại' : 'Re-run')
                    : (isVi ? 'Run Warmup' : 'Run Warmup')}
                </span>
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Section 2: Demo Operating Days (Day 10 - 14) */}
      <div className="timeline-section-card demo-section">
        <div className="tsc-header">
          <div className="tsc-title-group">
            <Play size={14} color="var(--neon-cyan)" />
            <h3>{isVi ? 'Demo Operating Days (Day 10–14)' : 'Demo Operating Days (Day 10–14)'}</h3>
          </div>
          <span className="tsc-hint">
            {isVi ? 'Bấm Chạy ở ngày bất kỳ để trải nghiệm' : 'Click Run on any day to start'}
          </span>
        </div>

        <div className="timeline-days-list demo-list">
          {demoDays.map((day) => renderDayRow(day))}
        </div>
      </div>
    </div>
  );
};

