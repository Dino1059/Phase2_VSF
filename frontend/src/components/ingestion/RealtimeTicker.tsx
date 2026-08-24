import React, { useEffect, useRef, useState } from 'react';
import { Activity, Radio, Zap, Cpu, Gauge, Terminal } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import type { RealtimeStatus } from '../../services/api';
import type { RealtimeTick, RealtimeSample } from '../../hooks/useIngestionState';

interface RealtimeTickerProps {
  status: RealtimeStatus | null;
  latestTick: RealtimeTick | null;
}

export const RealtimeTicker: React.FC<RealtimeTickerProps> = ({
  status,
  latestTick,
}) => {
  const { i18n } = useTranslation();
  const isVi = i18n.language === 'vi';
  const prevTickRef = useRef<number>(0);
  const dotRef = useRef<HTMLSpanElement>(null);
  const [samplesFeed, setSamplesFeed] = useState<RealtimeSample[]>([]);

  const tickCount = status?.tick_count ?? latestTick?.tick_count ?? 0;
  const currentDay = status?.current_day_idx ?? latestTick?.day_idx ?? 0;

  // Day progress metrics
  const readCursor = status?.read_cursor ?? latestTick?.read_cursor ?? 0;
  const totalDayRows = status?.total_day_rows ?? latestTick?.total_day_rows ?? 6589;
  const processedPercent = totalDayRows > 0 ? Math.min(100, Math.round((readCursor / totalDayRows) * 100)) : 0;
  const throughput = latestTick?.throughput_eps ?? (status?.active ? 50 : 0);

  // Pulse animation on new tick & append live feed samples
  useEffect(() => {
    if (tickCount > prevTickRef.current) {
      if (dotRef.current) {
        dotRef.current.classList.remove('tick-pulse');
        void dotRef.current.offsetWidth; // reflow
        dotRef.current.classList.add('tick-pulse');
      }
      if (latestTick?.recent_samples && latestTick.recent_samples.length > 0) {
        setSamplesFeed((prev) => [...latestTick.recent_samples!, ...prev].slice(0, 4));
      }
    }
    prevTickRef.current = tickCount;
  }, [tickCount, latestTick]);

  const cleanCount = status?.clean_total ?? latestTick?.clean_total ?? latestTick?.clean_count ?? 0;
  const quarCount = status?.quarantined_total ?? latestTick?.quarantined_total ?? latestTick?.quarantined_count ?? 0;
  const l1 = status?.l1_total ?? latestTick?.l1_total ?? latestTick?.l1_count ?? 0;
  const l2 = status?.l2_total ?? latestTick?.l2_total ?? latestTick?.l2_count ?? 0;
  const l3 = status?.l3_total ?? latestTick?.l3_total ?? latestTick?.l3_count ?? 0;
  const l4 = status?.l4_total ?? latestTick?.l4_total ?? latestTick?.l4_count ?? 0;

  const isStreaming = status?.active || tickCount > 0;

  return (
    <div className={`realtime-ticker-card ${isStreaming ? 'running' : ''}`}>
      {/* Header row */}
      <div className="ticker-header">
        <div className="ticker-title">
          <Radio size={16} className={isStreaming ? 'icon-spin-pulse' : ''} color="var(--electric-green)" />
          <span className="ticker-label">
            {isVi ? 'Realtime Telemetry Stream' : 'Realtime Telemetry Stream'}
            {currentDay >= 0 && (
              <span className="ticker-day-badge">
                ⚡ {isVi ? `Ngày ${currentDay}` : `Day ${currentDay}`}
              </span>
            )}
          </span>
        </div>

        {/* Live status pill */}
        <div className={`live-indicator ${isStreaming ? 'active' : ''}`}>
          <span ref={dotRef} className={`live-dot-inner ${isStreaming ? 'pulsing' : ''}`} />
          <span className="live-label">
            {isStreaming ? (isVi ? 'LIVE STREAMING' : 'LIVE STREAMING') : (isVi ? 'Đang chờ...' : 'Idle')}
          </span>
        </div>
      </div>

      {/* Progress Bar & Ingestion Counter */}
      <div className="ticker-progress-section">
        <div className="progress-metrics-row">
          <span className="pm-label">
            <Zap size={12} color="var(--electric-green)" />
            {isVi ? `Tiến trình Ingestion Ngày ${currentDay}:` : `Day ${currentDay} Ingestion Progress:`}
          </span>
          <span className="pm-values">
            <strong>{readCursor.toLocaleString()}</strong> / {totalDayRows.toLocaleString()} {isVi ? 'bản ghi' : 'rows'}
            <span className="pm-pct"> ({processedPercent}%)</span>
          </span>
        </div>
        <div className="ticker-progress-track">
          <div
            className="ticker-progress-fill"
            style={{ width: `${processedPercent}%` }}
          />
        </div>
      </div>

      {/* Stream Metrics & Equalizer Motion */}
      <div className="ticker-stream-bar">
        <div className="stream-equalizer">
          <span className="eq-bar bar-1" />
          <span className="eq-bar bar-2" />
          <span className="eq-bar bar-3" />
          <span className="eq-bar bar-4" />
          <span className="eq-bar bar-5" />
        </div>
        <div className="stream-stats">
          <span className="stat-pill"><Gauge size={12} color="var(--neon-cyan)" /> {throughput} rec/sec</span>
          <span className="stat-pill"><Cpu size={12} color="var(--royal-purple)" /> Latency: 12ms</span>
          <span className="stat-pill"><Activity size={12} color="var(--electric-green)" /> Tick: #{tickCount}</span>
        </div>
      </div>

      {/* Layer & Quality Counters */}
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

      {/* Live Stream Feed Terminal */}
      <div className="ticker-live-feed">
        <div className="feed-header">
          <Terminal size={12} color="var(--neon-cyan)" />
          <span>{isVi ? 'Stream Telemetry Trực tiếp (Live Event Feed)' : 'Live Telemetry Event Feed'}</span>
        </div>
        <div className="feed-list">
          {samplesFeed.length > 0 ? (
            samplesFeed.map((sample, idx) => (
              <div key={idx} className={`feed-item ${sample.status}`}>
                <span className="feed-time">[{new Date().toLocaleTimeString()}]</span>
                <span className="feed-vin">{sample.vin}</span>
                <span className="feed-detail">Pin: {sample.soc}% | Nhiệt độ: {sample.battery_temp}°C</span>
                <span className={`feed-status-badge ${sample.status}`}>
                  {sample.status === 'clean' ? '✓ CLEAN' : '⚠ FLAG'}
                </span>
              </div>
            ))
          ) : (
            <div className="feed-empty">
              {isStreaming ? (isVi ? 'Đang nhận gói tin dữ liệu mới...' : 'Waiting for incoming telemetry packets...') : (isVi ? 'Stream đang tạm dừng' : 'Stream is idle')}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

