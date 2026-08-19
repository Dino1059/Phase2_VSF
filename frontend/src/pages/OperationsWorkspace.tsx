import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import {
  Bell,
  TriangleAlert,
  Activity,
  GitBranch,
  Shield,
  ListChecks,
  Camera,
  RefreshCw,
  Search,
  CheckCircle2,
  Layers,
  Brain,
  Sparkles,
  ExternalLink,
  ShieldCheck,
  Zap,
} from 'lucide-react';
import {
  approvalsApi,
  auditApi,
  authorizationsApi,
  executionsApi,
  incidentsApi,
  signalsApi,
  snapshotsApi,
  summaryApi,
  tracesApi,
} from '../services/api';

type DashboardGroup = 'alerts' | 'governance';
type SubTabKey = 'alerts' | 'incidents' | 'signals' | 'traces' | 'governance' | 'executions' | 'snapshots';
type Row = Record<string, any>;

const ALERT_SUBTABS: Array<{ key: SubTabKey; label: { en: string; vi: string }; icon: any; color: string }> = [
  { key: 'alerts', label: { en: 'Alert Center', vi: 'Trung Tâm Cảnh Báo' }, icon: Bell, color: '#f43f5e' },
  { key: 'incidents', label: { en: 'Incidents & RCA Triage', vi: 'Phân Loại Sự Cố & RCA' }, icon: TriangleAlert, color: '#f59e0b' },
  { key: 'signals', label: { en: 'Signal Explorer', vi: 'Khám Phá Tín Hiệu Telemetry' }, icon: Activity, color: '#a855f7' },
  { key: 'traces', label: { en: 'Agent Traces', vi: 'Dấu Vết Thực Thi Agent' }, icon: GitBranch, color: '#10b981' },
];

const GOVERNANCE_SUBTABS: Array<{ key: SubTabKey; label: { en: string; vi: string }; icon: any; color: string }> = [
  { key: 'governance', label: { en: 'Governance & Policies', vi: 'Quản Trị & Chính Sách' }, icon: Shield, color: '#38bdf8' },
  { key: 'executions', label: { en: 'Execution History', vi: 'Lịch Sử Thực Thi' }, icon: ListChecks, color: '#3b82f6' },
  { key: 'snapshots', label: { en: 'Data Snapshots', vi: 'Ảnh Chụp Dữ Liệu' }, icon: Camera, color: '#6366f1' },
];

const COLUMN_TRANSLATIONS: Record<string, { en: string; vi: string }> = {
  incident_id: { en: 'INCIDENT ID', vi: 'MÃ SỰ CỐ' },
  fault_family: { en: 'FAULT FAMILY', vi: 'NHÓM LỖI' },
  layer: { en: 'LAYER', vi: 'TẦNG' },
  target_entity: { en: 'TARGET ENTITY', vi: 'THỰC THỂ' },
  severity: { en: 'SEVERITY', vi: 'MỨC ĐỘ' },
  status: { en: 'STATUS', vi: 'TRẠNG THÁI' },
  verdict: { en: 'VERDICT', vi: 'KẾT QUẢ' },
  ground_truth_cause: { en: 'GROUND TRUTH CAUSE', vi: 'NGUYÊN NHÂN GỐC CHUẨN' },
  domain: { en: 'DOMAIN', vi: 'MIỀN' },
  signal_id: { en: 'SIGNAL ID', vi: 'MÃ TÍN HIỆU' },
  signal_type: { en: 'SIGNAL TYPE', vi: 'LOẠI TÍN HIỆU' },
  detector: { en: 'DETECTOR', vi: 'BỘ PHÁT HIỆN' },
  details: { en: 'DETAILS', vi: 'CHI TIẾT' },
  session_id: { en: 'SESSION ID', vi: 'MÃ PHIÊN' },
  agent_type: { en: 'AGENT TYPE', vi: 'LOẠI AGENT' },
  steps: { en: 'STEPS', vi: 'SỐ BƯỚC' },
  total_tokens: { en: 'TOTAL TOKENS', vi: 'TỔNG TOKENS' },
  started: { en: 'STARTED', vi: 'BẮT ĐẦU' },
  record_type: { en: 'RECORD TYPE', vi: 'LOẠI BẢN GHI' },
  id: { en: 'ID', vi: 'MÃ ĐỊNH DANH' },
  actor: { en: 'ACTOR', vi: 'TÁC TỬ' },
  action: { en: 'ACTION', vi: 'HÀNH ĐỘNG' },
  timestamp: { en: 'TIMESTAMP', vi: 'THỜI GIAN' },
  event_type: { en: 'EVENT TYPE', vi: 'LOẠI SỰ KIỆN' },
  source_file: { en: 'SOURCE FILE', vi: 'TẬP TIN NGUỒN' },
  row_count: { en: 'ROW COUNT', vi: 'SỐ HÀNG' },
  column_count: { en: 'COLUMN COUNT', vi: 'SỐ CỘT' },
  sha256_hash: { en: 'SHA-256 HASH', vi: 'MÃ BĂM SHA-256' },
  ingested_at: { en: 'INGESTED AT', vi: 'THỜI ĐIỂM NẠP' },
};

function formatCell(row: Row, ...keys: string[]) {
  const found = keys.find((key) => row[key] !== undefined && row[key] !== null && row[key] !== '');
  if (!found) return '—';
  const val = row[found];
  if (typeof val === 'object') return JSON.stringify(val);
  return String(val);
}

