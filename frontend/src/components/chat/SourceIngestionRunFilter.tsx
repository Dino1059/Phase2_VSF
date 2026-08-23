import React, { useEffect, useState, useCallback } from 'react';
import { ChevronDown, Filter } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { ingestionApi } from '../../services/api';
import type { IngestionRun } from '../../services/api';

interface SourceIngestionRunFilterProps {
  value: string | null;
  onChange: (runId: string | null) => void;
}

export const SourceIngestionRunFilter: React.FC<SourceIngestionRunFilterProps> = ({
  value,
  onChange,
}) => {
  const { i18n } = useTranslation();
  const isVi = i18n.language === 'vi';
  const [runs, setRuns] = useState<IngestionRun[]>([]);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);

  const fetchRuns = useCallback(async () => {
    setLoading(true);
    try {
      const res = await ingestionApi.getRuns(20);
      setRuns(res.runs || []);
    } catch {
      setRuns([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (open) {
      void fetchRuns();
    }
  }, [open, fetchRuns]);

  const selectedRun = runs.find((r) => r.run_id === value);

  const label = selectedRun
    ? `${selectedRun.run_type} D${selectedRun.day_idx} (${selectedRun.run_id.slice(0, 10)}…)`
    : isVi
      ? 'Tất cả nguồn'
      : 'All sources';

  return (
    <div className="source-ingestion-filter">
      <div className="sif-trigger" onClick={() => setOpen((o) => !o)}>
        <Filter size={12} color="var(--neon-cyan)" />
        <span className="sif-label">{label}</span>
        <ChevronDown
          size={12}
          color="var(--text-muted)"
          style={{ transform: open ? 'rotate(180deg)' : 'none', transition: 'transform 150ms' }}
        />
      </div>

      {open && (
        <div className="sif-dropdown">
          <div className="sif-option" onClick={() => { onChange(null); setOpen(false); }}>
            <span className="sif-option-label">{isVi ? '— Tất cả nguồn —' : '— All sources —'}</span>
          </div>

          {runs.map((run) => (
            <div
              key={run.run_id}
              className={`sif-option ${run.run_id === value ? 'selected' : ''}`}
              onClick={() => { onChange(run.run_id); setOpen(false); }}
            >
              <div className="sif-option-main">
                <span className="sif-kind">{run.run_type}</span>
                <span className="sif-day-chip">D{run.day_idx}</span>
                <span className="sif-status-dot" data-status={run.status} />
                <span className="sif-rows">{run.rows_ingested.toLocaleString()} rows</span>
              </div>
              <div className="sif-option-sub">{run.run_id}</div>
            </div>
          ))}

          {loading && (
            <div className="sif-loading">{isVi ? 'Đang tải...' : 'Loading...'}</div>
          )}

          {!loading && runs.length === 0 && (
            <div className="sif-empty">{isVi ? 'Chưa có runs nào' : 'No runs yet'}</div>
          )}
        </div>
      )}

      {open && <div className="sif-backdrop" onClick={() => setOpen(false)} />}
    </div>
  );
};
