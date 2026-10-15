import { useState } from 'react';
import { useAuthStore } from '@/src/stores/authStore';
import { type RoleKey } from '@/src/lib/sod/catalog';
import {
  Inbox,
  Clock,
  CheckCircle2,
  AlertTriangle,
  RotateCcw,
  XCircle,
} from 'lucide-react';

interface PendingTask {
  id: string;
  ticketCode: string;
  title: string;
  requester: string;
  roleRequired: RoleKey;
  stepAction: string;
  stepIndex: number;
  totalSteps: number;
  slaRemainingHours: number;
  isUrgent: boolean;
  system: string;
  reason: string;
}

const DEMO_TASKS: PendingTask[] = [
  {
    id: 'task_01',
    ticketCode: 'TK-2026-089',
    title: 'Xin cấp quyền truy cập tập dữ liệu EV Telemetry & V-Green Charging',
    requester: 'Nguyễn An (Requestor)',
    roleRequired: 'LM',
    stepAction: 'Phê duyệt nhu cầu nghiệp vụ (A)',
    stepIndex: 2,
    totalSteps: 5,
    slaRemainingHours: 18,
    isUrgent: false,
    system: 'BigQuery Telemetry Warehouse',
    reason: 'Phân tích dữ liệu sạc xe điện V-Green phục vụ tối ưu hóa trạm sạc khu vực Hà Nội.',
  },
  {
    id: 'task_02',
    ticketCode: 'TK-2026-090',
    title: 'Cấp quyền truy xuất danh tính khách hàng Xanh SM (Chứa dữ liệu PII)',
    requester: 'Nguyễn Quốc Bảo (Lead Platform)',
    roleRequired: 'DPO',
    stepAction: 'Phê duyệt tuân thủ dữ liệu PII (A)',
    stepIndex: 3,
    totalSteps: 6,
    slaRemainingHours: 6,
    isUrgent: true,
    system: 'DataTrust Customer Profile Store',
    reason: 'Rà soát tuân thủ Nghị định 13/2023/NĐ-CP và chuẩn bị hồ sơ IPO.',
  },
  {
    id: 'task_03',
    ticketCode: 'TK-2026-091',
    title: 'Phê duyệt ngoại lệ kiểm soát: Cấp quyền khẩn cấp truy cập Core DB',
    requester: 'Ngô Minh (Prod Operator)',
    roleRequired: 'CISO',
    stepAction: 'Phê duyệt ngoại lệ cấp cao (A)',
    stepIndex: 2,
    totalSteps: 4,
    slaRemainingHours: 3,
    isUrgent: true,
    system: 'Core Financial Database',
    reason: 'Khắc phục sự cố tắc nghẽn giao dịch trong ca đêm.',
  },
  {
    id: 'task_04',
    ticketCode: 'TK-2026-092',
    title: 'Rà soát kiểm soát trước thực thi cho bản cập nhật quy tắc ITGC',
    requester: 'Nguyễn Quốc Bảo (Admin)',
    roleRequired: 'AUD',
    stepAction: 'Rà soát trước thực thi (R)',
    stepIndex: 3,
    totalSteps: 4,
    slaRemainingHours: 20,
    isUrgent: false,
    system: 'DataTrust Policy Engine',
    reason: 'Kiểm toán độc lập tính tuân thủ quy tắc kiểm soát chung CNTT.',
  },
];

