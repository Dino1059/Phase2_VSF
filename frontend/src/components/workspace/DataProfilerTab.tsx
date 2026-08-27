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
  Table as TableIcon,
  AlertTriangle,
} from 'lucide-react';

import { datasetsApi, ingestionApi } from '../../services/api';
import { useChatStore } from '../../stores/chatStore';
import { clearWarehouseOverlay, readWarehouseOverlay, writeWarehouseOverlay } from '../../demo/stewardLabels';

export interface ColumnProfile {
  name: string;
  table?: string;
  dtype?: string;
  type?: string;
  data_type?: string;
  null_count?: number;
  null_pct?: number;
  null_percentage?: number;
  unique_count?: number;
  distinct_count?: number;
  min_val?: any;
  min?: any;
  max_val?: any;
  max?: any;
  mean_val?: any;
  mean?: any;
  std?: any;
  quality_flags?: any[];
  anomalies_count?: number;
  anomaly_count?: number;
  top_values?: any;
  pattern_summary?: string;
}

export interface TableSummary {
  name: string;
  totalRows: number;
  columnsCount: number;
  healthScore: number | null;
  columns: ColumnProfile[];
  qualityFlags?: any[];
  summary?: string;
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
  /** Keep-mounted: refetch when shown so Unhappy warehouse can settle. */
  active?: boolean;
  dayIdx?: number | null;
  runId?: string | null;
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

export const DataProfilerTab: React.FC<DataProfilerTabProps> = ({ datasetKey, story, active = false, dayIdx = null, runId: _runId = null }) => {
  const [tablesMap, setTablesMap] = useState<Record<string, TableSummary>>({});
  const [selectedTable, setSelectedTable] = useState<string>('__all__');
  const [totalRowsAll, setTotalRowsAll] = useState<number>(0);
  const [totalColsAll, setTotalColsAll] = useState<number>(0);
  const [aggregateHealth, setAggregateHealth] = useState<number | null>(null);
  const [profile, setProfile] = useState<ProfileData | null>(null);
  const [loading, setLoading] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedColumn, setSelectedColumn] = useState<ColumnProfile | null>(null);
  const [pendingMode, setPendingMode] = useState<PendingMode>(() => readPendingMode());
  const [overlay, setOverlay] = useState<{ soc: number; open: number } | null>(() => readWarehouseOverlay());
  const { i18n } = useTranslation('pipeline');
  const isVi = i18n.language === 'vi';
  const chatMessages = useChatStore((s) => s.messages);

  const normalizeColumns = useCallback((rawCols: any[], tableName?: string): ColumnProfile[] => {
    if (!Array.isArray(rawCols)) return [];
    return rawCols.map((c: any) => {
      const name = c.name || c.column_name || c.col || 'unknown';
      const dtype = c.dtype || c.data_type || c.type || 'VARCHAR';
      let nullPct = c.null_pct;
      if (nullPct === undefined && typeof c.null_percentage === 'number') {
        nullPct = c.null_percentage > 1.0 ? c.null_percentage / 100 : c.null_percentage;
      }
      if (nullPct === undefined && typeof c.null_count === 'number' && c.total_count) {
        nullPct = c.null_count / c.total_count;
      }

      const flags = Array.isArray(c.quality_flags) ? c.quality_flags : [];
      const anomCount = c.anomalies_count ?? c.anomaly_count ?? (flags.length > 0 ? flags.length : 0);

      return {
        name,
        table: tableName || c.table,
        dtype,
        type: dtype,
        null_count: c.null_count ?? 0,
        null_pct: typeof nullPct === 'number' ? nullPct : 0,
        unique_count: c.unique_count ?? c.distinct_count ?? 0,
        distinct_count: c.distinct_count ?? c.unique_count ?? 0,
        min_val: c.min_val ?? c.min,
        max_val: c.max_val ?? c.max,
        mean_val: c.mean_val ?? c.mean,
        std: c.std ?? c.std_val,
        quality_flags: flags,
        anomalies_count: anomCount,
        top_values: c.top_values,
        pattern_summary: c.pattern_summary,
      };
    });
  }, []);

