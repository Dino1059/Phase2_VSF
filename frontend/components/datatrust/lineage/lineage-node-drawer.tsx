'use client';

import { AlertOctagon, AlertTriangle, CheckCircle2, Database, FileText, Layers, ShieldCheck, X } from 'lucide-react';
import type { LineageNode } from '@/lib/api-bridge';

interface LineageNodeDrawerProps {
  node: LineageNode | null;
  onClose: () => void;
  onSelectNode?: (nodeId: string) => void;
}

const statusTone = (status: string) => {
  switch (status.toUpperCase()) {
    case 'SUCCESS': case 'COMPLETED': return 'text-emerald-700 bg-emerald-500';
    case 'FAILED': return 'text-rose-700 bg-rose-500';
    case 'RUNNING': return 'text-blue-700 bg-blue-500';
    case 'SKIPPED': return 'text-slate-500 bg-slate-400';
    case 'QUEUED': case 'SCHEDULED': return 'text-amber-700 bg-amber-500';
    default: return 'text-slate-600 bg-slate-400';
  }
};

export function LineageNodeDrawer({ node, onClose }: LineageNodeDrawerProps) {
  if (!node) return null;

  const layerStyle: Record<string, string> = {
    RAW: 'bg-slate-100 text-slate-700 border-slate-300', BRONZE: 'bg-amber-50 text-amber-800 border-amber-300',
    SILVER: 'bg-emerald-50 text-emerald-800 border-emerald-300', QUARANTINE: 'bg-rose-50 text-rose-800 border-rose-300',
    WARNING: 'bg-yellow-50 text-yellow-800 border-yellow-300', AUDIT: 'bg-teal-50 text-teal-800 border-teal-300',
  };
  const layerIcons: Record<string, typeof Database> = { RAW: FileText, BRONZE: Layers, SILVER: CheckCircle2, QUARANTINE: AlertOctagon, WARNING: AlertTriangle, AUDIT: ShieldCheck };
  const Icon = layerIcons[node.layer] || Database;
  const tone = statusTone(node.status);
  const facets = node.facets ? Object.entries(node.facets) : [];

  return (
    <div className="fixed inset-y-0 right-0 z-50 flex w-full max-w-md flex-col border-l border-slate-200 bg-white shadow-2xl">
      <div className="flex items-center justify-between border-b border-slate-100 px-6 py-4">
        <div className="flex min-w-0 items-center gap-2.5">
          <div className={`flex size-9 shrink-0 items-center justify-center rounded-lg border ${layerStyle[node.layer] || 'bg-blue-50 text-blue-800 border-blue-300'}`}><Icon className="size-5" /></div>
          <div className="min-w-0">
            <div className="flex items-center gap-2"><span className="text-[10px] font-bold uppercase text-slate-500">{node.layer}</span>{node.stage !== undefined && <span className="text-xs text-slate-400">Giai đoạn {node.stage}</span>}</div>
            <h3 className="truncate text-base font-bold text-slate-900">{node.label || node.name}{node.mapIndex !== undefined && node.mapIndex >= 0 ? ` [${node.mapIndex}]` : ''}</h3>
          </div>
        </div>
        <button onClick={onClose} className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100"><X className="size-5" /></button>
      </div>

      <div className="flex-1 space-y-6 overflow-y-auto px-6 py-5 text-xs">
        <section>
          <h4 className="text-[11px] font-bold uppercase tracking-wider text-slate-400">Thông tin thực thể</h4>
          <div className="mt-2.5 space-y-2 rounded-xl border border-slate-100 bg-slate-50/70 p-3.5">
            <div className="flex justify-between gap-3"><span className="text-slate-500">Node ID</span><span className="break-all text-right font-mono text-slate-800">{node.id}</span></div>
            <div className="flex justify-between"><span className="text-slate-500">Loại</span><span className="font-semibold">{node.type === 'job' ? 'Task / Job' : 'Dataset'}</span></div>
            {node.operator && <div className="flex justify-between"><span className="text-slate-500">Operator</span><span className="font-mono">{node.operator}</span></div>}
            {node.mapIndex !== undefined && <div className="flex justify-between"><span className="text-slate-500">Map index</span><span className="font-mono">{node.mapIndex}</span></div>}
            <div className="flex justify-between"><span className="text-slate-500">Trạng thái</span><span className={`inline-flex items-center gap-1 font-semibold ${tone.split(' ')[0]}`}><span className={`size-1.5 rounded-full ${tone.split(' ')[1]}`} />{node.status}</span></div>
            {node.recordCount !== undefined && <div className="flex justify-between"><span className="text-slate-500">Bản ghi</span><span className="font-bold">{node.recordCount.toLocaleString('vi-VN')}</span></div>}
            {(node.totalDuration ?? node.duration) !== undefined && <div className="flex justify-between"><span className="text-slate-500">Tổng thời gian</span><span className="font-mono">{node.totalDuration ?? node.duration}s</span></div>}
          </div>
        </section>

        {node.description && <section><h4 className="text-[11px] font-bold uppercase tracking-wider text-slate-400">Mô tả</h4><p className="mt-2 leading-relaxed text-slate-600">{node.description}</p></section>}

        {!!node.attempts?.length && <section>
          <h4 className="text-[11px] font-bold uppercase tracking-wider text-slate-400">Các lần thử</h4>
          <div className="mt-2 space-y-2">{node.attempts.map((attempt) => <div key={attempt.tryNumber} className="rounded-lg border border-slate-200 p-3">
            <div className="flex justify-between"><strong>Try {attempt.tryNumber}</strong><span className={statusTone(attempt.status).split(' ')[0]}>{attempt.status}</span></div>
            <div className="mt-1 text-[11px] text-slate-500">{attempt.startedAt ? new Date(attempt.startedAt).toLocaleString('vi-VN') : '—'}{attempt.duration !== undefined && attempt.duration !== null ? ` · ${attempt.duration}s` : ''}</div>
          </div>)}</div>
        </section>}

        {!!facets.length && <section>
          <h4 className="text-[11px] font-bold uppercase tracking-wider text-slate-400">Metadata đã ghi nhận</h4>
          <div className="mt-2 space-y-2">{facets.map(([name, value]) => <div key={name} className="rounded-lg border border-slate-200 p-3"><div className="font-mono font-semibold text-slate-800">{name}</div><pre className="mt-1 overflow-x-auto whitespace-pre-wrap text-[10px] text-slate-600">{typeof value === 'string' ? value : JSON.stringify(value, null, 2)}</pre></div>)}</div>
        </section>}
      </div>
    </div>
  );
}
