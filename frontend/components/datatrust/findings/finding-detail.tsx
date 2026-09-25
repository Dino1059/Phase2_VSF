'use client';
import { useState } from 'react';
import type { ComponentProps } from 'react';
import { Link as RouterLink } from 'react-router-dom';
import {
  ArrowLeft,
  Check,
  CheckCircle2,
  Clock3,
  Copy,
  Download,
  Link2,
  Lock,
  SlidersHorizontal,
  Sparkles,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import type { FindingDetail as FindingDetailModel } from '@/lib/data/findings-types';
import { SeverityBadge, StateBadge } from './finding-badges';
import { useAgentStore } from '@/lib/agent-store';

function Link({ href, ...props }: Omit<ComponentProps<typeof RouterLink>, 'to'> & { href: string }) {
  return <RouterLink to={href} {...props} />;
}

const displayDate = (value: string) =>
  new Intl.DateTimeFormat('vi-VN', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value));

export function FindingDetail({ finding }: { finding: FindingDetailModel }) {
  const { currentRole } = useAgentStore();
  const [activeTab, setActiveTab] = useState<'agentic' | 'evidence' | 'history' | 'related'>('agentic');
  const [copiedPayload, setCopiedPayload] = useState(false);
  const [appliedRule, setAppliedRule] = useState(false);
  const [status, setStatus] = useState(finding.status);

  const copyEvidence = async (data: unknown) => {
    await navigator.clipboard.writeText(JSON.stringify(data, null, 2));
    setCopiedPayload(true);
    setTimeout(() => setCopiedPayload(false), 2000);
  };

  const handleDownload = () => {
    const dataStr =
      'data:text/json;charset=utf-8,' +
      encodeURIComponent(
        JSON.stringify(
          {
            finding_id: finding.id,
            title: finding.title,
            control: finding.control,
            severity: finding.severity,
            status,
            assigned_to: finding.assignedTo,
            ai_analysis: {
              impact: finding.impact,
              domain: finding.domain,
            },
            root_cause: finding.issueDescription,
            evidence: finding.evidence,
            recommended_actions: finding.recommendedActions,
            exported_at: new Date().toISOString(),
          },
          null,
          2
        )
      );
    const downloadAnchor = document.createElement('a');
    downloadAnchor.setAttribute('href', dataStr);
    downloadAnchor.setAttribute('download', `finding-${finding.id}.json`);
    document.body.appendChild(downloadAnchor);
    downloadAnchor.click();
    downloadAnchor.remove();
  };

  return (
    <section className="page-enter mx-auto max-w-[1360px] space-y-6">
      {/* Back Link */}
      <div>
        <Link
          href="/results?tab=findings"
          className="inline-flex items-center gap-1.5 text-xs font-semibold text-slate-500 hover:text-slate-900 transition"
        >
          <ArrowLeft size={14} /> Quay lại danh sách Finding
        </Link>
      </div>

      {/* Header Banner */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between border-b border-[#e2ece8] pb-5">
        <div className="space-y-1.5">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-mono text-xs font-bold text-slate-900 bg-[#04D3D4]/20 px-2.5 py-0.5 rounded-md border border-[#04D3D4]/40">
              {finding.id}
            </span>
            <SeverityBadge value={finding.severity} />
            <StateBadge value={status} />
            <Badge tone="slate">{finding.domain}</Badge>
          </div>
          <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-slate-900 leading-tight">
            {finding.title}
          </h1>
          <p className="text-xs text-slate-500">
            Kiểm soát liên quan: <strong className="text-slate-800">{finding.control.id} · {finding.control.name}</strong> · Phân công: <span className="font-medium text-slate-700">{finding.assignedTo}</span> · Ngày phát hiện: {displayDate(finding.createdAt)}
          </p>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          <Button
            variant="outline"
            size="sm"
            onClick={handleDownload}
            className="h-9 px-3 text-xs gap-1.5"
          >
            <Download size={14} /> Tải hồ sơ (.JSON)
          </Button>

          {status !== 'REMEDIATED' ? (
            <Button
              variant="xanhsm"
              size="sm"
              onClick={() => setStatus('REMEDIATED')}
              className="h-9 px-4 text-xs font-bold gap-1.5 bg-[#04D3D4] text-slate-950 hover:bg-[#03b8b9]"
            >
              <CheckCircle2 size={14} /> Đánh dấu đã xử lý
            </Button>
          ) : (
            <span className="inline-flex items-center gap-1.5 rounded-lg border border-emerald-300 bg-emerald-50 px-3 py-2 text-xs font-bold text-emerald-700">
              <Check size={14} strokeWidth={2.5} /> Đã khắc phục & Lưu vết
            </span>
          )}
        </div>
      </div>

      {/* Segmented Tabs (Agentic View as default) */}
      <div className="flex gap-2 border-b border-slate-200 overflow-x-auto pb-1">
        <button
          type="button"
          onClick={() => setActiveTab('agentic')}
          className={`flex items-center gap-2 px-3.5 py-2 text-xs font-bold rounded-lg transition ${
            activeTab === 'agentic'
              ? 'bg-[#04D3D4] text-slate-950 shadow-xs'
              : 'text-slate-600 hover:bg-slate-100'
          }`}
        >
          <Sparkles size={14} />
          Phân tích AI & Hành động (Core)
        </button>
        <button
          type="button"
          onClick={() => setActiveTab('evidence')}
          className={`flex items-center gap-2 px-3.5 py-2 text-xs font-bold rounded-lg transition ${
            activeTab === 'evidence'
              ? 'bg-[#04D3D4] text-slate-950 shadow-xs'
              : 'text-slate-600 hover:bg-slate-100'
          }`}
        >
          <Lock size={14} />
          Bằng chứng số liệu ({finding.evidence.length})
        </button>
        <button
          type="button"
          onClick={() => setActiveTab('history')}
          className={`flex items-center gap-2 px-3.5 py-2 text-xs font-bold rounded-lg transition ${
            activeTab === 'history'
              ? 'bg-[#04D3D4] text-slate-950 shadow-xs'
              : 'text-slate-600 hover:bg-slate-100'
          }`}
        >
          <Clock3 size={14} />
          Lịch sử thẩm tra ({finding.history.length})
        </button>
        <button
          type="button"
          onClick={() => setActiveTab('related')}
          className={`flex items-center gap-2 px-3.5 py-2 text-xs font-bold rounded-lg transition ${
            activeTab === 'related'
              ? 'bg-[#04D3D4] text-slate-950 shadow-xs'
              : 'text-slate-600 hover:bg-slate-100'
          }`}
        >
          <Link2 size={14} />
          Findings liên quan ({finding.related.length})
        </button>
      </div>

      {/* TAB 1: 4 AGENTIC PILLARS */}
      {activeTab === 'agentic' && (
        <div className="space-y-5">
          {/* PILLAR 1: AI ANALYSIS */}
          <Card className="rounded-xl border border-[#04D3D4]/30 bg-[#04D3D4]/5 p-5 shadow-xs space-y-3">
            <div className="flex items-center justify-between">
              <span className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-slate-900">
                <Sparkles size={15} className="text-[#04D3D4]" />
                1. Phân Tích & Đánh Giá Rủi Ro Từ AI Agent (AI Analysis)
              </span>
              <span className="text-[11px] font-semibold text-slate-700 bg-white px-2 py-0.5 rounded border border-slate-200">
                Độ tin cậy: 98%
              </span>
            </div>
            
            <p className="text-xs text-slate-700 leading-relaxed font-medium">
              AI Agent đã thực hiện kiểm tra đối soát tự động tiêu chuẩn <strong>{finding.control.id} ({finding.control.name})</strong>: {finding.control.evaluationMessage}.
            </p>

            <div className="rounded-lg bg-white p-3.5 border border-slate-200 space-y-1.5">
              <span className="text-[11px] font-bold text-slate-500 uppercase">Tác động kiểm toán (Impact Assessment):</span>
              <p className="text-xs text-slate-800 leading-relaxed font-medium">{finding.impact}</p>
            </div>
          </Card>

          {/* PILLAR 2: EVIDENCE PREVIEW */}
          <Card className="rounded-xl border border-slate-200 bg-white p-5 shadow-xs space-y-3">
            <div className="flex items-center justify-between">
              <span className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-slate-800">
                <Lock size={15} className="text-[#04D3D4]" />
                2. Bằng Chứng Mật Mã & Bản Ghi Nguồn (Evidence)
              </span>
              <button
                type="button"
                onClick={() => setActiveTab('evidence')}
                className="text-xs font-semibold text-slate-700 hover:text-[#04D3D4] hover:underline flex items-center gap-1"
              >
                Xem chi tiết {finding.evidence.length} bằng chứng <ArrowLeft size={12} className="rotate-180" />
              </button>
            </div>

            <div className="overflow-x-auto rounded-lg border border-slate-200">
              <table className="w-full text-left text-xs">
                <thead className="bg-slate-50 text-[11px] font-semibold text-slate-600 border-b border-slate-200">
                  <tr>
                    <th className="px-4 py-2.5">Mã bằng chứng</th>
                    <th className="px-4 py-2.5">Hệ thống nguồn</th>
                    <th className="px-4 py-2.5">Loại bằng chứng</th>
                    <th className="px-4 py-2.5">Thời gian bắt</th>
                    <th className="px-4 py-2.5">Đối tượng</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {finding.evidence.slice(0, 3).map((item) => (
                    <tr key={item.id} className="hover:bg-slate-50/50">
                      <td className="px-4 py-2.5 font-mono font-bold text-slate-900">{item.id}</td>
                      <td className="px-4 py-2.5 font-medium text-slate-700">{item.source}</td>
                      <td className="px-4 py-2.5">
                        <span className="rounded bg-slate-100 px-2 py-0.5 text-[11px] font-medium text-slate-700">
                          {item.type}
                        </span>
                      </td>
                      <td className="px-4 py-2.5 text-slate-500 whitespace-nowrap">{displayDate(item.capturedAt)}</td>
                      <td className="px-4 py-2.5 font-mono text-slate-600">{item.linkedObject}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>

          {/* PILLAR 3: SUGGESTED ACTIONS */}
          <Card className="rounded-xl border border-slate-200 bg-white p-5 shadow-xs space-y-4">
            <span className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-slate-800">
              <SlidersHorizontal size={15} className="text-[#04D3D4]" />
              3. Hành Động Đề Xuất Từ AI Agent (Suggested Action & Remediation)
            </span>

            {/* Recommended Steps */}
            <div className="space-y-2">
              <span className="text-xs font-semibold text-slate-600">Kế hoạch hành động từng bước:</span>
              <ol className="space-y-2">
                {finding.recommendedActions.map((action, index) => (
                  <li key={action} className="flex items-start gap-2.5 text-xs leading-relaxed text-slate-700">
                    <span className="grid size-5 shrink-0 place-items-center rounded-full bg-[#04D3D4]/20 text-[11px] font-bold text-slate-950 mt-0.5">
                      {index + 1}
                    </span>
                    <span>{action}</span>
                  </li>
                ))}
              </ol>
            </div>

            {/* AI 1-Click Action Box (Chỉ hiển thị cho Admin) */}
            {currentRole === 'admin' && (
              <div className="rounded-lg border border-[#cbebe2] bg-[#f0f9f6] p-4 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
                <div>
                  <strong className="block text-xs font-bold text-slate-900">
                    ⚡ 1-Click Áp dụng Rule kiểm soát tự động
                  </strong>
                  <p className="text-xs text-slate-600 mt-0.5">
                    Tự động biên dịch quy tắc kiểm soát và cập nhật vào Ingestion Pipeline.
                  </p>
                </div>
                <Button
                  variant="xanhsm"
                  size="sm"
                  onClick={() => {
                    setAppliedRule(true);
                    setTimeout(() => setAppliedRule(false), 3000);
                  }}
                  disabled={appliedRule}
                  className="text-xs font-semibold gap-1.5 shrink-0"
                >
                  {appliedRule ? <Check size={13} /> : <Sparkles size={13} />}
                  {appliedRule ? 'Đã kích hoạt rule vào Pipeline!' : 'Áp dụng Rule ngay'}
                </Button>
              </div>
            )}
          </Card>
        </div>
      )}

      {/* TAB 2: DETAILED EVIDENCE */}
      {activeTab === 'evidence' && (
        <div className="space-y-4">
          {finding.evidence.map((item) => (
            <Card key={item.id} className="rounded-xl border border-slate-200 bg-white p-5 shadow-xs space-y-3">
              <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 border-b border-slate-100 pb-3">
                <div className="space-y-0.5">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-xs font-bold text-[#007460] bg-[#e6f6f2] px-2 py-0.5 rounded border border-[#bfe7dc]">
                      {item.id}
                    </span>
                    <strong className="text-xs font-bold text-slate-900">{item.source} · {item.type}</strong>
                  </div>
                  <p className="text-xs text-slate-500">Mã tham chiếu: <code className="font-mono text-slate-700">{item.reference}</code></p>
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => copyEvidence(item.rawEvent)}
                  className="text-xs gap-1.5 self-start sm:self-auto"
                >
                  {copiedPayload ? <Check size={13} /> : <Copy size={13} />}
                  {copiedPayload ? 'Đã sao chép' : 'Sao chép raw JSON'}
                </Button>
              </div>

              {/* Raw JSON viewer */}
              <div className="rounded-lg border border-slate-800 bg-[#0c1917] p-3.5 overflow-x-auto max-h-60">
                <pre className="font-mono text-xs text-emerald-300 leading-relaxed whitespace-pre">
                  {JSON.stringify(item.rawEvent, null, 2)}
                </pre>
              </div>

              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-1 text-xs text-slate-500">
                <div><span>Tác nhân:</span> <strong className="block text-slate-700">{item.actor}</strong></div>
                <div><span>Đối tượng:</span> <strong className="block text-slate-700 font-mono">{item.linkedObject}</strong></div>
                <div><span>Thời gian:</span> <span className="block text-slate-700">{displayDate(item.capturedAt)}</span></div>
                <div><span>Kết quả kiểm soát:</span> <strong className="block text-[#007460] font-mono">{item.controlResultId}</strong></div>
              </div>
            </Card>
          ))}
        </div>
      )}

      {/* TAB 3: PROCESSING HISTORY */}
      {activeTab === 'history' && (
        <Card className="rounded-xl border border-slate-200 bg-white p-5 shadow-xs">
          <div className="space-y-4">
            {finding.history.map((item, index) => (
              <div key={`${item.label}-${index}`} className="flex gap-4">
                <div className="flex flex-col items-center">
                  <span
                    className={`grid size-7 place-items-center rounded-full text-xs ${
                      item.tone === 'green'
                        ? 'bg-emerald-50 text-emerald-600'
                        : item.tone === 'amber'
                        ? 'bg-amber-50 text-amber-600'
                        : 'bg-[#e6f6f2] text-[#007460]'
                    }`}
                  >
                    {item.tone === 'green' ? <CheckCircle2 size={14} /> : <Clock3 size={14} />}
                  </span>
                  {index < finding.history.length - 1 && <span className="h-10 w-px bg-slate-200" />}
                </div>
                <div className="space-y-0.5">
                  <p className="text-xs font-bold text-slate-800">{item.label}</p>
                  <p className="text-xs text-slate-600">{item.detail}</p>
                  <p className="text-[11px] text-slate-500">{displayDate(item.occurredAt)}</p>
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* TAB 4: RELATED FINDINGS */}
      {activeTab === 'related' && (
        <Card className="rounded-xl border border-slate-200 bg-white p-5 shadow-xs space-y-3">
          {finding.related.length > 0 ? (
            finding.related.map((item) => (
              <Link
                key={item.id}
                href={`/findings/${item.id}`}
                className="flex items-center justify-between gap-3 rounded-lg border border-slate-200 p-3 hover:border-[#04D3D4] hover:bg-[#04D3D4]/5 transition"
              >
                <div className="flex items-center gap-2.5">
                  <Link2 className="text-[#04D3D4]" size={16} />
                  <div>
                    <span className="font-mono text-xs font-bold text-slate-900">{item.id}</span>
                    <p className="text-xs font-semibold text-slate-800">{item.title}</p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <SeverityBadge value={item.severity} />
                  <StateBadge value={item.status} />
                </div>
              </Link>
            ))
          ) : (
            <p className="py-6 text-center text-xs text-slate-400">Không có finding liên quan.</p>
          )}
        </Card>
      )}
    </section>
  );
}
