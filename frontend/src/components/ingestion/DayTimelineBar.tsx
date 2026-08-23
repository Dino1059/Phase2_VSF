import React, { useState } from 'react';
import { Play, CheckCircle, Loader, Clock } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import type { IngestionDayTimeline, IngestionDaySnapshot } from '../../services/api';

interface DayTimelineBarProps {
  timeline: IngestionDayTimeline | null;
  currentDayIdx: number;
  onActivate: (dayIdx: number) => void;
  loading: boolean;
}

export const DayTimelineBar: React.FC<DayTimelineBarProps> = ({
  timeline,
  currentDayIdx,
  onActivate,
  loading,
}) => {
  const { t, i18n } = useTranslation();
  const isVi = i18n.language === 'vi';
  const [activatingDay, setActivatingDay] = useState<number | null>(null);

  const days = timeline?.days || [];

  const handleActivate = async (day: IngestionDaySnapshot) => {
    if (day.is_activated || activatingDay !== null) return;
    setActivatingDay(day.day_idx);
    try {
      await onActivate(day.day_idx);
    } finally {
      setActivatingDay(null);
    }
  };

  const getDayStatus = (day: IngestionDaySnapshot) => {
    if (day.is_activated) return 'activated';
    if (day.day_idx <= currentDayIdx) return 'completed';
    return 'idle';
  };

  const warmupDays = days.filter((d) => d.day_idx <= 9);
  const demoDays = days.filter((d) => d.day_idx >= 10);

  return (
    <div className="ingestion-timeline-bar">
      {/* Warmup zone */}
      <div className="timeline-section">
        <div className="timeline-section-label">
          <CheckCircle size={13} color="var(--electric-green)" />
          <span>{isVi ? 'Warmup (Day 0-9)' : 'Warmup (Day 0–9)'}</span>
        </div>
        <div className="timeline-days">
          {warmupDays.map((day) => {
            const status = getDayStatus(day);
            return (
              <div
                key={day.day_idx}
                className={`timeline-day-chip ${status} ${day.is_activated ? 'warmup-done' : ''}`}
                title={`Day ${day.day_idx}${day.is_activated ? ' ✓ activated' : day.is_ingested ? ` (${day.ingested_rows.toLocaleString()} rows)` : ''}`}
              >
                <span className="day-idx">{day.day_idx}</span>
                {day.is_activated && <CheckCircle size={10} color="var(--electric-green)" />}
              </div>
            );
          })}
        </div>
      </div>

      {/* Demo zone */}
      <div className="timeline-section">
        <div className="timeline-section-label">
          <Play size={13} color="var(--neon-cyan)" />
          <span>{isVi ? 'Demo Days (Day 10-14)' : 'Demo Days (Day 10–14)'}</span>
        </div>
        <div className="timeline-days">
          {demoDays.map((day) => {
            const status = getDayStatus(day);
            const isLoading = activatingDay === day.day_idx;
            return (
              <button
                key={day.day_idx}
                className={`timeline-day-chip ${status} demo-btn ${day.is_activated ? 'activated' : ''}`}
                onClick={() => handleActivate(day)}
                disabled={day.is_activated || isLoading || loading}
                title={
                  day.is_activated
                    ? `Day ${day.day_idx} ${isVi ? 'đã kích hoạt' : 'activated'}`
                    : `${isVi ? 'Kích hoạt' : 'Activate'} Day ${day.day_idx}`
                }
              >
                {isLoading ? (
                  <Loader size={11} color="var(--neon-cyan)" className="spin" />
                ) : (
                  <span className="day-idx">{day.day_idx}</span>
                )}
                {day.is_activated && !isLoading && (
                  <CheckCircle size={10} color="var(--electric-green)" />
                )}
              </button>
            );
          })}
        </div>
      </div>

      {/* Next available day */}
      {!loading && timeline && days.filter((d) => !d.is_activated).length > 0 && (
        <div className="timeline-next-hint">
          <Clock size={12} color="var(--text-muted)" />
          <span>
            {isVi
              ? `${days.filter((d) => !d.is_activated).length} ngày còn lại`
              : `${days.filter((d) => !d.is_activated).length} days remaining`}
          </span>
        </div>
      )}
    </div>
  );
};
