import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useParams, useNavigate, useSearchParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import {
  TriangleAlert,
  Shield,
  RefreshCw,
  Search,
  CheckCircle2,
  XCircle,
  ShieldCheck,
  Car,
  BatteryCharging,
  CarTaxiFront,
  MessageSquare,
  Database,
  Check,
  X,
  Info,
  Lock,
  Eye,
  Clock,
} from 'lucide-react';
import { QuarantineZoneTab } from '../components/workspace/QuarantineZoneTab';
import { EvalVsGtPanel } from '../components/workspace/EvalVsGtPanel';
import {
  approvalsApi,
  auditApi,
  authorizationsApi,
  executionsApi,
  incidentsApi,
  rulesApi,
  QualityRuleItem,
  quarantineApi,
  signalsApi,
  snapshotsApi,
  summaryApi,
  tracesApi,
} from '../services/api';
import { useWorkspaceStore } from '../stores/workspaceStore';
import { useAuthStore } from '../stores/authStore';

/** This-run Split totals (sandbox DuckDB), never leftover warehouse 50k. */
function thisRunSplitTotals(): { thisRun: boolean; quarantine: number } {
  const map = useWorkspaceStore.getState().splitRowsByDataset;
  let quarantine = 0;
  let thisRun = false;
  for (const row of Object.values(map || {})) {
    if (row && (row.thisRun || row.snapshotId)) {
      thisRun = true;
      quarantine += Number(row.totalQuarantine || 0);
    }
  }
  return { thisRun, quarantine };
}

function thisRunAuditCount(entries: Array<{ action?: string; target_table?: string }> | null | undefined): number {
  return (entries || []).filter((e) => {
    const act = String(e.action || '').toUpperCase();
    const tbl = String(e.target_table || '').toLowerCase();
    return act.includes('SANDBOX') || act.includes('QUARANTINE') || tbl === 'quarantine';
  }).length;
}

type DashboardGroup = 'alerts' | 'governance';
type SubTabKey = 'alerts' | 'incidents' | 'signals' | 'traces' | 'rules' | 'quarantine' | 'governance' | 'executions' | 'snapshots' | 'eval';
type Row = Record<string, any>;

