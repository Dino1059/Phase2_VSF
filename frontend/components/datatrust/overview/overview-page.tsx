'use client';
import { useState, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Activity,
  AlertTriangle,
  ArrowRight,
  Check,
  CheckCircle2,
  Clock,
  Copy,
  Cpu,
  FilePlus2,
  Loader2,
  Play,
  Scale,
  Search,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  X,
  XCircle,
  Zap,
} from 'lucide-react';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  useAgentStore,
  type ComplianceCaseItem,
  type FindingItem,
  type PolicyItem,
  type ProposedRule,
  type DatasetItem,
} from '@/lib/agent-store';
import { FindingInspectorModal } from '@/components/datatrust/findings/finding-inspector-modal';

interface ToastState {
  type: 'success' | 'info' | 'error';
  message: string;
}

// AI Agent Dataset Intelligence Profiles
const DATASET_AI_INSIGHTS: Record<
  string,
  {
    riskLevel: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
    summary: string;
    suggestedControls: { code: string; title: string; law: string; target: string }[];
    profilingMetrics: { completeness: string; validity: string; integrityScore: string };
  }
> = {
  trips: {
    riskLevel: 'HIGH',
    summary:
      'AI Agent phân tích 12,480 bản ghi: Phát hiện 18 cuốc xe cước 0đ/cự ly âm (IFRS 15) và 7 bản ghi lộ SĐT khách hàng cleartext. Đề xuất 2 Controls kiểm toán tự động.',
    suggestedControls: [
      { code: 'TC-REV-01', title: 'Hợp lệ Doanh thu & Cự ly', law: 'IFRS 15 / SOX 404', target: 'Quarantine Lane' },
      { code: 'TC-PII-02', title: 'Che mờ SĐT khách hàng', law: 'Nghị định 13/2023 & GDPR', target: 'Dynamic Masking' },
    ],
    profilingMetrics: { completeness: '99.85%', validity: '99.86%', integrityScore: '98.6/100' },
  },
  customers: {
    riskLevel: 'HIGH',
    summary:
      'AI Agent phân tích 10,000 bản ghi: Phát hiện 14 số CCCD/eID sai định dạng độ dài và 6 tài khoản disposable email. Đề xuất 2 Controls kiểm tra KYC & Ingestion Gate.',
    suggestedControls: [
      { code: 'TC-KYC-01', title: 'Định dạng Số CCCD/eID', law: 'Luật Căn cước 2023', target: 'SQL Schema Checker' },
    ],
    profilingMetrics: { completeness: '99.72%', validity: '99.86%', integrityScore: '98.9/100' },
  },
  drivers: {
    riskLevel: 'MEDIUM',
    summary:
      'AI Agent phân tích 1,200 bản ghi: Phát hiện 6 tài xế có GPLX hết hạn trong 7 ngày nhưng vẫn mở ca trực. Đề xuất 1 Control chặn điều phối tự động.',
    suggestedControls: [
      { code: 'TC-DRV-01', title: 'Hiệu lực GPLX Tài xế', law: 'Luật Giao thông 2024', target: 'Daily Dispatch Gate' },
    ],
    profilingMetrics: { completeness: '99.91%', validity: '99.50%', integrityScore: '99.2/100' },
  },
  charging: {
    riskLevel: 'MEDIUM',
    summary:
      'AI Agent phân tích 8,500 bản ghi: Phát hiện 9 phiên sạc sai lệch công tơ Modbus vượt 3%. Đề xuất 1 Control kiểm soát sai số điện năng trạm sạc DC.',
    suggestedControls: [
      { code: 'TC-CHG-01', title: 'Sai lệch Công tơ Trụ sạc', law: 'SOX 404 & Chuẩn Đo lường', target: 'Energy Billing Guard' },
    ],
    profilingMetrics: { completeness: '99.88%', validity: '99.64%', integrityScore: '99.1/100' },
  },
  telemetry: {
    riskLevel: 'CRITICAL',
    summary:
      'AI Agent phân tích 45,000 bản ghi: Phát hiện 12 gói tin IoT nhiệt độ cell pin BMS vượt 65°C và 28 bản ghi lỗi SoC pin âm. Đề xuất 1 Control ngắt sạc an toàn.',
    suggestedControls: [
      { code: 'TC-IOT-01', title: 'Nhiệt độ Cell Pin BMS', law: 'UN ECE R100', target: 'BMS Ingestion Gate' },
    ],
    profilingMetrics: { completeness: '99.95%', validity: '99.76%', integrityScore: '97.8/100' },
  },
};

