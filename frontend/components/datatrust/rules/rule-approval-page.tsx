'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { Activity, Database, RefreshCw, Scale, Search, Wand2 } from 'lucide-react';
import { Card } from '@/components/ui/card';
import { useAgentStore } from '@/lib/agent-store';
import { apiBridge, type ComplianceCheckRule, type DataTreatmentRule, type ReliabilityRule } from '@/lib/api-bridge';
import { RuleDetailDrawer, type UnifiedRuleItem } from './rule-detail-drawer';

type RuleTab = 'reliability' | 'compliance' | 'treatment';
const tabs = {
  reliability: { label: 'Technical Rules', lane: 'Lane A', icon: Activity },
  compliance: { label: 'Compliance Rules', lane: 'Lane B', icon: Scale },
  treatment: { label: 'Data Treatments', lane: 'Lane B', icon: Wand2 },
} satisfies Record<RuleTab, { label: string; lane: string; icon: typeof Activity }>;

const badgeClass = (value: string) => {
  const normalized = value.toUpperCase();
  if (['ACTIVE', 'ENFORCED'].includes(normalized)) return 'border-emerald-200 bg-emerald-50 text-emerald-700';
  if (['SHADOW', 'PENDING', 'PENDING_APPROVAL'].includes(normalized)) return 'border-amber-200 bg-amber-50 text-amber-700';
  if (normalized === 'NOT CONFIGURED') return 'border-rose-200 bg-rose-50 text-rose-700';
  return 'border-slate-200 bg-slate-100 text-slate-600';
};

const runtimeMode = (value?: string) => value?.toUpperCase() || 'NOT CONFIGURED';
const versionLabel = (version?: number) => `v${version ?? 1}`;

