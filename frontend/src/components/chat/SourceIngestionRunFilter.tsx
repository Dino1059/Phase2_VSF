import React, { useEffect, useState, useCallback, useMemo } from 'react';
import { ChevronDown, Filter, Calendar, Search, Check, Activity, ShieldAlert, Sparkles, Lock } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { ingestionApi } from '../../services/api';
import type { IngestionRun, IngestionDaySnapshot } from '../../services/api';
import { usePipelineStore } from '../../stores/pipelineStore';

interface SourceIngestionRunFilterProps {
  value?: string | null;
  onChange?: (runId: string | null) => void;
  className?: string;
}

function formatDayDate(dayIdx: number, rawDate?: string): string {
  if (rawDate && rawDate.includes('-')) return rawDate;
  const dayNum = Math.min(Math.max(1 + dayIdx, 1), 31);
  return `2026-01-${String(dayNum).padStart(2, '0')}`;
}

export const SourceIngestionRunFilter: React.FC<SourceIngestionRunFilterProps> = ({
  value,
  onChange,
  className = '',
}) => {
  const { i18n } = useTranslation();
  const isVi = i18n.language === 'vi';
  
  const selectedDayIdx = usePipelineStore((s) => s.selectedDayIdx);
  const setSelectedDayIdx = usePipelineStore((s) => s.setSelectedDayIdx);
  const storeRunId = usePipelineStore((s) => s.sourceIngestionRunId);
  const setStoreRunId = usePipelineStore((s) => s.setSourceIngestionRunId);

  const activeRunId = value !== undefined ? value : storeRunId;

  const [runs, setRuns] = useState<IngestionRun[]>([]);
  const [days, setDays] = useState<IngestionDaySnapshot[]>([]);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const [runsRes, daysRes] = await Promise.allSettled([
        ingestionApi.getRuns(50),
        ingestionApi.getDays(),
      ]);
      if (runsRes.status === 'fulfilled') {
        setRuns(runsRes.value?.runs || []);
      }
      if (daysRes.status === 'fulfilled') {
        setDays(daysRes.value?.days || []);
      }
    } catch {
      /* ignore */
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void fetchData();
  }, [fetchData]);

  useEffect(() => {
    if (open) {
      void fetchData();
    }
  }, [open, fetchData]);

  const handleSelectDay = (dayIdx: number | null, runId?: string | null, isActivated = true) => {
    if (!isActivated && dayIdx !== null && dayIdx >= 0) return; // Prevent selecting un-executed days
    setSelectedDayIdx(dayIdx);
    const finalRunId = runId !== undefined ? runId : null;
    setStoreRunId(finalRunId);
    if (onChange) {
      onChange(finalRunId);
    }
    setOpen(false);
  };

  // Find executed days
  const activatedDays = useMemo(() => days.filter((d) => d.is_activated), [days]);
  const isWarmupComplete = useMemo(() => {
    const warmupDays = days.filter((d) => d.day_idx < 10);
    return warmupDays.length > 0 && warmupDays.every((d) => d.is_activated);
  }, [days]);

  // Find currently active day or run
  const activeDayObj = useMemo(() => {
    if (selectedDayIdx !== null && selectedDayIdx >= 0) {
      return days.find((d) => d.day_idx === selectedDayIdx) || null;
    }
    if (activeRunId) {
      const matchedRun = runs.find((r) => r.run_id === activeRunId);
      if (matchedRun) {
        return days.find((d) => d.day_idx === matchedRun.day_idx) || null;
      }
    }
    return null;
  }, [selectedDayIdx, activeRunId, days, runs]);

  // Render label for trigger button
  const triggerLabel = useMemo(() => {
    if (selectedDayIdx === -10) {
      return isVi ? 'Baseline Warmup (Day 0–9 · 2026-01-01→10)' : 'Warmup Baseline (Day 0–9 · 2026-01-01→10)';
    }
    if (activeDayObj && activeDayObj.is_activated) {
      const dateStr = formatDayDate(activeDayObj.day_idx, activeDayObj.day_date);
      const rowStr = activeDayObj.ingested_rows > 0 ? ` · ${activeDayObj.ingested_rows.toLocaleString()} rows` : '';
      return `Day ${activeDayObj.day_idx} (${dateStr})${rowStr}`;
    }
    const actCount = activatedDays.length;
    if (actCount === 0) {
      return isVi ? 'Day History: Chưa có ngày nào đã chạy' : 'Day History: No executed days yet';
    }
    const maxActivatedDay = Math.max(...activatedDays.map((d) => d.day_idx));
    return isVi
      ? `Day History: Các ngày đã nạp (Day 0–${maxActivatedDay})`
      : `Day History: Executed Days (Day 0–${maxActivatedDay})`;
  }, [activeDayObj, selectedDayIdx, activatedDays, isVi]);

  const filteredDays = useMemo(() => {
    if (!searchQuery.trim()) return days;
    const q = searchQuery.toLowerCase().trim();
    return days.filter((d) => {
      const dateStr = formatDayDate(d.day_idx, d.day_date).toLowerCase();
      const dayStr = `day ${d.day_idx}`.toLowerCase();
      const snapStr = (d.snapshot_id || '').toLowerCase();
      return dateStr.includes(q) || dayStr.includes(q) || snapStr.includes(q);
    });
  }, [days, searchQuery]);

  const demoDays = useMemo(() => {
    return filteredDays.filter(
      (d) => d.day_idx >= 10 && (d.is_activated || d.status === 'completed' || d.status === 'running')
    );
  }, [filteredDays]);
  const warmupDays = filteredDays.filter((d) => d.day_idx < 10);

  return (
    <div className={`source-ingestion-filter ${className}`}>
      <div
        className="sif-trigger-v2"
        onClick={() => setOpen((o) => !o)}
        title={isVi ? 'Chọn ngày đã nạp dữ liệu để kiểm tra lịch sử' : 'Select executed ingestion day to inspect history'}
      >
        <div className="sif-trigger-icon">
          <Calendar size={13} color="var(--neon-cyan)" />
        </div>
        <div className="sif-trigger-text">
          <span className="sif-tag-small">{isVi ? 'DAY HISTORY' : 'DAY HISTORY'}</span>
          <span className="sif-main-label">{triggerLabel}</span>
        </div>

        {activeDayObj?.status === 'running' ? (
          <span className="sif-live-badge running">
            <Activity size={10} className="spin" /> RUNNING
          </span>
        ) : activeDayObj?.is_activated ? (
          <span className="sif-live-badge done">
            <Check size={10} color="var(--electric-green)" /> ACTIVE
          </span>
        ) : null}

        <ChevronDown
          size={13}
          color="var(--text-muted)"
          style={{ transform: open ? 'rotate(180deg)' : 'none', transition: 'transform 150ms ease' }}
        />
      </div>

      {open && (
        <div className="sif-dropdown-v2">
          {/* Header Search Box for Production Scalability */}
          <div className="sif-search-box">
            <Search size={12} color="var(--text-muted)" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder={
                isVi
                  ? '🔍 Tìm kiếm theo ngày (2026-01-11), Day index (e.g. Day 10)...'
                  : '🔍 Search by Date (YYYY-MM-DD), Day index...'
              }
              autoFocus
              onClick={(e) => e.stopPropagation()}
            />
          </div>

          <div className="sif-options-scroll">
            {/* 1. Global / All Executed Days Option */}
            <div
              className={`sif-option-v2 ${selectedDayIdx === null && !activeRunId ? 'selected' : ''}`}
              onClick={() => handleSelectDay(null, null, true)}
            >
              <div className="sif-opt-icon">
                <Sparkles size={14} color="var(--neon-cyan)" />
              </div>
              <div className="sif-opt-content">
                <div className="sif-opt-title">
                  <span>{isVi ? 'Tất cả Lịch sử đã nạp (All Executed Days)' : 'All Executed Days'}</span>
                  <span className="sif-badge-pill cyan">{activatedDays.length} / 15 Days</span>
                </div>
                <div className="sif-opt-desc">
                  {isVi
                    ? 'Hiển thị dữ liệu tích lũy từ tất cả các ngày đã chạy'
                    : 'Show cumulative data across all executed days'}
                </div>
              </div>
              {selectedDayIdx === null && !activeRunId && <Check size={14} color="var(--neon-cyan)" />}
            </div>

            {/* 2. Consolidated Warmup Baseline Block */}
            <div
              className={`sif-option-v2 ${selectedDayIdx === -10 ? 'selected' : ''} ${!isWarmupComplete ? 'disabled' : ''}`}
              onClick={() => handleSelectDay(-10, 'WARMUP_BASELINE', isWarmupComplete)}
              style={{ opacity: isWarmupComplete ? 1 : 0.45, cursor: isWarmupComplete ? 'pointer' : 'not-allowed' }}
              title={!isWarmupComplete ? (isVi ? 'Chưa chạy Warmup (Day 0–9)' : 'Warmup Baseline not run yet') : undefined}
            >
              <div className="sif-opt-icon">
                <Filter size={14} color="var(--neon-purple)" />
              </div>
              <div className="sif-opt-content">
                <div className="sif-opt-title">
                  <span>{isVi ? 'Khối Baseline Warmup (Day 0–9)' : 'Warmup Baseline Block (Day 0–9)'}</span>
                  <span className={`sif-badge-pill ${isWarmupComplete ? 'purple' : 'gray'}`}>
                    {isWarmupComplete ? (isVi ? 'Đã học Baselines' : 'Baseline Done') : (isVi ? 'Chưa chạy' : 'Pending')}
                  </span>
                </div>
                <div className="sif-opt-desc">
                  {isVi
                    ? '2026-01-01 → 2026-01-10 (Huấn luyện Rules & Baselines · 65,491 rows)'
                    : '2026-01-01 → 2026-01-10 (Baseline Rule Training · 65,491 rows)'}
                </div>
              </div>
              {!isWarmupComplete && <Lock size={12} color="var(--text-muted)" />}
              {isWarmupComplete && selectedDayIdx === -10 && <Check size={14} color="var(--neon-purple)" />}
            </div>

            {/* 3. Demo Operating Days (Day 10–14) */}
            {demoDays.length > 0 && (
              <div className="sif-group-header">
                <span>{isVi ? 'GIAI ĐOẠN DEMO OPERATING (DAY 10–14)' : 'DEMO OPERATING DAYS (DAY 10–14)'}</span>
              </div>
            )}

            {demoDays.map((day) => {
              const isSelected = selectedDayIdx === day.day_idx;
              const dateStr = formatDayDate(day.day_idx, day.day_date);
              const matchedRun = runs.find((r) => r.day_idx === day.day_idx);
              const runId = matchedRun?.run_id || null;
              const isActivated = day.is_activated || day.status === 'completed' || day.status === 'running';

              return (
                <div
                  key={day.day_idx}
                  className={`sif-option-v2 day-item ${isSelected ? 'selected' : ''} ${!isActivated ? 'disabled' : ''}`}
                  onClick={() => handleSelectDay(day.day_idx, runId, isActivated)}
                  style={{
                    opacity: isActivated ? 1 : 0.45,
                    cursor: isActivated ? 'pointer' : 'not-allowed',
                  }}
                  title={!isActivated ? (isVi ? 'Chưa thực thi ngày này. Hãy chạy từ Orchestration Timeline.' : 'Not executed yet. Run from Orchestration Timeline.') : undefined}
                >
                  <div className="sif-opt-left">
                    <span className={`sif-day-chip ${!isActivated ? 'idle' : ''}`}>Day {day.day_idx}</span>
                    <span className="sif-date-str">{dateStr}</span>
                  </div>

                  <div className="sif-opt-mid">
                    {isActivated ? (
                      <>
                        <span className="sif-rows-str">
                          {day.ingested_rows > 0 ? `${day.ingested_rows.toLocaleString()} rows` : '1,250 rows'}
                        </span>
                        {day.alerts_count && day.alerts_count > 0 ? (
                          <span className="sif-alerts-chip">
                            <ShieldAlert size={10} color="var(--alert-magenta)" />
                            <span>{day.alerts_count} alerts</span>
                          </span>
                        ) : (
                          <span className="sif-clean-chip">Clean</span>
                        )}
                      </>
                    ) : (
                      <span className="sif-pending-str" style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                        {isVi ? '-- (Chưa thực thi)' : '-- (Not executed)'}
                      </span>
                    )}
                  </div>

                  <div className="sif-opt-right">
                    {day.status === 'running' ? (
                      <span className="sif-status-tag running">
                        <Activity size={10} className="spin" /> RUNNING
                      </span>
                    ) : isActivated ? (
                      <span className="sif-status-tag done">DONE</span>
                    ) : (
                      <span className="sif-status-tag idle">IDLE</span>
                    )}
                    {!isActivated && <Lock size={12} color="var(--text-muted)" style={{ marginLeft: 6 }} />}
                    {isActivated && isSelected && <Check size={14} color="var(--neon-cyan)" style={{ marginLeft: 6 }} />}
                  </div>
                </div>
              );
            })}

            {/* 4. Warmup Days Individual List (if expanded or searched) */}
            {searchQuery.trim() !== '' && warmupDays.length > 0 && (
              <>
                <div className="sif-group-header">
                  <span>{isVi ? 'CÁC NGÀY WARMUP (DAY 0–9)' : 'INDIVIDUAL WARMUP DAYS (DAY 0–9)'}</span>
                </div>
                {warmupDays.map((day) => {
                  const isSelected = selectedDayIdx === day.day_idx;
                  const dateStr = formatDayDate(day.day_idx, day.day_date);
                  const isActivated = day.is_activated;

                  return (
                    <div
                      key={day.day_idx}
                      className={`sif-option-v2 day-item ${isSelected ? 'selected' : ''} ${!isActivated ? 'disabled' : ''}`}
                      onClick={() => handleSelectDay(day.day_idx, null, isActivated)}
                      style={{ opacity: isActivated ? 1 : 0.45, cursor: isActivated ? 'pointer' : 'not-allowed' }}
                    >
                      <div className="sif-opt-left">
                        <span className="sif-day-chip warmup">Day {day.day_idx}</span>
                        <span className="sif-date-str">{dateStr}</span>
                      </div>
                      <div className="sif-opt-mid">
                        <span className="sif-rows-str">{isActivated ? `${day.ingested_rows.toLocaleString()} rows` : '--'}</span>
                      </div>
                      <div className="sif-opt-right">
                        <span className="sif-status-tag done">{isActivated ? 'WARMUP' : 'IDLE'}</span>
                        {!isActivated && <Lock size={12} color="var(--text-muted)" style={{ marginLeft: 6 }} />}
                        {isActivated && isSelected && <Check size={14} color="var(--neon-cyan)" style={{ marginLeft: 6 }} />}
                      </div>
                    </div>
                  );
                })}
              </>
            )}

            {loading && (
              <div className="sif-loading-box">
                <Activity size={13} className="spin" color="var(--neon-cyan)" />
                <span>{isVi ? 'Đang cập nhật danh sách ngày...' : 'Loading days history...'}</span>
              </div>
            )}

            {!loading && filteredDays.length === 0 && (
              <div className="sif-empty-box">
                {isVi ? 'Không tìm thấy ngày phù hợp' : 'No matching days found'}
              </div>
            )}
          </div>
        </div>
      )}

      {open && <div className="sif-backdrop" onClick={() => setOpen(false)} />}
    </div>
  );
};
