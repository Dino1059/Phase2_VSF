'use client';

import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Play,
  X,
  Database,
  AlertTriangle,
  Loader2,
  ShieldCheck,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { apiBridge, type DatasetCatalogItem } from '@/lib/api-bridge';
import { useAgentStore } from '@/lib/agent-store';

interface StartRunModalProps {
  isOpen: boolean;
  onClose: () => void;
  onRunStarted?: (runId?: string) => void;
  defaultDatasetId?: string;
}

export function StartRunModal({ isOpen, onClose, onRunStarted, defaultDatasetId }: StartRunModalProps) {
  const navigate = useNavigate();
  const currentRole = useAgentStore((s) => s.currentRole);
  const isAuditor = currentRole === 'auditor';

  const [datasets, setDatasets] = useState<DatasetCatalogItem[]>([]);
  const [selectedDataset, setSelectedDataset] = useState<string>(
    defaultDatasetId || 'ride_hailing_xanh_sm_trips'
  );
  // Mặc định luôn chạy tất cả tùy chọn kiểm toán (Evidence & Lineage)
  const collectEvidence = true;
  const generateLineage = true;
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    if (isOpen) {
      apiBridge
        .fetchDatasets()
        .then((items) => {
          if (items && items.length > 0) {
            setDatasets(items);
            if (!defaultDatasetId) {
              setSelectedDataset(items[0].dataset_id);
            }
          }
        })
        .catch((err) => {
          console.warn('Could not fetch datasets:', err);
        });
      setErrorMessage(null);
    }
  }, [isOpen, defaultDatasetId]);

  if (!isOpen) return null;

  const handleStartRun = async () => {
    setIsLoading(true);
    setErrorMessage(null);

    try {
      const res = await apiBridge.createPipelineRun(selectedDataset, {
        collect_evidence: collectEvidence,
        generate_lineage: generateLineage,
      });

      onClose();
      if (onRunStarted) {
        onRunStarted(res.run_id);
      }
      // Chuyển hướng ngay sang màn hình Step 3: Run Monitoring
      navigate(`/runs/${res.run_id}`);
    } catch (err: any) {
      setErrorMessage(err.message || 'Không thể khởi chạy Pipeline. Vui lòng kiểm tra lại dịch vụ.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-xs p-4 animate-in fade-in duration-200">
      <div
        className="w-full max-w-xl rounded-2xl border border-slate-700/80 bg-slate-900 shadow-2xl overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between border-b border-slate-800 px-6 py-4 bg-slate-900/80">
          <div className="flex items-center gap-3">
            <div className="grid size-10 place-items-center rounded-xl bg-cyan-500/10 text-cyan-400 border border-cyan-500/20">
              <Play className="size-5 fill-cyan-400" />
            </div>
            <div>
              <h2 className="text-lg font-bold text-white tracking-tight">
                Khởi chạy Pipeline Kiểm toán
              </h2>
              <p className="text-xs text-slate-400">
                Thực thi 3 làn L1-L4 & Policy song song, phát sinh chữ ký số SOX 404
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-800 hover:text-white transition-colors"
          >
            <X className="size-5" />
          </button>
        </div>

        {/* Content */}
        <div className="p-6 space-y-5">
          {/* Auditor Assurance Notice */}
          {isAuditor && (
            <div className="rounded-xl border border-cyan-500/30 bg-cyan-500/10 p-4 text-xs text-cyan-300 flex items-start gap-3">
              <ShieldCheck className="size-5 shrink-0 text-cyan-400 mt-0.5" />
              <div>
                <p className="font-semibold text-cyan-200">
                  Lượt chạy Kiểm toán Độc lập (Auditor Assurance Run)
                </p>
                <p className="mt-1 text-slate-300">
                  Bạn đang khởi chạy quy trình kiểm tra dữ liệu với thẩm quyền Kiểm toán viên. Toàn bộ chữ ký số và bằng chứng sẽ được ghi nhận vào nhật ký kiểm toán độc lập.
                </p>
              </div>
            </div>
          )}

          {errorMessage && (
            <div className="rounded-xl border border-rose-500/30 bg-rose-500/10 p-4 text-xs text-rose-300 flex items-start gap-2.5">
              <AlertTriangle className="size-4 shrink-0 text-rose-400 mt-0.5" />
              <span>{errorMessage}</span>
            </div>
          )}

          {/* Dataset Selector */}
          <div className="space-y-2">
            <label className="text-xs font-semibold text-slate-300 flex items-center justify-between">
              <span className="flex items-center gap-1.5">
                <Database className="size-3.5 text-cyan-400" /> Bộ dữ liệu mục tiêu (Target Dataset)
              </span>
              <span className="text-[11px] text-slate-500">100% dữ liệu thực từ PostgreSQL</span>
            </label>
            <select
              value={selectedDataset}
              onChange={(e) => setSelectedDataset(e.target.value)}
              disabled={isLoading}
              className="w-full rounded-xl border border-slate-700 bg-slate-800/90 px-3.5 py-2.5 text-sm text-white focus:border-cyan-500 focus:outline-none focus:ring-1 focus:ring-cyan-500 disabled:opacity-50"
            >
              {datasets.map((d) => (
                <option key={d.dataset_id} value={d.dataset_id}>
                  {d.name || d.dataset_id} — {d.domain} ({d.row_count ? d.row_count.toLocaleString('vi-VN') : '0'} bản ghi)
                </option>
              ))}
              <option value="ALL">TẤT CẢ CÁC BẢNG (Chạy toàn bộ 8 datasets)</option>
            </select>
          </div>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-3 border-t border-slate-800 px-6 py-4 bg-slate-900/60">
          <Button
            variant="outline"
            onClick={onClose}
            disabled={isLoading}
            className="border-slate-700 text-slate-300 hover:bg-slate-800 hover:text-white"
          >
            Hủy bỏ
          </Button>
          <Button
            onClick={handleStartRun}
            disabled={isLoading}
            className="bg-cyan-500 text-slate-950 font-bold hover:bg-cyan-400 shadow-md shadow-cyan-500/20 disabled:opacity-50 disabled:cursor-not-allowed gap-2"
          >
            {isLoading ? (
              <>
                <Loader2 className="size-4 animate-spin text-slate-950" />
                <span>Đang kích hoạt Airflow…</span>
              </>
            ) : (
              <>
                <Play className="size-4 fill-slate-950" />
                <span>Bắt đầu Chạy Kiểm toán</span>
              </>
            )}
          </Button>
        </div>
      </div>
    </div>
  );
}
