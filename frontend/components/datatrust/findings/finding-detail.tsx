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
  AlertTriangle
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

  const handleTraceLineage = () => {
    if (!detail) return;
    const searchParams = new URLSearchParams({
      dataset: detail.dataset_id,
      run_id: detail.run_id,
    });
    navigate(`/lineage?${searchParams.toString()}`);
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
                            <span className="rounded-full bg-teal-50 border border-teal-200 px-2.5 py-0.5 text-[10px] font-bold text-teal-800">
                              AI Confidence {Math.round(aiAnalysis.confidence <= 1 ? aiAnalysis.confidence * 100 : aiAnalysis.confidence)}%
                            </span>
                          )}
                        </div>

                        <p className="text-xs text-slate-700 leading-relaxed">
                          {aiAnalysis?.explanation ||
                            (detail.column_name.includes('lat')
                              ? `Giá trị ${detail.column_name} (21.010083) nằm ngoài vùng địa lý được phép hoạt động của đội xe tại Berlin (EU). Điều này vi phạm yêu cầu về tính chính xác dữ liệu (${detail.law_ref || 'GDPR Art. 5'}) và có thể do:`
                              : `Quy tắc kiểm soát chất lượng dữ liệu phát hiện giá trị bất thường tại cột ${detail.column_name} không thỏa mãn điều kiện kiểm soát chính sách ${detail.policy_name || 'chất lượng dữ liệu'}. Các nguyên nhân có thể gồm:`)}
                        </p>

                        {/* Numbered Diagnostic Steps */}
                        <div className="space-y-2.5 pt-1">
                          <div className="flex items-start gap-3">
                            <span className="grid size-5.5 place-items-center rounded-full bg-blue-100 text-blue-700 font-bold text-[11px] shrink-0 mt-0.5">
                              1
                            </span>
                            <p className="text-xs text-slate-700 pt-0.5">
                              {aiAnalysis?.root_cause
                                ? aiAnalysis.root_cause
                                : 'Dữ liệu GPS hoặc cảm biến sai lệch hoặc thiếu độ chính xác thực tế'}
                            </p>
                          </div>

                          <div className="flex items-start gap-3">
                            <span className="grid size-5.5 place-items-center rounded-full bg-blue-100 text-blue-700 font-bold text-[11px] shrink-0 mt-0.5">
                              2
                            </span>
                            <p className="text-xs text-slate-700 pt-0.5">
                              Lỗi đồng bộ hoặc trôi dữ liệu từ thiết bị đầu cuối → hệ thống thu thập tập trung
                            </p>
                          </div>

                          <div className="flex items-start gap-3">
                            <span className="grid size-5.5 place-items-center rounded-full bg-blue-100 text-blue-700 font-bold text-[11px] shrink-0 mt-0.5">
                              3
                            </span>
                            <p className="text-xs text-slate-700 pt-0.5">
                              Bản ghi bị gán nhầm quy tắc kiểm định, đội xe hoặc phân vùng tài phán hoạt động
                            </p>
                          </div>
                        </div>

                        {/* AI issues if available */}
                        {aiAnalysis?.issues && aiAnalysis.issues.length > 0 && (
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
                  {/* TAB 3: REMEDIATION PROPOSAL                             */}
                  {/* ======================================================= */}
                  {activeTab === 'remediation' && (
                    <div className="space-y-4 text-xs">
                      {aiAnalysis?.remediation ? (
                        <div className="rounded-2xl border border-teal-200/90 bg-teal-50/30 p-5 space-y-4 shadow-2xs">
                          <div className="flex items-center justify-between gap-2">
                            <div className="flex items-center gap-2">
                              <Wand2 className="size-4 text-teal-600" />
                              <h4 className="font-bold text-teal-950 text-sm">Đề xuất Xử lý (Remediation)</h4>
                            </div>
                            <span className="rounded-full bg-teal-100 text-teal-800 border border-teal-200 px-2.5 py-0.5 text-[10px] font-bold uppercase">
                              {aiAnalysis.remediation.status === 'pending_execution'
                                ? 'Approved → Pending execution'
                                : aiAnalysis.remediation.status}
                            </span>
                          </div>

                          <div className="space-y-1">
                            <span className="text-[10px] font-bold uppercase text-slate-400">Hành động khắc phục:</span>
                            <p className="font-mono text-xs font-semibold text-slate-900 bg-white p-3 rounded-xl border border-slate-200">
                              {aiAnalysis.remediation.action}
                            </p>
                          </div>

                          <div className="space-y-1">
                            <span className="text-[10px] font-bold uppercase text-slate-400">Giải trình căn cứ:</span>
                            <p className="text-slate-700 leading-relaxed bg-white p-3 rounded-xl border border-slate-200">
                              {aiAnalysis.remediation.rationale}
                            </p>
                          </div>

                          <p className="text-[11px] text-slate-500">
                            Phạm vi: <strong>{aiAnalysis.remediation.scope.affected_records} bản ghi</strong> · Dataset: <code className="font-mono">{aiAnalysis.remediation.scope.dataset_id}</code>
                          </p>

                          {aiAnalysis.remediation.status === 'suggested' && (
                            <div className="flex justify-end gap-2 pt-2 border-t border-teal-100">
                              <Button
                                size="sm"
                                variant="outline"
                                disabled={isAuditor}
                                onClick={() => setRemediationDecision('reject')}
                                className="text-xs"
                              >
                                Từ chối đề xuất
                              </Button>
                              <Button
                                size="sm"
                                disabled={isAuditor}
                                onClick={() => setRemediationDecision('approve')}
                                className="bg-teal-600 hover:bg-teal-700 text-white text-xs font-bold"
                              >
                                Phê duyệt đề xuất
                              </Button>
                            </div>
                          )}
                        </div>
                      ) : (
                        <div className="p-8 text-center text-xs text-slate-500 rounded-2xl border border-slate-200 bg-slate-50/50 space-y-3">
                          <p>Chưa có đề xuất Remediation tự động từ AI Companion cho Finding này.</p>
                          <Button
                            size="sm"
                            onClick={handleAskAIExplain}
                            disabled={isAILoading}
                            className="bg-teal-600 hover:bg-teal-700 text-white text-xs font-bold gap-1.5"
                          >
                            <Sparkles size={13} />
                            <span>Yêu cầu AI phân tích Remediation ngay</span>
                          </Button>
                        </div>
                      )}
                    </div>
                  )}

                  {/* ======================================================= */}
                  {/* TAB 4: LINEAGE CONTEXT                                  */}
                  {/* ======================================================= */}
                  {activeTab === 'lineage' && (
                    <div className="space-y-4 text-xs">
                      <div className="rounded-2xl border border-slate-200 bg-white p-5 space-y-3 shadow-2xs">
                        <div className="flex items-center gap-2">
                          <GitFork className="size-4 text-slate-700" />
                          <h4 className="font-bold text-slate-900 text-sm">Truy vết Dòng dữ liệu (Lineage)</h4>
                        </div>
                        <p className="text-xs text-slate-600 leading-relaxed">
                          Finding này thuộc lượt chạy kiểm toán <strong className="font-mono text-slate-900">{detail.run_id}</strong> trên bảng <strong className="text-slate-900">{detail.dataset_id}</strong>, liên quan đến cột <strong className="font-mono text-teal-700">{detail.column_name}</strong>.
                        </p>
                        <div className="pt-2">
                          <Button
                            size="sm"
                            onClick={handleTraceLineage}
                            className="bg-slate-900 text-white text-xs font-bold hover:bg-slate-800 gap-1.5 cursor-pointer"
                          >
                            <GitFork size={13} />
                            <span>Mở màn hình Lineage chi tiết</span>
                          </Button>
                        </div>
                      </div>
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
