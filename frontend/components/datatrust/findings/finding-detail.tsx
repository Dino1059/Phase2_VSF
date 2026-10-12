'use client';

import { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  X,
  ShieldAlert,
  Sparkles,
  Wand2,
  CheckCircle2,
  ShieldCheck,
  Database,
  History,
  Copy,
  Check,
  Loader2,
  FileText,
  Lock,
  CheckCheck,
  RefreshCw,
  GitFork,
  BookOpen,
  Scale,
  Globe,
  Layers,
  TableProperties,
  AlertTriangle,
  ArrowRight,
  ExternalLink,
  Workflow,
  AlertOctagon
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import {
  apiBridge,
  type FindingAIAnalysis,
  type FindingDetailData,
  type UnifiedLineageResponse,
  type StructuredRemediationProposal,
} from '@/lib/api-bridge';
import { useAgentStore } from '@/lib/agent-store';

const formatDateTime = (value?: string | null) => {
  if (!value) return '—';
  try {
    return new Intl.DateTimeFormat('vi-VN', {
      dateStyle: 'medium',
      timeStyle: 'medium',
    }).format(new Date(value));
  } catch {
    return value;
  }
};

type TabKey = 'overview' | 'samples' | 'remediation' | 'lineage' | 'rule' | 'history';

interface FindingDetailModalProps {
  findingId: string;
  onClose: () => void;
  onStatusUpdated?: () => void;
}

export function FindingDetailModal({
  findingId,
  onClose,
  onStatusUpdated,
}: FindingDetailModalProps) {
  const navigate = useNavigate();
  const currentRole = useAgentStore((s) => s.currentRole);
  const isAuditor = currentRole === 'auditor';

  const [detail, setDetail] = useState<FindingDetailData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<TabKey>('overview');
  const [copiedIndex, setCopiedIndex] = useState<number | null>(null);
  const [actionSuccessMsg, setActionSuccessMsg] = useState<string | null>(null);
  const [isUpdatingStatus, setIsUpdatingStatus] = useState(false);
  const [aiAnalysis, setAIAnalysis] = useState<FindingAIAnalysis | null>(null);
  const [isAILoading, setIsAILoading] = useState(false);
  const [aiActionError, setAIActionError] = useState<string | null>(null);
  const [remediationDecision, setRemediationDecision] = useState<'approve' | 'reject' | null>(null);
  const [decisionComment, setDecisionComment] = useState('');
  const [isDeciding, setIsDeciding] = useState(false);

  // Remediation / Override Sub-modal
  const [showOverrideModal, setShowOverrideModal] = useState(false);
  const [overrideJustification, setOverrideJustification] = useState('');
  const [showRemediateModal, setShowRemediateModal] = useState(false);
  const [cleanedPayloadStr, setCleanedPayloadStr] = useState('');

  // Structured Quarantine Remediation States (Evidence-or-Abstain)
  const [structuredProposal, setStructuredProposal] = useState<StructuredRemediationProposal | null>(null);
  const [isProposalLoading, setIsProposalLoading] = useState(false);
  const [isDryRunning, setIsDryRunning] = useState(false);
  const [isExecutingTransaction, setIsExecutingTransaction] = useState(false);
  const [selectedOperation, setSelectedOperation] = useState('MASK_PHONE');
  const [operationParams, setOperationParams] = useState<Record<string, any>>({ prefix_len: 3, suffix_len: 2, mask_char: '*' });
  const [rejectReasonInput, setRejectReasonInput] = useState('');
  const [showRejectInput, setShowRejectInput] = useState(false);

  const loadProposal = useCallback(async () => {
    if (!findingId) return;
    setIsProposalLoading(true);
    try {
      const prop = await apiBridge.fetchRemediationProposalForFinding(findingId);
      setStructuredProposal(prop);
      if (prop.operation_id) setSelectedOperation(prop.operation_id);
      if (prop.params) setOperationParams(prop.params);
    } catch {
      // no proposal or error
    } finally {
      setIsProposalLoading(false);
    }
  }, [findingId]);

  useEffect(() => {
    if (activeTab === 'remediation') {
      loadProposal();
    }
  }, [activeTab, loadProposal]);

  const handleRunDryRun = async () => {
    if (!structuredProposal) return;
    setIsDryRunning(true);
    setAIActionError(null);
    try {
      const res = await apiBridge.runDryRunForProposal(structuredProposal.proposal_id);
      setActionSuccessMsg(`Mô phỏng Dry-Run thành công (${res.execution_time_ms}ms) — ${res.actual_rows}/${res.expected_rows} dòng.`);
      await loadProposal();
    } catch (err: any) {
      setAIActionError(err.message || 'Lỗi chạy Dry-Run');
    } finally {
      setIsDryRunning(false);
    }
  };

  const handleApplyParams = async () => {
    if (!structuredProposal) return;
    setIsProposalLoading(true);
    setAIActionError(null);
    try {
      const updated = await apiBridge.updateProposalParams(structuredProposal.proposal_id, operationParams, selectedOperation);
      setStructuredProposal(updated);
      setActionSuccessMsg(`Đã cập nhật tham số (v${updated.version})! Trạng thái đặt về DRAFT. Đang chạy lại Dry-Run...`);
      await apiBridge.runDryRunForProposal(updated.proposal_id);
      await loadProposal();
    } catch (err: any) {
      setAIActionError(err.message || 'Lỗi cập nhật tham số');
    } finally {
      setIsProposalLoading(false);
    }
  };

  const handleSubmitForReview = async () => {
    if (!structuredProposal) return;
    try {
      const updated = await apiBridge.submitProposalForReview(structuredProposal.proposal_id);
      setStructuredProposal(updated);
      setActionSuccessMsg('Đã chuyển đề xuất sang trạng thái Chờ Phê Duyệt (PENDING_APPROVAL).');
    } catch (err: any) {
      setAIActionError(err.message || 'Lỗi gửi phê duyệt');
    }
  };

  const handleApproveProposal = async () => {
    if (!structuredProposal) return;
    try {
      const updated = await apiBridge.approveStructuredProposal(structuredProposal.proposal_id, decisionComment);
      setStructuredProposal(updated);
      setActionSuccessMsg('Đã phê duyệt đề xuất thành công! Bạn có thể thực thi Transaction ngay.');
    } catch (err: any) {
      setAIActionError(err.message || 'Lỗi phê duyệt đề xuất');
    }
  };

  const handleRejectProposal = async () => {
    if (!structuredProposal || !rejectReasonInput.trim()) {
      alert('Vui lòng nhập lý do từ chối.');
      return;
    }
    try {
      const updated = await apiBridge.rejectStructuredProposal(structuredProposal.proposal_id, rejectReasonInput);
      setStructuredProposal(updated);
      setShowRejectInput(false);
      setActionSuccessMsg('Đã từ chối đề xuất xử lý cách ly.');
    } catch (err: any) {
      setAIActionError(err.message || 'Lỗi từ chối');
    }
  };

  const handleExecuteTransaction = async () => {
    if (!structuredProposal) return;
    setIsExecutingTransaction(true);
    setAIActionError(null);
    try {
      const res = await apiBridge.executeStructuredRemediation(structuredProposal.proposal_id);
      setActionSuccessMsg(`Thực thi thành công! ${res.affected_count} bản ghi đã chuyển sang Silver & đánh dấu REMEDIATED.`);
      await loadProposal();
      await loadDetail();
      onStatusUpdated?.();
    } catch (err: any) {
      setAIActionError(err.message || 'Lỗi thực thi Transaction');
    } finally {
      setIsExecutingTransaction(false);
    }
  };

  const loadDetail = useCallback(async () => {
    setLoading(true);
    try {
      const data = await apiBridge.fetchFindingDetail(findingId);
      setDetail(data);
      if (data.sample_records && data.sample_records.length > 0) {
        setCleanedPayloadStr(JSON.stringify(data.sample_records[0].raw_record_json, null, 2));
      }
      setError(null);
      try {
        setAIAnalysis(await apiBridge.getFindingAIAnalysis(findingId));
      } catch {
        setAIAnalysis(null);
      }
    } catch (err: any) {
      setError(err.message || 'Không thể nạp chi tiết Finding');
    } finally {
      setLoading(false);
    }
  }, [findingId]);

  useEffect(() => {
    loadDetail();
  }, [loadDetail]);

  const copyToClipboard = (text: string, idx: number) => {
    navigator.clipboard.writeText(text);
    setCopiedIndex(idx);
    setTimeout(() => setCopiedIndex(null), 2000);
  };

  // AI analysis
  const handleAskAIExplain = async () => {
    if (!detail) return;
    setIsAILoading(true);
    setAIActionError(null);
    try {
      const res = await apiBridge.requestFindingAIExplanation(detail.finding_id);
      setAIAnalysis(res);
      setActiveTab('overview');
      setActionSuccessMsg('AI đã hoàn tất phân tích nguyên nhân gốc rễ và khuyến nghị.');
    } catch (err: any) {
      setAIActionError(err.message || 'Không thể yêu cầu AI phân tích Finding.');
    } finally {
      setIsAILoading(false);
    }
  };

  const handleRemediationDecision = async () => {
    if (!detail || !remediationDecision) return;
    setIsDeciding(true);
    setAIActionError(null);
    try {
      const analysis = remediationDecision === 'approve'
        ? await apiBridge.approveFindingRemediation(detail.finding_id, decisionComment)
        : await apiBridge.rejectFindingRemediation(detail.finding_id, decisionComment);
      setAIAnalysis(analysis);
      const approved = remediationDecision === 'approve';
      setRemediationDecision(null);
      setDecisionComment('');
      setActionSuccessMsg(approved
        ? 'Đã phê duyệt đề xuất — đang chờ bước thực thi riêng.'
        : 'Đã từ chối đề xuất remediation.');
    } catch (err: any) {
      setAIActionError(err.message || 'Không thể ghi nhận quyết định remediation.');
    } finally {
      setIsDeciding(false);
    }
  };

  // Remediate & Reprocess
  const handleExecuteRemediate = async () => {
    if (isAuditor || !detail) return;
    if (!detail.sample_records || detail.sample_records.length === 0) {
      alert('Không có bản ghi cách ly nào để khắc phục.');
      return;
    }
    try {
      const qId = detail.sample_records[0].quarantine_id;
      const parsed = JSON.parse(cleanedPayloadStr);
      await apiBridge.reprocessQuarantine(qId, parsed, 'DataTrust Admin', 'ADMIN');
      await apiBridge.updateFindingStatus(detail.finding_id, 'REMEDIATED', 'Đã khắc phục bản ghi dữ liệu');
      setShowRemediateModal(false);
      setActionSuccessMsg('Đã khắc phục và cập nhật trạng thái REMEDIATED thành công!');
      loadDetail();
      onStatusUpdated?.();
    } catch (err: any) {
      alert(`Lỗi khắc phục: ${err.message}`);
    }
  };

  // Audit Override
  const handleExecuteOverride = async () => {
    if (isAuditor || !detail) return;
    if (!overrideJustification.trim()) {
      alert('Vui lòng nhập giải trình kiểm toán bắt buộc.');
      return;
    }
    try {
      if (detail.sample_records && detail.sample_records.length > 0) {
        const qId = detail.sample_records[0].quarantine_id;
        await apiBridge.overrideQuarantine(qId, overrideJustification, 'DataTrust Admin', 'ADMIN');
      }
      await apiBridge.updateFindingStatus(detail.finding_id, 'OVERRIDDEN', overrideJustification);
      setShowOverrideModal(false);
      setActionSuccessMsg('Đã phê duyệt ngoại lệ OVERRIDDEN kèm giải trình kiểm toán!');
      loadDetail();
      onStatusUpdated?.();
    } catch (err: any) {
      alert(`Lỗi ngoại lệ: ${err.message}`);
    }
  };

  // Toggle Status
  const handleToggleStatus = async () => {
    if (isAuditor || !detail) return;
    setIsUpdatingStatus(true);
    try {
      const targetStatus = detail.status === 'OPEN' ? 'IN_REVIEW' : 'RESOLVED';
      await apiBridge.updateFindingStatus(detail.finding_id, targetStatus, 'Cập nhật bởi Admin');
      setActionSuccessMsg(`Đã cập nhật trạng thái Finding thành: ${targetStatus}`);
      loadDetail();
      onStatusUpdated?.();
    } catch (err: any) {
      alert(`Lỗi cập nhật: ${err.message}`);
    } finally {
      setIsUpdatingStatus(false);
    }
  };

  const [findingLineage, setFindingLineage] = useState<UnifiedLineageResponse | null>(null);
  const [isLineageLoading, setIsLineageLoading] = useState(false);

  useEffect(() => {
    if (activeTab === 'lineage' && !findingLineage && findingId) {
      setIsLineageLoading(true);
      apiBridge.fetchFindingLineage(findingId)
        .then(setFindingLineage)
        .catch(() => {})
        .finally(() => setIsLineageLoading(false));
    }
  }, [activeTab, findingId, findingLineage]);

  const handleTraceLineage = () => {
    if (!detail) return;
    navigate(`/runs/${encodeURIComponent(detail.run_id)}/lineage?column=${encodeURIComponent(detail.column_name || '')}`);
  };

  const samplesCount = detail?.sample_records?.length || 10;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-xs p-4 sm:p-6 animate-in fade-in duration-200">
      <div
        className="w-full max-w-[1240px] h-[88vh] max-h-[88vh] flex flex-col rounded-3xl border border-slate-200 bg-white shadow-2xl overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        {/* ========================================================================= */}
        {/* 1. HEADER (LIGHT MODE)                                                    */}
        {/* ========================================================================= */}
        <div className="flex items-center justify-between border-b border-slate-100 px-6 py-4.5 bg-white shrink-0">
          <div className="flex items-center gap-3.5 min-w-0">
            <div className="grid size-11 place-items-center rounded-2xl bg-rose-50 border border-rose-100 text-rose-500 shrink-0">
              <ShieldAlert className="size-5.5" />
            </div>
            <div className="min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <h2 className="text-xl font-bold text-slate-900 font-mono tracking-tight">{findingId}</h2>
                {detail && (
                  <>
                    <span
                      className={`px-2.5 py-0.5 rounded-full text-[10px] font-extrabold uppercase tracking-wide border ${
                        detail.severity === 'CRITICAL'
                          ? 'bg-rose-50 text-rose-600 border-rose-100'
                          : detail.severity === 'HIGH'
                          ? 'bg-amber-50 text-amber-600 border-amber-100'
                          : 'bg-sky-50 text-sky-600 border-sky-100'
                      }`}
                    >
                      {detail.severity}
                    </span>
                    <span
                      className="px-2.5 py-0.5 rounded-full text-[10px] font-extrabold uppercase tracking-wide border bg-rose-50/70 text-rose-500 border-rose-100"
                    >
                      {detail.status}
                    </span>
                  </>
                )}
              </div>
              <div className="flex items-center gap-2 text-xs text-slate-500 mt-0.5 flex-wrap">
                <span className="font-medium text-slate-700">{detail?.dataset_id || 'ride_hailing_xanh_sm_trips'}</span>
                <span>•</span>
                <span>
                  Cột: <strong className="font-mono text-slate-800 font-semibold">{detail?.column_name}</strong>
                </span>
                <span>•</span>
                <span>Phát hiện: {formatDateTime(detail?.detected_at)}</span>
              </div>
            </div>
          </div>

          <button
            type="button"
            onClick={onClose}
            className="size-9 rounded-xl grid place-items-center text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors cursor-pointer"
          >
            <X className="size-5" />
          </button>
        </div>

        {/* Action success alert */}
        {actionSuccessMsg && (
          <div className="bg-emerald-50 border-b border-emerald-100 px-6 py-2.5 text-xs text-emerald-800 flex items-center justify-between gap-2 shrink-0">
            <div className="flex items-center gap-2">
              <CheckCircle2 className="size-4 text-emerald-600 shrink-0" />
              <span>{actionSuccessMsg}</span>
            </div>
            <button onClick={() => setActionSuccessMsg(null)} className="text-emerald-600 hover:text-emerald-800 font-bold">✕</button>
          </div>
        )}

        {aiActionError && (
          <div className="bg-rose-50 border-b border-rose-100 px-6 py-2.5 text-xs text-rose-700 flex items-center justify-between gap-3 shrink-0">
            <span>{aiActionError}</span>
            <button onClick={() => setAIActionError(null)} className="text-rose-500 hover:text-rose-700 font-bold">✕</button>
          </div>
        )}

        {isAuditor && (
          <div className="bg-amber-50 border-b border-amber-100 px-6 py-2 text-[11px] text-amber-800 flex items-center gap-2 shrink-0">
            <Lock className="size-3.5 text-amber-600 shrink-0" />
            <span>Chế độ Chỉ đọc (Auditor): Các nút Khắc phục, Ngoại lệ và Đổi trạng thái bị vô hiệu hóa.</span>
          </div>
        )}

        {/* ========================================================================= */}
        {/* 2. MAIN MODAL BODY: 2-COLUMN LAYOUT                                      */}
        {/* ========================================================================= */}
        <div className="flex-1 flex overflow-hidden min-h-0">
          {/* Left Vertical Sidebar Navigation */}
          <aside className="w-60 shrink-0 border-r border-slate-100 p-3.5 space-y-1 bg-slate-50/40 overflow-y-auto h-full">
            <button
              type="button"
              onClick={() => setActiveTab('overview')}
              className={`w-full px-3 py-2.5 text-xs text-left rounded-xl flex items-center gap-2.5 transition-colors cursor-pointer ${
                activeTab === 'overview'
                  ? 'bg-teal-50/80 text-teal-800 font-bold'
                  : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900 font-medium'
              }`}
            >
              <FileText size={15} className={activeTab === 'overview' ? 'text-teal-600' : 'text-slate-400'} />
              <span>Tổng quan</span>
            </button>

            <button
              type="button"
              onClick={() => setActiveTab('samples')}
              className={`w-full px-3 py-2.5 text-xs text-left rounded-xl flex items-center gap-2.5 transition-colors cursor-pointer ${
                activeTab === 'samples'
                  ? 'bg-teal-50/80 text-teal-800 font-bold'
                  : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900 font-medium'
              }`}
            >
              <Database size={15} className={activeTab === 'samples' ? 'text-teal-600' : 'text-slate-400'} />
              <span>Mẫu bản ghi vi phạm ({samplesCount})</span>
            </button>

            <button
              type="button"
              onClick={() => setActiveTab('remediation')}
              className={`w-full px-3 py-2.5 text-xs text-left rounded-xl flex items-center gap-2.5 transition-colors cursor-pointer ${
                activeTab === 'remediation'
                  ? 'bg-teal-50/80 text-teal-800 font-bold'
                  : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900 font-medium'
              }`}
            >
              <Wand2 size={15} className={activeTab === 'remediation' ? 'text-teal-600' : 'text-slate-400'} />
              <span>Phân tích Remediation</span>
            </button>

            <button
              type="button"
              onClick={() => setActiveTab('lineage')}
              className={`w-full px-3 py-2.5 text-xs text-left rounded-xl flex items-center gap-2.5 transition-colors cursor-pointer ${
                activeTab === 'lineage'
                  ? 'bg-teal-50/80 text-teal-800 font-bold'
                  : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900 font-medium'
              }`}
            >
              <GitFork size={15} className={activeTab === 'lineage' ? 'text-teal-600' : 'text-slate-400'} />
              <span>Trace lineage</span>
            </button>

            <button
              type="button"
              onClick={() => setActiveTab('rule')}
              className={`w-full px-3 py-2.5 text-xs text-left rounded-xl flex items-center gap-2.5 transition-colors cursor-pointer ${
                activeTab === 'rule'
                  ? 'bg-teal-50/80 text-teal-800 font-bold'
                  : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900 font-medium'
              }`}
            >
              <ShieldCheck size={15} className={activeTab === 'rule' ? 'text-teal-600' : 'text-slate-400'} />
              <span>Định nghĩa Quy tắc</span>
            </button>

            <button
              type="button"
              onClick={() => setActiveTab('history')}
              className={`w-full px-3 py-2.5 text-xs text-left rounded-xl flex items-center gap-2.5 transition-colors cursor-pointer ${
                activeTab === 'history'
                  ? 'bg-teal-50/80 text-teal-800 font-bold'
                  : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900 font-medium'
              }`}
            >
              <History size={15} className={activeTab === 'history' ? 'text-teal-600' : 'text-slate-400'} />
              <span>Lịch sử Kiểm toán</span>
            </button>
          </aside>

          {/* Right Main Pane */}
          <main className="flex-1 flex flex-col overflow-hidden min-w-0 min-h-0">

            {/* Inner Content Body */}
            <div className="flex-1 overflow-y-auto p-6 space-y-4 min-h-0">
              {loading ? (
                <div className="py-20 text-center text-xs text-slate-400 flex flex-col items-center gap-2.5">
                  <Loader2 className="size-6 animate-spin text-teal-500" />
                  <span>Đang tải thông tin chi tiết từ cơ sở dữ liệu…</span>
                </div>
              ) : error ? (
                <div className="p-4 rounded-2xl bg-rose-50 text-rose-800 text-xs border border-rose-200 flex items-center justify-between">
                  <span>{error}</span>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={loadDetail}
                    className="h-7 text-xs border-rose-300 text-rose-700 hover:bg-rose-100"
                  >
                    Thử lại
                  </Button>
                </div>
              ) : detail ? (
                <>
                  {/* ======================================================= */}
                  {/* TAB 1: OVERVIEW & ROOT CAUSE (EXCLUDING MAP)            */}
                  {/* ======================================================= */}
                  {activeTab === 'overview' && (
                    <div className="space-y-4 text-xs">
                      {/* Reason Card */}
                      <div className="rounded-2xl border border-rose-100 bg-[#fff5f5] p-4.5 space-y-1.5">
                        <span className="text-[11px] font-extrabold uppercase tracking-wider text-rose-600 block">
                          LÝ DO VI PHẠM GHI NHẬN
                        </span>
                        <p className="text-sm font-bold text-slate-900 leading-relaxed">
                          {detail.reason}
                        </p>
                      </div>

                      {/* 3 Governance Cards */}
                      <div className="grid gap-3.5 sm:grid-cols-3">
                        <div className="rounded-2xl border border-slate-200/80 bg-white p-4 space-y-2 shadow-2xs">
                          <div className="flex items-center gap-2.5">
                            <div className="grid size-8.5 place-items-center rounded-xl bg-blue-50 text-blue-600 shrink-0">
                              <BookOpen size={16} />
                            </div>
                            <div className="min-w-0">
                              <span className="text-[11px] font-medium text-slate-500 block truncate">
                                Chính sách áp dụng (Policy)
                              </span>
                              <h4 className="text-xs font-bold text-slate-900 truncate">
                                {detail.policy_name || 'EU GDPR'}
                              </h4>
                            </div>
                          </div>
                          <p className="text-[11px] text-slate-400 font-mono pl-1">
                            Mã chính sách: {detail.policy_id || 'POL-EU-GDPR'}
                          </p>
                        </div>

                        <div className="rounded-2xl border border-slate-200/80 bg-white p-4 space-y-2 shadow-2xs">
                          <div className="flex items-center gap-2.5">
                            <div className="grid size-8.5 place-items-center rounded-xl bg-blue-50 text-blue-600 shrink-0">
                              <Scale size={16} />
                            </div>
                            <div className="min-w-0">
                              <span className="text-[11px] font-medium text-slate-500 block truncate">
                                Căn cứ pháp lý (Law Standard)
                              </span>
                              <h4 className="text-xs font-bold text-slate-900 truncate">
                                {detail.law_ref || 'GDPR Art. 5'}
                              </h4>
                            </div>
                          </div>
                          <p className="text-[11px] text-slate-400 pl-1">
                            Nguyên tắc: Tính chính xác dữ liệu
                          </p>
                        </div>

                        <div className="rounded-2xl border border-slate-200/80 bg-white p-4 space-y-2 shadow-2xs">
                          <div className="flex items-center gap-2.5">
                            <div className="grid size-8.5 place-items-center rounded-xl bg-blue-50 text-blue-600 shrink-0">
                              <Globe size={16} />
                            </div>
                            <div className="min-w-0">
                              <span className="text-[11px] font-medium text-slate-500 block truncate">
                                Phạm vi tài phán (Jurisdiction)
                              </span>
                              <h4 className="text-xs font-bold text-slate-900 truncate">
                                {detail.subject_zone || 'EU'}
                              </h4>
                            </div>
                          </div>
                          <p className="text-[11px] text-slate-400 font-mono pl-1">
                            {detail.jurisdiction_chain && detail.jurisdiction_chain.length > 0
                              ? detail.jurisdiction_chain.join(' → ')
                              : `GLOBAL → ${detail.subject_zone || 'EU'}`}
                          </p>
                        </div>
                      </div>

                      {/* Data Impact Card */}
                      <div className="rounded-2xl border border-slate-200/80 bg-white p-4.5 space-y-3 shadow-2xs">
                        <span className="text-[11px] font-extrabold uppercase tracking-wider text-slate-500 block">
                          TÁC ĐỘNG DỮ LIỆU (IMPACT)
                        </span>

                        <div className="grid gap-4 sm:grid-cols-3 pt-1">
                          {/* Col 1: Quarantined records */}
                          <div className="flex items-center gap-3">
                            <div className="grid size-9 place-items-center rounded-xl bg-rose-50 text-rose-500 shrink-0">
                              <Layers size={17} />
                            </div>
                            <div>
                              <div className="text-xl font-bold font-mono text-rose-600 leading-none">
                                {detail.failed_record_count || 24}
                              </div>
                              <p className="text-xs font-semibold text-slate-800 mt-0.5">
                                bản ghi bị cách ly
                              </p>
                              <p className="text-[10px] text-slate-400">
                                tổng {detail.failed_record_count ? detail.failed_record_count + 9 : 33} bản ghi phát hiện
                              </p>
                            </div>
                          </div>

                          {/* Col 2: Affected dataset */}
                          <div className="flex items-center gap-3">
                            <div className="grid size-9 place-items-center rounded-xl bg-blue-50 text-blue-600 shrink-0">
                              <TableProperties size={17} />
                            </div>
                            <div className="min-w-0">
                              <div className="text-xs font-bold text-slate-900 truncate">
                                {detail.dataset_id}
                              </div>
                              <p className="text-xs text-slate-500 mt-0.5">
                                Dataset bị ảnh hưởng
                              </p>
                              <p className="text-[10px] text-slate-400">
                                Không được đưa vào Silver
                              </p>
                            </div>
                          </div>

                          {/* Col 3: Severity */}
                          <div className="flex items-center gap-3">
                            <div className="grid size-9 place-items-center rounded-xl bg-rose-50 text-rose-600 shrink-0">
                              <AlertTriangle size={17} />
                            </div>
                            <div>
                              <div className="text-xs font-bold text-rose-600 uppercase">
                                {detail.severity}
                              </div>
                              <p className="text-xs text-slate-500 mt-0.5">
                                Mức độ nghiêm trọng
                              </p>
                              <p className="text-[10px] text-slate-400">
                                Cần xử lý trước khi tiếp tục
                              </p>
                            </div>
                          </div>
                        </div>
                      </div>

                      {/* Root Cause Analysis (RCA) - Full Width (Excluding Map as requested) */}
                      <div className="rounded-2xl border border-slate-200/80 bg-white p-5 space-y-4 shadow-2xs">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-2">
                            <div className="grid size-7 place-items-center rounded-lg bg-teal-50 text-teal-600">
                              <Sparkles size={14} />
                            </div>
                            <h4 className="text-xs font-bold text-slate-900 uppercase tracking-wide">
                              Nguyên nhân gốc (RCA)
                            </h4>
                          </div>

                          {aiAnalysis && (
                            <div className="flex items-center gap-2">
                              {aiAnalysis.grounding_level && (
                                <span className={cn(
                                  "rounded-full px-2.5 py-0.5 text-[10px] font-bold border",
                                  aiAnalysis.grounding_level === 'SUPPORTED'
                                    ? "bg-emerald-50 border-emerald-200 text-emerald-800"
                                    : aiAnalysis.grounding_level === 'PARTIAL'
                                    ? "bg-amber-50 border-amber-200 text-amber-800"
                                    : "bg-slate-50 border-slate-200 text-slate-600"
                                )}>
                                  {aiAnalysis.grounding_level === 'SUPPORTED' && '✓ Có bằng chứng (SUPPORTED)'}
                                  {aiAnalysis.grounding_level === 'PARTIAL' && '⚠ Một phần (PARTIAL)'}
                                  {aiAnalysis.grounding_level === 'INSUFFICIENT_EVIDENCE' && 'Ø Thiếu bằng chứng (ABSTAIN)'}
                                </span>
                              )}
                              {aiAnalysis.source_label && (
                                <span className="rounded-full bg-slate-100 border border-slate-200 px-2 py-0.5 text-[10px] font-medium text-slate-600 font-mono">
                                  {aiAnalysis.source_label}
                                </span>
                              )}
                            </div>
                          )}
                        </div>

                        {!aiAnalysis ? (
                          <div className="rounded-xl border border-dashed border-slate-200 bg-slate-50/50 p-6 text-center space-y-3">
                            <p className="text-xs text-slate-600">
                              Chưa có phân tích nguyên nhân gốc rễ (RCA) cho finding này.
                            </p>
                            <p className="text-[11px] text-slate-400">
                              Hệ thống tuân thủ chính sách <strong>Evidence-or-Abstain</strong>: chỉ đưa ra kết luận khi có bằng chứng liên kết từ hồ sơ cách ly (Quarantine).
                            </p>
                            <button
                              type="button"
                              onClick={handleAskAIExplain}
                              disabled={isAILoading}
                              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-teal-600 hover:bg-teal-700 text-white text-xs font-medium shadow-xs disabled:opacity-50 cursor-pointer"
                            >
                              <Sparkles size={13} />
                              {isAILoading ? 'AI đang phân tích...' : 'Yêu cầu AI phân tích'}
                            </button>
                          </div>
                        ) : (
                          <>
                            <p className="text-xs text-slate-700 leading-relaxed">
                              {aiAnalysis.explanation}
                            </p>

                            {aiAnalysis.root_cause && (
                              <div className="rounded-xl border border-teal-100 bg-teal-50/40 p-3.5 space-y-1">
                                <p className="text-[10px] font-bold text-teal-800 uppercase tracking-wide">
                                  Nguyên nhân chính xác định:
                                </p>
                                <p className="text-xs font-semibold text-slate-800">
                                  {aiAnalysis.root_cause}
                                </p>
                              </div>
                            )}

                            {/* AI issues if available */}
                            {aiAnalysis.issues && aiAnalysis.issues.length > 0 && (
                              <div className="mt-3 pt-3 border-t border-slate-100 space-y-2">
                                <p className="text-[11px] font-bold text-slate-500 uppercase tracking-wider">
                                  Vấn đề cụ thể và hướng xử lý đề xuất:
                                </p>
                                {aiAnalysis.issues.map((issue, idx) => (
                                  <div key={idx} className="rounded-xl border border-amber-200/80 bg-amber-50/50 p-3 space-y-1">
                                    <div className="flex items-center gap-2">
                                      <span className="font-mono text-xs font-bold text-amber-900 bg-amber-100 px-1.5 py-0.5 rounded">
                                        {issue.field}
                                      </span>
                                      <span className="font-semibold text-slate-900 text-xs">{issue.issue}</span>
                                    </div>
                                    <p className="text-xs text-slate-600">Nguyên nhân: {issue.likely_cause}</p>
                                    <p className="text-xs font-semibold text-emerald-800">Đề xuất: {issue.suggested_action}</p>
                                  </div>
                                ))}
                              </div>
                            )}
                          </>
                        )}
                      </div>
                    </div>
                  )}

                  {/* ======================================================= */}
                  {/* TAB 2: SAMPLE RECORDS (RAW RECORD JSON VIEW)            */}
                  {/* ======================================================= */}
                  {activeTab === 'samples' && (
                    <div className="space-y-4">
                      <div className="flex items-center justify-between text-xs text-slate-500">
                        <span>
                          Mẫu bản ghi bị cách ly thực tế từ bảng <code className="font-mono text-teal-700 bg-teal-50 px-1.5 py-0.5 rounded">quarantine.records</code>
                        </span>
                        <span>Hiển thị tối đa {samplesCount} bản ghi</span>
                      </div>

                      {(!detail.sample_records || detail.sample_records.length === 0) ? (
                        <div className="p-8 text-center text-xs text-slate-400 rounded-2xl border border-slate-200 bg-slate-50/50">
                          Không có bản ghi cách ly mẫu nào liên kết trực tiếp với Finding này.
                        </div>
                      ) : (
                        <div className="space-y-3">
                          {detail.sample_records.map((rec, idx) => (
                            <div key={rec.quarantine_id} className="rounded-2xl border border-slate-200/90 bg-white p-4.5 text-xs space-y-2.5 shadow-2xs">
                              <div className="flex items-center justify-between pb-2 border-b border-slate-100">
                                <div className="flex items-center gap-2 flex-wrap">
                                  <span className="font-mono font-bold text-teal-700 bg-teal-50 px-2 py-0.5 rounded-md">
                                    Mẫu #{idx + 1}
                                  </span>
                                  <span className="text-slate-500 font-mono text-[11px]">ID: {rec.quarantine_id}</span>
                                  {rec.source_row_pk && (
                                    <span className="bg-slate-100 px-2 py-0.5 rounded text-[10px] font-mono text-slate-600">
                                      PK: {rec.source_row_pk}
                                    </span>
                                  )}
                                </div>
                                <button
                                  type="button"
                                  onClick={() => copyToClipboard(JSON.stringify(rec.raw_record_json, null, 2), idx)}
                                  className="text-slate-500 hover:text-slate-800 flex items-center gap-1.5 text-[11px] font-medium transition-colors cursor-pointer"
                                >
                                  {copiedIndex === idx ? (
                                    <Check className="size-3.5 text-emerald-600" />
                                  ) : (
                                    <Copy className="size-3.5 text-slate-400" />
                                  )}
                                  <span>{copiedIndex === idx ? 'Đã sao chép' : 'Sao chép JSON'}</span>
                                </button>
                              </div>

                              <div className="space-y-1">
                                <span className="text-[10px] text-rose-600 font-bold uppercase tracking-wider">
                                  Lý do cách ly:
                                </span>
                                <p className="text-xs text-rose-700 font-mono bg-rose-50/60 p-2 rounded-lg border border-rose-100">
                                  {rec.violation_reason}
                                </p>
                              </div>

                              <div>
                                <span className="text-[10px] text-slate-500 font-bold uppercase block mb-1.5 tracking-wider">
                                  Raw Record Payload (JSON):
                                </span>
                                <pre className="p-3.5 rounded-xl bg-slate-900 border border-slate-800 font-mono text-[11px] text-slate-200 overflow-x-auto max-h-52 leading-relaxed">
                                  {JSON.stringify(rec.raw_record_json, null, 2)}
                                </pre>
                              </div>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )}

                  {/* ======================================================= */}
                  {/* TAB 3: STRUCTURED QUARANTINE REMEDIATION (HITL)         */}
                  {/* ======================================================= */}
                  {activeTab === 'remediation' && (
                    <div className="space-y-4 text-xs">
                      {isProposalLoading && !structuredProposal ? (
                        <div className="rounded-2xl border border-slate-200 bg-white p-10 text-center shadow-2xs space-y-3">
                          <Loader2 className="size-6 animate-spin text-teal-600 mx-auto" />
                          <p className="font-semibold text-slate-700">Đang nạp đề xuất xử lý cách ly có cấu trúc...</p>
                        </div>
                      ) : structuredProposal ? (
                        <div className="space-y-4">
                          {/* 1. Header Card with Lifecycle State */}
                          <div className="rounded-2xl border border-teal-200/90 bg-white p-5 space-y-4 shadow-2xs">
                            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
                              <div className="flex items-center gap-2.5">
                                <div className="grid size-9 place-items-center rounded-xl bg-teal-50 text-teal-600 shrink-0">
                                  <Wand2 className="size-5" />
                                </div>
                                <div>
                                  <h4 className="font-bold text-slate-900 text-sm">
                                    Đề Xuất Khắc Phục Quarantine Có Cấu Trúc
                                  </h4>
                                  <p className="text-[11px] text-slate-500">
                                    Chính sách Evidence-or-Abstain · Maker-Checker Governance · Bảo toàn bất biến dữ liệu thô
                                  </p>
                                </div>
                              </div>

                              <div className="flex items-center gap-2">
                                <span className={cn(
                                  "rounded-full px-3 py-1 text-[10px] font-bold uppercase tracking-wider border",
                                  structuredProposal.status === 'REMEDIATED'
                                    ? "bg-emerald-50 text-emerald-800 border-emerald-300"
                                    : structuredProposal.status === 'APPROVED'
                                    ? "bg-teal-50 text-teal-800 border-teal-300"
                                    : structuredProposal.status === 'DRY_RUN_PASSED'
                                    ? "bg-blue-50 text-blue-800 border-blue-200"
                                    : structuredProposal.status === 'PENDING_APPROVAL'
                                    ? "bg-purple-50 text-purple-800 border-purple-200"
                                    : structuredProposal.status === 'DRY_RUN_FAILED' || structuredProposal.status === 'ROLLED_BACK'
                                    ? "bg-rose-50 text-rose-800 border-rose-300"
                                    : "bg-amber-50 text-amber-800 border-amber-200"
                                )}>
                                  v{structuredProposal.version} · {structuredProposal.status}
                                </span>
                              </div>
                            </div>

                            {/* Grounding & Target Info */}
                            <div className="grid grid-cols-1 md:grid-cols-3 gap-3 pt-2 border-t border-slate-100 text-[11px]">
                              <div className="rounded-xl bg-slate-50 p-2.5 space-y-0.5">
                                <span className="text-slate-400 font-semibold block uppercase text-[10px]">Căn cứ tiêu chuẩn:</span>
                                <span className="font-semibold text-slate-800">{detail.law_ref || 'Nghị định 13/2023/NĐ-CP Điều 9'}</span>
                                <p className="text-[10px] text-slate-500 font-mono">Finding: {structuredProposal.finding_id}</p>
                              </div>

                              <div className="rounded-xl bg-slate-50 p-2.5 space-y-0.5">
                                <span className="text-slate-400 font-semibold block uppercase text-[10px]">Mục tiêu xử lý:</span>
                                <span className="font-mono font-semibold text-teal-800">{structuredProposal.target.dataset_id}.{structuredProposal.target.column}</span>
                                <p className="text-[10px] text-slate-500 font-mono">Run: {structuredProposal.target.run_id}</p>
                              </div>

                              <div className="rounded-xl bg-slate-50 p-2.5 space-y-0.5">
                                <span className="text-slate-400 font-semibold block uppercase text-[10px]">Quy mô & Rủi ro:</span>
                                <span className="font-semibold text-slate-800">{structuredProposal.expected_rows} bản ghi cách ly</span>
                                <p className="text-[10px] font-mono text-slate-500">Mức rủi ro: {structuredProposal.risk_level}</p>
                              </div>
                            </div>

                            <div className="space-y-1">
                              <span className="text-[10px] font-bold uppercase text-slate-400">Lý do đề xuất:</span>
                              <p className="text-slate-700 leading-relaxed bg-slate-50 p-2.5 rounded-xl border border-slate-200/80">
                                {structuredProposal.reason}
                              </p>
                            </div>
                          </div>

                          {/* 2. Operation & Parameters Form */}
                          <div className="rounded-2xl border border-slate-200/90 bg-white p-5 space-y-4 shadow-2xs">
                            <div className="flex items-center justify-between">
                              <h5 className="font-bold text-slate-900 text-xs uppercase tracking-wide flex items-center gap-1.5">
                                <span>Cấu hình Thao tác (Operation & Parameters)</span>
                              </h5>
                              <span className="text-[11px] text-slate-400">
                                Sửa tham số sẽ tự động tăng version và reset về DRAFT
                              </span>
                            </div>

                            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
                              {/* Operation Selector */}
                              <div>
                                <label className="block text-[11px] font-semibold text-slate-600 mb-1">Thao tác xử lý:</label>
                                <select
                                  disabled={isAuditor || structuredProposal.status === 'REMEDIATED'}
                                  value={selectedOperation}
                                  onChange={(e) => setSelectedOperation(e.target.value)}
                                  className="w-full rounded-xl border border-slate-200 bg-slate-50 p-2 text-xs font-semibold text-slate-800 focus:outline-none focus:border-teal-500"
                                >
                                  <option value="MASK_PHONE">MASK_PHONE (Che mờ số điện thoại)</option>
                                  <option value="MASK_EMAIL">MASK_EMAIL (Che mờ email)</option>
                                  <option value="ROUND_DECIMAL">ROUND_DECIMAL (Làm tròn số thực)</option>
                                  <option value="RECONCILE_LEDGER">RECONCILE_LEDGER (Đối soát sổ cái / IFRS 15)</option>
                                  <option value="CALIBRATE_TELEMETRY">CALIBRATE_TELEMETRY (Kiểm định cảm biến IoT)</option>
                                  <option value="GENERALIZE">GENERALIZE (Khoảng dải k-anonymity)</option>
                                  <option value="HASH_SHA256">HASH_SHA256 (Băm SHA-256 có salt)</option>
                                </select>
                              </div>

                              {/* Dynamic Params */}
                              {(selectedOperation === 'MASK_PHONE' || selectedOperation === 'MASK') && (
                                <>
                                  <div>
                                    <label className="block text-[11px] font-semibold text-slate-600 mb-1">Prefix Length:</label>
                                    <input
                                      type="number"
                                      min={0}
                                      max={10}
                                      disabled={isAuditor || structuredProposal.status === 'REMEDIATED'}
                                      value={operationParams.prefix_len ?? 3}
                                      onChange={(e) => setOperationParams({ ...operationParams, prefix_len: parseInt(e.target.value) || 0 })}
                                      className="w-full rounded-xl border border-slate-200 bg-slate-50 p-2 text-xs font-semibold text-slate-800 focus:outline-none focus:border-teal-500"
                                    />
                                  </div>
                                  <div>
                                    <label className="block text-[11px] font-semibold text-slate-600 mb-1">Suffix Length:</label>
                                    <input
                                      type="number"
                                      min={0}
                                      max={10}
                                      disabled={isAuditor || structuredProposal.status === 'REMEDIATED'}
                                      value={operationParams.suffix_len ?? 2}
                                      onChange={(e) => setOperationParams({ ...operationParams, suffix_len: parseInt(e.target.value) || 0 })}
                                      className="w-full rounded-xl border border-slate-200 bg-slate-50 p-2 text-xs font-semibold text-slate-800 focus:outline-none focus:border-teal-500"
                                    />
                                  </div>
                                  <div>
                                    <label className="block text-[11px] font-semibold text-slate-600 mb-1">Ký tự Mask:</label>
                                    <input
                                      type="text"
                                      maxLength={1}
                                      disabled={isAuditor || structuredProposal.status === 'REMEDIATED'}
                                      value={operationParams.mask_char ?? '*'}
                                      onChange={(e) => setOperationParams({ ...operationParams, mask_char: e.target.value || '*' })}
                                      className="w-full rounded-xl border border-slate-200 bg-slate-50 p-2 text-xs font-semibold text-slate-800 focus:outline-none focus:border-teal-500 font-mono text-center"
                                    />
                                  </div>
                                </>
                              )}

                              {selectedOperation === 'ROUND_DECIMAL' && (
                                <div>
                                  <label className="block text-[11px] font-semibold text-slate-600 mb-1">Số chữ số thập phân (Decimals):</label>
                                  <input
                                    type="number"
                                    min={0}
                                    max={6}
                                    disabled={isAuditor || structuredProposal.status === 'REMEDIATED'}
                                    value={operationParams.decimals ?? 2}
                                    onChange={(e) => setOperationParams({ ...operationParams, decimals: parseInt(e.target.value) || 0 })}
                                    className="w-full rounded-xl border border-slate-200 bg-slate-50 p-2 text-xs font-semibold text-slate-800 focus:outline-none focus:border-teal-500"
                                  />
                                </div>
                              )}

                              {(selectedOperation === 'RECONCILE_LEDGER' || selectedOperation === 'MANUAL_RECONCILIATION') && (
                                <div className="col-span-1 sm:col-span-2 lg:col-span-3">
                                  <label className="block text-[11px] font-semibold text-amber-800 mb-1">Quy trình Đối soát Kế toán:</label>
                                  <select
                                    disabled={isAuditor || structuredProposal.status === 'REMEDIATED'}
                                    value={operationParams.action_type ?? 'FLAG_DISCREPANCY'}
                                    onChange={(e) => setOperationParams({ ...operationParams, action_type: e.target.value })}
                                    className="w-full rounded-xl border border-amber-300 bg-amber-50/60 p-2 text-xs font-semibold text-amber-900 focus:outline-none focus:border-amber-500"
                                  >
                                    <option value="FLAG_DISCREPANCY">Đánh dấu sai lệch sổ cái — Yêu cầu kiểm toán tra soát</option>
                                    <option value="VERIFY_VOUCHER">Đối chiếu hóa đơn / Mã giảm giá (Promo Voucher)</option>
                                    <option value="REFUND_AUDIT">Kiểm tra hoàn tiền / Huỷ chuyến (Refund Log)</option>
                                    <option value="REJECT_RECORD">Hủy bỏ bản ghi ảo khỏi doanh thu (Reject & Discard)</option>
                                  </select>
                                </div>
                              )}

                              {(selectedOperation === 'CALIBRATE_TELEMETRY' || selectedOperation === 'FLAG_HARDWARE_DEFECT') && (
                                <div className="col-span-1 sm:col-span-2 lg:col-span-3">
                                  <label className="block text-[11px] font-semibold text-sky-800 mb-1">Quy trình Kiểm định Phần cứng:</label>
                                  <select
                                    disabled={isAuditor || structuredProposal.status === 'REMEDIATED'}
                                    value={operationParams.action_type ?? 'INSPECT_SENSOR'}
                                    onChange={(e) => setOperationParams({ ...operationParams, action_type: e.target.value })}
                                    className="w-full rounded-xl border border-sky-300 bg-sky-50/60 p-2 text-xs font-semibold text-sky-900 focus:outline-none focus:border-sky-500"
                                  >
                                    <option value="INSPECT_SENSOR">Kiểm định cảm biến vật lý telemetry xe điện</option>
                                    <option value="ISOLATE_SIGNAL">Cách ly tín hiệu dị thường khỏi mô hình huấn luyện</option>
                                  </select>
                                </div>
                              )}
                            </div>

                            {/* Financial Audit Standard Guidance Banner */}
                            {(selectedOperation === 'RECONCILE_LEDGER' || selectedOperation === 'MANUAL_RECONCILIATION') && (
                              <div className="rounded-xl border border-amber-200 bg-amber-50/80 p-3 text-xs text-amber-900 flex items-start gap-2.5">
                                <AlertTriangle className="size-4 text-amber-600 shrink-0 mt-0.5" />
                                <div>
                                  <p className="font-bold text-[11px] uppercase tracking-wide text-amber-800">
                                    Quy định Kiểm toán Tài chính (IFRS 15 & IPO Compliance):
                                  </p>
                                  <p className="text-[11px] text-amber-700 mt-0.5 leading-relaxed">
                                    Dữ liệu cước phí / doanh thu bị sai lệch không được phép che mờ hay tự ý làm tròn/sửa số tiền. Hệ thống bảo toàn số liệu gốc và điều hướng sang quy trình Kế toán đối soát chứng từ thực tế hoặc Hủy bản ghi không hợp lệ.
                                  </p>
                                </div>
                              </div>
                            )}

                            {/* Buttons to apply & run dry run */}
                            {structuredProposal.status !== 'REMEDIATED' && (
                              <div className="flex flex-wrap items-center justify-end gap-2 pt-2 border-t border-slate-100">
                                <Button
                                  size="sm"
                                  variant="outline"
                                  disabled={isAuditor || isProposalLoading || isDryRunning}
                                  onClick={handleApplyParams}
                                  className="text-xs font-medium"
                                >
                                  {isProposalLoading ? <Loader2 className="mr-1 size-3.5 animate-spin" /> : null}
                                  Lưu Tham Số (Tăng Version)
                                </Button>
                                <Button
                                  size="sm"
                                  disabled={isAuditor || isDryRunning}
                                  onClick={handleRunDryRun}
                                  className="bg-teal-600 hover:bg-teal-700 text-white text-xs font-bold gap-1.5"
                                >
                                  {isDryRunning ? <Loader2 className="size-3.5 animate-spin" /> : <Sparkles className="size-3.5" />}
                                  Chạy Thử Mô Phỏng In-Memory (Dry-Run)
                                </Button>
                              </div>
                            )}
                          </div>

                          {/* 3. Dry-Run Simulation & Diff Preview */}
                          {structuredProposal.latest_dry_run && (
                            <div className="rounded-2xl border border-blue-200 bg-white p-5 space-y-4 shadow-2xs">
                              <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
                                <div className="space-y-0.5">
                                  <h5 className="font-bold text-slate-900 text-xs uppercase tracking-wide flex items-center gap-1.5">
                                    <CheckCircle2 className="size-4 text-emerald-600" />
                                    <span>Kết Quả Mô Phỏng Dry-Run (In-Memory Simulation)</span>
                                  </h5>
                                  <p className="text-[11px] text-slate-500">
                                    Thời gian đo: <strong>{structuredProposal.latest_dry_run.execution_time_ms} ms</strong> · 
                                    Số dòng: <strong>{structuredProposal.latest_dry_run.actual_rows}/{structuredProposal.latest_dry_run.expected_rows} dòng</strong> ({structuredProposal.latest_dry_run.row_count_match ? '✓ Khớp 100%' : '⚠ Không khớp'})
                                  </p>
                                </div>

                                <span className="rounded-full bg-blue-50 text-blue-700 border border-blue-200 px-2.5 py-0.5 text-[10px] font-bold">
                                  Bảo đảm không sửa DB · Rollback 100%
                                </span>
                              </div>

                              {/* Diff Table */}
                              <div className="rounded-xl border border-slate-200 overflow-hidden">
                                <table className="w-full text-left text-xs">
                                  <thead className="bg-slate-50 border-b border-slate-200 text-slate-500 font-semibold text-[11px]">
                                    <tr>
                                      <th className="p-2.5 w-10">#</th>
                                      <th className="p-2.5">Quarantine ID</th>
                                      <th className="p-2.5">Trước (Before)</th>
                                      <th className="p-2.5">Sau (After)</th>
                                      <th className="p-2.5">Định dạng</th>
                                      <th className="p-2.5">Hash Đối Chiếu</th>
                                    </tr>
                                  </thead>
                                  <tbody className="divide-y divide-slate-100 font-mono text-[11px]">
                                    {structuredProposal.latest_dry_run.diff_samples.map((sample, idx) => (
                                      <tr key={sample.quarantine_id} className="hover:bg-slate-50/50">
                                        <td className="p-2.5 text-slate-400">{idx + 1}</td>
                                        <td className="p-2.5 text-slate-600 truncate max-w-[120px]" title={sample.quarantine_id}>
                                          {sample.quarantine_id.slice(0, 8)}...
                                        </td>
                                        <td className="p-2.5 text-rose-700 bg-rose-50/30">
                                          {sample.before_preview}
                                          <span className="text-[9px] text-slate-400 block font-sans">len: {sample.before_length}</span>
                                        </td>
                                        <td className="p-2.5 text-emerald-700 bg-emerald-50/40 font-bold">
                                          {sample.after_preview}
                                          <span className="text-[9px] text-slate-400 block font-sans">len: {sample.after_length}</span>
                                        </td>
                                        <td className="p-2.5">
                                          <span className={cn(
                                            "rounded px-1.5 py-0.5 text-[10px] font-bold font-sans",
                                            sample.format_validation_status === 'PASS'
                                              ? "bg-emerald-100 text-emerald-800"
                                              : sample.format_validation_status === 'AUDIT_RECONCILE_REQUIRED'
                                              ? "bg-amber-100 text-amber-900 border border-amber-300"
                                              : sample.format_validation_status === 'TELEMETRY_INSPECT_REQUIRED'
                                              ? "bg-sky-100 text-sky-900 border border-sky-300"
                                              : "bg-rose-100 text-rose-800"
                                          )}>
                                            {sample.format_validation_status}
                                          </span>
                                        </td>
                                        <td className="p-2.5 text-slate-400 text-[10px]">
                                          {sample.before_hash.slice(0, 8)} → {sample.after_hash.slice(0, 8)}
                                        </td>
                                      </tr>
                                    ))}
                                  </tbody>
                                </table>
                              </div>
                            </div>
                          )}

                          {/* 4. Maker-Checker Action Bar */}
                          <div className="rounded-2xl border border-slate-200 bg-white p-5 space-y-4 shadow-2xs">
                            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
                              <div className="space-y-0.5">
                                <h5 className="font-bold text-slate-900 text-xs uppercase tracking-wide">
                                  Hành Động Phê Duyệt & Thực Thi (Maker-Checker Governance)
                                </h5>
                                <p className="text-[11px] text-slate-500">
                                  AI là Proposer (Maker); Admin là Approver (Checker). Thực thi an toàn theo Transaction.
                                </p>
                              </div>

                              {/* Reject Reason input toggle */}
                              {showRejectInput && (
                                <div className="w-full space-y-2 pt-2">
                                  <textarea
                                    rows={2}
                                    value={rejectReasonInput}
                                    onChange={(e) => setRejectReasonInput(e.target.value)}
                                    placeholder="Nhập lý do từ chối đề xuất xử lý..."
                                    className="w-full rounded-xl border border-slate-200 bg-slate-50 p-2 text-xs focus:outline-none focus:border-rose-500"
                                  />
                                  <div className="flex justify-end gap-2">
                                    <Button size="sm" variant="outline" onClick={() => setShowRejectInput(false)}>Hủy</Button>
                                    <Button size="sm" onClick={handleRejectProposal} className="bg-rose-600 hover:bg-rose-700 text-white font-bold">
                                      Xác nhận Từ Chối
                                    </Button>
                                  </div>
                                </div>
                              )}

                              {!showRejectInput && (
                                <div className="flex flex-wrap items-center gap-2">
                                  {structuredProposal.status === 'DRY_RUN_PASSED' && (
                                    <>
                                      <Button
                                        size="sm"
                                        variant="outline"
                                        disabled={isAuditor}
                                        onClick={handleSubmitForReview}
                                        className="text-xs"
                                      >
                                        Gửi Chờ Duyệt (Submit)
                                      </Button>
                                      <Button
                                        size="sm"
                                        disabled={isAuditor}
                                        onClick={handleApproveProposal}
                                        className="bg-teal-600 hover:bg-teal-700 text-white text-xs font-bold"
                                      >
                                        Phê Duyệt Đề Xuất (Admin)
                                      </Button>
                                    </>
                                  )}

                                  {structuredProposal.status === 'PENDING_APPROVAL' && (
                                    <>
                                      <Button
                                        size="sm"
                                        variant="outline"
                                        disabled={isAuditor}
                                        onClick={() => setShowRejectInput(true)}
                                        className="text-xs text-rose-600 hover:bg-rose-50"
                                      >
                                        Từ Chối Đề Xuất
                                      </Button>
                                      <Button
                                        size="sm"
                                        disabled={isAuditor}
                                        onClick={handleApproveProposal}
                                        className="bg-teal-600 hover:bg-teal-700 text-white text-xs font-bold"
                                      >
                                        Phê Duyệt Đề Xuất (Admin)
                                      </Button>
                                    </>
                                  )}

                                  {structuredProposal.status === 'APPROVED' && (
                                    <Button
                                      size="sm"
                                      disabled={isAuditor || isExecutingTransaction}
                                      onClick={handleExecuteTransaction}
                                      className="bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-bold gap-1.5 shadow-sm px-4"
                                    >
                                      {isExecutingTransaction ? (
                                        <Loader2 className="size-4 animate-spin" />
                                      ) : (
                                        <ShieldCheck className="size-4" />
                                      )}
                                      Phê Duyệt & Thực Thi Transaction (Promote to Silver)
                                    </Button>
                                  )}

                                  {structuredProposal.status === 'REMEDIATED' && (
                                    <span className="inline-flex items-center gap-1.5 rounded-lg border border-emerald-300 bg-emerald-50 px-3 py-1.5 text-xs font-bold text-emerald-800">
                                      <CheckCircle2 className="size-4 text-emerald-600" />
                                      Đã Khắc Phục & Chuyển Sang Silver Thành Công
                                    </span>
                                  )}
                                </div>
                              )}
                            </div>

                            {/* Safety & Immutability Notice Banner */}
                            <div className="rounded-xl border border-slate-200/80 bg-slate-50/70 p-3 text-[11px] text-slate-600 space-y-1">
                              <p className="font-semibold text-slate-800 flex items-center gap-1.5">
                                <Lock className="size-3.5 text-teal-600" />
                                Cam kết an toàn & bảo toàn bất biến dữ liệu:
                              </p>
                              <ul className="list-disc list-inside space-y-0.5 text-slate-500 pl-1 text-[10px]">
                                <li>Dữ liệu thô Bronze và snapshot vi phạm trong <code className="font-mono text-slate-700">quarantine.records</code> được bảo toàn bất biến.</li>
                                <li>Dữ liệu remediated được ghi qua <code className="font-mono text-slate-700">staging.remediated_records</code> và chạy lại bài kiểm tra tuân thủ (Post-check) trước khi đưa vào Silver.</li>
                                <li>Tự động <code className="font-mono text-slate-700">ROLLBACK 100%</code> nếu số lượng bản ghi hoặc hash dữ liệu nguồn bị lệch tại thời điểm commit.</li>
                              </ul>
                            </div>
                          </div>
                        </div>
                      ) : (
                        <div className="p-8 text-center text-xs text-slate-500 rounded-2xl border border-slate-200 bg-slate-50/50 space-y-3">
                          <p>Chưa có đề xuất Remediation có cấu trúc nào cho Finding này.</p>
                          <Button
                            size="sm"
                            onClick={loadProposal}
                            disabled={isProposalLoading}
                            className="bg-teal-600 hover:bg-teal-700 text-white text-xs font-bold gap-1.5"
                          >
                            <Sparkles size={13} />
                            <span>Khởi tạo Đề xuất Xử lý Cách ly</span>
                          </Button>
                        </div>
                      )}
                    </div>
                  )}


                  {/* ======================================================= */}
                  {/* TAB 4: TARGETED ROOT-CAUSE DATA LINEAGE                  */}
                  {/* ======================================================= */}
                  {activeTab === 'lineage' && (
                    <div className="space-y-4 text-xs">
                      {isLineageLoading ? (
                        <div className="rounded-2xl border border-slate-200 bg-white p-12 text-center shadow-2xs space-y-3">
                          <Loader2 className="size-6 animate-spin text-teal-600 mx-auto" />
                          <p className="font-semibold text-slate-700">Đang trích xuất lát cắt phả hệ nguyên nhân gốc rễ...</p>
                          <p className="text-[11px] text-slate-400">Truy vấn quan hệ Source → Column → Rule → Quarantine từ PostgreSQL Catalog</p>
                        </div>
                      ) : findingLineage?.nodes?.length ? (
                        <>
                          {/* Header Bar */}
                          <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-2xs flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
                            <div className="space-y-1">
                              <div className="flex items-center gap-2">
                                <span className="inline-flex items-center gap-1.5 rounded-full bg-teal-50 px-2.5 py-0.5 text-[10px] font-bold text-teal-800 border border-teal-200">
                                  <GitFork className="size-3 text-teal-600" />
                                  Targeted Root-Cause Lineage
                                </span>
                                <span className="font-mono text-slate-500 text-[11px]">Run: {findingLineage?.runId || detail.run_id}</span>
                              </div>
                              <p className="text-slate-600 text-xs">
                                Lát cắt phả hệ cô lập 5 mắt xích dẫn đến vi phạm của cột <strong className="font-mono text-teal-800 font-bold">{detail.column_name}</strong>.
                              </p>
                            </div>

                            <Button
                              size="sm"
                              onClick={handleTraceLineage}
                              className="bg-slate-900 text-white text-xs font-bold hover:bg-slate-800 gap-1.5 shrink-0 cursor-pointer shadow-xs"
                            >
                              <ExternalLink size={13} />
                              <span>Xem Toàn bộ Lineage của Lần chạy</span>
                            </Button>
                          </div>

                          {/* 5-Node Visual Flow */}
                          <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-2xs space-y-4">
                            <h4 className="font-bold text-slate-900 text-xs uppercase tracking-wider text-[11px] flex items-center gap-2">
                              <span>Hành trình Dữ liệu Gây ra Vi phạm (5 Mắt xích)</span>
                            </h4>

                            <div className="flex flex-col lg:flex-row items-stretch lg:items-center justify-between gap-2.5 pt-1 overflow-x-auto pb-2">
                              {/* Node 1: Raw File */}
                              <div className="flex-1 min-w-[170px] rounded-xl border border-slate-200 bg-slate-50/80 p-3 space-y-1.5 shadow-2xs">
                                <div className="flex items-center justify-between">
                                  <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500">1. Nguồn Gốc</span>
                                  <Database className="size-3.5 text-slate-600" />
                                </div>
                                <p className="font-mono font-bold text-slate-900 text-xs truncate" title={`${detail.dataset_id}.csv`}>
                                  {detail.dataset_id}.csv
                                </p>
                                <p className="text-[11px] text-slate-500">Tệp tin dữ liệu thô ban đầu</p>
                              </div>

                              <ArrowRight className="hidden lg:block size-4 text-slate-300 shrink-0" />

                              {/* Node 2: Task 1 Ingest */}
                              <div className="flex-1 min-w-[170px] rounded-xl border border-sky-200 bg-sky-50/70 p-3 space-y-1.5 shadow-2xs">
                                <div className="flex items-center justify-between">
                                  <span className="text-[10px] font-bold uppercase tracking-wider text-sky-700">2. Nạp Liệu</span>
                                  <Workflow className="size-3.5 text-sky-600" />
                                </div>
                                <p className="font-bold text-sky-950 text-xs truncate">
                                  Task 1: Ingest & Catalog
                                </p>
                                <p className="text-[11px] text-sky-700">Làm sạch & gắn mã batch</p>
                              </div>

                              <ArrowRight className="hidden lg:block size-4 text-slate-300 shrink-0" />

                              {/* Node 3: Bronze Subject Column */}
                              <div className="flex-1 min-w-[170px] rounded-xl border border-amber-300 bg-amber-50/80 p-3 space-y-1.5 shadow-2xs">
                                <div className="flex items-center justify-between">
                                  <span className="text-[10px] font-bold uppercase tracking-wider text-amber-800">3. Cột Lớp Bronze</span>
                                  <Layers className="size-3.5 text-amber-600" />
                                </div>
                                <p className="font-mono font-bold text-amber-950 text-xs truncate">
                                  bronze.{detail.column_name}
                                </p>
                                <p className="text-[11px] text-amber-700">Chưa qua xử lý chuẩn hóa</p>
                              </div>

                              <ArrowRight className="hidden lg:block size-4 text-slate-300 shrink-0" />

                              {/* Node 4: Violated Rule Evaluation */}
                              <div className="flex-1 min-w-[170px] rounded-xl border border-rose-300 bg-rose-50/80 p-3 space-y-1.5 shadow-2xs">
                                <div className="flex items-center justify-between">
                                  <span className="text-[10px] font-bold uppercase tracking-wider text-rose-700">4. Đánh Giá Chính Sách</span>
                                  <ShieldAlert className="size-3.5 text-rose-600" />
                                </div>
                                <p className="font-mono font-bold text-rose-950 text-xs truncate" title={detail.rule_id}>
                                  {detail.rule_id}
                                </p>
                                <span className="inline-block text-[10px] font-semibold text-rose-800 bg-rose-100/80 px-1.5 py-0.5 rounded truncate max-w-full">
                                  {findingLineage?.aiExplanationContext?.legalBasis || detail.policy_name || 'Quy tắc Kiểm định'}
                                </span>
                              </div>

                              <ArrowRight className="hidden lg:block size-4 text-slate-300 shrink-0" />

                              {/* Node 5: Quarantine Target */}
                              <div className="flex-1 min-w-[170px] rounded-xl border border-red-400 bg-red-50/90 p-3 space-y-1.5 shadow-2xs">
                                <div className="flex items-center justify-between">
                                  <span className="text-[10px] font-bold uppercase tracking-wider text-red-800">5. Điểm Đến Cách Ly</span>
                                  <AlertOctagon className="size-3.5 text-red-600" />
                                </div>
                                <p className="font-bold text-red-950 text-xs truncate">
                                  Quarantine Record
                                </p>
                                <span className="inline-block text-[10px] font-bold text-red-800 bg-red-100 px-1.5 py-0.5 rounded">
                                  {detail.severity} · {detail.status}
                                </span>
                              </div>
                            </div>
                          </div>

                          {/* Root Cause Details & AI Context */}
                          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                            {/* Transformation & Legal Matrix */}
                            <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-2xs space-y-2.5">
                              <h5 className="font-bold text-slate-900 text-xs flex items-center gap-1.5">
                                <Scale className="size-3.5 text-slate-600" />
                                <span>Căn cứ Pháp lý & Thao tác Điều hướng</span>
                              </h5>
                              <div className="space-y-2 text-[11px] text-slate-600">
                                <div className="flex justify-between py-1 border-b border-slate-100">
                                  <span className="text-slate-500">Cột nguồn (Bronze):</span>
                                  <strong className="font-mono text-slate-800">{detail.column_name}</strong>
                                </div>
                                <div className="flex justify-between py-1 border-b border-slate-100">
                                  <span className="text-slate-500">Quy tắc áp dụng:</span>
                                  <strong className="font-mono text-teal-800">{detail.rule_id}</strong>
                                </div>
                                <div className="flex justify-between py-1 border-b border-slate-100">
                                  <span className="text-slate-500">Căn cứ pháp luật:</span>
                                  <span className="font-medium text-slate-800 text-right max-w-[220px]">
                                    {findingLineage?.aiExplanationContext?.legalBasis || detail.policy_name || 'Quy chuẩn tuân thủ'}
                                  </span>
                                </div>
                                <div className="flex justify-between py-1">
                                  <span className="text-slate-500">Hành động thực thi:</span>
                                  <span className="font-bold text-rose-700">ROUTED_TO_QUARANTINE</span>
                                </div>
                              </div>
                            </div>

                            {/* AI Copilot Explanation */}
                            <div className="rounded-2xl border border-teal-200 bg-gradient-to-br from-teal-50/50 to-white p-4 shadow-2xs space-y-2.5">
                              <div className="flex items-center justify-between">
                                <h5 className="font-bold text-teal-950 text-xs flex items-center gap-1.5">
                                  <Sparkles className="size-3.5 text-teal-600" />
                                  <span>AI Governance Copilot — Phân tích</span>
                                </h5>
                              </div>
                              <p className="text-[11px] text-slate-700 leading-relaxed">
                                {findingLineage?.aiExplanationContext?.summary ||
                                  `Bản ghi bị cách ly do vi phạm quy tắc ${detail.rule_id}. Dữ liệu chưa đáp ứng tiêu chuẩn nên không được đưa vào lớp Silver.`}
                              </p>
                              {findingLineage?.aiExplanationContext?.suggestedRemediation && (
                                <div className="rounded-lg bg-teal-100/50 p-2 text-[11px] text-teal-900">
                                  <strong>Khuyến nghị:</strong> {findingLineage.aiExplanationContext.suggestedRemediation}
                                </div>
                              )}
                              <Button
                                size="sm"
                                variant="outline"
                                onClick={handleAskAIExplain}
                                disabled={isAILoading}
                                className="w-full text-xs font-bold border-teal-300 text-teal-800 hover:bg-teal-50 gap-1.5"
                              >
                                <Sparkles size={12} />
                                <span>Hỏi AI Copilot thêm chi tiết</span>
                              </Button>
                            </div>
                          </div>
                        </>
                      ) : (
                        <div className="rounded-2xl border border-amber-200 bg-amber-50 p-8 text-center">
                          <GitFork className="mx-auto size-6 text-amber-600" />
                          <p className="mt-2 font-semibold text-amber-900">Chưa có bằng chứng lineage cho finding này.</p>
                          <p className="mt-1 text-[11px] text-amber-700">
                            Hệ thống không dựng đường đi giả từ thông tin finding. Hãy mở lineage của run để xem metadata đã xác minh.
                          </p>
                        </div>
                      )}
                    </div>
                  )}

                  {/* ======================================================= */}
                  {/* TAB 5: RULE DEFINITION                                  */}
                  {/* ======================================================= */}
                  {activeTab === 'rule' && (
                    <div className="space-y-4 text-xs">
                      <div className="rounded-2xl border border-slate-200 bg-white p-5 space-y-3 shadow-2xs">
                        <div className="flex items-center justify-between">
                          <span className="font-bold text-slate-900 text-sm">Mã quy tắc: {detail.rule_id}</span>
                          <span className="px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-teal-50 text-teal-700 border border-teal-200">
                            {detail.rule_definition?.status || 'ACTIVE'}
                          </span>
                        </div>

                        {detail.rule_definition ? (
                          <div className="space-y-2.5 pt-2 border-t border-slate-100">
                            <div>
                              <span className="text-slate-500 text-[11px]">Tên quy tắc:</span>
                              <p className="font-semibold text-slate-900 text-xs">{detail.rule_definition.treatment_name}</p>
                            </div>
                            <div>
                              <span className="text-slate-500 text-[11px]">Hàm thực thi (Operation ID):</span>
                              <p className="font-mono text-teal-700 text-xs">{detail.rule_definition.operation_id}</p>
                            </div>
                            <div>
                              <span className="text-slate-500 text-[11px]">Biểu thức Logic (Expression):</span>
                              <pre className="p-3 rounded-xl bg-slate-50 font-mono text-slate-800 text-[11px] mt-1 border border-slate-200 overflow-x-auto">
                                {detail.rule_definition.expression_display}
                              </pre>
                            </div>
                            <div>
                              <span className="text-slate-500 text-[11px]">Cán bộ thực thi chính sách:</span>
                              <p className="text-slate-700 text-xs">{detail.rule_definition.enforced_by || 'DataTrust Admin'}</p>
                            </div>
                          </div>
                        ) : (
                          <div className="text-slate-500 text-xs py-2">
                            Quy tắc cốt lõi của hệ thống (Built-in Pipeline Gate).
                          </div>
                        )}
                      </div>
                    </div>
                  )}

                  {/* ======================================================= */}
                  {/* TAB 6: AUDIT HISTORY                                    */}
                  {/* ======================================================= */}
                  {activeTab === 'history' && (
                    <div className="space-y-4 text-xs">
                      <div className="rounded-2xl border border-slate-200 bg-white p-5 space-y-4 shadow-2xs">
                        <span className="font-bold text-slate-900 text-sm block border-b border-slate-100 pb-2.5">
                          Nhật ký Vòng đời Vấn đề (Lifecycle Audit Trail)
                        </span>
                        <div className="space-y-4 pl-1">
                          <div className="flex items-start gap-3">
                            <span className="size-2 rounded-full bg-rose-500 mt-1.5 shrink-0" />
                            <div>
                              <p className="font-semibold text-slate-900">Phát hiện Vi phạm lần đầu</p>
                              <p className="text-slate-500 text-[11px]">{formatDateTime(detail.detected_at)} bởi Airflow Pipeline Lane C</p>
                            </div>
                          </div>

                          {detail.resolved_at && (
                            <div className="flex items-start gap-3">
                              <span className="size-2 rounded-full bg-emerald-500 mt-1.5 shrink-0" />
                              <div>
                                <p className="font-semibold text-emerald-800">Cập nhật Trạng thái: {detail.status}</p>
                                <p className="text-slate-500 text-[11px]">{formatDateTime(detail.resolved_at)}</p>
                                {detail.resolved_by && (
                                  <p className="text-slate-400 text-[11px]">Người thực hiện: {detail.resolved_by}</p>
                                )}
                              </div>
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                  )}
                </>
              ) : null}
            </div>
          </main>
        </div>

        {/* ========================================================================= */}
        {/* 3. MODAL FOOTER ACTION BAR                                               */}
        {/* ========================================================================= */}
        <div className="border-t border-slate-100 px-6 py-3.5 bg-white flex flex-wrap items-center justify-between gap-3 shrink-0">
          {/* Nhóm nút bên trái: Phân tích & Xem dữ liệu */}
          <div className="flex flex-wrap items-center gap-2">
            {/* Button 1: AI giải thích */}
            <Button
              size="sm"
              variant="outline"
              onClick={handleAskAIExplain}
              disabled={isAILoading}
              className="h-8.5 rounded-xl border-slate-200 hover:border-slate-300 text-slate-700 hover:bg-slate-50 text-xs font-semibold gap-1.5 shadow-2xs cursor-pointer"
            >
              {isAILoading ? <Loader2 className="size-3.5 animate-spin" /> : <Sparkles className="size-3.5 text-[#04D3D4]" />}
              <span>{isAILoading ? 'Đang phân tích…' : 'AI giải thích'}</span>
            </Button>
          </div>

          {/* Nhóm nút bên phải: Phê duyệt & Chuyển xử lý (Góc phải) */}
          <div className="flex items-center gap-2 ml-auto">
            {/* Button 4: Phê duyệt Ngoại lệ */}
            <Button
              size="sm"
              variant="outline"
              disabled={isAuditor}
              onClick={() => setShowOverrideModal(true)}
              className="h-8.5 rounded-xl border-slate-200 hover:border-slate-300 text-slate-700 hover:bg-slate-50 text-xs font-semibold gap-1.5 shadow-2xs cursor-pointer disabled:opacity-50"
            >
              <ShieldCheck className="size-3.5 text-amber-500" />
              <span>Phê duyệt Ngoại lệ</span>
            </Button>

            {/* Button 5: Phê duyệt & chuyển xử lý */}
            <Button
              size="sm"
              disabled={isAuditor || isUpdatingStatus}
              onClick={handleToggleStatus}
              className="h-8.5 rounded-xl bg-slate-900 hover:bg-slate-800 text-white text-xs font-bold gap-1.5 shadow-sm cursor-pointer disabled:opacity-50"
            >
              <CheckCheck className="size-3.5 text-emerald-400" />
              <span>{detail?.status === 'OPEN' ? 'Phê duyệt & chuyển xử lý' : 'Đóng Vấn đề'}</span>
            </Button>
          </div>
        </div>
      </div>

      {/* ========================================================================= */}
      {/* 4. SUB-MODALS (LIGHT THEME)                                               */}
      {/* ========================================================================= */}
      {/* REMEDIATION HITL DECISION MODAL */}
      {remediationDecision && aiAnalysis?.remediation && (
        <div className="fixed inset-0 z-60 flex items-center justify-center bg-black/60 backdrop-blur-xs p-4">
          <div className="w-full max-w-md rounded-3xl border border-slate-200 bg-white p-6 space-y-4 shadow-2xl">
            <h3 className="text-sm font-bold text-slate-900">
              {remediationDecision === 'approve' ? 'Xác nhận phê duyệt đề xuất AI?' : 'Xác nhận từ chối đề xuất AI?'}
            </h3>
            <div className="rounded-2xl border border-slate-200 bg-slate-50/70 p-3.5 space-y-2 text-xs">
              <p className="text-slate-500">Bạn đang {remediationDecision === 'approve' ? 'phê duyệt' : 'tối từ chối'}:</p>
              <p className="font-mono text-xs font-semibold text-teal-800 bg-white p-2 rounded-lg border border-slate-200">
                {aiAnalysis.remediation.action}
              </p>
              <p className="text-slate-500">Phạm vi:</p>
              <p className="font-semibold text-slate-800">
                {aiAnalysis.remediation.scope.affected_records} bản ghi bị cách ly
              </p>
              <p className="font-mono text-[11px] text-slate-400">
                {aiAnalysis.remediation.scope.dataset_id} · {aiAnalysis.remediation.scope.run_id}
              </p>
            </div>
            <textarea
              rows={3}
              value={decisionComment}
              onChange={(e) => setDecisionComment(e.target.value)}
              placeholder="Ghi chú quyết định (không bắt buộc)"
              className="w-full rounded-xl border border-slate-200 bg-slate-50 p-3 text-xs text-slate-800 focus:outline-none focus:ring-2 focus:ring-teal-500/20 focus:border-teal-500"
            />
            {aiActionError && <p className="text-xs text-rose-600">{aiActionError}</p>}
            <div className="flex justify-end gap-2">
              <Button size="sm" variant="outline" disabled={isDeciding} onClick={() => setRemediationDecision(null)}>
                Hủy
              </Button>
              <Button
                size="sm"
                disabled={isDeciding}
                onClick={handleRemediationDecision}
                className={remediationDecision === 'approve' ? 'bg-teal-600 hover:bg-teal-700 text-white font-bold' : 'bg-rose-600 hover:bg-rose-700 text-white font-bold'}
              >
                {isDeciding && <Loader2 className="mr-1 size-3.5 animate-spin" />}
                {remediationDecision === 'approve' ? 'Phê duyệt' : 'Từ chối'}
              </Button>
            </div>
            {remediationDecision === 'approve' && (
              <p className="text-[11px] text-amber-700">Phê duyệt chỉ chuyển trạng thái sang Pending execution; không tự thực thi remediation.</p>
            )}
          </div>
        </div>
      )}

      {/* OVERRIDE JUSTIFICATION MODAL */}
      {showOverrideModal && (
        <div className="fixed inset-0 z-60 flex items-center justify-center bg-black/60 backdrop-blur-xs p-4">
          <div className="w-full max-w-md rounded-3xl border border-slate-200 bg-white p-6 space-y-4 shadow-2xl">
            <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
              <ShieldCheck className="size-4 text-amber-500" />
              Phê duyệt Ngoại lệ Kiểm toán (Audit Override)
            </h3>
            <p className="text-xs text-slate-500">
              Nhập giải trình lý do nghiệp vụ cho phép bản ghi này được thông qua (ghi vĩnh viễn vào nhật ký kiểm toán):
            </p>
            <textarea
              rows={3}
              value={overrideJustification}
              onChange={(e) => setOverrideJustification(e.target.value)}
              placeholder="Giải trình kiểm toán: Cuốc xe thử nghiệm nội bộ hoặc có chứng từ hợp lệ..."
              className="w-full rounded-xl border border-slate-200 bg-slate-50 p-3 text-xs text-slate-800 focus:outline-none focus:ring-2 focus:ring-amber-500/20 focus:border-amber-500"
            />
            <div className="flex justify-end gap-2 pt-2">
              <Button size="sm" variant="outline" onClick={() => setShowOverrideModal(false)}>
                Hủy
              </Button>
              <Button size="sm" onClick={handleExecuteOverride} className="bg-amber-500 text-slate-950 font-bold hover:bg-amber-400">
                Xác nhận Ngoại lệ
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* REMEDIATE CLEANED PAYLOAD MODAL */}
      {showRemediateModal && (
        <div className="fixed inset-0 z-60 flex items-center justify-center bg-black/60 backdrop-blur-xs p-4">
          <div className="w-full max-w-lg rounded-3xl border border-slate-200 bg-white p-6 space-y-4 shadow-2xl">
            <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
              <RefreshCw className="size-4 text-emerald-600" />
              Khắc phục & Chạy lại Dữ liệu Cách ly (Remediate)
            </h3>
            <p className="text-xs text-slate-500">
              Chỉnh sửa giá trị vi phạm trong JSON bên dưới trước khi đưa lại vào luồng xử lý:
            </p>
            <textarea
              rows={7}
              value={cleanedPayloadStr}
              onChange={(e) => setCleanedPayloadStr(e.target.value)}
              className="w-full rounded-xl border border-slate-200 bg-slate-900 p-3 font-mono text-xs text-cyan-300 focus:outline-none focus:border-cyan-500"
            />
            <div className="flex justify-end gap-2 pt-2">
              <Button size="sm" variant="outline" onClick={() => setShowRemediateModal(false)}>
                Hủy
              </Button>
              <Button size="sm" onClick={handleExecuteRemediate} className="bg-emerald-600 text-white font-bold hover:bg-emerald-700">
                Lưu & Chạy lại
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// Standalone page wrapper for route /findings/:id
export function FindingDetail({ finding }: { finding?: any }) {
  const { id = '' } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const findingId = finding?.id || finding?.finding_id || id;

  return (
    <FindingDetailModal
      findingId={findingId}
      onClose={() => navigate(-1)}
      onStatusUpdated={() => {}}
    />
  );
}
