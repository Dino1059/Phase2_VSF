'use client';
import { useState } from 'react';
import { Link } from 'react-router-dom';
import {
  Check,
  CheckCircle2,
  Clock,
  ExternalLink,
  Pencil,
  Search,
  X,
} from 'lucide-react';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { useAgentStore, type ProposedRule, type DatasetItem } from '@/lib/agent-store';

export function RuleApprovalPage() {
  const {
    datasets,
    selectedDatasetId,
    selectDataset,
    approveRule,
    rejectRule,
    updateRuleExpression,
  } = useAgentStore();

  const [activeTab, setActiveTab] = useState<'all' | 'pending' | 'approved' | 'rejected'>('pending');
  const [searchQuery, setSearchQuery] = useState('');
  const [editingRuleId, setEditingRuleId] = useState<string | null>(null);
  const [editedExpr, setEditedExpr] = useState('');

  // Collect all rules across datasets
  const allRules: (ProposedRule & { datasetName: string })[] = [];
  Object.values(datasets).forEach((ds: DatasetItem) => {
    ds.proposedRules.forEach((r: ProposedRule) => {
      allRules.push({ ...r, datasetName: ds.title });
    });
  });


  const pendingCount = allRules.filter((r) => r.status === 'pending').length;
  const approvedCount = allRules.filter((r) => r.status === 'approved').length;
  const rejectedCount = allRules.filter((r) => r.status === 'rejected').length;

  const filteredRules = allRules.filter((r) => {
    if (activeTab === 'pending' && r.status !== 'pending') return false;
    if (activeTab === 'approved' && r.status !== 'approved') return false;
    if (activeTab === 'rejected' && r.status !== 'rejected') return false;
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
    <div className="page-enter mx-auto max-w-[1360px] space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <span className="text-[11px] font-bold uppercase tracking-wider text-[#008b74]">
            Human-In-The-Loop (HITL)
          </span>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">
            Duyệt Rule Kiểm Soát Dữ Liệu
          </h1>
          <p className="mt-1 text-sm text-slate-500">
            Thẩm định căn cứ và tác động của các luật do AI Agent đề xuất trước khi đưa vào sản xuất.
          </p>
        </div>

        {/* Quick dataset filter */}
        <div className="flex items-center gap-2">
          <span className="text-xs text-slate-500 font-medium">Lọc theo bộ dữ liệu:</span>
          <select
            value={selectedDatasetId}
            onChange={(e) => selectDataset(e.target.value)}
            className="h-9 rounded-lg border border-[#e2ece8] bg-white px-3 text-xs font-semibold text-slate-700 focus:outline-none focus:ring-1 focus:ring-[#008b74]"
          >
            {Object.values(datasets).map((ds: DatasetItem) => (
              <option key={ds.id} value={ds.id}>
                {ds.title}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Summary KPI Cards */}
      <div className="grid gap-4 sm:grid-cols-3">
        <Card
          onClick={() => setActiveTab('pending')}
          className={`cursor-pointer rounded-xl border p-4 transition ${
            activeTab === 'pending'
              ? 'border-[#008b74] bg-[#f0f9f6] shadow-xs'
              : 'border-[#e2ece8] bg-white hover:border-slate-300'
          }`}
        >
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-500">Chờ phê duyệt</span>
            <span className="grid size-7 place-items-center rounded-lg bg-amber-50 text-amber-600">
              <Clock size={15} />
            </span>
          </div>
          <p className="mt-2 text-2xl font-bold text-slate-900">{pendingCount}</p>
          <span className="mt-1 block text-[11px] text-amber-600 font-medium">Cần thẩm định HITL</span>
        </Card>

        <Card
          onClick={() => setActiveTab('approved')}
          className={`cursor-pointer rounded-xl border p-4 transition ${
            activeTab === 'approved'
              ? 'border-[#008b74] bg-[#f0f9f6] shadow-xs'
              : 'border-[#e2ece8] bg-white hover:border-slate-300'
          }`}
        >
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-500">Đã phê duyệt</span>
            <span className="grid size-7 place-items-center rounded-lg bg-[#e6f6f2] text-[#007460]">
              <CheckCircle2 size={15} />
            </span>
          </div>
          <p className="mt-2 text-2xl font-bold text-slate-900">{approvedCount}</p>
          <span className="mt-1 block text-[11px] text-[#007460] font-medium">Đang áp dụng thực thi</span>
        </Card>

        <Card
          onClick={() => setActiveTab('rejected')}
          className={`cursor-pointer rounded-xl border p-4 transition ${
            activeTab === 'rejected'
              ? 'border-[#008b74] bg-[#f0f9f6] shadow-xs'
              : 'border-[#e2ece8] bg-white hover:border-slate-300'
          }`}
        >
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-500">Đã từ chối</span>
            <span className="grid size-7 place-items-center rounded-lg bg-red-50 text-red-600">
              <X size={15} />
            </span>
          </div>
          <p className="mt-2 text-2xl font-bold text-slate-900">{rejectedCount}</p>
          <span className="mt-1 block text-[11px] text-slate-400">Không đưa vào catalog</span>
        </Card>
      </div>

      {/* Main Filter & List */}
      <Card className="overflow-hidden rounded-2xl border-[#e2ece8] bg-white shadow-xs">
        {/* Filter bar */}
        <div className="flex flex-col gap-3 border-b border-[#e2ece8] p-4 sm:flex-row sm:items-center sm:justify-between">
          {/* Tabs */}
          <div className="flex items-center gap-1.5 overflow-x-auto">
            <button
              onClick={() => setActiveTab('pending')}
              className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition ${
                activeTab === 'pending'
                  ? 'bg-[#0f3834] text-white shadow-xs'
                  : 'text-slate-600 hover:bg-slate-100'
              }`}
            >
              Chờ duyệt ({pendingCount})
            </button>
            <button
              onClick={() => setActiveTab('approved')}
              className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition ${
                activeTab === 'approved'
                  ? 'bg-[#0f3834] text-white shadow-xs'
                  : 'text-slate-600 hover:bg-slate-100'
              }`}
            >
              Đã duyệt ({approvedCount})
            </button>
            <button
              onClick={() => setActiveTab('rejected')}
              className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition ${
                activeTab === 'rejected'
                  ? 'bg-[#0f3834] text-white shadow-xs'
                  : 'text-slate-600 hover:bg-slate-100'
              }`}
            >
              Từ chối ({rejectedCount})
            </button>
            <button
              onClick={() => setActiveTab('all')}
              className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition ${
                activeTab === 'all'
                  ? 'bg-[#0f3834] text-white shadow-xs'
                  : 'text-slate-600 hover:bg-slate-100'
              }`}
            >
              Tất cả ({allRules.length})
            </button>
          </div>

          {/* Search box */}
          <div className="relative max-w-xs flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={14} />
            <input
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Tìm kiếm tên rule, biểu thức..."
              className="h-9 w-full rounded-lg border border-[#e2ece8] bg-slate-50 pl-9 pr-3 text-xs outline-none focus:border-[#008b74] focus:bg-white transition"
            />
          </div>
        </div>

        {/* Rules List */}
        <div className="divide-y divide-[#f0f4f2] p-6 space-y-6">
          {filteredRules.length === 0 ? (
            <div className="py-12 text-center text-slate-400">
              <CheckCircle2 size={36} className="mx-auto mb-2 text-[#008b74] opacity-50" />
              <p className="text-sm font-medium text-slate-600">Không có rule nào trong mục này</p>
              <p className="text-xs text-slate-400">Chọn tab khác hoặc điều chỉnh tìm kiếm.</p>
            </div>
          ) : (
            filteredRules.map((rule: ProposedRule & { datasetName: string }) => {
              const isPending = rule.status === 'pending';
              const isApproved = rule.status === 'approved';

              return (
                <div
                  key={rule.id}
                  className="rounded-xl border border-[#e2ece8] bg-[#fbfdfc] p-5 shadow-2xs transition hover:border-[#bfe7dc]"
                >
                  {/* Top line info */}
                  <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                    <div>
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="font-mono text-xs font-bold text-slate-900">{rule.name}</span>
                        <Badge
                          tone={rule.severity === 'CRITICAL' ? 'red' : rule.severity === 'HIGH' ? 'amber' : 'blue'}
                        >
                          {rule.severity}
                        </Badge>
                        <span className="rounded-md bg-slate-100 px-2 py-0.5 text-[10px] font-medium text-slate-600">
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
                            variant="xanhsm"
                            size="sm"
                            onClick={() => approveRule(rule.id)}
                            className="h-8 gap-1.5 px-3 text-xs font-semibold"
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
                            <Check size={14} /> Đã duyệt bởi Steward
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
                          className="h-8 flex-1 rounded-md border border-[#008b74] bg-white px-2.5 font-mono text-xs text-slate-800"
                        />
                        <Button size="sm" variant="xanhsm" onClick={() => handleSaveEdit(rule.id)} className="h-8">
                          Lưu
                        </Button>
                        <Button size="sm" variant="outline" onClick={() => setEditingRuleId(null)} className="h-8">
                          Hủy
                        </Button>
                      </div>
                    ) : (
                      <code className="block rounded-lg border border-[#d2e2dc] bg-white px-3 py-2 font-mono text-xs font-semibold text-[#007460]">
                        {rule.expression}
                      </code>
                    )}
                  </div>

                  {/* Sandbox Impact Preview */}
                  <div className="mt-4 rounded-lg border border-[#e2ece8] bg-white p-3.5">
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
                  <div className="mt-3.5 flex flex-wrap items-center justify-between gap-2 border-t border-[#f0f4f2] pt-2.5 text-[11px] text-slate-400">
                    <div className="flex items-center gap-3">
                      <span>Căn cứ pháp lý: <strong className="text-slate-600">{rule.lawRef}</strong></span>
                    </div>
                    <Link
                      to={`/results?tab=evidence&ref=${rule.evidenceId}`}
                      className="inline-flex items-center gap-1 font-medium text-[#008b74] hover:underline"
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
  );
}
