'use client';

import { useState, useMemo, useRef, useEffect } from 'react';
import {
  ShieldAlert,
  Search,
  ChevronDown,
  Sparkles,
  SlidersHorizontal,
  Check,
  CheckCircle2,
  X
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import type { FindingItem } from '@/lib/api-bridge';

export interface AuditFindingsTableProps {
  findings: FindingItem[];
  onInvestigate: (findingId: string) => void;
  onAskAi: (finding: FindingItem) => void;
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
            ? 'border-blue-300 bg-blue-50/40 text-blue-900'
            : 'border-slate-200 bg-white text-slate-700 hover:border-slate-300'
        }`}
      >
        {icon}
        <span>{displayLabel}</span>
        <ChevronDown size={13} className={`text-slate-400 transition-transform ${open ? 'rotate-180' : ''}`} />
      </button>

      {open && (
        <div className="absolute right-0 mt-1.5 min-w-[170px] rounded-xl border border-slate-200 bg-white py-1.5 shadow-lg z-30 animate-in fade-in-50 zoom-in-95 duration-150">
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
                    ? 'bg-blue-50 text-blue-700 font-semibold'
                    : 'text-slate-700 hover:bg-slate-50'
                }`}
              >
                <span>{opt.label}</span>
                {isSelected && <Check size={13} className="text-blue-600" />}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}

