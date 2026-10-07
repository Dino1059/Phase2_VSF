'use client';
import { useState, useMemo } from 'react';
import { Database, Search, X } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useAgentStore, type DatasetItem } from '@/lib/agent-store';

interface DatasetSelectorModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSelect?: (datasetId: string) => void;
  initialSelectedId?: string;
}

export function DatasetSelectorModal({
  isOpen,
  onClose,
  onSelect,
  initialSelectedId,
}: DatasetSelectorModalProps) {
  const { datasets, selectedDatasetId, selectDataset, getDatasetMetadataStats } = useAgentStore();
  const [selectedId, setSelectedId] = useState<string>(
    initialSelectedId || selectedDatasetId || ''
  );
  const [searchQuery, setSearchQuery] = useState('');

  // Extract unique real datasets from catalog.datasets
  const datasetList = useMemo(() => {
    const map = new Map<string, DatasetItem>();
    Object.values(datasets || {}).forEach((ds) => {
      if (ds && (ds.id || ds.filename)) {
        const canonicalKey = (ds.id || ds.filename || '').replace('.csv', '');
        if (!map.has(canonicalKey)) {
          map.set(canonicalKey, ds);
        }
      }
    });
    return Array.from(map.values());
  }, [datasets]);

  // Filter datasets based on search input
  const filteredDatasets = useMemo(() => {
    if (!searchQuery.trim()) return datasetList;
    const q = searchQuery.toLowerCase().trim();
    return datasetList.filter(
      (ds) =>
        ds.name?.toLowerCase().includes(q) ||
        ds.title?.toLowerCase().includes(q) ||
        ds.id?.toLowerCase().includes(q) ||
        ds.description?.toLowerCase().includes(q) ||
        ds.source?.toLowerCase().includes(q)
    );
  }, [datasetList, searchQuery]);

  if (!isOpen) return null;

  const handleConfirm = () => {
    if (selectedId) {
      selectDataset(selectedId);
      if (onSelect) onSelect(selectedId);
    }
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-slate-950/40 backdrop-blur-xs transition-opacity"
        onClick={onClose}
      />

      {/* Modal Dialog */}
      <div className="relative z-10 w-full max-w-2xl rounded-2xl border border-slate-200 bg-white p-0 shadow-2xl animate-in fade-in-50 zoom-in-95 duration-200 overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-slate-100 px-6 py-4.5 bg-slate-50/50">
          <div className="flex items-center gap-2.5">
            <span className="grid size-8 place-items-center rounded-xl bg-[#04D3D4]/15 border border-[#04D3D4]/30 text-slate-900 font-bold">
              <Database size={16} className="text-[#04D3D4]" />
            </span>
            <div>
              <h3 className="text-base font-bold text-slate-900">Chọn dataset</h3>
              <p className="text-[11px] text-slate-500">
                Danh mục 8 bộ dữ liệu quản trị từ PostgreSQL
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="grid size-8 place-items-center rounded-lg text-slate-400 hover:bg-slate-100 hover:text-slate-700 transition"
          >
            <X size={18} />
          </button>
        </div>

        {/* Search Bar */}
        <div className="p-4 border-b border-slate-100 bg-white">
          <div className="relative">
            <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 size-4 text-slate-400" />
            <input
              type="text"
              autoFocus
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="🔍 Tìm dataset theo tên bảng, nguồn hoặc mô tả..."
              className="w-full h-10 pl-9.5 pr-4 rounded-xl border border-slate-200 bg-slate-50/70 text-xs font-medium text-slate-900 placeholder:text-slate-400 focus:bg-white focus:outline-none focus:ring-2 focus:ring-[#04D3D4]/40 focus:border-[#04D3D4] transition"
            />
          </div>
        </div>

        {/* Dataset List */}
        <div className="max-h-[360px] overflow-y-auto p-4 space-y-2.5 divide-y divide-slate-100/0">
          {filteredDatasets.length === 0 ? (
            <div className="py-12 text-center text-xs text-slate-400">
              Không tìm thấy dataset nào phù hợp với từ khóa &quot;{searchQuery}&quot;
            </div>
          ) : (
            filteredDatasets.map((ds) => {
              const canonicalId = (ds.id || ds.filename || '').replace('.csv', '');
              const isSelected =
                selectedId === ds.id ||
                selectedId === ds.filename ||
                selectedId.replace('.csv', '') === canonicalId;
              const stats = getDatasetMetadataStats(canonicalId);
              const hasPii = ds.hasPii ?? stats.hasPii;
              const sourceLabel = ds.source || `PostgreSQL (bronze.${canonicalId})`;

              return (
                <div
                  key={canonicalId}
                  onClick={() => setSelectedId(ds.id || canonicalId)}
                  className={`group relative flex items-start gap-3.5 p-3.5 rounded-xl border cursor-pointer transition-all ${
                    isSelected
                      ? 'border-[#04D3D4] bg-[#04D3D4]/5 shadow-xs ring-1 ring-[#04D3D4]/30'
                      : 'border-slate-200/80 bg-white hover:border-slate-300 hover:bg-slate-50/60'
                  }`}
                >
                  {/* Custom Radio Button */}
                  <div className="pt-0.5">
                    <span
                      className={`grid size-4.5 place-items-center rounded-full border transition-all ${
                        isSelected
                          ? 'border-[#04D3D4] bg-[#04D3D4]'
                          : 'border-slate-300 bg-white group-hover:border-slate-400'
                      }`}
                    >
                      {isSelected ? (
                        <span className="size-1.5 rounded-full bg-slate-950" />
                      ) : null}
                    </span>
                  </div>

                  {/* Dataset Details */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between gap-2">
                      <div className="font-mono text-xs font-bold text-slate-900 truncate">
                        {canonicalId}
                      </div>
                      {hasPii && (
                        <span className="rounded bg-rose-50 px-1.5 py-0.5 text-[10px] font-semibold text-rose-700 border border-rose-200">
                          PII Protected
                        </span>
                      )}
                    </div>

                    {/* Metadata line: Source · Records */}
                    <div className="mt-1 flex flex-wrap items-center gap-2 text-[11px] text-slate-500 font-medium">
                      <span>{sourceLabel}</span>
                      <span>·</span>
                      <span className="font-semibold text-slate-700">{(ds.records || 0).toLocaleString()} records</span>
                    </div>

                    {/* Description if present */}
                    {ds.description && (
                      <p className="mt-1.5 text-[11px] text-slate-500 line-clamp-1 leading-relaxed">
                        {ds.description}
                      </p>
                    )}
                  </div>
                </div>
              );
            })
          )}
        </div>

        {/* Footer Actions */}
        <div className="flex items-center justify-end gap-2.5 border-t border-slate-100 bg-slate-50/50 px-6 py-3.5">
          <Button
            variant="outline"
            size="sm"
            onClick={onClose}
            className="h-9 px-4 text-xs font-semibold text-slate-700 hover:bg-slate-100"
          >
            Hủy
          </Button>
          <Button
            size="sm"
            onClick={handleConfirm}
            disabled={!selectedId}
            className="h-9 px-5 text-xs font-bold bg-[#04D3D4] text-slate-950 hover:bg-[#03b8b9] shadow-xs cursor-pointer disabled:opacity-50"
          >
            Chọn dataset
          </Button>
        </div>
      </div>
    </div>
  );
}
