'use client';
import { useState } from 'react';
import { Link } from 'react-router-dom';
import {
  ArrowRight,
  Check,
  CheckCircle2,
  Clock,
  Eye,
  FlaskConical,
  RotateCcw,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  X,
} from 'lucide-react';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { useAgentStore, type ProposedRule, type FindingItem } from '@/lib/agent-store';

export function SlideDownDashboard() {
  const {
    currentRole,
    selectedDatasetId,
    datasets,
    complianceCases,
    approveRule,
    rejectRule,
    simulateDryRun,
    openFindingModal,
    resetHomepageFlow,
  } = useAgentStore();

  const dataset = datasets[selectedDatasetId] || datasets.trips;
  const cases = complianceCases.filter((c) => c.datasetId === selectedDatasetId);
  const failedCases = cases.filter((c) => c.status === 'failed');

  const [testingRuleId, setTestingRuleId] = useState<string | null>(null);

  const handleDryRun = async (ruleId: string) => {
    setTestingRuleId(ruleId);
    await simulateDryRun(ruleId);
    setTestingRuleId(null);
  };

  return (
    <div className="space-y-5 animate-in fade-in-50 slide-in-from-top-6 duration-500">
      {/* Top Completion Banner */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between rounded-xl border border-[#04D3D4]/30 bg-gradient-to-r from-[#04D3D4]/10 via-[#FFC402]/10 to-white p-4 shadow-xs">
        <div className="flex items-center gap-3">
          <div className="grid size-10 place-items-center rounded-xl bg-[#04D3D4] text-slate-950 font-bold shadow-xs">
            <ShieldCheck size={22} />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-sm font-bold text-slate-900">
                {currentRole === 'auditor'
                  ? 'Dashboard Kết Quả Kiểm Tra Tuân Thủ & Bằng Chứng'
                  : 'Dashboard Kết Quả Kiểm Tra & Đề Xuất Giải Pháp (HITL)'}
              </h2>
              <span className="rounded-full bg-[#04D3D4]/20 border border-[#04D3D4]/40 px-2 py-0.5 text-[10px] font-extrabold text-slate-950">
                L1-L4 Hoàn tất
              </span>
            </div>
            <p className="mt-0.5 text-xs text-slate-600">
              Đã kiểm tra bộ dữ liệu <strong className="font-mono text-slate-900">{dataset.title}</strong> · Đối chiếu chuẩn SOX 404, IFRS 15 & Nghị định 13/2023
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <Button
            onClick={resetHomepageFlow}
            variant="outline"
            size="sm"
            className="h-8 gap-1.5 border-slate-200 bg-white text-xs font-semibold text-slate-600 hover:border-slate-300"
          >
            <RotateCcw size={13} />
            <span>Chạy lần khác</span>
          </Button>

          <Link to="/results">
            <Button
              size="sm"
              className="h-8 gap-1.5 bg-[#04D3D4] text-xs font-bold text-slate-950 hover:bg-[#03b8b9] shadow-xs"
            >
              <span>Xem toàn bộ Findings</span>
              <ArrowRight size={13} />
            </Button>
          </Link>
        </div>
      </div>

      {/* KPI Stats Bar */}
      <div
        className={`grid gap-3 ${
          currentRole === 'auditor' ? 'grid-cols-1 sm:grid-cols-3' : 'grid-cols-2 sm:grid-cols-4'
        }`}
      >
        <Card className="rounded-xl border border-slate-200 bg-white p-3.5 shadow-2xs">
          <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wide">
            Tổng bản ghi
          </span>
          <div className="mt-1 text-xl font-bold text-slate-900">
            {dataset.records.toLocaleString()}
          </div>
          <span className="text-[10px] text-emerald-600 font-medium">100% đã quét L1-L4</span>
        </Card>

        <Card className="rounded-xl border border-slate-200 bg-white p-3.5 shadow-2xs">
          <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wide">
            Hợp lệ (Pass rate)
          </span>
          <div className="mt-1 text-xl font-bold text-emerald-700">
            {((1 - dataset.anomalies / dataset.records) * 100).toFixed(2)}%
          </div>
          <span className="text-[10px] text-slate-500 font-medium">Đạt điều kiện Silver</span>
        </Card>

        <Card className="rounded-xl border border-rose-200 bg-rose-50/40 p-3.5 shadow-2xs">
          <span className="text-[11px] font-semibold text-rose-600 uppercase tracking-wide">
            Phát hiện vi phạm
          </span>
          <div className="mt-1 text-xl font-bold text-rose-700">{dataset.anomalies}</div>
          <span className="text-[10px] text-rose-600 font-medium">Cần cách ly & xử lý</span>
        </Card>

        {currentRole === 'admin' && (
          <Card className="rounded-xl border border-[#04D3D4]/30 bg-[#04D3D4]/10 p-3.5 shadow-2xs">
            <span className="text-[11px] font-bold text-slate-800 uppercase tracking-wide">
              Rule AI đề xuất
            </span>
            <div className="mt-1 text-xl font-bold text-slate-950">
              {dataset.proposedRules.length}
            </div>
            <span className="text-[10px] text-amber-800 font-semibold">Chờ Human duyệt (HITL)</span>
          </Card>
        )}
      </div>

      {/* Section 1: Failed Findings (Phát hiện vi phạm) */}
      <div className="space-y-2.5">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <ShieldAlert size={16} className="text-rose-600" />
            <h3 className="text-xs font-bold text-slate-900 uppercase tracking-wider">
              {currentRole === 'admin' ? '1. ' : ''}Danh sách vi phạm ({failedCases.length} control không đạt)
            </h3>
          </div>
          <span className="text-[11px] text-slate-400">
            Dữ liệu vi phạm đã tự động được cách ly khỏi luồng
          </span>
        </div>

        <div className="grid gap-2">
          {failedCases.map((c) => {
            const finding: FindingItem | undefined = c.findings[0];

            return (
              <div
                key={c.id}
                className="flex flex-col gap-2.5 rounded-xl border border-rose-200/80 bg-white p-3.5 shadow-2xs sm:flex-row sm:items-center sm:justify-between hover:border-rose-300 transition"
              >
                <div className="flex items-center gap-3 min-w-0 flex-1">
                  <span className="rounded-md bg-rose-100 px-2 py-1 font-mono text-[10px] font-extrabold text-rose-800 shrink-0">
                    {c.code}
                  </span>
                  
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2 flex-wrap">
                      <h4 className="text-xs font-bold text-slate-900">
                        {finding ? finding.title : c.name}
                      </h4>
                      <span className="rounded-full bg-rose-50 px-2 py-0.5 text-[10px] font-extrabold text-rose-700 border border-rose-200 shrink-0">
                        Cách ly {finding ? finding.evidence.quarantinedCount : 0} dòng
                      </span>
                    </div>
                    <p className="mt-0.5 text-[11px] text-slate-500">
                      Chuẩn mực: <span className="font-semibold text-slate-700">{c.lawStandard}</span>
                    </p>
                  </div>
                </div>

                <div className="flex items-center gap-2 self-end sm:self-center shrink-0">
                  {finding && (
                    <Button
                      onClick={() => openFindingModal(finding.id)}
                      variant="outline"
                      size="sm"
                      className="h-8 gap-1.5 border-slate-200 text-xs font-semibold text-slate-700 hover:border-rose-300 hover:text-rose-700 hover:bg-rose-50 shadow-2xs"
                    >
                      <Eye size={13} />
                      <span>Xem bằng chứng</span>
                    </Button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Section 2: HITL Remediation Proposals (AI Đề xuất giải pháp - Chỉ hiển thị cho Admin) */}
      {currentRole === 'admin' && (
        <div className="space-y-3 pt-2">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Sparkles size={16} className="text-[#04D3D4]" />
              <h3 className="text-xs font-bold text-slate-900 uppercase tracking-wider">
                2. Đề xuất giải pháp & Rule từ AI (Chờ Human-in-the-Loop duyệt)
              </h3>
            </div>
            <span className="rounded-full bg-[#FFC402]/20 border border-[#FFC402]/40 px-2.5 py-0.5 text-[10px] font-bold text-slate-950">
              Áp dụng sau khi được con người phê duyệt
            </span>
          </div>

          <div className="grid gap-3.5">
            {dataset.proposedRules.map((rule: ProposedRule) => {
              const isApproved = rule.status === 'approved';
              const isRejected = rule.status === 'rejected';
              const isPending = rule.status === 'pending';

              return (
                <div
                  key={rule.id}
                  className={`rounded-xl border p-4.5 transition-all shadow-xs ${
                    isApproved
                      ? 'border-emerald-300 bg-emerald-50/30'
                      : isRejected
                      ? 'border-slate-200 bg-slate-50/60 opacity-60'
                      : 'border-[#04D3D4]/30 bg-white ring-1 ring-[#04D3D4]/20'
                  }`}
                >
                  {/* Rule Header */}
                  <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                    <div className="space-y-1">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="rounded-md bg-slate-950 px-2 py-0.5 text-[10px] font-mono font-bold text-[#04D3D4]">
                          {rule.name}
                        </span>
                        <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-semibold text-slate-600">
                          {rule.domain}
                        </span>
                        <span className="rounded-full bg-[#04D3D4]/10 px-2 py-0.5 text-[10px] font-semibold text-slate-800 border border-[#04D3D4]/30">
                          Đích: {rule.compiledTarget}
                        </span>
                      </div>
                      <p className="text-xs text-slate-700 leading-relaxed font-normal pt-1">
                        {rule.rationale}
                      </p>
                    </div>

                    {/* Status Badge */}
                    <div>
                      {isApproved && (
                        <Badge className="bg-emerald-100 text-emerald-800 border-emerald-200 text-xs font-bold gap-1">
                          <CheckCircle2 size={13} /> Đã áp dụng vào Active Rules
                        </Badge>
                      )}
                      {isRejected && (
                        <Badge tone="slate" className="border-slate-300 text-slate-500 text-xs">
                          Đã từ chối
                        </Badge>
                      )}
                      {isPending && (
                        <span className="inline-flex items-center gap-1 rounded-full bg-[#FFC402] px-2.5 py-0.5 text-[10px] font-bold text-slate-950 shadow-2xs">
                          <Clock size={11} /> Chờ bạn thẩm định (HITL)
                        </span>
                      )}
                    </div>
                  </div>

                  {/* Expression & Law Box */}
                  <div className="mt-3.5 rounded-lg border border-slate-200 bg-slate-50/70 p-3 text-[11px]">
                    <div className="flex items-center justify-between text-[10px] font-semibold text-slate-500 mb-1">
                      <span>Biểu thức kiểm soát (SQL / Logic Filter):</span>
                      <span>Độ tin cậy AI: {rule.confidence}%</span>
                    </div>
                    <code className="block rounded bg-white p-2 font-mono text-xs font-semibold text-slate-900 border border-slate-200">
                      {rule.expression}
                    </code>
                    <div className="mt-2 flex flex-wrap items-center justify-between text-[10px] text-slate-500 pt-1">
                      <span>Căn cứ pháp lý: <strong className="text-slate-700">{rule.lawRef}</strong></span>
                      <span>Tác động bảo vệ: <strong className="text-rose-700">{rule.affectedRows} dòng</strong> sẽ chuyển sang Quarantine</span>
                    </div>
                  </div>

                  {/* Actions Bar */}
                  {isPending && (
                    <div className="mt-4 flex flex-wrap items-center justify-between gap-2 border-t border-slate-100 pt-3">
                      <Button
                        onClick={() => handleDryRun(rule.id)}
                        disabled={testingRuleId === rule.id}
                        variant="outline"
                        size="sm"
                        className="h-8 gap-1.5 border-slate-300 text-xs text-slate-700 hover:border-[#04D3D4] hover:text-slate-950 hover:bg-[#04D3D4]/10"
                      >
                        <FlaskConical size={13} />
                        <span>{testingRuleId === rule.id ? 'Đang giả lập...' : 'Chạy thử nghiệm (Dry-run)'}</span>
                      </Button>

                      <div className="flex items-center gap-2">
                        <Button
                          onClick={() => rejectRule(rule.id)}
                          variant="outline"
                          size="sm"
                          className="h-8 gap-1 border-rose-200 text-xs text-rose-700 hover:bg-rose-50"
                        >
                          <X size={13} />
                          <span>Từ chối</span>
                        </Button>

                        <Button
                          onClick={() => approveRule(rule.id)}
                          size="sm"
                          className="h-8 gap-1.5 bg-[#04D3D4] text-xs font-bold text-slate-950 hover:bg-[#03b8b9] shadow-xs"
                        >
                          <Check size={14} />
                          <span>Phê duyệt áp dụng (HITL)</span>
                        </Button>
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
