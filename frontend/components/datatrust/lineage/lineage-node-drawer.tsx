'use client';
import { X, ExternalLink, ShieldCheck, Database, Layers, CheckCircle2, AlertOctagon, AlertTriangle, FileText, ArrowRight } from 'lucide-react';
import type { LineageNode } from '@/lib/api-bridge';
import { Button } from '@/components/ui/button';

interface LineageNodeDrawerProps {
  node: LineageNode | null;
  onClose: () => void;
  onSelectNode?: (nodeId: string) => void;
}

export function LineageNodeDrawer({ node, onClose }: LineageNodeDrawerProps) {
  if (!node) return null;

  const getLayerColor = (layer: string) => {
    switch (layer) {
      case 'RAW':
        return 'bg-slate-100 text-slate-700 border-slate-300';
      case 'BRONZE':
        return 'bg-amber-50 text-amber-800 border-amber-300';
      case 'SILVER':
        return 'bg-emerald-50 text-emerald-800 border-emerald-300';
      case 'QUARANTINE':
        return 'bg-rose-50 text-rose-800 border-rose-300';
      case 'WARNING':
        return 'bg-yellow-50 text-yellow-800 border-yellow-300';
      case 'AUDIT':
        return 'bg-teal-50 text-teal-800 border-teal-300';
      case 'EVALUATION':
      case 'TASK':
      default:
        return 'bg-blue-50 text-blue-800 border-blue-300';
    }
  };

  const getLayerIcon = (layer: string) => {
    switch (layer) {
      case 'RAW':
        return FileText;
      case 'BRONZE':
        return Layers;
      case 'SILVER':
        return CheckCircle2;
      case 'QUARANTINE':
        return AlertOctagon;
      case 'WARNING':
        return AlertTriangle;
      case 'AUDIT':
        return ShieldCheck;
      default:
        return Database;
    }
  };

  const Icon = getLayerIcon(node.layer);

  return (
    <div className="fixed inset-y-0 right-0 z-50 flex w-full max-w-md flex-col border-l border-slate-200 bg-white shadow-2xl transition-all">
      {/* Drawer Header */}
      <div className="flex items-center justify-between border-b border-slate-100 px-6 py-4">
        <div className="flex items-center gap-2.5">
          <div className={`flex size-9 items-center justify-center rounded-lg border ${getLayerColor(node.layer)}`}>
            <Icon className="size-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className={`rounded-md border px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider ${getLayerColor(node.layer)}`}>
                {node.layer}
              </span>
              <span className="text-xs text-slate-400">Giai đoạn {node.stage || 1}</span>
            </div>
            <h3 className="text-base font-bold text-slate-900">{node.label || node.name}</h3>
          </div>
        </div>
        <button
          onClick={onClose}
          className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-700"
        >
          <X className="size-5" />
        </button>
      </div>

      {/* Drawer Body */}
      <div className="flex-1 space-y-6 overflow-y-auto px-6 py-5">
        {/* Node Metadata */}
        <div>
          <h4 className="text-[11px] font-bold uppercase tracking-wider text-slate-400">
            Thông tin thực thể (OpenLineage Entity)
          </h4>
          <div className="mt-2.5 space-y-2 rounded-xl border border-slate-100 bg-slate-50/70 p-3.5 text-xs">
            <div className="flex justify-between">
              <span className="text-slate-500">Mã định danh (Node ID):</span>
              <span className="font-mono font-medium text-slate-800">{node.id}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-500">Loại thực thể:</span>
              <span className="font-semibold text-slate-800">{node.type === 'job' ? 'Pipeline Task / Job' : 'Dataset'}</span>
            </div>
            {node.operator && (
              <div className="flex justify-between">
                <span className="text-slate-500">Airflow Operator:</span>
                <span className="font-mono text-slate-800">{node.operator}</span>
              </div>
            )}
            <div className="flex justify-between">
              <span className="text-slate-500">Trạng thái:</span>
              <span className="inline-flex items-center gap-1 font-semibold text-emerald-700">
                <span className="size-1.5 rounded-full bg-emerald-500" />
                {node.status}
              </span>
            </div>
            {node.recordCount !== undefined && (
              <div className="flex justify-between">
                <span className="text-slate-500">Số lượng bản ghi:</span>
                <span className="font-bold text-slate-900">{node.recordCount.toLocaleString('vi-VN')} bản ghi</span>
              </div>
            )}
          </div>
        </div>

        {/* Node Description */}
        <div>
          <h4 className="text-[11px] font-bold uppercase tracking-wider text-slate-400">
            Mục đích nghiệp vụ & Tuân thủ
          </h4>
          <p className="mt-2 text-xs leading-relaxed text-slate-600">
            {node.description || 'Thực thể thuộc chu trình xử lý dữ liệu và bảo chứng kiểm toán IPO DataTrust OS.'}
          </p>
        </div>

        {/* Facets & Standards */}
        <div>
          <h4 className="text-[11px] font-bold uppercase tracking-wider text-slate-400">
            OpenLineage Facets & Bảo chứng
          </h4>
          <div className="mt-2.5 space-y-2">
            <div className="rounded-xl border border-emerald-100 bg-emerald-50/40 p-3 text-xs">
              <div className="flex items-center gap-2 text-emerald-800">
                <ShieldCheck className="size-4" />
                <span className="font-bold">Chuẩn OpenLineage 1.0 Specification</span>
              </div>
              <p className="mt-1 text-[11px] text-emerald-700">
                Phát ra tự động qua Airflow OpenLineage Plugin, lưu trữ tại Marquez metadata backend.
              </p>
            </div>

            {node.layer === 'SILVER' && (
              <div className="rounded-xl border border-blue-100 bg-blue-50/40 p-3 text-xs">
                <span className="font-bold text-blue-900">Standard Facet: columnLineage</span>
                <p className="mt-1 text-[11px] text-blue-800">
                  Ánh xạ nguồn gốc cấp trường: che mờ PII SĐT (Luật 91/2025/QH15) và băm định danh (GDPR).
                </p>
              </div>
            )}

            {node.layer === 'AUDIT' && (
              <div className="rounded-xl border border-teal-100 bg-teal-50/40 p-3 text-xs">
                <span className="font-bold text-teal-900">Custom Facet: dataTrustAuditAssurance</span>
                <p className="mt-1 font-mono text-[11px] text-teal-800">
                  Ký số: SIG-AIRFLOW-3LANE-GSM-IPO-2026 kèm SHA-256 continuous hash chain.
                </p>
              </div>
            )}
          </div>
        </div>

        {/* Quick Links */}
        <div className="pt-2">
          <h4 className="text-[11px] font-bold uppercase tracking-wider text-slate-400">
            Hành động nhanh
          </h4>
          <div className="mt-2.5 flex flex-col gap-2">
            <Button
              variant="outline"
              size="sm"
              className="justify-between text-xs"
              onClick={() => window.open('http://localhost:3001', '_blank')}
            >
              <span>Mở trong Marquez Web UI</span>
              <ExternalLink className="size-3.5" />
            </Button>
            {node.layer === 'SILVER' && (
              <Button
                variant="outline"
                size="sm"
                className="justify-between text-xs text-emerald-700 hover:text-emerald-800"
                onClick={() => window.location.href = '/results?tab=silver'}
              >
                <span>Xem dữ liệu bảng Silver</span>
                <ArrowRight className="size-3.5" />
              </Button>
            )}
            {node.layer === 'QUARANTINE' && (
              <Button
                variant="outline"
                size="sm"
                className="justify-between text-xs text-rose-700 hover:text-rose-800"
                onClick={() => window.location.href = '/results?tab=quarantine'}
              >
                <span>Xem hồ sơ vi phạm Quarantine</span>
                <ArrowRight className="size-3.5" />
              </Button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
