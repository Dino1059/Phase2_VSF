import React, { useEffect, useRef } from 'react';
import { Activity, Radio, Pause, Play } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import type { RealtimeStatus, RealtimeTick } from '../../hooks/useIngestionState';

interface RealtimeTickerProps {
  status: RealtimeStatus | null;
  latestTick: RealtimeTick | null;
  onStart: () => void;
  onStop: () => void;
}

export const RealtimeTicker: React.FC<RealtimeTickerProps> = ({
  status,
  latestTick,
  onStart,
  onStop,
}) => {
  const { i18n } = useTranslation();
  const isVi = i18n.language === 'vi';
  const prevTickRef = useRef<number>(0);
  const dotRef = useRef<HTMLSpanElement>(null);

  const isRunning = status?.active || status?.status === 'running';
  const tickCount = status?.tick_count ?? 0;
  const currentDay = status?.current_day_idx ?? latestTick?.day_idx ?? -1;

  // Pulse animation on new tick
  useEffect(() => {
    if (tickCount > prevTickRef.current && dotRef.current) {
      dotRef.current.classList.remove('tick-pulse');
      void dotRef.current.offsetWidth; // reflow
      dotRef.current.classList.add('tick-pulse');
    }
    prevTickRef.current = tickCount;
  }, [tickCount]);

  const cleanCount = latestTick?.clean_count ?? 0;
  const quarCount = latestTick?.quarantined_count ?? 0;
  const l1 = latestTick?.l1_count ?? 0;
  const l2 = latestTick?.l2_count ?? 0;
  const l3 = latestTick?.l3_count ?? 0;
  const l4 = latestTick?.l4_count ?? 0;

  return (
    <div className={`realtime-ticker-card ${isRunning ? 'running' : 'idle'}`}>
      {/* Header row */}
      <div className="ticker-header">
        <div className="ticker-title">
          <Radio
            size={15}
            color={isRunning ? 'var(--electric-green)' : 'var(--text-muted)'}
          />
          <span className="ticker-label">
            {isVi ? 'Realtime' : 'Realtime'}
            {isRunning && currentDay >= 0 && (
              <span className="ticker-day-badge">
                {isVi ? 'Ngày' : 'Day'} {currentDay}
              </span>
            )}
          </span>
        </div>

        {/* Live status pill */}
        <div className={`live-indicator ${isRunning ? 'active' : ''}`}>
          <span ref={dotRef} className={`live-dot-inner ${isRunning ? 'pulsing' : ''}`} />
          <span className="live-label">
            {isRunning
              ? `${tickCount} ticks`
              : isVi
                ? 'Dừng'
                : 'Stopped'}
          </span>
        </div>

        {/* Start/Stop button */}
        <button
          className={`ticker-ctrl-btn ${isRunning ? 'stop' : 'start'}`}
          onClick={isRunning ? onStop : onStart}
          title={isRunning ? (isVi ? 'Dừng Realtime' : 'Stop Realtime') : (isVi ? 'Bắt đầu Realtime' : 'Start Realtime')}
        >
          {isRunning ? <Pause size={12} /> : <Play size={12} />}
          {isRunning ? (isVi ? 'Dừng' : 'Stop') : (isVi ? 'Chạy' : 'Start')}
        </button>
      </div>

      {/* Counters */}
      <div className="ticker-counters">
        <div className="ticker-count clean">
          <Activity size={12} color="var(--electric-green)" />
          <span className="count-val">{cleanCount.toLocaleString()}</span>
          <span className="count-label">{isVi ? 'sạch' : 'clean'}</span>
        </div>
        <div className="ticker-count quar">
          <Activity size={12} color="var(--alert-magenta)" />
          <span className="count-val">{quarCount.toLocaleString()}</span>
          <span className="count-label">{isVi ? 'cách ly' : 'quarantine'}</span>
        </div>
        <div className="ticker-divider" />
        <div className="ticker-count l1"><span className="layer-badge l1">L1</span><span className="count-val">{l1}</span></div>
        <div className="ticker-count l2"><span className="layer-badge l2">L2</span><span className="count-val">{l2}</span></div>
        <div className="ticker-count l3"><span className="layer-badge l3">L3</span><span className="count-val">{l3}</span></div>
        <div className="ticker-count l4"><span className="layer-badge l4">L4</span><span className="count-val">{l4}</span></div>
      </div>

      {/* Last tick time */}
      {status?.last_tick_at && (
        <div className="ticker-last-tick">
          {isVi ? 'Tick cuối:' : 'Last tick:'} {new Date(status.last_tick_at).toLocaleTimeString()}
        </div>
      )}

      {/* Idle message */}
      {!isRunning && (
        <div className="ticker-idle-msg">
          {isVi
            ? 'Nhấn "Chạy" để bắt đầu realtime monitoring'
            : 'Press "Start" to begin realtime monitoring'}
        </div>
      )}
    </div>
  );
};