  const parseProfilePayload = useCallback((payload: any) => {
    if (!payload) return null;
    const rawProf = payload.profile || payload;
    const newTablesMap: Record<string, TableSummary> = {};

    // 1. Multi-table format with tables dictionary
    if (rawProf.tables && typeof rawProf.tables === 'object' && Object.keys(rawProf.tables).length > 0) {
      let sumRows = 0;
      let sumCols = 0;
      const healths: number[] = [];

      for (const [tblName, tblData] of Object.entries(rawProf.tables)) {
        if (!tblData || typeof tblData !== 'object') continue;
        const dataObj: any = tblData;
        const rawCols = dataObj.columns || dataObj.profile?.columns || [];
        const normCols = normalizeColumns(rawCols, tblName);
        const health = dataObj.health_score ?? dataObj.data_health_score ?? dataObj.profile?.data_health_score;
        const rows = dataObj.total_rows ?? dataObj.row_count ?? dataObj.profile?.total_rows ?? 0;
        const colsCount = dataObj.columns_count ?? normCols.length;
        const measuredHealth = (typeof health === 'number' && (rows > 0 || colsCount > 0)) ? health : null;

        newTablesMap[tblName] = {
          name: tblName,
          totalRows: rows,
          columnsCount: colsCount,
          healthScore: measuredHealth,
          columns: normCols,
          summary: dataObj.summary || dataObj.profile?.summary,
        };

        sumRows += rows;
        sumCols += colsCount;
        if (measuredHealth != null) healths.push(measuredHealth);
      }

      const aggHealth = typeof payload.health_score === 'number'
        ? payload.health_score
        : (healths.length > 0 ? Math.min(...healths) : null);
      return {
        tablesMap: newTablesMap,
        totalRows: payload.total_rows ?? payload.sample_size ?? sumRows,
        totalCols: payload.columns_count ?? sumCols,
        healthScore: aggHealth,
      };
    }

    // 2. Single table format with columns list
    const rawCols = rawProf.columns || payload.columns || [];
    if (Array.isArray(rawCols) && rawCols.length > 0) {
      const defaultName = payload.table || (datasetKey && datasetKey.includes('::') ? datasetKey.split('::')[1] : (payload.dataset || datasetKey || 'dataset'));
      const normCols = normalizeColumns(rawCols, defaultName);
      const rows = rawProf.total_rows ?? rawProf.row_count ?? payload.sample_size ?? payload.total_rows ?? 0;
      const colsCount = rawProf.columns_count ?? normCols.length;
      const healthRaw = rawProf.data_health_score ?? rawProf.health_score ?? payload.health_score;
      const health = (typeof healthRaw === 'number' && (rows > 0 || colsCount > 0)) ? healthRaw : null;

      newTablesMap[defaultName] = {
        name: defaultName,
        totalRows: rows,
        columnsCount: colsCount,
        healthScore: health,
        columns: normCols,
        summary: rawProf.summary,
      };

      return {
        tablesMap: newTablesMap,
        totalRows: rows,
        totalCols: colsCount,
        healthScore: health,
      };
    }

    return null;
  }, [datasetKey, normalizeColumns]);

