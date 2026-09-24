'use client';
import { Link, useNavigate } from 'react-router-dom';
import {
  Check,
  ExternalLink,
  Loader2,
  Sparkles,
} from 'lucide-react';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  useAgentStore,
  type ProposedRule,
  type AgentStep,
  type DatasetItem,
} from '@/lib/agent-store';

export function OverviewPage() {
  const navigate = useNavigate();
  const {
    selectedDatasetId,
    agentStatus,
    datasets,
    steps,
    selectDataset,
    runAgent,
    approveRule,
    rejectRule,
    openChatWithPrompt,
  } = useAgentStore();

  const currentDataset: DatasetItem = datasets[selectedDatasetId] || datasets.trips;
  const pendingRules: ProposedRule[] = currentDataset.proposedRules;
  const pendingCount = pendingRules.filter((r: ProposedRule) => r.status === 'pending').length;


  return (
    <div className="page-enter mx-auto max-w-[1360px] space-y-6">
      {/* 1. Hero Header */}
      <div>
        <h1 className="text-3xl font-extrabold tracking-tight text-slate-900">
          Chọn dữ liệu. Agent lo phần còn lại.
        </h1>
        <p className="mt-1 text-sm text-slate-500">
          Bạn chỉ cần xem và duyệt các rule được đề xuất.
        </p>
      </div>

      {/* 2. Top Card: BẮT ĐẦU LẦN CHẠY */}
      <Card className="rounded-2xl border-[#e2ece8] bg-white p-6 shadow-xs">
        <div className="space-y-1">
          <span className="text-[11px] font-bold uppercase tracking-wider text-[#008b74]">
            BẮT ĐẦU LẦN CHẠY
          </span>
          <h2 className="text-xl font-bold tracking-tight text-slate-900">
            Kiểm tra bộ dữ liệu
          </h2>
          <p className="text-xs text-slate-500">
            Agent sẽ profiling, phát hiện bất thường, đề xuất rule và tạo bằng chứng.
          </p>
        </div>

        <div className="mt-5 flex flex-col gap-3 sm:flex-row sm:items-end">
          <div className="flex-1 space-y-1.5">
            <label htmlFor="dataset-select" className="block text-xs font-semibold text-slate-700">
              Bộ dữ liệu
            </label>
            <div className="relative">
              <select
                id="dataset-select"
                value={selectedDatasetId}
                disabled={agentStatus === 'running'}
                onChange={(e) => selectDataset(e.target.value)}
                className="h-10 w-full appearance-none rounded-lg border border-[#d2e2dc] bg-white px-3.5 pr-8 text-xs font-medium text-slate-800 transition focus:border-[#008b74] focus:outline-none focus:ring-1 focus:ring-[#008b74] disabled:opacity-50"
              >
                {Object.values(datasets).map((ds: DatasetItem) => (
                  <option key={ds.id} value={ds.id}>
                    {ds.name}
                  </option>
                ))}
              </select>
              <div className="pointer-events-none absolute inset-y-0 right-0 flex items-center px-2.5 text-slate-400">
                <svg className="size-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 9l-7 7-7-7" />
                </svg>
              </div>
            </div>
          </div>

          <Button
            onClick={runAgent}
            disabled={agentStatus === 'running'}
            className="h-10 px-5 text-xs font-semibold bg-[#0f3834] hover:bg-[#164a44] text-white rounded-lg shadow-xs transition"
          >
            {agentStatus === 'running' ? (
              <>
                <Loader2 size={14} className="animate-spin" />
                Đang xử lý...
              </>
            ) : (
              <>
                Cho agent chạy →
              </>
            )}
          </Button>
        </div>

        <p className="mt-3 text-[11px] text-slate-400">
          Luồng mô phỏng · không ghi hay sửa dữ liệu nguồn
        </p>
      </Card>

      {/* 3. Middle 2-Column Grid */}
      <div className="grid gap-6 lg:grid-cols-12">
        {/* Left Column: Agent đang làm gì? */}
        <Card className="rounded-2xl border-[#e2ece8] bg-white p-6 shadow-xs lg:col-span-7">
          <div className="flex items-center justify-between border-b border-[#f0f4f2] pb-4">
            <div className="flex items-center gap-2.5">
              <span className="grid size-8 place-items-center rounded-lg bg-[#e6f6f2] text-[#008b74]">
                <Sparkles size={16} />
              </span>
              <h3 className="text-base font-bold text-slate-900">Agent đang làm gì?</h3>
            </div>
            <span
              className={`rounded-full px-3 py-1 text-xs font-semibold ${
                agentStatus === 'completed'
                  ? 'border border-[#bfe7dc] bg-[#e6f6f2] text-[#007460]'
                  : agentStatus === 'running'
                  ? 'border border-amber-200 bg-amber-50 text-amber-700 animate-pulse'
                  : 'border border-slate-200 bg-slate-50 text-slate-500'
              }`}
            >
              {agentStatus === 'completed'
                ? 'Hoàn tất'
                : agentStatus === 'running'
                ? 'Đang phân tích...'
                : 'Sẵn sàng'}
            </span>
          </div>

          <div className="mt-4 divide-y divide-[#f2f6f4]">
            {steps.map((step: AgentStep) => {
              const isDone = step.status === 'done';
              const isRunning = step.status === 'running';

              return (
                <div key={step.id} className="flex items-start justify-between py-3.5 first:pt-1 last:pb-1">
                  <div className="flex items-start gap-3">
                    <span
                      className={`mt-0.5 grid size-6 shrink-0 place-items-center rounded-full text-xs transition-colors ${
                        isDone
                          ? 'bg-[#e6f6f2] text-[#008b74]'
                          : isRunning
                          ? 'bg-amber-100 text-amber-700 animate-spin'
                          : 'bg-slate-100 text-slate-400'
                      }`}
                    >
                      {isDone ? (
                        <Check size={13} strokeWidth={2.6} />
                      ) : isRunning ? (
                        <Loader2 size={13} />
                      ) : (
                        <span className="size-2 rounded-full bg-slate-300" />
                      )}
                    </span>
                    <div>
                      <strong className="block text-xs font-semibold text-slate-800">
                        {step.title}
                      </strong>
                      <p className="text-[11px] text-slate-400">{step.desc}</p>
                    </div>
                  </div>

                  <span
                    className={`text-[11px] font-medium ${
                      isDone
                        ? 'text-slate-400'
                        : isRunning
                        ? 'text-amber-600 font-semibold'
                        : 'text-slate-300'
                    }`}
                  >
                    {isDone ? 'Xong' : isRunning ? 'Đang chạy' : 'Chờ'}
                  </span>
                </div>
              );
            })}
          </div>
        </Card>

        {/* Right Column: LẦN CHẠY HIỆN TẠI */}
        <Card className="flex flex-col justify-between rounded-2xl border-[#e2ece8] bg-white p-6 shadow-xs lg:col-span-5">
          <div>
            <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400">
              LẦN CHẠY HIỆN TẠI
            </span>
            <h3 className="mt-1 text-xl font-bold tracking-tight text-slate-900">
              {currentDataset.title}
            </h3>
            <p className="mt-1 text-xs text-slate-500">
              {agentStatus === 'completed'
                ? 'Agent đã hoàn tất phân tích. Hãy xem và duyệt các rule đề xuất.'
                : 'Đang chuẩn bị phiên chạy giám sát chất lượng và kiểm soát tuân thủ.'}
            </p>

            {/* 3 Metric Cards row */}
            <div className="mt-5 grid grid-cols-3 gap-3">
              <div className="rounded-xl border border-[#e2ece8] bg-white p-3.5 shadow-2xs">
                <span className="block text-xl font-bold tracking-tight text-slate-900">
                  {currentDataset.records.toLocaleString('vi-VN')}
                </span>
                <span className="mt-1 block text-[11px] font-medium text-slate-400">
                  Bản ghi
                </span>
              </div>

              <div className="rounded-xl border border-[#e2ece8] bg-white p-3.5 shadow-2xs">
                <span className="block text-xl font-bold tracking-tight text-slate-900">
                  {currentDataset.anomalies}
                </span>
                <span className="mt-1 block text-[11px] font-medium text-slate-400">
                  Phát hiện
                </span>
              </div>

              <div className="rounded-xl border border-[#e2ece8] bg-white p-3.5 shadow-2xs">
                <span className="block text-xl font-bold tracking-tight text-slate-900">
                  {currentDataset.proposedRulesCount}
                </span>
                <span className="mt-1 block text-[11px] font-medium text-slate-400">
                  Rule đề xuất
                </span>
              </div>
            </div>
          </div>

          {/* Callout Notice at bottom */}
          <div className="mt-6 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between rounded-xl border border-[#cbebe2] bg-[#f0f9f6] p-4 text-xs leading-relaxed text-[#005b4c]">
            <p>
              Agent đã nối phát hiện với evidence. Rule mới chỉ được áp dụng sau khi bạn phê duyệt.
            </p>
            <button
              onClick={() => openChatWithPrompt('💡 Hướng dẫn tôi các bước sử dụng sản phẩm')}
              className="inline-flex items-center gap-1.5 font-semibold text-[#008b74] hover:underline cursor-pointer shrink-0"
            >
              <Sparkles size={13} className="text-amber-500" />
              Cần trợ giúp? Hỏi Trợ lý AI →
            </button>
          </div>
        </Card>
      </div>

      {/* 4. Bottom Card: Rule chờ bạn duyệt */}
      <Card className="rounded-2xl border-[#e2ece8] bg-white p-6 shadow-xs">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between border-b border-[#f0f4f2] pb-4">
          <div>
            <h3 className="text-base font-bold text-slate-900">Rule chờ bạn duyệt</h3>
            <p className="mt-0.5 text-xs text-slate-400">
              {pendingCount > 0 ? `${pendingCount} rule chờ duyệt` : 'Tất cả các rule đã được xử lý'}
            </p>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={() => navigate('/rules')}
            className="rounded-lg border-slate-200 text-xs font-semibold text-slate-700 hover:bg-slate-50"
          >
            Xem tất cả
          </Button>
        </div>

        {/* Rule Items */}
        <div className="mt-4 space-y-4">
          {pendingRules.map((rule: ProposedRule) => {
            const isPending = rule.status === 'pending';
            const isApproved = rule.status === 'approved';

            return (
              <div
                key={rule.id}
                className="rounded-xl border border-[#e2ece8] bg-[#fbfdfc] p-4 transition hover:border-[#bfe7dc]"
              >
                <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                  <div className="space-y-1.5 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-mono text-xs font-bold text-slate-900">
                        {rule.name}
                      </span>
                      <Badge
                        tone={rule.severity === 'CRITICAL' ? 'red' : rule.severity === 'HIGH' ? 'amber' : 'blue'}
                      >
                        {rule.severity}
                      </Badge>
                      <span className="text-[11px] text-slate-400">· {rule.domain}</span>
                      <span className="text-[11px] text-slate-400">
                        · Độ tin cậy: <strong className="text-slate-700">{rule.confidence}%</strong>
                      </span>
                    </div>

                    <p className="text-xs text-slate-600">{rule.rationale}</p>

                    <div className="flex items-center gap-2 pt-1">
                      <code className="rounded-md border border-[#d2e2dc] bg-white px-2.5 py-1 font-mono text-[11px] text-[#007460]">
                        {rule.expression}
                      </code>
                    </div>
                  </div>

                  {/* Actions */}
                  <div className="flex flex-wrap items-center gap-2 shrink-0 pt-2 sm:pt-0">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => openChatWithPrompt(`Tại sao bạn lại đề xuất rule ${rule.name}?`)}
                      className="h-8 gap-1 text-xs text-amber-800 border-amber-300 bg-amber-50/70 hover:bg-amber-100 hover:border-amber-400 cursor-pointer"
                      title="Mở Trợ lý AI để giải thích lý do đề xuất rule này"
                    >
                      <Sparkles size={12} className="text-amber-600" />
                      Hỏi Agent
                    </Button>

                    {isPending ? (
                      <>
                        <Button
                          variant="xanhsm"
                          size="sm"
                          onClick={() => approveRule(rule.id)}
                          className="h-8 gap-1.5 px-3 text-xs font-semibold cursor-pointer"
                        >
                          <Check size={14} />
                          Phê duyệt rule
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => rejectRule(rule.id)}
                          className="h-8 text-xs text-slate-500 hover:text-red-600 hover:bg-red-50 cursor-pointer"
                        >
                          Từ chối
                        </Button>
                      </>
                    ) : isApproved ? (
                      <span className="inline-flex items-center gap-1.5 rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-1 text-xs font-semibold text-emerald-700">
                        <Check size={14} /> Đã duyệt bởi Steward
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1.5 rounded-lg border border-red-200 bg-red-50 px-3 py-1 text-xs font-semibold text-red-600">
                        Đã từ chối
                      </span>
                    )}
                  </div>
                </div>

                {/* Evidence Link Footer */}
                <div className="mt-3 flex items-center justify-between border-t border-[#f0f4f2] pt-2.5 text-[11px] text-slate-400">
                  <div className="flex items-center gap-4">
                    <span>
                      Ảnh hưởng: <strong className="text-slate-600">{rule.affectedRows} dòng</strong>
                    </span>
                    <span>
                      Căn cứ: <span className="text-slate-600">{rule.lawRef}</span>
                    </span>
                  </div>
                  <Link
                    to={`/results?tab=evidence&ref=${rule.evidenceId}`}
                    className="inline-flex items-center gap-1 text-[#008b74] hover:underline"
                  >
                    Evidence: {rule.evidenceId}
                    <ExternalLink size={11} />
                  </Link>
                </div>
              </div>
            );
          })}
        </div>
      </Card>
    </div>
  );
}
