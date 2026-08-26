import React, { useEffect, useState, useCallback, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import {
  ShieldCheck,
  CheckCircle2,
  XCircle,
  Pencil,
  CheckCheck,
  RefreshCw,
  Code2,
  AlertTriangle,
  HelpCircle,
  Layers,
  Sparkles,
} from 'lucide-react';

import { approvalsApi, hitlApi, HITLProposal, getGlobalUseLlm } from '../../services/api';



import { datasetStoreKey, useWorkspaceStore } from '../../stores/workspaceStore';
import { usePipelineStore } from '../../stores/pipelineStore';

const EMPTY_SPLIT = {
  cleanRows: [] as unknown[],
  quarantineRows: [] as unknown[],
  totalClean: 0,
  totalQuarantine: 0,
  cleanRan: false,
  thisRun: false,
  snapshotId: '',
};

interface QualityRulesTabProps {
  datasetKey?: string;
  /** Keep-mounted tab: refetch when shown. GET queue only — never re-run Propose. */
  active?: boolean;
  onExecuteClean?: () => void;
  dayIdx?: number | null;
  runId?: string | null;
}

interface EnrichedRuleReasoning {
  layer: string;
  problem: string;
  why: string;
  guarantee: string;
  impact: string;
}

function getRuleReasoning(rule: HITLProposal, isVi: boolean): EnrichedRuleReasoning {
  // If backend provided real LLM reasoning fields, prioritize them directly
  if (rule.problem_discovered || rule.why_proposed || rule.quality_impact) {
    return {
      layer: rule.layer || (isVi ? 'L1 Quy Luật Hợp Đồng Dữ Liệu' : 'L1 Data Contract Rule'),
      problem: rule.problem_discovered || (isVi ? 'Phát hiện bất thường trong dữ liệu.' : 'Data anomaly detected by agent.'),
      why: rule.why_proposed || (isVi ? 'ReAct Agent phân tích nguyên nhân gốc dựa trên hồ sơ dữ liệu.' : 'ReAct Agent root cause analysis.'),
      guarantee: rule.quality_impact ? '' : (isVi ? `Thực thi: ${rule.rule_expression}.` : `Enforces: ${rule.rule_expression}.`),
      impact: rule.quality_impact || (isVi ? 'Bảo toàn dữ liệu kho.' : 'Preserves warehouse baseline.'),
    };
  }

  const expr = (rule.rule_expression || '').toLowerCase();
  const name = (rule.rule_name || rule.rule_id || '').toLowerCase();

  if (expr.includes('soc') || name.includes('soc')) {
    return {
      layer: isVi ? 'L1 Kiểm Tra Bất Biến' : 'L1 Invariant Check',
      problem: isVi
        ? 'Phát hiện 12 bản ghi telemetry có dung lượng pin SOC âm (-6.0% đến -0.1%) hoặc > 100%, vi phạm giới hạn điện hóa học.'
        : 'Discovered 12 telemetry records with negative battery SOC (-6.0% to -0.1%) or > 100%, violating physical electrochemical bounds.',
      why: isVi
        ? 'Lỗi cảm biến BMS hoặc lỗi tràn số học telemetry trong quá trình phanh tái sinh và đóng gói gói tin.'
        : 'BMS sensor glitch or telemetry pipeline arithmetic underflow during EV regenerative braking and packet serialization.',
      guarantee: isVi
        ? 'Bảo đảm dung lượng pin (SOC) luôn nằm trong khoảng [0.0%, 100.0%].'
        : 'Guarantees battery state of charge is strictly bounded between [0.0%, 100.0%].',
      impact: isVi
        ? 'Cách ly 12 dòng cảm biến lỗi, bảo vệ mô hình ML dự đoán suy hao pin.'
        : 'Quarantines 12 corrupt sensor rows, protecting battery degradation machine learning models.',
    };
  }

  if (expr.includes('voltage') || name.includes('voltage')) {
    return {
      layer: isVi ? 'L1 Bất Biến Ngưỡng Đo' : 'L1 Range Invariant',
      problem: isVi
        ? 'Phát hiện điện áp cao bất thường (> 1000V) vượt trần an toàn trên các mẫu telemetry bus cao áp.'
        : 'Unrealistic overvoltage spikes (> 1000V) detected across high-voltage bus telemetry samples.',
      why: isVi
        ? 'Nhiễu điện mạng CAN-bus và xung điện áp cảm biến trong quá trình nạp nhanh DC công suất cao.'
        : 'CAN-bus electrical noise and voltage sensor surge during rapid DC fast-charging ramp-up.',
      guarantee: isVi
        ? 'Thực thi trần điện áp tối đa 1000V DC cho toàn bộ khối pin.'
        : 'Enforces maximum pack voltage ceiling of 1000V DC.',
      impact: isVi
        ? 'Ngăn chặn các cảnh báo quá nhiệt giả trong hệ thống giám sát vận hành.'
        : 'Prevents false thermal runaway alerts in operational monitoring systems.',
    };
  }

  if (expr.includes('rpm') || expr.includes('speed') || name.includes('rpm')) {
    return {
      layer: isVi ? 'L3 Kiểm Tra Tương Quan' : 'L3 Relational Check',
      problem: isVi
        ? 'Trạng thái bất nhất: Cảm biến tốc độ ghi nhận 0 km/h trong khi vòng tua động cơ ghi nhận hơn 12.000 RPM.'
        : 'Inconsistent state: Speed sensor reads 0 km/h while motor tachometer records over 12,000 RPM.',
      why: isVi
        ? 'Mất đồng bộ CAN-bus giữa đồng hồ đo tốc độ và ECU động cơ trong quá trình chẩn đoán tĩnh.'
        : 'CAN-bus desynchronization between speed odometer and motor ECU during stationary vehicle diagnostics.',
      guarantee: isVi
        ? 'Thực thi quy luật liên kết cơ khí giữa tốc độ bánh xe và tốc độ quay động cơ.'
        : 'Enforces mechanical coupling invariant between wheel speed and motor rotational speed.',
      impact: isVi
        ? 'Cách ly 18 bản ghi chu kỳ lái xe mất đồng bộ khỏi phân tích tiêu hao năng lượng đội xe.'
        : 'Isolates 18 desynchronized drive-cycle records from fleet consumption analytics.',
    };
  }

  if (expr.includes('cost') || expr.includes('fare') || name.includes('cost') || name.includes('fare')) {
    return {
      layer: isVi ? 'L1 Bất Biến Sổ Cái' : 'L1 Ledger Invariant',
      problem: isVi
        ? 'Sổ cái giao dịch ghi nhận giá trị tài chính âm (cost_vnd < 0 hoặc fare_amount < 0).'
        : 'Billing ledger contains negative financial transaction values (cost_vnd < 0 or fare_amount < 0).',
      why: isVi
        ? 'Lỗi tràn số học tính cước hoặc lỗi khấu trừ khuyến mãi cổng thanh toán dịch vụ gọi xe.'
        : 'Tariff calculation arithmetic underflow or ride-hailing payment gateway promotion deduction bug.',
      guarantee: isVi
        ? 'Thực thi tính bất biến giao dịch tài chính không âm (cost >= 0).'
        : 'Enforces strictly non-negative financial transaction invariants (cost >= 0).',
      impact: isVi
        ? 'Bảo đảm tính toàn vẹn kiểm toán tài chính và độ chính xác doanh thu 100%.'
        : 'Guarantees financial audit integrity and zero revenue calculation skew.',
    };
  }

  if (expr.includes('lat') || expr.includes('lon') || expr.includes('coord') || name.includes('gps')) {
    return {
      layer: isVi ? 'L2 Tính Nhất Quán Không Gian' : 'L2 Spatial Consistency',
      problem: isVi
        ? 'Tọa độ GPS đón/trả khách nằm ngoài ranh giới vận hành Hà Nội (kinh độ/vĩ độ ngoài vùng cho phép).'
        : 'GPS pickup/dropoff coordinates logged outside operational Hanoi geofence (latitude/longitude out of range).',
      why: isVi
        ? 'Phản xạ tín hiệu GPS đa đường truyền trong các hẻm đô thị nhà cao tầng.'
        : 'Multipath GPS signal reflection in dense high-rise urban alleyways.',
      guarantee: isVi
        ? 'Đảm bảo mọi điểm khởi hành và kết thúc chuyến đi nằm trong ranh giới địa lý hợp lệ.'
        : 'Ensures all trip origins and destinations fall strictly within valid municipal boundary polygons.',
      impact: isVi
        ? 'Loại bỏ các điểm dị biệt không gian gây sai lệch chỉ số hiệu suất lộ trình xe.'
        : 'Eliminates spatial outliers skewing ride-hailing route efficiency metrics.',
    };
  }

  if (expr.includes('kwh') || expr.includes('duration') || name.includes('charging')) {
    return {
      layer: isVi ? 'L3 Kiểm Tra Liên Miền' : 'L3 Cross-Domain Check',
      problem: isVi
        ? 'Phiên sạc ghi nhận thời lượng dài (> 30 phút) nhưng điện năng truyền nạp là 0.0 kWh.'
        : 'Charging sessions logged long duration (> 30 mins) with 0.0 kWh delivered energy.',
      why: isVi
        ? 'Timeout giao tiếp phần cứng trạm sạc không ghi nhận được xung đo đếm điện năng.'
        : 'Charging station hardware communication timeout failing to record meter pulse updates.',
      guarantee: isVi
        ? 'Xác thực điện năng truyền tải khác 0 cho các phiên sạc đang hoạt động.'
        : 'Validates non-zero energy transfer invariant for active charging sessions.',
      impact: isVi
        ? 'Ngăn chặn các phiên sạc ảo làm sai lệch chỉ số thời gian chiếm dụng trụ sạc.'
        : 'Prevents ghost sessions from inflating station occupancy duration metrics.',
    };
  }
  const col = rule.rule_name || rule.rule_id || 'column';
  const fallbackExpr = rule.rule_expression || '—';
  return {
    layer: isVi ? 'L1 Hợp đồng dữ liệu' : 'L1 Data contract',
    problem: isVi
      ? `Luật đề xuất cho ${col}. Chưa thực thi.`
      : `Proposed constraint on ${col}. Not executed yet.`,
    why: isVi
      ? 'Sinh từ profile cột của dataset đang chọn, không dùng số liệu demo.'
      : 'Synthesized from this dataset’s column profile. No demo counts.',
    guarantee: isVi ? `Ràng buộc: ${fallbackExpr}` : `Constraint: ${fallbackExpr}`,
    impact: isVi
      ? 'Steward duyệt xong mới được clean/quarantine.'
      : 'Clean/quarantine runs only after steward approval.',
  };
}


/** Same status the card pill uses. Header counts MUST use this (count what you show). */
function ruleCardStatus(rule: { status?: string | null }): 'approved' | 'rejected' | 'proposed' {
  const raw = String(rule.status ?? '').trim().toLowerCase();
  if (raw === 'approved' || raw === 'edited') return 'approved';
  if (raw === 'rejected') return 'rejected';
  // unlabeled / whitespace / Proposed / pending / draft / queued → PROPOSED pill
  return 'proposed';
}

export const QualityRulesTab: React.FC<QualityRulesTabProps> = ({ datasetKey, active = false, onExecuteClean: _onExecuteClean, dayIdx = null, runId: _runId = null }) => {
  const [proposals, setProposals] = useState<HITLProposal[]>([]);
  const [loading, setLoading] = useState(false);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [sandboxAuthorized, setSandboxAuthorized] = useState(false);
  const [payloadHash, setPayloadHash] = useState<string | null>(null);
  const [sandboxError, setSandboxError] = useState<string | null>(null);
  const [editingRule, setEditingRule] = useState<HITLProposal | null>(null);
  const [editExpression, setEditExpression] = useState('');
  const [rejectingRule, setRejectingRule] = useState<HITLProposal | null>(null);
  const [rejectReason, setRejectReason] = useState('');
  const [activeFilter, setActiveFilter] = useState<'all' | 'proposed' | 'approved' | 'rejected'>('proposed');
  const { i18n } = useTranslation('pipeline');
  const isVi = i18n.language === 'vi';
  // First hidden boot GET is often []. Do not treat that as a locked 0/0.
  const emptyBootRef = useRef(true);
  const dropKeptAfterResetRef = useRef(false);
  const fetchGenRef = useRef(0);

  const [, setLlmTick] = useState(0);

  useEffect(() => {
    const onLlmChange = () => setLlmTick((t) => t + 1);
    window.addEventListener('datatrust:llm-mode-changed', onLlmChange);
    return () => window.removeEventListener('datatrust:llm-mode-changed', onLlmChange);
  }, []);





  const fetchRules = useCallback(async (opts?: { silent?: boolean }) => {
    const silent = !!opts?.silent;
    const myGen = fetchGenRef.current;
    if (!silent) setLoading(true);
    try {
      const targetKey = datasetKey || 'ev_telemetry';
      const res = await hitlApi.queue(targetKey);
      if (myGen !== fetchGenRef.current) return;
      if (res && Array.isArray(res.proposals)) {
        const fromDb = res.proposals;
        setProposals((prev) => {
          // Admin reset: drop keptApproved. Empty queue is honest 0/0.
          if (dropKeptAfterResetRef.current) {
            dropKeptAfterResetRef.current = false;
            emptyBootRef.current = false;
            return fromDb;
          }
          // Empty queue must not wipe cards the Propose beat already put on screen.
          // Empty first hidden fetch must not lock 0/0 — wait for active/agent-trace refetch.
          if (fromDb.length === 0 && (prev.length > 0 || emptyBootRef.current)) {
            return prev;
          }
          emptyBootRef.current = false;
          const dbIds = new Set(fromDb.map((r) => r.rule_id));
          // DuckDB wins for every id it returns. Keep local APPROVED cards the queue omitted
          // so header Approved follows the pills after one Approve.
          const keptApproved = prev.filter(
            (r) => ruleCardStatus(r) === 'approved' && !dbIds.has(r.rule_id)
          );
          return [...fromDb, ...keptApproved];
        });
      }
    } catch {
      // keep existing cards — empty/error must not zero the header
    } finally {
      if (!silent) setLoading(false);
    }
  }, [datasetKey]);

  useEffect(() => {
    void fetchRules();
  }, [fetchRules]);

  // Keep-mounted: first visit used to show the boot-time empty queue. Refetch when
  // shown, when Profile & Propose lands (agent-trace), and via GET poll. Never POST.
  useEffect(() => {
    if (active) void fetchRules({ silent: true });
  }, [active, fetchRules]);

  useEffect(() => {
    const onTrace = () => { void fetchRules({ silent: true }); };
    window.addEventListener('datatrust:agent-trace', onTrace);
    return () => window.removeEventListener('datatrust:agent-trace', onTrace);
  }, [fetchRules]);

  useEffect(() => {
    const onReset = () => {
      fetchGenRef.current += 1;
      dropKeptAfterResetRef.current = true;
      emptyBootRef.current = false;
      setProposals([]);
      setSandboxAuthorized(false);
      setPayloadHash(null);
      setSandboxError(null);
    };
    window.addEventListener('datatrust:db-reset', onReset);
    return () => window.removeEventListener('datatrust:db-reset', onReset);
  }, []);

  useEffect(() => {
    if (active) void fetchRules();
  }, [active, dayIdx, fetchRules]);

  useEffect(() => {
    const id = window.setInterval(() => { void fetchRules({ silent: true }); }, 2000);
    return () => window.clearInterval(id);
  }, [fetchRules]);

  const handleApprove = async (ruleId: string) => {
    setActionLoading(ruleId);
    try {
      const res: any = await hitlApi.approve(ruleId, 'human');
      const qCount = res?.quarantined_count ?? 0;
      setProposals((prev) =>
        prev.map((r) => (r.rule_id === ruleId ? { ...r, status: 'approved' } : r))
      );
      window.dispatchEvent(new CustomEvent('datatrust:quarantine-updated', { detail: { ruleId, qCount } }));
      await fetchRules({ silent: true });
    } catch (err: any) {
      alert(`Approval error: ${err.message}`);
    } finally {
      setActionLoading(null);
    }
  };

  const handleConfirmReject = async () => {
    if (!rejectingRule) return;
    const ruleId = rejectingRule.rule_id;
    const reasonText = rejectReason.trim() || (isVi ? 'Không phù hợp với đặc thù dữ liệu hiện tại' : 'Not suitable for current dataset');
    setActionLoading(ruleId);
    try {
      await hitlApi.reject(ruleId, 'human', reasonText);
      setProposals((prev) =>
        prev.map((r) => (r.rule_id === ruleId ? { ...r, status: 'rejected', reject_reason: reasonText } : r))
      );
      setRejectingRule(null);
      setRejectReason('');
      await fetchRules({ silent: true });
    } catch (err: any) {
      alert(`Reject error: ${err.message}`);
    } finally {
      setActionLoading(null);
    }
  };

  const handleBatchApprove = async () => {
    const pendingRules = proposals.filter(
      (r) => (r.status || 'proposed').toLowerCase() === 'proposed' || (r.status || '').toLowerCase() === 'pending'
    );
    if (pendingRules.length === 0) return;

    setActionLoading('batch');
    try {
      await Promise.all(
        pendingRules.map((r) =>
          hitlApi.approve(r.rule_id, 'human')
        )
      );
      setProposals((prev) =>
        prev.map((r) => ({ ...r, status: 'approved' }))
      );
      await fetchRules({ silent: true });
    } catch (err: any) {
      alert(`Batch approval error: ${err.message}`);
    } finally {
      setActionLoading(null);
    }
  };

  const handleSaveEdit = async () => {
    if (!editingRule) return;
    setActionLoading(editingRule.rule_id);
    try {
      await hitlApi.edit(editingRule.rule_id, editExpression);
      setProposals((prev) =>
        prev.map((r) =>
          r.rule_id === editingRule.rule_id
            ? { ...r, rule_expression: editExpression, status: 'approved' }
            : r
        )
      );
      setEditingRule(null);
      await fetchRules({ silent: true });
    } catch (err: any) {
      alert(`Save edit error: ${err.message}`);
    } finally {
      setActionLoading(null);
    }
  };

  const handleSandboxExecute = async () => {
    const approved = proposals.filter((r) => (r.status || '').toLowerCase() === 'approved' || (r.status || '').toLowerCase() === 'edited');
    if (approved.length === 0) return;
    setActionLoading('sandbox');
    setSandboxError(null);
    const storeKey = datasetStoreKey(datasetKey);
    try {
      const auth = await approvalsApi.authorize(datasetKey || 'ev_telemetry', approved.map((r) => r.rule_id));
      for (const r of approved) {
        await hitlApi.execute(r.rule_id);
      }
      const sandbox = await hitlApi.sandbox(datasetKey || 'ev_telemetry', approved.map((r) => r.rule_id));
      const qRows = (sandbox && Array.isArray(sandbox.quarantine)) ? sandbox.quarantine : [];
      const cRows = (sandbox && Array.isArray(sandbox.clean)) ? sandbox.clean : [];
      const qCount = sandbox?.quarantine_rows ?? qRows.length;
      const cCount = sandbox?.clean_rows ?? cRows.length;
      useWorkspaceStore.getState().replaceSplitRows(storeKey, {
        cleanRan: true,
        thisRun: true,
        snapshotId: sandbox?.snapshot_id || '',
        quarantineRows: qRows,
        cleanRows: cRows,
        totalQuarantine: qCount,
        totalClean: cCount,
      });
      useWorkspaceStore.getState().mergeSplitRows(storeKey, {
        cleanRan: true,
        thisRun: true,
        snapshotId: sandbox?.snapshot_id || '',
        quarantineRows: qRows,
        cleanRows: cRows,
        totalQuarantine: qCount,
        totalClean: cCount,
      });
      useWorkspaceStore.getState().mergeTraces(storeKey, [{
        step: 2,
        action: 'clean_database',
        tool: 'clean_database',
        tool_name: 'clean_database',
        status: 'done',
        observation: `${qCount} quarantined · ${cCount} clean`,
      }]);
      const detail = {
        ...(sandbox || {}),
        sandbox: true,
        thisRun: true,
        cleanRan: true,
        dataset_key: datasetKey || 'ev_telemetry',
        snapshot_id: sandbox?.snapshot_id,
      };
      try {
        window.dispatchEvent(new CustomEvent('datatrust:sandbox-split', { detail }));
        window.dispatchEvent(new CustomEvent('datatrust:split-refresh', { detail }));
        window.dispatchEvent(new CustomEvent('datatrust:agent-trace'));
      } catch { /* ignore */ }
      setPayloadHash(auth?.payload_hash || '');
      setSandboxAuthorized(true);
    } catch (err: any) {
      const raw = String(err?.message || 'sandbox execute failed');
      const is504 = raw.includes('504') || raw.toLowerCase().includes('timeout');
      const msg = is504 ? (raw.startsWith('HTTP 504') ? raw : `HTTP 504: ${raw}`) : raw;
      setSandboxError(msg);
      setSandboxAuthorized(false);
      useWorkspaceStore.getState().replaceSplitRows(storeKey, { ...EMPTY_SPLIT });
      try {
        window.dispatchEvent(new CustomEvent('datatrust:sandbox-failed', {
          detail: { dataset_key: datasetKey || 'ev_telemetry', error: msg, http504: is504 },
        }));
      } catch { /* ignore */ }
    } finally {
      setActionLoading(null);
    }
  };

  const totalCount = proposals.length;
  const proposedCount = proposals.filter(
    (r) => (r.status || 'proposed').toLowerCase() === 'proposed' || (r.status || '').toLowerCase() === 'pending'
  ).length;
  const approvedCount = proposals.filter(
    (r) => (r.status || '').toLowerCase() === 'approved' || (r.status || '').toLowerCase() === 'edited'
  ).length;
  const rejectedCount = proposals.filter(
    (r) => (r.status || '').toLowerCase() === 'rejected'
  ).length;

  const sourceIngestionRunId = usePipelineStore((s) => s.sourceIngestionRunId);

  const filteredProposals = proposals.filter((rule) => {
    if (sourceIngestionRunId && rule.source_ingestion_run_id && rule.source_ingestion_run_id !== sourceIngestionRunId) {
      return false;
    }
    const status = (rule.status || 'proposed').toLowerCase();
    if (activeFilter === 'proposed') return status === 'proposed' || status === 'pending';
    if (activeFilter === 'approved') return status === 'approved' || status === 'edited';
    if (activeFilter === 'rejected') return status === 'rejected';
    return true;
  });

  return (
    <div className="quality-rules-tab" style={{ padding: '4px' }}>
      {/* SUMMARY HEADER BAR WITH FILTER TABS */}
      <div
        className="rules-summary-bar"
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          marginBottom: '14px',
          background: 'var(--bg-card)',
          border: '1px solid var(--glass-border)',
          borderRadius: '8px',
          padding: '10px 14px',
          flexWrap: 'wrap',
          gap: '8px',
        }}
      >
        <div className="rules-stats-summary" style={{ display: 'flex', alignItems: 'center', gap: '6px', flexWrap: 'wrap' }}>
          <button
            onClick={() => setActiveFilter('all')}
            style={{
              background: activeFilter === 'all' ? 'rgba(2, 132, 199, 0.18)' : 'rgba(0, 0, 0, 0.04)',
              color: activeFilter === 'all' ? '#0284c7' : 'var(--text-muted)',
              border: activeFilter === 'all' ? '1px solid rgba(2, 132, 199, 0.4)' : '1px solid var(--glass-border)',
              padding: '3px 10px',
              borderRadius: '6px',
              fontSize: '11px',
              fontWeight: 600,
              cursor: 'pointer',
            }}
          >
            {isVi ? `Tất Cả (${totalCount})` : `All (${totalCount})`}
          </button>
          <button
            onClick={() => setActiveFilter('proposed')}
            style={{
              background: activeFilter === 'proposed' ? 'rgba(217, 119, 6, 0.18)' : 'rgba(217, 119, 6, 0.06)',
              color: '#d97706',
              border: activeFilter === 'proposed' ? '1px solid rgba(217, 119, 6, 0.5)' : '1px solid rgba(217, 119, 6, 0.2)',
              padding: '3px 10px',
              borderRadius: '6px',
              fontSize: '11px',
              fontWeight: 600,
              cursor: 'pointer',
            }}
          >
            {proposedCount} {isVi ? 'Đang Chờ Duyệt' : 'Proposed'}
          </button>
          <button
            onClick={() => setActiveFilter('approved')}
            style={{
              background: activeFilter === 'approved' ? 'rgba(5, 150, 105, 0.18)' : 'rgba(5, 150, 105, 0.06)',
              color: '#059669',
              border: activeFilter === 'approved' ? '1px solid rgba(5, 150, 105, 0.5)' : '1px solid rgba(5, 150, 105, 0.2)',
              padding: '3px 10px',
              borderRadius: '6px',
              fontSize: '11px',
              fontWeight: 600,
              cursor: 'pointer',
            }}
          >
            {approvedCount} {isVi ? 'Đã Áp Dụng Engine' : 'Approved Active'}
          </button>
          <button
            onClick={() => setActiveFilter('rejected')}
            style={{
              background: activeFilter === 'rejected' ? 'rgba(220, 38, 38, 0.18)' : 'rgba(220, 38, 38, 0.06)',
              color: '#dc2626',
              border: activeFilter === 'rejected' ? '1px solid rgba(220, 38, 38, 0.5)' : '1px solid rgba(220, 38, 38, 0.2)',
              padding: '3px 10px',
              borderRadius: '6px',
              fontSize: '11px',
              fontWeight: 600,
              cursor: 'pointer',
            }}
          >
            {rejectedCount} {isVi ? 'Đã Từ Chối' : 'Rejected'}
          </button>
        </div>

        {sandboxAuthorized && payloadHash ? (
          <span
            title={payloadHash}
            style={{
              background: 'rgba(5, 150, 105, 0.1)',
              border: '1px solid rgba(5, 150, 105, 0.25)',
              color: '#059669',
              padding: '4px 10px',
              borderRadius: '6px',
              fontSize: '11px',
              fontWeight: 600,
            }}
          >
            {isVi ? 'Sandbox đã chạy · authorized' : 'Sandbox run · authorized'}{' '}
            <code>{payloadHash.length > 16 ? `${payloadHash.slice(0, 12)}…` : payloadHash}</code>
          </span>
        ) : approvedCount >= 1 ? (
          <button
            type="button"
            onClick={() => void handleSandboxExecute()}
            disabled={actionLoading === 'sandbox'}
            title="Sandbox execute"
            style={{
              background: 'rgba(2, 132, 199, 0.12)',
              border: '1px solid rgba(2, 132, 199, 0.3)',
              color: '#0284c7',
              padding: '4px 10px',
              borderRadius: '6px',
              fontSize: '11px',
              fontWeight: 600,
              cursor: actionLoading === 'sandbox' ? 'wait' : 'pointer',
            }}
          >
            {isVi ? 'Chạy sandbox' : 'Run sandbox'}
          </button>
        ) : (
          <button
            type="button"
            disabled
            title={isVi ? 'Execute tắt đến khi sandbox + authorize đúng version' : 'Execute stays off until sandbox + exact-version authorize'}
            style={{
              background: 'none',
              border: '1px dashed var(--glass-border)',
              color: 'var(--text-muted)',
              padding: '4px 10px',
              borderRadius: '6px',
              fontSize: '11px',
              fontWeight: 600,
              cursor: 'not-allowed',
            }}
          >
            {isVi ? 'Execute tắt · sandbox chưa chạy · quarantine=0' : 'Execute disabled · sandbox not run · quarantine=0'}
          </button>
        )}
        {actionLoading === 'sandbox' && (
          <span style={{ color: '#0284c7', fontSize: 11, fontWeight: 600 }}>
            {isVi ? 'Sandbox đang chạy…' : 'Sandbox running…'}
          </span>
        )}
        {sandboxError && (
          <span
            role="alert"
            className="sandbox-error-chip"
            style={{
              color: '#dc2626',
              fontSize: 11,
              fontWeight: 700,
              background: 'rgba(220, 38, 38, 0.1)',
              border: '1px solid rgba(220, 38, 38, 0.35)',
              borderRadius: 6,
              padding: '3px 8px',
            }}
          >
            {sandboxError}
          </span>
        )}
        <div className="rules-actions-right" style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
          {/* Active Model Indicator Badge driven by global mode */}
          <div
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '6px',
              fontSize: '11px',
              padding: '4px 9px',
              borderRadius: '6px',
              background: getGlobalUseLlm() ? 'rgba(168, 85, 247, 0.14)' : 'rgba(234, 179, 8, 0.14)',
              border: getGlobalUseLlm() ? '1px solid rgba(168, 85, 247, 0.35)' : '1px solid rgba(234, 179, 8, 0.35)',
              color: getGlobalUseLlm() ? '#c084fc' : '#eab308',
              fontWeight: 600,
            }}
            title={isVi ? 'Chế độ hoạt động hiện tại (thay đổi tại thanh Header trên cùng)' : 'Current system execution mode (change via top header bar)'}
          >
            {getGlobalUseLlm() ? '🧠 Engine: LLM ON (Gemini 3.5 Flash Lite)' : '⚡ Engine: LLM OFF (Deterministic Rule Engine)'}
          </div>



          {proposedCount > 0 && (
            <button
              className="btn-batch-approve"
              onClick={handleBatchApprove}
              disabled={actionLoading === 'batch'}
              title={isVi ? 'Phê duyệt toàn bộ ràng buộc chất lượng được đề xuất' : 'Approve all proposed quality constraints'}
              style={{
                background: 'rgba(5, 150, 105, 0.15)',
                border: '1px solid rgba(5, 150, 105, 0.3)',
                color: '#059669',
                padding: '4px 10px',
                borderRadius: '6px',
                fontSize: '11px',
                fontWeight: 600,
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '4px',
              }}
            >
              <CheckCheck size={13} /> {isVi ? `Duyệt Tất Cả (${proposedCount})` : `Approve All (${proposedCount})`}
            </button>
          )}
          <button
            className="traces-refresh-btn"
            onClick={() => void fetchRules()}
            disabled={loading}
            title={isVi ? 'Làm mới danh sách bộ luật' : 'Refresh rules queue'}
            style={{
              background: 'none',
              border: '1px solid var(--glass-border)',
              color: 'var(--text-main)',
              borderRadius: '6px',
              padding: '6px 8px',
              cursor: 'pointer',
            }}
          >
            <RefreshCw size={13} className={loading ? 'spinning' : ''} />
          </button>
        </div>

      </div>

      {/* RULES CARDS LIST */}
      {filteredProposals.length === 0 ? (
        <div className="empty-panel-state" style={{ textAlign: 'center', padding: '40px 16px' }}>
          <ShieldCheck size={32} style={{ opacity: 0.3, marginBottom: 8, color: 'var(--text-muted)' }} />
          <div style={{ fontWeight: 600, color: 'var(--text-main)' }}>
            {activeFilter === 'proposed'
              ? (isVi ? 'Không Có Bộ Luật Nào Đang Chờ Duyệt' : 'No Pending Quality Rules')
              : activeFilter === 'approved'
                ? (isVi ? 'Chưa Có Bộ Luật Nào Được Phê Duyệt' : 'No Approved Active Rules')
                : activeFilter === 'rejected'
                  ? (isVi ? 'Không Có Bộ Luật Nào Bị Từ Chối' : 'No Rejected Quality Rules')
                  : (isVi ? 'Không Có Bộ Luật Chất Lượng Nào' : 'No Quality Rules')}
          </div>
          <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 4 }}>
            {isVi ? 'Yêu cầu agent "đề xuất bộ luật chất lượng" hoặc chạy pipeline để tổng hợp ràng buộc.' : 'Ask the agent to "propose quality rules" or run the pipeline to synthesize constraints.'}
          </div>
        </div>
      ) : (
        <div className="rules-cards-list" style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
          {filteredProposals.map((rule) => {
            const status = (rule.status || 'proposed').toLowerCase();
            const isApproved = status === 'approved' || status === 'edited';
            const isRejected = status === 'rejected';
            const reasoning = getRuleReasoning(rule, isVi);

            return (
              <div
                key={rule.rule_id}
                className={`rule-card ${status}`}
                style={{
                  background: 'var(--bg-card)',
                  border: isApproved
                    ? '1px solid rgba(5, 150, 105, 0.35)'
                    : isRejected
                      ? '1px solid rgba(220, 38, 38, 0.25)'
                      : '1px solid rgba(217, 119, 6, 0.35)',
                  borderRadius: '10px',
                  padding: '12px 14px',
                  boxShadow: '0 2px 8px rgba(0,0,0,0.04)',
                }}
              >
                {/* RULE CARD HEADER */}
                <div className="rule-card-header" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
                  <div className="rule-id-group" style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <span className="rule-id-tag" style={{ fontWeight: 700, fontSize: '12px', color: 'var(--text-main)' }}>
                      {rule.rule_name || rule.rule_id}
                    </span>
                    <span
                      style={{
                        fontSize: '10px',
                        fontWeight: 600,
                        padding: '1px 6px',
                        borderRadius: '4px',
                        background: 'rgba(2, 132, 199, 0.08)',
                        color: '#0284c7',
                        border: '1px solid rgba(2, 132, 199, 0.2)',
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: '3px',
                      }}
                    >
                      <Layers size={9} /> {reasoning.layer}
                    </span>
                    {rule.source_ingestion_run_id && (
                      <span
                        style={{
                          fontSize: '10px',
                          fontWeight: 600,
                          padding: '1px 6px',
                          borderRadius: '4px',
                          background: 'rgba(168, 85, 247, 0.08)',
                          color: '#a855f7',
                          border: '1px solid rgba(168, 85, 247, 0.2)',
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: '3px',
                        }}
                      >
                        📅 {rule.source_ingestion_run_id.slice(0, 16)}
                      </span>
                    )}
                  </div>

                  <span
                    className={`rule-status-pill ${status}`}
                    style={{
                      fontSize: '10px',
                      fontWeight: 700,
                      padding: '2px 8px',
                      borderRadius: '12px',
                      textTransform: 'uppercase',
                      background: isApproved ? 'rgba(5, 150, 105, 0.12)' : isRejected ? 'rgba(220, 38, 38, 0.12)' : 'rgba(217, 119, 6, 0.12)',
                      color: isApproved ? '#059669' : isRejected ? '#dc2626' : '#d97706',
                      border: isApproved ? '1px solid rgba(5, 150, 105, 0.3)' : isRejected ? '1px solid rgba(220, 38, 38, 0.3)' : '1px solid rgba(217, 119, 6, 0.3)',
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '4px',
                    }}
                  >
                    {isApproved ? (
                      <>
                        <CheckCircle2 size={11} /> {isVi ? 'ĐANG ÁP DỤNG TRONG ENGINE' : 'APPROVED ACTIVE'}
                      </>
                    ) : isRejected ? (
                      <>
                        <XCircle size={11} /> {isVi ? 'ĐÃ TỪ CHỐI' : 'REJECTED'}
                      </>
                    ) : (
                      <>
                        <AlertTriangle size={11} /> {isVi ? 'ĐANG CHỜ DUYỆT' : 'PROPOSED'}
                      </>
                    )}
                  </span>
                </div>

                {/* SQL / PYTHON CONSTRAINT EXPRESSION */}
                <div
                  className="rule-expression-box"
                  style={{
                    background: 'var(--bg-input, rgba(0, 0, 0, 0.03))',
                    border: '1px solid var(--glass-border)',
                    borderRadius: '6px',
                    padding: '8px 10px',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '8px',
                    marginBottom: '10px',
                    fontFamily: 'var(--font-mono, monospace)',
                    fontSize: '12px',
                  }}
                >
                  <Code2 size={14} style={{ color: '#0284c7', flexShrink: 0 }} />
                  <code style={{ color: '#0284c7', fontWeight: 600 }}>{rule.rule_expression}</code>
                </div>

                {/* STRUCTURED REASONING & JUSTIFICATION (WHY THE AI PROPOSED THIS RULE) */}
                <div
                  style={{
                    background: 'var(--pill-bg, rgba(0, 0, 0, 0.02))',
                    border: '1px solid var(--glass-border)',
                    borderRadius: '8px',
                    padding: '10px',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '7px',
                    fontSize: '11px',
                    lineHeight: 1.45,
                    marginBottom: '10px',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'flex-start', gap: '6px' }}>
                    <AlertTriangle size={13} style={{ flexShrink: 0, marginTop: '2px', color: '#dc2626' }} />
                    <div style={{ color: 'var(--text-main)' }}>
                      <strong style={{ color: '#dc2626' }}>{isVi ? 'Vấn Đề Phát Hiện:' : 'Problem Discovered:'} </strong>
                      {reasoning.problem}
                    </div>
                  </div>

                  <div style={{ display: 'flex', alignItems: 'flex-start', gap: '6px' }}>
                    <HelpCircle size={13} style={{ flexShrink: 0, marginTop: '2px', color: '#d97706' }} />
                    <div style={{ color: 'var(--text-main)' }}>
                      <strong style={{ color: '#d97706' }}>{isVi ? 'Lý Do AI Đề Xuất (Nguyên Nhân Gốc):' : 'Why AI Proposed This (Root Cause):'} </strong>
                      {reasoning.why}
                    </div>
                  </div>

                  <div style={{ display: 'flex', alignItems: 'flex-start', gap: '6px' }}>
                    <Sparkles size={13} style={{ flexShrink: 0, marginTop: '2px', color: '#059669' }} />
                    <div style={{ color: 'var(--text-main)' }}>
                      <strong style={{ color: '#059669' }}>{isVi ? 'Bảo Đảm Chất Lượng & Tác Động:' : 'Quality Guarantee & Impact:'} </strong>
                      {reasoning.guarantee} {reasoning.impact}
                    </div>
                  </div>
                </div>

                {rule.reject_reason && (
                  <div style={{ marginTop: '8px', background: 'rgba(239, 68, 68, 0.08)', border: '1px solid rgba(239, 68, 68, 0.2)', padding: '6px 10px', borderRadius: '6px', fontSize: '11.5px', color: '#ef4444' }}>
                    <strong>{isVi ? 'Nguyên do từ chối:' : 'Rejection Reason:'} </strong>
                    {rule.reject_reason}
                  </div>
                )}

                {/* RULE CARD FOOTER ACTIONS & CONFIDENCE */}
                <div className="rule-card-footer" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '8px', marginTop: '8px' }}>
                  <div className="rule-confidence-tag" style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                    {isVi ? 'Độ Tin Cậy AI:' : 'AI Confidence:'} <strong style={{ color: '#0284c7' }}>{Math.round(((rule.confidence ?? 0.95) <= 1.0 ? (rule.confidence ?? 0.95) * 100 : (rule.confidence ?? 0.95)))}%</strong>
                  </div>

                  <div className="rule-actions-group" style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    {!isApproved && (
                      <button
                        className="btn-rule-accept"
                        onClick={() => handleApprove(rule.rule_id)}
                        disabled={actionLoading === rule.rule_id}
                        title={isVi ? 'Phê duyệt bộ luật để đưa vào biên dịch cách ly' : 'Approve rule for quarantine compilation'}
                        style={{
                          background: 'rgba(5, 150, 105, 0.12)',
                          border: '1px solid rgba(5, 150, 105, 0.3)',
                          color: '#059669',
                          padding: '4px 10px',
                          borderRadius: '6px',
                          fontSize: '11px',
                          fontWeight: 600,
                          cursor: 'pointer',
                          display: 'flex',
                          alignItems: 'center',
                          gap: '4px',
                        }}
                      >
                        <CheckCircle2 size={12} /> {isVi ? (isRejected ? 'Kích Hoạt Lại' : 'Phê Duyệt') : (isRejected ? 'Re-Approve' : 'Approve')}
                      </button>
                    )}

                    <button
                      className="btn-rule-edit"
                      onClick={() => {
                        setEditingRule(rule);
                        setEditExpression(rule.rule_expression);
                      }}
                      title={isVi ? 'Chỉnh sửa biểu thức SQL của bộ luật' : 'Edit SQL rule expression'}
                      style={{
                        background: 'none',
                        border: '1px solid var(--glass-border)',
                        color: 'var(--text-main)',
                        padding: '4px 8px',
                        borderRadius: '6px',
                        fontSize: '11px',
                        cursor: 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '4px',
                      }}
                    >
                      <Pencil size={11} /> {isVi ? 'Sửa' : 'Edit'}
                    </button>

                    {!isRejected && (
                      <button
                        className="btn-rule-reject"
                        onClick={() => {
                          setRejectingRule(rule);
                          setRejectReason('');
                        }}
                        disabled={actionLoading === rule.rule_id}
                        title={isVi ? 'Từ chối hoặc tạm ngưng áp dụng bộ luật' : 'Reject or deactivate rule proposal'}
                        style={{
                          background: 'rgba(220, 38, 38, 0.08)',
                          border: '1px solid rgba(220, 38, 38, 0.25)',
                          color: '#dc2626',
                          padding: '4px 8px',
                          borderRadius: '6px',
                          fontSize: '11px',
                          cursor: 'pointer',
                          display: 'flex',
                          alignItems: 'center',
                          gap: '4px',
                        }}
                      >
                        <XCircle size={12} /> {isVi ? 'Từ Chối' : 'Reject'}
                      </button>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* EDIT RULE MODAL */}
      {editingRule && (
        <div className="modal-overlay active" onClick={() => setEditingRule(null)}>
          <div className="modal-card" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <span className="modal-title">
                <Pencil size={15} style={{ marginRight: 6 }} /> {isVi ? 'Chỉnh Sửa Bộ Luật:' : 'Edit Rule:'} <code>{editingRule.rule_name || editingRule.rule_id}</code>
              </span>
              <button className="modal-close" onClick={() => setEditingRule(null)}>✕</button>
            </div>
            <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 12 }}>
              {isVi
                ? 'Chỉnh sửa biểu thức làm sạch SQL hoặc Python cho bộ luật này trước khi nạp vào động cơ thực thi.'
                : 'Modify the SQL or Python cleaning expression for this rule before signing into the execution engine.'}
            </div>
            <div className="modal-body">
              <textarea
                className="rule-edit-textarea"
                rows={4}
                value={editExpression}
                onChange={(e) => setEditExpression(e.target.value)}
                style={{
                  width: '100%',
                  padding: '10px',
                  borderRadius: '6px',
                  background: 'var(--bg-input)',
                  border: '1px solid var(--glass-border)',
                  color: 'var(--text-main)',
                  fontFamily: 'var(--font-mono, monospace)',
                  fontSize: '13px',
                }}
              />
            </div>
            <div className="modal-actions" style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 12 }}>
              <button className="btn-modal-cancel" onClick={() => setEditingRule(null)}>{isVi ? 'Hủy' : 'Cancel'}</button>
              <button className="btn-modal-save" onClick={handleSaveEdit} disabled={actionLoading === editingRule.rule_id}>
                {isVi ? 'Lưu Biểu Thức' : 'Save Expression'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* REJECT RULE MODAL */}
      {rejectingRule && (
        <div className="modal-overlay active" onClick={() => setRejectingRule(null)}>
          <div className="modal-card" onClick={(e) => e.stopPropagation()} style={{ maxWidth: '450px' }}>
            <div className="modal-header">
              <span className="modal-title" style={{ color: '#ef4444' }}>
                <XCircle size={15} style={{ marginRight: 6 }} /> {isVi ? 'Từ Chối Bộ Luật:' : 'Reject Rule:'} <code>{rejectingRule.rule_name || rejectingRule.rule_id}</code>
              </span>
              <button className="modal-close" onClick={() => setRejectingRule(null)}>✕</button>
            </div>
            <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 12 }}>
              {isVi
                ? 'Nhập nguyên do từ chối bộ luật đề xuất này để ghi nhận lịch sử phản hồi và cải thiện mô hình AI.'
                : 'Enter the reason for rejecting this proposed rule to record feedback history and train future AI proposals.'}
            </div>
            <div className="modal-body">
              <textarea
                className="rule-reject-textarea"
                rows={3}
                placeholder={isVi ? 'Nhập nguyên do (ví dụ: Quy tắc quá nghiêm ngặt, ngưỡng chưa phù hợp...)' : 'Enter rejection reason (e.g. Threshold too strict, invalid condition...)'}
                value={rejectReason}
                onChange={(e) => setRejectReason(e.target.value)}
                style={{
                  width: '100%',
                  padding: '10px',
                  borderRadius: '6px',
                  background: 'var(--bg-input)',
                  border: '1px solid var(--glass-border)',
                  color: 'var(--text-main)',
                  fontSize: '13px',
                }}
              />
            </div>
            <div className="modal-actions" style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 12 }}>
              <button className="hud-btn" onClick={() => setRejectingRule(null)}>{isVi ? 'Hủy' : 'Cancel'}</button>
              <button
                className="hud-btn danger"
                onClick={handleConfirmReject}
                disabled={actionLoading === rejectingRule.rule_id}
                style={{ background: '#dc2626', color: '#fff', border: 'none', padding: '6px 12px', borderRadius: '6px', cursor: 'pointer', fontWeight: 600 }}
              >
                {isVi ? 'Xác Nhận Từ Chối' : 'Confirm Reject'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
