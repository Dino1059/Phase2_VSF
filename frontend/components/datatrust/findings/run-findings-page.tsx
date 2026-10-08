'use client';

import { useEffect, useState, useCallback } from 'react';
import { useParams, useSearchParams, Link, useNavigate } from 'react-router-dom';
import {
  Search,
  ShieldAlert,
  CheckCircle2,
  Eye,
  RefreshCw,
  Loader2,
  FileText,
  SlidersHorizontal,
  X
} from 'lucide-react';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { apiBridge, type FindingItem, type DatasetCatalogItem } from '@/lib/api-bridge';
import { FindingDetailModal } from './finding-detail';

const formatDateTime = (value?: string | null) => {
  if (!value) return '—';
  try {
    return new Intl.DateTimeFormat('vi-VN', {
      dateStyle: 'medium',
      timeStyle: 'short',
    }).format(new Date(value));
  } catch {
    return value;
  }
};

export function RunFindingsPage() {
  const { runId: paramRunId } = useParams<{ runId: string }>();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();

  // URL Query Parameters
  const initialRule = searchParams.get('rule_id') || '';
  const initialSeverity = searchParams.get('severity') || 'ALL';
  const initialStatus = searchParams.get('status') || 'ALL';
  const initialSubjectZone = searchParams.get('subject_zone') || 'ALL';

  const [findings, setFindings] = useState<FindingItem[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // 6 Filters State
  const [selectedRunId, setSelectedRunId] = useState<string>(paramRunId || '');
  const [selectedDataset, setSelectedDataset] = useState<string>('ALL');
  const [selectedRule, setSelectedRule] = useState<string>(initialRule);
  const [selectedSeverity, setSelectedSeverity] = useState<string>(initialSeverity);
  const [selectedStatus, setSelectedStatus] = useState<string>(initialStatus);
  const [selectedColumn, setSelectedColumn] = useState<string>('');
  const [selectedSubjectZone, setSelectedSubjectZone] = useState<string>(initialSubjectZone);
  const [searchText, setSearchText] = useState<string>('');

  // Catalog Datasets
  const [datasets, setDatasets] = useState<DatasetCatalogItem[]>([]);

  // Selected finding for modal
  const [activeFindingId, setActiveFindingId] = useState<string | null>(null);

  // Load datasets on mount
  useEffect(() => {
    apiBridge.fetchDatasets().then((items) => {
      if (items) setDatasets(items);
    }).catch(console.warn);
  }, []);

  // Fetch Findings from PostgreSQL
  const loadFindings = useCallback(async () => {
    setLoading(true);
    try {
      const data = await apiBridge.fetchFindings({
        runId: selectedRunId ? selectedRunId : undefined,
        datasetId: selectedDataset !== 'ALL' ? selectedDataset : undefined,
        ruleId: selectedRule || undefined,
        severity: selectedSeverity !== 'ALL' ? selectedSeverity : undefined,
        status: selectedStatus !== 'ALL' ? selectedStatus : undefined,
        column: selectedColumn || undefined,
        subjectZone: selectedSubjectZone !== 'ALL' ? selectedSubjectZone : undefined,
        search: searchText || undefined,
        limit: 100,
        offset: 0,
      });
      setFindings(data.findings || []);
      setTotalCount(data.total || 0);
      setError(null);
    } catch (err: any) {
      setError(err.message || 'Không thể nạp danh sách Findings');
    } finally {
      setLoading(false);
    }
  }, [selectedRunId, selectedDataset, selectedRule, selectedSeverity, selectedStatus, selectedColumn, selectedSubjectZone, searchText]);

  useEffect(() => {
    loadFindings();
  }, [loadFindings]);

  const resetFilters = () => {
    setSelectedDataset('ALL');
    setSelectedRule('');
    setSelectedSeverity('ALL');
    setSelectedStatus('ALL');
    setSelectedColumn('');
    setSelectedSubjectZone('ALL');
    setSearchText('');
  };

  return (
    <section className="page-enter mx-auto max-w-[1360px] space-y-6 pb-12">
      {/* Header & Breadcrumbs */}
      <div>
        <div className="mb-3 flex items-center gap-2 text-xs font-semibold text-slate-400">
          <Link to="/runs" className="hover:text-white transition-colors">
            Danh sách lượt chạy
          </Link>
          {selectedRunId && (
            <>
              <span>/</span>
              <Link to={`/runs/${selectedRunId}`} className="hover:text-white transition-colors">
                {selectedRunId}
              </Link>
            </>
          )}
          <span>/</span>
          <span className="text-cyan-400 font-bold">Danh sách Vấn đề Kiểm toán (Step 5)</span>
        </div>

        <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between bg-slate-900/60 border border-slate-800 rounded-2xl p-6 shadow-xl">
          <div className="space-y-1.5">
            <div className="flex items-center gap-3">
              <h1 className="text-2xl font-bold tracking-tight text-white flex items-center gap-2.5">
                <ShieldAlert className="size-6 text-rose-400" />
                Vấn đề Kiểm toán Dữ liệu (Audit Findings)
              </h1>
              <span className="rounded-full bg-cyan-500/10 px-3 py-1 text-xs font-mono font-bold text-cyan-400 border border-cyan-500/20">
                {totalCount} Vấn đề
              </span>
            </div>
            <p className="text-xs text-slate-400">
              Tổng hợp từ bảng <code className="text-slate-300">audit.findings</code> kết nối trực tiếp với các bản ghi cách ly <code className="text-slate-300">quarantine.records</code> trong PostgreSQL
            </p>
          </div>

          <div className="flex items-center gap-2">
            {selectedRunId && (
              <Button
                variant="outline"
                onClick={() => navigate(`/runs/${selectedRunId}/results`)}
                className="border-slate-700 text-slate-300 hover:bg-slate-800 gap-1.5"
              >
                <FileText className="size-4" />
                <span>Xem Kết quả KPIs</span>
              </Button>
            )}
            <Button
              variant="outline"
              onClick={loadFindings}
              className="border-slate-700 text-slate-300 hover:bg-slate-800 gap-1.5"
            >
              <RefreshCw className="size-3.5" />
              <span>Làm mới</span>
            </Button>
          </div>
        </div>
      </div>

      {/* BỘ LỌC TÌM KIẾM FINDINGS */}
      <Card className="rounded-2xl border-slate-800 bg-slate-900/80 p-5 shadow-xl space-y-4">
        <div className="flex items-center justify-between pb-3 border-b border-slate-800 text-xs font-bold text-white">
          <span className="flex items-center gap-2">
            <SlidersHorizontal className="size-4 text-cyan-400" />
            Bộ lọc Kiểm toán Nâng cao (7 Chiều)
          </span>
          <button
            onClick={resetFilters}
            className="text-[11px] font-normal text-slate-400 hover:text-cyan-400 transition-colors flex items-center gap-1"
          >
            <X className="size-3" /> Đặt lại bộ lọc
          </button>
        </div>

        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-7 text-xs">
          {/* Filter 1: Run ID */}
          <div className="space-y-1">
            <label className="text-[11px] font-semibold text-slate-400">1. Lượt chạy (Run ID)</label>
            <input
              type="text"
              placeholder="Tất cả runs / nhập ID..."
              value={selectedRunId}
              onChange={(e) => setSelectedRunId(e.target.value)}
              className="w-full rounded-lg border border-slate-700 bg-slate-800/80 px-2.5 py-1.5 text-xs text-white placeholder-slate-500 focus:border-cyan-500 focus:outline-none"
            />
          </div>

          {/* Filter 2: Dataset */}
          <div className="space-y-1">
            <label className="text-[11px] font-semibold text-slate-400">2. Bảng dữ liệu (Dataset)</label>
            <select
              value={selectedDataset}
              onChange={(e) => setSelectedDataset(e.target.value)}
              className="w-full rounded-lg border border-slate-700 bg-slate-800/80 px-2.5 py-1.5 text-xs text-white focus:border-cyan-500 focus:outline-none"
            >
              <option value="ALL">Tất cả bảng</option>
              {datasets.map((d) => (
                <option key={d.dataset_id} value={d.dataset_id}>
                  {d.name || d.dataset_id}
                </option>
              ))}
            </select>
          </div>

          {/* Filter 3: Rule ID */}
          <div className="space-y-1">
            <label className="text-[11px] font-semibold text-slate-400">3. Quy tắc (Rule ID)</label>
            <input
              type="text"
              placeholder="e.g. POLICY_BLOCK"
              value={selectedRule}
              onChange={(e) => setSelectedRule(e.target.value)}
              className="w-full rounded-lg border border-slate-700 bg-slate-800/80 px-2.5 py-1.5 text-xs text-white placeholder-slate-500 focus:border-cyan-500 focus:outline-none"
            />
          </div>

          {/* Filter 4: Severity */}
          <div className="space-y-1">
            <label className="text-[11px] font-semibold text-slate-400">4. Mức độ (Severity)</label>
            <select
              value={selectedSeverity}
              onChange={(e) => setSelectedSeverity(e.target.value)}
              className="w-full rounded-lg border border-slate-700 bg-slate-800/80 px-2.5 py-1.5 text-xs text-white focus:border-cyan-500 focus:outline-none"
            >
              <option value="ALL">Tất cả mức độ</option>
              <option value="CRITICAL">CRITICAL (Nghiêm trọng)</option>
              <option value="HIGH">HIGH (Cao)</option>
              <option value="MEDIUM">MEDIUM (Trung bình)</option>
              <option value="LOW">LOW (Thấp)</option>
            </select>
          </div>

          {/* Filter 5: Status */}
          <div className="space-y-1">
            <label className="text-[11px] font-semibold text-slate-400">5. Trạng thái (Status)</label>
            <select
              value={selectedStatus}
              onChange={(e) => setSelectedStatus(e.target.value)}
              className="w-full rounded-lg border border-slate-700 bg-slate-800/80 px-2.5 py-1.5 text-xs text-white focus:border-cyan-500 focus:outline-none"
            >
              <option value="ALL">Tất cả trạng thái</option>
              <option value="OPEN">OPEN (Đang mở)</option>
              <option value="IN_REVIEW">IN_REVIEW (Đang xem xét)</option>
              <option value="REMEDIATED">REMEDIATED (Đã khắc phục)</option>
              <option value="OVERRIDDEN">OVERRIDDEN (Đã ngoại lệ)</option>
              <option value="RESOLVED">RESOLVED (Đã đóng)</option>
            </select>
          </div>

          {/* Filter 6: Column */}
          <div className="space-y-1">
            <label className="text-[11px] font-semibold text-slate-400">6. Cột mục tiêu (Column)</label>
            <input
              type="text"
              placeholder="e.g. fare_amount"
              value={selectedColumn}
              onChange={(e) => setSelectedColumn(e.target.value)}
              className="w-full rounded-lg border border-slate-700 bg-slate-800/80 px-2.5 py-1.5 text-xs text-white placeholder-slate-500 focus:border-cyan-500 focus:outline-none"
            />
          </div>

          {/* Filter 7: Subject zone */}
          <div className="space-y-1">
            <label className="text-[11px] font-semibold text-slate-400">7. Zone áp dụng</label>
            <select
              value={selectedSubjectZone}
              onChange={(e) => setSelectedSubjectZone(e.target.value)}
              className="w-full rounded-lg border border-slate-700 bg-slate-800/80 px-2.5 py-1.5 text-xs text-white focus:border-cyan-500 focus:outline-none"
            >
              <option value="ALL">Tất cả zone</option>
              <option value="VN">VN</option>
              <option value="EU">EU</option>
              <option value="US">US</option>
              <option value="GLOBAL">GLOBAL</option>
            </select>
          </div>
        </div>

        {/* Free text search bar */}
        <div className="pt-2">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-slate-400" />
            <input
              type="text"
              placeholder="Tìm kiếm nội dung lý do vi phạm, điều khoản luật, tên chính sách..."
              value={searchText}
              onChange={(e) => setSearchText(e.target.value)}
              className="w-full rounded-xl border border-slate-700 bg-slate-800/60 pl-9 pr-4 py-2 text-xs text-white placeholder-slate-500 focus:border-cyan-500 focus:outline-none"
            />
          </div>
        </div>
      </Card>

      {/* DANH SÁCH BẢNG FINDINGS */}
      <Card className="rounded-2xl border-slate-800 bg-slate-900/90 p-5 shadow-xl">
        {loading ? (
          <div className="py-12 flex flex-col items-center justify-center gap-3 text-slate-400 text-xs">
            <Loader2 className="size-6 animate-spin text-cyan-400" />
            <span>Đang truy vấn danh sách Findings từ PostgreSQL…</span>
          </div>
        ) : error ? (
          <div className="p-4 text-xs text-rose-300 rounded-xl bg-rose-500/10 border border-rose-500/30">
            {error}
          </div>
        ) : findings.length === 0 ? (
          <div className="py-12 text-center text-xs text-slate-400 space-y-2">
            <CheckCircle2 className="size-8 mx-auto text-emerald-400 opacity-80" />
            <p className="text-white font-medium">Không tìm thấy vấn đề kiểm toán (Finding) nào phù hợp.</p>
            <p className="text-slate-500">Hãy thử nới lỏng các bộ lọc tìm kiếm.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs text-slate-300">
              <thead className="bg-slate-800/60 uppercase font-mono text-[10px] text-slate-400 border-b border-slate-800">
                <tr>
                  <th className="py-3 px-3">Finding ID</th>
                  <th className="py-3 px-3">Bảng / Cột</th>
                  <th className="py-3 px-3">Quy tắc / Policy</th>
                  <th className="py-3 px-3">Zone</th>
                  <th className="py-3 px-3">Mức độ</th>
                  <th className="py-3 px-3">Trạng thái</th>
                  <th className="py-3 px-3 text-right">Bản ghi vi phạm</th>
                  <th className="py-3 px-3">Lý do & Tác động</th>
                  <th className="py-3 px-3">Phát hiện lúc</th>
                  <th className="py-3 px-3 text-center">Thao tác</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {findings.map((f) => (
                  <tr
                    key={f.finding_id}
                    className="hover:bg-slate-800/40 transition-colors cursor-pointer"
                    onClick={() => setActiveFindingId(f.finding_id)}
                  >
                    <td className="py-3.5 px-3 font-mono font-bold text-cyan-400 whitespace-nowrap">
                      {f.finding_id}
                    </td>
                    <td className="py-3.5 px-3 whitespace-nowrap">
                      <span className="font-semibold text-white block">{f.dataset_id}</span>
                      <span className="text-[11px] font-mono text-cyan-300 block">{f.column_name}</span>
                    </td>
                    <td className="py-3.5 px-3">
                      <span className="font-mono font-bold text-slate-200 block">{f.rule_id}</span>
                      <span className="text-[11px] text-slate-400 block line-clamp-1">{f.policy_name || 'Chưa xác định chính sách'}</span>
                    </td>
                    <td className="py-3.5 px-3 whitespace-nowrap">
                      <span className="inline-block rounded border border-violet-500/30 bg-violet-500/10 px-2 py-0.5 font-mono text-[10px] font-bold text-violet-300">
                        {f.subject_zone || 'Chưa xác định'}
                      </span>
                    </td>
                    <td className="py-3.5 px-3 whitespace-nowrap">
                      <span
                        className={`inline-block px-2 py-0.5 rounded text-[10px] font-bold ${
                          f.severity === 'CRITICAL'
                            ? 'bg-rose-500/20 text-rose-300 border border-rose-500/30'
                            : f.severity === 'HIGH'
                            ? 'bg-amber-500/20 text-amber-300 border border-amber-500/30'
                            : 'bg-slate-700 text-slate-300'
                        }`}
                      >
                        {f.severity}
                      </span>
                    </td>
                    <td className="py-3.5 px-3 whitespace-nowrap">
                      <span
                        className={`inline-block px-2 py-0.5 rounded text-[10px] font-bold ${
                          f.status === 'OPEN'
                            ? 'bg-rose-500/10 text-rose-400 border border-rose-500/20'
                            : f.status === 'IN_REVIEW'
                            ? 'bg-amber-500/10 text-amber-400 border border-amber-500/20'
                            : 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                        }`}
                      >
                        {f.status}
                      </span>
                    </td>
                    <td className="py-3.5 px-3 text-right font-mono font-bold text-rose-400 whitespace-nowrap">
                      {f.failed_record_count.toLocaleString('vi-VN')}
                    </td>
                    <td className="py-3.5 px-3 text-slate-300 max-w-xs">
                      <p className="line-clamp-2" title={f.reason}>{f.reason}</p>
                    </td>
                    <td className="py-3.5 px-3 font-mono text-[11px] text-slate-400 whitespace-nowrap">
                      {formatDateTime(f.detected_at)}
                    </td>
                    <td className="py-3.5 px-3 text-center whitespace-nowrap" onClick={(e) => e.stopPropagation()}>
                      <Button
                        size="sm"
                        onClick={() => setActiveFindingId(f.finding_id)}
                        className="h-7 px-3 text-[11px] bg-cyan-500 text-slate-950 font-bold hover:bg-cyan-400 gap-1"
                      >
                        <Eye className="size-3" />
                        <span>Xem chi tiết</span>
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {/* MODAL CHI TIẾT FINDING (STEP 5 / SPEC 08) */}
      {activeFindingId && (
        <FindingDetailModal
          findingId={activeFindingId}
          onClose={() => setActiveFindingId(null)}
          onStatusUpdated={() => loadFindings()}
        />
      )}
    </section>
  );
}
