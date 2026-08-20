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
  Stethoscope,
  FlaskConical,
  ScanSearch,
  Fingerprint,
} from 'lucide-react';
import { useDashboardStore } from '../stores/dashboardStore';
import { usePipelineStore } from '../stores/pipelineStore';
import { hitlApi, summaryApi } from '../services/api';
import type { HITLProposal } from '../services/api';
import type { AgentId } from '../types';

const AGENT_HEALTH: Array<{ id: AgentId; label: { en: string; vi: string }; icon: React.ComponentType<{ size?: number | string; className?: string; style?: React.CSSProperties }>; color: string; latency: string }> = [
  { id: 'profiler', label: { en: 'Data Profiling Agent', vi: 'Agent Khảo Sát Dữ Liệu' }, icon: ScanSearch, color: 'var(--royal-purple)', latency: '0.4ms' },
  { id: 'anomalyDetector', label: { en: 'Anomaly Detection Agent', vi: 'Agent Phát Hiện Bất Thường' }, icon: AlertTriangle, color: 'var(--warning-amber)', latency: '1.2ms' },
  { id: 'ruleProposer', label: { en: 'Rule Proposer Agent', vi: 'Agent Đề Xuất Bộ Luật' }, icon: Lightbulb, color: 'var(--electric-green)', latency: '0.8ms' },
  { id: 'diagnosis', label: { en: 'Diagnosis & RCA Agent', vi: 'Agent Chẩn Đoán & RCA' }, icon: Stethoscope, color: 'var(--alert-magenta)', latency: '2.1ms' },
  { id: 'orchestrator', label: { en: 'Pytest Integration Engine', vi: 'Động Cơ Tích Hợp Pytest' }, icon: FlaskConical, color: 'var(--electric-green)', latency: '1.4ms' },
];

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
  const metrics = useDashboardStore((s) => s.metrics);
  const insights = useDashboardStore((s) => s.insights);
  const activityFeed = useDashboardStore((s) => s.activityFeed);
  const signals = useDashboardStore((s) => s.signals);
  const summary = useDashboardStore((s) => s.summary);
  const loading = useDashboardStore((s) => s.loading);
  const fetchDashboardData = useDashboardStore((s) => s.fetchDashboardData);
  const setPipelineProposals = usePipelineStore((s) => s.setProposals);
  const [proposals, setProposals] = useState<HITLProposal[]>([]);
  const [editingRule, setEditingRule] = useState<HITLProposal | null>(null);
  const [editText, setEditText] = useState('');
  const [ruleStates, setRuleStates] = useState<Record<string, 'approved' | 'rejected' | 'edited'>>({});
  const [trendRange, setTrendRange] = useState<'24h' | '7d' | '30d'>('24h');
  const chartRef = useRef<HTMLCanvasElement>(null);
  const chartInstance = useRef<{ destroy: () => void } | null>(null);

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

  const isDark = () =>
    (document.documentElement.getAttribute('data-theme') || 'tech-dark') !== 'tech-light';

  // Dynamic anomaly trend chart (Chart.js)
  useEffect(() => {
    let isMounted = true;
    const canvas = chartRef.current;
    if (!canvas) return;
    const textColor = isDark() ? '#94a3b8' : '#475569';
    const gridColor = isDark() ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.06)';

    summaryApi
      .getTrend(trendRange)
      .then((res) => {
        if (!isMounted || !canvas) return;
        const labels = res?.labels?.length ? res.labels : ['00:00', '04:00', '08:00', '12:00', '16:00', '20:00', '24:00'];
        const dataA = res?.voltage_spikes?.length ? res.voltage_spikes : [12, 19, 85, 45, 120, 32, 15];
        const dataB = res?.thermal_flags?.length ? res.thermal_flags : [5, 12, 40, 25, 88, 20, 8];

        import('chart.js/auto').then(({ default: Chart }) => {
          if (!isMounted) return;
          if (chartInstance.current) chartInstance.current.destroy();
          chartInstance.current = new Chart(canvas, {
            type: 'line',
            data: {
              labels,
              datasets: [
                { label: 'BMS Voltage Spikes', data: dataA, borderColor: '#f87171', backgroundColor: 'rgba(248,113,113,0.08)', fill: true, tension: 0.3, borderWidth: 2, pointRadius: 3 },
                { label: 'Thermal Overheat Flags', data: dataB, borderColor: isDark() ? '#f8fafc' : '#0f172a', backgroundColor: isDark() ? 'rgba(248,250,252,0.08)' : 'rgba(15,23,42,0.06)', fill: true, tension: 0.3, borderWidth: 2, pointRadius: 3 },
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
        // Fallback default chart
        import('chart.js/auto').then(({ default: Chart }) => {
          if (!isMounted || !canvas) return;
          if (chartInstance.current) chartInstance.current.destroy();
          chartInstance.current = new Chart(canvas, {
            type: 'line',
            data: {
              labels: ['00:00', '04:00', '08:00', '12:00', '16:00', '20:00', '24:00'],
              datasets: [
                { label: 'BMS Voltage Spikes', data: [12, 19, 85, 45, 120, 32, 15], borderColor: '#f87171', backgroundColor: 'rgba(248,113,113,0.08)', fill: true, tension: 0.3, borderWidth: 2, pointRadius: 3 },
                { label: 'Thermal Overheat Flags', data: [5, 12, 40, 25, 88, 20, 8], borderColor: isDark() ? '#f8fafc' : '#0f172a', backgroundColor: isDark() ? 'rgba(248,250,252,0.08)' : 'rgba(15,23,42,0.06)', fill: true, tension: 0.3, borderWidth: 2, pointRadius: 3 },
              ],
            },
            options: {
              responsive: true,
              maintainAspectRatio: false,
              plugins: { legend: { display: true, position: 'top', labels: { color: textColor, boxWidth: 12, padding: 16 } } },
            },
          });
        });
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
      {/* TOP SUMMARY KPI CARDS (4 CARDS) */}
      <div className="kpi-grid">
        <div className="kpi-card">
          <div className="kpi-header">
            <span className="kpi-title">{t('enterpriseDatasets')}</span>
            <div className="kpi-icon blue"><Boxes size={15} /></div>
          </div>
          <div className="kpi-value">{loading ? '...' : summary?.projects_count ?? '4'}<span className="unit"> {t('active')}</span></div>
          <div className="kpi-subtext positive"><CheckCircle2 size={13} /> {summary?.provenance ?? 'SEMI_SYNTHETIC'} {isVi ? 'nguồn gốc' : 'provenance'}</div>
        </div>

        <div className="kpi-card">
          <div className="kpi-header">
            <span className="kpi-title">{t('totalRecords')}</span>
            <div className="kpi-icon green"><Layers size={15} /></div>
          </div>
          <div className="kpi-value">{loading ? '...' : metrics.cleanRecords.toLocaleString()}<span className="unit"> {t('rows')}</span></div>
          <div className="kpi-subtext positive"><CheckCircle2 size={13} /> {metrics.passValidationRate} {t('dataQuality')}</div>
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
      <div className="panels-grid">
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
                    <button className="btn-rule approve" onClick={() => handleRuleAction(rule, 'approve')}><Check size={13} /> {t('approveRule')}</button>
                    <button className="btn-rule edit" onClick={() => handleRuleAction(rule, 'edit')}><Pencil size={13} /> {t('editRule')}</button>
                    <button className="btn-rule reject" onClick={() => handleRuleAction(rule, 'reject')}><X size={13} /> {t('rejectRule')}</button>
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
            <canvas ref={chartRef} id="anomalyTrendChart" />
          </div>
          <div style={{ display: 'flex', gap: 16, fontSize: 12, color: 'var(--text-muted)', flexWrap: 'wrap' }}>
            <span>{isVi ? 'L1 Schema:' : 'L1 Schema:'} <strong style={{ color: 'var(--text-main)' }}>{layerCounts.L1 || 0}</strong></span>
            <span>{isVi ? 'L2 Độ Lệch:' : 'L2 Drift:'} <strong style={{ color: 'var(--text-main)' }}>{layerCounts.L2 || 0}</strong></span>
            <span>{isVi ? 'L3 Liên Thực Thể:' : 'L3 Multi-Entity:'} <strong style={{ color: 'var(--text-main)' }}>{layerCounts.L3 || 0}</strong></span>
            <span>{isVi ? 'L4 Nguyên Nhân Gốc:' : 'L4 Causal:'} <strong style={{ color: 'var(--text-main)' }}>{layerCounts.L4 || 0}</strong></span>
            <span>{isVi ? 'Tổng Tín Hiệu:' : 'Total Signals:'} <strong style={{ color: 'var(--alert-magenta)' }}>{totalSignals}</strong></span>
          </div>
        </div>

        {/* PANEL 3: AGENT HEALTH & LATENCY */}
        <div className="panel-card panel-agent-health">
          <div className="panel-header">
            <div className="panel-title-group">
              <Bot size={18} className="text-primary" />
              <h2>{t('agentHealth')}</h2>
            </div>
            <span className="status-pill online"><Check size={12} /> {t('activeAgents')}</span>
          </div>
          <div className="agents-status-list">
            {AGENT_HEALTH.map((agent) => (
              <div key={agent.id} className="agent-row">
                <div className="agent-name">
                  <agent.icon size={14} style={{ color: agent.color }} />
                  {agent.label[isVi ? 'vi' : 'en']}
                </div>
                <span className="agent-badge">{isVi ? 'Hoạt Động' : 'Active'}</span>
                <span className="stat-val">{agent.latency}</span>
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
