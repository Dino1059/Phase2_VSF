'use client';

import { useState } from 'react';
import {
  ShieldAlert,
  ShieldCheck,
  AlertTriangle,
  ChevronDown,
  ChevronUp,
  Copy,
  Check,
  Database,
  Lock,
  MapPin,
  Scale,
  Info,
} from 'lucide-react';
import {
  formatAuditReasonReport,
  type AuditExecutiveReport,
  type ViolationCategory,
} from '@/lib/formatters/audit-violation-formatter';

interface AuditorViolationCardProps {
  reason: string | undefined | null;
  policyViolations?: any[];
  contextInfo?: {
    ruleId?: string;
    policyName?: string;
    lawRef?: string;
  };
  compact?: boolean;
}

export function AuditorViolationCard({
  reason,
  policyViolations,
  contextInfo,
  compact = false,
}: AuditorViolationCardProps) {
  const [showTechnicalDetails, setShowTechnicalDetails] = useState(false);
  const [copied, setCopied] = useState(false);
  const [activeCategoryFilter, setActiveCategoryFilter] = useState<ViolationCategory | 'ALL'>('ALL');

  const report: AuditExecutiveReport = formatAuditReasonReport(
    reason,
    policyViolations,
    contextInfo
  );

  const handleCopyRaw = () => {
    if (!report.rawLogString) return;
    navigator.clipboard.writeText(report.rawLogString);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const filteredItems = activeCategoryFilter === 'ALL'
    ? report.items
    : report.items.filter((i) => i.category === activeCategoryFilter);

  const categoryCounts = {
    ALL: report.totalViolations,
    PRIVACY: report.byCategory.privacy.length,
    QUALITY: report.byCategory.quality.length,
    LOCATION: report.byCategory.location.length,
    GOVERNANCE: report.byCategory.governance.length,
  };

  // Compact Mode (dành cho danh sách bản ghi cách ly - Sample Records list)
  if (compact) {
    return (
      <div className="rounded-xl border border-rose-200/80 bg-rose-50/30 p-3 space-y-2 text-xs">
        <div className="flex flex-wrap items-center justify-between gap-1.5">
          <div className="flex items-center gap-1.5">
            <span className="text-[10px] text-rose-700 font-extrabold uppercase tracking-wider flex items-center gap-1">
              <ShieldAlert size={13} className="text-rose-600" />
              <span>Lý do cách ly ({report.totalViolations} vi phạm nghiệp vụ):</span>
            </span>
          </div>
          <span className="inline-flex items-center gap-1 text-[10px] font-bold text-emerald-800 bg-emerald-100/90 px-2.5 py-0.5 rounded-full border border-emerald-300 shadow-2xs">
            <ShieldCheck size={11} className="text-emerald-700" />
            <span>Đã cách ly an toàn</span>
          </span>
        </div>

        {/* Compact violation items */}
        <div className="space-y-1.5 pt-1">
          {report.items.map((item, idx) => (
            <div
              key={item.id || idx}
              className="p-2.5 rounded-lg bg-white border border-rose-100/90 text-[11px] space-y-1 shadow-2xs"
            >
              <div className="flex flex-wrap items-center justify-between gap-1.5">
                <div className="flex items-center gap-1.5 flex-wrap">
                  <span className={`px-1.5 py-0.5 rounded text-[9px] font-extrabold border ${item.categoryBadgeClass}`}>
                    {item.categoryLabel}
                  </span>
                  <span className="font-bold text-slate-900 leading-snug">{item.title}</span>
                </div>
                <span className="font-mono text-[10px] font-semibold text-slate-500 bg-slate-50 px-1.5 py-0.5 rounded border border-slate-200">
                  {item.fieldDisplay}
                </span>
              </div>

              <div className="flex flex-wrap items-center gap-x-3 text-[10px] text-slate-600 pt-0.5">
                {item.observedValue && (
                  <span>Giá trị: <strong className="font-mono text-rose-600">{item.observedValue}</strong></span>
                )}
                {item.thresholdOrStandard && (
                  <span>Quy chuẩn: <strong className="text-slate-800">{item.thresholdOrStandard}</strong></span>
                )}
                <span>Căn cứ: <strong className="text-slate-700">{item.legalBasis}</strong></span>
              </div>
            </div>
          ))}
        </div>

        {/* Technical log toggle */}
        <div className="pt-0.5">
          <button
            type="button"
            onClick={() => setShowTechnicalDetails(!showTechnicalDetails)}
            className="flex items-center gap-1 text-[10px] font-bold text-slate-500 hover:text-slate-800 transition-all cursor-pointer"
          >
            {showTechnicalDetails ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
            <span>{showTechnicalDetails ? 'Ẩn log kỹ thuật gốc' : 'Xem log kỹ thuật gốc (Raw Log)'}</span>
          </button>
          {showTechnicalDetails && (
            <div className="mt-1.5 p-2 rounded bg-slate-900 border border-slate-800 text-[10px] font-mono text-slate-300 break-all whitespace-pre-wrap">
              {report.rawLogString || '(Không có chuỗi log)'}
            </div>
          )}
        </div>
      </div>
    );
  }

  // Full Executive Mode (dành cho Tab Overview của Finding Detail)
  return (
    <div className="rounded-2xl border border-rose-200/80 bg-white shadow-xs overflow-hidden transition-all">
      {/* ========================================================================= */}
      {/* 1. AUDITOR EXECUTIVE BANNER & CONTAINMENT STATUS                          */}
      {/* ========================================================================= */}
      <div className="bg-gradient-to-r from-rose-50 via-amber-50/40 to-slate-50 border-b border-rose-100 p-4 sm:p-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2.5">
            <div className="grid size-9 place-items-center rounded-xl bg-rose-600 text-white shadow-xs">
              <ShieldAlert size={18} />
            </div>
            <div>
              <span className="text-[11px] font-extrabold uppercase tracking-wider text-rose-700 block">
                Báo cáo Lý do Vi phạm Ghi nhận (Auditor Executive Report)
              </span>
              <h3 className="text-sm font-bold text-slate-950 mt-0.5">
                Phát hiện {report.totalViolations} điểm vi phạm nghiệp vụ · Đã kích hoạt cơ chế cách ly
              </h3>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold bg-emerald-100 text-emerald-800 border border-emerald-300 shadow-2xs">
              <ShieldCheck size={14} className="text-emerald-700" />
              <span>Đã cách ly an toàn (Quarantined)</span>
            </span>
          </div>
        </div>

        {/* ======================================================================= */}
        {/* 2. 3 CORE AUDIT PILLARS (GIẢI TRÌNH 3 CÂU HỎI TRỌNG YẾU CHO AUDITOR)     */}
        {/* ======================================================================= */}
        <div className="grid gap-3 sm:grid-cols-3 mt-4 pt-4 border-t border-rose-200/60 text-xs">
          {/* Trụ 1: Vi phạm điều gì */}
          <div className="bg-white/80 backdrop-blur-xs p-3.5 rounded-xl border border-rose-100 space-y-1">
            <div className="flex items-center gap-1.5 text-rose-700 font-bold uppercase text-[10px] tracking-wider">
              <AlertTriangle size={13} />
              <span>1. Dữ liệu vi phạm điều gì?</span>
            </div>
            <p className="text-slate-800 font-medium leading-relaxed">
              {report.executiveSummary.whatViolated}
            </p>
          </div>

          {/* Trụ 2: Tại sao bị đánh dấu */}
          <div className="bg-white/80 backdrop-blur-xs p-3.5 rounded-xl border border-amber-100 space-y-1">
            <div className="flex items-center gap-1.5 text-amber-700 font-bold uppercase text-[10px] tracking-wider">
              <Scale size={13} />
              <span>2. Tại sao bị hệ thống đánh dấu?</span>
            </div>
            <p className="text-slate-800 font-medium leading-relaxed">
              {report.executiveSummary.whyFlagged}
            </p>
          </div>

          {/* Trụ 3: Đã được xử lý hay chưa */}
          <div className="bg-white/80 backdrop-blur-xs p-3.5 rounded-xl border border-emerald-100 space-y-1">
            <div className="flex items-center gap-1.5 text-emerald-700 font-bold uppercase text-[10px] tracking-wider">
              <ShieldCheck size={13} />
              <span>3. Đã được xử lý hay chưa?</span>
            </div>
            <p className="text-slate-800 font-semibold leading-relaxed">
              {report.executiveSummary.containmentStatus}
            </p>
          </div>
        </div>
      </div>

      {/* ========================================================================= */}
      {/* 3. CATEGORY FILTER TABS & BADGES                                          */}
      {/* ========================================================================= */}
      <div className="p-4 sm:p-5 space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 pb-3">
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="text-xs font-bold text-slate-500 mr-1">Phân nhóm vi phạm:</span>

            <button
              type="button"
              onClick={() => setActiveCategoryFilter('ALL')}
              className={`px-2.5 py-1 rounded-lg text-xs font-bold transition-all cursor-pointer ${
                activeCategoryFilter === 'ALL'
                  ? 'bg-slate-900 text-white shadow-2xs'
                  : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
              }`}
            >
              Tất cả ({categoryCounts.ALL})
            </button>

            {categoryCounts.PRIVACY > 0 && (
              <button
                type="button"
                onClick={() => setActiveCategoryFilter('PRIVACY')}
                className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-bold transition-all cursor-pointer ${
                  activeCategoryFilter === 'PRIVACY'
                    ? 'bg-purple-700 text-white shadow-2xs'
                    : 'bg-purple-50 text-purple-700 hover:bg-purple-100 border border-purple-200/60'
                }`}
              >
                <Lock size={12} />
                <span>Bảo vệ PII ({categoryCounts.PRIVACY})</span>
              </button>
            )}

            {categoryCounts.QUALITY > 0 && (
              <button
                type="button"
                onClick={() => setActiveCategoryFilter('QUALITY')}
                className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-bold transition-all cursor-pointer ${
                  activeCategoryFilter === 'QUALITY'
                    ? 'bg-emerald-700 text-white shadow-2xs'
                    : 'bg-emerald-50 text-emerald-700 hover:bg-emerald-100 border border-emerald-200/60'
                }`}
              >
                <Database size={12} />
                <span>Chất lượng dữ liệu ({categoryCounts.QUALITY})</span>
              </button>
            )}

            {categoryCounts.LOCATION > 0 && (
              <button
                type="button"
                onClick={() => setActiveCategoryFilter('LOCATION')}
                className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-bold transition-all cursor-pointer ${
                  activeCategoryFilter === 'LOCATION'
                    ? 'bg-amber-700 text-white shadow-2xs'
                    : 'bg-amber-50 text-amber-700 hover:bg-amber-100 border border-amber-200/60'
                }`}
              >
                <MapPin size={12} />
                <span>Vị trí địa lý ({categoryCounts.LOCATION})</span>
              </button>
            )}
          </div>

          <div className="flex items-center gap-2 text-[11px] font-semibold text-slate-500">
            <span>Mức nghiêm trọng:</span>
            {report.criticalCount > 0 && (
              <span className="text-rose-600 font-bold">{report.criticalCount} CRITICAL</span>
            )}
            {report.highCount > 0 && (
              <span className="text-amber-600 font-bold">{report.highCount} HIGH</span>
            )}
          </div>
        </div>

        {/* ======================================================================= */}
        {/* 4. CATEGORIZED VIOLATION CARDS LIST                                     */}
        {/* ======================================================================= */}
        <div className="grid gap-3">
          {filteredItems.map((item, idx) => (
            <div
              key={item.id || idx}
              className="rounded-xl border border-slate-200/90 bg-white p-4 space-y-3 hover:border-slate-300 transition-all shadow-2xs"
            >
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div className="space-y-1 max-w-2xl">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className={`inline-flex items-center px-2 py-0.5 rounded text-[10px] font-extrabold border ${item.categoryBadgeClass}`}>
                      {item.categoryLabel}
                    </span>

                    <span
                      className={`inline-flex items-center px-2 py-0.5 rounded text-[10px] font-bold ${
                        item.severity === 'CRITICAL'
                          ? 'bg-rose-100 text-rose-800 border border-rose-300'
                          : item.severity === 'HIGH'
                          ? 'bg-amber-100 text-amber-800 border border-amber-300'
                          : 'bg-yellow-100 text-yellow-800 border border-yellow-300'
                      }`}
                    >
                      {item.severity}
                    </span>

                    <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-medium bg-slate-100 text-slate-700 border border-slate-200">
                      Giai đoạn: {item.detectionPhaseLabel}
                    </span>
                  </div>

                  <h4 className="text-sm font-bold text-slate-900 leading-snug">
                    {item.title}
                  </h4>
                </div>

                <span className="text-[11px] font-mono font-semibold text-slate-500 bg-slate-50 px-2.5 py-1 rounded-md border border-slate-200">
                  {item.fieldDisplay}
                </span>
              </div>

              {/* Chi tiết Giá trị thực tế & Quy định chuẩn */}
              <div className="grid gap-2 sm:grid-cols-2 bg-slate-50/70 p-3 rounded-lg border border-slate-100 text-xs">
                <div>
                  <span className="text-[10px] font-bold uppercase text-slate-400 block tracking-wider">
                    Giá trị ghi nhận thực tế:
                  </span>
                  <p className="font-mono font-bold text-rose-600 mt-0.5">
                    {item.observedValue || '—'}
                  </p>
                </div>
                <div>
                  <span className="text-[10px] font-bold uppercase text-slate-400 block tracking-wider">
                    Quy chuẩn tuân thủ bắt buộc:
                  </span>
                  <p className="font-semibold text-slate-800 mt-0.5">
                    {item.thresholdOrStandard || '—'}
                  </p>
                </div>
              </div>

              {/* Ngữ cảnh Rule & Pháp lý */}
              <div className="flex flex-wrap items-center justify-between gap-2 pt-1 text-[11px] text-slate-600 border-t border-slate-100">
                <div className="flex flex-wrap items-center gap-3">
                  <span>
                    Mã quy tắc: <strong className="font-mono text-slate-800">{item.relatedRuleId}</strong>
                  </span>
                  <span>·</span>
                  <span>
                    Căn cứ pháp lý: <strong className="text-slate-800">{item.legalBasis}</strong>
                  </span>
                </div>

                <span className="text-[11px] font-bold text-emerald-700 flex items-center gap-1">
                  <ShieldCheck size={13} />
                  <span>{item.containmentStatus}</span>
                </span>
              </div>
            </div>
          ))}
        </div>

        {/* ======================================================================= */}
        {/* 5. COLLAPSIBLE RAW TECHNICAL LOGS (DÀNH CHO DATA ENGINEER / AUDITOR SÂU) */}
        {/* ======================================================================= */}
        <div className="border-t border-slate-200 pt-3">
          <button
            type="button"
            onClick={() => setShowTechnicalDetails(!showTechnicalDetails)}
            className="flex items-center justify-between w-full p-2.5 text-xs font-bold text-slate-600 hover:text-slate-900 hover:bg-slate-50 rounded-lg transition-all cursor-pointer"
          >
            <span className="flex items-center gap-2">
              <Info size={14} className="text-slate-400" />
              <span>Xem chi tiết log kỹ thuật gốc (Raw Technical Details)</span>
            </span>
            {showTechnicalDetails ? <ChevronUp size={15} /> : <ChevronDown size={15} />}
          </button>

          {showTechnicalDetails && (
            <div className="mt-2 p-3.5 rounded-xl bg-slate-900 border border-slate-800 text-slate-200 font-mono text-[11px] space-y-2">
              <div className="flex items-center justify-between pb-2 border-b border-slate-800">
                <span className="text-[10px] text-slate-400 uppercase tracking-wider font-bold">
                  Raw Semicolon-Separated Failure Log:
                </span>
                <button
                  type="button"
                  onClick={handleCopyRaw}
                  className="flex items-center gap-1 text-[10px] px-2 py-0.5 rounded bg-slate-800 text-slate-300 hover:bg-slate-700 transition-all cursor-pointer"
                >
                  {copied ? <Check size={12} className="text-emerald-400" /> : <Copy size={12} />}
                  <span>{copied ? 'Đã sao chép' : 'Sao chép chuỗi log'}</span>
                </button>
              </div>
              <p className="break-all leading-relaxed whitespace-pre-wrap text-slate-300">
                {report.rawLogString || '(Không có chuỗi log kỹ thuật)'}
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
