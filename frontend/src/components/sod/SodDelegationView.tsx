import React, { useState } from 'react';
import { useAuthStore } from '@/src/stores/authStore';
import { ROLES, ROLE_KEYS, type RoleKey } from '@/src/lib/sod/catalog';
import {
  UserCheck,
  Calendar,
  PlusCircle,
  CheckCircle2,
  Shield,
} from 'lucide-react';

interface DelegationItem {
  id: string;
  delegatorName: string;
  delegatorRole: RoleKey;
  delegateName: string;
  delegateRole: RoleKey;
  startDate: string;
  endDate: string;
  status: 'ACTIVE' | 'SCHEDULED' | 'EXPIRED';
  reason: string;
}

const INITIAL_DELEGATIONS: DelegationItem[] = [
  {
    id: 'del_01',
    delegatorName: 'Trần Bình',
    delegatorRole: 'LM',
    delegateName: 'Nguyễn Văn Cường',
    delegateRole: 'LM',
    startDate: '2026-10-14',
    endDate: '2026-10-20',
    status: 'ACTIVE',
    reason: 'Ủy quyền phê duyệt cấp quyền nhân viên trong thời gian công tác nước ngoài.',
  },
  {
    id: 'del_02',
    delegatorName: 'Lê Chi',
    delegatorRole: 'DPO',
    delegateName: 'Phạm Minh Trang',
    delegateRole: 'DPO',
    startDate: '2026-10-25',
    endDate: '2026-10-28',
    status: 'SCHEDULED',
    reason: 'Ủy quyền rà soát PII trong thời gian nghỉ phép.',
  },
];