export function RuleApprovalPage() {
  const { datasets, selectedDatasetId, selectDataset } = useAgentStore();
  const [tab, setTab] = useState<RuleTab>('reliability');
  const [query, setQuery] = useState('');
  const [rules, setRules] = useState<UnifiedRuleItem[]>([]);
  const [selected, setSelected] = useState<UnifiedRuleItem | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const datasetOptions = useMemo(() => {
    const result = new Map<string, string>();
    Object.values(datasets || {}).forEach((dataset) => {
      const id = (dataset?.id || dataset?.filename || '').replace('.csv', '');
      if (id) result.set(id, dataset.title || id);
    });
    return [...result.entries()];
  }, [datasets]);

  const loadRules = useCallback(async () => {
    setLoading(true);
    setError(null);
    const datasetId = selectedDatasetId && selectedDatasetId !== 'all' ? selectedDatasetId : undefined;
    try {
      if (tab === 'reliability') {
        const data = await apiBridge.fetchReliabilityRules(datasetId);
        setRules(data.map((rule: ReliabilityRule) => ({
          ruleId: rule.rule_id, ruleName: rule.rule_name || rule.detector_id, datasetId: rule.dataset_id,
          columnName: rule.target_fields?.join(', ') || 'dataset', policy: 'Data quality configuration',
          version: versionLabel(rule.version), scope: `${rule.dataset_id}.${rule.target_fields?.join(',') || '*'}`,
          condition: `${rule.detector_id} ${JSON.stringify(rule.params_json || {})}`, severity: rule.severity || 'MEDIUM',
          status: rule.status || 'DRAFT', requiredTreatment: rule.on_fail_action || 'QUARANTINE',
          source: 'engine.reliability_rules', description: rule.description || 'Cấu hình detector kỹ thuật cho Lane A.',
          ruleType: 'reliability', lane: 'Lane A', runtimeMode: runtimeMode(rule.runtime_mode),
          effectiveFrom: rule.effective_from, effectiveTo: rule.effective_to, updatedAt: rule.updated_at,
        })));
      } else if (tab === 'compliance') {
        const data = await apiBridge.fetchComplianceCheckRules(datasetId);
        setRules(data.map((rule: ComplianceCheckRule) => ({
          ruleId: rule.rule_id, ruleName: rule.rule_name, datasetId: rule.dataset_id, columnName: rule.column_name,
          policy: rule.policy_name || rule.law_ref, policyId: rule.policy_id, packId: rule.pack_id, clauseId: rule.clause_id,
          jurisdiction: rule.jurisdiction, country: rule.country, version: versionLabel(rule.version),
          scope: `${rule.dataset_id}.${rule.column_name}`, condition: rule.expression || JSON.stringify(rule.condition_json || {}),
          severity: rule.severity || 'HIGH', status: rule.status || 'DRAFT', requiredTreatment: rule.on_fail_action || 'QUARANTINE',
          source: rule.law_ref, description: rule.description || 'Kiểm tra tuân thủ pháp lý cho Lane B.',
          ruleType: 'compliance', lane: 'Lane B', runtimeMode: runtimeMode(rule.runtime_mode),
          effectiveFrom: rule.effective_from, effectiveTo: rule.effective_to, updatedAt: rule.enforced_at,
        })));
      } else {
        const data = await apiBridge.fetchDataTreatmentRules(datasetId);
        setRules(data.map((rule: DataTreatmentRule) => ({
          ruleId: rule.rule_id, ruleName: rule.treatment_name, datasetId: rule.dataset_id, columnName: rule.column_name,
          policy: rule.policy_name || rule.law_ref || 'Data treatment', policyId: rule.policy_id, packId: rule.pack_id,
          clauseId: rule.clause_id, jurisdiction: rule.jurisdiction, country: rule.country, version: versionLabel(rule.version),
          scope: `${rule.dataset_id}.${rule.column_name}`, condition: rule.expression_display || JSON.stringify(rule.params_json || {}),
          severity: rule.is_ai_proposed ? 'HIGH' : 'NORMAL', status: rule.status, requiredTreatment: rule.operation_id,
          source: rule.law_ref || 'policy.data_treatment_rules', description: rule.description || rule.treatment_name,
          ruleType: 'treatment', lane: 'Lane B', runtimeMode: runtimeMode(rule.runtime_mode),
          effectiveFrom: rule.effective_from, effectiveTo: rule.effective_to, updatedAt: rule.updated_at,
        })));
      }
    } catch (cause) {
      setRules([]);
      setError(cause instanceof Error ? cause.message : 'Không thể tải rules từ backend');
    } finally { setLoading(false); }
  }, [selectedDatasetId, tab]);

  useEffect(() => { void loadRules(); }, [loadRules]);
  const filtered = rules.filter((rule) => {
    const value = query.trim().toLowerCase();
    return !value || [rule.ruleId, rule.ruleName, rule.columnName, rule.policy, rule.jurisdiction, rule.country, rule.packId, rule.clauseId]
      .some((field) => field?.toLowerCase().includes(value));
  });

  return <div className="page-enter mx-auto max-w-[1500px] space-y-5">
    <div className="flex items-end justify-between gap-4"><div>
      <span className="text-[11px] font-bold uppercase tracking-wider text-slate-500">Read-only policy registry</span>
      <h1 className="text-2xl font-bold tracking-tight text-slate-950 sm:text-3xl">Rules & Policies</h1>
      <p className="mt-1 text-xs text-slate-600">Rule metadata được tải trực tiếp từ database; trang này không thay đổi hoặc phê duyệt rule.</p>
    </div><button onClick={() => void loadRules()} disabled={loading} className="flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-bold text-slate-700 shadow-2xs"><RefreshCw size={14} className={loading ? 'animate-spin' : ''} /> Làm mới</button></div>

    <div className="grid gap-2 sm:grid-cols-3">{(Object.keys(tabs) as RuleTab[]).map((key) => {
      const Icon = tabs[key].icon;
      return <button key={key} onClick={() => setTab(key)} className={`rounded-2xl border p-4 text-left transition ${tab === key ? 'border-[#04D3D4] bg-[#04D3D4]/8 shadow-sm' : 'border-slate-200 bg-white hover:border-slate-300'}`}>
        <div className="flex items-center justify-between"><Icon size={17} className={tab === key ? 'text-[#008b8c]' : 'text-slate-500'} /><span className="rounded-md bg-slate-100 px-2 py-0.5 text-[10px] font-extrabold text-slate-600">{tabs[key].lane}</span></div><div className="mt-2 text-sm font-bold text-slate-950">{tabs[key].label}</div>
      </button>;
    })}</div>

    <div className="flex flex-col gap-3 rounded-2xl border border-slate-200 bg-white p-4 sm:flex-row sm:items-center">
      <label className="flex items-center gap-2 text-xs font-bold text-slate-700"><Database size={14} className="text-[#04D3D4]" /> Dataset<select value={selectedDatasetId || 'all'} onChange={(event) => selectDataset(event.target.value === 'all' ? '' : event.target.value)} className="h-9 rounded-xl border border-slate-200 bg-slate-50 px-3 font-mono text-xs"><option value="all">Tất cả datasets</option>{datasetOptions.map(([id, name]) => <option key={id} value={id}>{name}</option>)}</select></label>
      <div className="relative flex-1"><Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-slate-400" /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Tìm rule, jurisdiction, pack hoặc clause..." className="h-9 w-full rounded-xl border border-slate-200 bg-slate-50 pl-9 pr-3 text-xs" /></div>
    </div>

    <Card className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-xs"><div className="overflow-x-auto"><table className="w-full text-left text-xs"><thead><tr className="border-b border-slate-200 bg-slate-50 text-[10px] font-extrabold uppercase tracking-wider text-slate-500"><th className="px-4 py-3">Rule</th><th className="px-4 py-3">Jurisdiction</th><th className="px-4 py-3">Target</th><th className="px-4 py-3">Version</th><th className="px-4 py-3">Status</th><th className="px-4 py-3">Runtime</th><th className="px-4 py-3">Action / Function</th></tr></thead><tbody className="divide-y divide-slate-100">
      {loading && <tr><td colSpan={7} className="p-10 text-center text-slate-400">Đang tải rules từ backend...</td></tr>}
      {!loading && error && <tr><td colSpan={7} className="p-10 text-center text-rose-600"><strong>Không tải được dữ liệu.</strong><div className="mt-1 font-mono text-[11px]">{error}</div></td></tr>}
      {!loading && !error && filtered.length === 0 && <tr><td colSpan={7} className="p-10 text-center text-slate-400">Không có rule phù hợp.</td></tr>}
      {!loading && !error && filtered.map((rule) => <tr key={`${rule.ruleType}-${rule.ruleId}`} onClick={() => setSelected(rule)} className="cursor-pointer hover:bg-slate-50">
        <td className="px-4 py-3"><div className="font-mono font-bold text-slate-950">{rule.ruleId}</div><div className="mt-0.5 max-w-[280px] truncate text-slate-500">{rule.ruleName}</div></td>
        <td className="px-4 py-3"><div className="font-mono font-bold text-slate-700">{rule.jurisdiction || '—'}</div>{rule.country && <div className="text-[10px] text-slate-500">{rule.country}</div>}</td>
        <td className="px-4 py-3 font-mono text-slate-700">{rule.columnName}</td><td className="px-4 py-3 font-mono text-slate-600">{rule.version}</td>
        <td className="px-4 py-3"><span className={`rounded-full border px-2 py-0.5 text-[10px] font-extrabold ${badgeClass(rule.status)}`}>{rule.status}</span></td>
        <td className="px-4 py-3"><span className={`rounded-full border px-2 py-0.5 text-[10px] font-extrabold ${badgeClass(rule.runtimeMode)}`}>{rule.runtimeMode}</span></td>
        <td className="px-4 py-3 font-mono font-bold text-slate-700">{rule.requiredTreatment}</td>
      </tr>)}</tbody></table></div></Card>
    <RuleDetailDrawer rule={selected} onClose={() => setSelected(null)} />
  </div>;
}