export function SodInboxView() {
  const user = useAuthStore((s) => s.user);
  const [tasks, setTasks] = useState<PendingTask[]>(DEMO_TASKS);
  const [activeTab, setActiveTab] = useState<'pending' | 'handled'>('pending');
  const [actionNotice, setActionNotice] = useState<string | null>(null);

  // Filter tasks: in demo mode, show matching tasks for user's role or all tasks if Admin/Auditor
  const currentRole = user?.role;
  const filteredTasks = tasks.filter((t) => {
    if (!currentRole) return true;
    if (currentRole === 'ADMIN' || currentRole === 'AUDITOR') return true;
    return t.roleRequired === currentRole;
  });

  const handleTaskAction = (taskId: string, outcome: 'APPROVE' | 'REJECT' | 'RETURN') => {
    const task = tasks.find((t) => t.id === taskId);
    setTasks(tasks.filter((t) => t.id !== taskId));
    const actionText = outcome === 'APPROVE' ? 'Đã phê duyệt' : outcome === 'REJECT' ? 'Đã từ chối' : 'Đã yêu cầu bổ sung';
    setActionNotice(`${actionText} thành công cho phiếu ${task?.ticketCode || taskId}!`);
    setTimeout(() => setActionNotice(null), 3000);
  };

  return (
    <div className="space-y-6">
      {actionNotice && (
        <div className="p-3.5 bg-emerald-50 border border-emerald-200 text-emerald-800 rounded-xl text-xs font-semibold flex items-center gap-2">
          <CheckCircle2 size={16} className="text-emerald-600 shrink-0" />
          <span>{actionNotice}</span>
        </div>
      )}

      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-white p-4 sm:p-5 rounded-2xl border border-slate-200 shadow-xs">
        <div>
          <div className="flex items-center gap-2">
            <span className="grid size-7 place-items-center rounded-lg bg-teal-50 text-[#008b74] border border-teal-200 font-bold text-xs">
              <Inbox size={14} />
            </span>
            <h2 className="text-base font-bold text-slate-900">Hộp việc Cần xử lý (Personal Task Inbox)</h2>
            <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-teal-50 text-teal-700 border border-teal-200">
              {filteredTasks.length} nhiệm vụ chờ
            </span>
          </div>
          <p className="text-xs text-slate-500 mt-1">
            Danh sách phiếu yêu cầu đang chờ thẩm tra hoặc phê duyệt từ vai trò{' '}
            <strong className="text-slate-700">{user?.role}</strong> ({user?.fullName}).
          </p>
        </div>

        <div className="flex items-center gap-2 bg-slate-100 p-1 rounded-xl text-xs">
          <button
            type="button"
            onClick={() => setActiveTab('pending')}
            className={`px-3 py-1.5 rounded-lg transition font-semibold cursor-pointer ${
              activeTab === 'pending'
                ? 'bg-white shadow-2xs text-slate-900'
                : 'text-slate-500 hover:text-slate-800'
            }`}
          >
            Chờ xử lý ({filteredTasks.length})
          </button>
          <button
            type="button"
            onClick={() => setActiveTab('handled')}
            className={`px-3 py-1.5 rounded-lg transition font-semibold cursor-pointer ${
              activeTab === 'handled'
                ? 'bg-white shadow-2xs text-slate-900'
                : 'text-slate-500 hover:text-slate-800'
            }`}
          >
            Đã xử lý
          </button>
        </div>
      </div>

      {/* Task Cards */}
      {activeTab === 'pending' && (
        <div className="space-y-4">
          {filteredTasks.length > 0 ? (
            filteredTasks.map((t) => (
              <div
                key={t.id}
                className="bg-white rounded-2xl border border-slate-200 shadow-xs p-5 space-y-4 hover:shadow-md transition-all"
              >
                <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-3">
                  <div className="space-y-1.5">
                    <div className="flex items-center gap-2.5">
                      <span className="font-mono font-bold text-xs bg-slate-900 text-[#04D3D4] px-2 py-0.5 rounded-md">
                        {t.ticketCode}
                      </span>
                      <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-blue-50 text-blue-700 border border-blue-200">
                        {t.stepAction}
                      </span>
                      {t.isUrgent && (
                        <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-rose-50 text-rose-700 border border-rose-200 animate-pulse flex items-center gap-1">
                          <AlertTriangle size={10} />
                          <span>Sắp hết hạn SLA</span>
                        </span>
                      )}
                    </div>
                    <h3 className="font-bold text-sm text-slate-900">{t.title}</h3>
                    <div className="flex items-center gap-3 text-xs text-slate-500">
                      <span>Người yêu cầu: <strong className="text-slate-700">{t.requester}</strong></span>
                      <span>Hệ thống: <strong className="text-slate-700">{t.system}</strong></span>
                    </div>
                  </div>

                  {/* SLA Countdown pill */}
                  <div className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-xl border border-slate-200 bg-slate-50 text-slate-700 shrink-0">
                    <Clock size={13} className={t.isUrgent ? 'text-rose-600' : 'text-slate-500'} />
                    <span>SLA: còn <strong>{t.slaRemainingHours} giờ</strong></span>
                  </div>
                </div>

                <div className="p-3 bg-slate-50 rounded-xl text-xs text-slate-700 space-y-1 border border-slate-200/80">
                  <span className="text-slate-400 font-semibold block text-[11px]">Nội dung lý do yêu cầu:</span>
                  <p>{t.reason}</p>
                </div>

                {/* Action buttons */}
                <div className="flex items-center justify-between pt-2 border-t border-slate-100">
                  <span className="text-xs text-slate-400">
                    Bước {t.stepIndex}/{t.totalSteps} trong chuỗi RACIX
                  </span>
                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      onClick={() => handleTaskAction(t.id, 'APPROVE')}
                      className="px-3.5 py-1.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-bold text-xs flex items-center gap-1.5 transition cursor-pointer shadow-2xs"
                    >
                      <CheckCircle2 size={13} />
                      <span>Phê duyệt</span>
                    </button>
                    <button
                      type="button"
                      onClick={() => handleTaskAction(t.id, 'RETURN')}
                      className="px-3 py-1.5 rounded-xl bg-amber-50 hover:bg-amber-100 text-amber-800 border border-amber-200 font-semibold text-xs flex items-center gap-1.5 transition cursor-pointer"
                    >
                      <RotateCcw size={13} />
                      <span>Trả lại / Bổ sung</span>
                    </button>
                    <button
                      type="button"
                      onClick={() => handleTaskAction(t.id, 'REJECT')}
                      className="px-3 py-1.5 rounded-xl bg-rose-50 hover:bg-rose-100 text-rose-700 border border-rose-200 font-semibold text-xs flex items-center gap-1.5 transition cursor-pointer"
                    >
                      <XCircle size={13} />
                      <span>Từ chối</span>
                    </button>
                  </div>
                </div>
              </div>
            ))
          ) : (
            <div className="bg-white rounded-2xl border border-slate-200 p-12 text-center space-y-3">
              <div className="size-12 rounded-2xl bg-teal-50 text-teal-600 mx-auto grid place-items-center">
                <CheckCircle2 size={24} />
              </div>
              <h3 className="font-bold text-slate-800 text-sm">Tuyệt vời! Bạn không còn nhiệm vụ nào tồn đọng</h3>
              <p className="text-xs text-slate-500 max-w-sm mx-auto">
                Tất cả các phiếu yêu cầu thuộc thẩm quyền vai trò {user?.role} đã được xử lý xong.
              </p>
            </div>
          )}
        </div>
      )}

      {activeTab === 'handled' && (
        <div className="bg-white rounded-2xl border border-slate-200 p-8 text-center text-xs text-slate-500 space-y-2">
          <Clock size={20} className="mx-auto text-slate-400" />
          <p>Lịch sử 14 phiếu bạn đã phê duyệt hoặc từ chối trong 30 ngày qua đã được lưu vào sổ cái kiểm toán.</p>
        </div>
      )}
    </div>
  );
}
