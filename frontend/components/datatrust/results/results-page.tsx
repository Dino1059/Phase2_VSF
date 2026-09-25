'use client';
import { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  AlertTriangle,
  ArrowDownRight,
  ArrowUpRight,
  CheckCircle2,
  Clock3,
  Copy,
  FileWarning,
  Fingerprint,
  Search,
  TableProperties,
  X,
} from 'lucide-react';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { Badge } from '@/components/ui/badge';
import { Card, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { dashboardDataSource } from '@/lib/data/local-dashboard-data';
import { findingsDataSource } from '@/lib/data/local-findings-data';
import type { DashboardData, FindingSeverity, FindingState } from '@/lib/data/dashboard-types';
import type { FindingListItem } from '@/lib/data/findings-types';
import evidenceCsv from '../../../../data/datatrust_audit_demo_csv/evidence.csv?raw';
import { parseCsv, type CsvRow } from '@/lib/data/csv';


const domainColors = ['#04D3D4', '#FFC402', '#06b6d4', '#10b981', '#64748b'];
const severityTone: Record<FindingSeverity, 'red' | 'amber' | 'blue' | 'slate'> = {
  CRITICAL: 'red',
  HIGH: 'red',
  MEDIUM: 'amber',
  LOW: 'blue',
};
const stateTone: Record<FindingState, 'red' | 'amber' | 'green' | 'blue'> = {
  OPEN: 'red',
  IN_REVIEW: 'amber',
  REMEDIATED: 'green',
  CLOSED: 'green',
};

interface EvidenceItem {
  id: string;
  type: string;
  source: string;
  sourceEventId: string;
  capturedAt: string;
  actor: string;
  linkedObject: string;
  hash: string;
  rawReference: string;
}

export function ResultsPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const initialTab = searchParams.get('tab') || 'dashboard';
  const highlightRef = searchParams.get('ref') || '';

  const [activeTab, setActiveTab] = useState<'dashboard' | 'evidence' | 'findings'>(
    initialTab === 'evidence' ? 'evidence' : initialTab === 'findings' ? 'findings' : 'dashboard'
  );

  const [dashboardData, setDashboardData] = useState<DashboardData | null>(null);
  const [findings, setFindings] = useState<FindingListItem[]>([]);
  const [evidenceList, setEvidenceList] = useState<EvidenceItem[]>([]);
  const [evidenceSearch, setEvidenceSearch] = useState(highlightRef);
  const [selectedEvidence, setSelectedEvidence] = useState<EvidenceItem | null>(null);
  const [copiedHash, setCopiedHash] = useState<string | null>(null);

  useEffect(() => {
    dashboardDataSource.getDashboardData().then(setDashboardData);
    findingsDataSource.listFindings().then(setFindings);

    const parsedEvidence = parseCsv(evidenceCsv).map((row: CsvRow) => ({
      id: row.evidence_id,
      type: row.evidence_type,
      source: row.source_system,
      sourceEventId: row.source_event_id,
      capturedAt: row.captured_at,
      actor: row.actor_user_id || 'SYSTEM_DAEMON',
      linkedObject: row.trip_id || row.request_id || row.run_id || row.source_event_id || 'N/A',
      hash: row.integrity_hash_sha256_demo || 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
      rawReference: row.raw_reference || `${row.source_system}.log#${row.source_event_id}`,
    }));
    setEvidenceList(parsedEvidence);
  }, []);

  const handleTabChange = (tab: 'dashboard' | 'evidence' | 'findings') => {
    setActiveTab(tab);
    setSearchParams({ tab });
  };

  const copyHash = (hash: string) => {
    navigator.clipboard.writeText(hash);
    setCopiedHash(hash);
    setTimeout(() => setCopiedHash(null), 2000);
  };

  const filteredEvidence = evidenceList.filter((e) => {
    if (!evidenceSearch) return true;
    const q = evidenceSearch.toLowerCase();
    return (
      e.id.toLowerCase().includes(q) ||
      e.type.toLowerCase().includes(q) ||
      e.actor.toLowerCase().includes(q) ||
      e.linkedObject.toLowerCase().includes(q) ||
      e.hash.toLowerCase().includes(q)
    );
  });

  return (
    <div className="page-enter mx-auto max-w-[1360px] space-y-6">
      {/* Top Header */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <span className="text-[11px] font-bold uppercase tracking-wider text-slate-700">
            Giám Sát & Truy Vết
          </span>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">
            Kết Quả Kiểm Soát & Bằng Chứng
          </h1>
          <p className="mt-1 text-sm text-slate-500">
            Xem báo cáo tuân thủ tổng thể chuẩn IPO, kho bằng chứng bất biến SHA-256 và danh sách vi phạm.
          </p>
        </div>

        {/* Tab Switcher */}
        <div className="flex rounded-xl border border-slate-200 bg-white p-1 shadow-2xs">
          <button
            onClick={() => handleTabChange('dashboard')}
            className={`flex items-center gap-1.5 rounded-lg px-3.5 py-1.5 text-xs font-bold transition ${
              activeTab === 'dashboard'
                ? 'bg-[#04D3D4] text-slate-950 shadow-xs'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            <TableProperties size={13} />
            Dashboard Tuân Thủ
          </button>
          <button
            onClick={() => handleTabChange('evidence')}
            className={`flex items-center gap-1.5 rounded-lg px-3.5 py-1.5 text-xs font-bold transition ${
              activeTab === 'evidence'
                ? 'bg-[#04D3D4] text-slate-950 shadow-xs'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            <Fingerprint size={13} />
            Kho Bằng Chứng ({evidenceList.length})
          </button>
          <button
            onClick={() => handleTabChange('findings')}
            className={`flex items-center gap-1.5 rounded-lg px-3.5 py-1.5 text-xs font-bold transition ${
              activeTab === 'findings'
                ? 'bg-[#04D3D4] text-slate-950 shadow-xs'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            <FileWarning size={13} />
            Danh Sách Vi Phạm ({findings.length})
          </button>
        </div>
      </div>

      {/* TAB 1: DASHBOARD */}
      {activeTab === 'dashboard' && dashboardData && (
        <div className="space-y-6">
          {/* Top 4 Metrics */}
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <Card className="rounded-xl border-[#e2ece8] bg-white p-5 shadow-2xs">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-slate-500">Tổng số Vi phạm</span>
                <span className="grid size-9 place-items-center rounded-lg bg-red-50 text-red-600">
                  <FileWarning size={18} />
                </span>
              </div>
              <p className="mt-2 text-2xl font-bold text-slate-900">{dashboardData.metrics.total}</p>
              <span className="mt-1 flex items-center gap-1 text-[11px] font-medium text-red-500">
                <ArrowUpRight size={12} /> +8% trong đợt audit gần nhất
              </span>
            </Card>

            <Card className="rounded-xl border-[#e2ece8] bg-white p-5 shadow-2xs">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-slate-500">Đã Khắc phục / Đóng</span>
                <span className="grid size-9 place-items-center rounded-lg bg-[#e6f6f2] text-[#007460]">
                  <CheckCircle2 size={18} />
                </span>
              </div>
              <p className="mt-2 text-2xl font-bold text-slate-900">{dashboardData.metrics.resolved}</p>
              <span className="mt-1 flex items-center gap-1 text-[11px] font-medium text-[#007460]">
                <ArrowUpRight size={12} /> Tỷ lệ xử lý 58%
              </span>
            </Card>

            <Card className="rounded-xl border-[#e2ece8] bg-white p-5 shadow-2xs">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-slate-500">Đang Xử lý (Active)</span>
                <span className="grid size-9 place-items-center rounded-lg bg-amber-50 text-amber-600">
                  <Clock3 size={18} />
                </span>
              </div>
              <p className="mt-2 text-2xl font-bold text-slate-900">{dashboardData.metrics.inProgress}</p>
              <span className="mt-1 flex items-center gap-1 text-[11px] font-medium text-amber-600">
                Được gán cho Steward / Analyst
              </span>
            </Card>

            <Card className="rounded-xl border-[#e2ece8] bg-white p-5 shadow-2xs">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-slate-500">Quá Hạn Xử lý</span>
                <span className="grid size-9 place-items-center rounded-lg bg-red-50 text-red-600">
                  <AlertTriangle size={18} />
                </span>
              </div>
              <p className="mt-2 text-2xl font-bold text-slate-900">{dashboardData.metrics.overdue}</p>
              <span className="mt-1 flex items-center gap-1 text-[11px] font-medium text-red-500">
                <ArrowDownRight size={12} /> Cần can thiệp khẩn cấp
              </span>
            </Card>
          </div>

          {/* Charts Row */}
          <div className="grid gap-6 xl:grid-cols-12">
            {/* Compliance Score Gauge */}
            <Card className="rounded-2xl border-[#e2ece8] bg-white p-6 shadow-xs xl:col-span-4">
              <CardTitle className="text-sm font-semibold text-slate-800">
                Tỷ lệ Tuân thủ Chuẩn IPO
              </CardTitle>
              <div className="mt-6 flex flex-col items-center justify-center">
                <div
                  className="relative grid size-44 place-items-center rounded-full shadow-inner"
                  style={{
                    background: `conic-gradient(#04D3D4 ${dashboardData.complianceScore * 3.6}deg, #e2ece8 0)`,
                  }}
                >
                  <div className="grid size-32 place-items-center rounded-full bg-white text-center shadow-xs">
                    <div>
                      <strong className="text-3xl font-extrabold text-slate-900">
                        {dashboardData.complianceScore}%
                      </strong>
                      <span className="block text-[11px] font-bold text-slate-700">
                        Đạt chuẩn
                      </span>
                    </div>
                  </div>
                </div>
                <p className="mt-4 text-center text-xs font-semibold text-emerald-700">
                  ↑ Tăng 5% sau khi áp dụng các rule L1-L4
                </p>
              </div>
            </Card>

            {/* Control Results Bars */}
            <Card className="rounded-2xl border-[#e2ece8] bg-white p-6 shadow-xs xl:col-span-4">
              <CardTitle className="text-sm font-semibold text-slate-800">
                Kết quả Đánh giá Control
              </CardTitle>
              <div className="mt-4 h-[220px]">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={dashboardData.controls} margin={{ top: 10, right: 8, left: -20, bottom: 0 }}>
                    <CartesianGrid vertical={false} stroke="#f0f4f2" />
                    <XAxis dataKey="name" tick={{ fontSize: 11 }} axisLine={false} tickLine={false} />
                    <YAxis tick={{ fontSize: 11 }} axisLine={false} tickLine={false} />
                    <Tooltip />
                    <Bar dataKey="value" radius={[6, 6, 0, 0]}>
                      {dashboardData.controls.map((item) => (
                        <Cell
                          key={item.name}
                          fill={item.name === 'Pass' ? '#04D3D4' : item.name === 'Fail' ? '#ef4444' : '#94a3b8'}
                        />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </Card>

            {/* Findings by Domain Pie */}
            <Card className="rounded-2xl border-slate-200 bg-white p-6 shadow-xs xl:col-span-4">
              <CardTitle className="text-sm font-semibold text-slate-800">
                Phân bố Vi phạm theo Miền
              </CardTitle>
              <div className="mt-4 grid h-[220px] grid-cols-[1fr_130px] items-center">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={dashboardData.findingsByDomain}
                      dataKey="value"
                      nameKey="name"
                      innerRadius={46}
                      outerRadius={74}
                      paddingAngle={3}
                    >
                      {dashboardData.findingsByDomain.map((entry, index) => (
                        <Cell key={entry.name} fill={domainColors[index % domainColors.length]} />
                      ))}
                    </Pie>
                    <Tooltip />
                  </PieChart>
                </ResponsiveContainer>
                <div className="space-y-2">
                  {dashboardData.findingsByDomain.map((item, index) => (
                    <div key={item.name} className="flex items-center gap-2 text-[11px]">
                      <span
                        className="size-2 rounded-full shrink-0"
                        style={{ background: domainColors[index % domainColors.length] }}
                      />
                      <span className="truncate text-slate-500">{item.name}</span>
                      <strong className="text-slate-800 ml-auto">{item.value}</strong>
                    </div>
                  ))}
                </div>
              </div>
            </Card>
          </div>

          {/* Compliance Trend Line */}
          <Card className="rounded-2xl border-slate-200 bg-white p-6 shadow-xs">
            <div className="flex items-center justify-between">
              <div>
                <CardTitle className="text-sm font-semibold text-slate-800">
                  Xu hướng Tuân thủ qua các đợt chạy Pipeline
                </CardTitle>
                <span className="text-[11px] text-slate-400">
                  Dữ liệu tổng hợp từ kết quả thực thi các luật chất lượng và bảo mật
                </span>
              </div>
            </div>
            <div className="mt-4 h-[220px]">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={dashboardData.complianceTrend} margin={{ top: 10, right: 16, left: -20, bottom: 0 }}>
                  <CartesianGrid vertical={false} stroke="#f0f4f2" />
                  <XAxis dataKey="date" tick={{ fontSize: 10 }} axisLine={false} tickLine={false} />
                  <YAxis domain={[0, 100]} tick={{ fontSize: 10 }} axisLine={false} tickLine={false} />
                  <Tooltip formatter={(value) => [`${value}%`, 'Tỷ lệ Tuân thủ']} />
                  <Line
                    type="monotone"
                    dataKey="score"
                    stroke="#04D3D4"
                    strokeWidth={2.8}
                    dot={{ r: 3.5, fill: '#04D3D4', strokeWidth: 0 }}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </Card>
        </div>
      )}

      {/* TAB 2: AUDIT EVIDENCE STORE */}
      {activeTab === 'evidence' && (
        <Card className="overflow-hidden rounded-2xl border-slate-200 bg-white shadow-xs">
          <div className="flex flex-col gap-3 border-b border-slate-200 p-5 sm:flex-row sm:items-center sm:justify-between">
            <div className="relative max-w-md flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={14} />
              <input
                value={evidenceSearch}
                onChange={(e) => setEvidenceSearch(e.target.value)}
                placeholder="Tìm kiếm Evidence ID, Actor, Event, SHA-256..."
                className="h-9 w-full rounded-lg border border-slate-200 bg-slate-50 pl-9 pr-3 text-xs outline-none focus:border-[#04D3D4] focus:bg-white transition"
              />
            </div>

            <div className="flex items-center gap-2">
              <span className="text-xs text-slate-400 font-medium">
                Hiển thị {filteredEvidence.length} / {evidenceList.length} bằng chứng
              </span>
            </div>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full min-w-[980px] text-left text-xs">
              <thead className="border-b border-slate-200 bg-slate-50 text-[10px] uppercase tracking-wide text-slate-500">
                <tr>
                  {['Mã Evidence', 'Loại Bằng chứng', 'Hệ thống Nguồn', 'Tác nhân (Actor)', 'Đối tượng', 'Mã băm SHA-256', 'Thời điểm', ''].map(
                    (col, idx) => (
                      <th key={idx} className="px-5 py-3 font-semibold">
                        {col}
                      </th>
                    )
                  )}
                </tr>
              </thead>
              <tbody className="divide-y divide-[#f2f6f4]">
                {filteredEvidence.slice(0, 50).map((ev) => (
                  <tr key={ev.id} className="hover:bg-slate-50 transition-colors">
                    <td className="px-5 py-3.5 font-mono text-[11px] font-bold text-slate-900">{ev.id}</td>
                    <td className="px-5 py-3.5">
                      <span className="rounded-md border border-[#04D3D4]/30 bg-[#04D3D4]/15 px-2 py-0.5 text-[10px] font-bold text-slate-950">
                        {ev.type}
                      </span>
                    </td>
                    <td className="px-5 py-3.5 text-slate-600 font-medium">{ev.source}</td>
                    <td className="px-5 py-3.5 font-mono text-[11px] text-slate-700">{ev.actor}</td>
                    <td className="px-5 py-3.5 font-mono text-[11px] text-slate-500">{ev.linkedObject}</td>
                    <td className="px-5 py-3.5">
                      <div className="flex items-center gap-1.5 font-mono text-[10px] text-slate-500">
                        <span className="truncate max-w-[130px]">{ev.hash}</span>
                        <button
                          onClick={() => copyHash(ev.hash)}
                          className="hover:text-[#04D3D4] text-slate-400"
                          title="Sao chép SHA-256"
                        >
                          {copiedHash === ev.hash ? (
                            <CheckCircle2 size={12} className="text-[#04D3D4]" />
                          ) : (
                            <Copy size={12} />
                          )}
                        </button>
                      </div>
                    </td>
                    <td className="whitespace-nowrap px-5 py-3.5 text-slate-400">
                      {ev.capturedAt ? new Date(ev.capturedAt).toLocaleString('vi-VN') : 'N/A'}
                    </td>
                    <td className="px-5 py-3.5 text-right">
                      <button
                        onClick={() => setSelectedEvidence(ev)}
                        className="rounded-md border border-slate-200 bg-white px-2.5 py-1 text-[11px] font-medium text-slate-700 hover:border-[#04D3D4] hover:text-[#04D3D4]"
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

      {/* TAB 3: FINDINGS LIST */}
      {activeTab === 'findings' && (
        <Card className="overflow-hidden rounded-2xl border-slate-200 bg-white shadow-xs">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[920px] text-left text-xs">
              <thead className="border-b border-slate-200 bg-slate-50 text-[10px] uppercase tracking-wide text-slate-500">
                <tr>
                  {['Mã Finding', 'Tiêu đề vi phạm', 'Miền kiểm soát', 'Mức độ', 'Trạng thái', 'Ngày phát hiện'].map(
                    (col, idx) => (
                      <th key={idx} className="px-5 py-3 font-semibold">
                        {col}
                      </th>
                    )
                  )}
                </tr>
              </thead>
              <tbody className="divide-y divide-[#f2f6f4]">
                {findings.map((f) => (
                  <tr key={f.id} className="hover:bg-slate-50 transition-colors">
                    <td className="px-5 py-3.5 font-mono text-[11px] font-bold text-slate-900">{f.id}</td>
                    <td className="max-w-md px-5 py-3.5 font-medium text-slate-800 truncate">{f.title}</td>
                    <td className="px-5 py-3.5 text-slate-500">{f.domain}</td>
                    <td className="px-5 py-3.5">
                      <Badge tone={severityTone[f.severity]}>{f.severity}</Badge>
                    </td>
                    <td className="px-5 py-3.5">
                      <Badge tone={stateTone[f.status]}>{f.status.replace('_', ' ')}</Badge>
                    </td>
                    <td className="px-5 py-3.5 text-slate-400">
                      {new Date(f.createdAt).toLocaleDateString('vi-VN')}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      {/* Evidence Modal / Drawer */}
      {selectedEvidence && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/40 p-4 backdrop-blur-xs">
          <div className="w-full max-w-lg rounded-2xl border border-slate-200 bg-white p-6 shadow-xl">
            <div className="flex items-center justify-between border-b border-slate-200 pb-3">
              <div className="flex items-center gap-2">
                <Fingerprint size={18} className="text-[#04D3D4]" />
                <h3 className="text-base font-bold text-slate-900">Chi tiết Bằng chứng Kiểm toán</h3>
              </div>
              <button onClick={() => setSelectedEvidence(null)} className="text-slate-400 hover:text-slate-700">
                <X size={18} />
              </button>
            </div>

            <div className="mt-4 space-y-3 text-xs">
              <div className="flex justify-between py-1 border-b border-slate-100">
                <span className="text-slate-400">Mã Evidence:</span>
                <span className="font-mono font-bold text-slate-900">{selectedEvidence.id}</span>
              </div>
              <div className="flex justify-between py-1 border-b border-slate-100">
                <span className="text-slate-400">Loại bằng chứng:</span>
                <span className="font-medium text-slate-800">{selectedEvidence.type}</span>
              </div>
              <div className="flex justify-between py-1 border-b border-slate-100">
                <span className="text-slate-400">Hệ thống nguồn:</span>
                <span className="font-medium text-slate-800">{selectedEvidence.source}</span>
              </div>
              <div className="flex justify-between py-1 border-b border-slate-100">
                <span className="text-slate-400">Tác nhân ghi nhận:</span>
                <span className="font-mono text-slate-700">{selectedEvidence.actor}</span>
              </div>
              <div className="flex justify-between py-1 border-b border-slate-100">
                <span className="text-slate-400">Tham chiếu gốc:</span>
                <span className="font-mono text-slate-700 truncate max-w-[280px]">
                  {selectedEvidence.rawReference}
                </span>
              </div>
              <div>
                <span className="text-slate-400 block mb-1">Mã băm toàn vẹn SHA-256 (Tamper-proof):</span>
                <div className="flex items-center justify-between rounded-lg border border-[#c2ebe0] bg-[#f0f9f6] p-2.5 font-mono text-[11px] text-[#007460]">
                  <span className="break-all">{selectedEvidence.hash}</span>
                  <button
                    onClick={() => copyHash(selectedEvidence.hash)}
                    className="ml-2 hover:text-[#004d40] shrink-0"
                  >
                    <Copy size={13} />
                  </button>
                </div>
              </div>
            </div>

            <div className="mt-6 flex justify-end">
              <Button variant="xanhsm" size="sm" onClick={() => setSelectedEvidence(null)}>
                Đóng
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
