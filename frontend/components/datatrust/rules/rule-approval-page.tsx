'use client';
import { useState } from 'react';
import { Link } from 'react-router-dom';
import {
  Check,
  CheckCircle2,
  Clock,
  ExternalLink,
  Pause,
  Pencil,
  Play,
  Search,
  ShieldCheck,
  Sparkles,
  X,
} from 'lucide-react';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  useAgentStore,
  type ProposedRule,
  type DatasetItem,
  type ActiveRule,
} from '@/lib/agent-store';

export function RuleApprovalPage() {
  const {
    currentRole,
    datasets,
    selectedDatasetId,
    selectDataset,
    approveRule,
    rejectRule,
    updateRuleExpression,
    activeRules,
    rulesSegmentTab,
    setRulesSegmentTab,
    toggleActiveRuleStatus,
  } = useAgentStore();

  const [proposedSubTab, setProposedSubTab] = useState<'all' | 'pending' | 'approved' | 'rejected'>('pending');
  const [searchQuery, setSearchQuery] = useState('');
  const [editingRuleId, setEditingRuleId] = useState<string | null>(null);
  const [editedExpr, setEditedExpr] = useState('');

  // Collect all proposed rules across datasets
  const allProposedRules: (ProposedRule & { datasetName: string })[] = [];
  Object.values(datasets).forEach((ds: DatasetItem) => {
    ds.proposedRules.forEach((r: ProposedRule) => {
      allProposedRules.push({ ...r, datasetName: ds.title });
    });
  });

  const pendingCount = allProposedRules.filter((r) => r.status === 'pending').length;
  const approvedCount = allProposedRules.filter((r) => r.status === 'approved').length;
  const rejectedCount = allProposedRules.filter((r) => r.status === 'rejected').length;

  const filteredProposedRules = allProposedRules.filter((r) => {
    if (proposedSubTab === 'pending' && r.status !== 'pending') return false;
    if (proposedSubTab === 'approved' && r.status !== 'approved') return false;
    if (proposedSubTab === 'rejected' && r.status !== 'rejected') return false;
    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      return (
        r.name.toLowerCase().includes(q) ||
        r.expression.toLowerCase().includes(q) ||
        r.rationale.toLowerCase().includes(q)
      );
    }
    return true;
  });

  const filteredActiveRules = activeRules.filter((r: ActiveRule) => {
    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      return (
        r.name.toLowerCase().includes(q) ||
        r.expression.toLowerCase().includes(q) ||
        r.lawRef.toLowerCase().includes(q)
      );
    }
    return true;
  });

  const totalScannedCount = activeRules.reduce((sum, r) => sum + r.scannedCount, 0);
  const totalQuarantinedCount = activeRules.reduce((sum, r) => sum + r.quarantinedCount, 0);

  const handleStartEdit = (rule: ProposedRule) => {
    setEditingRuleId(rule.id);
    setEditedExpr(rule.expression);
  };

  const handleSaveEdit = (ruleId: string) => {
    if (editedExpr.trim()) {
      updateRuleExpression(ruleId, editedExpr.trim());
    }
    setEditingRuleId(null);
  };

  return (
    <div className="page-enter mx-auto max-w-[1400px] space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <span className="text-[11px] font-bold uppercase tracking-wider text-slate-700">
            Data Governance & IPO Assurance · Human-In-The-Loop
          </span>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">
            Quản Lý Rule Kiểm Soát Dữ Liệu
          </h1>
        </div>

        {/* Quick dataset filter & Role badge */}
        <div className="flex flex-wrap items-center gap-2.5">

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

      {/* Segmented Slider Toggle for Admin / Clean Header for Auditor */}
      {currentRole === 'admin' ? (
        <div className="relative flex rounded-2xl border border-slate-200 bg-slate-100 p-1.5 shadow-2xs">
          {/* Sliding active background indicator */}
          <div
            className={`absolute top-1.5 bottom-1.5 rounded-xl bg-white shadow-sm border border-slate-200/80 transition-all duration-300 ease-out ${
              rulesSegmentTab === 'active'
                ? 'left-1.5 w-[calc(50%-6px)]'
                : 'left-[calc(50%+3px)] w-[calc(50%-4.5px)]'
            }`}
          />

          {/* Segment 1: Rules đang áp dụng */}
          <button
            onClick={() => setRulesSegmentTab('active')}
            className={`relative z-10 flex flex-1 items-center justify-center gap-2.5 py-3 text-xs font-bold transition-colors ${
              rulesSegmentTab === 'active' ? 'text-slate-950 font-extrabold' : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            <ShieldCheck size={17} className={rulesSegmentTab === 'active' ? 'text-[#04D3D4]' : 'text-slate-400'} />
            <span>Rule đang áp dụng cho luồng</span>
            <span
              className={`rounded-full px-2.5 py-0.5 text-[10px] font-extrabold ${
                rulesSegmentTab === 'active'
                  ? 'bg-[#04D3D4] text-slate-950 shadow-2xs'
                  : 'bg-slate-200 text-slate-700'
              }`}
            >
              {activeRules.length} Active
            </span>
          </button>

          {/* Segment 2: Đề xuất mới của AI */}
          <button
            onClick={() => setRulesSegmentTab('proposed')}
            className={`relative z-10 flex flex-1 items-center justify-center gap-2.5 py-3 text-xs font-bold transition-colors ${
              rulesSegmentTab === 'proposed' ? 'text-slate-950 font-extrabold' : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            <Sparkles size={17} className={rulesSegmentTab === 'proposed' ? 'text-[#04D3D4]' : 'text-slate-400'} />
            <span>Các đề xuất của AI</span>
            {pendingCount > 0 ? (
              <span className="rounded-full bg-[#FFC402] px-2.5 py-0.5 text-[10px] font-extrabold text-slate-950 shadow-2xs">
                {pendingCount} chờ duyệt
              </span>
            ) : (
              <span className="rounded-full bg-slate-200 px-2 py-0.5 text-[10px] font-bold text-slate-600">
                0
              </span>
            )}
          </button>
        </div>
      ) : (
        <div className="flex items-center justify-between rounded-xl border border-slate-200 bg-white px-4 py-3 shadow-2xs">
          <div className="flex items-center gap-2.5">
            <ShieldCheck size={18} className="text-[#04D3D4]" />
            <span className="text-xs font-bold text-slate-900">
              Danh sách Rule đang thực thi kiểm soát trên luồng (Active in Production)
            </span>
          </div>
          <span className="rounded-full bg-[#04D3D4]/15 border border-[#04D3D4]/30 px-2.5 py-0.5 text-[10px] font-bold text-slate-950">
            {activeRules.length} Active
          </span>
        </div>
      )}

      {/* VIEW 1: ACTIVE PRODUCTION RULES */}
      {(rulesSegmentTab === 'active' || currentRole === 'auditor') && (
        <div className="space-y-4 animate-in fade-in-50 duration-300">
          {/* Active Status Bar */}
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between rounded-xl border border-[#04D3D4]/30 bg-gradient-to-r from-[#04D3D4]/10 via-[#FFC402]/10 to-white p-4">
            <div className="flex items-center gap-3">
              <div className="grid size-9 place-items-center rounded-lg bg-[#04D3D4] text-slate-950 font-bold shadow-xs">
                <ShieldCheck size={20} />
              </div>
              <div>
                <div className="flex flex-wrap items-center gap-2">
                  <h3 className="text-xs font-bold text-slate-900">
                    Bảo Vệ Luồng Dữ Liệu Thực Tế
                  </h3>
                </div>
                <p className="mt-1 text-[11px] text-slate-600">
                  Tất cả các giao dịch và telemetry đi qua pipeline đều được đối chiếu liên tục theo các chính sách đã phê duyệt.
                </p>
              </div>
            </div>

            <div className="relative max-w-xs flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={14} />
              <input
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Tìm rule đang áp dụng..."
                className="h-8 w-full rounded-lg border border-slate-200 bg-white pl-8 pr-3 text-xs outline-none focus:border-[#04D3D4]"
              />
            </div>
          </div>

          {/* Active Rules Grid */}
          <div className="grid gap-3.5">
            {filteredActiveRules.map((rule: ActiveRule) => {
              const isPaused = rule.status === 'paused';
              return (
                <div
                  key={rule.id}
                  className={`rounded-xl border p-4.5 transition-all shadow-2xs ${
                    isPaused
                      ? 'border-slate-200 bg-slate-50/80 opacity-75'
                      : 'border-slate-200 bg-white hover:border-[#04D3D4]/50'
                  }`}
                >
                  <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                    <div>
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="font-mono text-xs font-bold text-slate-900">{rule.name}</span>
                        <Badge
                          tone={rule.severity === 'CRITICAL' ? 'red' : rule.severity === 'HIGH' ? 'amber' : 'blue'}
                        >
                          {rule.severity}
                        </Badge>
                        <span className="rounded-md bg-slate-100 px-2 py-0.5 font-mono text-[10px] font-semibold text-slate-700">
                          {rule.datasetName}
                        </span>
                        <span className="rounded-md bg-[#04D3D4]/10 px-2 py-0.5 text-[10px] font-semibold text-slate-800 border border-[#04D3D4]/30">
                          {rule.targetLane}
                        </span>
                      </div>

                      <div className="mt-2 text-xs text-slate-600">
                        <span>Căn cứ kiểm toán: </span>
                        <strong className="text-slate-800">{rule.lawRef}</strong>
                        <span className="text-slate-400"> · Phê duyệt bởi: </span>
                        <span className="font-semibold text-slate-700">{rule.enforcedBy}</span>
                      </div>
                    </div>

                    <div className="flex items-center gap-2">
                      <span
                        className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-[10px] font-bold ${
                          isPaused
                            ? 'bg-slate-200 text-slate-600'
                            : 'bg-emerald-100 text-emerald-800'
                        }`}
                      >
                        <span
                          className={`size-1.5 rounded-full ${
                            isPaused ? 'bg-slate-400' : 'bg-emerald-600 animate-pulse'
                          }`}
                        />
                        {isPaused ? 'Tạm dừng (Paused)' : 'Đang thực thi (Active)'}
                      </span>

                      {currentRole === 'admin' && (
                        <Button
                          onClick={() => toggleActiveRuleStatus(rule.id)}
                          variant="outline"
                          size="sm"
                          className="h-7 text-[11px] gap-1 border-slate-200 text-slate-600 hover:bg-slate-50"
                        >
                          {isPaused ? <Play size={11} /> : <Pause size={11} />}
                          <span>{isPaused ? 'Bật lại' : 'Tạm dừng'}</span>
                        </Button>
                      )}
                    </div>
                  </div>

                  {/* Expression code box */}
                  <div className="mt-3">
                    <code className="block rounded-lg border border-slate-200 bg-slate-50/70 px-3 py-2 font-mono text-xs font-semibold text-slate-900">
                      {rule.expression}
                    </code>
                  </div>

                  {/* Production Stats Footer */}
                  <div className="mt-3.5 grid grid-cols-2 gap-3 sm:grid-cols-4 border-t border-[#f0f4f2] pt-2.5 text-[11px]">
                    <div>
                      <span className="text-slate-400">Engine thực thi:</span>
                      <div className="font-semibold text-slate-700">{rule.engine}</div>
                    </div>
                    <div>
                      <span className="text-slate-400">Đã quét qua rule:</span>
                      <div className="font-semibold text-slate-700">
                        {rule.scannedCount.toLocaleString()} dòng
                      </div>
                    </div>
                    <div>
                      <span className="text-slate-400">Đã cách ly vi phạm:</span>
                      <div className="font-bold text-rose-600">
                        {rule.quarantinedCount.toLocaleString()} dòng
                      </div>
                    </div>
                    <div>
                      <span className="text-slate-400">Thời điểm kích hoạt:</span>
                      <div className="text-slate-600">
                        {new Date(rule.enforcedAt).toLocaleDateString('vi-VN')}
                      </div>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* VIEW 2: AI PROPOSED RULES (AWAITING HITL REVIEW - ADMIN ONLY) */}
      {rulesSegmentTab === 'proposed' && currentRole === 'admin' && (
        <div className="space-y-6 animate-in fade-in-50 duration-300">
          {/* Summary KPI Cards */}
          <div className="grid gap-4 sm:grid-cols-3">
            <Card
              onClick={() => setProposedSubTab('pending')}
              className={`cursor-pointer rounded-xl border p-4 transition ${
                proposedSubTab === 'pending'
                  ? 'border-[#FFC402] bg-[#FFC402]/10 shadow-xs'
                  : 'border-slate-200 bg-white hover:border-slate-300'
              }`}
            >
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-slate-500">Chờ phê duyệt</span>
                <span className="grid size-7 place-items-center rounded-lg bg-[#FFC402]/20 text-slate-950 font-bold">
                  <Clock size={15} />
                </span>
              </div>
              <p className="mt-2 text-2xl font-bold text-slate-900">{pendingCount}</p>
              <span className="mt-1 block text-[11px] text-amber-800 font-semibold">Cần thẩm định HITL</span>
            </Card>

            <Card
              onClick={() => setProposedSubTab('approved')}
              className={`cursor-pointer rounded-xl border p-4 transition ${
                proposedSubTab === 'approved'
                  ? 'border-[#04D3D4] bg-[#04D3D4]/10 shadow-xs'
                  : 'border-slate-200 bg-white hover:border-slate-300'
              }`}
            >
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-slate-500">Đã phê duyệt</span>
                <span className="grid size-7 place-items-center rounded-lg bg-[#04D3D4]/20 text-slate-950">
                  <CheckCircle2 size={15} />
                </span>
              </div>
              <p className="mt-2 text-2xl font-bold text-slate-900">{approvedCount}</p>
              <span className="mt-1 block text-[11px] text-slate-700 font-semibold">Đã chuyển sang Active</span>
            </Card>

            <Card
              onClick={() => setProposedSubTab('rejected')}
              className={`cursor-pointer rounded-xl border p-4 transition ${
                proposedSubTab === 'rejected'
                  ? 'border-slate-400 bg-slate-100 shadow-xs'
                  : 'border-slate-200 bg-white hover:border-slate-300'
              }`}
            >
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-slate-500">Đã từ chối</span>
                <span className="grid size-7 place-items-center rounded-lg bg-red-50 text-red-600">
                  <X size={15} />
                </span>
              </div>
              <p className="mt-2 text-2xl font-bold text-slate-900">{rejectedCount}</p>
              <span className="mt-1 block text-[11px] text-slate-400">Không đưa vào production</span>
            </Card>
          </div>

          {/* Sub Filter & Search Bar */}
          <Card className="overflow-hidden rounded-2xl border-slate-200 bg-white shadow-xs">
            <div className="flex flex-col gap-3 border-b border-slate-200 p-4 sm:flex-row sm:items-center sm:justify-between">
              {/* Tabs */}
              <div className="flex items-center gap-1.5 overflow-x-auto">
                <button
                  onClick={() => setProposedSubTab('pending')}
                  className={`rounded-lg px-3 py-1.5 text-xs font-bold transition ${
                    proposedSubTab === 'pending'
                      ? 'bg-[#04D3D4] text-slate-950 shadow-xs'
                      : 'text-slate-600 hover:bg-slate-100'
                  }`}
                >
                  Chờ duyệt ({pendingCount})
                </button>
                <button
                  onClick={() => setProposedSubTab('approved')}
                  className={`rounded-lg px-3 py-1.5 text-xs font-bold transition ${
                    proposedSubTab === 'approved'
                      ? 'bg-[#04D3D4] text-slate-950 shadow-xs'
                      : 'text-slate-600 hover:bg-slate-100'
                  }`}
                >
                  Đã duyệt ({approvedCount})
                </button>
                <button
                  onClick={() => setProposedSubTab('rejected')}
                  className={`rounded-lg px-3 py-1.5 text-xs font-bold transition ${
                    proposedSubTab === 'rejected'
                      ? 'bg-[#04D3D4] text-slate-950 shadow-xs'
                      : 'text-slate-600 hover:bg-slate-100'
                  }`}
                >
                  Từ chối ({rejectedCount})
                </button>
                <button
                  onClick={() => setProposedSubTab('all')}
                  className={`rounded-lg px-3 py-1.5 text-xs font-bold transition ${
                    proposedSubTab === 'all'
                      ? 'bg-[#04D3D4] text-slate-950 shadow-xs'
                      : 'text-slate-600 hover:bg-slate-100'
                  }`}
                >
                  Tất cả ({allProposedRules.length})
                </button>
              </div>

              {/* Search */}
              <div className="relative max-w-xs flex-1">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={14} />
                <input
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Tìm kiếm rule đề xuất..."
                  className="h-9 w-full rounded-lg border border-slate-200 bg-slate-50 pl-9 pr-3 text-xs outline-none focus:border-[#04D3D4] focus:bg-white transition"
                />
              </div>
            </div>

            {/* Rules List */}
            <div className="divide-y divide-[#f0f4f2] p-6 space-y-6">
              {filteredProposedRules.length === 0 ? (
                <div className="py-12 text-center text-slate-400">
                  <CheckCircle2 size={36} className="mx-auto mb-2 text-[#04D3D4] opacity-80" />
                  <p className="text-sm font-medium text-slate-600">Không có rule đề xuất nào trong mục này</p>
                  <p className="text-xs text-slate-400">Hãy chọn tab khác hoặc thay đổi bộ lọc.</p>
                </div>
              ) : (
                filteredProposedRules.map((rule: ProposedRule & { datasetName: string }) => {
                  const isPending = rule.status === 'pending';
                  const isApproved = rule.status === 'approved';

                  return (
                    <div
                      key={rule.id}
                      className="rounded-xl border border-slate-200 bg-white p-5 shadow-2xs transition hover:border-[#04D3D4]/40"
                    >
                      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                        <div>
                          <div className="flex flex-wrap items-center gap-2">
                            <span className="font-mono text-xs font-bold text-slate-900">{rule.name}</span>
                            <Badge
                              tone={rule.severity === 'CRITICAL' ? 'red' : rule.severity === 'HIGH' ? 'amber' : 'blue'}
                            >
                              {rule.severity}
                            </Badge>
                            <span className="rounded-md bg-slate-100 px-2 py-0.5 font-mono text-[10px] font-semibold text-slate-700">
                              {rule.datasetName}
                            </span>
                            <span className="text-[11px] text-slate-400">· {rule.domain}</span>
                          </div>

                          <p className="mt-2 text-xs text-slate-600 leading-relaxed">
                            <strong className="text-slate-800">Căn cứ AI:</strong> {rule.rationale}
                          </p>
                        </div>

                        {/* Action buttons */}
                        <div className="flex items-center gap-2 shrink-0">
                          {isPending ? (
                            <>
                              <Button
                                size="sm"
                                onClick={() => approveRule(rule.id)}
                                className="h-8 gap-1.5 px-3 text-xs font-bold bg-[#04D3D4] text-slate-950 hover:bg-[#03b8b9] shadow-xs"
                              >
                                <Check size={14} />
                                Phê duyệt rule
                              </Button>
                              <Button
                                variant="outline"
                                size="sm"
                                onClick={() => rejectRule(rule.id)}
                                className="h-8 text-xs text-slate-600 hover:text-red-600 hover:bg-red-50"
                              >
                                Từ chối
                              </Button>
                              <Button
                                variant="outline"
                                size="sm"
                                onClick={() => handleStartEdit(rule)}
                                className="h-8 text-xs text-slate-600 hover:bg-slate-100"
                              >
                                <Pencil size={13} />
                              </Button>
                            </>
                          ) : isApproved ? (
                            <div className="text-right">
                              <span className="inline-flex items-center gap-1.5 rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-1 text-xs font-semibold text-emerald-700">
                                <Check size={14} /> Đã duyệt vào Active
                              </span>
                              <span className="block mt-1 text-[10px] text-slate-400">
                                {rule.approvedAt ? new Date(rule.approvedAt).toLocaleDateString('vi-VN') : 'Hôm nay'}
                              </span>
                            </div>
                          ) : (
                            <span className="inline-flex items-center gap-1.5 rounded-lg border border-red-200 bg-red-50 px-3 py-1 text-xs font-semibold text-red-600">
                              Đã từ chối
                            </span>
                          )}
                        </div>
                      </div>

                      {/* Expression code */}
                      <div className="mt-3">
                        {editingRuleId === rule.id ? (
                          <div className="flex items-center gap-2">
                            <input
                              value={editedExpr}
                              onChange={(e) => setEditedExpr(e.target.value)}
                              className="h-8 flex-1 rounded-md border border-[#04D3D4] bg-white px-2.5 font-mono text-xs text-slate-800"
                            />
                            <Button size="sm" onClick={() => handleSaveEdit(rule.id)} className="h-8 bg-[#04D3D4] text-slate-950 font-bold hover:bg-[#03b8b9]">
                              Lưu
                            </Button>
                            <Button size="sm" variant="outline" onClick={() => setEditingRuleId(null)} className="h-8">
                              Hủy
                            </Button>
                          </div>
                        ) : (
                          <code className="block rounded-lg border border-slate-200 bg-slate-50/70 px-3 py-2 font-mono text-xs font-semibold text-slate-900">
                            {rule.expression}
                          </code>
                        )}
                      </div>

                      {/* Sandbox Impact Preview */}
                      <div className="mt-4 rounded-lg border border-slate-200 bg-white p-3.5">
                        <span className="block text-[11px] font-bold uppercase tracking-wider text-slate-400 mb-2">
                          Mô phỏng tác động (Sandbox Preview)
                        </span>
                        <div className="grid grid-cols-2 gap-4 sm:grid-cols-4 text-xs">
                          <div>
                            <span className="text-slate-400 block text-[11px]">Độ tin cậy AI</span>
                            <strong className="text-sm font-bold text-slate-800">{rule.confidence}%</strong>
                          </div>
                          <div>
                            <span className="text-slate-400 block text-[11px]">Dòng hợp lệ (Silver)</span>
                            <strong className="text-sm font-bold text-emerald-600">
                              {rule.passRows.toLocaleString('vi-VN')} dòng
                            </strong>
                          </div>
                          <div>
                            <span className="text-slate-400 block text-[11px]">Cách ly (Quarantine)</span>
                            <strong className="text-sm font-bold text-red-600">
                              {rule.quarantineRows.toLocaleString('vi-VN')} dòng
                            </strong>
                          </div>
                          <div>
                            <span className="text-slate-400 block text-[11px]">Mục tiêu biên dịch</span>
                            <span className="block truncate text-slate-700 font-mono text-[11px]">
                              {rule.compiledTarget}
                            </span>
                          </div>
                        </div>
                      </div>

                      {/* Card Footer */}
                      <div className="mt-3.5 flex flex-wrap items-center justify-between gap-2 border-t border-slate-100 pt-2.5 text-[11px] text-slate-400">
                        <div className="flex items-center gap-3">
                          <span>Căn cứ pháp lý: <strong className="text-slate-600">{rule.lawRef}</strong></span>
                        </div>
                        <Link
                          to={`/results?tab=evidence&ref=${rule.evidenceId}`}
                          className="inline-flex items-center gap-1 font-medium text-slate-700 hover:text-[#04D3D4] hover:underline"
                        >
                          Bằng chứng kiểm toán: {rule.evidenceId}
                          <ExternalLink size={11} />
                        </Link>
                      </div>
                    </div>
                  );
                })
              )}
            </div>
          </Card>
        </div>
      )}
    </div>
  );
}
