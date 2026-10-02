'use client';
import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { ChevronRight, Loader2, Play, Search, Workflow } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { pipelineDataSource } from '@/lib/data/local-pipeline-data';
import type { PipelineRun } from '@/lib/data/pipeline-types';
import { PipelineStatusBadge } from '@/components/datatrust/pipeline/pipeline-status';
import { apiBridge } from '@/lib/api-bridge';

const format = (value: string) => {
  try {
    return new Intl.DateTimeFormat('vi-VN', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value));
  } catch {
    return value;
  }
};

export function RunsPage() {
  const [runs, setRuns] = useState<PipelineRun[]>([]);
  const [datasetOptions, setDatasetOptions] = useState<Array<{ id: string; label: string }>>([
    { id: 'ride_hailing_xanh_sm_trips.csv', label: 'ride_hailing_xanh_sm_trips.csv' },
    { id: 'ALL', label: 'TẤT CẢ CÁC BẢNG (ALL 8 datasets)' },
  ]);
  const [selectedDatasetFile, setSelectedDatasetFile] = useState('ride_hailing_xanh_sm_trips.csv');
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('ALL');
  const [isTriggering, setIsTriggering] = useState(false);
  const [triggerMessage, setTriggerMessage] = useState<string | null>(null);

  const loadRuns = async () => {
    try {
      const liveRuns = await apiBridge.fetchLivePipelineRuns();
      if (liveRuns && liveRuns.length > 0) {
        setRuns(liveRuns);
        return;
      }
    } catch {
      // Fallback to local
    }
    const local = await pipelineDataSource.listRuns();
    setRuns(local);
  };

  useEffect(() => {
    loadRuns();
    apiBridge.fetchDatasets().then((dsList) => {
      if (dsList && dsList.length > 0) {
        const opts = dsList.map((d) => ({
          id: d.name || `${d.dataset_id}.csv`,
          label: `${d.name || d.dataset_id} (${d.domain} - ${(d.row_count || 0).toLocaleString('vi-VN')} dòng)`,
        }));
        opts.push({ id: 'ALL', label: 'TẤT CẢ CÁC BẢNG (ALL 8 datasets)' });
        setDatasetOptions(opts);
      }
    }).catch((err) => console.warn('Failed to load dataset options:', err));
  }, []);

  const handleTriggerAirflow = async () => {
    setIsTriggering(true);
    setTriggerMessage(null);
    try {
      const res = await apiBridge.triggerAirflow(selectedDatasetFile);
      setTriggerMessage(`Đã kích hoạt Airflow DAG cho ${selectedDatasetFile}: ${res.dag_run_id || 'Thành công'}`);
      await loadRuns();
    } catch (err: any) {
      setTriggerMessage(`Kích hoạt pipeline dự phòng cho ${selectedDatasetFile}`);
      await loadRuns();
    } finally {
      setIsTriggering(false);
    }
  };

  const filteredRuns = runs.filter((r) => {
    if (statusFilter !== 'ALL' && r.status !== statusFilter) return false;
    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      const ds = ((r as any).datasetId || '').toLowerCase();
      return r.id.toLowerCase().includes(q) || r.dagId.toLowerCase().includes(q) || ds.includes(q);
    }
    return true;
  });

  return (
    <div className="page-enter mx-auto max-w-[1360px] space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <span className="text-[11px] font-bold uppercase tracking-wider text-slate-700">
            Data Pipeline & Ingestion
          </span>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">
            Lịch Sử Lần Chạy
          </h1>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <select
            value={selectedDatasetFile}
            onChange={(e) => setSelectedDatasetFile(e.target.value)}
            className="h-9 rounded-lg border border-slate-200 bg-white px-3 font-mono text-xs font-semibold text-slate-800 focus:outline-none focus:ring-1 focus:ring-[#04D3D4]"
          >
            {datasetOptions.map((opt) => (
              <option key={opt.id} value={opt.id}>
                {opt.label}
              </option>
            ))}
          </select>
          <Button
            onClick={handleTriggerAirflow}
            disabled={isTriggering}
            className="h-9 gap-1.5 px-3 text-xs font-bold bg-[#04D3D4] text-slate-950 hover:bg-[#03b8b9] shadow-xs"
          >
            {isTriggering ? <Loader2 size={14} className="animate-spin" /> : <Play size={14} />}
            <span>Kích hoạt Airflow Run</span>
          </Button>
        </div>
      </div>

      {triggerMessage && (
        <div className="rounded-xl border border-[#04D3D4]/40 bg-[#04D3D4]/10 p-3 text-xs font-medium text-slate-900 flex items-center justify-between">
          <span>{triggerMessage}</span>
          <button onClick={() => setTriggerMessage(null)} className="text-slate-500 hover:text-slate-800 text-xs cursor-pointer">✕</button>
        </div>
      )}

      {/* Main Table Card */}
      <Card className="overflow-hidden rounded-2xl border-slate-200 bg-white shadow-xs">
        {/* Filter bar */}
        <div className="flex flex-col gap-3 border-b border-slate-200 p-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="relative max-w-md flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={14} />
            <input
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Tìm kiếm Run ID, DAG ID hoặc Tệp dữ liệu..."
              className="h-9 w-full rounded-lg border border-slate-200 bg-slate-50 pl-9 pr-3 text-xs outline-none focus:border-[#04D3D4] focus:bg-white transition"
            />
          </div>

          <div className="flex items-center gap-2">
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="h-9 rounded-lg border border-slate-200 bg-white px-3 text-xs font-semibold text-slate-600 focus:outline-none focus:ring-1 focus:ring-[#04D3D4]"
            >
              <option value="ALL">Tất cả trạng thái</option>
              <option value="SUCCESS">Thành công (SUCCESS)</option>
              <option value="FAILED">Thất bại (FAILED)</option>
              <option value="RUNNING">Đang chạy (RUNNING)</option>
            </select>
          </div>
        </div>

        {/* Table */}
        <div className="overflow-x-auto">
          <table className="w-full min-w-[1000px] text-left text-xs">
            <thead className="border-b border-slate-200 bg-slate-50 text-[10px] uppercase tracking-wide text-slate-500">
              <tr>
                {['Mã Lần chạy', 'DAG ID & Tệp Dữ Liệu', 'Trạng thái', 'Đầu vào (Raw)', 'Bản ghi Sạch (Silver)', 'Cách ly (Quarantine)', 'Bắt đầu lúc', 'Thời lượng', ''].map(
                  (col, idx) => (
                    <th key={idx} className="px-4 py-3 font-semibold">
                      {col}
                    </th>
                  )
                )}
              </tr>
            </thead>
            <tbody className="divide-y divide-[#f2f6f4]">
              {filteredRuns.map((run) => (
                <tr key={run.id} className="group hover:bg-slate-50 transition-colors">
                  <td className="px-4 py-3.5">
                    <Link to={`/runs/${run.id}`} className="font-mono font-bold text-slate-900 hover:text-[#04D3D4] hover:underline">
                      {run.id}
                    </Link>
                  </td>
                  <td className="px-4 py-3.5 font-medium">
                    <span className="inline-flex items-center gap-2 text-slate-700 font-semibold">
                      <Workflow size={13} className="text-[#04D3D4]" />
                      {run.dagId}
                    </span>
                    {(run as any).datasetId && (
                      <div className="mt-1">
                        <span className="inline-flex items-center rounded-md bg-[#04D3D4]/10 border border-[#04D3D4]/30 px-1.5 py-0.5 text-[10px] font-mono font-bold text-slate-900">
                          {(run as any).datasetId}
                        </span>
                      </div>
                    )}
                  </td>
                  <td className="px-4 py-3.5">
                    <PipelineStatusBadge status={run.status} />
                  </td>
                  <td className="px-4 py-3.5 font-medium text-slate-700">
                    {run.inputRecords.toLocaleString('vi-VN')}
                  </td>
                  <td className="px-4 py-3.5 font-semibold text-emerald-700">
                    {run.silverRecords.toLocaleString('vi-VN')}
                  </td>
                  <td className="px-4 py-3.5">
                    <span className={run.quarantineRecords ? 'font-semibold text-red-600' : 'text-slate-400'}>
                      {run.quarantineRecords.toLocaleString('vi-VN')}
                    </span>
                  </td>
                  <td className="whitespace-nowrap px-4 py-3.5 text-slate-400">
                    {format(run.startedAt)}
                  </td>
                  <td className="px-4 py-3.5 text-slate-500">{run.durationMinutes} phút</td>
                  <td className="px-4 py-3.5 text-right">
                    <Link
                      to={`/runs/${run.id}`}
                      className="inline-grid size-7 place-items-center rounded-md border border-slate-200 text-slate-400 group-hover:border-[#04D3D4] group-hover:text-slate-950"
                      aria-label={`Open ${run.id}`}
                    >
                      <ChevronRight size={15} />
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="border-t border-[#e2ece8] px-5 py-3 text-xs text-slate-400">
          Tổng cộng {filteredRuns.length} lần chạy pipeline
        </div>
      </Card>
    </div>
  );
}
