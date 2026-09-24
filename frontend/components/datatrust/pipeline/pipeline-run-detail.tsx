import type { ComponentProps } from 'react';
import { Link as RouterLink } from 'react-router-dom';
import { ArrowLeft, ArrowRight, CheckCircle2, Database, FileText, ShieldAlert, Timer, XCircle } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Card, CardTitle } from '@/components/ui/card';
import { PipelineStatusBadge } from './pipeline-status';
import type {
  PipelineRunDetail as Detail,
  PipelineRuleResult,
  PipelineFinding,
  PipelineEvidence,
} from '@/lib/data/pipeline-types';


function Link({ href, ...props }: Omit<ComponentProps<typeof RouterLink>, 'to'> & { href: string }) {
  return <RouterLink to={href} {...props} />;
}

const format = (value: string) =>
  new Intl.DateTimeFormat('vi-VN', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value));

export function PipelineRunDetail({ run }: { run: Detail }) {
  const counts = [
    { label: 'Bản ghi đầu vào (Raw)', value: run.inputRecords, icon: Database },
    { label: 'Bản ghi Sạch (Silver)', value: run.silverRecords, icon: CheckCircle2 },
    { label: 'Bản ghi Cách ly (Quarantine)', value: run.quarantineRecords, icon: ShieldAlert },
    { label: 'Thời lượng', value: `${run.durationMinutes} phút`, icon: Timer },
  ];

  return (
    <section className="page-enter mx-auto max-w-[1360px] space-y-6">
      <div>
        <Link
          href="/runs"
          className="mb-4 inline-flex items-center gap-1.5 text-xs font-semibold text-slate-500 hover:text-[#008b74]"
        >
          <ArrowLeft size={14} /> Trở lại danh sách lần chạy
        </Link>
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-2xl font-bold tracking-tight text-slate-900">{run.id}</h1>
              <PipelineStatusBadge status={run.status} />
            </div>
            <p className="mt-1 text-sm text-slate-500">
              DAG: <strong className="text-slate-700">{run.dagId}</strong> · Bắt đầu lúc {format(run.startedAt)}
            </p>
          </div>
        </div>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {counts.map((item) => {
          const Icon = item.icon;
          return (
            <Card key={item.label} className="rounded-xl border-[#e2ece8] bg-white p-5 shadow-2xs">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-xs text-slate-500">{item.label}</p>
                  <p className="mt-2 text-2xl font-bold text-slate-900">
                    {typeof item.value === 'number' ? item.value.toLocaleString('vi-VN') : item.value}
                  </p>
                </div>
                <span className="grid size-10 place-items-center rounded-lg bg-[#e6f6f2] text-[#007460]">
                  <Icon size={18} />
                </span>
              </div>
            </Card>
          );
        })}
      </div>

      <Card className="rounded-xl border-[#e2ece8] bg-white p-5 shadow-2xs">
        <CardTitle className="text-sm font-semibold text-slate-800">
          Luồng phân tách dữ liệu (Raw → Silver & Quarantine)
        </CardTitle>
        <div className="mt-4 flex flex-col items-stretch gap-3 sm:flex-row sm:items-center">
          <Flow value={run.inputRecords} label="Dữ liệu thô (Raw)" />
          <ArrowRight className="self-center text-slate-300" />
          <Flow value={run.silverRecords} label="Dữ liệu sạch (Silver)" tone="green" />
          <ArrowRight className="self-center text-slate-300" />
          <Flow value={run.quarantineRecords} label="Dữ liệu cách ly (Quarantine)" tone="amber" />
        </div>
      </Card>

      <div className="grid gap-6 xl:grid-cols-2">
        <Card className="rounded-xl border-[#e2ece8] bg-white p-5 shadow-2xs">
          <div className="flex items-center justify-between border-b border-[#f0f4f2] pb-3">
            <CardTitle className="text-sm font-semibold text-slate-800">Kết quả đánh giá Rule</CardTitle>
            <div className="flex gap-2">
              <Badge tone="green">{run.rulePassCount} đạt</Badge>
              <Badge tone="red">{run.ruleFailCount} vi phạm</Badge>
            </div>
          </div>
          <div className="mt-4 space-y-2">
            {run.rules.length ? (
              run.rules.map((rule: PipelineRuleResult) => (
                <div key={rule.id} className="flex gap-3 rounded-lg border border-[#e2ece8] bg-[#fbfdfc] p-3">
                  {rule.status === 'PASS' ? (
                    <CheckCircle2 className="shrink-0 text-emerald-600 mt-0.5" size={17} />
                  ) : (
                    <XCircle className="shrink-0 text-red-500 mt-0.5" size={17} />
                  )}
                  <div className="min-w-0">
                    <p className="text-xs font-semibold text-slate-900">
                      {rule.controlId} · {rule.name}
                    </p>
                    <p className="mt-1 truncate text-[11px] text-slate-500">{rule.message}</p>
                  </div>
                </div>
              ))
            ) : (
              <Empty text="Không có kết quả kiểm soát liên kết." />
            )}
          </div>
        </Card>

        <Card className="rounded-xl border-[#e2ece8] bg-white p-5 shadow-2xs">
          <div className="flex items-center justify-between border-b border-[#f0f4f2] pb-3">
            <CardTitle className="text-sm font-semibold text-slate-800">Phát hiện liên quan (Findings)</CardTitle>
            <span className="text-[11px] text-slate-400">{run.findings.length} phát hiện</span>
          </div>
          <div className="mt-4 space-y-2">
            {run.findings.length ? (
              run.findings.map((finding: PipelineFinding) => (
                <Link
                  key={finding.id}
                  href={`/results?tab=findings`}
                  className="flex items-center gap-3 rounded-lg border border-[#e2ece8] bg-[#fbfdfc] p-3 hover:bg-[#e6f6f2] transition"
                >
                  <ShieldAlert className="text-red-500" size={16} />
                  <div className="min-w-0 flex-1">
                    <p className="text-xs font-semibold text-[#008b74]">{finding.id}</p>
                    <p className="truncate text-[11px] text-slate-500">{finding.title}</p>
                  </div>
                  <Badge tone={finding.status === 'OPEN' ? 'red' : 'green'}>
                    {finding.status.replace('_', ' ')}
                  </Badge>
                </Link>
              ))
            ) : (
              <Empty text="Không có phát hiện vi phạm nào trong lần chạy này." />
            )}
          </div>
        </Card>
      </div>

      <Card className="rounded-xl border-[#e2ece8] bg-white p-5 shadow-2xs">
        <div className="flex items-center justify-between border-b border-[#f0f4f2] pb-3">
          <CardTitle className="text-sm font-semibold text-slate-800">Bằng chứng liên kết (Evidence)</CardTitle>
          <span className="text-[11px] text-slate-400">{run.evidence.length} mục bằng chứng</span>
        </div>
        <div className="mt-4 grid gap-3 md:grid-cols-2">
          {run.evidence.length ? (
            run.evidence.map((item: PipelineEvidence) => (
              <div key={item.id} className="flex items-center gap-3 rounded-lg border border-[#e2ece8] bg-[#fbfdfc] p-4">
                <span className="grid size-9 place-items-center rounded-lg bg-[#e6f6f2] text-[#007460]">
                  <FileText size={16} />
                </span>
                <div className="min-w-0">
                  <p className="text-xs font-semibold text-[#008b74]">{item.id}</p>
                  <p className="truncate text-[11px] text-slate-500">
                    {item.type} · {item.source}
                  </p>
                  <p className="mt-1 truncate font-mono text-[10px] text-slate-400">{item.reference}</p>
                </div>
              </div>
            ))
          ) : (
            <Empty text="Không có bằng chứng kiểm toán được liên kết." />
          )}
        </div>
      </Card>
    </section>
  );
}

function Flow({
  value,
  label,
  tone = 'blue',
}: {
  value: number;
  label: string;
  tone?: 'blue' | 'green' | 'amber';
}) {
  return (
    <div className="flex-1 rounded-lg border border-[#e2ece8] bg-slate-50 p-4 text-center">
      <p className="text-[11px] uppercase tracking-wide text-slate-400">{label}</p>
      <p
        className={
          tone === 'green'
            ? 'mt-1 text-xl font-bold text-[#008b74]'
            : tone === 'amber'
            ? 'mt-1 text-xl font-bold text-amber-600'
            : 'mt-1 text-xl font-bold text-slate-800'
        }
      >
        {value.toLocaleString('vi-VN')}
      </p>
    </div>
  );
}

function Empty({ text }: { text: string }) {
  return <p className="py-8 text-center text-xs text-slate-400">{text}</p>;
}