export function SodDelegationView() {
  const user = useAuthStore((s) => s.user);
  const [delegations, setDelegations] = useState<DelegationItem[]>(INITIAL_DELEGATIONS);
  const [isCreating, setIsCreating] = useState(false);

  // Form fields
  const [delegateName, setDelegateName] = useState('');
  const [delegateRole, setDelegateRole] = useState<RoleKey>((user?.role as RoleKey) || 'LM');
  const [startDate, setStartDate] = useState('2026-10-16');
  const [endDate, setEndDate] = useState('2026-10-23');
  const [reason, setReason] = useState('');
  const [successMsg, setSuccessMsg] = useState('');

  const handleCreate = (e: React.FormEvent) => {
    e.preventDefault();
    if (!delegateName.trim() || !reason.trim()) return;

    const newItem: DelegationItem = {
      id: `del_${Date.now()}`,
      delegatorName: user?.fullName || 'Người dùng',
      delegatorRole: (user?.role as RoleKey) || 'LM',
      delegateName: delegateName.trim(),
      delegateRole,
      startDate,
      endDate,
      status: 'ACTIVE',
      reason: reason.trim(),
    };

    setDelegations([newItem, ...delegations]);
    setIsCreating(false);
    setDelegateName('');
    setReason('');
    setSuccessMsg('Đã thiết lập ủy quyền vắng mặt thành công. Người được ủy quyền sẽ có thể ký duyệt thay bạn!');
    setTimeout(() => setSuccessMsg(''), 4000);
  };

  return (
    <div className="space-y-6">
      {successMsg && (
        <div className="p-3.5 bg-emerald-50 border border-emerald-200 text-emerald-800 rounded-xl text-xs font-semibold flex items-center gap-2">
          <CheckCircle2 size={16} className="text-emerald-600 shrink-0" />
          <span>{successMsg}</span>
        </div>
      )}

      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-white p-4 sm:p-5 rounded-2xl border border-slate-200 shadow-xs">
        <div>
          <div className="flex items-center gap-2">
            <span className="grid size-7 place-items-center rounded-lg bg-teal-50 text-[#008b74] border border-teal-200 font-bold text-xs">
              <UserCheck size={14} />
            </span>
            <h2 className="text-base font-bold text-slate-900">Ủy quyền Vắng mặt (Delegations)</h2>
          </div>
          <p className="text-xs text-slate-500 mt-1">
            Chuyển giao quyền phê duyệt tạm thời cho nhân sự có cùng vai trò chuyên môn khi đi công tác hoặc nghỉ phép.
          </p>
        </div>

        <button
          type="button"
          onClick={() => setIsCreating(!isCreating)}
          className="px-3.5 py-2 rounded-xl bg-slate-900 hover:bg-slate-800 text-[#04D3D4] font-bold text-xs flex items-center gap-1.5 transition cursor-pointer shrink-0"
        >
          <PlusCircle size={14} />
          <span>{isCreating ? 'Hủy biểu mẫu' : 'Thiết lập Ủy quyền Mới'}</span>
        </button>
      </div>

      {/* Create Modal / Form */}
      {isCreating && (
        <div className="bg-white p-6 rounded-2xl border border-teal-200 shadow-md space-y-4">
          <div className="flex items-center gap-2 text-slate-900 font-bold text-sm">
            <Shield size={16} className="text-teal-600" />
            <span>Tạo Ủy quyền Vắng mặt Mới</span>
          </div>

          <form onSubmit={handleCreate} className="space-y-4 text-xs">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <label className="font-semibold text-slate-700">Người được ủy quyền (Cùng vai trò):</label>
                <input
                  type="text"
                  value={delegateName}
                  onChange={(e) => setDelegateName(e.target.value)}
                  placeholder="Nhập họ tên nhân sự được ủy quyền..."
                  className="w-full bg-white border border-slate-200 rounded-xl px-3 py-2 text-xs text-slate-800 focus:outline-hidden focus:border-[#04D3D4]"
                />
              </div>

              <div className="space-y-1.5">
                <label className="font-semibold text-slate-700">Vai trò ủy quyền:</label>
                <select
                  value={delegateRole}
                  onChange={(e) => setDelegateRole(e.target.value as RoleKey)}
                  className="w-full bg-white border border-slate-200 rounded-xl px-3 py-2 text-xs text-slate-800 focus:outline-hidden focus:border-[#04D3D4]"
                >
                  {ROLE_KEYS.map((r) => (
                    <option key={r} value={r}>
                      {ROLES[r].name} ({r})
                    </option>
                  ))}
                </select>
              </div>

              <div className="space-y-1.5">
                <label className="font-semibold text-slate-700">Ngày bắt đầu hiệu lực:</label>
                <input
                  type="date"
                  value={startDate}
                  onChange={(e) => setStartDate(e.target.value)}
                  className="w-full bg-white border border-slate-200 rounded-xl px-3 py-2 text-xs text-slate-800 focus:outline-hidden focus:border-[#04D3D4]"
                />
              </div>

              <div className="space-y-1.5">
                <label className="font-semibold text-slate-700">Ngày kết thúc hiệu lực:</label>
                <input
                  type="date"
                  value={endDate}
                  onChange={(e) => setEndDate(e.target.value)}
                  className="w-full bg-white border border-slate-200 rounded-xl px-3 py-2 text-xs text-slate-800 focus:outline-hidden focus:border-[#04D3D4]"
                />
              </div>
            </div>

            <div className="space-y-1.5">
              <label className="font-semibold text-slate-700">Lý do ủy quyền:</label>
              <textarea
                rows={2}
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                placeholder="Ghi rõ lý do công tác, nghỉ phép..."
                className="w-full bg-white border border-slate-200 rounded-xl p-3 text-xs text-slate-800 focus:outline-hidden focus:border-[#04D3D4]"
              />
            </div>

            <div className="p-3 bg-amber-50 rounded-xl border border-amber-200 text-amber-800 text-[11px] space-y-0.5">
              <strong className="block">Quy tắc Kiểm soát SoD về Ủy quyền:</strong>
              <div>Người được ủy quyền bắt buộc phải có cùng vai trò kỹ thuật hoặc quản lý tương đương. Quyết định phê duyệt sẽ ghi nhận rõ ràng: &ldquo;ký thay mặt&rdquo; để phục vụ kiểm toán.</div>
            </div>

            <div className="flex justify-end gap-2 pt-2">
              <button
                type="button"
                onClick={() => setIsCreating(false)}
                className="px-4 py-2 rounded-xl border border-slate-200 hover:bg-slate-50 text-slate-600 font-semibold cursor-pointer"
              >
                Hủy bỏ
              </button>
              <button
                type="submit"
                className="px-4 py-2 rounded-xl bg-slate-900 hover:bg-slate-800 text-[#04D3D4] font-bold cursor-pointer"
              >
                Xác nhận Thiết lập
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Delegations List */}
      <div className="space-y-3">
        {delegations.map((d) => (
          <div
            key={d.id}
            className="bg-white rounded-2xl border border-slate-200 shadow-xs p-5 flex flex-col sm:flex-row sm:items-center justify-between gap-4"
          >
            <div className="space-y-1.5">
              <div className="flex items-center gap-2">
                <span className="font-bold text-xs text-slate-900">
                  {d.delegatorName} ({d.delegatorRole}) → {d.delegateName} ({d.delegateRole})
                </span>
                <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full border ${
                  d.status === 'ACTIVE'
                    ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                    : 'bg-blue-50 text-blue-700 border-blue-200'
                }`}>
                  {d.status === 'ACTIVE' ? 'Đang hiệu lực' : 'Đã lên lịch'}
                </span>
              </div>
              <p className="text-xs text-slate-600">{d.reason}</p>
              <div className="flex items-center gap-3 text-xs text-slate-400">
                <span className="flex items-center gap-1">
                  <Calendar size={12} />
                  {d.startDate} đến {d.endDate}
                </span>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <span className="text-xs text-slate-400">Mã: {d.id}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