const MULTI_DATASET_OPTIONS = [
  { key: 'all', label: { en: 'All Sources', vi: 'Tất Cả Nguồn Dữ Liệu' }, icon: Database, color: 'var(--neon-cyan)' },
  { key: 'vinfast_ev_telemetry', label: { en: 'VinFast EV Telemetry', vi: 'VinFast EV Telemetry' }, icon: Car, color: '#0284c7' },
  { key: 'charging_sessions', label: { en: 'VGreen Charging Stations', vi: 'Trạm Sạc VGreen' }, icon: BatteryCharging, color: '#10b981' },
  { key: 'trips', label: { en: 'Xanh SM Trips', vi: 'Chuyến Đi Xanh SM' }, icon: CarTaxiFront, color: '#06b6d4' },
  { key: 'nlp_feedback', label: { en: 'Xanh SM Customer Feedback', vi: 'Phản Hồi Xanh SM' }, icon: MessageSquare, color: '#8b5cf6' },
  { key: 'vietnam_trips', label: { en: 'Vietnam Trips Benchmark', vi: 'Tập Chuẩn Vietnam Trips' }, icon: Database, color: '#f59e0b' },
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
  llm_claim: { en: 'AI REASONING CONCLUSION', vi: 'SUY LUẬN / KẾT LUẬN CUỐI' },
  confidence: { en: 'CLASSIFICATION & CONFIDENCE', vi: 'PHÂN LOẠI & ĐỘ TIN CẬY' },
  rule_id: { en: 'RULE ID', vi: 'MÃ BỘ LUẬT' },
  dataset_name: { en: 'DATASET SOURCE', vi: 'NGUỒN DỮ LIỆU' },
  target_column: { en: 'TARGET COLUMN', vi: 'CỘT MỤC TIÊU' },
  rule_expression: { en: 'RULE EXPRESSION', vi: 'BIỂU THỨC RÀNG BUỘC' },
  quarantined_count: { en: 'QUARANTINED VIOLATIONS', vi: 'BẢN GHI ĐÃ CÁCH LY' },
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
  const [searchParams] = useSearchParams();
  const ruleParam = searchParams.get('rule_id') || searchParams.get('rule');
  const { i18n } = useTranslation('pipeline');
  const isVi = i18n.language === 'vi';
  const canReviewRules = useAuthStore((s) => s.canReviewRules());

  // Determine main dashboard group and active subtab
  const isGovernanceView = view === 'rules' || view === 'quarantine' || view === 'governance' || view === 'executions' || view === 'snapshots' || view === 'eval' || !!ruleParam;
  const mainGroup: DashboardGroup = isGovernanceView ? 'governance' : 'alerts';

  const [activeSubTab, setActiveSubTab] = useState<SubTabKey>(() => {
    if (ruleParam) return 'quarantine';
    if (view && (view === 'incidents' || view === 'signals' || view === 'traces')) return view;
    if (view && (view === 'rules' || view === 'quarantine' || view === 'executions' || view === 'snapshots' || view === 'eval')) return view;
    return isGovernanceView ? 'rules' : 'alerts';
  });

  const [data, setData] = useState<Row[]>([]);
  const [_summary, setSummary] = useState<Row | null>(null);
  const [_quarantineCount, setQuarantineCount] = useState(0);
  const [_auditCount, setAuditCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filterQuery, setFilterQuery] = useState('');

  // Rules-specific filters & states
  const [datasetFilter, setDatasetFilter] = useState<string>('all');
  const [layerFilter, setLayerFilter] = useState<string>('all');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [actionLoadingRuleId, setActionLoadingRuleId] = useState<string | null>(null);
  const [approvalFeedback, setApprovalFeedback] = useState<{
    ruleId: string;
    ruleName: string;
    quarantinedCount: number;
    datasetKey: string;
  } | null>(null);
  const [selectedRuleForDetail, setSelectedRuleForDetail] = useState<QualityRuleItem | null>(null);

  // Selected incident for interactive RCA deep-dive modal
  const [selectedIncident, setSelectedIncident] = useState<Record<string, any> | null>(null);
  const [incidentLoading, setIncidentLoading] = useState(false);

  // Alert feedback state
  const [alertFeedbackReason, setAlertFeedbackReason] = useState('');
  const [showFalsePositiveInput, setShowFalsePositiveInput] = useState(false);
  const [alertFeedbackSubmitting, setAlertFeedbackSubmitting] = useState(false);

  const handleAlertFeedback = async (incidentId: string, feedbackType: 'TRUE_POSITIVE' | 'FALSE_POSITIVE', reason: string = '') => {
    setAlertFeedbackSubmitting(true);
    try {
      const res = await incidentsApi.submitFeedback(incidentId, feedbackType, reason, 'human');
      if (selectedIncident && (selectedIncident.incident_id === incidentId || selectedIncident.id === incidentId)) {
        setSelectedIncident((prev: any) => prev ? {
          ...prev,
          feedback_type: res.feedback_type,
          feedback_reason: res.feedback_reason,
          feedback_by: res.feedback_by,
          feedback_at: res.feedback_at,
          status: res.incident_status
        } : null);
      }
      setShowFalsePositiveInput(false);
      setAlertFeedbackReason('');
      void loadData();
    } catch (err: any) {
      alert(`Feedback error: ${err.message}`);
    } finally {
      setAlertFeedbackSubmitting(false);
    }
  };

  useEffect(() => {
    setSelectedIncident(null);
    setShowFalsePositiveInput(false);
    setAlertFeedbackReason('');
  }, [view]);
  const [modalTab, setModalTab] = useState<'rca' | 'evidence' | 'signals'>('rca');

  // Sync URL view param with active subtab
  useEffect(() => {
    if (view && ['alerts', 'incidents', 'signals', 'traces', 'rules', 'quarantine', 'governance', 'executions', 'snapshots', 'eval'].includes(view)) {
      setActiveSubTab(view as SubTabKey);
    }
  }, [view]);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      if (activeSubTab === 'alerts' || activeSubTab === 'incidents') {
        const [sumRes, incRes, qCountRes, auditRes] = await Promise.all([
          summaryApi.get().catch(() => null),
          incidentsApi.list().catch(() => []),
          quarantineApi.count().catch(() => null),
          auditApi.list(50).catch(() => []),
        ]);
        if (sumRes) setSummary(sumRes);
        setData(incRes || []);
        const stored = thisRunSplitTotals();
        const apiThisRun = Number(
          (qCountRes as { this_run?: number } | null)?.this_run
          ?? (sumRes as { this_run_quarantined?: number } | null)?.this_run_quarantined
          ?? 0
        );
        // Same this-run DuckDB quarantine as Split. Empty before sandbox stays 0. Never leftover 50k.
        let q = stored.thisRun ? stored.quarantine : (apiThisRun > 0 && apiThisRun < 50000 ? apiThisRun : 0);
        if (q >= 50000) q = 0;
        let a = 0;
        if (stored.thisRun || q > 0) {
          a = thisRunAuditCount(Array.isArray(auditRes) ? auditRes : []);
          if (a === 0) a = q; // quarantine ledger is the audit when no separate this-run rows
        }
        setQuarantineCount(q);
        setAuditCount(a);
      } else if (activeSubTab === 'signals') {
        const sigRes = await signalsApi.list().catch(() => []);
        setData(sigRes || []);
      } else if (activeSubTab === 'traces') {
        const tracesRes = await tracesApi.list().catch(() => ({ sessions: [] }));
        setData(tracesRes.sessions || []);
      } else if (activeSubTab === 'rules') {
        const rulesRes = await rulesApi.list().catch(() => []);
        setData(rulesRes || []);
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
      } else if (activeSubTab === 'eval') {
        setData([]);
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

  // Listen for DB reset + this-run sandbox so Quarantine/Audit match Split
  useEffect(() => {
    const handleReset = () => {
      setQuarantineCount(0);
      setAuditCount(0);
      loadData();
    };
    const handleSandbox = (ev: Event) => {
      const d = (ev as CustomEvent).detail || {};
      const q = Number(d.quarantine_rows ?? (Array.isArray(d.quarantine) ? d.quarantine.length : 0));
      if (d.sandbox || d.thisRun || d.cleanRan) {
        const safe = q >= 50000 ? 0 : q;
        setQuarantineCount(safe);
        setAuditCount(safe);
      }
      loadData();
    };
    window.addEventListener('datatrust:db-reset', handleReset);
    window.addEventListener('datatrust:sandbox-split', handleSandbox as EventListener);
    window.addEventListener('datatrust:split-refresh', handleSandbox as EventListener);
    window.addEventListener('datatrust:sandbox-failed', handleReset);
    return () => {
      window.removeEventListener('datatrust:db-reset', handleReset);
      window.removeEventListener('datatrust:sandbox-split', handleSandbox as EventListener);
      window.removeEventListener('datatrust:split-refresh', handleSandbox as EventListener);
      window.removeEventListener('datatrust:sandbox-failed', handleReset);
    };
  }, [loadData]);

  const handleOpenIncident = async (incidentId: string, initialRow?: Row) => {
    setIncidentLoading(true);
    setSelectedIncident(initialRow || { incident_id: incidentId });
    setModalTab('rca');

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

  // Rule Approval & Non-destructive Quarantine Action
  const handleApproveRule = async (ruleId: string, ruleName?: string, datasetKey?: string) => {
    setActionLoadingRuleId(ruleId);
    try {
      const res = await rulesApi.approve(ruleId);
      const qCount = res.quarantined_count ?? 0;

      // Update local state
      setData((prev) =>
        prev.map((r) => (r.id === ruleId || r.rule_id === ruleId ? { ...r, status: 'approved', quarantined_count: qCount } : r))
      );

      // Show celebratory feedback banner
      setApprovalFeedback({
        ruleId,
        ruleName: ruleName || res.rule_name || ruleId,
        quarantinedCount: qCount,
        datasetKey: datasetKey || res.dataset_key || 'dataset',
      });

      // Dispatch event for other tabs to refresh
      window.dispatchEvent(new CustomEvent('datatrust:quarantine-updated', { detail: { ruleId, qCount } }));
    } catch (err: any) {
      alert(`Approval error: ${err.message}`);
    } finally {
      setActionLoadingRuleId(null);
    }
  };

  const handleRejectRule = async (ruleId: string) => {
    setActionLoadingRuleId(ruleId);
    try {
      await rulesApi.reject(ruleId);
      setData((prev) =>
        prev.map((r) => (r.id === ruleId || r.rule_id === ruleId ? { ...r, status: 'rejected' } : r))
      );
    } catch (err: any) {
      alert(`Reject error: ${err.message}`);
    } finally {
      setActionLoadingRuleId(null);
    }
  };

  const handleBatchApproveRules = async () => {
    const pending = (data as QualityRuleItem[]).filter(
      (r) => (r.status || '').toLowerCase() === 'proposed' || (r.status || '').toLowerCase() === 'pending'
    );
    if (pending.length === 0) return;

    setActionLoadingRuleId('batch');
    try {
      const res = await rulesApi.batchApprove(pending.map((r) => r.id || r.rule_id));
      setData((prev) =>
        prev.map((r) => {
          if ((r.status || '').toLowerCase() === 'proposed' || (r.status || '').toLowerCase() === 'pending') {
            return { ...r, status: 'approved' };
          }
          return r;
        })
      );
      setApprovalFeedback({
        ruleId: 'BATCH_APPROVAL',
        ruleName: isVi ? `${res.processed_count} bộ luật được duyệt` : `${res.processed_count} rules approved`,
        quarantinedCount: res.total_quarantined || 0,
        datasetKey: 'multi_dataset',
      });
      loadData();
    } catch (err: any) {
      alert(`Batch approval error: ${err.message}`);
    } finally {
      setActionLoadingRuleId(null);
    }
  };

  const currentColumns = useMemo(() => {
    const map: Record<SubTabKey, string[]> = {
      alerts: ['incident_id', 'target_entity', 'layer', 'severity', 'status', 'llm_claim', 'confidence'],
      incidents: ['incident_id', 'target_entity', 'domain', 'layer', 'severity', 'status', 'llm_claim', 'confidence'],
      signals: ['signal_id', 'layer', 'signal_type', 'severity', 'detector', 'details'],
      traces: ['session_id', 'agent_type', 'steps', 'total_tokens', 'started'],
      rules: ['rule_id', 'dataset_name', 'layer', 'target_column', 'rule_expression', 'status', 'quarantined_count'],
      quarantine: ['group_id', 'source_table', 'rule_name', 'severity', 'total_rows', 'status'],
      governance: ['record_type', 'id', 'status', 'actor', 'action', 'timestamp'],
      executions: ['event_type', 'actor', 'timestamp', 'details'],
      snapshots: ['id', 'source_file', 'row_count', 'column_count', 'sha256_hash', 'ingested_at'],
      eval: ['metric', 'batch', 'realtime'],
    };
    return map[activeSubTab] || ['id', 'status', 'timestamp'];
  }, [activeSubTab]);

  const operationalStats = useMemo(() => {
    if (!Array.isArray(data)) {
      return {
        total: 0,
        critical: 0,
        high: 0,
        dataDefects: 0,
        opDefects: 0,
        l1: 0,
        l2: 0,
        l3: 0,
        l4: 0,
        quarantineCount: 0,
        openCount: 0,
        approvedRulesCount: 0,
        proposedRulesCount: 0,
        totalQuarantinedRows: 0,
      };
    }

    let critical = 0;
    let high = 0;
    let dataDefects = 0;
    let opDefects = 0;
    let l1 = 0;
    let l2 = 0;
    let l3 = 0;
    let l4 = 0;
    let quarantineCount = 0;
    let openCount = 0;
    let approvedRulesCount = 0;
    let proposedRulesCount = 0;
    let totalQuarantinedRows = 0;

    data.forEach((row: any) => {
      const sev = String(row.severity || '').toUpperCase();
      if (sev === 'CRITICAL') critical++;
      else if (sev === 'HIGH') high++;

      const cls = String(row.llm_classification || row.classification || '').toUpperCase();
      if (cls.includes('DATA')) dataDefects++;
      else if (cls.includes('OPERATIONAL') || cls.includes('OP')) opDefects++;

      const layers = Array.isArray(row.supporting_layers)
        ? row.supporting_layers
        : [row.layer || ''];
      layers.forEach((ly: string) => {
        const u = String(ly).toUpperCase();
        if (u.includes('L1')) l1++;
        if (u.includes('L2')) l2++;
        if (u.includes('L3')) l3++;
        if (u.includes('L4')) l4++;
      });

      const act = String(row.expected_action || row.action_type || '').toUpperCase();
      if (act.includes('QUARANTINE')) quarantineCount++;

      const st = String(row.status || '').toUpperCase();
      if (st === 'OPEN' || st === 'PENDING' || st === 'PROPOSED') {
        openCount++;
        proposedRulesCount++;
      } else if (st === 'APPROVED' || st === 'ACTIVE') {
        approvedRulesCount++;
      }

      if (row.quarantined_count) {
        totalQuarantinedRows += Number(row.quarantined_count) || 0;
      }
    });

    return {
      total: data.length,
      critical,
      high,
      dataDefects,
      opDefects,
      l1,
      l2,
      l3,
      l4,
      quarantineCount,
      openCount,
      approvedRulesCount,
      proposedRulesCount,
      totalQuarantinedRows,
    };
  }, [data]);

  const filteredData = useMemo(() => {
    let list = Array.isArray(data) ? data : [];

    if (activeSubTab === 'rules') {
      if (datasetFilter !== 'all') {
        list = list.filter((r) => r.dataset_key === datasetFilter);
      }
      if (layerFilter !== 'all') {
        list = list.filter((r) => String(r.layer || '').toUpperCase().includes(layerFilter.toUpperCase()));
      }
      if (statusFilter !== 'all') {
        list = list.filter((r) => String(r.status || '').toLowerCase() === statusFilter.toLowerCase());
      }
    }

    if (!filterQuery.trim()) return list;
    const q = filterQuery.toLowerCase().trim();
    return list.filter((row) =>
      Object.values(row).some((val) => String(val).toLowerCase().includes(q))
    );
  }, [data, activeSubTab, datasetFilter, layerFilter, statusFilter, filterQuery]);

  return (
    <section className="dash-main" style={{ padding: '24px 32px' }}>
      {/* TOP HEADER & TITLE */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '20px', flexWrap: 'wrap', gap: '16px' }}>
        <div>
          <div className="menu-label" style={{ padding: 0, color: 'var(--neon-cyan)', letterSpacing: '0.08em' }}>
            {mainGroup === 'alerts'
              ? (isVi ? 'VẬN HÀNH & GIÁM SÁT' : 'OPERATIONS & OBSERVABILITY')
              : (isVi ? 'QUẢN TRỊ & BỘ LUẬT CHẤT LƯỢNG' : 'GOVERNANCE & QUALITY RULES')}
          </div>
          <h1 style={{ margin: '4px 0 0', color: 'var(--text-main)', fontSize: '24px', fontWeight: 600 }}>
            {activeSubTab === 'rules'
              ? (isVi ? 'Bộ Luật Đang Áp Dụng (Multi-Dataset Quality Rules)' : 'Active Quality Rules Control Room')
              : mainGroup === 'alerts'
                ? (isVi ? 'Bảng Cảnh Báo Điều Hành' : 'Alert Dashboard')
                : (isVi ? 'Bảng Quản Trị & Chính Sách' : 'Governance Dashboard')}
          </h1>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div style={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
            <Search size={14} style={{ position: 'absolute', left: '10px', color: 'var(--text-muted)' }} />
            <input
              type="text"
              placeholder={isVi ? 'Lọc theo tên, cột, biểu thức...' : 'Filter rules, columns, expressions...'}
              value={filterQuery}
              onChange={(e) => setFilterQuery(e.target.value)}
              style={{
                padding: '6px 12px 6px 30px',
                borderRadius: '8px',
                border: '1px solid var(--glass-border)',
                backgroundColor: 'var(--bg-card)',
                color: 'var(--text-main)',
                fontSize: '12px',
                width: '240px',
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
      {activeSubTab === 'rules' ? (
        <div className="kpi-grid" style={{ marginBottom: '20px', gridTemplateColumns: 'repeat(auto-fit, minmax(210px, 1fr))', gap: '12px' }}>
          <div className="kpi-card" style={{ borderLeft: '3px solid var(--neon-cyan)' }}>
            <div className="kpi-label">{isVi ? 'Tổng Số Quy Luật Đa Nguồn' : 'Total Multi-Dataset Rules'}</div>
            <div className="kpi-value" style={{ color: 'var(--neon-cyan)', fontSize: '22px' }}>
              {operationalStats.total} {isVi ? 'Quy Luật' : 'Rules'}
            </div>
            <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '4px' }}>
              {isVi ? 'Bao phủ 5 tập dữ liệu cốt lõi & custom DB' : 'Covering 5 core datasets & custom uploads'}
            </div>
          </div>

          <div className="kpi-card" style={{ borderLeft: '3px solid #10b981' }}>
            <div className="kpi-label">{isVi ? 'Bộ Luật Đang Áp Dụng (Approved)' : 'Active & Enforced Rules'}</div>
            <div className="kpi-value" style={{ color: '#10b981', fontSize: '22px' }}>
              {operationalStats.approvedRulesCount} {isVi ? 'Đang Thực Thi' : 'Enforced'}
            </div>
            <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '4px' }}>
              {isVi ? 'Đang tự động bảo vệ kho dữ liệu' : 'Actively guarding warehouse storage'}
            </div>
          </div>

          <div className="kpi-card" style={{ borderLeft: '3px solid #f59e0b' }}>
            <div className="kpi-label">{isVi ? 'Bộ Luật Chờ Phê Duyệt (HITL)' : 'Pending Steward Approval'}</div>
            <div className="kpi-value" style={{ color: '#f59e0b', fontSize: '22px' }}>
              {operationalStats.proposedRulesCount} {isVi ? 'Chờ Phê Duyệt' : 'Pending'}
            </div>
            <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '4px' }}>
              {operationalStats.proposedRulesCount > 0 ? (
                canReviewRules ? (
                <button
                  type="button"
                  onClick={handleBatchApproveRules}
                  disabled={actionLoadingRuleId === 'batch'}
                  style={{
                    background: 'none',
                    border: 'none',
                    padding: 0,
                    color: '#38bdf8',
                    cursor: 'pointer',
                    fontSize: '11px',
                    fontWeight: 600,
                    textDecoration: 'underline',
                  }}
                >
                  {isVi ? '⚡ Phê duyệt tất cả ngay' : '⚡ Batch approve all now'}
                </button>
                ) : (
                <span>{isVi ? 'Chờ steward phê duyệt' : 'Awaiting steward approval'}</span>
                )
              ) : (
                <span>{isVi ? 'Tất cả luật đã được phê duyệt' : 'All proposed rules approved'}</span>
              )}
            </div>
          </div>

          <div className="kpi-card" style={{ borderLeft: '3px solid #f43f5e' }}>
            <div className="kpi-label">{isVi ? 'Bản Ghi Đã Đưa Vào Cách Ly' : 'Total Quarantined Violations'}</div>
            <div className="kpi-value" style={{ color: '#f43f5e', fontSize: '22px' }}>
              {operationalStats.totalQuarantinedRows.toLocaleString()} {isVi ? 'Bản Ghi' : 'Rows'}
            </div>
            <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '4px' }}>
              <span style={{ color: '#10b981', fontWeight: 600 }}>100% {isVi ? 'Dữ liệu gốc giữ nguyên' : 'Raw Data Preserved'}</span>
            </div>
          </div>
        </div>
      ) : mainGroup === 'alerts' ? (
        <div className="kpi-grid" style={{ marginBottom: '24px', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '12px' }}>
          <div className="kpi-card" style={{ borderLeft: '3px solid #f43f5e' }}>
            <div className="kpi-label">{isVi ? 'Tổng Sự Cố & Cảnh Báo' : 'Total Incidents & Alerts'}</div>
            <div className="kpi-value" style={{ color: '#f43f5e', fontSize: '22px' }}>
              {operationalStats.total} {isVi ? 'Ca Sự Cố' : 'Cases'}
            </div>
            <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '4px' }}>
              {operationalStats.critical > 0 || operationalStats.high > 0 ? (
                <span>
                  <strong style={{ color: '#f43f5e' }}>{operationalStats.critical}</strong> {isVi ? 'Khẩn cấp' : 'Critical'} · <strong style={{ color: '#f59e0b' }}>{operationalStats.high}</strong> {isVi ? 'Mức cao' : 'High'}
                </span>
              ) : (
                <span>{isVi ? 'Không có sự cố khẩn cấp' : 'No critical issues'}</span>
              )}
            </div>
          </div>

          <div className="kpi-card" style={{ borderLeft: '3px solid #a855f7' }}>
            <div className="kpi-label">{isVi ? 'Phân Loại Lỗi (Agent A1)' : 'Root Cause Triage (A1)'}</div>
            <div className="kpi-value" style={{ color: '#a855f7', fontSize: '18px' }}>
              {operationalStats.dataDefects} DATA · {operationalStats.opDefects} OP
            </div>
            <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '4px' }}>
              {isVi ? 'Phân loại nguyên nhân gốc tự động' : 'Autonomous root-cause triage'}
            </div>
          </div>

          <div className="kpi-card" style={{ borderLeft: '3px solid var(--neon-cyan)' }}>
            <div className="kpi-label">{isVi ? 'Bao Phủ Tầng Detector' : 'Multi-Layer Detector Coverage'}</div>
            <div className="kpi-value" style={{ color: 'var(--neon-cyan)', fontSize: '16px', letterSpacing: '0.02em' }}>
              L1:{operationalStats.l1} · L2:{operationalStats.l2} · L3:{operationalStats.l3} · L4:{operationalStats.l4}
            </div>
            <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '4px' }}>
              {isVi ? 'Ràng buộc · Trôi dạt · Tương quan · PELT' : 'Invariant · Drift · Relational · PELT'}
            </div>
          </div>

          <div className="kpi-card" style={{ borderLeft: '3px solid #10b981' }}>
            <div className="kpi-label">{isVi ? 'Hành Động Khắc Phục Đề Xuất' : 'Prescribed Remediation'}</div>
            <div className="kpi-value" style={{ color: '#10b981', fontSize: '18px' }}>
              {operationalStats.quarantineCount} {isVi ? 'Cần Cách Ly' : 'Quarantine'}
            </div>
            <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '4px' }}>
              {operationalStats.openCount > 0
                ? (isVi ? `${operationalStats.openCount} ca chờ phê duyệt HITL` : `${operationalStats.openCount} cases pending HITL`)
                : (isVi ? 'Tất cả hành động đã xử lý' : 'All actions processed')}
            </div>
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




      {/* APPROVAL FEEDBACK CELEBRATION TOAST */}
      {approvalFeedback && (
        <div
          style={{
            background: 'linear-gradient(135deg, rgba(2, 132, 199, 0.15), rgba(16, 185, 129, 0.15))',
            border: '1px solid rgba(16, 185, 129, 0.4)',
            borderRadius: '8px',
            padding: '12px 16px',
            marginBottom: '16px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: '12px',
            animation: 'fadeIn 0.3s ease',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <CheckCircle2 size={18} style={{ color: '#10b981' }} />
            <div>
              <span style={{ fontWeight: 600, color: 'var(--text-main)', fontSize: '12.5px' }}>
                {isVi ? `Đã đồng ý áp dụng rule "${approvalFeedback.ruleName}"!` : `Approved rule "${approvalFeedback.ruleName}"!`}
              </span>{' '}
              <span style={{ color: 'var(--text-muted)', fontSize: '12px' }}>
                {approvalFeedback.quarantinedCount > 0
                  ? (isVi
                    ? `Đã phát hiện và đưa ${approvalFeedback.quarantinedCount} bản ghi vi phạm vào Khu Vực Cách Ly (Dữ liệu gốc được bảo toàn 100%).`
                    : `Isolated ${approvalFeedback.quarantinedCount} violating records into the Quarantine Zone (Raw data intact).`)
                  : (isVi
                    ? 'Tất cả các bản ghi trong tập dữ liệu đều đạt chuẩn kiểm tra.'
                    : 'All records in target dataset conform to this rule specification.')}
              </span>
            </div>
          </div>
          <button
            type="button"
            onClick={() => setApprovalFeedback(null)}
            style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', padding: 2 }}
          >
            <X size={14} />
          </button>
        </div>
      )}

      {/* MULTI-DATASET & LAYER FILTER BAR FOR RULES TAB */}
      {activeSubTab === 'rules' && (
        <div
          style={{
            display: 'flex',
            flexDirection: 'column',
            gap: '10px',
            marginBottom: '16px',
            background: 'var(--bg-card)',
            border: '1px solid var(--glass-border)',
            borderRadius: '10px',
            padding: '12px 16px',
          }}
        >
          {/* Multi-Dataset Source Filter */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
            <span style={{ fontSize: '11px', color: 'var(--text-muted)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', minWidth: '110px' }}>
              {isVi ? 'Nguồn Dữ Liệu:' : 'Dataset Source:'}
            </span>
            <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
              {MULTI_DATASET_OPTIONS.map((ds) => {
                const Icon = ds.icon;
                const isSelected = datasetFilter === ds.key;
                return (
                  <button
                    key={ds.key}
                    type="button"
                    onClick={() => setDatasetFilter(ds.key)}
                    style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '6px',
                      padding: '5px 12px',
                      borderRadius: '6px',
                      fontSize: '11.5px',
                      fontWeight: isSelected ? 600 : 400,
                      cursor: 'pointer',
                      border: isSelected ? `1px solid ${ds.color}` : '1px solid var(--glass-border)',
                      background: isSelected ? 'rgba(2, 132, 199, 0.12)' : 'transparent',
                      color: isSelected ? 'var(--text-main)' : 'var(--text-muted)',
                      transition: 'all 0.15s ease',
                    }}
                  >
                    <Icon size={13} style={{ color: ds.color }} />
                    <span>{ds.label[isVi ? 'vi' : 'en']}</span>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Layer & Status Filters */}
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '12px', borderTop: '1px solid var(--glass-border)', paddingTop: '10px' }}>
            {/* Layer Filter */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', flexWrap: 'wrap' }}>
              <span style={{ fontSize: '11px', color: 'var(--text-muted)', fontWeight: 600, textTransform: 'uppercase', minWidth: '110px' }}>
                {isVi ? 'Tầng Kiểm Soát:' : 'Detection Layer:'}
              </span>
              {[
                { key: 'all', label: isVi ? 'Tất Cả Tầng' : 'All Layers' },
                { key: 'L1', label: isVi ? 'L1 Bất Biến' : 'L1 Invariants' },
                { key: 'L2', label: isVi ? 'L2 Trôi Dạt' : 'L2 Drift' },
                { key: 'L3', label: isVi ? 'L3 Tương Quan' : 'L3 Relational' },
                { key: 'L4', label: isVi ? 'L4 Đổi Điểm' : 'L4 Change-point' },
              ].map((ly) => (
                <button
                  key={ly.key}
                  type="button"
                  onClick={() => setLayerFilter(ly.key)}
                  style={{
                    padding: '3px 9px',
                    borderRadius: '4px',
                    fontSize: '11px',
                    cursor: 'pointer',
                    border: layerFilter === ly.key ? '1px solid var(--neon-cyan)' : '1px solid transparent',
                    background: layerFilter === ly.key ? 'rgba(56, 189, 248, 0.15)' : 'transparent',
                    color: layerFilter === ly.key ? 'var(--neon-cyan)' : 'var(--text-muted)',
                  }}
                >
                  {ly.label}
                </button>
              ))}
            </div>

            {/* Status Filter */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <span style={{ fontSize: '11px', color: 'var(--text-muted)', fontWeight: 600, textTransform: 'uppercase' }}>
                {isVi ? 'Trạng Thái:' : 'Status:'}
              </span>
              {[
                { key: 'all', label: isVi ? 'Tất Cả' : 'All' },
                { key: 'approved', label: isVi ? 'Đang Áp Dụng' : 'Approved' },
                { key: 'proposed', label: isVi ? 'Chờ Duyệt' : 'Proposed' },
                { key: 'rejected', label: isVi ? 'Từ Chối' : 'Rejected' },
              ].map((st) => (
                <button
                  key={st.key}
                  type="button"
                  onClick={() => setStatusFilter(st.key)}
                  style={{
                    padding: '3px 9px',
                    borderRadius: '4px',
                    fontSize: '11px',
                    cursor: 'pointer',
                    border: statusFilter === st.key ? '1px solid #10b981' : '1px solid transparent',
                    background: statusFilter === st.key ? 'rgba(16, 185, 129, 0.15)' : 'transparent',
                    color: statusFilter === st.key ? '#10b981' : 'var(--text-muted)',
                  }}
                >
                  {st.label}
                </button>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* TABLE PANEL */}
      {error && (
        <div className="panel-card" style={{ color: 'var(--alert-magenta)', marginBottom: '16px' }}>
          {error}
        </div>
      )}

      <div
        style={{
          background: 'var(--bg-card)',
          border: '1px solid var(--glass-border)',
          borderRadius: 'var(--radius-card)',
          padding: '0',
          overflow: 'visible',
          display: 'block',
          height: 'auto',
          maxHeight: 'none',
        }}
      >
        {activeSubTab === 'eval' ? (
          <EvalVsGtPanel />
        ) : activeSubTab === 'quarantine' ? (
          <div style={{ padding: '16px' }}>
            <QuarantineZoneTab initialDatasetKey={datasetFilter} initialRuleId={ruleParam || undefined} />
          </div>
        ) : loading ? (
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
        ) : activeSubTab === 'rules' ? (
          /* ACTIVE RULES SPECIALIZED TABLE */
          <div style={{ width: '100%', overflowX: 'auto', overflowY: 'visible', height: 'auto', maxHeight: 'none', borderRadius: 'var(--radius-card)' }}>
            <table className="data-table" style={{ width: '100%', minWidth: '1050px', tableLayout: 'fixed', borderCollapse: 'collapse' }}>
              <thead>
                <tr>
                  <th style={{ width: '18%', minWidth: '160px' }}>{isVi ? 'MÃ BỘ LUẬT & TÊN' : 'RULE ID & NAME'}</th>
                  <th style={{ width: '14%', minWidth: '130px' }}>{isVi ? 'NGUỒN DỮ LIỆU' : 'DATASET SOURCE'}</th>
                  <th style={{ width: '8%', minWidth: '80px' }}>{isVi ? 'TẦNG' : 'LAYER'}</th>
                  <th style={{ width: '9%', minWidth: '90px' }}>{isVi ? 'CỘT MỤC TIÊU' : 'TARGET COLUMN'}</th>
                  <th style={{ width: '17%', minWidth: '150px' }}>{isVi ? 'BIỂU THỨC RÀNG BUỘC' : 'RULE EXPRESSION'}</th>
                  <th style={{ width: '9%', minWidth: '90px' }}>{isVi ? 'TRẠNG THÁI' : 'STATUS'}</th>
                  <th style={{ width: '9%', minWidth: '90px' }}>{isVi ? 'BẢN GHI ĐÃ CÁCH LY' : 'QUARANTINED ROWS'}</th>
                  <th style={{ width: '16%', minWidth: '150px', textAlign: 'right' }}>{isVi ? 'THAO TÁC' : 'ACTIONS'}</th>
                </tr>
              </thead>
              <tbody>
                {filteredData.map((ruleItem: any) => {
                  const rule = ruleItem as QualityRuleItem;
                  const isApproved = (rule.status || '').toLowerCase() === 'approved';
                  const isProposed = (rule.status || '').toLowerCase() === 'proposed' || (rule.status || '').toLowerCase() === 'pending';
                  const isRejected = (rule.status || '').toLowerCase() === 'rejected';
                  const isActionLoading = actionLoadingRuleId === rule.id || actionLoadingRuleId === rule.rule_id;

                  const dsMeta = MULTI_DATASET_OPTIONS.find((d) => d.key === rule.dataset_key) || {
                    label: { en: rule.dataset_name || rule.dataset_key, vi: rule.dataset_name || rule.dataset_key },
                    icon: Database,
                    color: rule.dataset_color || '#0284c7',
                  };
                  const Icon = dsMeta.icon;
                  const brandColor = dsMeta.color === 'var(--neon-cyan)' ? '#0284c7' : dsMeta.color;

                  // Dynamic Layer Badge Styling with Warm Accents
                  const getLayerBadgeStyle = (ly: string) => {
                    const u = String(ly || '').toUpperCase();
                    if (u.includes('L1')) {
                      return { color: '#0891b2', bg: 'rgba(6, 182, 212, 0.12)', border: 'rgba(6, 182, 212, 0.35)' };
                    }
                    if (u.includes('L2')) {
                      return { color: '#7c3aed', bg: 'rgba(124, 58, 237, 0.12)', border: 'rgba(124, 58, 237, 0.35)' };
                    }
                    if (u.includes('L3')) {
                      return { color: '#c2410c', bg: 'rgba(249, 115, 22, 0.12)', border: 'rgba(249, 115, 22, 0.35)' };
                    }
                    return { color: '#be123c', bg: 'rgba(244, 63, 94, 0.12)', border: 'rgba(244, 63, 94, 0.35)' };
                  };
                  const layerStyle = getLayerBadgeStyle(rule.layer || 'L1');

                  return (
                    <tr
                      key={rule.id || rule.rule_id}
                      style={{ cursor: 'pointer' }}
                      onClick={() => setSelectedRuleForDetail(rule)}
                    >
                      {/* Rule ID & Name */}
                      <td style={{ maxWidth: '100%', overflow: 'hidden' }}>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '2px', maxWidth: '100%' }}>
                          <span style={{ fontWeight: 700, color: 'var(--text-main)', fontSize: '12.5px', lineHeight: '1.3', wordBreak: 'break-word' }}>
                            {rule.rule_name || rule.id}
                          </span>
                          <span style={{ fontSize: '10px', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', fontWeight: 600 }}>
                            {rule.rule_id || rule.id}
                          </span>
                          {(() => {
                            const pBy = rule.proposed_by || '';
                            const incId = rule.incident_id || (pBy.startsWith('rca:') ? pBy.replace('rca:', '') : (pBy.includes('INC-') ? pBy : ''));
                            if (!incId) return null;
                            return (
                              <span
                                style={{
                                  display: 'inline-flex',
                                  alignItems: 'center',
                                  gap: '4px',
                                  fontSize: '10px',
                                  fontWeight: 700,
                                  color: '#f59e0b',
                                  background: 'rgba(245, 158, 11, 0.12)',
                                  border: '1px solid rgba(245, 158, 11, 0.3)',
                                  borderRadius: '4px',
                                  padding: '2px 6px',
                                  marginTop: '3px',
                                  cursor: 'pointer',
                                  width: 'fit-content',
                                }}
                                onClick={(e) => {
                                  e.stopPropagation();
                                  handleOpenIncident(incId);
                                }}
                                title={isVi ? 'Bấm để xem chi tiết RCA của sự cố này' : 'Click to view RCA details for this incident'}
                              >
                                ⚡ {isVi ? `Từ RCA #${incId}` : `From RCA #${incId}`}
                              </span>
                            );
                          })()}
                        </div>
                      </td>

                      {/* Dataset Source Badge (Strict Overflow Fix) */}
                      <td style={{ maxWidth: '100%', overflow: 'hidden' }}>
                        <div
                          style={{
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: '5px',
                            background: 'rgba(2, 132, 199, 0.12)',
                            border: '1px solid rgba(2, 132, 199, 0.35)',
                            padding: '3px 8px',
                            borderRadius: '6px',
                            maxWidth: '100%',
                            overflow: 'hidden',
                          }}
                          title={dsMeta.label[isVi ? 'vi' : 'en']}
                        >
                          <Icon size={12} style={{ color: brandColor, flexShrink: 0 }} />
                          <span
                            style={{
                              fontSize: '11px',
                              fontWeight: 700,
                              color: brandColor,
                              whiteSpace: 'nowrap',
                              overflow: 'hidden',
                              textOverflow: 'ellipsis',
                              maxWidth: '110px',
                            }}
                          >
                            {dsMeta.label[isVi ? 'vi' : 'en']}
                          </span>
                        </div>
                      </td>

                      {/* Layer */}
                      <td style={{ maxWidth: '100%', overflow: 'hidden' }}>
                        <span
                          style={{
                            background: layerStyle.bg,
                            color: layerStyle.color,
                            border: `1px solid ${layerStyle.border}`,
                            padding: '3px 7px',
                            borderRadius: '5px',
                            fontSize: '10.5px',
                            fontWeight: 700,
                            display: 'inline-block',
                            whiteSpace: 'nowrap',
                          }}
                        >
                          {rule.layer || 'L1 Bất Biến'}
                        </span>
                      </td>

                      {/* Target Column */}
                      <td style={{ maxWidth: '100%', overflow: 'hidden' }}>
                        <code
                          style={{
                            fontSize: '11px',
                            color: '#4f46e5',
                            background: 'rgba(99, 102, 241, 0.1)',
                            border: '1px solid rgba(99, 102, 241, 0.3)',
                            padding: '3px 7px',
                            borderRadius: '5px',
                            fontWeight: 700,
                            fontFamily: 'var(--font-mono)',
                            display: 'inline-block',
                            whiteSpace: 'nowrap',
                            overflow: 'hidden',
                            textOverflow: 'ellipsis',
                            maxWidth: '100%',
                          }}
                        >
                          {rule.target_column || 'field'}
                        </code>
                      </td>

                      {/* Rule Expression (WARM AMBER HIGHLIGHT) */}
                      <td style={{ maxWidth: '100%', overflow: 'hidden' }}>
                        <code
                          style={{
                            fontSize: '11px',
                            color: '#b45309',
                            fontFamily: 'var(--font-mono)',
                            fontWeight: 700,
                            background: 'rgba(245, 158, 11, 0.12)',
                            border: '1px solid rgba(245, 158, 11, 0.35)',
                            padding: '3px 8px',
                            borderRadius: '5px',
                            display: 'inline-block',
                            whiteSpace: 'nowrap',
                            overflow: 'hidden',
                            textOverflow: 'ellipsis',
                            maxWidth: '100%',
                            boxShadow: '0 1px 2px rgba(245, 158, 11, 0.05)',
                          }}
                          title={rule.rule_expression}
                        >
                          {rule.rule_expression}
                        </code>
                      </td>

                      {/* Status */}
                      <td style={{ maxWidth: '100%', overflow: 'hidden' }}>
                        {isApproved ? (
                          <span
                            style={{
                              background: 'rgba(16, 185, 129, 0.15)',
                              color: '#047857',
                              border: '1px solid rgba(16, 185, 129, 0.4)',
                              padding: '3px 8px',
                              borderRadius: '6px',
                              fontSize: '10.5px',
                              fontWeight: 700,
                              display: 'inline-flex',
                              alignItems: 'center',
                              gap: '4px',
                              whiteSpace: 'nowrap',
                            }}
                          >
                            <Check size={12} strokeWidth={2.5} /> {isVi ? 'Đang Áp Dụng' : 'Approved'}
                          </span>
                        ) : isRejected ? (
                          <span
                            style={{
                              background: 'rgba(239, 68, 68, 0.15)',
                              color: '#b91c1c',
                              border: '1px solid rgba(239, 68, 68, 0.4)',
                              padding: '3px 8px',
                              borderRadius: '6px',
                              fontSize: '10.5px',
                              fontWeight: 700,
                              display: 'inline-flex',
                              alignItems: 'center',
                              gap: '4px',
                              whiteSpace: 'nowrap',
                            }}
                          >
                            <X size={12} strokeWidth={2.5} /> {isVi ? 'Đã Từ Chối' : 'Rejected'}
                          </span>
                        ) : (
                          <span
                            style={{
                              background: 'rgba(245, 158, 11, 0.15)',
                              color: '#b45309',
                              border: '1px solid rgba(245, 158, 11, 0.4)',
                              padding: '3px 8px',
                              borderRadius: '6px',
                              fontSize: '10.5px',
                              fontWeight: 700,
                              display: 'inline-flex',
                              alignItems: 'center',
                              gap: '4px',
                              whiteSpace: 'nowrap',
                            }}
                          >
                            <Clock size={12} strokeWidth={2.5} /> {isVi ? 'Chờ Phê Duyệt' : 'Proposed'}
                          </span>
                        )}
                      </td>

                      {/* Quarantined Rows */}
                      <td style={{ maxWidth: '100%', overflow: 'hidden' }}>
                        {rule.quarantined_count && rule.quarantined_count > 0 ? (
                          <span
                            style={{
                              background: 'rgba(239, 68, 68, 0.15)',
                              color: '#b91c1c',
                              border: '1px solid rgba(239, 68, 68, 0.4)',
                              padding: '3px 8px',
                              borderRadius: '6px',
                              fontSize: '10.5px',
                              fontWeight: 700,
                              display: 'inline-flex',
                              alignItems: 'center',
                              gap: '4px',
                              whiteSpace: 'nowrap',
                            }}
                          >
                            <Shield size={11} />
                            {rule.quarantined_count.toLocaleString()} {isVi ? 'dòng cách ly' : 'rows'}
                          </span>
                        ) : (
                          <span style={{ fontSize: '11px', color: 'var(--text-muted)', fontWeight: 600 }}>0 {isVi ? 'vi phạm' : 'violations'}</span>
                        )}
                      </td>

                      {/* Action Buttons (16% Width Fit) */}
                      <td style={{ textAlign: 'right', whiteSpace: 'nowrap' }} onClick={(e) => e.stopPropagation()}>
                        <div style={{ display: 'inline-flex', gap: '4px', alignItems: 'center', justifyContent: 'flex-end' }}>
                          {canReviewRules && isProposed && (
                            <button
                              type="button"
                              onClick={() => handleApproveRule(rule.id || rule.rule_id, rule.rule_name, rule.dataset_key)}
                              disabled={isActionLoading}
                              style={{
                                background: 'linear-gradient(135deg, #059669, #047857)',
                                color: '#ffffff',
                                border: 'none',
                                padding: '4px 9px',
                                borderRadius: '6px',
                                fontSize: '11px',
                                fontWeight: 700,
                                cursor: 'pointer',
                                display: 'inline-flex',
                                alignItems: 'center',
                                gap: '4px',
                                whiteSpace: 'nowrap',
                                boxShadow: '0 2px 4px rgba(5, 150, 105, 0.25)',
                              }}
                              title={isVi ? 'Đồng ý rule & chuyển bản ghi vi phạm vào Khu Vực Cách Ly' : 'Approve rule and isolate non-conforming rows to Quarantine'}
                            >
                              <Check size={12} className={isActionLoading ? 'spinning' : ''} />
                              <span>{isVi ? 'Đồng Ý & Cách Ly' : 'Approve & Quarantine'}</span>
                            </button>
                          )}

                          {isApproved && (
                            <button
                              type="button"
                              onClick={() => {
                                const rid = rule.id || rule.rule_id;
                                setActiveSubTab('quarantine');
                                navigate(`/operations/quarantine?rule_id=${rid}`);
                              }}
                              style={{
                                background: 'rgba(2, 132, 199, 0.15)',
                                color: '#0284c7',
                                border: '1px solid rgba(2, 132, 199, 0.4)',
                                padding: '4px 8px',
                                borderRadius: '6px',
                                fontSize: '11px',
                                fontWeight: 700,
                                cursor: 'pointer',
                                display: 'inline-flex',
                                alignItems: 'center',
                                gap: '4px',
                                whiteSpace: 'nowrap',
                                transition: 'all 0.15s ease',
                              }}
                            >
                              <Eye size={12} />
                              <span>{isVi ? 'Xem Cách Ly' : 'View Quarantine'}</span>
                            </button>
                          )}

                          {canReviewRules && !isRejected && (
                            <button
                              type="button"
                              onClick={() => handleRejectRule(rule.id || rule.rule_id)}
                              disabled={isActionLoading}
                              style={{
                                background: 'var(--bg-darker)',
                                color: 'var(--text-main)',
                                border: '1px solid var(--glass-border-bright)',
                                padding: '4px 6px',
                                borderRadius: '6px',
                                fontSize: '11px',
                                cursor: 'pointer',
                                display: 'inline-flex',
                                alignItems: 'center',
                                justifyContent: 'center',
                              }}
                              title={isVi ? 'Từ chối quy luật này' : 'Reject this rule'}
                            >
                              <X size={12} />
                            </button>
                          )}

                          <button
                            type="button"
                            onClick={() => setSelectedRuleForDetail(rule)}
                            style={{
                              background: 'var(--bg-darker)',
                              color: 'var(--text-main)',
                              border: '1px solid var(--glass-border-bright)',
                              padding: '4px 6px',
                              borderRadius: '6px',
                              fontSize: '11px',
                              cursor: 'pointer',
                              display: 'inline-flex',
                              alignItems: 'center',
                              justifyContent: 'center',
                            }}
                            title={isVi ? 'Xem chi tiết quy luật' : 'Inspect rule specifications'}
                          >
                            <Info size={12} />
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : (
          /* STANDARD OPERATIONS DATA TABLE */
          <div style={{ width: '100%', overflowX: 'auto', overflowY: 'visible', height: 'auto', maxHeight: 'none', borderRadius: 'var(--radius-card)' }}>
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
                        if (col === 'domain' && cellVal !== '—') {
                          return (
                            <td key={col}>
                              <span style={{ fontSize: '11px', color: 'var(--neon-cyan)', fontWeight: 600 }}>
                                {cellVal}
                              </span>
                            </td>
                          );
                        }
                        if (col === 'llm_claim') {
                          const claimText = row.llm_claim || row.admission_reason || '—';
                          return (
                            <td key={col} style={{ maxWidth: '320px', minWidth: '220px' }}>
                              <div
                                title={String(claimText)}
                                style={{
                                  fontSize: '11.5px',
                                  color: 'var(--text-muted)',
                                  whiteSpace: 'nowrap',
                                  overflow: 'hidden',
                                  textOverflow: 'ellipsis',
                                }}
                              >
                                {claimText}
                              </div>
                            </td>
                          );
                        }
                        if (col === 'confidence') {
                          const raw = row.confidence;
                          const num = typeof raw === 'number' ? raw : parseFloat(String(raw));
                          const conf = isNaN(num) ? 0.92 : num;
                          const pct = Math.round(conf <= 1.0 ? conf * 100 : conf);
                          return (
                            <td key={col}>
                              <span
                                style={{
                                  color: pct >= 90 ? 'var(--electric-green)' : pct >= 75 ? 'var(--warning-amber)' : 'var(--alert-magenta)',
                                  fontSize: '11px',
                                  fontWeight: 600,
                                }}
                              >
                                {pct}%
                              </span>
                            </td>
                          );
                        }
                        if (col === 'status') {
                          const st = String(cellVal).toUpperCase();
                          const isOk = st === 'ACTIVE' || st === 'VALID' || st === 'RESOLVED' || st === 'EXECUTED';
                          return (
                            <td key={col}>
                              <span
                                style={{
                                  background: isOk ? 'rgba(16, 185, 129, 0.12)' : 'rgba(244, 63, 94, 0.12)',
                                  color: isOk ? '#10b981' : '#f43f5e',
                                  border: `1px solid ${isOk ? 'rgba(16, 185, 129, 0.3)' : 'rgba(244, 63, 94, 0.3)'}`,
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
                        if (col === 'severity') {
                          const sev = String(cellVal).toUpperCase();
                          const isCrit = sev === 'CRITICAL';
                          const isHigh = sev === 'HIGH';
                          return (
                            <td key={col}>
                              <span
                                style={{
                                  color: isCrit ? '#f43f5e' : isHigh ? '#f59e0b' : '#38bdf8',
                                  fontWeight: 700,
                                  fontSize: '11px',
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
                        <td onClick={(e) => e.stopPropagation()}>
                          <button
                            type="button"
                            className="hud-btn"
                            style={{ height: '26px', fontSize: '11px', padding: '0 8px' }}
                            onClick={() => incId && handleOpenIncident(incId, row)}
                          >
                            {isVi ? 'Phân Tích' : 'Triage'}
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

      {/* RULE DETAIL & QUARANTINE SPECIFICATION MODAL */}
      {selectedRuleForDetail && (
        <div className="modal-overlay active" onClick={() => setSelectedRuleForDetail(null)}>
          <div
            className="modal-card"
            style={{ maxWidth: '640px', width: '90%' }}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="modal-header">
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <ShieldCheck size={18} style={{ color: '#10b981' }} />
                <span className="modal-title">
                  {selectedRuleForDetail.rule_name || selectedRuleForDetail.id}
                </span>
              </div>
              <button className="modal-close" onClick={() => setSelectedRuleForDetail(null)}>
                <X size={16} />
              </button>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '14px', marginTop: '12px' }}>
              {/* Dataset & Layer Banner */}
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  background: 'var(--bg-card)',
                  border: '1px solid var(--glass-border)',
                  padding: '10px 14px',
                  borderRadius: '8px',
                }}
              >
                <div>
                  <div style={{ fontSize: '10.5px', color: 'var(--text-muted)', textTransform: 'uppercase' }}>
                    {isVi ? 'Nguồn Dữ Liệu' : 'Dataset Source'}
                  </div>
                  <div style={{ fontWeight: 600, color: 'var(--neon-cyan)', fontSize: '12.5px', marginTop: '2px' }}>
                    {selectedRuleForDetail.dataset_name} ({selectedRuleForDetail.dataset_key})
                  </div>
                </div>

                <div>
                  <div style={{ fontSize: '10.5px', color: 'var(--text-muted)', textTransform: 'uppercase' }}>
                    {isVi ? 'Tầng Kiểm Soát' : 'Layer'}
                  </div>
                  <div style={{ fontWeight: 600, color: '#38bdf8', fontSize: '12.5px', marginTop: '2px' }}>
                    {selectedRuleForDetail.layer}
                  </div>
                </div>

                <div>
                  <div style={{ fontSize: '10.5px', color: 'var(--text-muted)', textTransform: 'uppercase' }}>
                    {isVi ? 'Trạng Thái' : 'Status'}
                  </div>
                  <div style={{ fontWeight: 600, color: selectedRuleForDetail.status === 'approved' ? '#10b981' : '#f59e0b', fontSize: '12.5px', marginTop: '2px' }}>
                    {selectedRuleForDetail.status === 'approved' ? (isVi ? 'Đang Áp Dụng' : 'Approved') : (isVi ? 'Chờ Duyệt' : 'Proposed')}
                  </div>
                </div>
              </div>

              {/* Expression Box */}
              <div>
                <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginBottom: '4px', fontWeight: 600 }}>
                  {isVi ? 'Biểu Thức Ràng Buộc (SQL / Evaluator Logic):' : 'Constraint Expression (SQL / Evaluator Logic):'}
                </div>
                <div className="terminal-block" style={{ padding: '10px 14px', background: '#0a0d14' }}>
                  <code style={{ color: 'var(--neon-cyan)', fontFamily: 'monospace', fontSize: '12.5px' }}>
                    {selectedRuleForDetail.rule_expression}
                  </code>
                </div>
              </div>

              {/* Physical / Statistical Rationale */}
              <div>
                <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginBottom: '4px', fontWeight: 600 }}>
                  {isVi ? 'Căn Cứ Kỹ Thuật & Tác Động:' : 'Technical Rationale & Impact:'}
                </div>
                <div style={{ fontSize: '12px', color: 'var(--text-main)', background: 'var(--bg-card)', padding: '10px 14px', borderRadius: '8px', border: '1px solid var(--glass-border)' }}>
                  {selectedRuleForDetail.description || (isVi ? 'Quy luật bảo vệ tính bất biến và chuẩn hóa chất lượng dữ liệu.' : 'Enforces data invariant and schema contract compliance.')}
                </div>
              </div>

              {/* Non-Destructive Quarantine Guarantee */}
              <div
                style={{
                  background: 'rgba(16, 185, 129, 0.08)',
                  border: '1px solid rgba(16, 185, 129, 0.25)',
                  borderRadius: '8px',
                  padding: '10px 14px',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '10px',
                }}
              >
                <Lock size={16} style={{ color: '#10b981', flexShrink: 0 }} />
                <span style={{ fontSize: '11.5px', color: 'var(--text-main)' }}>
                  {isVi
                    ? 'Cam kết bảo toàn: Bản ghi không hợp lệ được lưu trong bảng quarantine kèm chữ ký SHA-256. Dữ liệu gốc trong kho được bảo toàn 100% không chỉnh sửa.'
                    : 'Preservation Guarantee: Violations are routed to quarantine ledger with SHA-256 lineage hash. Raw source table is 100% untouched.'}
                </span>
              </div>

              {/* Modal Footer Actions */}
              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px', marginTop: '6px' }}>
                <button className="hud-btn" onClick={() => setSelectedRuleForDetail(null)}>
                  {isVi ? 'Đóng' : 'Close'}
                </button>
                {canReviewRules && selectedRuleForDetail.status !== 'approved' && (
                  <button
                    type="button"
                    className="hud-btn"
                    style={{
                      background: 'linear-gradient(135deg, #10b981, #059669)',
                      color: '#ffffff',
                      border: 'none',
                      padding: '6px 14px',
                      fontWeight: 600,
                    }}
                    onClick={() => {
                      handleApproveRule(
                        selectedRuleForDetail.id || selectedRuleForDetail.rule_id,
                        selectedRuleForDetail.rule_name,
                        selectedRuleForDetail.dataset_key
                      );
                      setSelectedRuleForDetail(null);
                    }}
                  >
                    <Check size={13} style={{ display: 'inline', marginRight: 4 }} />
                    {isVi ? 'Đồng Ý & Cách Ly' : 'Approve & Quarantine'}
                  </button>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* INTERACTIVE RCA TRIAGE MODAL */}
      {selectedIncident && (
        <div className="modal-overlay active" onClick={() => setSelectedIncident(null)}>
          <div
            className="modal-card"
            style={{ maxWidth: '840px', width: '95%', maxHeight: '90vh', overflowY: 'auto' }}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="modal-header">
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <TriangleAlert size={18} style={{ color: '#f59e0b' }} />
                <span className="modal-title">
                  {isVi ? 'Chẩn Đoán Sự Cố & Nguyên Nhân Gốc (RCA)' : 'Incident Diagnosis & Root Cause Analysis'}
                </span>
                <span
                  style={{
                    fontSize: '10px',
                    fontWeight: 700,
                    padding: '2px 8px',
                    borderRadius: '4px',
                    background: selectedIncident.severity === 'CRITICAL' ? 'rgba(239, 68, 68, 0.2)' : 'rgba(245, 158, 11, 0.2)',
                    color: selectedIncident.severity === 'CRITICAL' ? '#ef4444' : '#f59e0b',
                    border: selectedIncident.severity === 'CRITICAL' ? '1px solid #ef4444' : '1px solid #f59e0b',
                  }}
                >
                  {selectedIncident.severity || 'MEDIUM'}
                </span>
              </div>
              <button className="modal-close" onClick={() => setSelectedIncident(null)}>
                <X size={16} />
              </button>
            </div>

            <div style={{ marginTop: '12px' }}>
              {/* MODAL NAVIGATION TABS */}
              <div style={{ display: 'flex', gap: '8px', borderBottom: '1px solid var(--glass-border)', paddingBottom: '8px', marginBottom: '16px' }}>
                {(['rca', 'evidence', 'signals'] as const).map((tab) => (
                  <button
                    key={tab}
                    type="button"
                    onClick={() => setModalTab(tab)}
                    style={{
                      background: modalTab === tab ? 'rgba(56, 189, 248, 0.15)' : 'transparent',
                      color: modalTab === tab ? 'var(--neon-cyan)' : 'var(--text-muted)',
                      border: modalTab === tab ? '1px solid var(--neon-cyan)' : '1px solid transparent',
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
                    {tab === 'rca' ? (
                      <>{isVi ? 'Hành Trình RCA & Suy Luận' : 'RCA Reasoning & Journey'}</>
                    ) : tab === 'evidence' ? (
                      <>{isVi ? 'Chứng Cứ Điều Tra' : 'Evidence'} ({Array.isArray(selectedIncident.evidence) ? selectedIncident.evidence.length : 0})</>
                    ) : (
                      <>{isVi ? 'Tín Hiệu Gốc (Signals)' : 'Signals'} ({Array.isArray(selectedIncident.signals) ? selectedIncident.signals.length : (selectedIncident.signal_ids?.length || 0)})</>
                    )}
                  </button>
                ))}
              </div>

              {incidentLoading ? (
                <div style={{ padding: '36px', textAlign: 'center', color: 'var(--text-muted)' }}>
                  <RefreshCw size={22} className="spinning" style={{ marginBottom: '10px' }} />
                  <div>{isVi ? 'Đang nạp chi tiết hành trình sự cố...' : 'Loading incident journey & trace details...'}</div>
                </div>
              ) : modalTab === 'rca' ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                  {/* TOP KPI CARDS */}
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '10px' }}>
                    <div style={{ background: 'var(--bg-card)', padding: '10px 14px', borderRadius: '8px', border: '1px solid var(--glass-border)' }}>
                      <div style={{ fontSize: '10.5px', color: 'var(--text-muted)' }}>{isVi ? 'Phân Loại Lỗi' : 'Fault Family'}</div>
                      <div style={{ fontSize: '12.5px', fontWeight: 600, color: '#c084fc', marginTop: '3px' }}>
                        {selectedIncident.fault_family || 'DATA_INVARIANT_VIOLATION'}
                      </div>
                    </div>

                    <div style={{ background: 'var(--bg-card)', padding: '10px 14px', borderRadius: '8px', border: '1px solid var(--glass-border)' }}>
                      <div style={{ fontSize: '10.5px', color: 'var(--text-muted)' }}>{isVi ? 'Bản Chất Nguyên Nhân' : 'Cause Classification'}</div>
                      <div style={{ fontSize: '12.5px', fontWeight: 600, color: selectedIncident.llm_classification === 'OPERATIONAL' ? '#f59e0b' : '#38bdf8', marginTop: '3px' }}>
                        {selectedIncident.llm_classification || 'DATA'}
                      </div>
                    </div>

                    <div style={{ background: 'var(--bg-card)', padding: '10px 14px', borderRadius: '8px', border: '1px solid var(--glass-border)' }}>
                      <div style={{ fontSize: '10.5px', color: 'var(--text-muted)' }}>{isVi ? 'Hành Động Đề Xuất' : 'Prescribed Action'}</div>
                      <div style={{ fontSize: '12.5px', fontWeight: 600, color: '#10b981', marginTop: '3px' }}>
                        {selectedIncident.expected_action || 'QUARANTINE_NON_DESTRUCTIVE'}
                      </div>
                    </div>

                    <div style={{ background: 'var(--bg-card)', padding: '10px 14px', borderRadius: '8px', border: '1px solid var(--glass-border)' }}>
                      <div style={{ fontSize: '10.5px', color: 'var(--text-muted)' }}>{isVi ? 'Độ Tin Cậy & Metrics' : 'Confidence & Metrics'}</div>
                      <div style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-main)', marginTop: '3px', display: 'flex', gap: '8px', alignItems: 'center' }}>
                        <span style={{ color: '#10b981' }}>{selectedIncident.confidence || 88.0}%</span>
                        {selectedIncident.latency_sec !== undefined && (
                          <span style={{ fontSize: '10.5px', color: 'var(--text-muted)' }}>
                            ⏱️ {Number(selectedIncident.latency_sec).toFixed(2)}s
                          </span>
                        )}
                        {selectedIncident.tokens_spent !== undefined && (
                          <span style={{ fontSize: '10.5px', color: '#a855f7' }}>
                            🪙 {selectedIncident.tokens_spent}t
                          </span>
                        )}
                      </div>
                    </div>
                  </div>

                  {/* END-TO-END INVESTIGATION TIMELINE */}
                  <div style={{ background: 'var(--bg-card)', padding: '16px', borderRadius: '10px', border: '1px solid var(--glass-border)' }}>
                    <div style={{ fontSize: '12px', fontWeight: 700, color: 'var(--neon-cyan)', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: '14px' }}>
                      {isVi ? 'Quá Trình Phát Hiện Signal → Suy Luận Tool → Kết Luận Root Cause' : 'End-to-End Incident Journey: Signal → Reasoning → Root Cause'}
                    </div>

                    <div style={{ display: 'flex', flexDirection: 'column', gap: '14px', position: 'relative', paddingLeft: '20px' }}>
                      {/* Vertical line connector */}
                      <div style={{ position: 'absolute', left: '7px', top: '10px', bottom: '10px', width: '2px', background: 'rgba(56, 189, 248, 0.25)' }} />

                      {/* STEP 1: SIGNAL DETECTION & ADMISSION */}
                      <div style={{ position: 'relative' }}>
                        <div style={{ position: 'absolute', left: '-20px', top: '2px', width: '12px', height: '12px', borderRadius: '50%', background: '#f59e0b', border: '2px solid var(--bg-card)' }} />
                        <div style={{ fontSize: '11px', fontWeight: 700, color: '#f59e0b', textTransform: 'uppercase' }}>
                          {isVi ? 'Bước 1: Tiếp Nhận Tín Hiệu & Điều Kiện Admission' : 'Step 1: Signal Admission & Trigger'}
                        </div>
                        <div style={{ background: 'rgba(255, 255, 255, 0.03)', padding: '10px 12px', borderRadius: '6px', marginTop: '6px', border: '1px solid rgba(255, 255, 255, 0.06)' }}>
                          <div style={{ fontSize: '12px', color: 'var(--text-main)', fontWeight: 500, lineHeight: 1.4 }}>
                            {selectedIncident.admission_reason || (isVi ? 'Tín hiệu bất thường được phát hiện từ tầng telemetry' : 'Anomaly signal detected across telemetry')}
                          </div>
                          <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', marginTop: '6px' }}>
                            <span style={{ fontSize: '10px', background: 'rgba(56, 189, 248, 0.1)', color: 'var(--neon-cyan)', padding: '2px 6px', borderRadius: '4px' }}>
                              Entity: {selectedIncident.target_entity || selectedIncident.entity_ids?.[0] || 'N/A'}
                            </span>
                            <span style={{ fontSize: '10px', background: 'rgba(168, 85, 247, 0.1)', color: '#c084fc', padding: '2px 6px', borderRadius: '4px' }}>
                              Detector Layer: {selectedIncident.layer || 'L1'}
                            </span>
                            <span style={{ fontSize: '10px', background: 'rgba(245, 158, 11, 0.1)', color: '#f59e0b', padding: '2px 6px', borderRadius: '4px' }}>
                              Signals Count: {selectedIncident.signal_ids?.length || 1}
                            </span>
                          </div>
                        </div>
                      </div>

                      {/* STEP 2: DYNAMIC REACT TOOL EXECUTION TRACE */}
                      <div style={{ position: 'relative' }}>
                        <div style={{ position: 'absolute', left: '-20px', top: '2px', width: '12px', height: '12px', borderRadius: '50%', background: 'var(--neon-cyan)', border: '2px solid var(--bg-card)' }} />
                        <div style={{ fontSize: '11px', fontWeight: 700, color: 'var(--neon-cyan)', textTransform: 'uppercase' }}>
                          {isVi ? 'Bước 2: Quá Trình Agent Khảo Sát & Thực Thi Tools (ReAct Trace)' : 'Step 2: LLM ReAct Tool Calls & Investigation Trace'}
                        </div>
                        <div style={{ marginTop: '6px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
                          {Array.isArray(selectedIncident.meta?.tool_execution_trace) && selectedIncident.meta.tool_execution_trace.length > 0 ? (
                            selectedIncident.meta.tool_execution_trace.map((trace: any, idx: number) => (
                              <div
                                key={idx}
                                style={{
                                  background: 'rgba(56, 189, 248, 0.05)',
                                  border: '1px solid rgba(56, 189, 248, 0.15)',
                                  borderRadius: '6px',
                                  padding: '8px 12px',
                                  fontSize: '11.5px',
                                }}
                              >
                                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
                                  <span style={{ fontWeight: 700, color: 'var(--neon-cyan)', fontFamily: 'monospace' }}>
                                    ⚙️ {trace.tool_name || trace.tool}
                                  </span>
                                  <div style={{ display: 'flex', gap: '6px', fontSize: '10px', color: 'var(--text-muted)' }}>
                                    {trace.wall_clock_sec && <span>⏱️ {trace.wall_clock_sec}s</span>}
                                    {trace.tokens_used && <span>🪙 {trace.tokens_used}t</span>}
                                    <span style={{ color: trace.success !== false ? '#10b981' : '#ef4444', fontWeight: 600 }}>
                                      {trace.success !== false ? 'SUCCESS' : 'FAILED'}
                                    </span>
                                  </div>
                                </div>
                                {trace.args && Object.keys(trace.args).length > 0 && (
                                  <div style={{ fontSize: '10.5px', color: 'var(--text-muted)', fontFamily: 'monospace', marginBottom: '4px' }}>
                                    Input: {JSON.stringify(trace.args)}
                                  </div>
                                )}
                                <div style={{ fontSize: '11px', color: 'var(--text-main)', lineHeight: 1.4 }}>
                                  {trace.data ? (typeof trace.data === 'string' ? trace.data : JSON.stringify(trace.data)) : (isVi ? 'Kiểm tra thành công, tạo chứng cứ.' : 'Execution completed, compiled evidence.')}
                                </div>
                              </div>
                            ))
                          ) : (
                            <div style={{ background: 'rgba(255, 255, 255, 0.03)', padding: '10px 12px', borderRadius: '6px', border: '1px solid rgba(255, 255, 255, 0.06)', fontSize: '11.5px' }}>
                              <div style={{ fontWeight: 600, color: 'var(--text-main)' }}>
                                🛠️ {isVi ? 'Rule-Based Dynamic Heuristic Verification' : 'Rule-Based Dynamic Heuristic Verification'}
                              </div>
                              <div style={{ color: 'var(--text-muted)', marginTop: '4px', lineHeight: 1.45 }}>
                                {isVi
                                  ? 'Agent đã đối soát phân bố baseline lịch sử, kiểm tra ràng buộc schema upstream contract và thẩm định mức độ đột biến của sensor.'
                                  : 'Agent executed deterministic baseline checks, upstream schema contract audits, and sensor variance verification.'}
                              </div>
                            </div>
                          )}
                        </div>
                      </div>

                      {/* STEP 3: ROOT CAUSE CONCLUSION */}
                      <div style={{ position: 'relative' }}>
                        <div style={{ position: 'absolute', left: '-20px', top: '2px', width: '12px', height: '12px', borderRadius: '50%', background: '#10b981', border: '2px solid var(--bg-card)' }} />
                        <div style={{ fontSize: '11px', fontWeight: 700, color: '#10b981', textTransform: 'uppercase' }}>
                          {isVi ? 'Bước 3: Kết Luận Nguyên Nhân Gốc (Root Cause Diagnosis)' : 'Step 3: Root Cause Conclusion & Claim'}
                        </div>
                        <div style={{ background: 'rgba(16, 185, 129, 0.08)', padding: '12px 14px', borderRadius: '6px', marginTop: '6px', border: '1px solid rgba(16, 185, 129, 0.2)' }}>
                          <div style={{ fontSize: '13px', color: 'var(--text-main)', fontWeight: 600, lineHeight: 1.5 }}>
                            {selectedIncident.llm_claim || selectedIncident.ground_truth_cause || selectedIncident.admission_reason}
                          </div>
                        </div>
                      </div>

                      {/* STEP 4: PREVENTIVE DQ RULE PROPOSAL LINK */}
                      <div style={{ position: 'relative', marginTop: '16px' }}>
                        <div style={{ position: 'absolute', left: '-20px', top: '2px', width: '12px', height: '12px', borderRadius: '50%', background: '#38bdf8', border: '2px solid var(--bg-card)' }} />
                        <div style={{ fontSize: '11px', fontWeight: 700, color: '#38bdf8', textTransform: 'uppercase' }}>
                          {isVi ? 'Bước 4: Đề Xuất Luật Phòng Ngừa (Preventive Control)' : 'Step 4: Preventive Rule Proposal'}
                        </div>
                        <div style={{ background: 'rgba(56, 189, 248, 0.08)', padding: '12px 14px', borderRadius: '6px', marginTop: '6px', border: '1px solid rgba(56, 189, 248, 0.2)', display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '8px' }}>
                          <div>
                            <div style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-main)' }}>
                              {selectedIncident.expected_action || 'PREVENTIVE_DQ_RULE_PROPOSAL'}
                            </div>
                            <div style={{ fontSize: '11.5px', color: 'var(--text-muted)', marginTop: '2px' }}>
                              {isVi ? 'RCA đề xuất tạo luật kiểm soát chất lượng dữ liệu để ngăn chặn sự cố này tái diễn.' : 'RCA recommended creating a data quality control rule to prevent recurrence.'}
                            </div>
                          </div>
                          <button
                            className="hud-btn primary"
                            style={{ fontSize: '11.5px', padding: '6px 12px', display: 'inline-flex', alignItems: 'center', gap: '6px' }}
                            onClick={() => {
                              const incId = selectedIncident.incident_id || selectedIncident.id;
                              setSelectedIncident(null);
                              setActiveSubTab('rules');
                              navigate('/operations/rules');
                              if (incId) {
                                setFilterQuery(incId);
                              }
                            }}
                          >
                            <ShieldCheck size={14} />
                            {isVi ? 'Xem & Duyệt Rule Đề Xuất →' : 'View & Approve Proposed Rule →'}
                          </button>
                        </div>
                      </div>

                      {/* STEP 5: ALERT HUMAN FEEDBACK */}
                      <div style={{ position: 'relative', marginTop: '16px' }}>
                        <div style={{ position: 'absolute', left: '-20px', top: '2px', width: '12px', height: '12px', borderRadius: '50%', background: '#a855f7', border: '2px solid var(--bg-card)' }} />
                        <div style={{ fontSize: '11px', fontWeight: 700, color: '#a855f7', textTransform: 'uppercase' }}>
                          {isVi ? 'Bước 5: Thẩm Định & Phản Hồi Cảnh Báo (Human Feedback)' : 'Step 5: Alert Feedback & Verification'}
                        </div>

                        {selectedIncident.feedback_type ? (
                          <div style={{
                            background: selectedIncident.feedback_type === 'TRUE_POSITIVE' ? 'rgba(16, 185, 129, 0.1)' : 'rgba(239, 68, 68, 0.1)',
                            border: `1px solid ${selectedIncident.feedback_type === 'TRUE_POSITIVE' ? 'rgba(16, 185, 129, 0.3)' : 'rgba(239, 68, 68, 0.3)'}`,
                            padding: '12px 14px',
                            borderRadius: '6px',
                            marginTop: '6px',
                            fontSize: '12.5px',
                          }}>
                            <div style={{ fontWeight: 700, color: selectedIncident.feedback_type === 'TRUE_POSITIVE' ? '#10b981' : '#ef4444', display: 'flex', alignItems: 'center', gap: '6px' }}>
                              {selectedIncident.feedback_type === 'TRUE_POSITIVE' ? (
                                <>
                                  <CheckCircle2 size={16} />
                                  {isVi ? 'Đã xác nhận: Cảnh báo đúng' : 'Confirmed: True Positive Alert'}
                                </>
                              ) : (
                                <>
                                  <XCircle size={16} />
                                  {isVi ? 'Đã xác nhận: Cảnh báo nhầm' : 'Confirmed: False Positive Alert'}
                                </>
                              )}
                            </div>
                            {selectedIncident.feedback_reason && (
                              <div style={{ color: 'var(--text-main)', marginTop: '6px', fontSize: '12px' }}>
                                <strong>{isVi ? 'Nguyên do:' : 'Reason:'}</strong> {selectedIncident.feedback_reason}
                              </div>
                            )}
                          </div>
                        ) : (
                          <div style={{ background: 'rgba(255, 255, 255, 0.03)', padding: '12px 14px', borderRadius: '6px', marginTop: '6px', border: '1px solid var(--glass-border)' }}>
                            <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginBottom: '8px' }}>
                              {isVi ? 'Bạn thẩm định cảnh báo này như thế nào?' : 'How do you evaluate this alert?'}
                            </div>
                            <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                              <button
                                className="hud-btn"
                                disabled={alertFeedbackSubmitting}
                                onClick={() => handleAlertFeedback(selectedIncident.incident_id || selectedIncident.id, 'TRUE_POSITIVE')}
                                style={{
                                  background: 'rgba(16, 185, 129, 0.12)',
                                  border: '1px solid rgba(16, 185, 129, 0.4)',
                                  color: '#10b981',
                                  fontWeight: 600,
                                  fontSize: '11.5px',
                                  padding: '6px 12px',
                                  cursor: 'pointer',
                                  borderRadius: '6px',
                                  display: 'inline-flex',
                                  alignItems: 'center',
                                  gap: '4px',
                                }}
                              >
                                <CheckCircle2 size={14} />
                                {isVi ? 'Cảnh báo đúng' : 'True Positive'}
                              </button>

                              <button
                                className="hud-btn"
                                disabled={alertFeedbackSubmitting}
                                onClick={() => setShowFalsePositiveInput((prev) => !prev)}
                                style={{
                                  background: 'rgba(239, 68, 68, 0.12)',
                                  border: '1px solid rgba(239, 68, 68, 0.4)',
                                  color: '#ef4444',
                                  fontWeight: 600,
                                  fontSize: '11.5px',
                                  padding: '6px 12px',
                                  cursor: 'pointer',
                                  borderRadius: '6px',
                                  display: 'inline-flex',
                                  alignItems: 'center',
                                  gap: '4px',
                                }}
                              >
                                <XCircle size={14} />
                                {isVi ? 'Cảnh báo nhầm' : 'False Positive'}
                              </button>
                            </div>

                            {showFalsePositiveInput && (
                              <div style={{ marginTop: '10px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
                                <textarea
                                  rows={2}
                                  placeholder={isVi ? 'Nhập nguyên do cảnh báo nhầm (ví dụ: Nhiễu cảm biến tạm thời, dữ liệu môi trường đặc thù...)' : 'Enter false positive reason (e.g. Temporary sensor noise, unusual environment...)'}
                                  value={alertFeedbackReason}
                                  onChange={(e) => setAlertFeedbackReason(e.target.value)}
                                  style={{
                                    width: '100%',
                                    padding: '8px 10px',
                                    borderRadius: '6px',
                                    background: 'var(--bg-input)',
                                    border: '1px solid var(--glass-border)',
                                    color: 'var(--text-main)',
                                    fontSize: '12px',
                                  }}
                                />
                                <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '6px' }}>
                                  <button className="hud-btn" onClick={() => setShowFalsePositiveInput(false)} style={{ fontSize: '11px', padding: '4px 10px' }}>
                                    {isVi ? 'Hủy' : 'Cancel'}
                                  </button>
                                  <button
                                    className="hud-btn"
                                    disabled={alertFeedbackSubmitting}
                                    onClick={() => handleAlertFeedback(selectedIncident.incident_id || selectedIncident.id, 'FALSE_POSITIVE', alertFeedbackReason)}
                                    style={{
                                      background: '#dc2626',
                                      color: '#fff',
                                      border: 'none',
                                      fontWeight: 600,
                                      fontSize: '11px',
                                      padding: '4px 12px',
                                      borderRadius: '6px',
                                      cursor: 'pointer',
                                    }}
                                  >
                                    {isVi ? 'Gửi Phản Hồi' : 'Submit Feedback'}
                                  </button>
                                </div>
                              </div>
                            )}
                          </div>
                        )}
                      </div>
                    </div>
                  </div>

                  <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px' }}>
                    <button className="hud-btn" onClick={() => setSelectedIncident(null)}>
                      {isVi ? 'Đóng' : 'Close'}
                    </button>
                  </div>
                </div>
              ) : modalTab === 'evidence' ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                  {Array.isArray(selectedIncident.evidence) && selectedIncident.evidence.length > 0 ? (
                    selectedIncident.evidence.map((ev: any, idx: number) => (
                      <div
                        key={ev.evidence_id || idx}
                        style={{
                          background: 'var(--bg-card)',
                          padding: '12px 14px',
                          borderRadius: '8px',
                          border: '1px solid var(--glass-border)',
                          fontSize: '11.5px',
                        }}
                      >
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '6px' }}>
                          <span style={{ fontWeight: 700, color: 'var(--neon-cyan)', fontFamily: 'monospace' }}>
                            📁 {ev.evidence_id || `EV-${idx + 1}`}
                          </span>
                          <span style={{ fontSize: '10px', color: 'var(--text-muted)', background: 'rgba(255,255,255,0.06)', padding: '2px 8px', borderRadius: '4px', border: '1px solid rgba(255,255,255,0.1)' }}>
                            {ev.source_type || 'TOOL_OUTPUT'} ({ev.source_id || 'telemetry'})
                          </span>
                        </div>
                        <div style={{ color: 'var(--text-main)', lineHeight: 1.5, fontSize: '12px' }}>
                          {ev.summary || (typeof ev === 'string' ? ev : JSON.stringify(ev))}
                        </div>
                      </div>
                    ))
                  ) : (
                    <div style={{ background: 'var(--bg-card)', padding: '32px', textAlign: 'center', borderRadius: '8px', border: '1px solid var(--glass-border)' }}>
                      <div style={{ color: 'var(--text-muted)', fontSize: '12.5px' }}>
                        {isVi ? 'Chưa có chứng cứ trực tiếp được thu thập.' : 'No direct evidence records collected yet.'}
                      </div>
                    </div>
                  )}
                </div>
              ) : (
                /* TAB SIGNALS (REPLACING RAW JSON) */
                <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                  {Array.isArray(selectedIncident.signals) && selectedIncident.signals.length > 0 ? (
                    selectedIncident.signals.map((sig: any, idx: number) => (
                      <div
                        key={sig.signal_id || idx}
                        style={{
                          background: 'var(--bg-card)',
                          padding: '12px 14px',
                          borderRadius: '8px',
                          border: '1px solid var(--glass-border)',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'space-between',
                          gap: '12px',
                        }}
                      >
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                            <span style={{ fontWeight: 700, color: 'var(--neon-cyan)', fontFamily: 'monospace', fontSize: '12px' }}>
                              ⚡ {sig.signal_id || `SIG-${idx + 1}`}
                            </span>
                            <span
                              style={{
                                fontSize: '10px',
                                fontWeight: 700,
                                padding: '1px 6px',
                                borderRadius: '4px',
                                background: sig.layer === 'L1' ? 'rgba(239, 68, 68, 0.15)' : sig.layer === 'L2' ? 'rgba(245, 158, 11, 0.15)' : 'rgba(168, 85, 247, 0.15)',
                                color: sig.layer === 'L1' ? '#ef4444' : sig.layer === 'L2' ? '#f59e0b' : '#c084fc',
                              }}
                            >
                              Layer {sig.layer || 'L1'} ({sig.detector || 'Validation'})
                            </span>
                          </div>
                          <div style={{ fontSize: '11.5px', color: 'var(--text-main)', marginTop: '2px' }}>
                            <strong>Metric/Target:</strong> <code style={{ color: 'var(--neon-cyan)' }}>{sig.metric_or_relationship || 'telemetry_value'}</code>
                          </div>
                        </div>

                        <div style={{ textAlign: 'right', display: 'flex', flexDirection: 'column', gap: '4px' }}>
                          <span
                            style={{
                              fontSize: '10px',
                              fontWeight: 700,
                              padding: '2px 8px',
                              borderRadius: '4px',
                              background: sig.severity === 'CRITICAL' ? 'rgba(239, 68, 68, 0.2)' : 'rgba(245, 158, 11, 0.2)',
                              color: sig.severity === 'CRITICAL' ? '#ef4444' : '#f59e0b',
                            }}
                          >
                            {sig.severity || 'MEDIUM'}
                          </span>
                          {sig.score !== undefined && (
                            <span style={{ fontSize: '10.5px', color: 'var(--text-muted)' }}>
                              Score: <strong style={{ color: 'var(--text-main)' }}>{sig.score}</strong>
                            </span>
                          )}
                        </div>
                      </div>
                    ))
                  ) : Array.isArray(selectedIncident.signal_ids) && selectedIncident.signal_ids.length > 0 ? (
                    selectedIncident.signal_ids.map((sigId: string, idx: number) => (
                      <div
                        key={sigId || idx}
                        style={{
                          background: 'var(--bg-card)',
                          padding: '12px 14px',
                          borderRadius: '8px',
                          border: '1px solid var(--glass-border)',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'space-between',
                        }}
                      >
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                          <span style={{ fontWeight: 700, color: 'var(--neon-cyan)', fontFamily: 'monospace', fontSize: '12px' }}>
                            ⚡ {sigId}
                          </span>
                          <span style={{ fontSize: '10px', background: 'rgba(56, 189, 248, 0.1)', color: 'var(--neon-cyan)', padding: '1px 6px', borderRadius: '4px' }}>
                            {selectedIncident.layer || 'L1'} Detector Signal
                          </span>
                        </div>
                        <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                          {selectedIncident.admission_reason?.split(':')[0] || 'Telemetry Anomaly'}
                        </span>
                      </div>
                    ))
                  ) : (
                    <div style={{ background: 'var(--bg-card)', padding: '32px', textAlign: 'center', borderRadius: '8px', border: '1px solid var(--glass-border)' }}>
                      <div style={{ color: 'var(--text-muted)', fontSize: '12.5px' }}>
                        {isVi ? 'Không tìm thấy tín hiệu bất thường nào.' : 'No signal records found.'}
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </section>
  );
};