  const fetchProfile = useCallback(async () => {
    if (!active) return;
    setLoading(true);
    try {
      let res;
      const targetKey = datasetKey || 'ev_telemetry';
      try {
        res = await datasetsApi.profile(targetKey, undefined, dayIdx ?? undefined);
      } catch {
        const fallbackKey = targetKey.startsWith('uploaded_') ? targetKey.replace('uploaded_', '') : 'ev_telemetry';
        res = await datasetsApi.profile(fallbackKey, undefined, dayIdx ?? undefined);
      }
      const parsed = parseProfilePayload(res);

      let dayRows = parsed?.totalRows ?? 0;
      let dayHealth: number | null = parsed?.healthScore ?? null;

      if (dayIdx !== null && dayIdx !== undefined && dayIdx >= 0) {
        try {
          const daySnap = await ingestionApi.getDay(dayIdx);
          if (daySnap && (daySnap.ingested_rows ?? 0) > 0) {
            dayRows = daySnap.ingested_rows;
            const alerts = daySnap.alerts_count || 0;
            if (alerts > 0) {
              dayHealth = Math.max(60, 100 - alerts * 3);
            }
          }
        } catch {
          /* ignore */
        }
      }

      if (parsed && Object.keys(parsed.tablesMap).length > 0) {
        const tblKeys = Object.keys(parsed.tablesMap);
        if (tblKeys.length > 0 && dayRows > 0) {
          const mainKey = tblKeys[0];
          parsed.tablesMap[mainKey] = {
            ...parsed.tablesMap[mainKey],
            totalRows: dayRows,
            healthScore: dayHealth,
          };
        }
        setTablesMap(parsed.tablesMap);
        setTotalRowsAll(dayRows > 0 ? dayRows : parsed.totalRows);
        setTotalColsAll(parsed.totalCols);
        setAggregateHealth(dayHealth);
        if (tblKeys.length === 1) {
          setSelectedTable(tblKeys[0]);
        } else {
          setSelectedTable((prev) => (prev !== '__all__' && !parsed.tablesMap[prev] ? '__all__' : prev));
        }
      }
    } catch (err) {
      console.warn('Could not fetch remote profile:', err);
    } finally {
      setLoading(false);
    }
  }, [datasetKey, active, dayIdx, parseProfilePayload]);

  useEffect(() => {
    if (!active) return;
    setProfile(null);
    fetchProfile();
  }, [active, dayIdx, fetchProfile]);

