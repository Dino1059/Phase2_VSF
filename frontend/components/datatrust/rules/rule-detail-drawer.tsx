'use client';
import { useState, useEffect } from 'react';
import {
  CheckCircle2,
  History,
  Scale,
  Shield,
  ShieldAlert,
  ShieldCheck,
  X,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { apiBridge } from '@/lib/api-bridge';

export type UnifiedRuleItem = {
  ruleId: string;
  ruleName: string;
  datasetId: string;
  columnName: string;
  policy: string;
  policyId?: string | null;
  packId?: string | null;
  clauseId?: string | null;
  jurisdiction?: string;
  country?: string | null;
  version?: string;
  scope: string;
  condition: string;
  severity: string;
  status: string;
  requiredTreatment: string;
  source: string;
  description: string;
  ruleType: 'reliability' | 'compliance' | 'treatment';
  lane: 'Lane A' | 'Lane B' | 'Treatment';
  runtimeMode: string;
  effectiveFrom?: string | null;
  effectiveTo?: string | null;
  updatedAt?: string;
};

interface RuleDetailDrawerProps {
  rule: UnifiedRuleItem | null;
  onClose: () => void;
}

interface RunUsageItem {
  run_id: string;
  dataset_id: string;
  status: string;
  scanned_count?: number;
  silver_count?: number;
  quarantine_count?: number;
  started_at?: string;
}

export function RuleDetailDrawer({ rule, onClose }: RuleDetailDrawerProps) {
  const [showUsage, setShowUsage] = useState(false);
  const [loadingUsage, setLoadingUsage] = useState(false);
  const [runHistory, setRunHistory] = useState<RunUsageItem[]>([]);

  useEffect(() => {
    setShowUsage(false);
    setRunHistory([]);
  }, [rule?.ruleId]);

  if (!rule) return null;

  const handleFetchUsage = async () => {
    if (showUsage) {
      setShowUsage(false);
      return;
    }
    setLoadingUsage(true);
    setShowUsage(true);
    try {
      const runs = await apiBridge.fetchLivePipelineRuns();
      // Filter runs that correspond to this rule's dataset
      const cleanDs = rule.datasetId.replace('.csv', '');
      const filtered = (runs || []).filter((r: any) => {
        const runDs = (r.dataset_id || '').replace('.csv', '');
        return runDs === cleanDs || !r.dataset_id;
      });
      setRunHistory(filtered);
    } catch (err) {
      console.warn('Failed to fetch run usage:', err);
    } finally {
      setLoadingUsage(false);
    }
  };

  const getSeverityBadge = (severity: string) => {
    const s = severity.toUpperCase();
    if (s === 'CRITICAL') {
      return (
        <span className="inline-flex items-center gap-1 rounded-md bg-rose-50 border border-rose-200 px-2.5 py-0.5 text-[11px] font-extrabold text-rose-700">
          <ShieldAlert size={12} className="text-rose-600" />
          CRITICAL
        </span>
      );
    }
    if (s === 'HIGH') {
      return (
        <span className="inline-flex items-center gap-1 rounded-md bg-amber-50 border border-amber-200 px-2.5 py-0.5 text-[11px] font-extrabold text-amber-700">
          <ShieldAlert size={12} className="text-amber-600" />
          HIGH
        </span>
      );
    }
    return (
      <span className="inline-flex items-center gap-1 rounded-md bg-slate-100 border border-slate-200 px-2.5 py-0.5 text-[11px] font-bold text-slate-700">
        <Shield size={12} className="text-slate-500" />
        {s || 'NORMAL'}
      </span>
    );
  };

  return (
    <div className="fixed inset-0 z-50 overflow-hidden">
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-slate-950/30 backdrop-blur-2xs transition-opacity animate-in fade-in-50 duration-200"
        onClick={onClose}
      />

      {/* Drawer Container */}
      <div className="fixed inset-y-0 right-0 flex max-w-full pl-10">
        <div className="w-screen max-w-lg transform bg-white shadow-2xl transition-all duration-300 ease-in-out border-l border-slate-200 flex flex-col animate-in slide-in-from-right duration-300">
          {/* Header */}
          <div className="flex items-center justify-between border-b border-slate-100 px-6 py-4.5 bg-slate-50/50">
            <div className="flex items-center gap-2.5">
              <span className="grid size-8 place-items-center rounded-xl bg-[#04D3D4]/15 border border-[#04D3D4]/30 text-slate-950 font-bold">
                <Scale size={16} className="text-[#04D3D4]" />
              </span>
              <div>
                <h3 className="text-sm font-bold text-slate-900">Chi tiết Quy tắc (Rule Detail)</h3>
                <p className="text-[11px] font-mono text-slate-500">{rule.ruleId}</p>
              </div>
            </div>
            <button
              onClick={onClose}
              className="grid size-8 place-items-center rounded-lg text-slate-400 hover:bg-slate-100 hover:text-slate-700 transition"
            >
              <X size={18} />
            </button>
          </div>

          {/* Body Content */}
          <div className="flex-1 overflow-y-auto p-6 space-y-5">
            {/* Rule Identity Card */}
            <div className="rounded-xl border border-slate-200/80 bg-slate-50/50 p-4 space-y-3">
              <div className="flex items-center justify-between">
                <span className="font-mono text-xs font-extrabold text-slate-950 px-2 py-0.5 rounded bg-white border border-slate-200 shadow-2xs">
                  {rule.ruleId}
                </span>
                <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 border border-emerald-200 px-2.5 py-0.5 text-[10px] font-extrabold text-emerald-800">
                  <CheckCircle2 size={11} className="text-emerald-600" />
                  {rule.status}
                </span>
              </div>

              <div>
                <h4 className="text-sm font-bold text-slate-900">{rule.ruleName}</h4>
                {rule.description && (
                  <p className="mt-1 text-xs text-slate-600 leading-relaxed">
                    {rule.description}
                  </p>
                )}
              </div>
            </div>

            {/* Spec 5.1 & 18 Properties Grid */}
            <div className="space-y-3.5 text-xs">
              {/* Policy */}
              <div className="rounded-xl border border-slate-100 bg-white p-3.5 shadow-2xs">
                <span className="text-[11px] font-bold text-slate-400 uppercase tracking-wider block">
                  Policy / Căn cứ pháp lý
                </span>
                <div className="mt-1 font-semibold text-slate-900 flex items-center gap-1.5">
                  <ShieldCheck size={14} className="text-[#04D3D4]" />
                  <span>{rule.policy}</span>
                </div>
              </div>

              <div className="rounded-xl border border-slate-100 bg-white p-3.5 shadow-2xs">
                <span className="text-[11px] font-bold text-slate-400 uppercase tracking-wider block">Traceability</span>
                <dl className="mt-2 grid grid-cols-2 gap-x-4 gap-y-2 text-xs">
                  <div><dt className="text-slate-400">Jurisdiction</dt><dd className="font-mono font-bold text-slate-900">{rule.jurisdiction || '—'}</dd></div>
                  <div><dt className="text-slate-400">Country / State</dt><dd className="font-mono font-bold text-slate-900">{rule.country || '—'}</dd></div>
                  <div><dt className="text-slate-400">Policy ID</dt><dd className="break-all font-mono text-slate-700">{rule.policyId || '—'}</dd></div>
                  <div><dt className="text-slate-400">Policy pack</dt><dd className="break-all font-mono text-slate-700">{rule.packId || '—'}</dd></div>
                  <div><dt className="text-slate-400">Clause</dt><dd className="break-all font-mono text-slate-700">{rule.clauseId || '—'}</dd></div>
                  <div><dt className="text-slate-400">Rule version</dt><dd className="font-mono text-slate-700">{rule.version || '—'}</dd></div>
                </dl>
              </div>

              {/* Target & Scope */}
              <div className="grid grid-cols-2 gap-3">
                <div className="rounded-xl border border-slate-100 bg-white p-3.5 shadow-2xs">
                  <span className="text-[11px] font-bold text-slate-400 uppercase tracking-wider block">
                    Target Column
                  </span>
                  <div className="mt-1 font-mono font-bold text-slate-900 truncate">
                    {rule.columnName}
                  </div>
                </div>

                <div className="rounded-xl border border-slate-100 bg-white p-3.5 shadow-2xs">
                  <span className="text-[11px] font-bold text-slate-400 uppercase tracking-wider block">
                    Dataset Scope
                  </span>
                  <div className="mt-1 font-mono text-slate-700 truncate">
                    {rule.datasetId.replace('.csv', '')}
                  </div>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div className="rounded-xl border border-slate-100 bg-white p-3.5 shadow-2xs">
                  <span className="text-[11px] font-bold text-slate-400 uppercase tracking-wider block">Effective from</span>
                  <div className="mt-1 font-mono text-slate-700">{rule.effectiveFrom ? new Date(rule.effectiveFrom).toLocaleString('vi-VN') : '—'}</div>
                </div>
                <div className="rounded-xl border border-slate-100 bg-white p-3.5 shadow-2xs">
                  <span className="text-[11px] font-bold text-slate-400 uppercase tracking-wider block">Effective to</span>
                  <div className="mt-1 font-mono text-slate-700">{rule.effectiveTo ? new Date(rule.effectiveTo).toLocaleString('vi-VN') : 'Không giới hạn'}</div>
                </div>
              </div>

              {/* Condition / Expression */}
              <div className="rounded-xl border border-slate-100 bg-white p-3.5 shadow-2xs">
                <span className="text-[11px] font-bold text-slate-400 uppercase tracking-wider block">
                  Condition / Biểu thức logic
                </span>
                <div className="mt-1.5 rounded-lg bg-slate-950 p-3 font-mono text-xs text-[#04D3D4] overflow-x-auto">
                  <code>{rule.condition}</code>
                </div>
              </div>

              {/* Severity & Required Treatment */}
              <div className="grid grid-cols-2 gap-3">
                <div className="rounded-xl border border-slate-100 bg-white p-3.5 shadow-2xs">
                  <span className="text-[11px] font-bold text-slate-400 uppercase tracking-wider block">Lane</span>
                  <div className="mt-1 font-bold text-slate-900">{rule.lane}</div>
                </div>
                <div className="rounded-xl border border-slate-100 bg-white p-3.5 shadow-2xs">
                  <span className="text-[11px] font-bold text-slate-400 uppercase tracking-wider block">Runtime mode</span>
                  <div className="mt-1 font-mono font-bold text-slate-900">{rule.runtimeMode}</div>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div className="rounded-xl border border-slate-100 bg-white p-3.5 shadow-2xs">
                  <span className="text-[11px] font-bold text-slate-400 uppercase tracking-wider block">
                    Severity
                  </span>
                  <div className="mt-1.5">{getSeverityBadge(rule.severity)}</div>
                </div>

                <div className="rounded-xl border border-slate-100 bg-white p-3.5 shadow-2xs">
                  <span className="text-[11px] font-bold text-slate-400 uppercase tracking-wider block">
                    Required Treatment
                  </span>
                  <div className="mt-1 font-mono font-bold text-slate-900">
                    {rule.requiredTreatment}
                  </div>
                </div>
              </div>

              {/* Source & Updated */}
              <div className="grid grid-cols-2 gap-3">
                <div className="rounded-xl border border-slate-100 bg-white p-3.5 shadow-2xs">
                  <span className="text-[11px] font-bold text-slate-400 uppercase tracking-wider block">
                    Source
                  </span>
                  <div className="mt-1 text-slate-700 line-clamp-1">{rule.source}</div>
                </div>

                <div className="rounded-xl border border-slate-100 bg-white p-3.5 shadow-2xs">
                  <span className="text-[11px] font-bold text-slate-400 uppercase tracking-wider block">
                    Updated
                  </span>
                  <div className="mt-1 font-mono text-slate-700">
                    {rule.updatedAt ? new Date(rule.updatedAt).toLocaleDateString('vi-VN') : '—'}
                  </div>
                </div>
              </div>
            </div>

            {/* Optional Action: [ View usage ] - Spec 18 */}
            <div className="border-t border-slate-100 pt-4">
              <div className="flex items-center justify-between">
                <div>
                  <span className="text-xs font-bold text-slate-900 block">Lịch sử pipeline theo dataset</span>
                  <span className="text-[11px] text-slate-500">
                    Các run cùng dataset; không thay thế execution evidence theo rule.
                  </span>
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleFetchUsage}
                  disabled={loadingUsage}
                  className="h-8 gap-1.5 text-xs font-bold border-slate-300 hover:border-slate-900 hover:bg-slate-100 text-slate-800 cursor-pointer shadow-2xs"
                >
                  <History size={13} className={loadingUsage ? 'animate-spin' : 'text-[#04D3D4]'} />
                  <span>{showUsage ? 'Ẩn usage' : 'View usage'}</span>
                </Button>
              </div>

              {/* Usage Runs List (Live from /api/runs) */}
              {showUsage && (
                <div className="mt-3.5 rounded-xl border border-slate-200 bg-slate-50/70 p-3.5 space-y-2.5 animate-in fade-in-50 duration-200">
                  <span className="text-[10px] font-extrabold uppercase tracking-wider text-slate-500 block">
                    Các lần chạy đã sử dụng ({runHistory.length} runs):
                  </span>

                  {runHistory.length === 0 ? (
                    <div className="py-4 text-center text-xs text-slate-400">
                      Chưa có lần chạy nào được ghi nhận cho bộ dữ liệu này.
                    </div>
                  ) : (
                    <div className="space-y-2 max-h-52 overflow-y-auto pr-1">
                      {runHistory.map((run) => (
                        <div
                          key={run.run_id}
                          className="flex items-center justify-between rounded-lg border border-slate-200/80 bg-white p-2.5 text-xs shadow-2xs"
                        >
                          <div>
                            <span className="font-mono font-bold text-slate-900 block truncate max-w-[200px]">
                              {run.run_id}
                            </span>
                            <span className="text-[10px] text-slate-400">
                              {run.started_at ? new Date(run.started_at).toLocaleString('vi-VN') : 'Gần đây'}
                            </span>
                          </div>

                          <div className="text-right">
                            <span
                              className={`inline-block rounded px-1.5 py-0.5 text-[10px] font-extrabold ${
                                run.status === 'COMPLETED' || run.status === 'success'
                                  ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                                  : 'bg-amber-50 text-amber-700 border border-amber-200'
                              }`}
                            >
                              {run.status}
                            </span>
                            {run.scanned_count !== undefined && (
                              <span className="block text-[10px] text-slate-500 font-mono mt-0.5">
                                {run.scanned_count.toLocaleString()} rows
                              </span>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>

          {/* Footer */}
          <div className="border-t border-slate-100 bg-slate-50/50 px-6 py-3.5 flex items-center justify-between">
            <span className="text-[11px] text-slate-400">
              Chế độ xem chỉ đọc (Read-Only)
            </span>
            <Button
              size="sm"
              variant="outline"
              onClick={onClose}
              className="h-8 px-4 text-xs font-semibold"
            >
              Đóng
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
