'use client';

import { useState, useMemo, useRef, useEffect } from 'react';
import {
  AlertTriangle,
  Search,
  ChevronDown,
  Sparkles,
  SlidersHorizontal,
  Check,
  CheckCircle2,
  X,
  FileText,
  Activity,
  Layers,
  Info
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import type { WarningRecord } from '@/lib/api-bridge';

export interface AuditWarningsTableProps {
  warnings: WarningRecord[];
  onAskAi: (warning: WarningRecord) => void;
  onViewDetails?: (warning: WarningRecord) => void;
}

interface FilterDropdownProps {
  label: string;
  icon?: React.ReactNode;
  value: string;
  options: { value: string; label: string }[];
  onChange: (value: string) => void;
}

function FilterDropdown({ label, icon, value, options, onChange }: FilterDropdownProps) {
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    }
    if (open) {
      document.addEventListener('mousedown', handleClickOutside);
      return () => document.removeEventListener('mousedown', handleClickOutside);
    }
  }, [open]);

  const activeOption = options.find((opt) => opt.value === value);
  const displayLabel = value === 'ALL' || !value ? label : activeOption?.label || label;

  return (
    <div className="relative" ref={containerRef}>
      <button
        type="button"
        onClick={() => setOpen((prev) => !prev)}
        className={`h-9 px-3 rounded-xl border text-xs font-medium flex items-center gap-1.5 transition-colors shadow-2xs cursor-pointer ${
          value !== 'ALL' && value !== ''
            ? 'border-amber-300 bg-amber-50/50 text-amber-900'
            : 'border-slate-200 bg-white text-slate-700 hover:border-slate-300'
        }`}
      >
        {icon}
        <span>{displayLabel}</span>
        <ChevronDown size={13} className={`text-slate-400 transition-transform ${open ? 'rotate-180' : ''}`} />
      </button>

      {open && (
        <div className="absolute right-0 mt-1.5 min-w-[180px] rounded-xl border border-slate-200 bg-white py-1.5 shadow-lg z-30 animate-in fade-in-50 zoom-in-95 duration-150">
          {options.map((opt) => {
            const isSelected = opt.value === value;
            return (
              <button
                key={opt.value}
                type="button"
                onClick={() => {
                  onChange(opt.value);
                  setOpen(false);
                }}
                className={`w-full px-3 py-1.5 text-left text-xs flex items-center justify-between transition-colors cursor-pointer ${
                  isSelected
                    ? 'bg-amber-50 text-amber-800 font-semibold'
                    : 'text-slate-700 hover:bg-slate-50'
                }`}
              >
                <span>{opt.label}</span>
                {isSelected && <Check size={13} className="text-amber-600" />}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}

export function AuditWarningsTable({
  warnings,
  onAskAi,
  onViewDetails,
}: AuditWarningsTableProps) {
  // Filters state
  const [searchText, setSearchText] = useState('');
  const [selectedLayer, setSelectedLayer] = useState('ALL');
  const [selectedLane, setSelectedLane] = useState('ALL');
  const [selectedSort, setSelectedSort] = useState('score_desc');
  const [selectedWarningModal, setSelectedWarningModal] = useState<WarningRecord | null>(null);

  // Pagination state (10 records per page for crisp display)
  const [currentPage, setCurrentPage] = useState(1);
  const pageSize = 10;

  // Filter & Sort logic
  const filteredAndSortedWarnings = useMemo(() => {
    let result = [...warnings];

    // Search text filter
    if (searchText.trim()) {
      const term = searchText.trim().toLowerCase();
      result = result.filter(
        (w) =>
          w.warning_id.toLowerCase().includes(term) ||
          (w.warning_type && w.warning_type.toLowerCase().includes(term)) ||
          (w.warning_reason && w.warning_reason.toLowerCase().includes(term)) ||
          (w.source_row_pk && w.source_row_pk.toLowerCase().includes(term)) ||
          (w.dataset_id && w.dataset_id.toLowerCase().includes(term))
      );
    }

    // Layer filter (L1, L2, L3, L4)
    if (selectedLayer !== 'ALL') {
      result = result.filter((w) => (w.signal_layer || 'L2').toUpperCase() === selectedLayer);
    }

    // Lane filter (LANE_A, LANE_B)
    if (selectedLane !== 'ALL') {
      result = result.filter((w) => (w.signal_lane || 'LANE_A').toUpperCase() === selectedLane);
    }

    // Sorting
    result.sort((a, b) => {
      if (selectedSort === 'score_desc') {
        const sA = a.score_or_zvalue ?? 0;
        const sB = b.score_or_zvalue ?? 0;
        return sB - sA;
      }
      if (selectedSort === 'newest') {
        const tA = a.detected_at ? new Date(a.detected_at).getTime() : 0;
        const tB = b.detected_at ? new Date(b.detected_at).getTime() : 0;
        return tB - tA;
      }
      if (selectedSort === 'oldest') {
        const tA = a.detected_at ? new Date(a.detected_at).getTime() : 0;
        const tB = b.detected_at ? new Date(b.detected_at).getTime() : 0;
        return tA - tB;
      }
      return 0;
    });

    return result;
  }, [warnings, searchText, selectedLayer, selectedLane, selectedSort]);

  // Reset pagination on filter change
  useEffect(() => {
    setCurrentPage(1);
  }, [searchText, selectedLayer, selectedLane, selectedSort]);

  const totalPages = Math.max(1, Math.ceil(filteredAndSortedWarnings.length / pageSize));
  const paginatedWarnings = useMemo(() => {
    const start = (currentPage - 1) * pageSize;
    return filteredAndSortedWarnings.slice(start, start + pageSize);
  }, [filteredAndSortedWarnings, currentPage, pageSize]);

  return (
    <div className="rounded-2xl border border-slate-200/90 bg-white p-6 shadow-xs space-y-4">
      {/* 1. Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <AlertTriangle className="size-5 text-amber-500 shrink-0" />
          <h3 className="text-base font-bold text-slate-900 tracking-tight">
            Chi tiết cảnh báo & độ lệch dữ liệu ({warnings.length} warnings)
          </h3>
        </div>
        <span className="text-xs text-slate-500 font-medium hidden sm:inline-flex items-center gap-1.5">
          <Info size={13} className="text-slate-400" />
          <span>Dữ liệu vẫn được lưu vào Silver, cần lưu ý cho mô hình phân tích Gold</span>
        </span>
      </div>

      {/* 2. Filter Toolbar */}
      <div className="flex flex-wrap items-center justify-between gap-3 pt-1">
        {/* Search input */}
        <div className="relative flex-1 min-w-[260px] max-w-sm">
          <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 size-4 text-slate-400" />
          <input
            type="text"
            value={searchText}
            onChange={(e) => setSearchText(e.target.value)}
            placeholder="Tìm kiếm warning, lý do, mã chuyến xe..."
            className="h-9 w-full rounded-xl border border-slate-200 bg-white pl-9.5 pr-4 text-xs text-slate-800 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-amber-500/20 focus:border-amber-500 shadow-2xs transition-colors"
          />
          {searchText && (
            <button
              type="button"
              onClick={() => setSearchText('')}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 cursor-pointer"
            >
              <X size={13} />
            </button>
          )}
        </div>

        {/* Filter & Sort dropdowns */}
        <div className="flex flex-wrap items-center gap-2">
          <FilterDropdown
            label="Tầng kiểm soát"
            icon={<Layers size={13} className="text-slate-500" />}
            value={selectedLayer}
            options={[
              { value: 'ALL', label: 'Tất cả tầng kiểm soát' },
              { value: 'L4', label: 'Lớp L4 (Changepoint Detection)' },
              { value: 'L3', label: 'Lớp L3 (Relational Regression)' },
              { value: 'L2', label: 'Lớp L2 (Robust Drift / Z-Score)' },
              { value: 'L1', label: 'Lớp L1 (Advisory Warning)' },
            ]}
            onChange={setSelectedLayer}
          />

          <FilterDropdown
            label="Làn kiểm soát"
            icon={<Activity size={13} className="text-slate-500" />}
            value={selectedLane}
            options={[
              { value: 'ALL', label: 'Tất cả làn' },
              { value: 'LANE_A', label: 'Làn A (Kỹ thuật / Thống kê)' },
              { value: 'LANE_B', label: 'Làn B (Chính sách / Pháp lý)' },
            ]}
            onChange={setSelectedLane}
          />

          <FilterDropdown
            label="Sắp xếp"
            icon={<SlidersHorizontal size={13} className="text-slate-500" />}
            value={selectedSort}
            options={[
              { value: 'score_desc', label: 'Điểm dị thường cao nhất' },
              { value: 'newest', label: 'Mới nhất' },
              { value: 'oldest', label: 'Cũ nhất' },
            ]}
            onChange={setSelectedSort}
          />
        </div>
      </div>

      {/* 3. Warnings Table */}
      {warnings.length === 0 ? (
        <div className="rounded-2xl border border-emerald-200 bg-emerald-50/40 p-8 text-center space-y-2">
          <CheckCircle2 className="size-8 text-emerald-600 mx-auto" />
          <h4 className="text-sm font-bold text-emerald-950">
            Không ghi nhận cảnh báo trôi dạt dữ liệu nào cho lượt chạy này
          </h4>
          <p className="text-xs text-emerald-800 max-w-md mx-auto">
            Các chỉ số thống kê chuỗi thời gian, hồi quy tương quan và độ phân phối đều nằm hoàn toàn trong ngưỡng an toàn ổn định.
          </p>
        </div>
      ) : filteredAndSortedWarnings.length === 0 ? (
        <div className="rounded-xl border border-slate-200 bg-slate-50/50 p-8 text-center space-y-2 text-xs text-slate-500">
          <p className="font-semibold text-slate-700">Không tìm thấy cảnh báo nào phù hợp với bộ lọc</p>
          <p>Vui lòng thử tìm kiếm với từ khóa khác hoặc thiết lập lại bộ lọc.</p>
          <Button
            size="sm"
            variant="outline"
            onClick={() => {
              setSearchText('');
              setSelectedLayer('ALL');
              setSelectedLane('ALL');
              setSelectedSort('score_desc');
            }}
            className="mt-2 h-7 text-xs"
          >
            Đặt lại bộ lọc
          </Button>
        </div>
      ) : (
        <div className="space-y-3">
          <div className="overflow-x-auto rounded-xl border border-slate-200/80 bg-white">
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="border-b border-slate-200/80 bg-white text-slate-600 font-semibold text-[11px]">
                  <th className="py-3 px-3 whitespace-nowrap">Mã Warning</th>
                  <th className="py-3 px-3 whitespace-nowrap">Tầng / Làn</th>
                  <th className="py-3 px-3 text-slate-700 min-w-[280px]">Mô tả & Lý do cảnh báo</th>
                  <th className="py-3 px-3 whitespace-nowrap text-slate-700">Mã chuyến xe / PK</th>
                  <th className="py-3 px-3 whitespace-nowrap text-slate-700">Điểm dị thường (Score)</th>
                  <th className="py-3 px-3 whitespace-nowrap text-slate-700">Trạng thái dữ liệu</th>
                  <th className="py-3 px-3 whitespace-nowrap text-slate-700 text-center">Thao tác</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {paginatedWarnings.map((w) => {
                  const layerStr = (w.signal_layer || 'L2').toUpperCase();
                  const laneStr = (w.signal_lane || 'LANE_A').toUpperCase();
                  const scoreVal = w.score_or_zvalue !== null && w.score_or_zvalue !== undefined
                    ? Number(w.score_or_zvalue).toFixed(2)
                    : 'N/A';

                  return (
                    <tr
                      key={w.warning_id}
                      className="hover:bg-amber-50/20 transition-colors"
                    >
                      {/* Mã Warning */}
                      <td className="py-3 px-3 whitespace-nowrap">
                        <span className="font-mono text-xs font-semibold text-amber-700">
                          {w.warning_id.length > 12 ? `${w.warning_id.slice(0, 10)}...` : w.warning_id}
                        </span>
                      </td>

                      {/* Tầng & Làn */}
                      <td className="py-3 px-3 whitespace-nowrap">
                        <div className="flex items-center gap-1.5">
                          <span className="inline-flex items-center px-2 py-0.5 rounded-md text-[10px] font-extrabold font-mono bg-amber-50 text-amber-800 border border-amber-200">
                            {layerStr}
                          </span>
                          <span className="inline-flex items-center px-2 py-0.5 rounded-md text-[10px] font-medium bg-slate-100 text-slate-700 border border-slate-200">
                            {laneStr === 'LANE_A' ? 'Lane A (Tech)' : 'Lane B'}
                          </span>
                        </div>
                      </td>

                      {/* Mô tả & Lý do */}
                      <td className="py-3 px-3 text-slate-800 leading-relaxed font-normal">
                        <div className="space-y-0.5">
                          <div className="font-medium text-slate-900 truncate max-w-md" title={w.warning_type}>
                            {w.warning_type}
                          </div>
                          <div className="text-[11px] text-slate-500 line-clamp-1" title={w.warning_reason}>
                            {w.warning_reason}
                          </div>
                        </div>
                      </td>

                      {/* Mã chuyến xe / PK */}
                      <td className="py-3 px-3 whitespace-nowrap">
                        <span className="font-mono text-xs text-slate-600 bg-slate-50 px-2 py-0.5 rounded border border-slate-200/60">
                          {w.source_row_pk || '—'}
                        </span>
                      </td>

                      {/* Điểm dị thường (Score / Z-value) */}
                      <td className="py-3 px-3 whitespace-nowrap">
                        <span className="font-mono font-bold text-xs text-amber-700">
                          {scoreVal}
                        </span>
                      </td>

                      {/* Trạng thái dữ liệu */}
                      <td className="py-3 px-3 whitespace-nowrap">
                        <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-emerald-50 text-emerald-700 border border-emerald-200">
                          <span>✓ Đã nạp Silver</span>
                        </span>
                      </td>

                      {/* Thao tác */}
                      <td className="py-3 px-3 whitespace-nowrap text-center">
                        <div className="flex items-center justify-center gap-2">
                          {/* 1. AI Giải thích */}
                          <button
                            type="button"
                            onClick={() => onAskAi(w)}
                            title="Yêu cầu AI giải thích bản chất cảnh báo này"
                            className="h-7.5 px-2.5 rounded-lg border border-slate-200/90 bg-white hover:bg-slate-50 text-slate-700 text-xs font-medium flex items-center gap-1.5 shadow-2xs transition-colors cursor-pointer"
                          >
                            <Sparkles size={13} className="text-[#04D3D4]" />
                            <span>AI giải thích</span>
                          </button>

                          {/* 2. Xem Bằng chứng */}
                          <button
                            type="button"
                            onClick={() => {
                              setSelectedWarningModal(w);
                              if (onViewDetails) onViewDetails(w);
                            }}
                            title="Xem chi tiết dữ liệu và bằng chứng trôi dạt"
                            className="h-7.5 px-2.5 rounded-lg border border-slate-200/90 bg-white hover:bg-slate-50 text-slate-700 text-xs font-medium flex items-center gap-1.5 shadow-2xs transition-colors cursor-pointer"
                          >
                            <FileText size={13} className="text-slate-600" />
                            <span>Bằng chứng</span>
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {/* Phân trang */}
          {totalPages > 1 && (
            <div className="flex items-center justify-between text-xs text-slate-500 pt-1 px-1">
              <span>
                Hiển thị {((currentPage - 1) * pageSize) + 1} – {Math.min(currentPage * pageSize, filteredAndSortedWarnings.length)} trên tổng số {filteredAndSortedWarnings.length} cảnh báo
              </span>
              <div className="flex items-center gap-1.5">
                <Button
                  size="sm"
                  variant="outline"
                  disabled={currentPage <= 1}
                  onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                  className="h-7 text-xs"
                >
                  Trước
                </Button>
                <span className="px-2 font-medium text-slate-700">
                  {currentPage} / {totalPages}
                </span>
                <Button
                  size="sm"
                  variant="outline"
                  disabled={currentPage >= totalPages}
                  onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
                  className="h-7 text-xs"
                >
                  Sau
                </Button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Warning Evidence Modal */}
      {selectedWarningModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 backdrop-blur-xs p-4 animate-in fade-in-50 duration-200">
          <Card className="max-w-2xl w-full rounded-2xl border border-slate-200 bg-white p-6 shadow-2xl space-y-4 max-h-[85vh] overflow-y-auto">
            <div className="flex items-start justify-between border-b border-slate-100 pb-3">
              <div className="space-y-1">
                <div className="flex items-center gap-2">
                  <span className="text-xs font-bold font-mono px-2 py-0.5 rounded bg-amber-50 text-amber-800 border border-amber-200">
                    {selectedWarningModal.signal_layer || 'L2'}
                  </span>
                  <h4 className="text-sm font-bold text-slate-900">
                    Chi tiết cảnh báo: {selectedWarningModal.warning_id}
                  </h4>
                </div>
                <p className="text-xs text-slate-500">
                  {selectedWarningModal.warning_type} · {selectedWarningModal.dataset_id}
                </p>
              </div>
              <button
                onClick={() => setSelectedWarningModal(null)}
                className="text-slate-400 hover:text-slate-600 cursor-pointer p-1 rounded-lg hover:bg-slate-100"
              >
                <X size={16} />
              </button>
            </div>

            {/* Info grid */}
            <div className="grid grid-cols-2 gap-3 text-xs">
              <div className="p-3 rounded-xl bg-slate-50 border border-slate-100 space-y-1">
                <span className="text-slate-400">Mã chuyến xe (PK)</span>
                <div className="font-mono font-semibold text-slate-800">
                  {selectedWarningModal.source_row_pk || 'N/A'}
                </div>
              </div>
              <div className="p-3 rounded-xl bg-slate-50 border border-slate-100 space-y-1">
                <span className="text-slate-400">Điểm dị thường (Score / Z-value)</span>
                <div className="font-mono font-semibold text-amber-700">
                  {selectedWarningModal.score_or_zvalue !== null && selectedWarningModal.score_or_zvalue !== undefined
                    ? Number(selectedWarningModal.score_or_zvalue).toFixed(2)
                    : 'N/A'}
                </div>
              </div>
            </div>

            {/* Lý do chi tiết */}
            <div className="space-y-1.5 text-xs">
              <span className="font-semibold text-slate-700">Lý do ghi nhận cảnh báo:</span>
              <div className="p-3 rounded-xl bg-amber-50/50 border border-amber-200/60 text-amber-950 font-medium leading-relaxed">
                {selectedWarningModal.warning_reason}
              </div>
            </div>

            {/* Evidence JSON */}
            {selectedWarningModal.evidence_json && Object.keys(selectedWarningModal.evidence_json).length > 0 && (
              <div className="space-y-1.5 text-xs">
                <span className="font-semibold text-slate-700">Bằng chứng thống kê & Thông số phát hiện:</span>
                <pre className="p-3 rounded-xl bg-slate-900 text-slate-100 font-mono text-[11px] overflow-x-auto">
                  {JSON.stringify(selectedWarningModal.evidence_json, null, 2)}
                </pre>
              </div>
            )}

            {/* Redacted Data */}
            {selectedWarningModal.redacted_record_json && Object.keys(selectedWarningModal.redacted_record_json).length > 0 && (
              <div className="space-y-1.5 text-xs">
                <span className="font-semibold text-slate-700">Bản ghi trích mẫu (Đã bảo vệ PII):</span>
                <pre className="p-3 rounded-xl bg-slate-900 text-slate-100 font-mono text-[11px] overflow-x-auto">
                  {JSON.stringify(selectedWarningModal.redacted_record_json, null, 2)}
                </pre>
              </div>
            )}

            <div className="flex justify-end pt-2 border-t border-slate-100">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setSelectedWarningModal(null)}
                className="text-xs"
              >
                Đóng
              </Button>
            </div>
          </Card>
        </div>
      )}
    </div>
  );
}
