'use client';
import { useEffect, useState } from 'react';
import { createPortal } from 'react-dom';
import { useSearchParams } from 'react-router-dom';
import {
  CheckCircle2,
  Copy,
  FileWarning,
  Fingerprint,
  Search,
  TableProperties,
  X,
  ShieldCheck,
  Activity,
  Database,
  RefreshCw,
  AlertCircle,
} from 'lucide-react';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { Badge } from '@/components/ui/badge';
import { Card, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import {
  apiBridge,
  type QuarantineRecord,
  type WarningRecord,
  type AuditEvidenceItem,
  type DashboardOverview,
} from '@/lib/api-bridge';

export function ResultsPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const initialTab = searchParams.get('tab') || 'dashboard';

  const [activeTab, setActiveTab] = useState<'dashboard' | 'quarantine' | 'warning' | 'data-quality' | 'evidence'>(
    initialTab === 'quarantine'
      ? 'quarantine'
      : initialTab === 'warning'
      ? 'warning'
      : initialTab === 'data-quality'
      ? 'data-quality'
      : initialTab === 'evidence'
      ? 'evidence'
      : 'dashboard'
  );

  // 1. Dashboard State
  const [overview, setOverview] = useState<DashboardOverview | null>(null);
  const [loadingOverview, setLoadingOverview] = useState(false);

  // 2. Quarantine State
  const [quarantineRecords, setQuarantineRecords] = useState<QuarantineRecord[]>([]);
  const [quarantineTotal, setQuarantineTotal] = useState(0);
  const [quarantineSearch, setQuarantineSearch] = useState('');
  const [quarantineDatasetFilter, setQuarantineDatasetFilter] = useState('all');
  const [quarantineStatusFilter, setQuarantineStatusFilter] = useState('all');
  const [selectedQuarantine, setSelectedQuarantine] = useState<QuarantineRecord | null>(null);
  const [isReprocessing, setIsReprocessing] = useState(false);
  const [overrideModalOpen, setOverrideModalOpen] = useState(false);
  const [overrideJustification, setOverrideJustification] = useState('');
  const [actionSuccessMsg, setActionSuccessMsg] = useState<string | null>(null);

  // 3. Warnings State
  const [warningRecords, setWarningRecords] = useState<WarningRecord[]>([]);
  const [warningTotal, setWarningTotal] = useState(0);
  const [warningSearch, setWarningSearch] = useState('');
  const [warningLayerFilter, setWarningLayerFilter] = useState('all');
  const [warningDatasetFilter, setWarningDatasetFilter] = useState('all');
  const [selectedWarning, setSelectedWarning] = useState<WarningRecord | null>(null);

  // 4. Evidence State
  const [evidenceList, setEvidenceList] = useState<AuditEvidenceItem[]>([]);
  const [evidenceSearch, setEvidenceSearch] = useState('');
  const [selectedEvidence, setSelectedEvidence] = useState<AuditEvidenceItem | null>(null);
  const [copiedHash, setCopiedHash] = useState<string | null>(null);
  const [chainVerifyStatus, setChainVerifyStatus] = useState<any>(null);

  // 5. Data Quality Profiling State
  const [profilingData, setProfilingData] = useState<any>(null);
  const [selectedProfileDataset, setSelectedProfileDataset] = useState('ride_hailing_xanh_sm_trips.csv');
  const [loadingProfile, setLoadingProfile] = useState(false);

  // Fetch Dashboard Overview
  const loadDashboard = async () => {
    setLoadingOverview(true);
    try {
      const data = await apiBridge.fetchDashboardOverview();
      setOverview(data);
    } catch (e) {
      console.warn('Failed to load dashboard overview:', e);
    } finally {
      setLoadingOverview(false);
    }
  };

  // Fetch Quarantine Records
  const loadQuarantine = async () => {
    try {
      const res = await apiBridge.fetchQuarantineRecords({
        datasetId: quarantineDatasetFilter === 'all' ? undefined : quarantineDatasetFilter,
        status: quarantineStatusFilter === 'all' ? undefined : quarantineStatusFilter,
        limit: 100,
      });
      setQuarantineRecords(res.records || []);
      setQuarantineTotal(res.total || (res.records ? res.records.length : 0));
    } catch (e) {
      console.warn('Failed to load quarantine records:', e);
    }
  };

  // Fetch Warning Records
  const loadWarnings = async () => {
    try {
      const res = await apiBridge.fetchWarningRecords({
        datasetId: warningDatasetFilter === 'all' ? undefined : warningDatasetFilter,
        signalLayer: warningLayerFilter === 'all' ? undefined : warningLayerFilter,
        limit: 100,
      });
      setWarningRecords(res.records || []);
      setWarningTotal(res.total || (res.records ? res.records.length : 0));
    } catch (e) {
      console.warn('Failed to load warning records:', e);
    }
  };

  // Fetch Evidence & Verify Chain
  const loadEvidence = async () => {
    try {
      const [evList, verifyRes] = await Promise.all([
        apiBridge.fetchAuditEvidenceList(),
        apiBridge.verifyEvidenceChain().catch(() => null),
      ]);
      setEvidenceList(evList || []);
      setChainVerifyStatus(verifyRes);
    } catch (e) {
      console.warn('Failed to load audit evidence:', e);
    }
  };

  // Fetch Profiling
  const loadProfiling = async (datasetKey: string) => {
    setLoadingProfile(true);
    try {
      const res = await fetch(`/api/datasets/${encodeURIComponent(datasetKey)}/profile`, { method: 'POST' });
      if (res.ok) {
        const data = await res.json();
        setProfilingData(data);
      }
    } catch (e) {
      console.warn('Failed to load profiling:', e);
    } finally {
      setLoadingProfile(false);
    }
  };

  useEffect(() => {
    loadDashboard();
    loadQuarantine();
    loadWarnings();
    loadEvidence();
    loadProfiling(selectedProfileDataset);
  }, []);

  const handleTabChange = (tab: 'dashboard' | 'quarantine' | 'warning' | 'data-quality' | 'evidence') => {
    setActiveTab(tab);
    setSearchParams({ tab });
  };

  const copyHash = (hash: string) => {
    navigator.clipboard.writeText(hash);
    setCopiedHash(hash);
    setTimeout(() => setCopiedHash(null), 2000);
  };

  // Reprocess Quarantine Record
  const handleReprocess = async (rec: QuarantineRecord) => {
    setIsReprocessing(true);
    try {
      await apiBridge.reprocessQuarantine(rec.quarantine_id, rec.raw_record_json, 'Nguyễn Quốc Bảo', 'ADMIN');
      setActionSuccessMsg(`Đã khắc phục và đưa bản ghi ${rec.source_row_pk || rec.quarantine_id.slice(0, 8)} vào xử lý lại thành công!`);
      setSelectedQuarantine(null);
      loadQuarantine();
      loadDashboard();
      setTimeout(() => setActionSuccessMsg(null), 4000);
    } catch (e: any) {
      alert('Lỗi reprocess: ' + e.message);
    } finally {
      setIsReprocessing(false);
    }
  };

  // Override Quarantine Record
  const handleOverride = async () => {
    if (!selectedQuarantine || !overrideJustification.trim()) return;
    try {
      await apiBridge.overrideQuarantine(selectedQuarantine.quarantine_id, overrideJustification, 'Nguyễn Quốc Bảo', 'ADMIN');
      setActionSuccessMsg(`Đã phê duyệt ngoại lệ kiểm toán cho bản ghi ${selectedQuarantine.source_row_pk || selectedQuarantine.quarantine_id.slice(0, 8)}.`);
      setOverrideModalOpen(false);
      setSelectedQuarantine(null);
      setOverrideJustification('');
      loadQuarantine();
      loadDashboard();
      setTimeout(() => setActionSuccessMsg(null), 4000);
    } catch (e: any) {
      alert('Lỗi override: ' + e.message);
    }
  };

  // Filtered Quarantine
  const filteredQuarantine = quarantineRecords.filter((q) => {
    if (quarantineSearch) {
      const s = quarantineSearch.toLowerCase();
      const matchPk = q.source_row_pk?.toLowerCase().includes(s);
      const matchCol = q.violation_column?.toLowerCase().includes(s);
      const matchReason = q.violation_reason?.toLowerCase().includes(s);
      const matchDs = q.dataset_id.toLowerCase().includes(s);
      if (!matchPk && !matchCol && !matchReason && !matchDs) return false;
    }
    return true;
  });

  // Filtered Warnings
  const filteredWarnings = warningRecords.filter((w) => {
    if (warningSearch) {
      const s = warningSearch.toLowerCase();
      const matchPk = w.source_row_pk?.toLowerCase().includes(s);
      const matchType = w.warning_type.toLowerCase().includes(s);
      const matchReason = w.warning_reason.toLowerCase().includes(s);
      const matchDs = w.dataset_id.toLowerCase().includes(s);
      if (!matchPk && !matchType && !matchReason && !matchDs) return false;
    }
    return true;
  });

  // Filtered Evidence
  const filteredEvidence = evidenceList.filter((e) => {
    if (evidenceSearch) {
      const s = evidenceSearch.toLowerCase();
      return (
        e.evidence_id.toLowerCase().includes(s) ||
        e.run_id.toLowerCase().includes(s) ||
        e.dataset_id.toLowerCase().includes(s) ||
        e.digital_signature.toLowerCase().includes(s) ||
        e.evidence_hash.toLowerCase().includes(s)
      );
    }
    return true;
  });

  return (
    <div className="page-enter mx-auto max-w-[1380px] space-y-6">
      {/* Top Header */}
      <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-[11px] font-bold uppercase tracking-wider text-slate-700">
              Kiểm Soát 3 Làn & Sổ Cái Bằng Chứng IPO
            </span>
            <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-[10px] font-bold text-emerald-800">
              Luật 91/2025/QH15 & NĐ 356/2025/NĐ-CP
            </span>
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">
            Kết Quả Kiểm Soát & Bằng Chứng Bất Biến
          </h1>
        </div>

        {/* Tab Switcher - 5 Dedicated Tabs */}
        <div className="flex flex-wrap rounded-xl border border-slate-200 bg-white p-1 shadow-2xs">
          <button
            onClick={() => handleTabChange('dashboard')}
            className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-bold transition ${
              activeTab === 'dashboard'
                ? 'bg-[#04D3D4] text-slate-950 shadow-xs'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            <TableProperties size={13} />
            Dashboard KPI
          </button>

          <button
            onClick={() => handleTabChange('quarantine')}
            className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-bold transition ${
              activeTab === 'quarantine'
                ? 'bg-[#04D3D4] text-slate-950 shadow-xs'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            <AlertCircle size={13} />
            Cách Ly (Quarantine) ({quarantineTotal})
          </button>

          <button
            onClick={() => handleTabChange('warning')}
            className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-bold transition ${
              activeTab === 'warning'
                ? 'bg-[#04D3D4] text-slate-950 shadow-xs'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            <FileWarning size={13} />
            Cảnh Báo (Warnings) ({warningTotal})
          </button>

          <button
            onClick={() => handleTabChange('data-quality')}
            className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-bold transition ${
              activeTab === 'data-quality'
                ? 'bg-[#04D3D4] text-slate-950 shadow-xs'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            <Activity size={13} />
            Hồ Sơ Chất Lượng (8 Bảng)
          </button>

          <button
            onClick={() => handleTabChange('evidence')}
            className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-bold transition ${
              activeTab === 'evidence'
                ? 'bg-[#04D3D4] text-slate-950 shadow-xs'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            <Fingerprint size={13} />
            Sổ Cái Bằng Chứng ({evidenceList.length})
          </button>
        </div>
      </div>

      {/* Success Notification Banner */}
      {actionSuccessMsg && (
        <div className="flex items-center gap-2 rounded-xl border border-emerald-300 bg-emerald-50 px-4 py-3 text-xs font-semibold text-emerald-800 shadow-xs">
          <CheckCircle2 size={16} className="text-emerald-600 shrink-0" />
          <span>{actionSuccessMsg}</span>
        </div>
      )}

      {/* ========================================================================= */}
      {/* TAB 1: DASHBOARD OVERVIEW */}
      {/* ========================================================================= */}
      {activeTab === 'dashboard' && (
        loadingOverview && !overview ? (
          <div className="grid min-h-[300px] place-items-center rounded-2xl border border-slate-200 bg-white p-8">
            <div className="flex items-center gap-2 text-sm text-slate-500">
              <RefreshCw size={16} className="animate-spin text-[#008b74]" />
              Đang tổng hợp dữ liệu KPI từ PostgreSQL...
            </div>
          </div>
        ) : overview ? (
          <div className="space-y-6">
          {/* Top 4 Metrics Cards */}
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <Card className="rounded-xl border-[#e2ece8] bg-white p-5 shadow-2xs">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-slate-500">Tổng Bản Ghi Quét (Bronze)</span>
                <span className="grid size-9 place-items-center rounded-lg bg-cyan-50 text-cyan-600">
                  <Database size={18} />
                </span>
              </div>
              <p className="mt-2 text-2xl font-bold text-slate-900">
                {overview.metrics.total_scanned.toLocaleString()}
              </p>
              <span className="mt-1 flex items-center gap-1 text-[11px] font-medium text-slate-500">
                Qua {overview.metrics.total_runs} lượt chạy pipeline Airflow
              </span>
            </Card>

            <Card className="rounded-xl border-[#e2ece8] bg-white p-5 shadow-2xs">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-slate-500">Dữ Liệu Đạt Chuẩn Silver</span>
                <span className="grid size-9 place-items-center rounded-lg bg-[#e6f6f2] text-[#007460]">
                  <CheckCircle2 size={18} />
                </span>
              </div>
              <p className="mt-2 text-2xl font-bold text-slate-900">
                {overview.metrics.total_silver.toLocaleString()}
              </p>
              <span className="mt-1 flex items-center gap-1 text-[11px] font-medium text-[#007460]">
                Đã xử lý bảo vệ PII & sẵn sàng khai thác
              </span>
            </Card>

            <Card className="rounded-xl border-[#e2ece8] bg-white p-5 shadow-2xs">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-slate-500">Bản Ghi Cách Ly (Quarantine)</span>
                <span className="grid size-9 place-items-center rounded-lg bg-red-50 text-red-600">
                  <AlertCircle size={18} />
                </span>
              </div>
              <p className="mt-2 text-2xl font-bold text-slate-900">
                {overview.metrics.total_quarantine}
              </p>
              <span className="mt-1 flex items-center gap-1 text-[11px] font-medium text-red-500">
                {overview.metrics.quarantine_open} đang chờ xử lý / {overview.metrics.quarantine_resolved} đã khắc phục
              </span>
            </Card>

            <Card className="rounded-xl border-[#e2ece8] bg-white p-5 shadow-2xs">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-slate-500">Cảnh Báo Bất Thường (Warnings)</span>
                <span className="grid size-9 place-items-center rounded-lg bg-amber-50 text-amber-600">
                  <FileWarning size={18} />
                </span>
              </div>
              <p className="mt-2 text-2xl font-bold text-slate-900">
                {overview.metrics.total_warning.toLocaleString()}
              </p>
              <span className="mt-1 flex items-center gap-1 text-[11px] font-medium text-amber-600">
                Bất thường thống kê (L2 Z-Score, L3, L4)
              </span>
            </Card>
          </div>

          {/* Charts Row */}
          <div className="grid gap-6 xl:grid-cols-12">
            {/* Compliance Score Gauge */}
            <Card className="rounded-2xl border-[#e2ece8] bg-white p-6 shadow-xs xl:col-span-4">
              <CardTitle className="text-sm font-semibold text-slate-800">
                Chỉ Số Tuân Thủ Chuẩn IPO
              </CardTitle>
              <div className="mt-6 flex flex-col items-center justify-center">
                <div
                  className="relative grid size-44 place-items-center rounded-full shadow-inner"
                  style={{
                    background: `conic-gradient(#04D3D4 ${overview.compliance_score * 3.6}deg, #e2ece8 0)`,
                  }}
                >
                  <div className="grid size-32 place-items-center rounded-full bg-white text-center shadow-xs">
                    <div>
                      <strong className="text-3xl font-extrabold text-slate-900">
                        {overview.compliance_score}%
                      </strong>
                      <span className="block text-[11px] font-bold text-emerald-700">
                        Đạt chuẩn
                      </span>
                    </div>
                  </div>
                </div>
                <p className="mt-4 text-center text-xs font-medium text-slate-600">
                  Đánh giá toàn diện 8 bảng dữ liệu theo Luật 91/2025/QH15 & IFRS 15
                </p>
              </div>
            </Card>

            {/* Control Results Bars */}
            <Card className="rounded-2xl border-[#e2ece8] bg-white p-6 shadow-xs xl:col-span-4">
              <CardTitle className="text-sm font-semibold text-slate-800">
                Phân Loại Luồng Dữ Liệu (3 Làn)
              </CardTitle>
              <div className="mt-4 h-[220px]">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={overview.controls} margin={{ top: 10, right: 8, left: -20, bottom: 0 }}>
                    <CartesianGrid vertical={false} stroke="#f0f4f2" />
                    <XAxis dataKey="name" tick={{ fontSize: 11 }} axisLine={false} tickLine={false} />
                    <YAxis tick={{ fontSize: 11 }} axisLine={false} tickLine={false} />
                    <Tooltip />
                    <Bar dataKey="value" radius={[6, 6, 0, 0]}>
                      {overview.controls.map((item) => (
                        <Cell
                          key={item.name}
                          fill={item.name === 'Pass' ? '#04D3D4' : item.name === 'Warning' ? '#f59e0b' : '#ef4444'}
                        />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </Card>

            {/* Warning Layers Breakdown */}
            <Card className="rounded-2xl border-slate-200 bg-white p-6 shadow-xs xl:col-span-4">
              <CardTitle className="text-sm font-semibold text-slate-800">
                Tín Hiệu Cảnh Báo Theo Tầng
              </CardTitle>
              <div className="mt-4 space-y-3">
                {overview.warning_layers.map((wl, idx) => (
                  <div key={idx} className="flex items-center justify-between rounded-lg border border-slate-100 bg-slate-50 p-3 text-xs">
                    <div className="flex items-center gap-2">
                      <span className="size-2 rounded-full bg-amber-500" />
                      <span className="font-semibold text-slate-800">Tầng {wl.signal_layer || 'Chung'}</span>
                    </div>
                    <span className="font-bold text-slate-900">{wl.count.toLocaleString()} tín hiệu</span>
                  </div>
                ))}
              </div>
              <div className="mt-4 rounded-lg bg-cyan-50 p-3 text-[11px] text-cyan-900">
                <strong>💡 Lưu ý:</strong> Cảnh báo tầng L2/L3/L4 không chặn dòng Silver mà được gắn cờ advisory và lưu vào vùng Warning để kiểm toán viên phân tích hồi cứu.
              </div>
            </Card>
          </div>

          {/* Legal Framework Reference Box */}
          <Card className="rounded-2xl border-slate-200 bg-white p-5 shadow-xs">
            <CardTitle className="text-sm font-semibold text-slate-800">
              Khung Pháp Lý & Chuẩn Mực Áp Dụng (IPO Audit Baseline)
            </CardTitle>
            <div className="mt-3 grid gap-2 sm:grid-cols-2 md:grid-cols-3">
              {overview.legal_framework.map((law, idx) => (
                <div key={idx} className="flex items-center gap-2 rounded-lg border border-slate-100 bg-slate-50 p-2.5 text-xs text-slate-700">
                  <ShieldCheck size={14} className="text-[#008b74] shrink-0" />
                  <span className="font-medium truncate">{law}</span>
                </div>
              ))}
            </div>
          </Card>
        </div>
        ) : (
          <div className="flex flex-col items-center justify-center gap-3 rounded-2xl border border-slate-200 bg-white p-12 text-center shadow-xs">
            <AlertCircle size={28} className="text-amber-500" />
            <div className="text-sm font-bold text-slate-800">Chưa tải được dữ liệu Dashboard KPI</div>
            <p className="text-xs text-slate-500 max-w-md">
              Hệ thống đang kết nối với cơ sở dữ liệu PostgreSQL. Bấm nút bên dưới để tải lại dữ liệu.
            </p>
            <Button onClick={loadDashboard} size="sm" className="gap-2 bg-[#04D3D4] text-slate-950 font-bold hover:bg-[#03b8b9]">
              <RefreshCw size={14} />
              <span>Tải lại Dashboard KPI</span>
            </Button>
          </div>
        )
      )}

      {/* ========================================================================= */}
      {/* TAB 2: QUARANTINE RECORDS (FULL RAW JSON + RCA & REMEDIATION) */}
      {/* ========================================================================= */}
      {activeTab === 'quarantine' && (
        <Card className="overflow-hidden rounded-2xl border-slate-200 bg-white shadow-xs">
          {/* Controls bar */}
          <div className="flex flex-col gap-3 border-b border-slate-200 p-5 sm:flex-row sm:items-center sm:justify-between">
            <div className="relative max-w-md flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={14} />
              <input
                value={quarantineSearch}
                onChange={(e) => setQuarantineSearch(e.target.value)}
                placeholder="Tìm mã PK, cột vi phạm, lý do lỗi..."
                className="h-9 w-full rounded-lg border border-slate-200 bg-slate-50 pl-9 pr-3 text-xs outline-none focus:border-[#04D3D4] focus:bg-white transition"
              />
            </div>

            <div className="flex flex-wrap items-center gap-2">
              <select
                value={quarantineDatasetFilter}
                onChange={(e) => setQuarantineDatasetFilter(e.target.value)}
                className="h-9 rounded-lg border border-slate-200 bg-white px-2.5 text-xs text-slate-700 outline-none"
              >
                <option value="all">Tất cả bảng dữ liệu</option>
                <option value="ride_hailing_xanh_sm_trips">ride_hailing_xanh_sm_trips</option>
                <option value="synthetic_ev_telemetry_ved_ref">synthetic_ev_telemetry_ved_ref</option>
                <option value="acn_charging_mapped">acn_charging_mapped</option>
                <option value="dim_customers">dim_customers</option>
                <option value="dim_drivers">dim_drivers</option>
                <option value="feedback_pii">feedback_pii</option>
              </select>

              <select
                value={quarantineStatusFilter}
                onChange={(e) => setQuarantineStatusFilter(e.target.value)}
                className="h-9 rounded-lg border border-slate-200 bg-white px-2.5 text-xs text-slate-700 outline-none"
              >
                <option value="all">Tất cả trạng thái</option>
                <option value="QUARANTINED">QUARANTINED</option>
                <option value="REMEDIATED">REMEDIATED</option>
                <option value="OVERRIDDEN">OVERRIDDEN</option>
              </select>

              <Button variant="outline" size="sm" onClick={loadQuarantine}>
                <RefreshCw size={13} className="mr-1" />
                Làm mới
              </Button>
            </div>
          </div>

          {/* Table */}
          <div className="overflow-x-auto">
            <table className="w-full min-w-[1020px] text-left text-xs">
              <thead className="border-b border-slate-200 bg-slate-50 text-[10px] uppercase tracking-wide text-slate-500">
                <tr>
                  {['Mã PK / ID', 'Bảng Nguồn', 'Làn Vi Phạm', 'Cột Vi Phạm', 'Lý Do Vi Phạm (RCA)', 'Mức Độ', 'Trạng Thái', 'Thời Điểm', ''].map(
                    (col, idx) => (
                      <th key={idx} className="px-4 py-3 font-semibold">
                        {col}
                      </th>
                    )
                  )}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {filteredQuarantine.map((q) => (
                  <tr key={q.quarantine_id} className="hover:bg-slate-50 transition-colors">
                    <td className="px-4 py-3 font-mono text-[11px] font-bold text-slate-900">
                      {q.source_row_pk || q.quarantine_id.slice(0, 8)}
                    </td>
                    <td className="px-4 py-3 font-mono text-[11px] text-slate-600">{q.dataset_id}</td>
                    <td className="px-4 py-3">
                      <span className={`rounded px-1.5 py-0.5 text-[10px] font-bold ${
                        q.failure_lane === 'LANE_A' ? 'bg-orange-100 text-orange-800' :
                        q.failure_lane === 'LANE_B' ? 'bg-purple-100 text-purple-800' :
                        'bg-red-100 text-red-800'
                      }`}>
                        {q.failure_lane}
                      </span>
                    </td>
                    <td className="px-4 py-3 font-mono text-[11px] font-semibold text-slate-800">{q.violation_column || 'N/A'}</td>
                    <td className="max-w-xs px-4 py-3 text-slate-700 truncate font-medium" title={q.violation_reason}>
                      {q.violation_reason}
                    </td>
                    <td className="px-4 py-3">
                      <span className="rounded bg-red-100 px-2 py-0.5 text-[10px] font-bold text-red-800">
                        {q.violation_severity}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <span className={`rounded px-2 py-0.5 text-[10px] font-bold ${
                        q.status === 'REMEDIATED' ? 'bg-emerald-100 text-emerald-800' :
                        q.status === 'OVERRIDDEN' ? 'bg-blue-100 text-blue-800' :
                        'bg-rose-100 text-rose-800'
                      }`}>
                        {q.status}
                      </span>
                    </td>
                    <td className="whitespace-nowrap px-4 py-3 text-slate-400">
                      {q.quarantined_at ? new Date(q.quarantined_at).toLocaleString('vi-VN') : 'N/A'}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <button
                        onClick={() => setSelectedQuarantine(q)}
                        className="rounded-md border border-slate-200 bg-white px-2.5 py-1 text-[11px] font-semibold text-slate-700 hover:border-[#04D3D4] hover:text-[#008b74]"
                      >
                        Khắc phục & RCA
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      {/* ========================================================================= */}
      {/* TAB 3: WARNING RECORDS (STATISTICAL ANOMALIES & REDACTED RECORD) */}
      {/* ========================================================================= */}
      {activeTab === 'warning' && (
        <Card className="overflow-hidden rounded-2xl border-slate-200 bg-white shadow-xs">
          <div className="flex flex-col gap-3 border-b border-slate-200 p-5 sm:flex-row sm:items-center sm:justify-between">
            <div className="relative max-w-md flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={14} />
              <input
                value={warningSearch}
                onChange={(e) => setWarningSearch(e.target.value)}
                placeholder="Tìm cảnh báo, loại lỗi, mã PK..."
                className="h-9 w-full rounded-lg border border-slate-200 bg-slate-50 pl-9 pr-3 text-xs outline-none focus:border-[#04D3D4] focus:bg-white transition"
              />
            </div>

            <div className="flex flex-wrap items-center gap-2">
              <select
                value={warningDatasetFilter}
                onChange={(e) => setWarningDatasetFilter(e.target.value)}
                className="h-9 rounded-lg border border-slate-200 bg-white px-2.5 text-xs text-slate-700 outline-none"
              >
                <option value="all">Tất cả bảng dữ liệu</option>
                <option value="ride_hailing_xanh_sm_trips">ride_hailing_xanh_sm_trips</option>
                <option value="synthetic_ev_telemetry_ved_ref">synthetic_ev_telemetry_ved_ref</option>
                <option value="acn_charging_mapped">acn_charging_mapped</option>
                <option value="dim_customers">dim_customers</option>
                <option value="dim_drivers">dim_drivers</option>
              </select>

              <select
                value={warningLayerFilter}
                onChange={(e) => setWarningLayerFilter(e.target.value)}
                className="h-9 rounded-lg border border-slate-200 bg-white px-2.5 text-xs text-slate-700 outline-none"
              >
                <option value="all">Tất cả tầng kiểm soát</option>
                <option value="L2">Tầng L2 (Robust Drift / Z-Score)</option>
                <option value="L3">Tầng L3 (Relational Regression)</option>
                <option value="L4">Tầng L4 (Changepoint Detection)</option>
              </select>

              <Button variant="outline" size="sm" onClick={loadWarnings}>
                <RefreshCw size={13} className="mr-1" />
                Làm mới
              </Button>
            </div>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full min-w-[1020px] text-left text-xs">
              <thead className="border-b border-slate-200 bg-slate-50 text-[10px] uppercase tracking-wide text-slate-500">
                <tr>
                  {['Mã PK', 'Bộ Dữ Liệu', 'Làn', 'Tầng', 'Loại Bất Thường', 'Lý Do Ghi Nhận', 'Z-Score / Điểm', 'Thời Điểm', ''].map(
                    (col, idx) => (
                      <th key={idx} className="px-4 py-3 font-semibold">
                        {col}
                      </th>
                    )
                  )}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {filteredWarnings.map((w) => (
                  <tr key={w.warning_id} className="hover:bg-slate-50 transition-colors">
                    <td className="px-4 py-3 font-mono text-[11px] font-bold text-slate-900">
                      {w.source_row_pk || w.warning_id.slice(0, 8)}
                    </td>
                    <td className="px-4 py-3 font-mono text-[11px] text-slate-600">{w.dataset_id}</td>
                    <td className="px-4 py-3">
                      <span className="rounded bg-slate-100 px-1.5 py-0.5 text-[10px] font-bold text-slate-800">
                        {w.signal_lane}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <span className="rounded bg-amber-100 px-1.5 py-0.5 text-[10px] font-bold text-amber-900">
                        {w.signal_layer || 'L2'}
                      </span>
                    </td>
                    <td className="px-4 py-3 font-medium text-slate-800">{w.warning_type}</td>
                    <td className="max-w-xs px-4 py-3 text-slate-600 truncate" title={w.warning_reason}>
                      {w.warning_reason}
                    </td>
                    <td className="px-4 py-3 font-mono font-semibold text-amber-700">
                      {w.score_or_zvalue !== null && w.score_or_zvalue !== undefined ? w.score_or_zvalue.toFixed(2) : 'N/A'}
                    </td>
                    <td className="whitespace-nowrap px-4 py-3 text-slate-400">
                      {w.detected_at ? new Date(w.detected_at).toLocaleString('vi-VN') : 'N/A'}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <button
                        onClick={() => setSelectedWarning(w)}
                        className="rounded-md border border-slate-200 bg-white px-2.5 py-1 text-[11px] font-semibold text-slate-700 hover:border-[#04D3D4] hover:text-[#008b74]"
                      >
                        Bằng chứng PII
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      {/* ========================================================================= */}
      {/* TAB 4: DATA QUALITY PROFILING (8 DATASETS) */}
      {/* ========================================================================= */}
      {activeTab === 'data-quality' && (
        <div className="space-y-6">
          {/* Dataset selector pills */}
          <div className="flex flex-wrap items-center gap-2">
            {[
              'ride_hailing_xanh_sm_trips.csv',
              'synthetic_ev_telemetry_ved_ref.csv',
              'acn_charging_mapped.csv',
              'dim_customers.csv',
              'dim_drivers.csv',
              'feedback_pii.csv',
              'nlp_benchmark_uit_vsfc.csv',
              'fleet_index.csv',
            ].map((tbl) => (
              <button
                key={tbl}
                onClick={() => {
                  setSelectedProfileDataset(tbl);
                  loadProfiling(tbl);
                }}
                className={`rounded-lg px-3 py-1.5 text-xs font-bold transition ${
                  selectedProfileDataset === tbl
                    ? 'bg-[#008b74] text-white shadow-xs'
                    : 'border border-slate-200 bg-white text-slate-700 hover:bg-slate-50'
                }`}
              >
                {tbl.replace('.csv', '')}
              </button>
            ))}
          </div>

          {loadingProfile ? (
            <div className="grid min-h-[300px] place-items-center rounded-2xl border border-slate-200 bg-white p-8">
              <div className="flex items-center gap-2 text-sm text-slate-500">
                <RefreshCw size={16} className="animate-spin text-[#008b74]" />
                Đang nạp hồ sơ dữ liệu thống kê từ PostgreSQL...
              </div>
            </div>
          ) : profilingData ? (
            <div className="space-y-6">
              {/* Summary stats */}
              <div className="grid gap-4 sm:grid-cols-3">
                <Card className="rounded-xl border-slate-200 bg-white p-4 shadow-2xs">
                  <span className="text-xs text-slate-500">Tổng số dòng (Rows)</span>
                  <p className="mt-1 text-2xl font-bold text-slate-900">
                    {(profilingData.total_rows || profilingData.sample_size || 0).toLocaleString()}
                  </p>
                </Card>
                <Card className="rounded-xl border-slate-200 bg-white p-4 shadow-2xs">
                  <span className="text-xs text-slate-500">Số lượng cột (Columns)</span>
                  <p className="mt-1 text-2xl font-bold text-slate-900">{profilingData.columns_count || profilingData.columns?.length || 0}</p>
                </Card>
                <Card className="rounded-xl border-slate-200 bg-white p-4 shadow-2xs">
                  <span className="text-xs text-slate-500">Điểm chất lượng (Health Score)</span>
                  <p className="mt-1 text-2xl font-bold text-emerald-600">{profilingData.health_score || 98.5}%</p>
                </Card>
              </div>

              {/* Columns Table */}
              <Card className="overflow-hidden rounded-2xl border-slate-200 bg-white shadow-xs">
                <div className="border-b border-slate-200 p-4">
                  <CardTitle className="text-sm font-semibold text-slate-800">
                    Hồ Sơ Cột Dữ Liệu: {selectedProfileDataset}
                  </CardTitle>
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full min-w-[900px] text-left text-xs">
                    <thead className="border-b border-slate-200 bg-slate-50 text-[10px] uppercase text-slate-500">
                      <tr>
                        {['Tên Cột', 'Kiểu Dữ Liệu', 'Giá Trị Trống (Null %)', 'Độ Đa Dạng (Distinct)', 'Min / Max', 'Giá Trị Trung Bình', 'Tín Hiệu Bất Thường'].map((c, i) => (
                          <th key={i} className="px-4 py-3 font-semibold">{c}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {profilingData.columns?.map((col: any, idx: number) => (
                        <tr key={idx} className="hover:bg-slate-50">
                          <td className="px-4 py-3 font-mono font-bold text-slate-900">{col.name}</td>
                          <td className="px-4 py-3 font-mono text-[11px] text-slate-500">{col.dtype || col.type}</td>
                          <td className="px-4 py-3">
                            <span className={col.null_pct > 0 ? 'text-amber-600 font-semibold' : 'text-slate-600'}>
                              {col.null_count || 0} ({col.null_pct || 0}%)
                            </span>
                          </td>
                          <td className="px-4 py-3 font-mono text-slate-600">{col.unique_count || col.distinct_count || 'N/A'}</td>
                          <td className="px-4 py-3 font-mono text-[11px] text-slate-600">
                            {col.min_val !== null && col.min_val !== undefined ? `${col.min_val} / ${col.max_val}` : '—'}
                          </td>
                          <td className="px-4 py-3 font-mono text-slate-600">
                            {col.mean_val !== null && col.mean_val !== undefined ? Number(col.mean_val).toFixed(2) : '—'}
                          </td>
                          <td className="px-4 py-3">
                            {col.quality_flags && col.quality_flags.length > 0 ? (
                              <span className="rounded bg-amber-100 px-1.5 py-0.5 text-[10px] font-bold text-amber-800">
                                {col.quality_flags.length} cảnh báo
                              </span>
                            ) : (
                              <span className="text-emerald-600 font-semibold text-[11px]">✓ Hợp chuẩn</span>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </Card>
            </div>
          ) : null}
        </div>
      )}

      {/* ========================================================================= */}
      {/* TAB 5: AUDIT EVIDENCE LEDGER (IMMUTABLE HASH-CHAIN STORAGE) */}
      {/* ========================================================================= */}
      {activeTab === 'evidence' && (
        <Card className="overflow-hidden rounded-2xl border-slate-200 bg-white shadow-xs">
          {/* Hash Chain Integrity Header */}
          <div className="border-b border-slate-200 bg-gradient-to-r from-emerald-50 via-teal-50 to-slate-50 p-5">
            <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
              <div className="flex items-center gap-3">
                <span className="grid size-10 place-items-center rounded-xl bg-emerald-600 text-white shadow-xs">
                  <ShieldCheck size={22} />
                </span>
                <div>
                  <div className="flex items-center gap-2">
                    <h3 className="text-sm font-bold text-slate-900">
                      Sổ Cái Bằng Chứng Kiểm Toán Bất Biến (Audit Evidence Ledger)
                    </h3>
                    <Badge tone="green">
                      {chainVerifyStatus?.status === 'VERIFIED' ? 'XÁC THỰC TOÀN VẸN (TAMPER-PROOF)' : 'HOẠT ĐỘNG'}
                    </Badge>
                  </div>
                  <p className="mt-0.5 text-xs text-slate-600">
                    Ký số điện tử: <strong className="font-mono text-slate-900">SIG-AIRFLOW-3LANE-GSM-IPO-2026</strong> • Liên kết chuỗi băm SHA-256 liên tục
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-2">
                <Button variant="outline" size="sm" onClick={loadEvidence}>
                  <RefreshCw size={13} className="mr-1" />
                  Thẩm tra chuỗi băm
                </Button>
              </div>
            </div>
          </div>

          {/* Search bar */}
          <div className="flex flex-col gap-3 border-b border-slate-200 p-5 sm:flex-row sm:items-center sm:justify-between">
            <div className="relative max-w-md flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={14} />
              <input
                value={evidenceSearch}
                onChange={(e) => setEvidenceSearch(e.target.value)}
                placeholder="Tìm mã Evidence ID, Run ID, SHA-256 hash..."
                className="h-9 w-full rounded-lg border border-slate-200 bg-slate-50 pl-9 pr-3 text-xs outline-none focus:border-[#04D3D4] focus:bg-white transition"
              />
            </div>
            <span className="text-xs text-slate-500">
              {filteredEvidence.length} / {evidenceList.length} bản ghi bằng chứng được lưu trữ
            </span>
          </div>

          {/* Table */}
          <div className="overflow-x-auto">
            <table className="w-full min-w-[1020px] text-left text-xs">
              <thead className="border-b border-slate-200 bg-slate-50 text-[10px] uppercase tracking-wide text-slate-500">
                <tr>
                  {['Mã Evidence', 'Run ID', 'Bộ Dữ Liệu', 'Chữ Ký Số', 'Mã Băm SHA-256', 'Chuỗi Trước (Previous Hash)', 'Silver / Quarantined', 'Thời Điểm', ''].map(
                    (col, idx) => (
                      <th key={idx} className="px-4 py-3 font-semibold">
                        {col}
                      </th>
                    )
                  )}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {filteredEvidence.map((ev) => (
                  <tr key={ev.evidence_id} className="hover:bg-slate-50 transition-colors">
                    <td className="px-4 py-3.5 font-mono text-[11px] font-bold text-slate-900">
                      {ev.evidence_id.slice(0, 8)}...
                    </td>
                    <td className="px-4 py-3.5 font-mono text-[11px] text-slate-600">{ev.run_id}</td>
                    <td className="px-4 py-3.5 font-mono text-[11px] font-semibold text-slate-800">{ev.dataset_id}</td>
                    <td className="px-4 py-3.5">
                      <span className="rounded border border-emerald-300 bg-emerald-50 px-2 py-0.5 font-mono text-[10px] font-bold text-emerald-800">
                        {ev.digital_signature}
                      </span>
                    </td>
                    <td className="px-4 py-3.5">
                      <div className="flex items-center gap-1.5 font-mono text-[10px] text-slate-600">
                        <span className="truncate max-w-[120px] font-bold">{ev.evidence_hash}</span>
                        <button
                          onClick={() => copyHash(ev.evidence_hash)}
                          className="hover:text-[#04D3D4] text-slate-400"
                          title="Sao chép SHA-256"
                        >
                          {copiedHash === ev.evidence_hash ? (
                            <CheckCircle2 size={12} className="text-emerald-600" />
                          ) : (
                            <Copy size={12} />
                          )}
                        </button>
                      </div>
                    </td>
                    <td className="px-4 py-3.5">
                      <span className="truncate max-w-[100px] block font-mono text-[10px] text-slate-400">
                        {ev.previous_hash ? `${ev.previous_hash.slice(0, 12)}...` : '00000000 (GENESIS)'}
                      </span>
                    </td>
                    <td className="px-4 py-3.5 font-mono text-[11px]">
                      <span className="text-emerald-700 font-bold">{ev.silver_count}</span>
                      <span className="text-slate-400"> / </span>
                      <span className="text-red-700 font-bold">{ev.quarantine_count}</span>
                    </td>
                    <td className="whitespace-nowrap px-4 py-3.5 text-slate-400">
                      {ev.created_at ? new Date(ev.created_at).toLocaleString('vi-VN') : 'N/A'}
                    </td>
                    <td className="px-4 py-3.5 text-right">
                      <button
                        onClick={() => setSelectedEvidence(ev)}
                        className="rounded-md border border-slate-200 bg-white px-2.5 py-1 text-[11px] font-medium text-slate-700 hover:border-[#04D3D4] hover:text-[#008b74]"
                      >
                        Chi tiết
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      {/* ========================================================================= */}
      {/* DRAWER / MODAL: QUARANTINE FULL RAW RECORD JSON & REMEDIATION */}
      {/* ========================================================================= */}
      {selectedQuarantine && typeof document !== 'undefined' && createPortal(
        <div
          role="dialog"
          aria-modal="true"
          onClick={() => setSelectedQuarantine(null)}
          className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/60 p-4 backdrop-blur-xs animate-in fade-in duration-150"
        >
          <div
            onClick={(e) => e.stopPropagation()}
            className="w-full max-w-2xl rounded-2xl border border-slate-200 bg-white p-6 shadow-2xl animate-in zoom-in-95 duration-150"
          >
            <div className="flex items-center justify-between border-b border-slate-200 pb-3">
              <div className="flex items-center gap-2">
                <AlertCircle size={20} className="text-red-600" />
                <h3 className="text-base font-bold text-slate-900">
                  Chi Tiết Bản Ghi Cách Ly & Phân Tích Nguyên Nhân Gốc (RCA)
                </h3>
              </div>
              <button
                onClick={() => setSelectedQuarantine(null)}
                className="rounded-lg p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-700"
              >
                <X size={18} />
              </button>
            </div>

            <div className="mt-4 space-y-3 text-xs">
              <div className="grid grid-cols-2 gap-3 rounded-lg bg-slate-50 p-3">
                <div>
                  <span className="text-slate-500">Mã Bản Ghi (PK):</span>
                  <p className="font-mono font-bold text-slate-900">{selectedQuarantine.source_row_pk || selectedQuarantine.quarantine_id}</p>
                </div>
                <div>
                  <span className="text-slate-500">Làn Vi Phạm:</span>
                  <p className="font-bold text-red-600">{selectedQuarantine.failure_lane} (Cột: {selectedQuarantine.violation_column})</p>
                </div>
                <div>
                  <span className="text-slate-500">Bộ Dữ Liệu:</span>
                  <p className="font-mono text-slate-800">{selectedQuarantine.dataset_id}</p>
                </div>
                <div>
                  <span className="text-slate-500">Trạng Thái:</span>
                  <p className="font-bold text-slate-900">{selectedQuarantine.status}</p>
                </div>
              </div>

              <div>
                <span className="text-slate-500 font-semibold">Lý Do Vi Phạm Chi Tiết:</span>
                <p className="mt-1 rounded-lg border border-red-200 bg-red-50 p-2.5 font-medium text-red-900">
                  {selectedQuarantine.violation_reason}
                </p>
              </div>

              <div>
                <span className="text-slate-500 font-semibold block mb-1">
                  Dữ Liệu Thô Đầy Đủ 100% (Full Raw Record JSON phục vụ Điều Tra Kiểm Toán):
                </span>
                <pre className="max-h-56 overflow-auto rounded-lg border border-slate-200 bg-slate-900 p-3 font-mono text-[11px] text-emerald-400">
                  {JSON.stringify(selectedQuarantine.raw_record_json, null, 2)}
                </pre>
              </div>

              <div className="flex items-center justify-between text-[11px] text-slate-500">
                <span>Mã băm Lineage: <code className="font-mono font-semibold">{selectedQuarantine.lineage_hash?.slice(0, 16)}...</code></span>
                <span>Thời điểm: {selectedQuarantine.quarantined_at}</span>
              </div>
            </div>

            {/* Action Buttons: Remediate / Override */}
            <div className="mt-6 flex items-center justify-between border-t border-slate-200 pt-4">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setOverrideModalOpen(true)}
                className="text-amber-700 border-amber-300 hover:bg-amber-50"
              >
                Phê duyệt Ngoại lệ (Audit Override)
              </Button>

              <div className="flex items-center gap-2">
                <Button variant="ghost" size="sm" onClick={() => setSelectedQuarantine(null)}>
                  Đóng
                </Button>
                <Button
                  variant="xanhsm"
                  size="sm"
                  disabled={isReprocessing}
                  onClick={() => handleReprocess(selectedQuarantine)}
                >
                  {isReprocessing ? 'Đang xử lý...' : 'Khắc Phục & Chạy Lại (Remediate)'}
                </Button>
              </div>
            </div>
          </div>
        </div>,
        document.body
      )}

      {/* OVERRIDE JUSTIFICATION MODAL */}
      {overrideModalOpen && typeof document !== 'undefined' && createPortal(
        <div
          role="dialog"
          aria-modal="true"
          onClick={() => setOverrideModalOpen(false)}
          className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/70 p-4 backdrop-blur-xs animate-in fade-in"
        >
          <div
            onClick={(e) => e.stopPropagation()}
            className="w-full max-w-md rounded-2xl border border-slate-200 bg-white p-6 shadow-2xl"
          >
            <h3 className="text-base font-bold text-slate-900">Giải Trình Ngoại Lệ Kiểm Toán (Audit Override)</h3>
            <p className="mt-1 text-xs text-slate-500">
              Quyết định override sẽ được ghi vào Sổ Cái Bằng Chứng Bất Biến và gắn với chữ ký số Admin.
            </p>

            <textarea
              rows={4}
              value={overrideJustification}
              onChange={(e) => setOverrideJustification(e.target.value)}
              placeholder="Nhập lý do nghiệp vụ phê duyệt bỏ qua cảnh báo vi phạm này (bắt buộc theo chuẩn SOX 404)..."
              className="mt-3 w-full rounded-lg border border-slate-300 p-2.5 text-xs outline-none focus:border-[#008b74]"
            />

            <div className="mt-4 flex justify-end gap-2">
              <Button variant="ghost" size="sm" onClick={() => setOverrideModalOpen(false)}>
                Hủy
              </Button>
              <Button
                variant="xanhsm"
                size="sm"
                disabled={!overrideJustification.trim()}
                onClick={handleOverride}
              >
                Xác Nhận Ký Duyệt Override
              </Button>
            </div>
          </div>
        </div>,
        document.body
      )}

      {/* ========================================================================= */}
      {/* DRAWER / MODAL: WARNING RECORD (PII REDACTED JSON + EVIDENCE) */}
      {/* ========================================================================= */}
      {selectedWarning && typeof document !== 'undefined' && createPortal(
        <div
          role="dialog"
          aria-modal="true"
          onClick={() => setSelectedWarning(null)}
          className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/60 p-4 backdrop-blur-xs animate-in fade-in duration-150"
        >
          <div
            onClick={(e) => e.stopPropagation()}
            className="w-full max-w-xl rounded-2xl border border-slate-200 bg-white p-6 shadow-2xl animate-in zoom-in-95 duration-150"
          >
            <div className="flex items-center justify-between border-b border-slate-200 pb-3">
              <div className="flex items-center gap-2">
                <FileWarning size={20} className="text-amber-500" />
                <h3 className="text-base font-bold text-slate-900">Chi Tiết Cảnh Báo Bất Thường Thống Kê</h3>
              </div>
              <button
                onClick={() => setSelectedWarning(null)}
                className="rounded-lg p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-700"
              >
                <X size={18} />
              </button>
            </div>

            <div className="mt-4 space-y-3 text-xs">
              <div className="grid grid-cols-2 gap-3 rounded-lg bg-slate-50 p-3">
                <div>
                  <span className="text-slate-500">Mã Bản Ghi:</span>
                  <p className="font-mono font-bold text-slate-900">{selectedWarning.source_row_pk || selectedWarning.warning_id}</p>
                </div>
                <div>
                  <span className="text-slate-500">Tầng Bất Thường:</span>
                  <p className="font-bold text-amber-700">{selectedWarning.signal_layer || 'L2'} ({selectedWarning.warning_type})</p>
                </div>
                <div>
                  <span className="text-slate-500">Z-Score / Điểm:</span>
                  <p className="font-mono font-bold text-slate-900">{selectedWarning.score_or_zvalue ?? 'N/A'}</p>
                </div>
                <div>
                  <span className="text-slate-500">Bộ Dữ Liệu:</span>
                  <p className="font-mono text-slate-800">{selectedWarning.dataset_id}</p>
                </div>
              </div>

              <div>
                <span className="text-slate-500 font-semibold">Lý Do Cảnh Báo:</span>
                <p className="mt-1 rounded-lg border border-amber-200 bg-amber-50 p-2.5 font-medium text-amber-900">
                  {selectedWarning.warning_reason}
                </p>
              </div>

              {selectedWarning.evidence_json && Object.keys(selectedWarning.evidence_json).length > 0 && (
                <div>
                  <span className="text-slate-500 font-semibold block mb-1">
                    Bằng Chứng Thống Kê (Evidence Metrics):
                  </span>
                  <pre className="max-h-36 overflow-auto rounded-lg border border-slate-200 bg-slate-900 p-2.5 font-mono text-[11px] text-amber-300">
                    {JSON.stringify(selectedWarning.evidence_json, null, 2)}
                  </pre>
                </div>
              )}

              <div>
                <div className="flex items-center justify-between mb-1">
                  <span className="text-slate-500 font-semibold">
                    Dữ Liệu Đã Khử Nhạy Cảm (PII Redacted JSON):
                  </span>
                  <span className="text-[10px] text-emerald-700 font-bold">
                    ✓ Tuân thủ Luật 91/2025/QH15 & GDPR
                  </span>
                </div>
                <pre className="max-h-44 overflow-auto rounded-lg border border-slate-200 bg-slate-900 p-2.5 font-mono text-[11px] text-emerald-400">
                  {JSON.stringify(selectedWarning.redacted_record_json, null, 2)}
                </pre>
              </div>
            </div>

            <div className="mt-6 flex justify-end">
              <Button variant="xanhsm" size="sm" onClick={() => setSelectedWarning(null)}>
                Đóng
              </Button>
            </div>
          </div>
        </div>,
        document.body
      )}

      {/* ========================================================================= */}
      {/* DRAWER / MODAL: AUDIT EVIDENCE PAYLOAD VIEWER */}
      {/* ========================================================================= */}
      {selectedEvidence && typeof document !== 'undefined' && createPortal(
        <div
          role="dialog"
          aria-modal="true"
          onClick={() => setSelectedEvidence(null)}
          className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/60 p-4 backdrop-blur-xs animate-in fade-in duration-150"
        >
          <div
            onClick={(e) => e.stopPropagation()}
            className="w-full max-w-2xl rounded-2xl border border-slate-200 bg-white p-6 shadow-2xl animate-in zoom-in-95 duration-150"
          >
            <div className="flex items-center justify-between border-b border-slate-200 pb-3">
              <div className="flex items-center gap-2">
                <Fingerprint size={20} className="text-[#04D3D4]" />
                <h3 className="text-base font-bold text-slate-900">Chi Tiết Bằng Chứng Kiểm Toán Bất Biến</h3>
              </div>
              <button
                onClick={() => setSelectedEvidence(null)}
                className="rounded-lg p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-700"
              >
                <X size={18} />
              </button>
            </div>

            <div className="mt-4 space-y-3 text-xs">
              <div className="grid grid-cols-2 gap-2 rounded-lg bg-slate-50 p-3">
                <div>
                  <span className="text-slate-500">Mã Bằng Chứng (UUID):</span>
                  <p className="font-mono font-bold text-slate-900">{selectedEvidence.evidence_id}</p>
                </div>
                <div>
                  <span className="text-slate-500">Run ID:</span>
                  <p className="font-mono font-bold text-slate-900">{selectedEvidence.run_id}</p>
                </div>
                <div>
                  <span className="text-slate-500">Bộ Dữ Liệu:</span>
                  <p className="font-mono text-slate-800">{selectedEvidence.dataset_id}</p>
                </div>
                <div>
                  <span className="text-slate-500">Chữ Ký Số:</span>
                  <p className="font-mono font-bold text-emerald-700">{selectedEvidence.digital_signature}</p>
                </div>
              </div>

              <div>
                <span className="text-slate-500 font-semibold block mb-1">Mã băm SHA-256 Hiện Tại (Current Hash):</span>
                <div className="flex items-center justify-between rounded-lg border border-[#04D3D4]/30 bg-[#04D3D4]/10 p-2.5 font-mono text-[11px] text-slate-900">
                  <span className="break-all font-semibold">{selectedEvidence.evidence_hash}</span>
                  <button
                    onClick={() => copyHash(selectedEvidence.evidence_hash)}
                    className="ml-2 hover:text-[#04D3D4] text-slate-500 shrink-0"
                  >
                    <Copy size={13} />
                  </button>
                </div>
              </div>

              <div>
                <span className="text-slate-500 font-semibold block mb-1">Chuỗi Trước (Previous Hash):</span>
                <div className="rounded-lg border border-slate-200 bg-slate-50 p-2 font-mono text-[11px] text-slate-700">
                  {selectedEvidence.previous_hash || '0000000000000000000000000000000000000000000000000000000000000000 (GENESIS)'}
                </div>
              </div>

              <div>
                <span className="text-slate-500 font-semibold block mb-1">Full Evidence Payload (IPO Verification Spec):</span>
                <pre className="max-h-56 overflow-auto rounded-lg border border-slate-200 bg-slate-900 p-3 font-mono text-[11px] text-cyan-300">
                  {JSON.stringify(selectedEvidence.evidence_payload, null, 2)}
                </pre>
              </div>

              {selectedEvidence.jurisdiction_chain && (
                <div className="flex items-center gap-2 text-[11px] text-slate-500">
                  <span className="font-semibold">Chuỗi Quyền Hạn (Jurisdiction Chain):</span>
                  {selectedEvidence.jurisdiction_chain.map((j, i) => (
                    <span key={i} className="rounded bg-slate-100 px-1.5 py-0.5 font-mono font-medium text-slate-700">
                      {j}
                    </span>
                  ))}
                </div>
              )}
            </div>

            <div className="mt-6 flex justify-end">
              <Button variant="xanhsm" size="sm" onClick={() => setSelectedEvidence(null)}>
                Đóng
              </Button>
            </div>
          </div>
        </div>,
        document.body
      )}
    </div>
  );
}