export function OverviewPage() {
  const navigate = useNavigate();
  const {
    currentRole,
    selectedDatasetId,
    selectDataset,
    datasets,
    complianceCases,
    runComplianceCase,
    runAllComplianceCasesForDataset,
    openFindingModal,
    policies,
    selectedPolicyId,
    selectPolicy,
    simulatePolicyDryRun,
    approvePolicyRule,
    rejectPolicyRule,
    addNewPolicyText,
    approveRule,
    rejectRule,
  } = useAgentStore();

  const currentDataset: DatasetItem = datasets[selectedDatasetId] || datasets.trips;
  const aiInsight = DATASET_AI_INSIGHTS[selectedDatasetId] || DATASET_AI_INSIGHTS.trips;

  // AI Agent Lifecycle State on Dataset Selection
  const [isAgentAnalyzingDataset, setIsAgentAnalyzingDataset] = useState(false);
  const [agentAnalysisProgress, setAgentAnalysisProgress] = useState(100);
  const [agentAnalysisStepText, setAgentAnalysisStepText] = useState('AI Agent đã sẵn sàng');

  // Local state for Search & Filters
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<'all' | 'passed' | 'failed' | 'not_evaluated'>('all');
  const [adminRuleFilter, setAdminRuleFilter] = useState<'all' | 'pending' | 'approved' | 'rejected'>('all');

  // Modal & Copy State
  const [showAddPolicyModal, setShowAddPolicyModal] = useState(false);
  const [newPolicyTitle, setNewPolicyTitle] = useState('');
  const [newPolicyText, setNewPolicyText] = useState('');
  const [isAnalyzingNewPolicy, setIsAnalyzingNewPolicy] = useState(false);
  const [isSimulatingPolicy, setIsSimulatingPolicy] = useState(false);
  const [copiedId, setCopiedId] = useState<string | null>(null);

  // Toast Feedback State
  const [toast, setToast] = useState<ToastState | null>(null);

  const showToast = (message: string, type: 'success' | 'info' | 'error' = 'success') => {
    setToast({ message, type });
    setTimeout(() => {
      setToast((cur) => (cur?.message === message ? null : cur));
    }, 3500);
  };

  const handleCopy = (text: string, id: string) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    showToast('Đã sao chép vào bộ nhớ tạm', 'info');
    setTimeout(() => {
      setCopiedId((cur) => (cur === id ? null : cur));
    }, 2000);
  };

  // Trigger automated AI agent analysis when dataset changes
  const handleSelectDataset = (datasetId: string) => {
    if (datasetId === selectedDatasetId) return;
    selectDataset(datasetId);
    setIsAgentAnalyzingDataset(true);
    setAgentAnalysisProgress(20);
    setAgentAnalysisStepText('1. AI Agent quét lược đồ dữ liệu & cấu trúc bảng...');

    setTimeout(() => {
      setAgentAnalysisProgress(65);
      setAgentAnalysisStepText('2. AI Agent đối chiếu tiêu chuẩn kiểm toán & phát hiện bất thường...');
    }, 250);

    setTimeout(() => {
      setAgentAnalysisProgress(100);
      setAgentAnalysisStepText('3. AI Agent đề xuất Compliance Controls hoàn tất!');
      setIsAgentAnalyzingDataset(false);
    }, 550);
  };

  // Auditor Data Calculations
  const casesForDataset = useMemo(
    () => complianceCases.filter((c: ComplianceCaseItem) => c.datasetId === selectedDatasetId),
    [complianceCases, selectedDatasetId]
  );
  const totalCases = casesForDataset.length;
  const passedCases = casesForDataset.filter((c) => c.status === 'passed').length;
  const failedCases = casesForDataset.filter((c) => c.status === 'failed').length;
  const notEvaluatedCases = casesForDataset.filter((c) => c.status === 'not_evaluated').length;
  const isAnyRunning = casesForDataset.some((c) => c.status === 'running');

  // Filtered Auditor Cases
  const filteredCases = useMemo(() => {
    return casesForDataset.filter((item) => {
      if (statusFilter !== 'all' && item.status !== statusFilter) return false;
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase();
        return (
          item.code.toLowerCase().includes(q) ||
          item.name.toLowerCase().includes(q) ||
          item.domain.toLowerCase().includes(q) ||
          item.lawStandard.toLowerCase().includes(q) ||
          item.description.toLowerCase().includes(q)
        );
      }
      return true;
    });
  }, [casesForDataset, statusFilter, searchQuery]);

  // Admin Data Calculations
  const policiesForDataset = useMemo(
    () => policies.filter((p: PolicyItem) => p.datasetId === selectedDatasetId),
    [policies, selectedDatasetId]
  );
  const currentPolicy =
    policiesForDataset.find((p) => p.id === selectedPolicyId) ||
    policiesForDataset[0] ||
    policies[0];

  const filteredRules = useMemo(() => {
    return currentDataset.proposedRules.filter((r) => {
      if (adminRuleFilter !== 'all' && r.status !== adminRuleFilter) return false;
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase();
        return (
          r.name.toLowerCase().includes(q) ||
          r.expression.toLowerCase().includes(q) ||
          r.rationale.toLowerCase().includes(q)
        );
      }
      return true;
    });
  }, [currentDataset.proposedRules, adminRuleFilter, searchQuery]);

  // Handlers for AI Agent Orchestration
  const handleRunAllCases = async () => {
    showToast('AI Agent bắt đầu điều phối kiểm toán toàn bộ tiêu chuẩn...', 'info');
    await runAllComplianceCasesForDataset();
    showToast('AI Agent đã hoàn tất kiểm toán tự động cho bộ dữ liệu!', 'success');
  };

  const handleRunSingleCase = async (caseId: string, caseCode: string) => {
    showToast(`AI Agent đang kiểm toán tiêu chuẩn ${caseCode}...`, 'info');
    await runComplianceCase(caseId);
    showToast(`AI Agent: Kiểm toán hoàn tất cho ${caseCode}`, 'success');
  };

  const handleAddNewPolicy = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newPolicyTitle.trim() || !newPolicyText.trim()) return;
    setIsAnalyzingNewPolicy(true);
    showToast('AI Agent đang phân tích văn bản & trích xuất Control đề xuất...', 'info');

    setTimeout(() => {
      addNewPolicyText(newPolicyTitle.trim(), newPolicyText.trim());
      setIsAnalyzingNewPolicy(false);
      setNewPolicyTitle('');
      setNewPolicyText('');
      setShowAddPolicyModal(false);
      showToast('AI Agent đã diễn dịch thành công Rule kỹ thuật mới!', 'success');
    }, 700);
  };

  const handleRunSimulation = async (policyId: string) => {
    setIsSimulatingPolicy(true);
    showToast('AI Agent đang chạy mô phỏng Dry-Run an toàn trên tập dữ liệu...', 'info');
    await simulatePolicyDryRun(policyId);
    setIsSimulatingPolicy(false);
    showToast('Mô phỏng Dry-Run hoàn tất! Xem báo cáo phân tích trước khi duyệt.', 'success');
  };

  const handleApprovePolicyRule = (policyId: string) => {
    approvePolicyRule(policyId);
    showToast('Đã phê duyệt Rule đề xuất! AI Agent đã kích hoạt vào Pipeline sản xuất.', 'success');
  };

  const handleRejectPolicyRule = (policyId: string) => {
    rejectPolicyRule(policyId);
    showToast('Đã từ chối áp dụng rule.', 'info');
  };

  const handleApproveRule = (ruleId: string, ruleName: string) => {
    approveRule(ruleId);
    showToast(`Đã duyệt rule "${ruleName}" vào Pipeline!`, 'success');
  };

  const handleRejectRule = (ruleId: string) => {
    rejectRule(ruleId);
    showToast('Đã từ chối áp dụng rule.', 'info');
  };

  return (
    <div className="page-enter mx-auto max-w-[1360px] space-y-6">
      
      {/* Toast Notification */}
      {toast && (
        <div
          role="status"
          aria-live="polite"
          className={`fixed bottom-6 right-6 z-50 flex items-center gap-3 rounded-xl border px-4 py-3 shadow-lg transition-all animate-in fade-in slide-in-from-bottom-5 duration-200 ${
            toast.type === 'success'
              ? 'border-emerald-200 bg-emerald-50 text-emerald-900'
              : toast.type === 'error'
              ? 'border-rose-200 bg-rose-50 text-rose-900'
              : 'border-[#bfe7dc] bg-[#f0f9f6] text-[#006e5b]'
          }`}
        >
          {toast.type === 'success' && <CheckCircle2 size={18} className="text-emerald-600 shrink-0" />}
          {toast.type === 'error' && <AlertTriangle size={18} className="text-rose-600 shrink-0" />}
          {toast.type === 'info' && <Sparkles size={18} className="text-[#008b74] shrink-0" />}
          <span className="text-xs font-semibold">{toast.message}</span>
          <button
            type="button"
            onClick={() => setToast(null)}
            className="ml-2 text-slate-400 hover:text-slate-600 focus:outline-none"
            aria-label="Đóng thông báo"
          >
            <X size={14} />
          </button>
        </div>
      )}

      {/* 1. Header with Primary Action (Consistent Layout) */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <span className="text-[11px] font-bold uppercase tracking-wider text-[#008b74]">
            {currentRole === 'auditor' ? 'AI Agent Kiểm Toán Tuân Thủ' : 'AI Agent Quản Trị & Thích Ứng Rule'}
          </span>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">
            {currentRole === 'auditor' ? 'Tổng Quan Kiểm Toán & Bằng Chứng' : 'Tổng Quan Quản Trị Hệ Thống'}
          </h1>
        </div>

        {/* Primary CTA */}
        <div>
          {currentRole === 'auditor' ? (
            <Button
              variant="xanhsm"
              size="sm"
              onClick={handleRunAllCases}
              disabled={isAnyRunning || isAgentAnalyzingDataset}
              className="h-9 px-4 text-xs font-semibold shadow-xs gap-2"
            >
              {isAnyRunning ? (
                <>
                  <Loader2 size={14} className="animate-spin" />
                  AI Agent đang kiểm toán...
                </>
              ) : (
                <>
                  <Sparkles size={14} />
                   AI Agent: Điều phối Kiểm toán Toàn bộ
                </>
              )}
            </Button>
          ) : (
            <Button
              variant="xanhsm"
              size="sm"
              onClick={() => setShowAddPolicyModal(true)}
              className="h-9 px-4 text-xs font-semibold shadow-xs gap-2"
            >
              <FilePlus2 size={14} />
              Thêm chính sách mới (AI Trích xuất)
            </Button>
          )}
        </div>
      </div>

      {/* 2. Executive Summary Metrics (KPI Cards) */}
      {currentRole === 'auditor' ? (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          <Card className="p-4 rounded-xl border-[#e2ece8] bg-white shadow-2xs">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-slate-600 uppercase tracking-wide">
                Quy định kiểm tra
              </span>
              <span className="grid size-7 place-items-center rounded-lg bg-slate-100 text-slate-600">
                <ShieldCheck size={15} />
              </span>
            </div>
            <div className="mt-2 flex items-baseline gap-2">
              <span className="text-2xl font-bold text-slate-900">{totalCases}</span>
              <span className="text-xs text-slate-500">quy định</span>
            </div>
          </Card>

          <Card
            onClick={() => setStatusFilter(statusFilter === 'passed' ? 'all' : 'passed')}
            className={`cursor-pointer p-4 rounded-xl border transition shadow-2xs ${
              statusFilter === 'passed'
                ? 'border-[#008b74] bg-[#f0f9f6] ring-1 ring-[#008b74]'
                : 'border-[#e2ece8] bg-white hover:border-[#bfe7dc]'
            }`}
          >
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-emerald-700 uppercase tracking-wide">
                Đạt chuẩn (PASS)
              </span>
              <span className="grid size-7 place-items-center rounded-lg bg-emerald-50 text-emerald-700">
                <CheckCircle2 size={15} />
              </span>
            </div>
            <div className="mt-2 flex items-baseline gap-2">
              <span className="text-2xl font-bold text-emerald-700">{passedCases}</span>
              <span className="text-xs text-emerald-600">quy định</span>
            </div>
          </Card>

          <Card
            onClick={() => setStatusFilter(statusFilter === 'failed' ? 'all' : 'failed')}
            className={`cursor-pointer p-4 rounded-xl border transition shadow-2xs ${
              statusFilter === 'failed'
                ? 'border-rose-400 bg-rose-50/60 ring-1 ring-rose-400'
                : 'border-[#e2ece8] bg-white hover:border-rose-200'
            }`}
          >
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-rose-700 uppercase tracking-wide">
                Phát hiện vi phạm (FAIL)
              </span>
              <span className="grid size-7 place-items-center rounded-lg bg-rose-50 text-rose-700">
                <AlertTriangle size={15} />
              </span>
            </div>
            <div className="mt-2 flex items-baseline gap-2">
              <span className="text-2xl font-bold text-rose-700">{failedCases}</span>
              <span className="text-xs text-rose-600">quy định</span>
            </div>
          </Card>

          <Card
            onClick={() => setStatusFilter(statusFilter === 'not_evaluated' ? 'all' : 'not_evaluated')}
            className={`cursor-pointer p-4 rounded-xl border transition shadow-2xs ${
              statusFilter === 'not_evaluated'
                ? 'border-slate-400 bg-slate-100 ring-1 ring-slate-400'
                : 'border-[#e2ece8] bg-white hover:border-slate-300'
            }`}
          >
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-slate-600 uppercase tracking-wide">
                Chưa kiểm tra
              </span>
              <span className="grid size-7 place-items-center rounded-lg bg-slate-100 text-slate-600">
                <Clock size={15} />
              </span>
            </div>
            <div className="mt-2 flex items-baseline gap-2">
              <span className="text-2xl font-bold text-slate-800">{notEvaluatedCases}</span>
              <span className="text-xs text-slate-500">quy định</span>
            </div>
          </Card>
        </div>
      ) : (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          <Card className="p-4 rounded-xl border-[#e2ece8] bg-white shadow-2xs">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-slate-600 uppercase tracking-wide">
                Chính sách áp dụng
              </span>
              <span className="grid size-7 place-items-center rounded-lg bg-[#e6f6f2] text-[#007460]">
                <Scale size={15} />
              </span>
            </div>
            <div className="mt-2 flex items-baseline gap-2">
              <span className="text-2xl font-bold text-slate-900">{policiesForDataset.length}</span>
              <span className="text-xs text-slate-500">chính sách</span>
            </div>
          </Card>

          <Card
            onClick={() => setAdminRuleFilter(adminRuleFilter === 'approved' ? 'all' : 'approved')}
            className="cursor-pointer p-4 rounded-xl border border-[#e2ece8] bg-white shadow-2xs hover:border-[#bfe7dc] transition"
          >
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-[#007460] uppercase tracking-wide">
                Luật đang chạy (Active Rules)
              </span>
              <span className="grid size-7 place-items-center rounded-lg bg-emerald-50 text-emerald-700">
                <CheckCircle2 size={15} />
              </span>
            </div>
            <div className="mt-2 flex items-baseline gap-2">
              <span className="text-2xl font-bold text-[#007460]">
                {currentDataset.proposedRules.length}
              </span>
              <span className="text-xs text-slate-500">quy tắc</span>
            </div>
          </Card>

          <Card className="p-4 rounded-xl border-[#e2ece8] bg-white shadow-2xs">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-emerald-700 uppercase tracking-wide">
                Dữ liệu sạch (Silver)
              </span>
              <span className="grid size-7 place-items-center rounded-lg bg-emerald-50 text-emerald-700">
                <Sparkles size={15} />
              </span>
            </div>
            <div className="mt-2 flex items-baseline gap-2">
              <span className="text-2xl font-bold text-emerald-700">99.85%</span>
              <span className="text-xs text-emerald-600">chuẩn IPO</span>
            </div>
          </Card>

          <Card className="p-4 rounded-xl border-[#e2ece8] bg-white shadow-2xs">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-amber-700 uppercase tracking-wide">
                Bản ghi cách ly (Quarantine)
              </span>
              <span className="grid size-7 place-items-center rounded-lg bg-amber-50 text-amber-700">
                <AlertTriangle size={15} />
              </span>
            </div>
            <div className="mt-2 flex items-baseline gap-2">
              <span className="text-2xl font-bold text-amber-700">{currentDataset.anomalies}</span>
              <span className="text-xs text-amber-600">bản ghi</span>
            </div>
          </Card>
        </div>
      )}

      {/* 3. Dataset Selector Bar */}
      <Card className="rounded-xl border-[#e2ece8] bg-white p-4 shadow-xs space-y-3">
        <div className="flex flex-col gap-2.5 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-2">
            <span className="text-xs font-semibold text-slate-800">Bộ dữ liệu:</span>
            <span className="text-xs text-slate-500">Chọn dataset để AI Agent tự động phân tích & đề xuất Controls</span>
          </div>

          <div className="flex items-center gap-1.5 overflow-x-auto pb-1 sm:pb-0">
            {Object.values(datasets).map((ds: DatasetItem) => {
              const isSelected = ds.id === selectedDatasetId;
              return (
                <button
                  key={ds.id}
                  type="button"
                  onClick={() => handleSelectDataset(ds.id)}
                  className={`inline-flex items-center gap-2 rounded-lg px-3 py-1.5 text-xs font-medium transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#008b74] ${
                    isSelected
                      ? 'bg-[#008b74] text-white shadow-xs font-semibold'
                      : 'bg-slate-100 text-slate-700 hover:bg-slate-200/70'
                  }`}
                >
                  <span className="font-mono uppercase">{ds.id}</span>
                  <span className="text-[11px] opacity-85">({ds.records.toLocaleString('vi-VN')})</span>
                  {ds.anomalies > 0 ? (
                    <span
                      className={`size-2 rounded-full ${isSelected ? 'bg-amber-300' : 'bg-rose-500'}`}
                      title={`${ds.anomalies} bản ghi cách ly`}
                    />
                  ) : null}
                </button>
              );
            })}
          </div>
        </div>

        {/* Live scanning progress bar when changing dataset */}
        {isAgentAnalyzingDataset && (
          <div className="rounded-lg border border-[#bfe7dc] bg-[#f0f9f6] p-3 space-y-2 animate-in fade-in">
            <div className="flex items-center justify-between text-xs text-[#007460] font-semibold">
              <span className="flex items-center gap-2">
                <Loader2 size={13} className="animate-spin text-[#008b74]" />
                {agentAnalysisStepText}
              </span>
              <span className="font-mono">{agentAnalysisProgress}%</span>
            </div>
            <div className="h-1.5 w-full bg-[#d2e2dc] rounded-full overflow-hidden">
              <div
                className="h-full bg-[#008b74] transition-all duration-300 ease-out"
                style={{ width: `${agentAnalysisProgress}%` }}
              />
            </div>
          </div>
        )}
      </Card>

      {/* 4. AI AGENT INTELLIGENCE & RECOMMENDATION HUB (Agent-Centric Core) */}
      <Card className="rounded-xl border border-[#bfe7dc] bg-[#f8fbf9] p-5 shadow-xs space-y-4">
        {/* Agent Header */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 border-b border-[#e2ece8] pb-3">
          <div className="flex items-center gap-2.5">
            <span className="grid size-8 place-items-center rounded-lg bg-[#e6f6f2] text-[#007460]">
              <Sparkles size={16} />
            </span>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-sm font-bold text-slate-900">
                  AI Agent Intelligence Hub
                </h2>
                <span className="inline-flex items-center gap-1 rounded-full bg-[#e6f6f2] px-2 py-0.5 text-[10px] font-bold text-[#007460] border border-[#bfe7dc]">
                  <span className="size-1.5 rounded-full bg-[#008b74] animate-pulse" />
                  AI Agent Active
                </span>
              </div>
              <p className="text-xs text-slate-500 mt-0.5">
                AI Agent liên tục phân tích schema, profiling chất lượng và đề xuất controls phù hợp.
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <Badge
              tone={
                aiInsight.riskLevel === 'CRITICAL'
                  ? 'red'
                  : aiInsight.riskLevel === 'HIGH'
                  ? 'amber'
                  : 'green'
              }
              className="text-xs px-2.5 py-1 font-semibold"
            >
              Mức độ rủi ro: {aiInsight.riskLevel}
            </Badge>
          </div>
        </div>

        {/* AI Insight Body */}
        <div className="grid sm:grid-cols-3 gap-4 text-xs">
          {/* Col 1 & 2: AI Analysis Summary & Recommendations */}
          <div className="sm:col-span-2 space-y-3">
            <div className="rounded-lg bg-white p-3.5 border border-[#d2e2dc] space-y-1.5">
              <span className="text-[11px] font-bold text-[#007460] uppercase tracking-wide flex items-center gap-1.5">
                <Cpu size={13} />
                Kết quả phân tích tự động từ AI Agent:
              </span>
              <p className="text-xs leading-relaxed text-slate-700 font-medium">
                {aiInsight.summary}
              </p>
            </div>

            {/* AI Suggested Controls Chips */}
            <div className="space-y-1.5">
              <span className="text-[11px] font-semibold text-slate-500 uppercase tracking-wide">
                AI Agent đề xuất áp dụng ngay các Controls trọng yếu:
              </span>
              <div className="flex flex-wrap gap-2">
                {aiInsight.suggestedControls.map((sc) => (
                  <div
                    key={sc.code}
                    className="inline-flex items-center gap-2 rounded-lg border border-[#bfe7dc] bg-white px-3 py-1.5 text-xs shadow-2xs"
                  >
                    <span className="font-mono font-bold text-[#007460]">{sc.code}</span>
                    <span className="font-medium text-slate-800">{sc.title}</span>
                    <span className="text-[11px] text-slate-400">· {sc.law}</span>
                    <span className="rounded bg-[#e6f6f2] px-1.5 py-0.2 text-[10px] font-semibold text-[#006e5b]">
                      {sc.target}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Col 3: Automated Profiling Metrics & One-Click Agent Orchestration */}
          <div className="space-y-3 flex flex-col justify-between rounded-lg border border-slate-200 bg-white p-3.5">
            <div className="space-y-2">
              <span className="text-[11px] font-bold text-slate-500 uppercase tracking-wide block">
                Chỉ số Data Health:
              </span>
              <div className="grid grid-cols-3 gap-2 text-center">
                <div className="rounded bg-slate-50 p-1.5 border border-slate-100">
                  <span className="text-[10px] text-slate-500 block">Toàn vẹn</span>
                  <strong className="text-xs font-bold text-slate-800">{aiInsight.profilingMetrics.integrityScore}</strong>
                </div>
                <div className="rounded bg-slate-50 p-1.5 border border-slate-100">
                  <span className="text-[10px] text-slate-500 block">Đầy đủ</span>
                  <strong className="text-xs font-bold text-emerald-700">{aiInsight.profilingMetrics.completeness}</strong>
                </div>
                <div className="rounded bg-slate-50 p-1.5 border border-slate-100">
                  <span className="text-[10px] text-slate-500 block">Hợp lệ</span>
                  <strong className="text-xs font-bold text-emerald-700">{aiInsight.profilingMetrics.validity}</strong>
                </div>
              </div>
            </div>

            {/* Orchestration Trigger Button inside the Hub */}
            <div className="pt-2 border-t border-slate-100">
              {currentRole === 'auditor' ? (
                <Button
                  variant="xanhsm"
                  size="sm"
                  onClick={handleRunAllCases}
                  disabled={isAnyRunning}
                  className="w-full text-xs font-semibold gap-1.5 h-8 shadow-xs"
                >
                  {isAnyRunning ? (
                    <>
                      <Loader2 size={13} className="animate-spin" />
                      Đang điều phối kiểm toán...
                    </>
                  ) : (
                    <>
                      <Zap size={13} />
                      Chạy toàn bộ Controls đề xuất
                    </>
                  )}
                </Button>
              ) : (
                <Button
                  variant="xanhsm"
                  size="sm"
                  onClick={() => setShowAddPolicyModal(true)}
                  className="w-full text-xs font-semibold gap-1.5 h-8 shadow-xs"
                >
                  <FilePlus2 size={13} />
                  Thêm chính sách cho AI xử lý
                </Button>
              )}
            </div>
          </div>
        </div>

        {/* Real-time AI Agent Orchestration Stepper Banner (When Running) */}
        {isAnyRunning && (
          <div className="rounded-lg border border-amber-300 bg-amber-50/50 p-3.5 space-y-2.5 animate-in fade-in">
            <div className="flex items-center justify-between text-xs font-bold text-amber-900">
              <span className="flex items-center gap-2">
                <Loader2 size={14} className="animate-spin text-amber-600" />
                AI Agent đang điều phối tiến trình kiểm toán tự động:
              </span>
              <span className="text-[11px] font-mono text-amber-700">Đang chạy...</span>
            </div>
            <div className="grid sm:grid-cols-3 gap-2 text-xs">
              <div className="flex items-center gap-2 bg-white px-3 py-2 rounded-md border border-amber-200 text-slate-700 font-medium">
                <Loader2 size={13} className="animate-spin text-amber-600 shrink-0" />
                <span>1. Phân tích ràng buộc tiêu chuẩn</span>
              </div>
              <div className="flex items-center gap-2 bg-white px-3 py-2 rounded-md border border-amber-200 text-slate-700 font-medium">
                <span className="size-2 rounded-full bg-amber-500 animate-pulse shrink-0" />
                <span>2. Tính mã Merkle Leaf Hash SHA-256</span>
              </div>
              <div className="flex items-center gap-2 bg-white px-3 py-2 rounded-md border border-amber-200 text-slate-700 font-medium">
                <span className="size-2 rounded-full bg-slate-300 shrink-0" />
                <span>3. Trích xuất Finding & Bằng chứng</span>
              </div>
            </div>
          </div>
        )}
      </Card>

      {/* 5. Toolbar: Search Bar & Status Filter Tabs */}
      <Card className="rounded-xl border-[#e2ece8] bg-white p-3.5 shadow-xs flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        {/* Search */}
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={14} />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder={
              currentRole === 'auditor'
                ? 'Tìm kiếm mã case, tiêu chuẩn, tên quy tắc...'
                : 'Tìm kiếm rule, logic biểu thức...'
            }
            className="h-9 w-full rounded-lg border border-[#e2ece8] bg-slate-50 pl-9 pr-8 text-xs text-slate-800 placeholder-slate-400 focus:border-[#008b74] focus:bg-white focus:outline-none focus:ring-1 focus:ring-[#008b74] transition"
          />
          {searchQuery && (
            <button
              type="button"
              onClick={() => setSearchQuery('')}
              className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
              aria-label="Xóa từ khóa tìm kiếm"
            >
              <X size={14} />
            </button>
          )}
        </div>

        {/* Filter Tabs */}
        {currentRole === 'auditor' ? (
          <div className="flex items-center gap-1 overflow-x-auto">
            <button
              type="button"
              onClick={() => setStatusFilter('all')}
              className={`rounded-lg px-2.5 py-1 text-xs font-medium transition ${
                statusFilter === 'all'
                  ? 'bg-[#0f3834] text-white font-semibold'
                  : 'text-slate-600 hover:bg-slate-100'
              }`}
            >
              Tất cả ({totalCases})
            </button>
            <button
              type="button"
              onClick={() => setStatusFilter('passed')}
              className={`rounded-lg px-2.5 py-1 text-xs font-medium transition ${
                statusFilter === 'passed'
                  ? 'bg-emerald-700 text-white font-semibold'
                  : 'text-emerald-700 hover:bg-emerald-50'
              }`}
            >
              Đạt chuẩn ({passedCases})
            </button>
            <button
              type="button"
              onClick={() => setStatusFilter('failed')}
              className={`rounded-lg px-2.5 py-1 text-xs font-medium transition ${
                statusFilter === 'failed'
                  ? 'bg-rose-700 text-white font-semibold'
                  : 'text-rose-700 hover:bg-rose-50'
              }`}
            >
              Vi phạm ({failedCases})
            </button>
            <button
              type="button"
              onClick={() => setStatusFilter('not_evaluated')}
              className={`rounded-lg px-2.5 py-1 text-xs font-medium transition ${
                statusFilter === 'not_evaluated'
                  ? 'bg-slate-700 text-white font-semibold'
                  : 'text-slate-600 hover:bg-slate-100'
              }`}
            >
              Chưa đánh giá ({notEvaluatedCases})
            </button>
          </div>
        ) : (
          <div className="flex items-center gap-1 overflow-x-auto">
            <button
              type="button"
              onClick={() => setAdminRuleFilter('all')}
              className={`rounded-lg px-2.5 py-1 text-xs font-medium transition ${
                adminRuleFilter === 'all'
                  ? 'bg-[#0f3834] text-white font-semibold'
                  : 'text-slate-600 hover:bg-slate-100'
              }`}
            >
              Tất cả ({currentDataset.proposedRules.length})
            </button>
            <button
              type="button"
              onClick={() => setAdminRuleFilter('approved')}
              className={`rounded-lg px-2.5 py-1 text-xs font-medium transition ${
                adminRuleFilter === 'approved'
                  ? 'bg-emerald-700 text-white font-semibold'
                  : 'text-emerald-700 hover:bg-emerald-50'
              }`}
            >
              Đang chạy ({currentDataset.proposedRules.filter((r) => r.status === 'approved').length})
            </button>
            <button
              type="button"
              onClick={() => setAdminRuleFilter('pending')}
              className={`rounded-lg px-2.5 py-1 text-xs font-medium transition ${
                adminRuleFilter === 'pending'
                  ? 'bg-amber-600 text-white font-semibold'
                  : 'text-amber-700 hover:bg-amber-50'
              }`}
            >
              Chờ duyệt ({currentDataset.proposedRules.filter((r) => r.status === 'pending').length})
            </button>
            <button
              type="button"
              onClick={() => setAdminRuleFilter('rejected')}
              className={`rounded-lg px-2.5 py-1 text-xs font-medium transition ${
                adminRuleFilter === 'rejected'
                  ? 'bg-slate-700 text-white font-semibold'
                  : 'text-slate-600 hover:bg-slate-100'
              }`}
            >
              Đã hủy ({currentDataset.proposedRules.filter((r) => r.status === 'rejected').length})
            </button>
          </div>
        )}
      </Card>

      {/* ========================================================================= */}
      {/* 6A. AUDITOR VIEW: COMPLIANCE CASES & FINDINGS WORKSPACE                   */}
      {/* ========================================================================= */}
      {currentRole === 'auditor' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-base font-bold text-slate-900">
                Danh Sách Quy Định Kiểm Tra ({filteredCases.length})
              </h3>
            </div>
          </div>

          {filteredCases.length === 0 ? (
            <Card className="p-8 text-center rounded-xl border-[#e2ece8] bg-white">
              <div className="mx-auto grid size-10 place-items-center rounded-full bg-slate-100 text-slate-500 mb-3">
                <Search size={18} />
              </div>
              <h4 className="text-sm font-semibold text-slate-800">Không tìm thấy tiêu chuẩn phù hợp</h4>
              <p className="mt-1 text-xs text-slate-500">
                Thử thay đổi từ khóa tìm kiếm hoặc điều chỉnh bộ lọc trạng thái.
              </p>
              {(searchQuery || statusFilter !== 'all') && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    setSearchQuery('');
                    setStatusFilter('all');
                  }}
                  className="mt-3 text-xs"
                >
                  Xóa bộ lọc
                </Button>
              )}
            </Card>
          ) : (
            filteredCases.map((caseItem: ComplianceCaseItem) => {
              const isRunning = caseItem.status === 'running';
              const isPassed = caseItem.status === 'passed';
              const isFailed = caseItem.status === 'failed';
              const isNotEvaluated = caseItem.status === 'not_evaluated';

              return (
                <Card
                  key={caseItem.id}
                  className={`rounded-xl border p-5 transition shadow-2xs ${
                    isFailed
                      ? 'border-rose-200 bg-white hover:border-rose-300'
                      : isPassed
                      ? 'border-[#cbebe2] bg-white hover:border-[#a2ded1]'
                      : isRunning
                      ? 'border-amber-300 bg-amber-50/15'
                      : 'border-[#e2ece8] bg-white hover:border-slate-300'
                  }`}
                >
                  {/* Case Header */}
                  <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between border-b border-slate-100 pb-4">
                    <div className="space-y-1.5 flex-1 pr-3">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="font-mono text-xs font-bold text-[#007460] bg-[#e6f6f2] px-2 py-0.5 rounded border border-[#bfe7dc]">
                          {caseItem.code}
                        </span>
                        <h4 className="text-sm font-bold text-slate-900 leading-tight">
                          {caseItem.name}
                        </h4>
                        <Badge tone="slate" className="text-[11px]">
                          {caseItem.domain}
                        </Badge>
                      </div>

                      <div className="flex items-center gap-1.5 pt-0.5 text-xs text-slate-600">
                        <Scale size={13} className="text-[#008b74] shrink-0" />
                        <span>
                          Căn cứ pháp lý: <strong className="text-slate-700">{caseItem.lawStandard}</strong>
                        </span>
                      </div>

                      <p className="text-xs text-slate-600 pt-0.5 leading-relaxed">
                        <span className="font-medium text-slate-700">Mô tả kiểm soát: </span>
                        {caseItem.description}
                      </p>
                    </div>

                    {/* Status Badge & Action */}
                    <div className="flex items-center gap-3 shrink-0 sm:self-start">
                      {isNotEvaluated && (
                        <Badge tone="slate" className="px-2.5 py-1 text-xs font-semibold gap-1.5">
                          <Clock size={12} /> Chưa đánh giá
                        </Badge>
                      )}

                      {isRunning && (
                        <Badge tone="amber" className="px-2.5 py-1 text-xs font-semibold gap-1.5 animate-pulse">
                          <Loader2 size={12} className="animate-spin" /> AI đang kiểm tra...
                        </Badge>
                      )}

                      {isPassed && (
                        <Badge tone="green" className="px-2.5 py-1 text-xs font-bold gap-1.5">
                          <CheckCircle2 size={13} /> ĐẠT CHUẨN (PASS)
                        </Badge>
                      )}

                      {isFailed && (
                        <Badge tone="red" className="px-2.5 py-1 text-xs font-bold gap-1.5">
                          <AlertTriangle size={13} /> VI PHẠM (FAIL)
                        </Badge>
                      )}

                      <Button
                        variant={isNotEvaluated ? 'xanhsm' : 'outline'}
                        size="sm"
                        onClick={() => handleRunSingleCase(caseItem.id, caseItem.code)}
                        disabled={isRunning}
                        className="h-8 px-3 text-xs font-semibold gap-1.5"
                      >
                        {isRunning ? (
                          <Loader2 size={12} className="animate-spin" />
                        ) : (
                          <Play size={12} />
                        )}
                        {isNotEvaluated ? 'Chạy kiểm tra' : 'Kiểm tra lại'}
                      </Button>
                    </div>
                  </div>

                  {/* Body Content */}
                  <div className="mt-4">
                    {/* 1. Passed State */}
                    {isPassed && (
                      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 rounded-lg border border-[#cbebe2] bg-[#f0f9f6] p-3 text-xs text-[#006e5b]">
                        <div className="flex items-center gap-2">
                          <CheckCircle2 size={16} className="text-[#008b74] shrink-0" />
                          <span>
                            <strong>AI Agent xác nhận: 100% dữ liệu đạt chuẩn.</strong> Không phát hiện ngoại lệ hay rủi ro pháp lý.
                          </span>
                        </div>
                        <div className="flex items-center gap-3 font-mono text-[11px] text-slate-600">
                          <div className="flex items-center gap-1 bg-white px-2 py-0.5 rounded border border-[#bfe7dc]">
                            <span>Hash: </span>
                            <span className="font-semibold text-slate-800">
                              {(caseItem.evidenceHash || 'sha256:7a8f09d...821b').slice(0, 20)}...
                            </span>
                            <button
                              type="button"
                              onClick={() => handleCopy(caseItem.evidenceHash || 'sha256:7a8f09d821b', caseItem.id)}
                              className="ml-1 text-slate-400 hover:text-slate-700"
                              title="Sao chép toàn bộ mã SHA-256"
                              aria-label="Sao chép mã hash SHA-256"
                            >
                              {copiedId === caseItem.id ? (
                                <Check size={12} className="text-emerald-600" />
                              ) : (
                                <Copy size={12} />
                              )}
                            </button>
                          </div>
                          <span>{caseItem.executionTimeMs || 420}ms</span>
                        </div>
                      </div>
                    )}

                    {/* 2. Failed State: Structured Findings List */}
                    {isFailed && (
                      <div className="space-y-3">
                        <div className="flex items-center justify-between">
                          <span className="text-xs font-bold text-rose-800 uppercase tracking-wide flex items-center gap-1.5">
                            <ShieldAlert size={14} className="text-rose-600" />
                            AI Agent phát hiện {caseItem.findings.length} Finding vi phạm tiêu chuẩn
                          </span>
                          <span className="text-xs text-slate-500">
                            Click để mở phân tích nguyên nhân gốc rễ và đề xuất AI
                          </span>
                        </div>

                        <div className="space-y-2">
                          {caseItem.findings.map((finding: FindingItem) => (
                            <div
                              key={finding.id}
                              className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 rounded-lg border border-rose-200 bg-rose-50/20 p-3.5 hover:border-[#008b74] transition"
                            >
                              <div className="space-y-1 flex-1 pr-3">
                                <div className="flex flex-wrap items-center gap-2">
                                  <span className="font-mono text-xs font-bold text-rose-700 bg-white px-2 py-0.5 rounded border border-rose-200">
                                    {finding.id}
                                  </span>
                                  <Badge tone={finding.severity === 'CRITICAL' ? 'red' : 'amber'}>
                                    {finding.severity}
                                  </Badge>
                                  <strong className="text-xs text-slate-900">
                                    {finding.title}
                                  </strong>
                                  {finding.status === 'AUDITED' && (
                                    <Badge tone="green" className="text-[10px]">
                                      ✓ ĐÃ KIỂM TOÁN
                                    </Badge>
                                  )}
                                </div>
                                <p className="text-xs text-slate-600 line-clamp-1">
                                  {finding.rootCauseAnalysis}
                                </p>
                                <div className="flex items-center gap-3 text-xs text-slate-500 font-mono">
                                  <span>
                                    Cách ly: <strong className="text-rose-600">{finding.evidence.quarantinedCount} bản ghi</strong>
                                  </span>
                                  <span>
                                    SHA: {finding.evidence.hashSha256.slice(0, 16)}...
                                  </span>
                                </div>
                              </div>

                              <Button
                                variant="outline"
                                size="sm"
                                onClick={() => openFindingModal(finding.id)}
                                className="h-8 px-3 text-xs font-semibold text-[#007460] border-[#bfe7dc] bg-white hover:bg-[#e6f6f2] shrink-0 gap-1.5"
                              >
                                <Search size={13} />
                                Xem phân tích AI & Bằng chứng
                              </Button>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                </Card>
              );
            })
          )}
        </div>
      )}

      {/* ========================================================================= */}
      {/* 6B. ADMIN VIEW: POLICY ADAPTATION, DRY-RUN & RULES GOVERNANCE             */}
      {/* ========================================================================= */}
      {currentRole === 'admin' && (
        <div className="space-y-6">
          
          {/* Section: AI Policy Adaptation Engine & Dry-Run Simulation */}
          <Card className="rounded-xl border-[#e2ece8] bg-white p-5 shadow-xs space-y-5">
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between border-b border-[#f0f4f2] pb-4">
              <div>
                <span className="text-[11px] font-bold uppercase tracking-wider text-[#008b74]">
                  BỘ THÍCH ỨNG CHÍNH SÁCH BẰNG AI (POLICY ADAPTATION ENGINE)
                </span>
                <h3 className="text-lg font-bold text-slate-900 mt-0.5">
                  Thích ứng Quy định & Thử nghiệm Dry-Run An Toàn
                </h3>
                <p className="text-xs text-slate-500">
                  AI Agent tự động diễn dịch chính sách thành Rule kỹ thuật và chạy thử nghiệm trước khi áp dụng.
                </p>
              </div>

              {/* Policy Selector Dropdown */}
              <div className="flex items-center gap-2 mt-3 sm:mt-0">
                <span className="text-xs font-medium text-slate-600">Chọn chính sách:</span>
                <select
                  value={currentPolicy.id}
                  onChange={(e) => selectPolicy(e.target.value)}
                  className="h-9 rounded-lg border border-[#e2ece8] bg-white px-3 pr-8 text-xs font-semibold text-slate-800 focus:border-[#008b74] focus:outline-none focus:ring-1 focus:ring-[#008b74]"
                >
                  {policiesForDataset.map((pol: PolicyItem) => (
                    <option key={pol.id} value={pol.id}>
                      {pol.title}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            {/* Current Policy Card */}
            <div className="rounded-lg border border-[#e2ece8] bg-slate-50/50 p-4 space-y-4">
              <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3 border-b border-slate-200/60 pb-3">
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-xs font-bold text-[#007460] bg-white px-2 py-0.5 rounded border border-[#bfe7dc]">
                      {currentPolicy.id}
                    </span>
                    <strong className="text-sm font-bold text-slate-900">
                      {currentPolicy.title}
                    </strong>
                  </div>
                  <p className="text-xs text-slate-500">
                    Nguồn văn bản: <span className="font-medium text-slate-700">{currentPolicy.sourceDoc}</span> · Hiệu lực từ: {currentPolicy.effectiveDate}
                  </p>
                </div>

                <div>
                  {currentPolicy.status === 'approved' && (
                    <Badge tone="green" className="text-xs font-bold px-2.5 py-1">
                      ✓ ĐÃ ÁP DỤNG PIPELINE
                    </Badge>
                  )}
                  {currentPolicy.status === 'simulated' && (
                    <Badge tone="blue" className="text-xs font-bold px-2.5 py-1">
                      ● ĐÃ CHẠY THỬ NGHIỆM
                    </Badge>
                  )}
                  {currentPolicy.status === 'rejected' && (
                    <Badge tone="red" className="text-xs font-bold px-2.5 py-1">
                      ✕ ĐÃ TỪ CHỐI
                    </Badge>
                  )}
                  {currentPolicy.status === 'draft' && (
                    <Badge tone="slate" className="text-xs font-bold px-2.5 py-1">
                      BẢN THẢO
                    </Badge>
                  )}
                </div>
              </div>

              {/* AI Analysis Box */}
              <div className="rounded-lg border border-[#bfe7dc] bg-[#f0f9f6] p-3 text-xs space-y-1">
                <span className="font-bold text-[#007460] flex items-center gap-1.5">
                  <Sparkles size={14} /> Diễn giải phân tích từ AI Agent:
                </span>
                <p className="text-slate-700 leading-relaxed font-medium">
                  {currentPolicy.aiAnalysisSummary}
                </p>
              </div>

              {/* Generated Rule Technical Definition */}
              <div className="grid sm:grid-cols-2 gap-4 text-xs">
                <div className="rounded-lg border border-slate-200 bg-white p-3 space-y-1">
                  <span className="text-[11px] font-semibold text-slate-500 uppercase">
                    Quy tắc / Control do AI Agent đề xuất:
                  </span>
                  <p className="font-semibold text-slate-800">{currentPolicy.generatedRule.name}</p>
                  <p className="text-xs text-slate-500">
                    Target Engine: <strong className="text-[#008b74]">{currentPolicy.generatedRule.compiledTarget}</strong>
                  </p>
                </div>

                <div className="rounded-lg border border-slate-200 bg-white p-3 space-y-1">
                  <div className="flex items-center justify-between">
                    <span className="text-[11px] font-semibold text-slate-500 uppercase">
                      Biểu thức Logic Enforce:
                    </span>
                    <button
                      type="button"
                      onClick={() => handleCopy(currentPolicy.generatedRule.expression, 'expr-' + currentPolicy.id)}
                      className="text-slate-400 hover:text-slate-600 text-xs flex items-center gap-1"
                      title="Sao chép biểu thức logic"
                      aria-label="Sao chép biểu thức logic"
                    >
                      {copiedId === 'expr-' + currentPolicy.id ? (
                        <Check size={12} className="text-emerald-600" />
                      ) : (
                        <Copy size={12} />
                      )}
                      <span>Chép</span>
                    </button>
                  </div>
                  <code className="block rounded bg-slate-50 p-2 font-mono text-xs text-[#007460] border border-slate-200 overflow-x-auto">
                    {currentPolicy.generatedRule.expression}
                  </code>
                </div>
              </div>

              {/* Dry-Run Simulation Results Section */}
              <div className="rounded-lg border border-slate-200 bg-white p-4 space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold uppercase tracking-wider text-slate-800 flex items-center gap-2">
                    <Activity size={15} className="text-[#008b74]" />
                    Kết quả thử nghiệm an toàn (Dry-Run Simulation)
                  </span>
                  <span className="text-xs text-slate-500 font-mono">
                    Độ trễ dự kiến: +{currentPolicy.dryRunSimulation.estimatedLatencyMs}ms
                  </span>
                </div>

                <div className="grid grid-cols-3 gap-3">
                  <div className="rounded-md border border-slate-200 bg-slate-50 p-2.5 text-center">
                    <span className="text-[11px] text-slate-500 uppercase font-medium">Dòng quét</span>
                    <strong className="block text-sm font-bold text-slate-900">
                      {currentPolicy.dryRunSimulation.scannedRows.toLocaleString('vi-VN')}
                    </strong>
                  </div>

                  <div className="rounded-md border border-emerald-200 bg-emerald-50/60 p-2.5 text-center">
                    <span className="text-[11px] text-emerald-800 uppercase font-medium">Silver Sạch (Pass)</span>
                    <strong className="block text-sm font-bold text-emerald-800">
                      {currentPolicy.dryRunSimulation.silverCleanRows.toLocaleString('vi-VN')}
                    </strong>
                  </div>

                  <div className="rounded-md border border-rose-200 bg-rose-50/60 p-2.5 text-center">
                    <span className="text-[11px] text-rose-800 uppercase font-medium">Cách ly (Quarantine)</span>
                    <strong className="block text-sm font-bold text-rose-800">
                      {currentPolicy.dryRunSimulation.quarantinedRows}
                    </strong>
                  </div>
                </div>

                {/* Simulation Clean Ratio Bar */}
                <div className="space-y-1 pt-1">
                  <div className="flex justify-between text-xs text-slate-600 font-medium">
                    <span>Tỷ lệ đạt chuẩn Silver: 99.9%</span>
                    <span>Cách ly: {((currentPolicy.dryRunSimulation.quarantinedRows / currentPolicy.dryRunSimulation.scannedRows) * 100).toFixed(2)}%</span>
                  </div>
                  <div className="h-2 w-full rounded-full bg-slate-100 overflow-hidden flex">
                    <div className="h-full bg-[#008b74]" style={{ width: '99.9%' }} />
                    <div className="h-full bg-rose-500" style={{ width: '0.1%' }} />
                  </div>
                </div>
              </div>

              {/* Action Buttons for Admin Decision */}
              <div className="flex flex-col sm:flex-row items-center justify-between gap-3 border-t border-slate-200/60 pt-3">
                <span className="text-xs text-slate-500">
                  {currentPolicy.status === 'approved'
                    ? 'Rule đã được thêm vào catalog và pipeline đang tự động thực thi.'
                    : 'Xem kết quả thử nghiệm trước khi quyết định deploy vào pipeline.'}
                </span>

                <div className="flex items-center gap-2">
                  {currentPolicy.status === 'draft' && (
                    <Button
                      variant="xanhsm"
                      size="sm"
                      onClick={() => handleRunSimulation(currentPolicy.id)}
                      disabled={isSimulatingPolicy}
                      className="text-xs font-semibold gap-1.5"
                    >
                      {isSimulatingPolicy ? (
                        <Loader2 size={13} className="animate-spin" />
                      ) : (
                        <Play size={13} />
                      )}
                      Chạy thử nghiệm Dry-Run
                    </Button>
                  )}

                  {currentPolicy.status === 'simulated' && (
                    <>
                      <Button
                        variant="xanhsm"
                        size="sm"
                        onClick={() => handleApprovePolicyRule(currentPolicy.id)}
                        className="text-xs font-semibold gap-1.5"
                      >
                        <Check size={14} />
                        Duyệt & Áp dụng 1-Click
                      </Button>
                      <Button
                        variant="danger"
                        size="sm"
                        onClick={() => handleRejectPolicyRule(currentPolicy.id)}
                        className="text-xs font-semibold gap-1.5"
                      >
                        <X size={14} />
                        Từ chối đề xuất
                      </Button>
                    </>
                  )}

                  {currentPolicy.status === 'approved' && (
                    <Badge tone="green" className="text-xs font-bold px-3 py-1.5 gap-1.5">
                      <Check size={13} strokeWidth={2.5} /> Đang chạy trong Pipeline sản xuất
                    </Badge>
                  )}

                  {currentPolicy.status === 'rejected' && (
                    <Badge tone="red" className="text-xs font-bold px-3 py-1.5 gap-1.5">
                      <XCircle size={13} /> Đã từ chối áp dụng
                    </Badge>
                  )}
                </div>
              </div>
            </div>
          </Card>

          {/* Section: Active Rules Governance on Current Dataset */}
          <Card className="rounded-xl border-[#e2ece8] bg-white p-5 shadow-xs space-y-4">
            <div className="flex items-center justify-between border-b border-[#f0f4f2] pb-3">
              <div>
                <h3 className="text-base font-bold text-slate-900">
                  Rules đang hoạt động trên bộ dữ liệu {currentDataset.title} ({filteredRules.length} rules)
                </h3>
                <p className="text-xs text-slate-500">
                  Danh sách quy tắc kiểm soát dữ liệu do AI Agent thiết lập và đã được quản trị viên phê duyệt.
                </p>
              </div>
              <Button
                variant="outline"
                size="sm"
                onClick={() => navigate('/rules')}
                className="text-xs text-slate-700"
              >
                Mở trung tâm quản lý Rules <ArrowRight size={13} className="ml-1" />
              </Button>
            </div>

            {filteredRules.length === 0 ? (
              <div className="py-6 text-center text-xs text-slate-500">
                Không tìm thấy quy tắc nào khớp với bộ lọc.
              </div>
            ) : (
              <div className="space-y-3">
                {filteredRules.map((rule: ProposedRule) => {
                  const isApproved = rule.status === 'approved';
                  const isPending = rule.status === 'pending';

                  return (
                    <div
                      key={rule.id}
                      className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 rounded-lg border border-slate-200 bg-slate-50/40 p-3.5 hover:border-[#bfe7dc] transition"
                    >
                      <div className="space-y-1 flex-1 pr-3">
                        <div className="flex flex-wrap items-center gap-2">
                          <strong className="font-mono text-xs font-bold text-slate-900">
                            {rule.name}
                          </strong>
                          <Badge tone={rule.severity === 'CRITICAL' ? 'red' : 'amber'}>
                            {rule.severity}
                          </Badge>
                          <span className="text-xs text-slate-500">· {rule.domain}</span>
                          <span className="text-xs text-slate-500">· Độ tin cậy: {rule.confidence}%</span>
                        </div>
                        <p className="text-xs text-slate-600">{rule.rationale}</p>
                        <div className="flex items-center gap-2 pt-0.5">
                          <code className="text-xs font-mono text-[#007460] bg-white px-2 py-0.5 rounded border border-slate-200">
                            {rule.expression}
                          </code>
                          <button
                            type="button"
                            onClick={() => handleCopy(rule.expression, rule.id)}
                            className="text-slate-400 hover:text-slate-600"
                            title="Sao chép biểu thức"
                            aria-label="Sao chép biểu thức"
                          >
                            {copiedId === rule.id ? (
                              <Check size={12} className="text-emerald-600" />
                            ) : (
                              <Copy size={12} />
                            )}
                          </button>
                        </div>
                      </div>

                      <div className="flex items-center gap-2 shrink-0">
                        {isPending ? (
                          <>
                            <Button
                              variant="xanhsm"
                              size="sm"
                              onClick={() => handleApproveRule(rule.id, rule.name)}
                              className="h-8 px-2.5 text-xs font-semibold gap-1"
                            >
                              <Check size={13} /> Duyệt rule
                            </Button>
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => handleRejectRule(rule.id)}
                              className="h-8 px-2.5 text-xs text-rose-600 hover:bg-rose-50"
                            >
                              Từ chối
                            </Button>
                          </>
                        ) : isApproved ? (
                          <Badge tone="green" className="text-xs font-semibold gap-1">
                            <Check size={12} /> Đang chạy
                          </Badge>
                        ) : (
                          <Badge tone="red" className="text-xs font-semibold">
                            Đã hủy
                          </Badge>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </Card>
        </div>
      )}

      {/* 7. Modal Dialog: Add New Policy (AI Auto-Extraction) */}
      {showAddPolicyModal && (
        <div
          role="dialog"
          aria-modal="true"
          aria-labelledby="add-policy-modal-title"
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/50 backdrop-blur-xs overflow-y-auto"
        >
          <div className="relative w-full max-w-xl rounded-xl border border-[#d2e2dc] bg-white p-6 shadow-2xl animate-in fade-in zoom-in-95 duration-150">
            <div className="flex items-center justify-between border-b border-[#e2ece8] pb-3">
              <div className="flex items-center gap-2">
                <span className="grid size-8 place-items-center rounded-lg bg-[#e6f6f2] text-[#008b74]">
                  <Sparkles size={16} />
                </span>
                <div>
                  <h3 id="add-policy-modal-title" className="text-base font-bold text-slate-900">
                    Thêm Chính Sách & Đề Xuất Rule Bằng AI
                  </h3>
                  <p className="text-xs text-slate-500">
                    AI Agent sẽ trích xuất ràng buộc dữ liệu và tự động sinh Rule kiểm soát cho {currentDataset.title}.
                  </p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setShowAddPolicyModal(false)}
                className="text-slate-400 hover:text-slate-600"
                aria-label="Đóng cửa sổ"
              >
                <X size={18} />
              </button>
            </div>

            <form onSubmit={handleAddNewPolicy} className="mt-4 space-y-4">
              <div>
                <label htmlFor="policy-title-input" className="block text-xs font-semibold text-slate-700 mb-1">
                  Tiêu đề văn bản chính sách / Quy chế <span className="text-rose-500">*</span>
                </label>
                <input
                  id="policy-title-input"
                  type="text"
                  required
                  placeholder="VD: Quy chuẩn giới hạn thời gian mở ca tài xế & kiểm soát an toàn đội xe 2026..."
                  value={newPolicyTitle}
                  onChange={(e) => setNewPolicyTitle(e.target.value)}
                  className="h-10 w-full rounded-lg border border-[#d2e2dc] bg-white px-3 text-xs text-slate-900 focus:border-[#008b74] focus:outline-none focus:ring-1 focus:ring-[#008b74]"
                />
              </div>

              <div>
                <label htmlFor="policy-text-input" className="block text-xs font-semibold text-slate-700 mb-1">
                  Nội dung quy định / Điều khoản pháp lý <span className="text-rose-500">*</span>
                </label>
                <textarea
                  id="policy-text-input"
                  rows={5}
                  required
                  placeholder="Dán nội dung quy định hoặc thông tư vào đây... AI Agent sẽ trích xuất các điều kiện ràng buộc kỹ thuật (constraints) và đề xuất biểu thức logic Enforce phù hợp."
                  value={newPolicyText}
                  onChange={(e) => setNewPolicyText(e.target.value)}
                  className="w-full rounded-lg border border-[#d2e2dc] bg-white p-3 text-xs text-slate-900 focus:border-[#008b74] focus:outline-none focus:ring-1 focus:ring-[#008b74] leading-relaxed"
                />
              </div>

              <div className="flex items-center justify-end gap-3 pt-3 border-t border-slate-100">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => setShowAddPolicyModal(false)}
                  disabled={isAnalyzingNewPolicy}
                  className="text-xs"
                >
                  Hủy
                </Button>
                <Button
                  type="submit"
                  variant="xanhsm"
                  size="sm"
                  disabled={isAnalyzingNewPolicy}
                  className="text-xs font-semibold gap-1.5"
                >
                  {isAnalyzingNewPolicy ? (
                    <>
                      <Loader2 size={13} className="animate-spin" />
                      AI Agent đang phân tích & sinh Rule...
                    </>
                  ) : (
                    <>
                      <Sparkles size={14} />
                      AI Agent: Phân Tích & Sinh Rule
                    </>
                  )}
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Global Inspector Modal for deep dive into Findings */}
      <FindingInspectorModal />

    </div>
  );
}
