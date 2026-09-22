import React, { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import {
  Boxes,
  Layers,
  Clock,
  Brain,
  Lightbulb,
  ChartLine,
  Bot,
  Microchip,
  ShieldCheck,
  Waypoints,
  Check,
  X,
  Pencil,
  Save,
  AlertTriangle,
  Database,
  CheckCircle2,
  UserCheck,
  Search,
  Fingerprint,
  ArrowRight,
} from 'lucide-react';
import { useDashboardStore } from '../stores/dashboardStore';
import { usePipelineStore } from '../stores/pipelineStore';
import { hitlApi, summaryApi } from '../services/api';
import type { HITLProposal } from '../services/api';
import { useAuthStore } from '../stores/authStore';

const SEVERITY_BADGE: Record<string, string> = {
  HIGH: 'danger',
  CRITICAL: 'danger',
  MEDIUM: 'warning',
  LOW: 'info',
};

export const ExecutiveDashboard: React.FC = () => {
  const navigate = useNavigate();
  const { t, i18n } = useTranslation('pipeline');
  const isVi = i18n.language === 'vi';
  const canReviewRules = useAuthStore((s) => s.canReviewRules());
  const metrics = useDashboardStore((s) => s.metrics);
  const insights = useDashboardStore((s) => s.insights);
  const activityFeed = useDashboardStore((s) => s.activityFeed);
  const signals = useDashboardStore((s) => s.signals);
  const incidents = useDashboardStore((s) => s.incidents);
  const summary = useDashboardStore((s) => s.summary);
  const loading = useDashboardStore((s) => s.loading);
  const dashboardError = useDashboardStore((s) => s.error);
  const fetchDashboardData = useDashboardStore((s) => s.fetchDashboardData);
  const setPipelineProposals = usePipelineStore((s) => s.setProposals);
  const [proposals, setProposals] = useState<HITLProposal[]>([]);
  const [editingRule, setEditingRule] = useState<HITLProposal | null>(null);
  const [editText, setEditText] = useState('');
  const [ruleStates, setRuleStates] = useState<Record<string, 'approved' | 'rejected' | 'edited'>>({});
  const [trendRange, setTrendRange] = useState<'24h' | '7d' | '30d'>('24h');
  const [trendUnavailable, setTrendUnavailable] = useState(false);
  const chartRef = useRef<HTMLCanvasElement>(null);
  const chartInstance = useRef<{ destroy: () => void; resize: () => void } | null>(null);

  // Data fetching
  useEffect(() => {
    fetchDashboardData();
    hitlApi
      .queue()
      .then((res) => {
        const pending = (res.proposals || []).filter(
          (p) => p.status === 'pending' || p.status === 'proposed'
        );
        setProposals(pending);
        setPipelineProposals(pending);
      })
      .catch(() => setProposals([]));
  }, [fetchDashboardData, setPipelineProposals]);

  useEffect(() => {
    const handleReset = () => {
      fetchDashboardData();
      hitlApi
        .queue()
        .then((res) => {
          const pending = (res.proposals || []).filter(
            (p) => p.status === 'pending' || p.status === 'proposed'
          );
          setProposals(pending);
          setPipelineProposals(pending);
        })
        .catch(() => setProposals([]));
    };
    window.addEventListener('datatrust:db-reset', handleReset);
    return () => window.removeEventListener('datatrust:db-reset', handleReset);
  }, [fetchDashboardData, setPipelineProposals]);

  // Dynamic anomaly trend chart (Chart.js)
  useEffect(() => {
    let isMounted = true;
    const canvas = chartRef.current;
    if (!canvas) return;
    const textColor = '#475569';
    const gridColor = 'rgba(15,23,42,0.08)';
    setTrendUnavailable(false);

    summaryApi
      .getTrend(trendRange)
      .then((res) => {
        if (!isMounted || !canvas) return;
        const labels = res?.labels || [];
        const dataA = res?.voltage_spikes || [];
        const dataB = res?.thermal_flags || [];
        if (!labels.length || (!dataA.length && !dataB.length)) {
          setTrendUnavailable(true);
          return;
        }

        import('chart.js/auto').then(({ default: Chart }) => {
          if (!isMounted) return;
          if (chartInstance.current) chartInstance.current.destroy();
          chartInstance.current = new Chart(canvas, {
            type: 'line',
            data: {
              labels,
              datasets: [
                { label: 'BMS Voltage Spikes', data: dataA, borderColor: '#f87171', backgroundColor: 'rgba(248,113,113,0.08)', fill: true, tension: 0.3, borderWidth: 2, pointRadius: 3 },
                { label: 'Thermal Overheat Flags', data: dataB, borderColor: '#0f172a', backgroundColor: 'rgba(15,23,42,0.06)', fill: true, tension: 0.3, borderWidth: 2, pointRadius: 3 },
              ],
            },
            options: {
              responsive: true,
              maintainAspectRatio: false,
              plugins: { legend: { display: true, position: 'top', labels: { color: textColor, boxWidth: 12, padding: 16 } } },
              scales: {
                x: { grid: { color: gridColor }, ticks: { color: textColor } },
                y: { grid: { color: gridColor }, ticks: { color: textColor } },
              },
            },
          });
        });
      })
      .catch(() => {
        if (!isMounted) return;
        chartInstance.current?.destroy();
        chartInstance.current = null;
        setTrendUnavailable(true);
      });

    return () => {
      isMounted = false;
      if (chartInstance.current) chartInstance.current.destroy();
    };
  }, [trendRange]);

  const handleRuleAction = async (proposal: HITLProposal, action: 'approve' | 'reject' | 'edit') => {
    if (action === 'approve') {
      setRuleStates((s) => ({ ...s, [proposal.rule_id]: 'approved' }));
      setProposals((p) => p.filter((r) => r.rule_id !== proposal.rule_id));
      try {
        await hitlApi.approve(proposal.rule_id);
      } catch {
        // offline: keep local state
      }
    } else if (action === 'reject') {
      setRuleStates((s) => ({ ...s, [proposal.rule_id]: 'rejected' }));
      setProposals((p) => p.filter((r) => r.rule_id !== proposal.rule_id));
      try {
        await hitlApi.reject(proposal.rule_id);
      } catch {
        // offline
      }
    } else if (action === 'edit') {
      setEditingRule(proposal);
      setEditText(proposal.rule_expression);
    }
  };

  const saveRuleEdit = async () => {
    if (!editingRule) return;
    try {
      await hitlApi.edit(editingRule.rule_id, editText);
    } catch {
      // offline
    }
    setRuleStates((s) => ({ ...s, [editingRule.rule_id]: 'edited' }));
    setProposals((p) => p.filter((r) => r.rule_id !== editingRule.rule_id));
    setEditingRule(null);
  };

  const totalSignals = signals.length;
  const openIncidents = incidents.filter((incident) => incident.status === 'OPEN').length;
  const nextAction = loading
    ? {
        title: isVi ? 'Đang tải trạng thái hệ thống' : 'Loading system status',
        description: isVi ? 'Vui lòng chờ trong giây lát.' : 'This should only take a moment.',
        label: isVi ? 'Đang tải…' : 'Loading…',
        path: null,
        step: 1,
      }
    : dashboardError
    ? {
        title: isVi ? 'Chưa tải được dữ liệu tổng quan' : 'Dashboard data is unavailable',
        description: isVi ? 'Kiểm tra kết nối máy chủ rồi thử tải lại. Hệ thống không hiển thị số liệu mẫu thay thế.' : 'Check the server connection and retry. Sample values are not shown as a fallback.',
        label: isVi ? 'Thử tải lại' : 'Retry',
        path: null,
        step: 1,
      }
    : proposals.length > 0
    ? {
        title: isVi ? `Duyệt ${proposals.length} bộ luật đang chờ` : `Review ${proposals.length} pending rule(s)`,
        description: isVi ? 'Kiểm tra đề xuất của AI trước khi áp dụng vào dữ liệu.' : 'Check AI proposals before applying them to data.',
        label: isVi ? 'Duyệt kết quả' : 'Review results',
        path: '/operations/rules',
        step: 3,
      }
    : openIncidents > 0
      ? {
          title: isVi ? `Kiểm tra ${openIncidents} sự cố đang mở` : `Inspect ${openIncidents} open incident(s)`,
          description: isVi ? 'Xem nguyên nhân gốc và bằng chứng trước khi xử lý.' : 'Review root causes and evidence before resolving them.',
          label: isVi ? 'Xem phân tích' : 'View analysis',
          path: '/operations/alerts',
          step: 2,
        }
      : {
          title: isVi ? 'Bắt đầu bằng việc nạp dữ liệu' : 'Start by ingesting data',
          description: isVi ? 'Nạp dữ liệu nền để hệ thống bắt đầu kiểm tra chất lượng.' : 'Load baseline data so quality checks can begin.',
          label: isVi ? 'Nạp dữ liệu' : 'Ingest data',
          path: '/dashboard/ingestion',
          step: 1,
        };
  const layerCounts = signals.reduce(
    (acc, sig) => {
      const l = sig.layer || 'L1';
      acc[l] = (acc[l] || 0) + 1;
      return acc;
    },
    { L1: 0, L2: 0, L3: 0, L4: 0 } as Record<string, number>
  );
  return (
    <div className="dash-main">
      {/* Page header matching Data Ingestion */}
      <div className="ingestion-page-header dash-page-header">
        <div className="iph-title-group">
          <Layers size={22} color="var(--neon-cyan)" />
          <h1 className="iph-title">{isVi ? 'Bảng Điều Khiển Điều Hành' : 'Executive Dashboard'}</h1>
          <span className="iph-subtitle">
            {isVi
              ? 'Tổng quan Giám sát Chất lượng Dữ liệu Doanh nghiệp · HITL Governance & AI Orchestration'
              : 'Enterprise Data Quality Overview · HITL Governance & AI Orchestration'}
          </span>
        </div>
      </div>

      <section className="dashboard-next-action" aria-labelledby="dashboard-next-title">
        <div className="dashboard-workflow" aria-label={isVi ? 'Quy trình chính' : 'Main workflow'}>
          {[1, 2, 3].map((step) => (
            <span key={step} className={step === nextAction.step ? 'active' : step < nextAction.step ? 'done' : ''}>
              <b>{step}</b>
              {step === 1
                ? (isVi ? 'Nạp dữ liệu' : 'Ingest')
                : step === 2
                  ? (isVi ? 'Phân tích' : 'Analyze')
                  : (isVi ? 'Duyệt kết quả' : 'Review')}
            </span>
          ))}
        </div>
        <div className="dashboard-next-body">
          <div>
            <span className="guide-eyebrow">{isVi ? 'VIỆC CẦN LÀM TIẾP THEO' : 'NEXT ACTION'}</span>
            <h2 id="dashboard-next-title">{nextAction.title}</h2>
            <p>{nextAction.description}</p>
          </div>
          <button type="button" className="primary-next-button" disabled={loading} onClick={() => nextAction.path ? navigate(nextAction.path) : void fetchDashboardData()}>
            {nextAction.label}<ArrowRight size={17} />
          </button>
        </div>
      </section>

      {/* TOP SUMMARY KPI CARDS (4 CARDS) */}
      <div className="kpi-grid">
        <div className="kpi-card">
          <div className="kpi-header">
            <span className="kpi-title">{t('enterpriseDatasets')}</span>
            <div className="kpi-icon blue"><Boxes size={15} /></div>
          </div>
          <div className="kpi-value">{loading ? '...' : openIncidents}<span className="unit"> OPEN</span></div>
          <div className="kpi-subtext positive"><CheckCircle2 size={13} /> {summary?.provenance ?? '—'} {isVi ? 'nguồn gốc' : 'provenance'}</div>
        </div>

        <div className="kpi-card">
          <div className="kpi-header">
            <span className="kpi-title">{t('totalRecords')}</span>
            <div className="kpi-icon green"><Layers size={15} /></div>
          </div>
          <div className="kpi-value">{loading ? '...' : metrics.cleanRecords.toLocaleString()}<span className="unit"> {t('rows')}</span></div>
          <div className="kpi-subtext warning"><AlertTriangle size={13} /> {metrics.quarantinedRecords.toLocaleString()} {isVi ? 'bản ghi cách ly' : 'quarantined rows'}</div>
        </div>

        <div className="kpi-card">
          <div className="kpi-header">
            <span className="kpi-title">{t('pendingReview')}</span>
            <div className="kpi-icon amber"><Clock size={15} /></div>
          </div>
          <div className="kpi-value amber">{proposals.length} {t('rules')}</div>
          <div className="kpi-subtext warning"><AlertTriangle size={13} /> {t('requiresAction')}</div>
        </div>

        <div className="kpi-card">
          <div className="kpi-header">
            <span className="kpi-title">{t('aiHealth')}</span>
            <div className="kpi-icon purple"><Brain size={15} /></div>
          </div>
          <div className="kpi-value purple">{loading ? '...' : metrics.avgResolutionTime}</div>
          <div className="kpi-subtext positive"><ShieldCheck size={13} /> {metrics.activeIncidentsCount} {isVi ? 'sự cố đang xử lý' : 'active incident(s)'}</div>
        </div>
      </div>

      {/* MAIN CONTENT GRID (6 PANELS) */}
      <div className="panels-grid primary-panels-grid">
        {/* PANEL 1: AI SUGGESTED RULES */}
        <div className="panel-card panel-suggested-rules">
          <div className="panel-header" style={{ cursor: 'pointer' }} onClick={() => navigate('/operations/rules')}>
            <div className="panel-title-group">
              <Lightbulb size={18} className="text-primary" />
              <h2>{t('suggestedRules')}</h2>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span className="badge-count">{proposals.length} {t('pendingReviewCount')}</span>
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  navigate('/operations/rules');
                }}
                style={{
                  background: 'none',
                  border: 'none',
                  color: 'var(--neon-cyan)',
                  fontSize: '11px',
                  fontWeight: 600,
                  cursor: 'pointer',
                  padding: 0,
                }}
              >
                {isVi ? 'Xem tất cả →' : 'View all →'}
              </button>
            </div>
          </div>

          <div className="rules-list">
            {proposals.length === 0 && ruleStates.approved === undefined && (
              <div className="rule-item" style={{ textAlign: 'center', color: 'var(--text-muted)', padding: '24px' }}>
                <Search size={18} style={{ marginBottom: 6 }} />
                <div>{t('noPendingRules')}</div>
                <div style={{ fontSize: 12, marginTop: 4 }}>{t('noPendingRulesHint')}</div>
              </div>
            )}

            {proposals.slice(0, 2).map((rule) => {
              const sev = (rule.rule_type || '').toUpperCase().includes('HIGH') || (rule.rule_name || '').toLowerCase().includes('high')
                ? 'danger'
                : (rule.rule_type || '').toUpperCase().includes('MEDIUM')
                ? 'warning'
                : 'info';
              const col = rule.rule_name || rule.rule_type || 'unknown';
              return (
                <div key={rule.rule_id} className="rule-item">
                  <div className="rule-top">
                    <span className={`badge ${sev}`}><AlertTriangle size={12} /> {sev === 'danger' ? t('highSeverity') : sev === 'warning' ? t('mediumSeverity') : t('infoSeverity')}</span>
                    <span className="column-tag"><Database size={12} /> {col}</span>
                  </div>
                  <div className="rule-code">
                    <code>{rule.rule_expression}</code>
                  </div>
                  <div className="rule-desc">
                    {rule.proposed_by || 'AI Steward'} · {t('confidence')} {(((rule.confidence ?? 0) <= 1.0 ? (rule.confidence ?? 0) * 100 : (rule.confidence ?? 0))).toFixed(1)}% · {rule.proposed_at ? new Date(rule.proposed_at).toLocaleString() : t('justNow')}
                  </div>
                  <div className="rule-actions">
                    {canReviewRules && (
                      <>
                    <button className="btn-rule approve" onClick={() => handleRuleAction(rule, 'approve')}><Check size={13} /> {t('approveRule')}</button>
                    <button className="btn-rule edit" onClick={() => handleRuleAction(rule, 'edit')}><Pencil size={13} /> {t('editRule')}</button>
                    <button className="btn-rule reject" onClick={() => handleRuleAction(rule, 'reject')}><X size={13} /> {t('rejectRule')}</button>
                      </>
                    )}
                  </div>
                </div>
              );
            })}

            {Object.entries(ruleStates).map(([id, status]) => (
              <div key={id} className="rule-item" style={{ borderColor: status === 'rejected' ? 'var(--alert-magenta)' : 'var(--electric-green)' }}>
                <span className={`badge ${status === 'rejected' ? 'danger' : 'info'}`}>
                  {status === 'approved' ? <CheckCircle2 size={12} /> : status === 'edited' ? <Pencil size={12} /> : <X size={12} />}
                  {status === 'approved' ? t('approvedBySteward') : status === 'edited' ? t('editedBySteward') : t('rejectedBySteward')}
                </span>
              </div>
            ))}

            {proposals.length > 2 && (
              <div style={{ textAlign: 'center', marginTop: '6px' }}>
                <button
                  type="button"
                  onClick={() => navigate('/operations/rules')}
                  style={{
                    background: 'rgba(2, 132, 199, 0.08)',
                    border: '1px solid rgba(2, 132, 199, 0.25)',
                    color: '#0284c7',
                    borderRadius: '6px',
                    padding: '6px 12px',
                    fontSize: '11.5px',
                    fontWeight: 600,
                    cursor: 'pointer',
                    width: '100%',
                    transition: 'all 0.15s ease',
                  }}
                >
                  {isVi ? `Xem thêm ${proposals.length - 2} bộ luật khác →` : `View remaining ${proposals.length - 2} rules →`}
                </button>
              </div>
            )}
          </div>
        </div>

      </div>

      <details
        className="dashboard-details"
        onToggle={(event) => {
          if (event.currentTarget.open) requestAnimationFrame(() => chartInstance.current?.resize());
        }}
      >
        <summary>
          <span>{isVi ? 'Xem phân tích chi tiết' : 'View detailed analysis'}</span>
          <span>{isVi ? 'Biểu đồ, nguyên nhân gốc và hoạt động hệ thống' : 'Charts, root causes, and system activity'}</span>
        </summary>
        <div className="panels-grid dashboard-details-grid">
        {/* PANEL 2: ANOMALY TRENDS */}
        <div className="panel-card panel-anomaly-chart">
          <div className="panel-header">
            <div className="panel-title-group">
              <ChartLine size={18} className="text-primary" />
              <h2>{t('anomalyTrends')}</h2>
            </div>
            <div className="time-filter-select" style={{ display: 'flex', gap: 6 }}>
              {(['24h', '7d', '30d'] as const).map((r) => (
                <button key={r} className={`filter-tab ${trendRange === r ? 'active' : ''}`} onClick={() => setTrendRange(r)}>
                  {r === '24h' ? '24h' : r}
                </button>
              ))}
            </div>
          </div>
          <div className="chart-container">
            <canvas ref={chartRef} id="anomalyTrendChart" hidden={trendUnavailable} />
            {trendUnavailable && (
              <div className="dashboard-empty-state">
                {isVi ? 'Chưa có dữ liệu xu hướng cho khoảng thời gian này.' : 'No trend data is available for this period.'}
              </div>
            )}
          </div>
          <div style={{ display: 'flex', gap: 16, fontSize: 12, color: 'var(--text-muted)', flexWrap: 'wrap' }}>
            <span>{isVi ? 'L1 Schema:' : 'L1 Schema:'} <strong style={{ color: 'var(--text-main)' }}>{layerCounts.L1 || 0}</strong></span>
            <span>{isVi ? 'L2 Độ Lệch:' : 'L2 Drift:'} <strong style={{ color: 'var(--text-main)' }}>{layerCounts.L2 || 0}</strong></span>
            <span>{isVi ? 'L3 Liên Thực Thể:' : 'L3 Multi-Entity:'} <strong style={{ color: 'var(--text-main)' }}>{layerCounts.L3 || 0}</strong></span>
            <span>{isVi ? 'L4 Nguyên Nhân Gốc:' : 'L4 Causal:'} <strong style={{ color: 'var(--text-main)' }}>{layerCounts.L4 || 0}</strong></span>
            <span>{isVi ? 'Tổng Tín Hiệu:' : 'Total Signals:'} <strong style={{ color: 'var(--alert-magenta)' }}>{totalSignals}</strong></span>
          </div>
        </div>

        {/* PANEL 3: live operational summary */}
        <div className="panel-card panel-agent-health">
          <div className="panel-header">
            <div className="panel-title-group">
              <Bot size={18} className="text-primary" />
              <h2>{isVi ? 'Tóm tắt vận hành' : 'Operational summary'}</h2>
            </div>
            <span className={`status-pill ${dashboardError ? 'offline' : 'online'}`}>{dashboardError ? (isVi ? 'Mất kết nối' : 'Unavailable') : (isVi ? 'Dữ liệu thật' : 'Live data')}</span>
          </div>
          <div className="agents-status-list">
            {[
              { label: isVi ? 'Tín hiệu phát hiện' : 'Detected signals', val: String(metrics.totalAnomalies) },
              { label: isVi ? 'Sự cố đang mở' : 'Open incidents', val: String(openIncidents) },
              { label: isVi ? 'Đề xuất chờ duyệt' : 'Pending proposals', val: String(proposals.length) },
              { label: isVi ? 'Bản ghi cách ly' : 'Quarantined rows', val: String(metrics.quarantinedRecords) },
              { label: isVi ? 'Luật đã thực thi' : 'Executed rules', val: String(metrics.rulesExecuted) },
              { label: isVi ? 'Nguồn dữ liệu' : 'Provenance', val: summary?.provenance ?? '—' },
            ].map((row) => (
              <div key={row.label} className="agent-row">
                <div className="agent-name">{row.label}</div>
                <span className="stat-val">{row.val}</span>
              </div>
            ))}
          </div>
        </div>

        {/* PANEL 4: AI DIAGNOSIS & ROOT CAUSE */}
        <div className="panel-card panel-rca">
          <div className="panel-header" style={{ cursor: 'pointer' }} onClick={() => navigate('/operations/alerts')}>
            <div className="panel-title-group">
              <Microchip size={18} className="text-primary" />
              <h2>{t('rcaTitle')}</h2>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span className="confidence-badge"><Fingerprint size={12} /> {insights.length} {t('activeRca')}</span>
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  navigate('/operations/alerts');
                }}
                style={{
                  background: 'none',
                  border: 'none',
                  color: 'var(--neon-cyan)',
                  fontSize: '11px',
                  fontWeight: 600,
                  cursor: 'pointer',
                  padding: 0,
                }}
              >
                {isVi ? 'Xem tất cả →' : 'View all →'}
              </button>
            </div>
          </div>
          <div className="rca-cards-list">
            {insights.length === 0 ? (
              <div className="insight-card" style={{ textAlign: 'center', color: 'var(--text-muted)' }}>
                <div>{t('noIncidents')}</div>
                <div style={{ fontSize: 12, marginTop: 6 }}>{t('noIncidentsHint')}</div>
              </div>
            ) : (
              (() => {
                const sevOrder: Record<string, number> = { CRITICAL: 4, HIGH: 3, MEDIUM: 2, LOW: 1 };
                const sorted = [...insights].sort((a, b) => {
                  const sA = sevOrder[String(a.severity || '').toUpperCase()] || 0;
                  const sB = sevOrder[String(b.severity || '').toUpperCase()] || 0;
                  return sB - sA;
                });
                const top2 = sorted.slice(0, 2);
                return (
                  <>
                    {top2.map((insight) => (
                      <div key={insight.id} className="insight-card">
                        <div className="insight-header">
                          <span className="insight-title"><Microchip size={14} /> {insight.title}</span>
                          <span className={`badge ${SEVERITY_BADGE[insight.severity?.toUpperCase()] || 'info'}`}>{insight.severity || 'MEDIUM'}</span>
                        </div>
                        <div className="insight-body"><strong>{t('rootCause')}</strong> {insight.rootCause}</div>
                        <div className="insight-action"><strong>{t('recommendedAction')}</strong> {insight.recommendedAction}</div>
                      </div>
                    ))}
                    {sorted.length > 2 && (
                      <div style={{ textAlign: 'center', marginTop: '6px' }}>
                        <button
                          type="button"
                          onClick={() => navigate('/operations/alerts')}
                          style={{
                            background: 'rgba(2, 132, 199, 0.08)',
                            border: '1px solid rgba(2, 132, 199, 0.25)',
                            color: '#0284c7',
                            borderRadius: '6px',
                            padding: '6px 12px',
                            fontSize: '11.5px',
                            fontWeight: 600,
                            cursor: 'pointer',
                            width: '100%',
                            transition: 'all 0.15s ease',
                          }}
                        >
                          {isVi ? `Xem thêm ${sorted.length - 2} sự cố & RCA khác →` : `View remaining ${sorted.length - 2} RCA cases →`}
                        </button>
                      </div>
                    )}
                  </>
                );
              })()
            )}
          </div>
        </div>

        {/* AI ACTIVITY FEED */}
        <div className="panel-card panel-activity">
          <div className="panel-header">
            <div className="panel-title-group">
              <Waypoints size={18} className="text-primary" />
              <h2>{t('activityFeed')}</h2>
            </div>
            <span className="live-dot"><span style={{ display: 'inline-block', width: 8, height: 8, borderRadius: '50%', background: 'var(--electric-green)', marginRight: 4 }} /> {isVi ? 'Trực Tiếp' : 'Live'}</span>
          </div>
          <div className="activity-timeline">
            {activityFeed.length === 0 ? (
              <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>{t('noActivity')}</div>
            ) : (
              activityFeed.map((item) => (
                <div key={item.id} className="activity-item">
                  <div className={`act-icon ${item.color}`}>
                    {item.icon === 'user-check' ? <UserCheck size={14} /> : item.icon === 'exclamation-triangle' ? <AlertTriangle size={14} /> : <Microchip size={14} />}
                  </div>
                  <div className="act-content">
                    <div className="act-title">{item.title}</div>
                    <div className="act-time">{item.time}</div>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
      </details>

      {/* RULE EDIT MODAL */}
      {editingRule && (
        <div className="modal-overlay active" onClick={() => setEditingRule(null)}>
          <div className="modal-card" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <span className="modal-title"><Pencil size={16} style={{ display: 'inline', marginRight: 6 }} /> {t('editRuleTitle')}</span>
              <button className="modal-close" onClick={() => setEditingRule(null)}><X size={16} /></button>
            </div>
            <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 10 }}>
              {isVi
                ? `Chỉnh sửa điều kiện làm sạch SQL / Python cho ${editingRule.rule_id} trước khi ký số nạp vào động cơ Pytest.`
                : `Modify the SQL / Python cleaning conditions for ${editingRule.rule_id} before signing into Pytest integration engine.`}
            </div>
            <textarea className="modal-textarea" value={editText} onChange={(e) => setEditText(e.target.value)} />
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10 }}>
              <button className="hud-btn" onClick={() => setEditingRule(null)}>{t('cancel')}</button>
              <button className="btn-accept" onClick={saveRuleEdit}><Save size={14} /> {t('applyModifiedRule')}</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