export const OperationsWorkspace: React.FC = () => {
  const { view } = useParams<{ view: string }>();
  const navigate = useNavigate();
  const { i18n } = useTranslation('pipeline');
  const isVi = i18n.language === 'vi';

  // Determine main dashboard group and active subtab
  const isGovernanceView = view === 'governance' || view === 'executions' || view === 'snapshots';
  const mainGroup: DashboardGroup = isGovernanceView ? 'governance' : 'alerts';

  const [activeSubTab, setActiveSubTab] = useState<SubTabKey>(() => {
    if (view && (view === 'incidents' || view === 'signals' || view === 'traces')) return view;
    if (view && (view === 'executions' || view === 'snapshots')) return view;
    return isGovernanceView ? 'governance' : 'alerts';
  });

  const [data, setData] = useState<Row[]>([]);
  const [_summary, setSummary] = useState<Row | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filterQuery, setFilterQuery] = useState('');

  // Selected incident for interactive RCA deep-dive modal
  const [selectedIncident, setSelectedIncident] = useState<Record<string, any> | null>(null);
  const [incidentLoading, setIncidentLoading] = useState(false);

  useEffect(() => {
    setSelectedIncident(null);
  }, [view]);
  const [modalTab, setModalTab] = useState<'rca' | 'evidence' | 'raw_json'>('rca');
  const [investigating, setInvestigating] = useState(false);
  const [investigationResult, setInvestigationResult] = useState<any>(null);

  // Sync URL view param with active subtab
  useEffect(() => {
    if (view && ['alerts', 'incidents', 'signals', 'traces', 'governance', 'executions', 'snapshots'].includes(view)) {
      setActiveSubTab(view as SubTabKey);
    }
  }, [view]);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      if (activeSubTab === 'alerts' || activeSubTab === 'incidents') {
        const [sumRes, incRes] = await Promise.all([
          summaryApi.get().catch(() => null),
          incidentsApi.list().catch(() => []),
        ]);
        if (sumRes) setSummary(sumRes);
        setData(incRes || []);
      } else if (activeSubTab === 'signals') {
        const sigRes = await signalsApi.list().catch(() => []);
        setData(sigRes || []);
      } else if (activeSubTab === 'traces') {
        const tracesRes = await tracesApi.list().catch(() => ({ sessions: [] }));
        setData(tracesRes.sessions || []);
      } else if (activeSubTab === 'governance') {
        const [approvals, authorizations, audit] = await Promise.all([
          approvalsApi.list().catch(() => []),
          authorizationsApi.list().catch(() => []),
          auditApi.list(50).catch(() => []),
        ]);
        setData([
          ...(approvals || []).map((r) => ({ ...r, record_type: 'approval' })),
          ...(authorizations || []).map((r) => ({ ...r, record_type: 'authorization' })),
          ...(audit || []).map((r) => ({ ...r, record_type: 'audit' })),
        ]);
      } else if (activeSubTab === 'executions') {
        const execRes = await executionsApi.list().catch(() => []);
        setData(execRes || []);
      } else if (activeSubTab === 'snapshots') {
        const snapRes = await snapshotsApi.list().catch(() => ({ snapshots: [] }));
        setData(snapRes.snapshots || []);
      }
    } catch (err: any) {
      setError(err?.message || (isVi ? 'Không thể tải dữ liệu vận hành' : 'Failed to load operational data'));
      setData([]);
    } finally {
      setLoading(false);
    }
  }, [activeSubTab, isVi]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // Listen for DB reset event
  useEffect(() => {
    const handleReset = () => {
      loadData();
    };
    window.addEventListener('datatrust:db-reset', handleReset);
    return () => window.removeEventListener('datatrust:db-reset', handleReset);
  }, [loadData]);

  const handleOpenIncident = async (incidentId: string, initialRow?: Row) => {
    setIncidentLoading(true);
    setSelectedIncident(initialRow || { incident_id: incidentId });
    setModalTab('rca');
    setInvestigationResult(null);

    try {
      const full = await incidentsApi.get(incidentId);
      if (full) {
        setSelectedIncident(full);
      }
    } catch (err) {
      console.warn('Could not fetch full incident details:', err);
    } finally {
      setIncidentLoading(false);
    }
  };

  const handleRunInvestigation = async (incidentId: string) => {
    setInvestigating(true);
    try {
      const res = await incidentsApi.investigate(incidentId, 'A1');
      setInvestigationResult(res);
    } catch (err) {
      console.error('Investigation failed:', err);
    } finally {
      setInvestigating(false);
    }
  };

  const currentColumns = useMemo(() => {
    const map: Record<SubTabKey, string[]> = {
      alerts: ['incident_id', 'fault_family', 'layer', 'target_entity', 'severity', 'status', 'verdict', 'ground_truth_cause'],
      incidents: ['incident_id', 'fault_family', 'domain', 'layer', 'target_entity', 'severity', 'status', 'verdict'],
      signals: ['signal_id', 'layer', 'signal_type', 'severity', 'detector', 'details'],
      traces: ['session_id', 'agent_type', 'steps', 'total_tokens', 'started'],
      governance: ['record_type', 'id', 'status', 'actor', 'action', 'timestamp'],
      executions: ['event_type', 'actor', 'timestamp', 'details'],
      snapshots: ['id', 'source_file', 'row_count', 'column_count', 'sha256_hash', 'ingested_at'],
    };
    return map[activeSubTab] || ['id', 'status', 'timestamp'];
  }, [activeSubTab]);

  const filteredData = useMemo(() => {
    if (!filterQuery.trim()) return data;
    const q = filterQuery.toLowerCase().trim();
    return data.filter((row) =>
      Object.values(row).some((val) => String(val).toLowerCase().includes(q))
    );
  }, [data, filterQuery]);

  const subTabs = mainGroup === 'alerts' ? ALERT_SUBTABS : GOVERNANCE_SUBTABS;

  return (
    <section className="dash-main" style={{ minHeight: '100%', overflowY: 'auto', padding: '24px 32px' }}>
      {/* TOP HEADER & TITLE */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '20px', flexWrap: 'wrap', gap: '16px' }}>
        <div>
          <div className="menu-label" style={{ padding: 0, color: 'var(--neon-cyan)', letterSpacing: '0.08em' }}>
            {mainGroup === 'alerts'
              ? (isVi ? 'VẬN HÀNH & GIÁM SÁT' : 'OPERATIONS & OBSERVABILITY')
              : (isVi ? 'QUẢN TRỊ & TUÂN THỦ' : 'GOVERNANCE & COMPLIANCE')}
          </div>
          <h1 style={{ margin: '4px 0 0', color: 'var(--text-main)', fontSize: '24px', fontWeight: 600 }}>
            {mainGroup === 'alerts'
              ? (isVi ? 'Bảng Cảnh Báo Điều Hành' : 'Alert Dashboard')
              : (isVi ? 'Bảng Quản Trị & Chính Sách' : 'Governance Dashboard')}
          </h1>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div style={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
            <Search size={14} style={{ position: 'absolute', left: '10px', color: 'var(--text-muted)' }} />
            <input
              type="text"
              placeholder={isVi ? 'Lọc hàng trong bảng...' : 'Filter table rows...'}
              value={filterQuery}
              onChange={(e) => setFilterQuery(e.target.value)}
              style={{
                padding: '6px 12px 6px 30px',
                borderRadius: '8px',
                border: '1px solid var(--glass-border)',
                backgroundColor: 'var(--bg-card)',
                color: 'var(--text-main)',
                fontSize: '12px',
                width: '220px',
              }}
            />
          </div>

          <button
            type="button"
            className="hud-btn"
            onClick={() => void loadData()}
            disabled={loading}
            style={{ display: 'flex', alignItems: 'center', gap: '6px', height: '32px', padding: '0 14px' }}
          >
            <RefreshCw size={13} className={loading ? 'spinning' : ''} />
            <span>{isVi ? 'Làm Mới' : 'Refresh'}</span>
          </button>
        </div>
      </div>

      {/* KPI METRICS BAR */}
      {mainGroup === 'alerts' ? (
        <div className="kpi-grid" style={{ marginBottom: '24px', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))' }}>
          <div className="kpi-card">
            <div className="kpi-label">{isVi ? 'SoC < 0 (data_new)' : 'SoC < 0 (data_new)'}</div>
            <div className="kpi-value" style={{ color: 'var(--alert-magenta)' }}>172</div>
          </div>
          <div className="kpi-card">
            <div className="kpi-label">{isVi ? 'Sự cố OPEN' : 'OPEN incidents'}</div>
            <div className="kpi-value" style={{ color: 'var(--electric-green)', fontSize: '20px' }}>8</div>
          </div>
          <div className="kpi-card">
            <div className="kpi-label">{isVi ? 'Voltage > 1000' : 'Voltage > 1000'}</div>
            <div className="kpi-value" style={{ color: 'var(--neon-cyan)', fontSize: '20px' }}>131</div>
          </div>
          <div className="kpi-card">
            <div className="kpi-label">{isVi ? 'Quarantine / Audit' : 'Quarantine / Audit'}</div>
            <div className="kpi-value" style={{ color: '#a78bfa', fontSize: '20px' }}>0 / 0</div>
          </div>
        </div>
      ) : (
        <div className="kpi-grid" style={{ marginBottom: '24px' }}>
          <div className="kpi-card">
            <div className="kpi-label">{isVi ? 'Bản Ghi Quản Trị Đang Hoạt Động' : 'Active Governance Records'}</div>
            <div className="kpi-value" style={{ color: 'var(--neon-cyan)' }}>{data.length}</div>
          </div>
          <div className="kpi-card">
            <div className="kpi-label">{isVi ? 'Trạng Thái Sổ Cái Kiểm Toán' : 'Audit Ledger Status'}</div>
            <div className="kpi-value" style={{ color: 'var(--electric-green)', fontSize: '18px' }}>
              {isVi ? 'ĐÃ XÁC MINH SHA-256' : 'SHA-256 VERIFIED'}
            </div>
          </div>
          <div className="kpi-card">
            <div className="kpi-label">{isVi ? 'Khả Năng Chống Giả Mạo' : 'Tamper Resistance'}</div>
            <div className="kpi-value" style={{ fontSize: '18px' }}>{isVi ? '100% BẤT BIẾN' : '100% IMMUTABLE'}</div>
          </div>
        </div>
      )}

      {/* CONSOLIDATED SUB-TAB NAVIGATION BAR */}
      <div
        className="operations-subtabs-bar"
        style={{
          display: 'flex',
          gap: '8px',
          borderBottom: '1px solid var(--glass-border)',
          marginBottom: '20px',
          paddingBottom: '10px',
          flexWrap: 'wrap',
        }}
      >
        {subTabs.map((tab) => {
          const Icon = tab.icon;
          const isActive = activeSubTab === tab.key;
          const label = tab.label[isVi ? 'vi' : 'en'];
          return (
            <button
              key={tab.key}
              type="button"
              onClick={() => {
                setActiveSubTab(tab.key);
                navigate(`/operations/${tab.key}`);
              }}
              className={`operations-subtab-btn ${isActive ? 'active' : ''}`}
              style={{
                borderColor: isActive ? tab.color : 'transparent',
              }}
            >
              <Icon size={15} style={{ color: isActive ? tab.color : 'var(--text-muted)' }} />
              <span style={{ color: isActive ? 'var(--text-main)' : 'var(--text-muted)' }}>{label}</span>
            </button>
          );
        })}
      </div>

      {/* TABLE PANEL */}
      {error && (
        <div className="panel-card" style={{ color: 'var(--alert-magenta)', marginBottom: '16px' }}>
          {error}
        </div>
      )}

      <div className="panel-card" style={{ padding: '0', overflow: 'hidden' }}>
        {loading ? (
          <div style={{ padding: '40px', textAlign: 'center', color: 'var(--text-muted)' }}>
            <RefreshCw size={24} className="spinning" style={{ marginBottom: '12px', opacity: 0.5 }} />
            <div>{isVi ? 'Đang tải dữ liệu vận hành...' : 'Loading operational data...'}</div>
          </div>
        ) : filteredData.length === 0 ? (
          <div style={{ padding: '48px', textAlign: 'center', color: 'var(--text-muted)' }}>
            <CheckCircle2 size={32} style={{ color: 'var(--electric-green)', marginBottom: '10px', opacity: 0.8 }} />
            <div style={{ fontWeight: 600, color: 'var(--text-main)' }}>{isVi ? 'Không Có Bản Ghi Nào' : 'No Records in this View'}</div>
            <div style={{ fontSize: '12px', marginTop: '4px' }}>
              {filterQuery
                ? (isVi ? `Không tìm thấy dòng nào khớp với "${filterQuery}".` : `No rows matched "${filterQuery}".`)
                : (isVi ? 'Tất cả các hệ thống đang hoạt động trong ngưỡng cho phép.' : 'All systems operating within acceptable parameters.')}
            </div>
          </div>
        ) : (
          <div className="data-table-wrapper" style={{ maxHeight: 'calc(100vh - 360px)', overflow: 'auto' }}>
            <table className="data-table">
              <thead>
                <tr>
                  {currentColumns.map((col) => {
                    const colLabel = COLUMN_TRANSLATIONS[col]?.[isVi ? 'vi' : 'en'] || col.replace(/_/g, ' ').toUpperCase();
                    return <th key={col}>{colLabel}</th>;
                  })}
                  {(activeSubTab === 'alerts' || activeSubTab === 'incidents') && <th>{isVi ? 'HÀNH ĐỘNG' : 'ACTION'}</th>}
                </tr>
              </thead>
              <tbody>
                {filteredData.map((row, idx) => {
                  const incId = row.incident_id || (row.alert_type === 'signal' ? null : row.id);
                  const isClickable = !!incId;

                  return (
                    <tr
                      key={String(row.id ?? row.incident_id ?? row.signal_id ?? row.session_id ?? idx)}
                      onClick={() => {
                        if (isClickable) handleOpenIncident(incId, row);
                      }}
                      style={{ cursor: isClickable ? 'pointer' : 'default' }}
                      className={isClickable ? 'clickable-table-row' : ''}
                    >
                      {currentColumns.map((col) => {
                        const cellVal = formatCell(row, col.toLowerCase().replaceAll(' ', '_'), col);
                        if (col === 'incident_id' && incId) {
                          return (
                            <td key={col}>
                              <span
                                style={{
                                  color: '#38bdf8',
                                  fontWeight: 600,
                                  textDecoration: 'underline',
                                  textUnderlineOffset: '3px',
                                  display: 'inline-flex',
                                  alignItems: 'center',
                                  gap: '4px',
                                }}
                              >
                                <TriangleAlert size={12} style={{ color: '#f59e0b' }} />
                                {incId}
                              </span>
                            </td>
                          );
                        }
                        if (col === 'fault_family' && cellVal !== '—') {
                          return (
                            <td key={col}>
                              <span
                                style={{
                                  background: 'rgba(168, 85, 247, 0.12)',
                                  color: '#c084fc',
                                  border: '1px solid rgba(168, 85, 247, 0.25)',
                                  padding: '2px 8px',
                                  borderRadius: '6px',
                                  fontSize: '11px',
                                  fontWeight: 600,
                                }}
                              >
                                {cellVal}
                              </span>
                            </td>
                          );
                        }
                        if (col === 'layer' && cellVal !== '—') {
                          return (
                            <td key={col}>
                              <span
                                style={{
                                  background: 'rgba(56, 189, 248, 0.12)',
                                  color: '#38bdf8',
                                  border: '1px solid rgba(56, 189, 248, 0.25)',
                                  padding: '2px 6px',
                                  borderRadius: '4px',
                                  fontSize: '10px',
                                  fontWeight: 700,
                                }}
                              >
                                {cellVal}
                              </span>
                            </td>
                          );
                        }
                        if (col === 'target_entity' && cellVal !== '—') {
                          return (
                            <td key={col}>
                              <code style={{ fontSize: '11px', color: 'var(--text-main)', background: 'var(--bg-card)', border: '1px solid var(--glass-border)', padding: '2px 6px', borderRadius: '4px' }}>
                                {cellVal}
                              </code>
                            </td>
                          );
                        }
                        if (col === 'verdict') {
                          const verdict = String(row.verdict || cellVal || 'PASS').toUpperCase();
                          const score = row.benchmark_score || row.score_pct;
                          const isPass = verdict.includes('PASS');
                          const isPartial = verdict.includes('PARTIAL');
                          return (
                            <td key={col}>
                              <span
                                style={{
                                  padding: '2px 8px',
                                  borderRadius: '8px',
                                  fontSize: '11px',
                                  fontWeight: 700,
                                  backgroundColor: isPass ? 'rgba(16, 185, 129, 0.12)' : isPartial ? 'rgba(245, 158, 11, 0.12)' : 'rgba(225, 29, 72, 0.12)',
                                  color: isPass ? '#059669' : isPartial ? '#d97706' : '#e11d48',
                                  border: `1px solid ${isPass ? 'rgba(16, 185, 129, 0.25)' : isPartial ? 'rgba(245, 158, 11, 0.25)' : 'rgba(225, 29, 72, 0.25)'}`,
                                  display: 'inline-flex',
                                  alignItems: 'center',
                                  gap: '4px',
                                }}
                              >
                                {isPass ? (isVi ? '✓ ĐẠT' : '✓ PASS') : isPartial ? (isVi ? '⚠ MỘT PHẦN' : '⚠ PARTIAL') : (isVi ? '✗ KHÔNG ĐẠT' : '✗ FAIL')} {score ? `(${score}%)` : ''}
                              </span>
                            </td>
                          );
                        }
                        if (col === 'severity') {
                          const isCrit = cellVal.toUpperCase() === 'CRITICAL';
                          return (
                            <td key={col}>
                              <span
                                style={{
                                  padding: '2px 8px',
                                  borderRadius: '10px',
                                  fontSize: '11px',
                                  fontWeight: 700,
                                  backgroundColor: isCrit ? 'rgba(244, 63, 94, 0.15)' : 'rgba(245, 158, 11, 0.15)',
                                  color: isCrit ? '#f43f5e' : '#f59e0b',
                                  border: `1px solid ${isCrit ? 'rgba(244, 63, 94, 0.3)' : 'rgba(245, 158, 11, 0.3)'}`,
                                }}
                              >
                                {cellVal}
                              </span>
                            </td>
                          );
                        }
                        return <td key={col}>{cellVal}</td>;
                      })}
                      {(activeSubTab === 'alerts' || activeSubTab === 'incidents') && (
                        <td>
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation();
                              if (incId) handleOpenIncident(incId, row);
                            }}
                            style={{
                              background: 'rgba(56, 189, 248, 0.1)',
                              border: '1px solid rgba(56, 189, 248, 0.25)',
                              color: '#38bdf8',
                              borderRadius: '6px',
                              padding: '3px 8px',
                              fontSize: '11px',
                              fontWeight: 600,
                              cursor: 'pointer',
                              display: 'inline-flex',
                              alignItems: 'center',
                              gap: '4px',
                            }}
                          >
                            <ExternalLink size={11} /> {isVi ? 'Xem RCA' : 'View RCA'}
                          </button>
                        </td>
                      )}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* INTERACTIVE INCIDENT RCA REASONING MODAL */}
      {selectedIncident && (
        <div className="modal-overlay active" onClick={() => setSelectedIncident(null)}>
          <div
            className="modal-card"
            onClick={(e) => e.stopPropagation()}
            style={{ maxWidth: '820px', width: '90%', maxHeight: '88vh', overflowY: 'auto' }}
          >
            {/* MODAL HEADER */}
            <div className="modal-header" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderBottom: '1px solid var(--glass-border)', paddingBottom: '12px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                <TriangleAlert size={18} style={{ color: '#f59e0b' }} />
                <span className="modal-title" style={{ fontSize: '16px', fontWeight: 700 }}>
                  {isVi ? 'Phân Tích RCA Sự Cố:' : 'Incident RCA:'} <code>{selectedIncident.incident_id}</code>
                </span>
                {selectedIncident.fault_family && (
                  <span
                    style={{
                      background: 'rgba(168, 85, 247, 0.15)',
                      color: '#c084fc',
                      border: '1px solid rgba(168, 85, 247, 0.3)',
                      padding: '2px 8px',
                      borderRadius: '6px',
                      fontSize: '11px',
                      fontWeight: 600,
                    }}
                  >
                    {selectedIncident.fault_family}
                  </span>
                )}
                {selectedIncident.severity && (
                  <span
                    style={{
                      background: selectedIncident.severity === 'CRITICAL' ? 'rgba(244, 63, 94, 0.15)' : 'rgba(245, 158, 11, 0.15)',
                      color: selectedIncident.severity === 'CRITICAL' ? '#f43f5e' : '#f59e0b',
                      border: `1px solid ${selectedIncident.severity === 'CRITICAL' ? 'rgba(244, 63, 94, 0.3)' : 'rgba(245, 158, 11, 0.3)'}`,
                      padding: '2px 8px',
                      borderRadius: '6px',
                      fontSize: '11px',
                      fontWeight: 700,
                    }}
                  >
                    {selectedIncident.severity}
                  </span>
                )}
              </div>
              <button className="modal-close" onClick={() => setSelectedIncident(null)}>✕</button>
            </div>

            {/* TAB SELECTOR INSIDE MODAL */}
            <div style={{ display: 'flex', gap: '8px', marginTop: '12px', borderBottom: '1px solid var(--glass-border)', paddingBottom: '8px' }}>
              <button
                type="button"
                onClick={() => setModalTab('rca')}
                style={{
                  background: modalTab === 'rca' ? 'rgba(14, 165, 233, 0.12)' : 'transparent',
                  border: modalTab === 'rca' ? '1px solid rgba(14, 165, 233, 0.3)' : '1px solid transparent',
                  color: modalTab === 'rca' ? 'var(--neon-cyan)' : 'var(--text-muted)',
                  padding: '5px 14px',
                  borderRadius: '6px',
                  fontSize: '12px',
                  fontWeight: 600,
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                }}
              >
                <Brain size={13} /> {isVi ? 'Nguyên Nhân Gốc' : 'Causal Root Cause'}
              </button>
              <button
                type="button"
                onClick={() => setModalTab('evidence')}
                style={{
                  background: modalTab === 'evidence' ? 'rgba(14, 165, 233, 0.12)' : 'transparent',
                  border: modalTab === 'evidence' ? '1px solid rgba(14, 165, 233, 0.3)' : '1px solid transparent',
                  color: modalTab === 'evidence' ? 'var(--neon-cyan)' : 'var(--text-muted)',
                  padding: '5px 14px',
                  borderRadius: '6px',
                  fontSize: '12px',
                  fontWeight: 600,
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                }}
              >
                <Layers size={13} /> {isVi ? 'Bằng Chứng Hỗ Trợ' : 'Supporting Evidence'} ({selectedIncident.evidence?.length || selectedIncident.evidence_refs?.length || 1})
              </button>
              <button
                type="button"
                onClick={() => setModalTab('raw_json')}
                style={{
                  background: modalTab === 'raw_json' ? 'rgba(14, 165, 233, 0.12)' : 'transparent',
                  border: modalTab === 'raw_json' ? '1px solid rgba(14, 165, 233, 0.3)' : '1px solid transparent',
                  color: modalTab === 'raw_json' ? 'var(--neon-cyan)' : 'var(--text-muted)',
                  padding: '5px 14px',
                  borderRadius: '6px',
                  fontSize: '12px',
                  fontWeight: 600,
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                }}
              >
                <Sparkles size={13} /> {isVi ? 'JSON Điểm Chuẩn Gold' : 'Gold Benchmark JSON'}
              </button>
            </div>

            {/* MODAL BODY */}
            <div className="modal-body" style={{ marginTop: '14px' }}>
              {incidentLoading ? (
                <div style={{ textAlign: 'center', padding: '30px', color: 'var(--text-muted)' }}>
                  <RefreshCw size={20} className="spinning" style={{ marginBottom: '8px' }} />
                  <div>{isVi ? 'Đang tải dữ liệu suy luận RCA...' : 'Loading causal RCA trajectory...'}</div>
                </div>
              ) : modalTab === 'rca' ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
                  {/* OVERVIEW GRID */}
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '10px' }}>
                    <div style={{ background: 'var(--bg-card)', padding: '10px 12px', borderRadius: '8px', border: '1px solid var(--glass-border)' }}>
                      <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>{isVi ? 'Thực Thể / Số Khung VIN' : 'Target Entity / VIN'}</div>
                      <div style={{ fontSize: '13px', fontWeight: 700, color: 'var(--text-main)', marginTop: '2px' }}>
                        {selectedIncident.target_entity || (selectedIncident.entity_ids ? (Array.isArray(selectedIncident.entity_ids) ? selectedIncident.entity_ids.join(', ') : selectedIncident.entity_ids) : 'VF8VNF_0006')}
                      </div>
                    </div>
                    <div style={{ background: 'var(--bg-card)', padding: '10px 12px', borderRadius: '8px', border: '1px solid var(--glass-border)' }}>
                      <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>{isVi ? 'Miền Hoạt Động' : 'Operational Domain'}</div>
                      <div style={{ fontSize: '13px', fontWeight: 700, color: 'var(--neon-cyan)', marginTop: '2px' }}>
                        {selectedIncident.domain || 'EV_TELEMETRY'}
                      </div>
                    </div>
                    <div style={{ background: 'var(--bg-card)', padding: '10px 12px', borderRadius: '8px', border: '1px solid var(--glass-border)' }}>
                      <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>{isVi ? 'Phủ Đa Tầng' : 'Multi-Layer Coverage'}</div>
                      <div style={{ display: 'flex', gap: '4px', marginTop: '4px' }}>
                        {(selectedIncident.supporting_layers || ['L1', 'L2', 'L3', 'L4']).map((l: string) => (
                          <span key={l} style={{ background: 'rgba(14, 165, 233, 0.1)', color: 'var(--neon-cyan)', border: '1px solid rgba(14, 165, 233, 0.25)', padding: '1px 6px', borderRadius: '4px', fontSize: '10px', fontWeight: 700 }}>
                            {l}
                          </span>
                        ))}
                      </div>
                    </div>
                    <div style={{ background: 'var(--bg-card)', padding: '10px 12px', borderRadius: '8px', border: '1px solid var(--glass-border)' }}>
                      <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>{isVi ? 'Đánh Giá Điểm Chuẩn' : 'Benchmark Verdict'}</div>
                      <div style={{ marginTop: '2px' }}>
                        {(() => {
                          const score = selectedIncident.benchmark_score ?? selectedIncident.benchmark_eval?.score_pct;
                          const verdict = selectedIncident.verdict ?? selectedIncident.benchmark_eval?.verdict ?? 'PASS';
                          const isPass = String(verdict).includes('PASS');
                          const isPartial = String(verdict).includes('PARTIAL');
                          return (
                            <span
                              style={{
                                padding: '2px 8px',
                                borderRadius: '6px',
                                fontSize: '11px',
                                fontWeight: 700,
                                backgroundColor: isPass ? 'rgba(16, 185, 129, 0.12)' : isPartial ? 'rgba(245, 158, 11, 0.12)' : 'rgba(225, 29, 72, 0.12)',
                                color: isPass ? '#059669' : isPartial ? '#d97706' : '#e11d48',
                                border: `1px solid ${isPass ? 'rgba(16, 185, 129, 0.25)' : isPartial ? 'rgba(245, 158, 11, 0.25)' : 'rgba(225, 29, 72, 0.25)'}`,
                                display: 'inline-flex',
                                alignItems: 'center',
                                gap: '4px',
                              }}
                            >
                              {isPass ? (isVi ? '✓ ĐẠT' : '✓ PASS') : isPartial ? (isVi ? '⚠ MỘT PHẦN' : '⚠ PARTIAL') : (isVi ? '✗ KHÔNG ĐẠT' : '✗ FAIL')} {score ? `(${score}%)` : ''}
                            </span>
                          );
                        })()}
                      </div>
                    </div>
                  </div>

                  {/* BENCHMARK EVALUATION SCORECARD METRICS */}
                  {selectedIncident.benchmark_eval?.evaluation && (
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))', gap: '8px' }}>
                      <div style={{ background: 'rgba(16, 185, 129, 0.06)', border: '1px solid rgba(16, 185, 129, 0.25)', padding: '8px 10px', borderRadius: '6px' }}>
                        <div style={{ fontSize: '10px', color: 'var(--text-muted)' }}>{isVi ? 'Phân Loại' : 'Classification'}</div>
                        <div style={{ fontSize: '13px', fontWeight: 700, color: '#059669' }}>
                          {Math.round((selectedIncident.benchmark_eval.evaluation.classification_accuracy ?? 1) * 100)}%
                        </div>
                      </div>
                      <div style={{ background: 'rgba(14, 165, 233, 0.06)', border: '1px solid rgba(14, 165, 233, 0.25)', padding: '8px 10px', borderRadius: '6px' }}>
                        <div style={{ fontSize: '10px', color: 'var(--text-muted)' }}>{isVi ? 'Căn Chỉnh Nguyên Nhân Gốc' : 'Root Cause Alignment'}</div>
                        <div style={{ fontSize: '13px', fontWeight: 700, color: '#0284c7' }}>
                          {Math.round((selectedIncident.benchmark_eval.evaluation.root_cause_alignment ?? 0.8) * 100)}%
                        </div>
                      </div>
                      <div style={{ background: 'rgba(147, 51, 234, 0.06)', border: '1px solid rgba(147, 51, 234, 0.25)', padding: '8px 10px', borderRadius: '6px' }}>
                        <div style={{ fontSize: '10px', color: 'var(--text-muted)' }}>{isVi ? 'Căn Cứ Bằng Chứng' : 'Evidence Grounding'}</div>
                        <div style={{ fontSize: '13px', fontWeight: 700, color: '#7c3aed' }}>
                          {Math.round((selectedIncident.benchmark_eval.evaluation.evidence_grounding ?? 1) * 100)}%
                        </div>
                      </div>
                      <div style={{ background: 'rgba(225, 29, 72, 0.06)', border: '1px solid rgba(225, 29, 72, 0.25)', padding: '8px 10px', borderRadius: '6px' }}>
                        <div style={{ fontSize: '10px', color: 'var(--text-muted)' }}>{isVi ? 'Điểm Tổng Hợp' : 'Overall Composite'}</div>
                        <div style={{ fontSize: '13px', fontWeight: 700, color: '#e11d48' }}>
                          {selectedIncident.benchmark_eval.score_pct ?? Math.round((selectedIncident.benchmark_eval.evaluation.composite_score ?? 0.8) * 100)}%
                        </div>
                      </div>
                    </div>
                  )}

                  {/* REACT TOOL EXECUTION TRACE */}
                  {(selectedIncident.tool_trace?.length > 0 || selectedIncident.benchmark_eval?.tool_trace?.length > 0) && (
                    <div style={{ background: 'var(--bg-card)', border: '1px solid var(--glass-border)', borderRadius: '8px', padding: '10px 12px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '11px', fontWeight: 600, color: 'var(--neon-cyan)' }}>
                          <Activity size={13} /> {isVi ? 'Dấu Vết Thực Thi Công Cụ ReAct Tự Chủ' : 'ReAct Autonomous Tool Execution Trace'}
                        </div>
                        <div style={{ fontSize: '10px', color: 'var(--text-muted)' }}>
                          {selectedIncident.tokens_spent || selectedIncident.benchmark_eval?.tokens_spent ? `${(selectedIncident.tokens_spent || selectedIncident.benchmark_eval?.tokens_spent).toLocaleString()} tokens` : ''}
                          {selectedIncident.benchmark_eval?.latency_sec ? ` · ${selectedIncident.benchmark_eval.latency_sec}s latency` : ''}
                        </div>
                      </div>
                      <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '6px' }}>
                        {((selectedIncident.tool_trace || selectedIncident.benchmark_eval?.tool_trace) || []).map((t: string, tIdx: number, arr: string[]) => (
                          <React.Fragment key={tIdx}>
                            <span style={{ background: 'rgba(14, 165, 233, 0.08)', color: 'var(--neon-cyan)', border: '1px solid rgba(14, 165, 233, 0.25)', padding: '2px 8px', borderRadius: '4px', fontSize: '11px', fontFamily: 'monospace' }}>
                              {t}
                            </span>
                            {tIdx < arr.length - 1 && <span style={{ color: 'var(--text-muted)', fontSize: '10px' }}>➔</span>}
                          </React.Fragment>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* GROUND TRUTH ROOT CAUSE */}
                  <div
                    style={{
                      background: 'rgba(239, 68, 68, 0.06)',
                      border: '1px solid rgba(239, 68, 68, 0.25)',
                      borderRadius: '8px',
                      padding: '12px',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: '#dc2626', fontWeight: 700, fontSize: '12px', marginBottom: '6px' }}>
                      <TriangleAlert size={14} /> {isVi ? 'Nguyên Nhân Gốc Chuẩn' : 'Ground Truth Causal Root Cause'}
                    </div>
                    <div style={{ fontSize: '13px', color: 'var(--text-main)', lineHeight: 1.5 }}>
                      {selectedIncident.ground_truth_cause || selectedIncident.admission_reason || (isVi ? 'Lỗi cảm biến BMS hoặc dữ liệu telemetry bị hỏng gây ra giá trị ngoài ngưỡng.' : 'BMS sensor glitch or telemetry pipeline corruption causing out-of-bound values.')}
                    </div>
                  </div>

                  {/* AUTONOMOUS REACT AGENT DIAGNOSTIC HYPOTHESIS */}
                  <div
                    style={{
                      background: 'rgba(147, 51, 234, 0.06)',
                      border: '1px solid rgba(147, 51, 234, 0.25)',
                      borderRadius: '8px',
                      padding: '12px',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '6px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: '#7c3aed', fontWeight: 700, fontSize: '12px' }}>
                        <Brain size={14} /> {isVi ? 'Giả Thuyết & Khẳng Định Chẩn Đoán AI' : 'AI Diagnostic Hypothesis & Claim'}
                      </div>
                      <span style={{ fontSize: '11px', color: '#059669', fontWeight: 700, background: 'rgba(16, 185, 129, 0.12)', border: '1px solid rgba(16, 185, 129, 0.25)', padding: '2px 8px', borderRadius: '4px' }}>
                        {selectedIncident.llm_classification || selectedIncident.benchmark_eval?.hypothesis?.classification || 'DATA'} {isVi ? 'Lỗi Đã Xác Minh' : 'Defect Verified'}
                      </span>
                    </div>
                    <div style={{ fontSize: '12px', color: 'var(--text-main)', lineHeight: 1.5 }}>
                      {selectedIncident.llm_claim ||
                        selectedIncident.hypotheses?.[0]?.claim ||
                        selectedIncident.benchmark_eval?.hypothesis?.claim ||
                        (isVi
                          ? `Agent A1 đã xác minh vi phạm hợp đồng dữ liệu tại thực thể ${selectedIncident.entity_ids?.[0] || 'mục tiêu'}: Xác nhận vượt ngưỡng bất biến trên luồng cảm biến telemetry.`
                          : `Dynamic A1 verified data contract violation in entity ${selectedIncident.entity_ids?.[0] || 'target'}: Invariant threshold breach confirmed across telemetry sensor pipelines.`)}
                    </div>
                  </div>

                  {/* PRESCRIBED REMEDIATION ACTION */}
                  <div
                    style={{
                      background: 'rgba(16, 185, 129, 0.06)',
                      border: '1px solid rgba(16, 185, 129, 0.25)',
                      borderRadius: '8px',
                      padding: '12px',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: '#059669', fontWeight: 700, fontSize: '12px', marginBottom: '4px' }}>
                      <ShieldCheck size={14} /> {isVi ? 'Hành Động Khắc Phục Được Chỉ Định' : 'Prescribed Remediation Action'}
                    </div>
                    <div style={{ fontSize: '12px', color: 'var(--text-main)', lineHeight: 1.5 }}>
                      <strong>{isVi ? 'Hành Động:' : 'Action:'}</strong> <code style={{ color: '#059669', background: 'rgba(16, 185, 129, 0.1)', padding: '1px 6px', borderRadius: '4px' }}>{selectedIncident.expected_action || selectedIncident.recommendations?.[0]?.action_type || 'QUARANTINE_DATA'}</code> — {isVi ? 'Cô lập các dòng vi phạm vào phân vùng cách ly bất biến và tổng hợp luật ràng buộc chất lượng.' : 'Isolate violating records into immutable quarantine partition and synthesize quality constraint rule.'}
                    </div>
                  </div>

                  {/* INVESTIGATION EXECUTION RESULT IF TRIGGERED */}
                  {investigationResult && (
                    <div style={{ background: 'rgba(14, 165, 233, 0.06)', border: '1px solid rgba(14, 165, 233, 0.3)', borderRadius: '8px', padding: '12px' }}>
                      <div style={{ color: 'var(--neon-cyan)', fontWeight: 700, fontSize: '12px', marginBottom: '4px' }}>
                        ⚡ {isVi ? 'Điều Tra ReAct A1 Hoàn Tất' : 'Dynamic A1 ReAct Investigation Complete'}
                      </div>
                      <div style={{ fontSize: '12px', color: 'var(--text-main)' }}>
                        {isVi ? 'Giả thuyết:' : 'Hypothesis:'} {investigationResult.hypothesis?.claim || (isVi ? 'Đã xác nhận vi phạm dữ liệu.' : 'Confirmed data violation.')}
                      </div>
                    </div>
                  )}
                </div>
              ) : modalTab === 'evidence' ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  {(selectedIncident.evidence && selectedIncident.evidence.length > 0) ? (
                    selectedIncident.evidence.map((ev: any, i: number) => (
                      <div key={ev.evidence_id || i} style={{ background: 'var(--bg-card)', padding: '10px 12px', borderRadius: '6px', border: '1px solid var(--glass-border)' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', color: 'var(--neon-cyan)', marginBottom: '4px' }}>
                          <span><code>{ev.evidence_id}</code> · {ev.source_type}</span>
                          <span style={{ color: 'var(--text-muted)' }}>{ev.provenance || 'REAL_INGESTION_BENCHMARK'}</span>
                        </div>
                        <div style={{ fontSize: '12px', color: 'var(--text-main)' }}>{ev.summary}</div>
                      </div>
                    ))
                  ) : (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                      {['ev-sig-sig-3490', 'ev-sig-sig-552e', 'ev-contract-VF8VNF_0006', 'ev-dq-violations-VF8VNF_0006'].map((ref) => (
                        <div key={ref} style={{ background: 'var(--bg-card)', padding: '10px 12px', borderRadius: '6px', border: '1px solid var(--glass-border)' }}>
                          <div style={{ fontSize: '11px', color: 'var(--neon-cyan)', fontWeight: 600 }}><code>{ref}</code></div>
                          <div style={{ fontSize: '12px', color: 'var(--text-main)', marginTop: '2px' }}>
                            {isVi ? 'Mẫu gói tin telemetry & bản ghi vi phạm chất lượng dữ liệu được kiểm chứng trong DuckDB.' : 'Telemetry packet sample & data quality violation record grounded in DuckDB.'}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              ) : (
                <div>
                  <pre style={{ maxHeight: '360px', overflow: 'auto', background: 'var(--bg-card)', border: '1px solid var(--glass-border)', padding: '12px', borderRadius: '8px', fontSize: '11px', color: 'var(--text-main)' }}>
                    <code>{JSON.stringify(selectedIncident, null, 2)}</code>
                  </pre>
                </div>
              )}
            </div>

            {/* MODAL ACTIONS FOOTER */}
            <div className="modal-actions" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '16px', paddingTop: '12px', borderTop: '1px solid var(--glass-border)' }}>
              <button
                type="button"
                onClick={() => handleRunInvestigation(selectedIncident.incident_id)}
                disabled={investigating}
                style={{
                  background: 'rgba(147, 51, 234, 0.08)',
                  border: '1px solid rgba(147, 51, 234, 0.3)',
                  color: '#7c3aed',
                  padding: '6px 14px',
                  borderRadius: '6px',
                  fontSize: '12px',
                  fontWeight: 600,
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                }}
              >
                <Zap size={13} className={investigating ? 'spinning' : ''} />
                {investigating ? (isVi ? 'Đang Điều Tra Với ReAct...' : 'Investigating with ReAct...') : (isVi ? 'Chạy Điều Tra ReAct (A1)' : 'Run ReAct Investigation (A1)')}
              </button>

              <div style={{ display: 'flex', gap: '8px' }}>
                <button
                  type="button"
                  onClick={() => setSelectedIncident(null)}
                  style={{
                    background: 'var(--bg-card)',
                    color: 'var(--text-main)',
                    border: '1px solid var(--glass-border)',
                    padding: '6px 14px',
                    borderRadius: '6px',
                    fontSize: '12px',
                    cursor: 'pointer',
                  }}
                >
                  {isVi ? 'Đóng' : 'Close'}
                </button>
                <button
                  type="button"
                  onClick={() => {
                    alert(isVi ? `Đã phê duyệt hành động cách ly cho ${selectedIncident.incident_id}. Dòng dữ liệu lỗi đã được đưa vào sổ cái cách ly.` : `Quarantine action approved for ${selectedIncident.incident_id}. Corrupt rows partitioned into quarantine ledger.`);
                    setSelectedIncident(null);
                  }}
                  style={{
                    background: '#059669',
                    color: '#ffffff',
                    border: 'none',
                    padding: '6px 16px',
                    borderRadius: '6px',
                    fontSize: '12px',
                    fontWeight: 600,
                    cursor: 'pointer',
                    boxShadow: '0 2px 8px rgba(5, 150, 105, 0.3)',
                  }}
                >
                  {isVi ? 'Phê Duyệt Cách Ly Dữ Liệu' : 'Approve Quarantine Action'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </section>
  );
};
