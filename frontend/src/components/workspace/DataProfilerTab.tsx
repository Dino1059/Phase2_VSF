import React, { useEffect, useState, useCallback, useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import {
  Activity,
  Search,
  RefreshCw,
  Database,
  BarChart3,
  Hash,
  Layers,
} from 'lucide-react';

import { datasetsApi } from '../../services/api';

interface ColumnProfile {
  name: string;
  dtype?: string;
  type?: string;
  null_count?: number;
  null_pct?: number;
  unique_count?: number;
  min_val?: any;
  max_val?: any;
  mean_val?: any;
  quality_flags?: string[];
  anomalies_count?: number;
}

interface ProfileData {
  dataset?: string;
  total_rows?: number;
  columns_count?: number;
  health_score?: number | null;
  data_health_score?: number;
  warehouse_soc_below_zero?: number;
  warehouse_open_incidents?: number;
  columns?: ColumnProfile[];
  summary?: string;
}

interface DataProfilerTabProps {
  datasetKey?: string;
  story?: string | null;
}

type PendingMode = 'happy' | 'unhappy' | null;

function readPendingMode(): PendingMode {
  try {
    const v = sessionStorage.getItem('dt-snap-pending');
    return v === 'happy' || v === 'unhappy' ? v : null;
  } catch {
    return null;
  }
}

function clearPendingMode() {
  try { sessionStorage.removeItem('dt-snap-pending'); } catch { /* ignore */ }
}

export const DataProfilerTab: React.FC<DataProfilerTabProps> = ({ datasetKey, story }) => {
  const [profile, setProfile] = useState<ProfileData | null>(null);
  const [loading, setLoading] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedColumn, setSelectedColumn] = useState<ColumnProfile | null>(null);
  const [pendingMode, setPendingMode] = useState<PendingMode>(() => readPendingMode());
  const { i18n } = useTranslation('pipeline');
  const isVi = i18n.language === 'vi';

  const fetchProfile = useCallback(async () => {
    if (!datasetKey) return;
    setLoading(true);
    try {
      const res = await datasetsApi.profile(datasetKey, 50000);
      if (res && res.profile) {
        const rawProf = res.profile;
        setProfile({
          dataset: res.dataset || datasetKey,
          total_rows: rawProf.total_rows ?? res.sample_size,
          columns_count: rawProf.columns ? rawProf.columns.length : 0,
          health_score: rawProf.data_health_score ?? rawProf.health_score ?? null,
          warehouse_soc_below_zero: rawProf.warehouse_soc_below_zero,
          warehouse_open_incidents: rawProf.warehouse_open_incidents,
          columns: (rawProf.columns || []).map((c: ColumnProfile & { data_type?: string }) => ({
            ...c,
            dtype: c.dtype || c.type || c.data_type,
          })),
          summary: rawProf.summary || 'Profile computed successfully.',
        });
      }
    } catch (err) {
      console.warn('Could not fetch remote profile:', err);
    } finally {
      setLoading(false);
    }
  }, [datasetKey, story]);

  useEffect(() => {
    setProfile(null);
    fetchProfile();
  }, [fetchProfile]);

  useEffect(() => {
    const onSnap = () => { void fetchProfile(); };
    window.addEventListener('datatrust:demo-snapshot', onSnap);
    return () => window.removeEventListener('datatrust:demo-snapshot', onSnap);
  }, [fetchProfile]);

  useEffect(() => {
    const onPending = (e: Event) => {
      const mode = (e as CustomEvent<{ mode?: string }>).detail?.mode;
      if (mode === 'happy' || mode === 'unhappy') {
        try { sessionStorage.setItem('dt-snap-pending', mode); } catch { /* ignore */ }
        setPendingMode(mode);
        setProfile(null); // drop leftover Happy 99.1 / Unhappy Critical immediately
      }
    };
    window.addEventListener('datatrust:demo-snapshot-pending', onPending);
    return () => window.removeEventListener('datatrust:demo-snapshot-pending', onPending);
  }, []);

  const columns = profile?.columns || [];
  const totalRows = profile?.total_rows || 0;
  const healthScore = profile?.health_score;

  const filteredColumns = useMemo(() => {
    const q = searchQuery.toLowerCase().trim();
    if (!q) return columns;
    return columns.filter(
      (c) =>
        c.name.toLowerCase().includes(q) ||
        (c.dtype || c.type || '').toLowerCase().includes(q)
    );
  }, [columns, searchQuery]);

  const warehouseFaults = (profile?.warehouse_soc_below_zero || 0) > 0 || (profile?.warehouse_open_incidents || 0) > 0;
  // Unhappy leftover Happy score (99.1 Excellent) is not a measured Critical settle.
  const holdUnhappyHealth = story === 'unhappy' && !warehouseFaults;
  // Instant pending hold: leftover Happy 99.1 must not paint while Loading snapshot…
  const holdPendingHealth = pendingMode != null;

  useEffect(() => {
    if (!pendingMode) return;
    const unhappySettled = pendingMode === 'unhappy' && warehouseFaults;
    const happyPendingSettled = pendingMode === 'happy' && story === 'happy' && !!profile && !warehouseFaults;
    if (unhappySettled || happyPendingSettled) {
      clearPendingMode();
      setPendingMode(null);
    }
  }, [pendingMode, warehouseFaults, story, profile]);

  const holdHealth = holdPendingHealth || holdUnhappyHealth;
  const healthGrade = useMemo(() => {
    if (holdHealth) return { text: isVi ? 'Chưa đo' : 'Not measured', color: 'var(--text-muted)', bg: 'transparent' };
    if (warehouseFaults) return { text: isVi ? 'Nghiêm Trọng' : 'Critical', color: 'var(--alert-magenta)', bg: 'rgba(248, 113, 113, 0.1)' };
    if (healthScore == null) return { text: isVi ? 'Chưa đo' : 'Not measured', color: 'var(--text-muted)', bg: 'transparent' };
    if (healthScore >= 95) return { text: isVi ? 'Xuất Sắc' : 'Excellent', color: 'var(--electric-green)', bg: 'rgba(52, 211, 153, 0.1)' };
    if (healthScore >= 80) return { text: isVi ? 'Tốt' : 'Good', color: 'var(--warning-amber)', bg: 'rgba(251, 191, 36, 0.1)' };
    return { text: isVi ? 'Nghiêm Trọng' : 'Critical', color: 'var(--alert-magenta)', bg: 'rgba(248, 113, 113, 0.1)' };
  }, [healthScore, isVi, warehouseFaults, holdHealth]);

  return (
    <div className="data-profiler-tab">
      {/* KPI METRIC CARDS */}
      <div className="profiler-kpi-grid">
        <div className="profiler-kpi-card">
          <div className="kpi-card-header">
            <Database size={13} style={{ color: 'var(--text-muted)' }} />
            <span>{isVi ? 'Số Dòng Lấy Mẫu' : 'Sampled Rows'}</span>
          </div>
          <div className="kpi-card-value">{totalRows.toLocaleString()}</div>
          <div className="kpi-card-sub">{isVi ? 'Động Cơ In-Memory' : 'In-Memory Engine'}</div>
        </div>

        <div className="profiler-kpi-card">
          <div className="kpi-card-header">
            <Layers size={13} style={{ color: 'var(--text-muted)' }} />
            <span>{isVi ? 'Độ Rộng Schema' : 'Schema Width'}</span>
          </div>
          <div className="kpi-card-value">{columns.length || profile?.columns_count || 0}</div>
          <div className="kpi-card-sub">{isVi ? 'Cột Đã Phân Tích' : 'Columns Analyzed'}</div>
        </div>

        <div className="profiler-kpi-card">
          <div className="kpi-card-header">
            <Activity size={13} style={{ color: healthGrade.color }} />
            <span>{isVi ? 'Điểm Sức Khỏe' : 'Health Score'}</span>
          </div>
          <div className="kpi-card-value" style={{ color: healthGrade.color }}>
            {warehouseFaults || healthScore == null || holdHealth ? '—' : `${healthScore}%`}
          </div>
          <div className="kpi-card-sub" style={{ color: healthGrade.color }}>
            ● {healthGrade.text}
          </div>
        </div>
      </div>

      {/* SEARCH AND FILTER BAR */}
      <div className="profiler-controls-bar">
        <div className="profiler-search-wrapper">
          <Search size={13} className="profiler-search-icon" />
          <input
            type="text"
            className="profiler-search-input"
            placeholder={isVi ? 'Tìm kiếm tên cột hoặc kiểu dữ liệu...' : 'Search column names or types...'}
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
        </div>
        <button className="traces-refresh-btn" onClick={fetchProfile} disabled={loading} title={isVi ? 'Chạy lại khảo sát sâu' : 'Re-run deep profiling'}>
          <RefreshCw size={13} className={loading ? 'spinning' : ''} />
        </button>
      </div>

      {/* COLUMNS TABLE */}
      {filteredColumns.length === 0 ? (
        <div className="empty-panel-state">
          <BarChart3 size={32} style={{ opacity: 0.3, marginBottom: 8 }} />
          <div style={{ fontWeight: 600, color: 'var(--text-main)' }}>{isVi ? 'Không Có Hồ Sơ Cột Nào Khả Dụng' : 'No Column Profiles Available'}</div>
          <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 4 }}>
            {datasetKey ? (isVi ? 'Nhấp làm mới để tính toán phân phối cột cho tập dữ liệu này.' : 'Click refresh to compute column distributions for this dataset.') : (isVi ? 'Chọn một tập dữ liệu từ thanh bên.' : 'Select a dataset from the sidebar.')}
          </div>
        </div>
      ) : (
        <div className="profiler-table-container">
          <table className="profiler-table">
            <thead>
              <tr>
                <th>{isVi ? 'Cột' : 'Column'}</th>
                <th>{isVi ? 'Kiểu' : 'Type'}</th>
                <th>{isVi ? 'Tỷ Lệ Null' : 'Null Rate'}</th>
                <th>{isVi ? 'Giá Trị Riêng Biệt' : 'Uniques'}</th>
                <th>{isVi ? 'Thống Kê / Khoảng' : 'Stats / Range'}</th>
              </tr>
            </thead>
            <tbody>
              {filteredColumns.map((col) => {
                const nullPct = col.null_pct ?? 0;
                const nullDisplay = typeof nullPct === 'number' && nullPct <= 1.0 ? (nullPct * 100).toFixed(1) : `${nullPct}`;
                const hasAnomalies = (col.anomalies_count && col.anomalies_count > 0) || (col.quality_flags && col.quality_flags.length > 0);

                return (
                  <tr
                    key={col.name}
                    className={selectedColumn?.name === col.name ? 'selected-row' : ''}
                    onClick={() => setSelectedColumn(col)}
                  >
                    <td>
                      <div className="col-name-cell">
                        <strong>{col.name}</strong>
                        {hasAnomalies && (
                          <span className="anomaly-dot" title={isVi ? 'Phát hiện bất thường trong cột' : 'Anomalies detected in column'} />
                        )}
                      </div>
                    </td>
                    <td>
                      <span className="type-badge">{col.dtype || col.type || 'VARCHAR'}</span>
                    </td>
                    <td>
                      <div className="null-rate-cell">
                        <div className="null-bar-track">
                          <div
                            className="null-bar-fill"
                            style={{
                              width: `${Math.min(100, Math.max(0, Number(nullDisplay)))}%`,
                              backgroundColor: Number(nullDisplay) > 5 ? 'var(--alert-magenta)' : 'var(--electric-green)',
                            }}
                          />
                        </div>
                        <span className="null-pct-text">{nullDisplay}%</span>
                      </div>
                    </td>
                    <td>
                      <span className="uniques-text">
                        {col.unique_count !== undefined ? col.unique_count.toLocaleString() : '—'}
                      </span>
                    </td>
                    <td>
                      <div className="stats-cell">
                        {col.min_val !== undefined && col.max_val !== undefined ? (
                          <span className="range-text">[{String(col.min_val)} .. {String(col.max_val)}]</span>
                        ) : (
                          <span className="text-dim">{isVi ? 'Phân phối chuẩn' : 'Standard distribution'}</span>
                        )}
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* SELECTED COLUMN DETAIL DRAWER */}
      {selectedColumn && (
        <div className="col-detail-card">
          <div className="col-detail-header">
            <span className="col-detail-title">
              <Hash size={13} /> {isVi ? 'Cột:' : 'Column:'} <code>{selectedColumn.name}</code>
            </span>
            <button className="col-detail-close" onClick={() => setSelectedColumn(null)}>✕</button>
          </div>
          <div className="col-detail-grid">
            <div className="col-detail-item">
              <span className="detail-label">{isVi ? 'Kiểu Dữ Liệu' : 'Data Type'}</span>
              <span className="detail-val">{selectedColumn.dtype || selectedColumn.type || 'VARCHAR'}</span>
            </div>
            <div className="col-detail-item">
              <span className="detail-label">{isVi ? 'Tỷ Lệ Null' : 'Null Rate'}</span>
              <span className="detail-val">{selectedColumn.null_pct ?? 0}%</span>
            </div>
            <div className="col-detail-item">
              <span className="detail-label">{isVi ? 'Giá Trị Riêng Biệt' : 'Distinct Values'}</span>
              <span className="detail-val">{selectedColumn.unique_count?.toLocaleString() || '—'}</span>
            </div>
            <div className="col-detail-item">
              <span className="detail-label">{isVi ? 'Tối Thiểu / Tối Đa' : 'Min / Max'}</span>
              <span className="detail-val">
                {selectedColumn.min_val !== undefined ? `${selectedColumn.min_val} / ${selectedColumn.max_val}` : '—'}
              </span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
