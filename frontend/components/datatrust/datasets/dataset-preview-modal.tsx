'use client';

import { useEffect, useState } from 'react';
import { createPortal } from 'react-dom';
import {
  FileSpreadsheet,
  Globe,
  Loader2,
  Search,
  Table,
  X,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { apiBridge } from '@/lib/api-bridge';

interface DatasetPreviewModalProps {
  isOpen: boolean;
  onClose: () => void;
  datasetId: string;
  datasetTitle: string;
  filename: string;
  totalRecords: number;
}

export function DatasetPreviewModal({
  isOpen,
  onClose,
  datasetId,
  datasetTitle,
  filename,
  totalRecords,
}: DatasetPreviewModalProps) {
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState<{
    columns: string[];
    rows: any[];
    total_records: number;
  } | null>(null);
  const [search, setSearch] = useState('');

  useEffect(() => {
    if (!isOpen || !datasetId) return;
    setLoading(true);
    apiBridge
      .fetchDatasetPreview(datasetId, 25)
      .then((res) => {
        setData(res);
        setLoading(false);
      })
      .catch((err) => {
        console.warn('Lỗi fetch preview:', err);
        setLoading(false);
      });
  }, [isOpen, datasetId]);

  if (!isOpen) return null;

  const filteredRows = (data?.rows || []).filter((r) => {
    if (!search) return true;
    const term = search.toLowerCase();
    return Object.values(r).some((v) => String(v ?? '').toLowerCase().includes(term));
  });

  const getPiiBadge = (colName: string) => {
    const col = colName.toLowerCase();
    if (col.includes('phone') || col.includes('email') || col.includes('name') || col.includes('national_id') || col.includes('citizen')) {
      return <span className="rounded bg-rose-50 border border-rose-200 px-1 py-0.5 text-[9px] font-bold text-rose-700">Direct ID</span>;
    }
    if (col.includes('vin') || col.includes('driver_id') || col.includes('customer_id') || col.includes('charger_id')) {
      return <span className="rounded bg-amber-50 border border-amber-200 px-1 py-0.5 text-[9px] font-bold text-amber-700">Linkable ID</span>;
    }
    if (col.includes('lat') || col.includes('lon') || col.includes('address') || col.includes('location')) {
      return <span className="rounded bg-indigo-50 border border-indigo-200 px-1 py-0.5 text-[9px] font-bold text-indigo-700">Contextual PII</span>;
    }
    if (col.includes('temp') || col.includes('voltage') || col.includes('soc') || col.includes('current') || col.includes('power')) {
      return <span className="rounded bg-blue-50 border border-blue-200 px-1 py-0.5 text-[9px] font-bold text-blue-700">Tech Telemetry</span>;
    }
    return <span className="rounded bg-slate-100 px-1 py-0.5 text-[9px] font-medium text-slate-500">Non-personal</span>;
  };

  const getZoneBadge = (zone: string) => {
    if (zone === 'VN') return <span className="rounded-md bg-emerald-100 border border-emerald-300 px-1.5 py-0.5 text-[10px] font-extrabold text-emerald-800">🇻🇳 VN</span>;
    if (zone === 'EU') return <span className="rounded-md bg-purple-100 border border-purple-300 px-1.5 py-0.5 text-[10px] font-extrabold text-purple-800">🇪🇺 EU</span>;
    if (zone === 'US') return <span className="rounded-md bg-amber-100 border border-amber-300 px-1.5 py-0.5 text-[10px] font-extrabold text-amber-800">🇺🇸 US</span>;
    return <span className="text-slate-500 font-mono text-[11px]">{zone}</span>;
  };

  return createPortal(
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 backdrop-blur-xs p-4 animate-in fade-in duration-200">
      <div className="flex flex-col w-full max-w-6xl max-h-[90vh] rounded-2xl bg-white shadow-2xl border border-slate-200 overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-slate-200 bg-slate-50/80 px-6 py-4">
          <div className="flex items-center gap-3">
            <span className="grid size-10 place-items-center rounded-xl bg-[#04D3D4]/20 border border-[#04D3D4]/40 text-slate-900">
              <FileSpreadsheet size={20} className="text-[#04D3D4]" />
            </span>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="font-mono font-bold text-base text-slate-900">
                  {filename}
                </h3>
              </div>
              <p className="text-xs text-slate-500 mt-0.5">
                Tổng số: <strong className="text-slate-900 font-bold">{totalRecords.toLocaleString()}</strong> bản ghi
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <Button
              variant="ghost"
              size="sm"
              onClick={onClose}
              className="size-8 p-0 rounded-lg text-slate-400 hover:text-slate-700 hover:bg-slate-200/50"
            >
              <X size={18} />
            </Button>
          </div>
        </div>

        {/* Filter bar */}
        <div className="flex items-center justify-between gap-4 border-b border-slate-200 px-6 py-3 bg-white">

          <div className="flex items-center gap-2 text-xs text-slate-600">
            <Globe size={14} className="text-slate-400" />
            <span>Đang hiển thị <strong>{filteredRows.length}</strong> dòng mẫu đầu tiên</span>
          </div>
        </div>

        {/* Content Table */}
        <div className="flex-1 overflow-auto p-6 bg-slate-50/50">
          {loading ? (
            <div className="flex flex-col items-center justify-center py-20 text-slate-400">
              <Loader2 size={32} className="animate-spin text-[#04D3D4] mb-3" />
              <p className="text-xs font-semibold">Đang đọc trực tiếp file CSV từ ổ đĩa…</p>
            </div>
          ) : !data || data.rows.length === 0 ? (
            <div className="py-16 text-center text-slate-500">
              <Table size={32} className="mx-auto text-slate-300 mb-2" />
              <p className="text-sm font-semibold">Không tìm thấy bản ghi trong file</p>
            </div>
          ) : (
            <div className="rounded-xl border border-slate-200 bg-white shadow-xs overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="border-b border-slate-200 bg-slate-100/70 text-[10px] uppercase font-semibold text-slate-600">
                    <th className="px-3 py-2.5 w-12 text-center text-slate-400 font-mono">#</th>
                    {data.columns.map((col) => (
                      <th key={col} className="px-3 py-2.5 whitespace-nowrap">
                        <div className="flex flex-col gap-1">
                          <span className="font-mono text-slate-900 font-bold text-[11px]">{col}</span>
                          {getPiiBadge(col)}
                        </div>
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {filteredRows.map((row, idx) => (
                    <tr key={idx} className="hover:bg-slate-50/80 transition-colors">
                      <td className="px-3 py-2.5 text-center text-[10px] font-mono text-slate-400">
                        {idx + 1}
                      </td>
                      {data.columns.map((col) => {
                        const val = row[col];
                        return (
                          <td key={col} className="px-3 py-2.5 whitespace-nowrap text-slate-800 font-mono text-[11px]">
                            {col === 'subject_zone' ? (
                              getZoneBadge(String(val))
                            ) : val === null || val === undefined ? (
                              <span className="italic text-slate-300">null</span>
                            ) : (
                              String(val)
                            )}
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between border-t border-slate-200 bg-white px-6 py-3 text-xs text-slate-500">

          <Button
            variant="outline"
            size="sm"
            onClick={onClose}
            className="h-8 px-4 text-xs font-semibold text-slate-700 hover:bg-slate-100 ml-auto"
          >
            Đóng
          </Button>
        </div>
      </div>
    </div>,
    document.body
  );
}
