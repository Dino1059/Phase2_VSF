'use client';
import { useState, useMemo, useEffect } from 'react';
import {
  CheckCircle2,
  Database,
  Filter,
  Info,
  Lock,
  RefreshCw,
  Search,
  Shield,
  ShieldAlert,
  Wand2,
} from 'lucide-react';
import { Card } from '@/components/ui/card';
import {
  useAgentStore,
  type ComplianceCheckRule,
  type DataTreatmentRule,
} from '@/lib/agent-store';
import { RuleDetailDrawer, type UnifiedRuleItem } from './rule-detail-drawer';

export function RuleApprovalPage() {
  const {
    datasets,
    selectedDatasetId,
    selectDataset,
    complianceCheckRules,
    dataTreatmentRules,
    isBackendLive,
    isSyncing,
    syncWithBackend,
  } = useAgentStore();

  useEffect(() => {
    syncWithBackend();
  }, [syncWithBackend]);

  // Drawer state
  const [activeRuleForDrawer, setActiveRuleForDrawer] = useState<UnifiedRuleItem | null>(null);

  // Filter states
  const [searchQuery, setSearchQuery] = useState('');
  const [typeFilter, setTypeFilter] = useState<'all' | 'compliance' | 'treatment'>('all');

  // Datasets options for dropdown
  const datasetOptions = useMemo(() => {
    const map = new Map<string, string>();
    Object.values(datasets || {}).forEach((ds) => {
      if (ds && (ds.id || ds.filename)) {
        const canonicalKey = (ds.id || ds.filename || '').replace('.csv', '');
        if (!map.has(canonicalKey)) {
          map.set(canonicalKey, ds.title || canonicalKey);
        }
      }
    });
    return Array.from(map.entries());
  }, [datasets]);

  // Unify compliance and treatment rules into spec 18 format
  const unifiedRules = useMemo<UnifiedRuleItem[]>(() => {
    const list: UnifiedRuleItem[] = [];

    // 1. Fixed Compliance Check Rules (from policy.compliance_rules)
    complianceCheckRules.forEach((r: ComplianceCheckRule) => {
      list.push({
        ruleId: r.rule_id,
        ruleName: r.rule_name,
        datasetId: r.dataset_id,
        columnName: r.column_name,
        policy: r.law_ref,
        version: 'v1.4',
        scope: `${r.dataset_id.replace('.csv', '')}.${r.column_name}`,
        condition: r.expression,
        severity: r.severity || 'HIGH',
        status: 'Active (Cố định)',
        requiredTreatment: r.on_fail_action || 'QUARANTINE',
        source: r.law_ref,
        description: r.description || `Kiểm tra tuân thủ bắt buộc trên trường ${r.column_name}.`,
        ruleType: 'compliance',
        updatedAt: r.enforced_at,
      });
    });

    // 2. Data Treatment Rules (from policy.data_treatment_rules)
    dataTreatmentRules.forEach((r: DataTreatmentRule) => {
      list.push({
        ruleId: r.rule_id,
        ruleName: r.treatment_name,
        datasetId: r.dataset_id,
        columnName: r.column_name,
        policy: 'Luật 91/2025/QH15 & Nghị định 356/2025/NĐ-CP',
        version: 'v1.2',
        scope: `${r.dataset_id.replace('.csv', '')}.${r.column_name}`,
        condition: r.expression_display,
        severity: r.is_ai_proposed ? 'HIGH' : 'NORMAL',
        status: r.status === 'active' ? 'Active' : r.status,
        requiredTreatment: r.operation_id,
        source: 'GSM Data Protection Standard',
        description: r.description || r.treatment_name,
        ruleType: 'treatment',
        updatedAt: r.updated_at || r.created_at,
      });
    });

    return list;
  }, [complianceCheckRules, dataTreatmentRules]);

  // Filter rules by selected dataset, search query, and rule type
  const filteredRules = useMemo(() => {
    return unifiedRules.filter((rule) => {
      // Dataset filter
      if (selectedDatasetId && selectedDatasetId !== 'all') {
        const cleanSelected = selectedDatasetId.replace('.csv', '');
        const cleanRuleDs = rule.datasetId.replace('.csv', '');
        if (cleanRuleDs !== cleanSelected) return false;
      }

      // Type filter
      if (typeFilter !== 'all' && rule.ruleType !== typeFilter) {
        return false;
      }

      // Search query
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase().trim();
        return (
          rule.ruleId.toLowerCase().includes(q) ||
          rule.ruleName.toLowerCase().includes(q) ||
          rule.columnName.toLowerCase().includes(q) ||
          rule.policy.toLowerCase().includes(q) ||
          rule.condition.toLowerCase().includes(q) ||
          rule.scope.toLowerCase().includes(q)
        );
      }

      return true;
    });
  }, [unifiedRules, selectedDatasetId, typeFilter, searchQuery]);

  const getSeverityBadge = (severity: string) => {
    const s = severity.toUpperCase();
    if (s === 'CRITICAL') {
      return (
        <span className="inline-flex items-center gap-1 rounded-md bg-rose-50 border border-rose-200 px-2 py-0.5 text-[10px] font-extrabold text-rose-700">
          <ShieldAlert size={11} className="text-rose-600" />
          CRITICAL
        </span>
      );
    }
    if (s === 'HIGH') {
      return (
        <span className="inline-flex items-center gap-1 rounded-md bg-amber-50 border border-amber-200 px-2 py-0.5 text-[10px] font-extrabold text-amber-700">
          <ShieldAlert size={11} className="text-amber-600" />
          HIGH
        </span>
      );
    }
    return (
      <span className="inline-flex items-center gap-1 rounded-md bg-slate-100 border border-slate-200 px-2 py-0.5 text-[10px] font-bold text-slate-700">
        <Shield size={11} className="text-slate-500" />
        {s}
      </span>
    );
  };

  return (
    <div className="page-enter mx-auto max-w-[1500px] space-y-6">
      {/* Header Banner */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <span className="text-[11px] font-bold uppercase tracking-wider text-slate-500">
            Data Governance & IPO Assurance · Applied Rules
          </span>
          <h1 className="text-2xl font-bold tracking-tight text-slate-950 sm:text-3xl">
            Quy tắc & Chính sách Tuân thủ (Applied Rules)
          </h1>
          <p className="mt-1 text-xs text-slate-600">
            Xem danh sách các quy tắc kiểm soát tuân thủ và xử lý dữ liệu đang áp dụng cho bộ dữ liệu
            hiện tại. Chế độ kiểm tra chỉ đọc (Read-Only).
          </p>
        </div>

        {/* Backend Status & Sync */}
        <div className="flex items-center gap-2.5">
          {isBackendLive ? (
            <div className="flex items-center gap-1.5 rounded-xl border border-emerald-200 bg-emerald-50 px-3 py-1.5 text-xs font-semibold text-emerald-800 shadow-2xs">
              <span className="size-2 rounded-full bg-emerald-500 animate-pulse" />
              <span>Live Backend (:8000)</span>
              <button
                onClick={() => syncWithBackend()}
                title="Làm mới dữ liệu từ PostgreSQL"
                className="ml-1 text-emerald-600 hover:text-emerald-900 transition-colors cursor-pointer"
              >
                <RefreshCw className={`size-3 ${isSyncing ? 'animate-spin' : ''}`} />
              </button>
            </div>
          ) : (
            <div className="flex items-center gap-1.5 rounded-xl border border-amber-200 bg-amber-50 px-3 py-1.5 text-xs font-semibold text-amber-800 shadow-2xs">
              <span className="size-2 rounded-full bg-amber-500" />
              <span>Offline / Syncing</span>
            </div>
          )}
        </div>
      </div>

      {/* Filter Bar Card */}
      <div className="rounded-2xl border border-slate-200 bg-white p-4.5 shadow-2xs space-y-3.5">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
          {/* Dataset Selector Dropdown */}
          <div className="flex items-center gap-2 min-w-0">
            <span className="text-xs font-bold text-slate-700 whitespace-nowrap flex items-center gap-1.5">
              <Database size={14} className="text-[#04D3D4]" />
              Bộ dữ liệu:
            </span>
            <select
              value={selectedDatasetId || 'all'}
              onChange={(e) => {
                const val = e.target.value;
                selectDataset(val === 'all' ? '' : val);
              }}
              className="h-9 rounded-xl border border-slate-200 bg-slate-50 px-3 font-mono text-xs font-semibold text-slate-900 focus:bg-white focus:outline-none focus:ring-2 focus:ring-[#04D3D4]/40 focus:border-[#04D3D4] transition"
            >
              <option value="all">Tất cả các bộ dữ liệu ({datasetOptions.length} bảng)</option>
              {datasetOptions.map(([id, title]) => (
                <option key={id} value={id}>
                  {id} ({title})
                </option>
              ))}
            </select>
          </div>

          {/* Search Box */}
          <div className="relative flex-1 max-w-md">
            <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 size-4 text-slate-400" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="🔍 Tìm theo Rule ID, tên rule, cột đích, căn cứ pháp lý..."
              className="w-full h-9.5 pl-9 pr-3 rounded-xl border border-slate-200 bg-slate-50 text-xs font-medium text-slate-900 placeholder:text-slate-400 focus:bg-white focus:outline-none focus:ring-2 focus:ring-[#04D3D4]/40 focus:border-[#04D3D4] transition"
            />
          </div>
        </div>

        {/* Tab Filter (All / Compliance / Treatment) */}
        <div className="flex items-center gap-2 border-t border-slate-100 pt-3">
          <span className="text-xs font-bold text-slate-500 mr-1 flex items-center gap-1">
            <Filter size={12} />
            Phân loại:
          </span>
          <button
            onClick={() => setTypeFilter('all')}
            className={`rounded-lg px-3 py-1 text-xs font-bold transition cursor-pointer ${
              typeFilter === 'all'
                ? 'bg-slate-950 text-white shadow-2xs'
                : 'text-slate-600 hover:bg-slate-100'
            }`}
          >
            Tất cả ({unifiedRules.length})
          </button>
          <button
            onClick={() => setTypeFilter('compliance')}
            className={`rounded-lg px-3 py-1 text-xs font-bold transition cursor-pointer flex items-center gap-1.5 ${
              typeFilter === 'compliance'
                ? 'bg-slate-950 text-[#04D3D4] shadow-2xs'
                : 'text-slate-600 hover:bg-slate-100'
            }`}
          >
            <Lock size={12} className="text-rose-500" />
            <span>Kiểm tra tuân thủ ({complianceCheckRules.length})</span>
          </button>
          <button
            onClick={() => setTypeFilter('treatment')}
            className={`rounded-lg px-3 py-1 text-xs font-bold transition cursor-pointer flex items-center gap-1.5 ${
              typeFilter === 'treatment'
                ? 'bg-slate-950 text-[#04D3D4] shadow-2xs'
                : 'text-slate-600 hover:bg-slate-100'
            }`}
          >
            <Wand2 size={12} className="text-[#04D3D4]" />
            <span>Xử lý dữ liệu ({dataTreatmentRules.length})</span>
          </button>
        </div>
      </div>

      {/* Applied Rules Table matching Spec 18 */}
      <Card className="rounded-2xl border border-slate-200 bg-white shadow-xs overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs border-collapse">
            <thead>
              <tr className="border-b border-slate-200 bg-slate-50/70 text-[11px] font-extrabold uppercase tracking-wider text-slate-500">
                <th className="py-3.5 px-4">Rule ID</th>
                <th className="py-3.5 px-4">Rule name</th>
                <th className="py-3.5 px-4">Policy</th>
                <th className="py-3.5 px-4">Version</th>
                <th className="py-3.5 px-4">Scope</th>
                <th className="py-3.5 px-4">Severity</th>
                <th className="py-3.5 px-4">Status</th>
                <th className="py-3.5 px-4 text-right">Updated</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {filteredRules.length === 0 ? (
                <tr>
                  <td colSpan={8} className="py-12 text-center text-xs text-slate-400">
                    Không tìm thấy rule nào đang áp dụng cho bộ dữ liệu hoặc điều kiện lọc này.
                  </td>
                </tr>
              ) : (
                filteredRules.map((rule) => {
                  return (
                    <tr
                      key={rule.ruleId}
                      onClick={() => setActiveRuleForDrawer(rule)}
                      className="group cursor-pointer hover:bg-slate-50/80 transition-colors"
                      title="Bấm để xem chi tiết Rule Detail Drawer"
                    >
                      {/* Rule ID */}
                      <td className="py-3.5 px-4">
                        <span className="font-mono font-bold text-slate-950 group-hover:text-[#008b74] transition-colors">
                          {rule.ruleId}
                        </span>
                        {rule.ruleType === 'compliance' ? (
                          <span className="ml-1.5 inline-block rounded bg-rose-50 px-1.5 py-0.2 text-[9px] font-bold text-rose-700 border border-rose-200">
                            Fixed
                          </span>
                        ) : null}
                      </td>

                      {/* Rule Name */}
                      <td className="py-3.5 px-4 font-semibold text-slate-900 max-w-[260px] truncate">
                        {rule.ruleName}
                      </td>

                      {/* Policy */}
                      <td className="py-3.5 px-4 text-slate-600 max-w-[200px] truncate">
                        {rule.policy}
                      </td>

                      {/* Version */}
                      <td className="py-3.5 px-4 font-mono text-[11px] text-slate-500">
                        {rule.version || 'v1.0'}
                      </td>

                      {/* Scope */}
                      <td className="py-3.5 px-4 font-mono text-slate-700 truncate max-w-[160px]">
                        {rule.columnName}
                      </td>

                      {/* Severity */}
                      <td className="py-3.5 px-4">{getSeverityBadge(rule.severity)}</td>

                      {/* Status */}
                      <td className="py-3.5 px-4">
                        <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 border border-emerald-200 px-2.5 py-0.5 text-[10px] font-extrabold text-emerald-800">
                          <CheckCircle2 size={11} className="text-emerald-600" />
                          {rule.status}
                        </span>
                      </td>

                      {/* Updated */}
                      <td className="py-3.5 px-4 text-right font-mono text-[11px] text-slate-500">
                        {rule.updatedAt
                          ? new Date(rule.updatedAt).toLocaleDateString('vi-VN')
                          : 'Hệ thống'}
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>

        {/* Footer info banner */}
        <div className="flex items-center justify-between border-t border-slate-100 bg-slate-50/50 px-5 py-3 text-[11px] text-slate-500">
          <div className="flex items-center gap-2">
            <Info size={13} className="text-slate-400" />
            <span>
              Bấm vào bất kỳ dòng nào để xem <strong>Rule Detail Drawer</strong> và lịch sử thực thi{' '}
              <strong>[View usage]</strong>.
            </span>
          </div>
          <span>Tổng số: {filteredRules.length} rule áp dụng</span>
        </div>
      </Card>

      {/* Rule Detail Right Drawer */}
      <RuleDetailDrawer
        rule={activeRuleForDrawer}
        onClose={() => setActiveRuleForDrawer(null)}
      />
    </div>
  );
}
