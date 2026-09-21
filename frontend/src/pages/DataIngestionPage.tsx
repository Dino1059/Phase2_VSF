import React from 'react';
import { ArrowRight, Database, Play } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import { useIngestionState } from '../hooks/useIngestionState';
import { DayTimelineBar } from '../components/ingestion/DayTimelineBar';
import { RealtimeTicker } from '../components/ingestion/RealtimeTicker';
import { RunHistoryTable } from '../components/ingestion/RunHistoryTable';
import { ResetDbButton } from '../components/ingestion/ResetDbButton';
import { QuarantinePanel } from '../components/ingestion/QuarantinePanel';

export const DataIngestionPage: React.FC = () => {
  const { i18n } = useTranslation();
  const isVi = i18n.language === 'vi';
  const navigate = useNavigate();
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
  const warmupCompleted = demoState?.warmup_completed ?? false;
  const totalDays = timeline?.total_days ?? 15;
  const hasFinishedTimeline = warmupCompleted && currentDay >= totalDays - 1;
  const isRunning = loading || ['ingesting', 'batch_analyzing', 'evaluating_rules', 'starting_realtime'].includes(executionStage);
  const nextDay = Math.min(currentDay + 1, totalDays - 1);
  const nextAction = hasFinishedTimeline
    ? {
        title: isVi ? 'Dữ liệu đã sẵn sàng' : 'Data is ready',
        description: isVi ? 'Tiếp tục sang bước 2 để xem phân tích và sự cố.' : 'Continue to step 2 to inspect analysis and incidents.',
        label: isVi ? 'Sang bước 2: Phân tích' : 'Go to step 2: Analyze',
        run: () => navigate('/workspace'),
      }
    : !warmupCompleted
      ? {
          title: isVi ? 'Bắt đầu với dữ liệu nền' : 'Start with baseline data',
          description: isVi ? 'Nạp 10 ngày đầu để hệ thống học đường cơ sở.' : 'Load the first 10 days so the system can establish a baseline.',
          label: isVi ? 'Nạp 10 ngày đầu' : 'Load first 10 days',
          run: runWarmup,
        }
      : {
          title: isVi ? `Nạp dữ liệu ngày ${nextDay + 1}` : `Load day ${nextDay + 1}`,
          description: isVi ? 'Nạp ngày kế tiếp rồi hệ thống sẽ tự chạy kiểm tra chất lượng.' : 'Load the next day; quality checks will run automatically.',
          label: isVi ? `Chạy ngày ${nextDay + 1}` : `Run day ${nextDay + 1}`,
          run: () => activateDay(nextDay),
        };

  return (
    <div className="ingestion-page">
      <div className="ingestion-page-header">
        <div className="iph-title-group">
          <Database size={20} color="var(--neon-cyan)" />
          <h1 className="iph-title">{isVi ? 'Nạp dữ liệu' : 'Data ingestion'}</h1>
          <span className="iph-subtitle">
            {isVi ? 'Bước 1/3 · Chuẩn bị dữ liệu để phân tích' : 'Step 1 of 3 · Prepare data for analysis'}
          </span>
        </div>
        <div className="iph-actions"><ResetDbButton onReset={reset} /></div>
      </div>

      <section className="ingestion-guide" aria-labelledby="ingestion-next-action">
        <div className="guide-steps" aria-label={isVi ? 'Quy trình xử lý' : 'Processing workflow'}>
          <span className="active"><b>1</b>{isVi ? 'Nạp dữ liệu' : 'Ingest'}</span>
          <span><b>2</b>{isVi ? 'Phân tích' : 'Analyze'}</span>
          <span><b>3</b>{isVi ? 'Duyệt kết quả' : 'Review'}</span>
        </div>
        <div className="guide-next-action">
          <div>
            <span className="guide-eyebrow">{isVi ? 'VIỆC CẦN LÀM TIẾP THEO' : 'NEXT ACTION'}</span>
            <h2 id="ingestion-next-action">{isRunning ? (isVi ? 'Đang xử lý dữ liệu…' : 'Processing data…') : nextAction.title}</h2>
            <p>{isRunning ? (isVi ? 'Vui lòng giữ trang mở. Trạng thái sẽ tự cập nhật.' : 'Keep this page open; status updates automatically.') : nextAction.description}</p>
          </div>
          <button type="button" className="primary-next-button" disabled={isRunning} onClick={nextAction.run}>
            {isRunning ? (isVi ? 'Đang chạy…' : 'Running…') : nextAction.label}
            <ArrowRight size={17} />
          </button>
        </div>
      </section>

      {error && <div className="ingestion-error-banner"><span>{error}</span></div>}
      {loading && executionStage === 'idle' && (
        <div className="ingestion-loading-bar"><div className="ingestion-loading-progress" /></div>
      )}

      <div className="ingestion-panel ingestion-panel-a">
        <div className="panel-card-header">
          <Database size={16} color="var(--neon-cyan)" />
          <h2>{isVi ? 'Tiến độ nạp dữ liệu' : 'Ingestion progress'}</h2>
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

      <div className="ingestion-panel ingestion-panel-c">
        <div className="panel-card-header">
          <Play size={16} color="var(--electric-green)" />
          <h2>{isVi ? 'Dữ liệu thời gian thực' : 'Live data'}</h2>
        </div>
        <RealtimeTicker status={realtimeStatus} latestTick={latestTick} />
      </div>

      <details className="ingestion-panel ingestion-panel-b secondary-disclosure">
        <summary className="panel-card-header">
          <Play size={16} color="var(--royal-purple)" />
          <h2>{isVi ? 'Lịch sử các lần chạy' : 'Run history'}</h2>
          <span>{isVi ? 'Xem chi tiết' : 'View details'}</span>
        </summary>
        <RunHistoryTable runs={runs} loading={loading} />
      </details>

      <details className="ingestion-panel ingestion-panel-d secondary-disclosure">
        <summary className="panel-card-header">
          <Play size={16} color="var(--alert-magenta)" />
          <h2>{isVi ? 'Dữ liệu bị cách ly' : 'Quarantined data'}</h2>
          <span>{isVi ? 'Xem chi tiết' : 'View details'}</span>
        </summary>
        <QuarantinePanel table="ev_telemetry" />
      </details>
    </div>
  );
};
