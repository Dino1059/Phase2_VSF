import { useState, useEffect } from 'react';
import {
  Check,
  CheckCircle2,
  Lock,
  Pause,
  Pencil,
  Play,
  RefreshCw,
  Search,
  ShieldCheck,
  Sparkles,
  Wand2,
  X,
} from 'lucide-react';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  useAgentStore,
  type DatasetItem,
  type ComplianceCheckRule,
  type DataTreatmentRule,
} from '@/lib/agent-store';

export function RuleApprovalPage() {
  const {
    currentRole,
    datasets,
    selectedDatasetId,
    selectDataset,
    complianceCheckRules,
    dataTreatmentRules,
    rulesMainTab,
    setRulesMainTab,
    updateTreatmentRuleExpression,
    approveTreatmentRule,
    rejectTreatmentRule,
    toggleTreatmentRuleStatus,
    isBackendLive,
    isSyncing,
    syncWithBackend,
  } = useAgentStore();

  useEffect(() => {
    syncWithBackend();
  }, [syncWithBackend]);

  // Sub-tabs & Search States for Data Treatments
  const [treatmentSubTab, setTreatmentSubTab] = useState<'all' | 'active' | 'pending' | 'paused' | 'rejected'>('all');
  const [treatmentSearch, setTreatmentSearch] = useState('');
  const [complianceSearch, setComplianceSearch] = useState('');

  // Inline Expression Editing State
  const [editingRuleId, setEditingRuleId] = useState<string | null>(null);
  const [editedExpr, setEditedExpr] = useState('');

  // Filter Data Treatment Rules
  const pendingAiCount = dataTreatmentRules.filter((r) => r.is_ai_proposed && r.status === 'pending').length;
  const activeTreatmentsCount = dataTreatmentRules.filter((r) => r.status === 'active').length;
  const pausedTreatmentsCount = dataTreatmentRules.filter((r) => r.status === 'paused').length;
  const rejectedTreatmentsCount = dataTreatmentRules.filter((r) => r.status === 'rejected').length;

  const filteredTreatmentRules = dataTreatmentRules.filter((r: DataTreatmentRule) => {
    // Filter by Dataset if selected
    if (selectedDatasetId && selectedDatasetId !== 'all') {
      const canonicalSelected = selectedDatasetId.replace('.csv', '');
      const ruleDs = r.dataset_id.replace('.csv', '');
      if (ruleDs !== canonicalSelected && r.dataset_id !== selectedDatasetId) {
        // Allow dataset match
      }
    }

    // Filter by SubTab
    if (treatmentSubTab === 'active' && r.status !== 'active') return false;
    if (treatmentSubTab === 'pending' && (!r.is_ai_proposed || r.status !== 'pending')) return false;
    if (treatmentSubTab === 'paused' && r.status !== 'paused') return false;
    if (treatmentSubTab === 'rejected' && r.status !== 'rejected') return false;

    // Search query
    if (treatmentSearch) {
      const q = treatmentSearch.toLowerCase();
      return (
        r.treatment_name.toLowerCase().includes(q) ||
        r.column_name.toLowerCase().includes(q) ||
        r.expression_display.toLowerCase().includes(q) ||
        (r.ai_rationale && r.ai_rationale.toLowerCase().includes(q)) ||
        (r.description && r.description.toLowerCase().includes(q)) ||
        r.dataset_id.toLowerCase().includes(q)
      );
    }
    return true;
  });

  // Filter Fixed Compliance Check Rules
  const filteredComplianceRules = complianceCheckRules.filter((r: ComplianceCheckRule) => {
    if (complianceSearch) {
      const q = complianceSearch.toLowerCase();
      return (
        r.rule_name.toLowerCase().includes(q) ||
        r.rule_code.toLowerCase().includes(q) ||
        r.column_name.toLowerCase().includes(q) ||
        r.expression.toLowerCase().includes(q) ||
        r.law_ref.toLowerCase().includes(q) ||
        r.dataset_id.toLowerCase().includes(q)
      );
    }
    return true;
  });

  const handleStartEdit = (rule: DataTreatmentRule) => {
    setEditingRuleId(rule.rule_id);
    setEditedExpr(rule.expression_display);
  };

  const handleSaveEdit = async (ruleId: string) => {
    if (editedExpr.trim()) {
      await updateTreatmentRuleExpression(ruleId, editedExpr.trim());
    }
    setEditingRuleId(null);
  };

  return (
    <div className="page-enter mx-auto max-w-[1400px] space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <span className="text-[11px] font-bold uppercase tracking-wider text-slate-700">
            Data Governance & IPO Assurance · Rule Architecture
          </span>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">
            Quản Lý Rule Kiểm Soát & Xử Lý Dữ Liệu
          </h1>
          <p className="mt-1 text-xs text-slate-600">
            Tách biệt rõ ràng giữa <strong>Rule Kiểm Tra Tuân Thủ cố định</strong> và <strong>Rule Xử Lý Dữ Liệu linh hoạt</strong> (hỗ trợ AI đề xuất & chỉnh sửa biểu thức).
          </p>
        </div>

        {/* Connection status & Dataset filter */}
        <div className="flex flex-wrap items-center gap-2.5">
          {/* Backend Connection Indicator */}
          {isBackendLive ? (
            <div className="flex items-center gap-1.5 rounded-lg border border-emerald-200 bg-emerald-50 px-2.5 py-1.5 text-xs font-semibold text-emerald-800 shadow-2xs">
              <span className="size-2 rounded-full bg-emerald-500 animate-pulse" />
              <span>Live Backend (:8000)</span>
              <button
                onClick={() => syncWithBackend()}
                title="Làm mới dữ liệu từ Backend"
                className="ml-1 text-emerald-600 hover:text-emerald-900 transition-colors"
              >
                <RefreshCw className={`size-3 ${isSyncing ? 'animate-spin' : ''}`} />
              </button>
            </div>
          ) : (
            <div className="flex items-center gap-1.5 rounded-lg border border-amber-200 bg-amber-50 px-2.5 py-1.5 text-xs font-semibold text-amber-800 shadow-2xs">
              <span className="size-2 rounded-full bg-amber-500" />
              <span>Chế độ Demo (Fallback)</span>
              <button
                onClick={() => syncWithBackend()}
                title="Thử kết nối lại Backend FastAPI"
                className="ml-1 text-amber-600 hover:text-amber-900 transition-colors"
              >
                <RefreshCw className={`size-3 ${isSyncing ? 'animate-spin' : ''}`} />
              </button>
            </div>
          )}

          <div className="flex items-center gap-2">
            <span className="text-xs text-slate-500 font-medium">Lọc theo bộ dữ liệu:</span>
            <select
              value={selectedDatasetId}
              onChange={(e) => selectDataset(e.target.value)}
              className="h-9 rounded-lg border border-slate-200 bg-white px-3 font-mono text-xs font-semibold text-slate-800 focus:outline-none focus:ring-1 focus:ring-[#04D3D4]"
            >
              {Object.values(datasets).map((ds: DatasetItem) => (
                <option key={ds.id} value={ds.id}>
                  {ds.title}
                </option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {/* Main Tab Segmented Slider: Xử Lý Dữ Liệu vs Kiểm Tra Tuân Thủ */}
      <div className="relative flex rounded-2xl border border-slate-200 bg-slate-100 p-1.5 shadow-2xs">
        {/* Sliding active background indicator */}
        <div
          className={`absolute top-1.5 bottom-1.5 rounded-xl bg-white shadow-sm border border-slate-200/80 transition-all duration-300 ease-out ${
            rulesMainTab === 'treatments'
              ? 'left-1.5 w-[calc(50%-6px)]'
              : 'left-[calc(50%+3px)] w-[calc(50%-4.5px)]'
          }`}
        />

        {/* Tab 1: Rule Xử Lý Dữ Liệu */}
        <button
          onClick={() => setRulesMainTab('treatments')}
          className={`relative z-10 flex flex-1 items-center justify-center gap-2.5 py-3 text-xs font-bold transition-colors ${
            rulesMainTab === 'treatments' ? 'text-slate-950 font-extrabold' : 'text-slate-600 hover:text-slate-900'
          }`}
        >
          <Wand2 size={17} className={rulesMainTab === 'treatments' ? 'text-[#04D3D4]' : 'text-slate-400'} />
          <span>Rule Xử Lý Dữ Liệu (Data Treatments)</span>
          <span
            className={`rounded-full px-2.5 py-0.5 text-[10px] font-extrabold ${
              rulesMainTab === 'treatments'
                ? 'bg-[#04D3D4] text-slate-950 shadow-2xs'
                : 'bg-slate-200 text-slate-700'
            }`}
          >
            {dataTreatmentRules.length} Rule
          </span>
          {pendingAiCount > 0 && (
            <span className="rounded-full bg-[#FFC402] px-2 py-0.5 text-[10px] font-extrabold text-slate-950 shadow-2xs animate-bounce">
              {pendingAiCount} AI đề xuất
            </span>
          )}
        </button>

        {/* Tab 2: Rule Kiểm Tra Tuân Thủ (Cố Định) */}
        <button
          onClick={() => setRulesMainTab('compliance_checks')}
          className={`relative z-10 flex flex-1 items-center justify-center gap-2.5 py-3 text-xs font-bold transition-colors ${
            rulesMainTab === 'compliance_checks' ? 'text-slate-950 font-extrabold' : 'text-slate-600 hover:text-slate-900'
          }`}
        >
          <Lock size={17} className={rulesMainTab === 'compliance_checks' ? 'text-rose-600' : 'text-slate-400'} />
          <span>Rule Kiểm Tra Tuân Thủ (Cố Định Backend)</span>
          <span
            className={`rounded-full px-2.5 py-0.5 text-[10px] font-extrabold ${
              rulesMainTab === 'compliance_checks'
                ? 'bg-rose-100 text-rose-800 border border-rose-200 shadow-2xs'
                : 'bg-slate-200 text-slate-700'
            }`}
          >
            {complianceCheckRules.length} Cố định · Read-Only
          </span>
        </button>
      </div>

      {/* ========================================================================= */}
      {/* TAB 1: RULE XỬ LÝ DỮ LIỆU (DATA TREATMENTS) */}
      {/* ========================================================================= */}
      {rulesMainTab === 'treatments' && (
        <div className="space-y-6 animate-in fade-in-50 duration-300">
          {/* Explain Banner */}
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between rounded-xl border border-[#04D3D4]/30 bg-gradient-to-r from-[#04D3D4]/10 via-[#FFC402]/10 to-white p-4">
            <div className="flex items-center gap-3">
              <div className="grid size-9 place-items-center rounded-lg bg-[#04D3D4] text-slate-950 font-bold shadow-xs">
                <Wand2 size={20} />
              </div>
              <div>
                <div className="flex flex-wrap items-center gap-2">
                  <h3 className="text-xs font-bold text-slate-900">
                    Quy Tắc Xử Lý Dữ Liệu Chung (Data Transformations & Masking)
                  </h3>
                  <span className="rounded-full bg-slate-900 text-white px-2 py-0.5 text-[10px] font-semibold">
                    Admin có thể sửa biểu thức trên UI
                  </span>
                </div>
                <p className="mt-1 text-[11px] text-slate-600 leading-relaxed">
                  Bao gồm che mờ thông tin (masking), mã hóa băm (hashing), làm tròn tọa độ (rounding), chuẩn hóa ký tự (to_upper), cắt khoảng trắng...
                  Quy tắc do AI đề xuất được gắn huy hiệu riêng để Admin phê duyệt hoặc điều chỉnh biểu thức trực tiếp.
                </p>
              </div>
            </div>
          </div>

          {/* Sub-Tabs & Search */}
          <Card className="overflow-hidden rounded-2xl border-slate-200 bg-white shadow-xs">
            <div className="flex flex-col gap-3 border-b border-slate-200 p-4 sm:flex-row sm:items-center sm:justify-between">
              {/* Filter Tabs */}
              <div className="flex items-center gap-1.5 overflow-x-auto">
                <button
                  onClick={() => setTreatmentSubTab('all')}
                  className={`rounded-lg px-3 py-1.5 text-xs font-bold transition ${
                    treatmentSubTab === 'all'
                      ? 'bg-slate-900 text-white shadow-xs'
                      : 'text-slate-600 hover:bg-slate-100'
                  }`}
                >
                  Tất cả ({dataTreatmentRules.length})
                </button>
                <button
                  onClick={() => setTreatmentSubTab('active')}
                  className={`rounded-lg px-3 py-1.5 text-xs font-bold transition ${
                    treatmentSubTab === 'active'
                      ? 'bg-emerald-600 text-white shadow-xs'
                      : 'text-slate-600 hover:bg-slate-100'
                  }`}
                >
                  Đang áp dụng ({activeTreatmentsCount})
                </button>
                <button
                  onClick={() => setTreatmentSubTab('pending')}
                  className={`flex items-center gap-1 rounded-lg px-3 py-1.5 text-xs font-bold transition ${
                    treatmentSubTab === 'pending'
                      ? 'bg-[#FFC402] text-slate-950 shadow-xs'
                      : 'text-slate-600 hover:bg-slate-100'
                  }`}
                >
                  <Sparkles size={12} className="text-amber-600" />
                  <span>AI đề xuất chờ duyệt ({pendingAiCount})</span>
                </button>
                <button
                  onClick={() => setTreatmentSubTab('paused')}
                  className={`rounded-lg px-3 py-1.5 text-xs font-bold transition ${
                    treatmentSubTab === 'paused'
                      ? 'bg-slate-500 text-white shadow-xs'
                      : 'text-slate-600 hover:bg-slate-100'
                  }`}
                >
                  Tạm dừng ({pausedTreatmentsCount})
                </button>
                <button
                  onClick={() => setTreatmentSubTab('rejected')}
                  className={`rounded-lg px-3 py-1.5 text-xs font-bold transition ${
                    treatmentSubTab === 'rejected'
                      ? 'bg-rose-600 text-white shadow-xs'
                      : 'text-slate-600 hover:bg-slate-100'
                  }`}
                >
                  Từ chối ({rejectedTreatmentsCount})
                </button>
              </div>

              {/* Search */}
              <div className="relative max-w-xs flex-1">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={14} />
                <input
                  value={treatmentSearch}
                  onChange={(e) => setTreatmentSearch(e.target.value)}
                  placeholder="Tìm kiếm rule xử lý data..."
                  className="h-9 w-full rounded-lg border border-slate-200 bg-slate-50 pl-9 pr-3 text-xs outline-none focus:border-[#04D3D4] focus:bg-white transition"
                />
              </div>
            </div>

            {/* Treatment Rules Grid */}
            <div className="p-6 space-y-4">
              {filteredTreatmentRules.length === 0 ? (
                <div className="py-12 text-center text-slate-400">
                  <CheckCircle2 size={36} className="mx-auto mb-2 text-[#04D3D4] opacity-80" />
                  <p className="text-sm font-medium text-slate-600">Không có quy tắc xử lý nào phù hợp</p>
                  <p className="text-xs text-slate-400">Hãy chọn tab khác hoặc thay đổi từ khóa tìm kiếm.</p>
                </div>
              ) : (
                filteredTreatmentRules.map((rule: DataTreatmentRule) => {
                  const isAi = rule.is_ai_proposed;
                  const isPending = rule.status === 'pending';
                  const isActive = rule.status === 'active';
                  const isPaused = rule.status === 'paused';
                  const isRejected = rule.status === 'rejected';

                  return (
                    <div
                      key={rule.rule_id}
                      className={`rounded-xl border p-5 transition-all shadow-2xs ${
                        isAi && isPending
                          ? 'border-amber-300 bg-gradient-to-r from-amber-50/50 via-white to-white ring-1 ring-amber-200'
                          : isPaused
                          ? 'border-slate-200 bg-slate-50/80 opacity-75'
                          : isRejected
                          ? 'border-rose-200 bg-rose-50/30 opacity-75'
                          : 'border-slate-200 bg-white hover:border-[#04D3D4]/50'
                      }`}
                    >
                      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                        <div>
                          <div className="flex flex-wrap items-center gap-2">
                            {/* Rule Name & Code */}
                            <span className="font-mono text-xs font-bold text-slate-900">{rule.treatment_name}</span>
                            <span className="font-mono text-[10px] text-slate-400">({rule.rule_id})</span>

                            {/* Dataset & Column */}
                            <span className="rounded-md bg-slate-100 px-2 py-0.5 font-mono text-[10px] font-semibold text-slate-700">
                              {rule.dataset_id}
                            </span>
                            <span className="rounded-md bg-sky-50 text-sky-800 border border-sky-200 px-2 py-0.5 font-mono text-[10px] font-semibold">
                              Cột: {rule.column_name}
                            </span>
                            <span className="rounded-md bg-slate-100 px-2 py-0.5 text-[10px] text-slate-600">
                              Thao tác: {rule.operation_id}
                            </span>

                            {/* AI Proposed Note Badge */}
                            {isAi && (
                              <span className="inline-flex items-center gap-1 rounded-full bg-gradient-to-r from-amber-500 to-orange-500 px-2.5 py-0.5 text-[10px] font-bold text-white shadow-2xs">
                                <Sparkles size={11} />
                                <span>✨ AI Đề Xuất (Chờ Duyệt)</span>
                              </span>
                            )}

                            {/* Status badge */}
                            <span
                              className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-[10px] font-bold ${
                                isActive
                                  ? 'bg-emerald-100 text-emerald-800'
                                  : isPending
                                  ? 'bg-amber-100 text-amber-800'
                                  : isPaused
                                  ? 'bg-slate-200 text-slate-600'
                                  : 'bg-rose-100 text-rose-800'
                              }`}
                            >
                              <span
                                className={`size-1.5 rounded-full ${
                                  isActive
                                    ? 'bg-emerald-600 animate-pulse'
                                    : isPending
                                    ? 'bg-amber-600'
                                    : isPaused
                                    ? 'bg-slate-400'
                                    : 'bg-rose-600'
                                }`}
                              />
                              {isActive
                                ? 'Đang áp dụng (Active)'
                                : isPending
                                ? 'Chờ duyệt (Pending)'
                                : isPaused
                                ? 'Tạm dừng (Paused)'
                                : 'Đã từ chối (Rejected)'}
                            </span>
                          </div>

                          {/* Description or AI Rationale */}
                          {rule.description && (
                            <p className="mt-1.5 text-xs text-slate-600 leading-relaxed">
                              {rule.description}
                            </p>
                          )}
                          {isAi && rule.ai_rationale && (
                            <div className="mt-2 rounded-lg border border-amber-200 bg-amber-50/80 p-2.5 text-xs text-amber-900">
                              <div className="flex items-center gap-2 font-bold mb-1">
                                <Sparkles size={13} className="text-amber-600" />
                                <span>Lý do AI đề xuất (Độ tin cậy: {Math.round((rule.ai_confidence || 0.95) * 100)}%):</span>
                              </div>
                              <p className="text-[11px] leading-relaxed text-amber-800">{rule.ai_rationale}</p>
                            </div>
                          )}
                        </div>

                        {/* Action buttons (Admin only) */}
                        {currentRole === 'admin' ? (
                          <div className="flex items-center gap-2 shrink-0">
                            {/* If AI proposed pending -> Approve / Reject */}
                            {isPending && (
                              <>
                                <Button
                                  size="sm"
                                  onClick={() => approveTreatmentRule(rule.rule_id)}
                                  className="h-8 gap-1.5 px-3 text-xs font-bold bg-[#04D3D4] text-slate-950 hover:bg-[#03b8b9] shadow-xs"
                                >
                                  <Check size={14} />
                                  Duyệt rule
                                </Button>
                                <Button
                                  variant="outline"
                                  size="sm"
                                  onClick={() => rejectTreatmentRule(rule.rule_id)}
                                  className="h-8 text-xs text-slate-600 hover:text-red-600 hover:bg-red-50"
                                >
                                  <X size={14} />
                                  Từ chối
                                </Button>
                              </>
                            )}

                            {/* Active or Paused toggle */}
                            {(isActive || isPaused) && (
                              <Button
                                onClick={() => toggleTreatmentRuleStatus(rule.rule_id)}
                                variant="outline"
                                size="sm"
                                className="h-8 text-[11px] gap-1.5 border-slate-200 text-slate-700 hover:bg-slate-50"
                              >
                                {isPaused ? <Play size={13} className="text-emerald-600" /> : <Pause size={13} className="text-amber-600" />}
                                <span>{isPaused ? 'Kích hoạt lại' : 'Tạm dừng'}</span>
                              </Button>
                            )}

                            {/* Pencil Button for inline editing expression */}
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => handleStartEdit(rule)}
                              title="Chỉnh sửa biểu thức xử lý trên UI"
                              className="h-8 text-xs text-slate-700 hover:bg-slate-100 gap-1"
                            >
                              <Pencil size={13} />
                              <span className="hidden sm:inline">Sửa biểu thức</span>
                            </Button>
                          </div>
                        ) : (
                          <div className="text-xs text-slate-400 italic">
                            Chế độ xem (Auditor)
                          </div>
                        )}
                      </div>

                      {/* Expression code box (View or Inline Edit) */}
                      <div className="mt-3">
                        {editingRuleId === rule.rule_id ? (
                          <div className="flex flex-col gap-2 rounded-lg border border-[#04D3D4] bg-slate-50 p-2.5">
                            <span className="text-[11px] font-bold text-slate-700">
                              Chỉnh sửa biểu thức xử lý dữ liệu:
                            </span>
                            <div className="flex items-center gap-2">
                              <input
                                value={editedExpr}
                                onChange={(e) => setEditedExpr(e.target.value)}
                                className="h-8 flex-1 rounded-md border border-slate-300 bg-white px-2.5 font-mono text-xs font-semibold text-slate-900 focus:outline-none focus:border-[#04D3D4]"
                              />
                              <Button
                                size="sm"
                                onClick={() => handleSaveEdit(rule.rule_id)}
                                className="h-8 bg-[#04D3D4] text-slate-950 font-bold hover:bg-[#03b8b9]"
                              >
                                Lưu biểu thức
                              </Button>
                              <Button
                                size="sm"
                                variant="outline"
                                onClick={() => setEditingRuleId(null)}
                                className="h-8"
                              >
                                Hủy
                              </Button>
                            </div>
                          </div>
                        ) : (
                          <div className="flex items-center justify-between rounded-lg border border-slate-200 bg-slate-50/70 px-3 py-2">
                            <code className="font-mono text-xs font-semibold text-slate-900">
                              {rule.expression_display}
                            </code>
                            <span className="text-[10px] text-slate-400 font-mono">
                              Params: {JSON.stringify(rule.params_json)}
                            </span>
                          </div>
                        )}
                      </div>

                      {/* Card Footer */}
                      <div className="mt-3 flex flex-wrap items-center justify-between gap-2 border-t border-slate-100 pt-2 text-[11px] text-slate-400">
                        <div>
                          <span>Người thiết lập/duyệt: <strong className="text-slate-700">{rule.enforced_by}</strong></span>
                        </div>
                        <div>
                          <span>Cập nhật lần cuối: {new Date(rule.updated_at).toLocaleString('vi-VN')}</span>
                        </div>
                      </div>
                    </div>
                  );
                })
              )}
            </div>
          </Card>
        </div>
      )}

      {/* ========================================================================= */}
      {/* TAB 2: RULE KIỂM TRA TUÂN THỦ (FIXED COMPLIANCE CHECKS - READ-ONLY) */}
      {/* ========================================================================= */}
      {rulesMainTab === 'compliance_checks' && (
        <div className="space-y-6 animate-in fade-in-50 duration-300">
          {/* Locked Notice Banner */}
          <div className="flex flex-col gap-3 rounded-xl border border-rose-300 bg-gradient-to-r from-rose-50 via-rose-50/50 to-white p-4">
            <div className="flex items-start gap-3">
              <div className="grid size-9 shrink-0 place-items-center rounded-lg bg-rose-600 text-white font-bold shadow-xs">
                <Lock size={20} />
              </div>
              <div className="space-y-1">
                <div className="flex flex-wrap items-center gap-2">
                  <h3 className="text-xs font-bold text-rose-950 uppercase tracking-wide">
                    Hệ Thống Quy Tắc Kiểm Tra Tuân Thủ Bất Biến (Fixed Compliance Quality Gates)
                  </h3>
                  <span className="rounded-full bg-rose-200 text-rose-900 border border-rose-300 px-2.5 py-0.5 text-[10px] font-extrabold">
                    🔒 Cố Định (Backend Managed) · Không Thể Sửa Trên UI
                  </span>
                </div>
                <p className="text-xs text-rose-900/90 leading-relaxed">
                  Toàn bộ quy tắc kiểm tra tính hợp lệ & tuân thủ (chuẩn IPO / SOX 404 / IFRS 15 / ISO 26262 / Nghị định 13) được định nghĩa cố định trong cơ sở dữ liệu và mã nguồn Backend.
                  <strong> AI không có quyền đề xuất hay tự động sinh quy tắc này.</strong> Giao diện người dùng ở chế độ <strong>Read-Only hoàn toàn</strong> (không có nút Sửa/Tạm dừng/Xóa) nhằm bảo đảm tính toàn vẹn và bằng chứng kiểm toán bất biến.
                </p>
              </div>
            </div>
          </div>

          {/* Compliance Rules Card */}
          <Card className="overflow-hidden rounded-2xl border-slate-200 bg-white shadow-xs">
            <div className="flex flex-col gap-3 border-b border-slate-200 p-4 sm:flex-row sm:items-center sm:justify-between">
              <div className="flex items-center gap-2">
                <ShieldCheck size={18} className="text-rose-600" />
                <span className="text-xs font-bold text-slate-900">
                  Danh mục kiểm tra chất lượng & tuân thủ đang cưỡng chế trên luồng ({filteredComplianceRules.length} Rule)
                </span>
              </div>

              {/* Search */}
              <div className="relative max-w-xs flex-1">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={14} />
                <input
                  value={complianceSearch}
                  onChange={(e) => setComplianceSearch(e.target.value)}
                  placeholder="Tìm mã rule, chuẩn kiểm toán, biểu thức..."
                  className="h-9 w-full rounded-lg border border-slate-200 bg-slate-50 pl-9 pr-3 text-xs outline-none focus:border-rose-400 focus:bg-white transition"
                />
              </div>
            </div>

            {/* List */}
            <div className="divide-y divide-slate-100 p-6 space-y-4">
              {filteredComplianceRules.length === 0 ? (
                <div className="py-12 text-center text-slate-400">
                  <CheckCircle2 size={36} className="mx-auto mb-2 text-rose-400 opacity-80" />
                  <p className="text-sm font-medium text-slate-600">Không tìm thấy quy tắc kiểm tra phù hợp</p>
                </div>
              ) : (
                filteredComplianceRules.map((rule: ComplianceCheckRule) => (
                  <div
                    key={rule.rule_id}
                    className="rounded-xl border border-slate-200 bg-white p-5 shadow-2xs transition hover:border-rose-300"
                  >
                    <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                      <div>
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="font-mono text-xs font-bold text-slate-900">{rule.rule_name}</span>
                          <span className="font-mono text-xs font-extrabold text-rose-600">[{rule.rule_code}]</span>
                          <Badge
                            tone={rule.severity === 'CRITICAL' ? 'red' : 'amber'}
                          >
                            {rule.severity}
                          </Badge>
                          <span className="rounded-md bg-slate-100 px-2 py-0.5 font-mono text-[10px] font-semibold text-slate-700">
                            {rule.dataset_id}
                          </span>
                          <span className="rounded-md bg-slate-100 px-2 py-0.5 font-mono text-[10px] text-slate-700">
                            Cột: {rule.column_name}
                          </span>
                          <span className="rounded-md bg-rose-50 border border-rose-200 text-rose-700 px-2 py-0.5 text-[10px] font-bold">
                            Khi lỗi: {rule.on_fail_action}
                          </span>
                        </div>

                        <p className="mt-2 text-xs text-slate-600 leading-relaxed">
                          {rule.description}
                        </p>
                      </div>

                      {/* Fixed status badge - Read only */}
                      <div className="shrink-0 flex items-center gap-1.5 rounded-lg border border-slate-200 bg-slate-50 px-3 py-1 text-xs font-semibold text-slate-600">
                        <Lock size={12} className="text-slate-500" />
                        <span>Cố định (Read-Only)</span>
                      </div>
                    </div>

                    {/* Expression code box */}
                    <div className="mt-3">
                      <div className="flex items-center justify-between rounded-lg border border-rose-200 bg-rose-50/30 px-3 py-2">
                        <code className="font-mono text-xs font-bold text-rose-950">
                          {rule.expression}
                        </code>
                        <span className="text-[10px] font-semibold text-rose-700 uppercase">
                          Logic kiểm tra hợp lệ
                        </span>
                      </div>
                    </div>

                    {/* Footer */}
                    <div className="mt-3.5 flex flex-wrap items-center justify-between gap-2 border-t border-slate-100 pt-2.5 text-[11px] text-slate-500">
                      <div className="flex items-center gap-2">
                        <span>Căn cứ pháp lý & Chuẩn kiểm toán:</span>
                        <strong className="text-slate-800 font-bold">{rule.law_ref}</strong>
                      </div>
                      <div className="text-slate-400 text-[10px] italic">
                        Chỉ có thể cập nhật qua migration backend
                      </div>
                    </div>
                  </div>
                ))
              )}
            </div>
          </Card>
        </div>
      )}
    </div>
  );
}