export function AuditFindingsTable({
  findings,
  onInvestigate,
  onAskAi,
}: AuditFindingsTableProps) {
  // Filters state
  const [searchText, setSearchText] = useState('');
  const [selectedStatus, setSelectedStatus] = useState('ALL');
  const [selectedSeverity, setSelectedSeverity] = useState('ALL');
  const [selectedZone, setSelectedZone] = useState('ALL');
  const [selectedSort, setSelectedSort] = useState('newest');

  // Filter & Sort logic
  const filteredAndSortedFindings = useMemo(() => {
    let result = [...findings];

    // Search text filter
    if (searchText.trim()) {
      const term = searchText.trim().toLowerCase();
      result = result.filter(
        (f) =>
          f.finding_id.toLowerCase().includes(term) ||
          (f.rule_id && f.rule_id.toLowerCase().includes(term)) ||
          (f.column_name && f.column_name.toLowerCase().includes(term)) ||
          (f.reason && f.reason.toLowerCase().includes(term)) ||
          (f.subject_zone && f.subject_zone.toLowerCase().includes(term)) ||
          (f.policy_name && f.policy_name.toLowerCase().includes(term))
      );
    }

    // Status filter
    if (selectedStatus !== 'ALL') {
      result = result.filter((f) => f.status === selectedStatus);
    }

    // Severity filter
    if (selectedSeverity !== 'ALL') {
      result = result.filter((f) => f.severity === selectedSeverity);
    }

    // Zone filter
    if (selectedZone !== 'ALL') {
      result = result.filter((f) => (f.subject_zone || 'VN') === selectedZone);
    }

    // Sorting
    result.sort((a, b) => {
      if (selectedSort === 'newest') {
        const tA = (a as any).detected_at ? new Date((a as any).detected_at).getTime() : 0;
        const tB = (b as any).detected_at ? new Date((b as any).detected_at).getTime() : 0;
        return tB - tA;
      }
      if (selectedSort === 'oldest') {
        const tA = (a as any).detected_at ? new Date((a as any).detected_at).getTime() : 0;
        const tB = (b as any).detected_at ? new Date((b as any).detected_at).getTime() : 0;
        return tA - tB;
      }
      if (selectedSort === 'records_desc') {
        return (b.failed_record_count || 0) - (a.failed_record_count || 0);
      }
      if (selectedSort === 'severity') {
        const score: Record<string, number> = { CRITICAL: 4, HIGH: 3, MEDIUM: 2, LOW: 1 };
        return (score[b.severity] || 0) - (score[a.severity] || 0);
      }
      return 0;
    });

    return result;
  }, [findings, searchText, selectedStatus, selectedSeverity, selectedZone, selectedSort]);

  return (
    <div className="rounded-2xl border border-slate-200/90 bg-white p-6 shadow-xs space-y-4">
      {/* 1. Header (Excluded 'Xuất báo cáo' button as requested) */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <ShieldAlert className="size-5 text-rose-500 shrink-0" />
          <h3 className="text-base font-bold text-slate-900 tracking-tight">
            Chi tiết vấn đề kiểm toán & đề xuất xử lý ({findings.length} findings)
          </h3>
        </div>
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
            placeholder="Tìm kiếm finding, rule, cột..."
            className="h-9 w-full rounded-xl border border-slate-200 bg-white pl-9.5 pr-4 text-xs text-slate-800 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 shadow-2xs transition-colors"
          />
          {searchText && (
            <button
              type="button"
              onClick={() => setSearchText('')}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
            >
              <X size={13} />
            </button>
          )}
        </div>

        {/* Filter & Sort dropdowns */}
        <div className="flex flex-wrap items-center gap-2">
          <FilterDropdown
            label="Trạng thái"
            value={selectedStatus}
            options={[
              { value: 'ALL', label: 'Tất cả trạng thái' },
              { value: 'OPEN', label: 'OPEN' },
              { value: 'IN_REVIEW', label: 'IN_REVIEW' },
              { value: 'REMEDIATED', label: 'REMEDIATED' },
              { value: 'OVERRIDDEN', label: 'OVERRIDDEN' },
              { value: 'RESOLVED', label: 'RESOLVED' },
            ]}
            onChange={setSelectedStatus}
          />

          <FilterDropdown
            label="Mức độ"
            value={selectedSeverity}
            options={[
              { value: 'ALL', label: 'Tất cả mức độ' },
              { value: 'CRITICAL', label: 'CRITICAL' },
              { value: 'HIGH', label: 'HIGH' },
              { value: 'MEDIUM', label: 'MEDIUM' },
              { value: 'LOW', label: 'LOW' },
            ]}
            onChange={setSelectedSeverity}
          />

          <FilterDropdown
            label="Zone"
            value={selectedZone}
            options={[
              { value: 'ALL', label: 'Tất cả Zone' },
              { value: 'EU', label: 'EU' },
              { value: 'VN', label: 'VN' },
              { value: 'US', label: 'US' },
              { value: 'GLOBAL', label: 'GLOBAL' },
            ]}
            onChange={setSelectedZone}
          />

          <FilterDropdown
            label="Mới nhất"
            icon={<SlidersHorizontal size={13} className="text-slate-500" />}
            value={selectedSort}
            options={[
              { value: 'newest', label: 'Mới nhất' },
              { value: 'oldest', label: 'Cũ nhất' },
              { value: 'records_desc', label: 'Bản ghi nhiều nhất' },
              { value: 'severity', label: 'Nghiêm trọng nhất' },
            ]}
            onChange={setSelectedSort}
          />
        </div>
      </div>

      {/* 3. Findings Table */}
      {findings.length === 0 ? (
        <div className="rounded-2xl border border-emerald-200 bg-emerald-50/40 p-8 text-center space-y-2">
          <CheckCircle2 className="size-8 text-emerald-600 mx-auto" />
          <h4 className="text-sm font-bold text-emerald-950">
            Không phát hiện vi phạm kiểm toán nào cho lượt chạy này
          </h4>
          <p className="text-xs text-emerald-800 max-w-md mx-auto">
            100% dữ liệu đã vượt qua các cổng kiểm soát L1-L4 và Policy Gate. Bằng chứng kiểm toán hợp lệ đã được lưu trữ vào sổ cái bất biến.
          </p>
        </div>
      ) : filteredAndSortedFindings.length === 0 ? (
        <div className="rounded-xl border border-slate-200 bg-slate-50/50 p-8 text-center space-y-2 text-xs text-slate-500">
          <p className="font-semibold text-slate-700">Không tìm thấy finding nào phù hợp với bộ lọc</p>
          <p>Vui lòng thử tìm kiếm với từ khóa khác hoặc thiết lập lại bộ lọc.</p>
          <Button
            size="sm"
            variant="outline"
            onClick={() => {
              setSearchText('');
              setSelectedStatus('ALL');
              setSelectedSeverity('ALL');
              setSelectedZone('ALL');
            }}
            className="mt-2 h-7 text-xs"
          >
            Đặt lại bộ lọc
          </Button>
        </div>
      ) : (
        <div className="overflow-x-auto rounded-xl border border-slate-200/80 bg-white">
          <table className="w-full text-left text-xs border-collapse">
            <thead>
              <tr className="border-b border-slate-200/80 bg-white text-slate-600 font-semibold text-[11px]">
                <th className="py-3 px-3 whitespace-nowrap">
                  <div className="flex items-center gap-1 text-slate-700">
                    <span>ID</span>
                  </div>
                </th>
                <th className="py-3 px-3 whitespace-nowrap text-slate-700">Mức độ</th>
                <th className="py-3 px-3 text-slate-700 min-w-[280px]">Mô tả</th>
                <th className="py-3 px-3 whitespace-nowrap text-slate-700">Cột chính</th>
                <th className="py-3 px-3 whitespace-nowrap text-slate-700">Bản ghi</th>
                <th className="py-3 px-3 whitespace-nowrap text-slate-700">Zone</th>
                <th className="py-3 px-3 whitespace-nowrap">
                  <div className="flex items-center gap-1 text-slate-700">
                    <span>Trạng thái</span>
                  </div>
                </th>
                <th className="py-3 px-3 whitespace-nowrap text-slate-700 text-center">Thao tác</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {filteredAndSortedFindings.map((f) => {
                const sevUpper = (f.severity || 'CRITICAL').toUpperCase();
                const zoneDisplay = f.subject_zone || 'VN';

                return (
                  <tr
                    key={f.finding_id}
                    onClick={() => onInvestigate(f.finding_id)}
                  >
                    {/* ID */}
                    <td className="py-3 px-3 whitespace-nowrap">
                      <span className="font-mono text-xs font-semibold text-blue-600 hover:text-blue-800 hover:underline">
                        {f.finding_id}
                      </span>
                    </td>

                    {/* Mức độ (Severity Badge) */}
                    <td className="py-3 px-3 whitespace-nowrap">
                      <span
                        className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-[10px] font-extrabold uppercase tracking-wide border ${
                          sevUpper === 'CRITICAL'
                            ? 'bg-rose-50 text-rose-600 border-rose-100'
                            : sevUpper === 'HIGH'
                            ? 'bg-amber-50 text-amber-600 border-amber-100'
                            : sevUpper === 'MEDIUM'
                            ? 'bg-sky-50 text-sky-600 border-sky-100'
                            : 'bg-slate-100 text-slate-600 border-slate-200'
                        }`}
                      >
                        {sevUpper}
                      </span>
                    </td>

                    {/* Mô tả (Description / Reason) */}
                    <td className="py-3 px-3 text-slate-800 leading-relaxed font-normal">
                      <span className="line-clamp-2" title={f.reason}>
                        {f.reason}
                      </span>
                    </td>

                    {/* Cột chính (Column name) */}
                    <td className="py-3 px-3 whitespace-nowrap">
                      <span className="font-mono text-xs text-slate-600">
                        {f.column_name || '—'}
                      </span>
                    </td>

                    {/* Bản ghi (Failed record count) */}
                    <td className="py-3 px-3 whitespace-nowrap">
                      <span className="font-bold text-xs text-slate-900">
                        {f.failed_record_count ? f.failed_record_count.toLocaleString('vi-VN') : 0}
                      </span>
                    </td>

                    {/* Zone */}
                    <td className="py-3 px-3 whitespace-nowrap">
                      <span className="inline-flex items-center px-2 py-0.5 rounded-md text-[10px] font-bold font-mono bg-[#f5f3ff] text-[#7c3aed] border border-[#ede9fe]">
                        {zoneDisplay}
                      </span>
                    </td>

                    {/* Trạng thái (Status) */}
                    <td className="py-3 px-3 whitespace-nowrap">
                      <span
                        className={`inline-flex items-center px-2.5 py-0.5 rounded-md text-[10px] font-bold border ${
                          f.status === 'OPEN'
                            ? 'bg-[#eff6ff] text-[#2563eb] border-[#dbeafe]'
                            : f.status === 'IN_REVIEW'
                            ? 'bg-amber-50 text-amber-700 border-amber-200'
                            : f.status === 'REMEDIATED'
                            ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                            : f.status === 'OVERRIDDEN'
                            ? 'bg-fuchsia-50 text-fuchsia-700 border-fuchsia-200'
                            : 'bg-slate-100 text-slate-600 border-slate-200'
                        }`}
                      >
                        {f.status || 'OPEN'}
                      </span>
                    </td>

                    {/* Thao tác (Actions) */}
                    <td
                      className="py-3 px-3 whitespace-nowrap text-center"
                      onClick={(e) => e.stopPropagation()}
                    >
                      <div className="flex items-center justify-center gap-2">
                        {/* 1. Ai giải thích */}
                        <button
                          type="button"
                          onClick={() => onAskAi(f)}
                          title="Gửi câu hỏi nhờ AI Companion giải thích chi tiết"
                          className="h-7.5 px-2.5 rounded-lg border border-slate-200/90 bg-white hover:bg-slate-50 text-slate-700 text-xs font-medium flex items-center gap-1.5 shadow-2xs transition-colors cursor-pointer"
                        >
                          <Sparkles size={13} className="text-[#04D3D4]" />
                          <span>Ai giải thích</span>
                        </button>

                        {/* 2. Điều tra */}
                        <button
                          type="button"
                          onClick={() => onInvestigate(f.finding_id)}
                          title="Mở giao diện điều tra chi tiết"
                          className="h-7.5 px-2.5 rounded-lg border border-slate-200/90 bg-white hover:bg-slate-50 text-slate-700 text-xs font-medium flex items-center gap-1.5 shadow-2xs transition-colors cursor-pointer"
                        >
                          <Search size={13} className="text-slate-600" />
                          <span>Điều tra</span>
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
