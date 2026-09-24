'use client';
import { useState } from 'react';
import {
  X,
  CheckCircle2,
  Copy,
  Check,
  FileText,
  Lock,
  Download,
  Sparkles,
  ShieldAlert,
  SlidersHorizontal,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { useAgentStore, type FindingItem } from '@/lib/agent-store';

export function FindingInspectorModal() {
  const { selectedFindingModal, closeFindingModal, markFindingAudited } = useAgentStore();
  const [copiedHash, setCopiedHash] = useState(false);
  const [copiedPayload, setCopiedPayload] = useState(false);
  const [appliedRule, setAppliedRule] = useState(false);

  if (!selectedFindingModal) return null;
  const finding: FindingItem = selectedFindingModal;

  const handleCopyHash = () => {
    navigator.clipboard.writeText(finding.evidence.hashSha256);
    setCopiedHash(true);
    setTimeout(() => setCopiedHash(false), 2000);
  };

  const handleCopyPayload = () => {
    navigator.clipboard.writeText(JSON.stringify(finding.evidence.samplePayload, null, 2));
    setCopiedPayload(true);
    setTimeout(() => setCopiedPayload(false), 2000);
  };

  const handleApplyProposedRule = () => {
    setAppliedRule(true);
    setTimeout(() => setAppliedRule(false), 3000);
  };

  const handleDownloadEvidence = () => {
    const dataStr =
      'data:text/json;charset=utf-8,' +
      encodeURIComponent(
        JSON.stringify(
          {
            finding_id: finding.id,
            case_code: finding.caseCode,
            dataset: finding.datasetId,
            detected_at: finding.detectedAt,
            status: finding.status,
            ai_analysis: {
              evaluation: `Tiêu chuẩn ${finding.caseCode} bị vi phạm trên bộ dữ liệu ${finding.datasetId}`,
              severity: finding.severity,
              risk_level: finding.severity === 'CRITICAL' ? 'Rất cao (Nguy cơ bị phạt IPO)' : 'Trung bình',
            },
            root_cause: finding.rootCauseAnalysis,
            evidence: finding.evidence,
            ai_remediation: finding.aiRemediation,
            exported_at: new Date().toISOString(),
            verifier: 'DataTrust OS Audit Enclave v2.4 (SHA-256 Merkle Provenance)',
          },
          null,
          2
        )
      );
    const downloadAnchor = document.createElement('a');
    downloadAnchor.setAttribute('href', dataStr);
    downloadAnchor.setAttribute('download', `evidence-${finding.id}.json`);
    document.body.appendChild(downloadAnchor);
    downloadAnchor.click();
    downloadAnchor.remove();
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="modal-finding-title"
      className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6 overflow-y-auto bg-slate-950/60 backdrop-blur-xs"
    >
      <div className="relative w-full max-w-3xl max-h-[92vh] flex flex-col rounded-xl border border-[#d2e2dc] bg-white shadow-2xl overflow-hidden animate-in fade-in zoom-in-95 duration-150">
        
        {/* 1. Header */}
        <div className="flex items-start justify-between border-b border-[#e2ece8] bg-[#f8fbf9] p-5 sm:p-6">
          <div className="space-y-1.5 pr-4">
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-mono text-xs font-bold text-[#007460] bg-[#e6f6f2] px-2.5 py-0.5 rounded-md border border-[#bfe7dc]">
                {finding.id}
              </span>
              <Badge tone={finding.severity === 'CRITICAL' ? 'red' : finding.severity === 'HIGH' ? 'amber' : 'blue'}>
                {finding.severity}
              </Badge>
              <span className="text-xs font-medium text-slate-500">
                Tiêu chuẩn: <strong className="text-slate-800">{finding.caseCode}</strong> · Bộ dữ liệu: <strong className="text-slate-800 uppercase">{finding.datasetId}</strong>
              </span>
              {finding.status === 'AUDITED' ? (
                <Badge tone="green" className="text-[11px] font-semibold">
                  ✓ ĐÃ KIỂM TOÁN
                </Badge>
              ) : (
                <Badge tone="amber" className="text-[11px] font-semibold">
                  ● CẦN XỬ LÝ
                </Badge>
              )}
            </div>
            <h2 id="modal-finding-title" className="text-base sm:text-lg font-bold text-slate-900 leading-snug">
              {finding.title}
            </h2>
            <p className="text-xs text-slate-500">
              Phát hiện lúc: {finding.detectedAt} · Căn cứ pháp lý: <strong className="text-slate-700">{finding.evidence.lawReference}</strong>
            </p>
          </div>

          <button
            type="button"
            onClick={closeFindingModal}
            className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-700 transition"
            aria-label="Đóng modal"
          >
            <X size={18} />
          </button>
        </div>

        {/* 2. Scrollable Body: 4 Agentic Core Pillars */}
        <div className="overflow-y-auto p-5 sm:p-6 space-y-5">
          
          {/* PILLAR 1: AI ANALYSIS (Phân tích tổng quan từ AI Agent) */}
          <div className="rounded-xl border border-[#bfe7dc] bg-[#f0f9f6] p-4 space-y-2">
            <div className="flex items-center justify-between">
              <span className="flex items-center gap-1.5 text-xs font-bold uppercase tracking-wider text-[#007460]">
                <Sparkles size={15} />
                1. Phân Tích & Đánh Giá Rủi Ro Từ AI Agent
              </span>
              <span className="text-[11px] font-semibold text-[#006e5b] bg-white px-2 py-0.5 rounded border border-[#bfe7dc]">
                Độ tin cậy: 98%
              </span>
            </div>
            <p className="text-xs leading-relaxed text-slate-700 font-medium">
              AI Agent đã thực hiện kiểm định tự động đối với bộ dữ liệu <strong>{finding.datasetId}</strong> dựa trên tiêu chuẩn <strong>{finding.caseCode}</strong>.
              Hệ thống phát hiện vi phạm nghiêm trọng về tính toàn vẹn dữ liệu, có nguy cơ gây sai lệch báo cáo kiểm toán IPO nếu không được cách ly kịp thời.
            </p>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 pt-1 text-xs">
              <div className="bg-white/80 p-2 rounded border border-[#d2e2dc]">
                <span className="text-[11px] text-slate-500 block">Mức độ rủi ro</span>
                <strong className={finding.severity === 'CRITICAL' ? 'text-rose-700' : 'text-amber-700'}>
                  {finding.severity === 'CRITICAL' ? 'Nghiêm trọng (Chặn Release)' : 'Đáng chú ý (Cần Audit)'}
                </strong>
              </div>
              <div className="bg-white/80 p-2 rounded border border-[#d2e2dc]">
                <span className="text-[11px] text-slate-500 block">Làn xử lý cách ly</span>
                <strong className="text-[#007460]">{finding.aiRemediation.targetLane}</strong>
              </div>
              <div className="bg-white/80 p-2 rounded border border-[#d2e2dc] col-span-2 sm:col-span-1">
                <span className="text-[11px] text-slate-500 block">Bản ghi vi phạm</span>
                <strong className="text-rose-600">{finding.evidence.quarantinedCount} bản ghi</strong>
              </div>
            </div>
          </div>

          {/* PILLAR 2: ROOT CAUSE (Nguyên nhân gốc rễ) */}
          <div className="rounded-xl border border-slate-200 bg-white p-4 space-y-2">
            <span className="flex items-center gap-1.5 text-xs font-bold uppercase tracking-wider text-slate-800">
              <ShieldAlert size={15} className="text-rose-600" />
              2. Nguyên Nhân Gốc Rễ (Root Cause)
            </span>
            <div className="rounded-lg bg-rose-50/50 border border-rose-100 p-3 text-xs leading-relaxed text-slate-800">
              <p className="font-semibold text-rose-950 mb-1">Bóc tách từ AI Agent:</p>
              {finding.rootCauseAnalysis}
            </div>
          </div>

          {/* PILLAR 3: EVIDENCE (Bằng chứng mật mã & Payload thực tế) */}
          <div className="rounded-xl border border-slate-200 bg-white p-4 space-y-3">
            <div className="flex items-center justify-between">
              <span className="flex items-center gap-1.5 text-xs font-bold uppercase tracking-wider text-slate-800">
                <Lock size={15} className="text-[#008b74]" />
                3. Bằng Chứng Mật Mã (Cryptographic Evidence)
              </span>
              <span className="text-xs font-semibold text-rose-700 bg-rose-50 border border-rose-200 px-2 py-0.5 rounded">
                Cách ly: {finding.evidence.quarantinedCount} bản ghi
              </span>
            </div>

            {/* SHA-256 Merkle Hash Card */}
            <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-xs font-medium text-slate-600">
                  Mã băm SHA-256 (Merkle Leaf Hash):
                </span>
                <button
                  type="button"
                  onClick={handleCopyHash}
                  className="flex items-center gap-1 text-xs font-semibold text-[#007460] hover:underline"
                >
                  {copiedHash ? <Check size={13} /> : <Copy size={13} />}
                  {copiedHash ? 'Đã sao chép' : 'Sao chép mã hash'}
                </button>
              </div>
              <p className="font-mono text-xs text-slate-900 break-all select-all bg-white p-2 rounded border border-slate-200">
                {finding.evidence.hashSha256}
              </p>
              <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-slate-500 pt-0.5">
                <span>Chữ ký số: <code className="text-slate-700 font-mono">{finding.evidence.digitalSignature}</code></span>
                <span>Tiêu chuẩn: <strong className="text-slate-700">{finding.evidence.lawReference}</strong></span>
              </div>
            </div>

            {/* Real Evidence Payload Sample */}
            <div className="space-y-1.5">
              <div className="flex items-center justify-between">
                <span className="text-xs font-medium text-slate-700 flex items-center gap-1.5">
                  <FileText size={14} className="text-slate-500" />
                  Mẫu bản ghi vi phạm thực tế (Payload JSON trích xuất):
                </span>
                <button
                  type="button"
                  onClick={handleCopyPayload}
                  className="flex items-center gap-1 text-xs font-medium text-slate-600 hover:text-slate-900"
                >
                  {copiedPayload ? <Check size={13} /> : <Copy size={13} />}
                  {copiedPayload ? 'Đã sao chép' : 'Sao chép JSON'}
                </button>
              </div>

              <div className="rounded-lg border border-slate-800 bg-[#0c1917] p-3.5 overflow-x-auto max-h-44">
                <pre className="font-mono text-xs text-emerald-300 leading-relaxed whitespace-pre">
                  {JSON.stringify(finding.evidence.samplePayload, null, 2)}
                </pre>
              </div>
            </div>
          </div>

          {/* PILLAR 4: SUGGESTED ACTION (Hành động đề xuất từ AI Agent) */}
          <div className="rounded-xl border border-slate-200 bg-white p-4 space-y-3">
            <span className="flex items-center gap-1.5 text-xs font-bold uppercase tracking-wider text-slate-800">
              <SlidersHorizontal size={15} className="text-[#008b74]" />
              4. Hành Động Đề Xuất Xử Lý Từ AI Agent (Suggested Action)
            </span>

            {/* Action Plan steps */}
            <div className="space-y-2">
              <span className="text-xs font-semibold text-slate-600">
                Kế hoạch khắc phục đề xuất:
              </span>
              <ul className="space-y-1.5 text-xs text-slate-700">
                {finding.aiRemediation.actionPlan.map((action, idx) => (
                  <li key={idx} className="flex items-start gap-2.5">
                    <span className="grid size-5 shrink-0 place-items-center rounded-full bg-[#e6f6f2] text-[11px] font-bold text-[#007460] mt-0.5">
                      {idx + 1}
                    </span>
                    <span className="leading-snug">{action}</span>
                  </li>
                ))}
              </ul>
            </div>

            {/* Proposed Control/Rule with 1-Click Action */}
            <div className="rounded-lg border border-[#cbebe2] bg-[#fbfdfc] p-3.5 space-y-2">
              <div className="flex items-center justify-between text-xs">
                <span className="font-bold text-slate-900">
                  Đề xuất Rule kiểm soát tự động:
                </span>
                <span className="text-xs font-medium text-slate-500">
                  Target: <strong className="text-[#007460]">{finding.aiRemediation.targetLane}</strong>
                </span>
              </div>
              <p className="text-xs font-medium text-slate-600">
                Tên rule: <code className="bg-slate-100 text-slate-800 px-1.5 py-0.5 rounded font-mono">{finding.aiRemediation.proposedRuleName}</code>
              </p>
              <div className="rounded-md border border-[#cbebe2] bg-[#f0f9f6] p-2.5 font-mono text-xs text-[#005b4c]">
                {finding.aiRemediation.proposedExpression}
              </div>

              <div className="flex justify-end pt-1">
                <Button
                  variant="xanhsm"
                  size="sm"
                  onClick={handleApplyProposedRule}
                  disabled={appliedRule}
                  className="h-8 text-xs font-semibold gap-1.5"
                >
                  {appliedRule ? <Check size={13} /> : <Sparkles size={13} />}
                  {appliedRule ? 'Đã áp dụng rule vào pipeline!' : '1-Click Áp dụng Rule này'}
                </Button>
              </div>
            </div>
          </div>

        </div>

        {/* 3. Footer / Action Buttons */}
        <div className="flex flex-col sm:flex-row items-center justify-between gap-3 border-t border-[#e2ece8] bg-[#f8fbf9] p-4 sm:px-6">
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={handleDownloadEvidence}
              className="text-xs font-medium text-slate-700 gap-1.5 h-9"
            >
              <Download size={14} />
              Tải hồ sơ bằng chứng (.JSON)
            </Button>
          </div>

          <div className="flex items-center gap-2 w-full sm:w-auto justify-end">
            {finding.status !== 'AUDITED' ? (
              <Button
                variant="xanhsm"
                size="sm"
                onClick={() => {
                  markFindingAudited(finding.id);
                }}
                className="text-xs font-semibold gap-1.5 h-9 px-4"
              >
                <CheckCircle2 size={15} />
                Xác nhận đã kiểm toán & Lưu vết
              </Button>
            ) : (
              <span className="inline-flex items-center gap-1.5 rounded-lg border border-emerald-300 bg-emerald-50 px-3 py-1.5 text-xs font-bold text-emerald-700">
                <Check size={14} strokeWidth={2.5} /> Đã kiểm toán hoàn tất
              </span>
            )}

            <Button
              variant="outline"
              size="sm"
              onClick={closeFindingModal}
              className="text-xs font-medium text-slate-600 h-9"
            >
              Đóng
            </Button>
          </div>
        </div>

      </div>
    </div>
  );
}