  // Fallback: parse profile data from chat messages if API hasn't loaded
  useEffect(() => {
    if (Object.keys(tablesMap).length > 0) return;
    if (!chatMessages || chatMessages.length === 0) return;

    for (let i = chatMessages.length - 1; i >= 0; i--) {
      const msg = chatMessages[i];
      const content = msg.content || '';

      // Check metadata first
      const rawData = (msg.metadata as any)?.raw_data || (msg.metadata as any)?.profile;
      if (rawData) {
        const parsed = parseProfilePayload(rawData);
        if (parsed && Object.keys(parsed.tablesMap).length > 0) {
          setTablesMap(parsed.tablesMap);
          setTotalRowsAll(parsed.totalRows);
          setTotalColsAll(parsed.totalCols);
          setAggregateHealth(parsed.healthScore ?? null);
          const tblKeys = Object.keys(parsed.tablesMap);
          if (tblKeys.length === 1) setSelectedTable(tblKeys[0]);
          break;
        }
      }

      // Check content string (Observation or Markdown or JSON string)
      if (
        content.includes('profile') ||
        content.includes('Profile') ||
        content.includes('Khảo Sát') ||
        (msg.agentId as string) === 'profile_dataset'
      ) {
        try {
          let jsonStr = content;
          if (content.includes('Observation:')) {
            const obsIdx = content.indexOf('Observation:');
            jsonStr = content.slice(obsIdx + 12).trim();
          } else {
            const braceIdx = content.indexOf('{');
            if (braceIdx !== -1) {
              jsonStr = content.slice(braceIdx).trim();
            }
          }

          if (jsonStr.startsWith('{')) {
            const normalizedJson = jsonStr
              .replace(/'/g, '"')
              .replace(/None/g, 'null')
              .replace(/True/g, 'true')
              .replace(/False/g, 'false');
            const parsedObj = JSON.parse(normalizedJson);
            const parsed = parseProfilePayload(parsedObj);
            if (parsed && Object.keys(parsed.tablesMap).length > 0) {
              setTablesMap(parsed.tablesMap);
              setTotalRowsAll(parsed.totalRows);
              setTotalColsAll(parsed.totalCols);
              setAggregateHealth(parsed.healthScore ?? null);
              const tblKeys = Object.keys(parsed.tablesMap);
              if (tblKeys.length === 1) setSelectedTable(tblKeys[0]);
              break;
            }
          }
        } catch {
          // Non-blocking parse error
        }
      }
    }
  }, [chatMessages, tablesMap, parseProfilePayload]);

  const tableNames = useMemo(() => Object.keys(tablesMap), [tablesMap]);
  const isMultiTable = tableNames.length > 1;

  // Active columns based on selected table
  const activeColumns = useMemo<ColumnProfile[]>(() => {
    if (tableNames.length === 0) return [];
    if (selectedTable === '__all__' || !tablesMap[selectedTable]) {
      const allCols: ColumnProfile[] = [];
      tableNames.forEach((tbl) => {
        allCols.push(...tablesMap[tbl].columns);
      });
      return allCols;
    }
    return tablesMap[selectedTable].columns;
  }, [tablesMap, tableNames, selectedTable]);

  // Dynamic KPI Metrics for Active Selection
  const activeTotalRows = useMemo(() => {
    if (selectedTable !== '__all__' && tablesMap[selectedTable]) {
      return tablesMap[selectedTable].totalRows;
    }
    return totalRowsAll;
  }, [tablesMap, selectedTable, totalRowsAll]);

  const activeColumnsCount = useMemo(() => {
    if (selectedTable !== '__all__' && tablesMap[selectedTable]) {
      return tablesMap[selectedTable].columnsCount;
    }
    return totalColsAll || activeColumns.length;
  }, [tablesMap, selectedTable, totalColsAll, activeColumns.length]);

  const activeHealthScore = useMemo(() => {
    if (selectedTable !== '__all__' && tablesMap[selectedTable]) {
      return tablesMap[selectedTable].healthScore;
    }
    return aggregateHealth;
  }, [tablesMap, selectedTable, aggregateHealth]);


  useEffect(() => {
    const onSnap = (e: Event) => {
      const d = (e as CustomEvent<{ soc_below_zero?: number; open_incidents?: number }>).detail;
      const soc = Number(d?.soc_below_zero);
      const open = Number(d?.open_incidents);
      if (Number.isFinite(soc) && Number.isFinite(open)) {
        writeWarehouseOverlay(soc, open);
        setOverlay({ soc, open });
      } else {
        setOverlay(readWarehouseOverlay());
      }
      void fetchProfile();
    };
    window.addEventListener('datatrust:demo-snapshot', onSnap);
    return () => window.removeEventListener('datatrust:demo-snapshot', onSnap);
  }, [fetchProfile]);

  useEffect(() => {
    const onPending = (e: Event) => {
      const mode = (e as CustomEvent<{ mode?: string }>).detail?.mode;
      if (mode === 'happy' || mode === 'unhappy') {
        try { sessionStorage.setItem('dt-snap-pending', mode); } catch { /* ignore */ }
        clearWarehouseOverlay();
        setOverlay(null);
        setPendingMode(mode);
        setProfile(null); // drop leftover Happy 99.1 / Unhappy Critical immediately
      }
    };
    window.addEventListener('datatrust:demo-snapshot-pending', onPending);
    return () => window.removeEventListener('datatrust:demo-snapshot-pending', onPending);
  }, []);


  const filteredColumns = useMemo(() => {
    const q = searchQuery.toLowerCase().trim();
    if (!q) return activeColumns;
    return activeColumns.filter(
      (c) =>
        c.name.toLowerCase().includes(q) ||
        (c.table || '').toLowerCase().includes(q) ||
        (c.dtype || c.type || '').toLowerCase().includes(q)
    );
  }, [activeColumns, searchQuery]);

  const profileSoc = Number(profile?.warehouse_soc_below_zero) || 0;
  const profileOpen = Number(profile?.warehouse_open_incidents) || 0;
  const soc = profileSoc || overlay?.soc || 0;
  const open = profileOpen || overlay?.open || 0;
  const warehouseFaults = soc > 0 || open > 0;
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

  const holdHealth = (holdPendingHealth || holdUnhappyHealth) && !warehouseFaults;
  const healthGrade = useMemo(() => {
    if (warehouseFaults) return { text: isVi ? 'Nghiêm Trọng' : 'Critical', color: 'var(--alert-magenta)', bg: 'rgba(248, 113, 113, 0.1)' };
    if (activeTotalRows === 0 && activeColumnsCount === 0)
      return { text: isVi ? 'Chưa đo' : 'Unknown', color: 'var(--text-muted)', bg: 'transparent' };
    if (activeHealthScore == null)
      return { text: '—', color: 'var(--text-muted)', bg: 'transparent' };
    if (activeHealthScore >= 95)
      return { text: isVi ? 'Xuất Sắc' : 'Excellent', color: 'var(--electric-green)', bg: 'rgba(52, 211, 153, 0.1)' };
    if (activeHealthScore >= 80)
      return { text: isVi ? 'Tốt' : 'Good', color: 'var(--warning-amber)', bg: 'rgba(251, 191, 36, 0.1)' };
    return { text: isVi ? 'Nghiêm Trọng' : 'Critical', color: 'var(--alert-magenta)', bg: 'rgba(248, 113, 113, 0.1)' };
  }, [activeHealthScore, isVi, warehouseFaults, activeTotalRows, activeColumnsCount]);

  return (
    <div className="data-profiler-tab">
      {/* MULTI-TABLE SELECTOR BAR */}
      {isMultiTable && (
        <div className="profiler-table-selector">
          <button
            type="button"
            className={`profiler-table-pill ${selectedTable === '__all__' ? 'active' : ''}`}
            onClick={() => setSelectedTable('__all__')}
          >
            <Database size={12} />
            <span>{isVi ? `Tất Cả Bảng (${tableNames.length})` : `All Tables (${tableNames.length})`}</span>
          </button>
          {tableNames.map((tblName) => {
            const tbl = tablesMap[tblName];
            const isActive = selectedTable === tblName;
            const dotColor =
              tbl.healthScore == null
                ? 'var(--text-muted)'
                : tbl.healthScore >= 95
                ? 'var(--electric-green)'
                : tbl.healthScore >= 80
                ? 'var(--warning-amber)'
                : 'var(--alert-magenta)';

            return (
              <button
                key={tblName}
                type="button"
                className={`profiler-table-pill ${isActive ? 'active' : ''}`}
                onClick={() => setSelectedTable(tblName)}
                title={`${tblName}: ${tbl.columnsCount} ${isVi ? 'cột' : 'cols'} • ${tbl.totalRows.toLocaleString()} ${isVi ? 'dòng' : 'rows'}`}
              >
                <span className="profiler-health-dot" style={{ backgroundColor: dotColor }} />
                <TableIcon size={12} />
                <span>{tblName}</span>
                <span className="profiler-pill-badge">
                  ({tbl.columnsCount} cols • {tbl.totalRows.toLocaleString()})
                </span>
              </button>
            );
          })}
        </div>
      )}

      {/* KPI METRIC CARDS */}
      <div className="profiler-kpi-grid">
        <div className="profiler-kpi-card">
          <div className="kpi-card-header">
            <Database size={13} style={{ color: 'var(--text-muted)' }} />
            <span>{isVi ? 'Tổng Số Dòng' : 'Total Rows'}</span>
          </div>
          <div className="kpi-card-value">{activeTotalRows.toLocaleString()}</div>
          <div className="kpi-card-sub">
            {selectedTable === '__all__'
              ? (isVi ? `${tableNames.length} Bảng Phân Tích` : `${tableNames.length} Tables Analyzed`)
              : (isVi ? `Bảng: ${selectedTable}` : `Table: ${selectedTable}`)}
          </div>
        </div>

        <div className="profiler-kpi-card">
          <div className="kpi-card-header">
            <Layers size={13} style={{ color: 'var(--text-muted)' }} />
            <span>{isVi ? 'Độ Rộng Schema' : 'Schema Width'}</span>
          </div>
          <div className="kpi-card-value">{activeColumnsCount}</div>
          <div className="kpi-card-sub">{isVi ? 'Cột Đã Phân Tích' : 'Columns Analyzed'}</div>
        </div>

        <div className="profiler-kpi-card">
          <div className="kpi-card-header">
            <Activity size={13} style={{ color: healthGrade.color }} />
            <span>{isVi ? 'Điểm Sức Khỏe' : 'Health Score'}</span>
          </div>
          <div className="kpi-card-value" style={{ color: healthGrade.color }}>
            {warehouseFaults || activeHealthScore == null || (activeTotalRows === 0 && activeColumnsCount === 0)
              ? '—'
              : `${activeHealthScore}%`}
          </div>
          <div className="kpi-card-sub" style={{ color: healthGrade.color }}>
            ● {healthGrade.text}
            {warehouseFaults && !holdHealth ? ` · SoC<0 = ${soc} · OPEN = ${open}` : ''}
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
            placeholder={
              isMultiTable && selectedTable === '__all__'
                ? (isVi ? 'Tìm kiếm theo tên cột, bảng hoặc kiểu dữ liệu...' : 'Search column names, tables, or types...')
                : (isVi ? 'Tìm kiếm tên cột hoặc kiểu dữ liệu...' : 'Search column names or types...')
            }
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
        </div>
        <button
          className="traces-refresh-btn"
          onClick={fetchProfile}
          disabled={loading}
          title={isVi ? 'Chạy lại khảo sát sâu' : 'Re-run deep profiling'}
        >
          <RefreshCw size={13} className={loading ? 'spinning' : ''} />
        </button>
      </div>

      {/* COLUMNS TABLE */}
      {filteredColumns.length === 0 ? (
        <div className="empty-panel-state">
          <BarChart3 size={32} style={{ opacity: 0.3, marginBottom: 8 }} />
          <div style={{ fontWeight: 600, color: 'var(--text-main)' }}>
            {isVi ? 'Không Có Hồ Sơ Cột Nào Khả Dụng' : 'No Column Profiles Available'}
          </div>
          <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 4 }}>
            {datasetKey
              ? (isVi
                  ? 'Nhấp làm mới để tính toán phân phối cột cho tập dữ liệu này.'
                  : 'Click refresh to compute column distributions for this dataset.')
              : (isVi
                  ? 'Chọn một tập dữ liệu từ thanh bên.'
                  : 'Select a dataset from the sidebar.')}
          </div>
        </div>
      ) : (
        <div className="profiler-table-container">
          <table className="profiler-table">
            <thead>
              <tr>
                <th>{isVi ? 'Cột' : 'Column'}</th>
                {isMultiTable && selectedTable === '__all__' && <th>{isVi ? 'Bảng' : 'Table'}</th>}
                <th>{isVi ? 'Kiểu' : 'Type'}</th>
                <th>{isVi ? 'Tỷ Lệ Null' : 'Null Rate'}</th>
                <th>{isVi ? 'Giá Trị Riêng Biệt' : 'Uniques'}</th>
                <th>{isVi ? 'Thống Kê / Khoảng' : 'Stats / Range'}</th>
              </tr>
            </thead>
            <tbody>
              {filteredColumns.map((col, idx) => {
                const nullPct = col.null_pct ?? 0;
                const nullDisplay =
                  typeof nullPct === 'number' && nullPct <= 1.0 ? (nullPct * 100).toFixed(1) : `${nullPct}`;
                const hasAnomalies =
                  (col.anomalies_count && col.anomalies_count > 0) ||
                  (col.quality_flags && col.quality_flags.length > 0);
                const isSelected =
                  selectedColumn?.name === col.name &&
                  (!col.table || !selectedColumn?.table || col.table === selectedColumn?.table);

                return (
                  <tr
                    key={`${col.table || 't'}-${col.name}-${idx}`}
                    className={isSelected ? 'selected-row' : ''}
                    onClick={() => setSelectedColumn(col)}
                  >
                    <td>
                      <div className="col-name-cell">
                        <strong>{col.name}</strong>
                        {hasAnomalies && (
                          <span
                            className="anomaly-dot"
                            title={isVi ? 'Phát hiện bất thường trong cột' : 'Anomalies detected in column'}
                          />
                        )}
                      </div>
                    </td>
                    {isMultiTable && selectedTable === '__all__' && (
                      <td>
                        <span className="profiler-table-badge">{col.table || 'main'}</span>
                      </td>
                    )}
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
                              backgroundColor:
                                Number(nullDisplay) > 5 ? 'var(--alert-magenta)' : 'var(--electric-green)',
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
                          <span className="range-text">
                            [{String(col.min_val)} .. {String(col.max_val)}]
                          </span>
                        ) : col.mean_val !== undefined ? (
                          <span className="range-text">
                            μ={typeof col.mean_val === 'number' ? col.mean_val.toFixed(2) : String(col.mean_val)}
                          </span>
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
              {selectedColumn.table && <span className="profiler-table-badge">{selectedColumn.table}</span>}
            </span>
            <button className="col-detail-close" onClick={() => setSelectedColumn(null)}>
              ✕
            </button>
          </div>
          <div className="col-detail-grid">
            <div className="col-detail-item">
              <span className="detail-label">{isVi ? 'Kiểu Dữ Liệu' : 'Data Type'}</span>
              <span className="detail-val">{selectedColumn.dtype || selectedColumn.type || 'VARCHAR'}</span>
            </div>
            <div className="col-detail-item">
              <span className="detail-label">{isVi ? 'Tỷ Lệ Null' : 'Null Rate'}</span>
              <span className="detail-val">
                {typeof selectedColumn.null_pct === 'number' && selectedColumn.null_pct <= 1.0
                  ? `${(selectedColumn.null_pct * 100).toFixed(1)}%`
                  : `${selectedColumn.null_pct ?? 0}%`}
                {selectedColumn.null_count !== undefined ? ` (${selectedColumn.null_count.toLocaleString()} dòng)` : ''}
              </span>
            </div>
            <div className="col-detail-item">
              <span className="detail-label">{isVi ? 'Giá Trị Riêng Biệt' : 'Distinct Values'}</span>
              <span className="detail-val">{selectedColumn.unique_count?.toLocaleString() || '—'}</span>
            </div>
            <div className="col-detail-item">
              <span className="detail-label">{isVi ? 'Tối Thiểu / Tối Đa' : 'Min / Max'}</span>
              <span className="detail-val">
                {selectedColumn.min_val !== undefined && selectedColumn.max_val !== undefined
                  ? `${selectedColumn.min_val} / ${selectedColumn.max_val}`
                  : '—'}
              </span>
            </div>
            {selectedColumn.mean_val !== undefined && (
              <div className="col-detail-item">
                <span className="detail-label">{isVi ? 'Giá Trị Trung Bình (Mean)' : 'Mean'}</span>
                <span className="detail-val">
                  {typeof selectedColumn.mean_val === 'number'
                    ? selectedColumn.mean_val.toFixed(3)
                    : String(selectedColumn.mean_val)}
                  {selectedColumn.std !== undefined ? ` (σ = ${typeof selectedColumn.std === 'number' ? selectedColumn.std.toFixed(3) : selectedColumn.std})` : ''}
                </span>
              </div>
            )}
            {selectedColumn.anomalies_count !== undefined && selectedColumn.anomalies_count > 0 && (
              <div className="col-detail-item" style={{ gridColumn: 'span 2' }}>
                <span className="detail-label" style={{ color: 'var(--alert-magenta)' }}>
                  <AlertTriangle size={11} style={{ display: 'inline', marginRight: 4 }} />
                  {isVi ? 'Cảnh Báo Bất Thường' : 'Anomalies & Quality Flags'}
                </span>
                <span className="detail-val" style={{ color: 'var(--alert-magenta)' }}>
                  {isVi
                    ? `Phát hiện ${selectedColumn.anomalies_count} mẫu dữ liệu bất thường.`
                    : `Detected ${selectedColumn.anomalies_count} anomaly patterns in this column.`}
                </span>
              </div>
            )}
            {selectedColumn.top_values && (
              <div className="col-detail-item" style={{ gridColumn: 'span 2' }}>
                <span className="detail-label">{isVi ? 'Phân Phối Giá Trị Tiêu Biểu' : 'Top Values'}</span>
                <div className="top-values-chips">
                  {Array.isArray(selectedColumn.top_values)
                    ? selectedColumn.top_values.slice(0, 5).map((tv: any, idx: number) => (
                        <span key={idx} className="top-val-chip">
                          {String(tv.value ?? tv)}: {tv.count ? tv.count.toLocaleString() : ''}
                        </span>
                      ))
                    : typeof selectedColumn.top_values === 'object'
                    ? Object.entries(selectedColumn.top_values)
                        .slice(0, 5)
                        .map(([val, cnt]: [string, any], idx) => (
                          <span key={idx} className="top-val-chip">
                            {val}: {Number(cnt).toLocaleString()}
                          </span>
                        ))
                    : null}
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
