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
  Code2,
  History,
  Copy,
  Check,
  Loader2,
  FileText,
  Lock,
  CheckCheck,
  RefreshCw,
  GitFork
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { apiBridge, type FindingAIAnalysis, type FindingDetailData } from '@/lib/api-bridge';
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
  const [activeTab, setActiveTab] = useState<'overview' | 'samples' | 'rule' | 'history'>('overview');
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

  // AI only analyses existing Finding context; it never creates or activates rules.
  const handleAskAIExplain = async () => {
    if (!detail) return;
    setIsAILoading(true);
    setAIActionError(null);
    try {
      setAIAnalysis(await apiBridge.requestFindingAIExplanation(detail.finding_id));
      setActiveTab('overview');
      setActionSuccessMsg('AI đã hoàn tất phân tích dựa trên ngữ cảnh của Finding.');
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
        ? 'Đã phê duyệt — đang chờ bước thực thi riêng.'
        : 'Đã từ chối đề xuất remediation.');
    } catch (err: any) {
      setAIActionError(err.message || 'Không thể ghi nhận quyết định remediation.');
    } finally {
      setIsDeciding(false);
    }
  };

  // Fixed Action 3: Khắc phục & Reprocess
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

  // Fixed Action 4: Phê duyệt Ngoại lệ (Override)
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

  // Fixed Action 5: Cập nhật Trạng thái (OPEN -> IN_REVIEW -> RESOLVED)
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

  const handleTraceLineage = () => {
    if (!detail) return;

    const searchParams = new URLSearchParams({
      dataset: detail.dataset_id,
      run_id: detail.run_id,
    });
    navigate(`/lineage?${searchParams.toString()}`);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-xs p-4 animate-in fade-in duration-200">
      <div
        className="w-full max-w-4xl max-h-[92vh] flex flex-col rounded-2xl border border-slate-700 bg-slate-900 shadow-2xl overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between border-b border-slate-800 px-6 py-4 bg-slate-900/90">
          <div className="flex items-center gap-3">
            <span
              className={`grid size-10 place-items-center rounded-xl font-bold ${
                detail?.severity === 'CRITICAL'
                  ? 'bg-rose-500/10 text-rose-400 border border-rose-500/30'
                  : 'bg-amber-500/10 text-amber-400 border border-amber-500/30'
              }`}
            >
              <ShieldAlert className="size-5" />
            </span>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-lg font-bold text-white font-mono">{findingId}</h2>
                {detail && (
                  <>
                    <span
                      className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                        detail.severity === 'CRITICAL'
                          ? 'bg-rose-500/20 text-rose-300'
                          : 'bg-amber-500/20 text-amber-300'
                      }`}
                    >
                      {detail.severity}
                    </span>
                    <span
                      className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                        detail.status === 'OPEN'
                          ? 'bg-rose-500/10 text-rose-400 border border-rose-500/20'
                          : detail.status === 'IN_REVIEW'
                          ? 'bg-amber-500/10 text-amber-400 border border-amber-500/20'
                          : 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                      }`}
                    >
                      {detail.status}
                    </span>
                  </>
                )}
              </div>
              <p className="text-xs text-slate-400">
                {detail?.dataset_id} · Cột: <strong className="text-cyan-400 font-mono">{detail?.column_name}</strong> · Phát hiện: {formatDateTime(detail?.detected_at)}
              </p>
            </div>
          </div>

          <button
            onClick={onClose}
            className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-800 hover:text-white transition-colors"
          >
            <X className="size-5" />
          </button>
        </div>

        {/* Action success alert */}
        {actionSuccessMsg && (
          <div className="bg-cyan-500/10 border-b border-cyan-500/20 px-6 py-2.5 text-xs text-cyan-300 flex items-center gap-2">
            <CheckCircle2 className="size-4 text-cyan-400 shrink-0" />
            <span>{actionSuccessMsg}</span>
          </div>
        )}
        {aiActionError && (
          <div className="bg-rose-500/10 border-b border-rose-500/20 px-6 py-2.5 text-xs text-rose-300 flex items-center justify-between gap-3">
            <span>{aiActionError}</span>
            <button onClick={() => setAIActionError(null)} className="text-rose-200 hover:text-white">Đóng</button>
          </div>
        )}

        {/* RBAC Auditor Notice */}
        {isAuditor && (
          <div className="bg-amber-500/10 border-b border-amber-500/20 px-6 py-2 text-[11px] text-amber-300 flex items-center gap-2">
            <Lock className="size-3.5 text-amber-400 shrink-0" />
            <span>Chế độ Chỉ đọc (Auditor): Các nút Khắc phục, Ngoại lệ và Đổi trạng thái bị vô hiệu hóa.</span>
          </div>
        )}

        {/* Tab Header */}
        <div className="flex border-b border-slate-800 bg-slate-900/50 px-6 text-xs font-semibold">
          <button
            onClick={() => setActiveTab('overview')}
            className={`py-3 px-4 border-b-2 transition-colors flex items-center gap-2 ${
              activeTab === 'overview'
                ? 'border-cyan-400 text-cyan-400'
                : 'border-transparent text-slate-400 hover:text-white'
            }`}
          >
            <FileText className="size-3.5" />
            <span>1. Tổng quan & Tác động</span>
          </button>
          <button
            onClick={() => setActiveTab('samples')}
            className={`py-3 px-4 border-b-2 transition-colors flex items-center gap-2 ${
              activeTab === 'samples'
                ? 'border-cyan-400 text-cyan-400'
                : 'border-transparent text-slate-400 hover:text-white'
            }`}
          >
            <Database className="size-3.5" />
            <span>2. Mẫu bản ghi vi phạm ({detail?.sample_records?.length || 0})</span>
          </button>
          <button
            onClick={() => setActiveTab('rule')}
            className={`py-3 px-4 border-b-2 transition-colors flex items-center gap-2 ${
              activeTab === 'rule'
                ? 'border-cyan-400 text-cyan-400'
                : 'border-transparent text-slate-400 hover:text-white'
            }`}
          >
            <Code2 className="size-3.5" />
            <span>3. Định nghĩa Quy tắc</span>
          </button>
          <button
            onClick={() => setActiveTab('history')}
            className={`py-3 px-4 border-b-2 transition-colors flex items-center gap-2 ${
              activeTab === 'history'
                ? 'border-cyan-400 text-cyan-400'
                : 'border-transparent text-slate-400 hover:text-white'
            }`}
          >
            <History className="size-3.5" />
            <span>4. Lịch sử Kiểm toán</span>
          </button>
        </div>

        {/* Tab Body */}
        <div className="flex-1 overflow-y-auto p-6 space-y-4">
          {loading ? (
            <div className="py-16 text-center text-xs text-slate-400 flex flex-col items-center gap-2">
              <Loader2 className="size-6 animate-spin text-cyan-400" />
              <span>Đang tải thông tin chi tiết từ cơ sở dữ liệu…</span>
            </div>
          ) : error ? (
            <div className="p-4 rounded-xl bg-rose-500/10 text-rose-300 text-xs border border-rose-500/30 flex items-center justify-between">
              <span>{error}</span>
              <Button
                size="sm"
                variant="outline"
                onClick={loadDetail}
                className="h-7 text-xs border-rose-500/40 text-rose-200 hover:bg-rose-500/20"
              >
                Thử lại
              </Button>
            </div>
          ) : detail ? (
            <>
              {/* TAB 1: OVERVIEW & IMPACT */}
              {activeTab === 'overview' && (
                <div className="space-y-4 text-xs">
                  <div className="rounded-xl border border-slate-800 bg-slate-950 p-4 space-y-2">
                    <span className="text-[11px] font-bold uppercase text-slate-400 tracking-wider">
                      Lý do Vi phạm Ghi nhận:
                    </span>
                    <p className="text-sm font-medium text-white leading-relaxed">{detail.reason}</p>
                  </div>

                  <div className="grid gap-3 md:grid-cols-3">
                    <div className="rounded-xl border border-slate-800 bg-slate-950 p-4 space-y-2">
                      <span className="text-[11px] font-bold text-slate-400">Chính sách Áp dụng (Policy):</span>
                      <p className="text-xs font-semibold text-cyan-300">{detail.policy_name || 'Chưa xác định chính sách'}</p>
                      <p className="text-[11px] font-mono text-slate-400">Mã chính sách: {detail.policy_id || 'Chưa xác định'}</p>
                    </div>

                    <div className="rounded-xl border border-slate-800 bg-slate-950 p-4 space-y-2">
                      <span className="text-[11px] font-bold text-slate-400">Căn cứ Pháp lý (Law Standard):</span>
                      <p className="text-xs font-semibold text-emerald-400">{detail.law_ref || 'Chưa xác định căn cứ pháp lý'}</p>
                    </div>

                    <div className="rounded-xl border border-slate-800 bg-slate-950 p-4 space-y-2">
                      <span className="text-[11px] font-bold text-slate-400">Phạm vi tài phán (Jurisdiction):</span>
                      <p className="text-xs font-semibold text-violet-300">{detail.subject_zone || 'Chưa xác định zone'}</p>
                      {detail.jurisdiction_chain && detail.jurisdiction_chain.length > 0 && (
                        <p className="text-[11px] font-mono text-slate-400">{detail.jurisdiction_chain.join(' → ')}</p>
                      )}
                    </div>
                  </div>

                  <div className="rounded-xl border border-slate-800 bg-slate-950 p-4 space-y-2">
                    <span className="text-[11px] font-bold text-slate-400">Tác động Dữ liệu (Impact & Quarantine):</span>
                    <p className="text-xs text-slate-300">
                      Có <strong className="text-rose-400 font-mono">{detail.failed_record_count} bản ghi</strong> đã bị ngắt khỏi luồng sản xuất và chuyển sang làn Quarantine.
                      {detail.impact && <> {detail.impact}</>}
                    </p>
                  </div>

                  {aiAnalysis && (
                    <div className="rounded-xl border border-indigo-500/30 bg-indigo-950/20 p-4 space-y-4">
                      <div className="flex items-center justify-between gap-3">
                        <span className="flex items-center gap-2 text-sm font-bold text-indigo-200">
                          <Sparkles className="size-4 text-indigo-400" /> AI Analysis
                        </span>
                        <span className="rounded-full border border-indigo-500/30 bg-indigo-500/10 px-2.5 py-1 font-mono text-[11px] text-indigo-200">
                          Confidence {Math.round(aiAnalysis.confidence <= 1 ? aiAnalysis.confidence * 100 : aiAnalysis.confidence)}%
                        </span>
                      </div>

                      <div className="space-y-1">
                        <p className="font-bold text-slate-300">Điều gì đã xảy ra</p>
                        <p className="leading-relaxed text-slate-200">{aiAnalysis.explanation}</p>
                      </div>
                      <div className="space-y-1">
                        <p className="font-bold text-slate-300">Nguyên nhân gốc rễ (RCA)</p>
                        <p className="leading-relaxed text-white">{aiAnalysis.root_cause}</p>
                      </div>

                      {aiAnalysis.issues?.length > 0 && (
                        <div className="space-y-2">
                          <p className="text-[11px] font-bold uppercase tracking-wider text-slate-500">Vấn đề cụ thể và hướng xử lý</p>
                          {aiAnalysis.issues.map((issue, index) => (
                            <div key={`${issue.field}-${index}`} className="rounded-lg border border-amber-500/25 bg-amber-950/10 p-3">
                              <div className="flex flex-wrap items-center gap-2">
                                <code className="rounded bg-slate-900 px-2 py-1 text-xs font-semibold text-amber-300">{issue.field}</code>
                                <span className="text-sm font-semibold text-white">{issue.issue}</span>
                              </div>
                              {issue.observed_condition && (
                                <p className="mt-2 text-xs text-slate-300">Quan sát: {issue.observed_condition}</p>
                              )}
                              <p className="mt-1 text-xs text-slate-400">Nguyên nhân có thể: {issue.likely_cause}</p>
                              <p className="mt-2 text-sm text-emerald-300">Đề xuất: {issue.suggested_action}</p>
                              {issue.evidence_reference && (
                                <p className="mt-1 font-mono text-[10px] text-cyan-400">Evidence: {issue.evidence_reference}</p>
                              )}
                            </div>
                          ))}
                        </div>
                      )}

                      <div className="space-y-2">
                        <p className="font-bold text-slate-300">Data path / Context references</p>
                        <div className="flex flex-wrap items-center gap-1.5">
                          {aiAnalysis.evidence_references.map((reference, index) => (
                            <span key={`${reference}-${index}`} className="rounded border border-slate-700 bg-slate-900 px-2 py-1 font-mono text-[10px] text-cyan-300">
                              {reference}
                            </span>
                          ))}
                        </div>
                        {aiAnalysis.missing_context.length > 0 && (
                          <p className="text-[11px] text-amber-300">Thiếu context: {aiAnalysis.missing_context.join(', ')}</p>
                        )}
                      </div>

                      {aiAnalysis.remediation && (
                        <div className="rounded-lg border border-cyan-500/30 bg-slate-950 p-3 space-y-3">
                          <div className="flex items-center justify-between gap-2">
                            <p className="font-bold text-cyan-200">Đề xuất xử lý (Remediation)</p>
                            <span className="rounded bg-slate-800 px-2 py-1 text-[10px] font-bold uppercase text-slate-200">
                              {aiAnalysis.remediation.status === 'pending_execution'
                                ? 'Approved → Pending execution'
                                : aiAnalysis.remediation.status}
                            </span>
                          </div>
                          <p className="font-mono text-sm text-white">{aiAnalysis.remediation.action}</p>
                          <p className="text-slate-300">{aiAnalysis.remediation.rationale}</p>
                          <p className="text-[11px] text-slate-400">
                            Scope: {aiAnalysis.remediation.scope.affected_records} bản ghi · dataset {aiAnalysis.remediation.scope.dataset_id}
                          </p>
                          {aiAnalysis.remediation.status === 'suggested' && (
                            <div className="flex justify-end gap-2 pt-1">
                              <Button size="sm" variant="outline" disabled={isAuditor} onClick={() => setRemediationDecision('reject')} className="text-xs">
                                Reject
                              </Button>
                              <Button size="sm" disabled={isAuditor} onClick={() => setRemediationDecision('approve')} className="bg-cyan-600 text-xs hover:bg-cyan-500">
                                Approve
                              </Button>
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )}

              {/* TAB 2: SAMPLE RECORDS (RAW RECORD JSON VIEW) */}
              {activeTab === 'samples' && (
                <div className="space-y-4">
                  <div className="flex items-center justify-between text-xs text-slate-400">
                    <span>Mẫu bản ghi bị cách ly thực tế từ bảng <code className="text-cyan-400 font-mono">quarantine.records</code></span>
                    <span>Hiển thị tối đa 10 bản ghi</span>
                  </div>

                  {(!detail.sample_records || detail.sample_records.length === 0) ? (
                    <div className="p-8 text-center text-xs text-slate-500 rounded-xl border border-slate-800">
                      Không có bản ghi cách ly mẫu nào liên kết trực tiếp với Finding này.
                    </div>
                  ) : (
                    <div className="space-y-3">
                      {detail.sample_records.map((rec, idx) => (
                        <div key={rec.quarantine_id} className="rounded-xl border border-slate-800 bg-slate-950 p-4 text-xs space-y-2">
                          <div className="flex items-center justify-between pb-2 border-b border-slate-800/80">
                            <div className="flex items-center gap-2">
                              <span className="font-mono font-bold text-cyan-400">Mẫu #{idx + 1}</span>
                              <span className="text-slate-500 font-mono text-[11px]">ID: {rec.quarantine_id}</span>
                              {rec.source_row_pk && (
                                <span className="bg-slate-800 px-2 py-0.5 rounded text-[10px] font-mono text-slate-300">
                                  PK: {rec.source_row_pk}
                                </span>
                              )}
                            </div>
                            <button
                              onClick={() => copyToClipboard(JSON.stringify(rec.raw_record_json, null, 2), idx)}
                              className="text-slate-400 hover:text-white flex items-center gap-1 text-[11px] transition-colors"
                            >
                              {copiedIndex === idx ? (
                                <Check className="size-3.5 text-emerald-400" />
                              ) : (
                                <Copy className="size-3.5" />
                              )}
                              <span>Sao chép JSON</span>
                            </button>
                          </div>

                          <div className="space-y-1">
                            <span className="text-[10px] text-rose-400 font-bold uppercase">Lý do cách ly:</span>
                            <p className="text-xs text-rose-300 font-mono">{rec.violation_reason}</p>
                          </div>

                          <div className="mt-2">
                            <span className="text-[10px] text-slate-400 font-bold uppercase block mb-1">
                              Raw Record Payload (JSON):
                            </span>
                            <pre className="p-3 rounded-lg bg-slate-900 border border-slate-800 font-mono text-[11px] text-slate-200 overflow-x-auto max-h-48 leading-relaxed">
                              {JSON.stringify(rec.raw_record_json, null, 2)}
                            </pre>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {/* TAB 3: RULE DEFINITION */}
              {activeTab === 'rule' && (
                <div className="space-y-4 text-xs">
                  <div className="rounded-xl border border-slate-800 bg-slate-950 p-4 space-y-3">
                    <div className="flex items-center justify-between">
                      <span className="font-bold text-white text-sm">Mã quy tắc: {detail.rule_id}</span>
                      <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-cyan-500/20 text-cyan-300 border border-cyan-500/30">
                        {detail.rule_definition?.status || 'ACTIVE'}
                      </span>
                    </div>

                    {detail.rule_definition ? (
                      <div className="space-y-2 pt-2 border-t border-slate-800">
                        <div>
                          <span className="text-slate-400 text-[11px]">Tên quy tắc:</span>
                          <p className="font-semibold text-white">{detail.rule_definition.treatment_name}</p>
                        </div>
                        <div>
                          <span className="text-slate-400 text-[11px]">Hàm thực thi (Operation ID):</span>
                          <p className="font-mono text-cyan-400">{detail.rule_definition.operation_id}</p>
                        </div>
                        <div>
                          <span className="text-slate-400 text-[11px]">Biểu thức Logic (Expression):</span>
                          <pre className="p-2 rounded bg-slate-900 font-mono text-cyan-300 text-[11px] mt-1 border border-slate-800">
                            {detail.rule_definition.expression_display}
                          </pre>
                        </div>
                        <div>
                          <span className="text-slate-400 text-[11px]">Cán bộ thực thi chính sách:</span>
                          <p className="text-slate-200">{detail.rule_definition.enforced_by || 'DataTrust Admin'}</p>
                        </div>
                      </div>
                    ) : (
                      <div className="text-slate-400 text-xs py-2">
                        Quy tắc lõi của hệ thống (Built-in Pipeline Gate).
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* TAB 4: AUDIT HISTORY */}
              {activeTab === 'history' && (
                <div className="space-y-4 text-xs">
                  <div className="rounded-xl border border-slate-800 bg-slate-950 p-4 space-y-3">
                    <span className="font-bold text-white text-sm block border-b border-slate-800 pb-2">
                      Nhật ký Vòng đời Vấn đề (Lifecycle Audit Trail)
                    </span>
                    <div className="space-y-3">
                      <div className="flex items-start gap-3">
                        <span className="size-2 rounded-full bg-rose-400 mt-1.5 shrink-0" />
                        <div>
                          <p className="font-semibold text-white">Phát hiện Vi phạm lần đầu</p>
                          <p className="text-slate-400 text-[11px]">{formatDateTime(detail.detected_at)} bởi Airflow Pipeline Lane C</p>
                        </div>
                      </div>

                      {detail.resolved_at && (
                        <div className="flex items-start gap-3">
                          <span className="size-2 rounded-full bg-emerald-400 mt-1.5 shrink-0" />
                          <div>
                            <p className="font-semibold text-emerald-300">Cập nhật Trạng thái: {detail.status}</p>
                            <p className="text-slate-400 text-[11px]">{formatDateTime(detail.resolved_at)}</p>
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

        {/* 5 NÚT THAO TÁC CỐ ĐỊNH Ở ĐÁY MODAL (SPEC 08 FIXED ACTION BUTTONS) */}
        <div className="border-t border-slate-800 px-6 py-4 bg-slate-950/80 flex flex-wrap items-center justify-between gap-3">
          <div className="flex flex-wrap items-center gap-2">
            <Button
              size="sm"
              variant="outline"
              disabled={!detail}
              onClick={handleTraceLineage}
              className="border-cyan-600/50 text-cyan-300 hover:bg-cyan-950/30 text-xs disabled:opacity-50 gap-1.5"
            >
              <GitFork className="size-3.5" />
              <span>Trace lineage</span>
            </Button>

            {/* Button 1: Yêu cầu AI giải thích */}
            <Button
              size="sm"
              onClick={handleAskAIExplain}
              disabled={isAILoading}
              className="bg-indigo-600 hover:bg-indigo-500 text-white font-semibold text-xs gap-1.5"
            >
              {isAILoading ? <Loader2 className="size-3.5 animate-spin" /> : <Sparkles className="size-3.5" />}
              <span>1. {isAILoading ? 'Đang phân tích…' : 'Yêu cầu AI Giải thích'}</span>
            </Button>

            {/* Button 2: remediation analysis, never rule creation */}
            <Button
              size="sm"
              disabled={isAILoading}
              onClick={() => aiAnalysis ? setActiveTab('overview') : handleAskAIExplain()}
              className="bg-cyan-600 hover:bg-cyan-500 text-white font-semibold text-xs gap-1.5"
            >
              <Wand2 className="size-3.5" />
              <span>2. Phân tích Remediation</span>
            </Button>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            {/* Button 3: Khắc phục & Reprocess */}
            <Button
              size="sm"
              variant="outline"
              disabled={isAuditor}
              onClick={() => setShowRemediateModal(true)}
              className="border-emerald-600/50 text-emerald-400 hover:bg-emerald-950/30 text-xs disabled:opacity-50 gap-1.5"
            >
              <RefreshCw className="size-3.5" />
              <span>3. Khắc phục & Chạy lại</span>
            </Button>

            {/* Button 4: Phê duyệt Ngoại lệ */}
            <Button
              size="sm"
              variant="outline"
              disabled={isAuditor}
              onClick={() => setShowOverrideModal(true)}
              className="border-amber-600/50 text-amber-400 hover:bg-amber-950/30 text-xs disabled:opacity-50 gap-1.5"
            >
              <ShieldCheck className="size-3.5" />
              <span>4. Phê duyệt Ngoại lệ (Override)</span>
            </Button>

            {/* Button 5: Chuyển trạng thái */}
            <Button
              size="sm"
              disabled={isAuditor || isUpdatingStatus}
              onClick={handleToggleStatus}
              className="bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 text-xs disabled:opacity-50 gap-1.5"
            >
              <CheckCheck className="size-3.5 text-cyan-400" />
              <span>5. {detail?.status === 'OPEN' ? 'Chuyển Xem xét' : 'Đóng Vấn đề'}</span>
            </Button>
          </div>
        </div>
      </div>

      {/* Strict HITL confirmation: approval records a decision but does not execute it. */}
      {remediationDecision && aiAnalysis?.remediation && (
        <div className="fixed inset-0 z-60 flex items-center justify-center bg-black/70 p-4">
          <div className="w-full max-w-md rounded-2xl border border-cyan-500/30 bg-slate-900 p-6 space-y-4 shadow-2xl">
            <h3 className="text-sm font-bold text-white">
              {remediationDecision === 'approve' ? 'Approve AI recommendation?' : 'Reject AI recommendation?'}
            </h3>
            <div className="rounded-xl border border-slate-700 bg-slate-950 p-3 space-y-2 text-xs">
              <p className="text-slate-400">Bạn đang {remediationDecision === 'approve' ? 'phê duyệt' : 'từ chối'}:</p>
              <p className="font-mono text-sm font-semibold text-cyan-200">{aiAnalysis.remediation.action}</p>
              <p className="text-slate-400">Scope:</p>
              <p className="font-semibold text-white">
                {aiAnalysis.remediation.scope.affected_records} quarantined records
              </p>
              <p className="font-mono text-[11px] text-slate-400">
                {aiAnalysis.remediation.scope.dataset_id} · {aiAnalysis.remediation.scope.run_id}
              </p>
            </div>
            <textarea
              rows={3}
              value={decisionComment}
              onChange={(event) => setDecisionComment(event.target.value)}
              placeholder="Ghi chú quyết định (không bắt buộc)"
              className="w-full rounded-xl border border-slate-700 bg-slate-800 p-3 text-xs text-white focus:border-cyan-500 focus:outline-none"
            />
            {aiActionError && <p className="text-xs text-rose-300">{aiActionError}</p>}
            <div className="flex justify-end gap-2">
              <Button size="sm" variant="outline" disabled={isDeciding} onClick={() => setRemediationDecision(null)}>
                Cancel
              </Button>
              <Button
                size="sm"
                disabled={isDeciding}
                onClick={handleRemediationDecision}
                className={remediationDecision === 'approve' ? 'bg-cyan-600 hover:bg-cyan-500' : 'bg-rose-600 hover:bg-rose-500'}
              >
                {isDeciding && <Loader2 className="mr-1 size-3.5 animate-spin" />}
                {remediationDecision === 'approve' ? 'Approve' : 'Reject'}
              </Button>
            </div>
            {remediationDecision === 'approve' && (
              <p className="text-[11px] text-amber-300">Phê duyệt chỉ chuyển trạng thái sang Pending execution; không tự thực thi remediation.</p>
            )}
          </div>
        </div>
      )}

      {/* OVERRIDE JUSTIFICATION MODAL */}
      {showOverrideModal && (
        <div className="fixed inset-0 z-60 flex items-center justify-center bg-black/70 p-4">
          <div className="w-full max-w-md rounded-2xl border border-slate-700 bg-slate-900 p-6 space-y-4">
            <h3 className="text-sm font-bold text-white flex items-center gap-2">
              <ShieldCheck className="size-4 text-amber-400" />
              Phê duyệt Ngoại lệ Kiểm toán (Audit Override)
            </h3>
            <p className="text-xs text-slate-400">
              Nhập giải trình lý do nghiệp vụ cho phép bản ghi này được thông qua (ghi vĩnh viễn vào nhật ký kiểm toán):
            </p>
            <textarea
              rows={3}
              value={overrideJustification}
              onChange={(e) => setOverrideJustification(e.target.value)}
              placeholder="Giải trình kiểm toán: Cuốc xe thử nghiệm nội bộ hoặc có chứng từ hợp lệ..."
              className="w-full rounded-xl border border-slate-700 bg-slate-800 p-3 text-xs text-white focus:outline-none focus:border-cyan-500"
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
        <div className="fixed inset-0 z-60 flex items-center justify-center bg-black/70 p-4">
          <div className="w-full max-w-lg rounded-2xl border border-slate-700 bg-slate-900 p-6 space-y-4">
            <h3 className="text-sm font-bold text-white flex items-center gap-2">
              <RefreshCw className="size-4 text-emerald-400" />
              Khắc phục & Chạy lại Dữ liệu Cách ly (Remediate)
            </h3>
            <p className="text-xs text-slate-400">
              Chỉnh sửa giá trị vi phạm trong JSON bên dưới trước khi đưa lại vào luồng xử lý:
            </p>
            <textarea
              rows={7}
              value={cleanedPayloadStr}
              onChange={(e) => setCleanedPayloadStr(e.target.value)}
              className="w-full rounded-xl border border-slate-700 bg-slate-800 p-3 font-mono text-xs text-cyan-300 focus:outline-none focus:border-cyan-500"
            />
            <div className="flex justify-end gap-2 pt-2">
              <Button size="sm" variant="outline" onClick={() => setShowRemediateModal(false)}>
                Hủy
              </Button>
              <Button size="sm" onClick={handleExecuteRemediate} className="bg-emerald-500 text-slate-950 font-bold hover:bg-emerald-400">
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
