'use client';
import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { ChevronRight, Play, Search, Workflow } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { pipelineDataSource } from '@/lib/data/local-pipeline-data';
import type { PipelineRun } from '@/lib/data/pipeline-types';
import { PipelineStatusBadge } from '@/components/datatrust/pipeline/pipeline-status';


const format = (value: string) =>
  new Intl.DateTimeFormat('vi-VN', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value));

export function RunsPage() {
  const [runs, setRuns] = useState<PipelineRun[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('ALL');

  useEffect(() => {
    pipelineDataSource.listRuns().then(setRuns);
  }, []);

  const filteredRuns = runs.filter((r) => {
    if (statusFilter !== 'ALL' && r.status !== statusFilter) return false;
    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      return r.id.toLowerCase().includes(q) || r.dagId.toLowerCase().includes(q);
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
          <p className="mt-1 text-sm text-slate-500">
            Theo dõi tiến trình luân chuyển dữ liệu nguồn → Silver sạch và Quarantine cách ly.
          </p>
        </div>

        <Button variant="xanhsm" size="sm" className="h-9 gap-1.5 px-4 text-xs font-bold bg-[#04D3D4] text-slate-950 hover:bg-[#03b8b9]">
          <Play size={14} /> Chạy pipeline mới
        </Button>
      </div>

      {/* Main Table Card */}
      <Card className="overflow-hidden rounded-2xl border-slate-200 bg-white shadow-xs">
        {/* Filter bar */}
        <div className="flex flex-col gap-3 border-b border-slate-200 p-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="relative max-w-md flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={14} />
            <input
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Tìm kiếm Run ID hoặc DAG ID..."
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
                {['Mã Lần chạy', 'DAG ID', 'Trạng thái', 'Đầu vào (Raw)', 'Bản ghi Sạch (Silver)', 'Cách ly (Quarantine)', 'Bắt đầu lúc', 'Thời lượng', ''].map(
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
                    <span className="inline-flex items-center gap-2 text-slate-700">
                      <Workflow size={13} className="text-[#04D3D4]" />
                      {run.dagId}
                    </span>
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
