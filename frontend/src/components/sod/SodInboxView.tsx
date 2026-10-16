import { useState, useEffect, useCallback } from 'react';
import { useAuthStore } from '@/src/stores/authStore';
import { sodApi } from '@/src/services/api';
import {
  Inbox,
  Clock,
  CheckCircle2,
  AlertTriangle,
  RotateCcw,
  XCircle,
  Loader2,
  RefreshCw,
  UserCheck
} from 'lucide-react';

interface PendingTask {
  id: string;
  ticketId: string;
  stepId: string;
  ticketCode: string;
  title: string;
  requester: string;
  roleRequired: string;
  stepAction: string;
  stepIndex: number;
  totalSteps: number;
  slaRemainingHours: number;
  isUrgent: boolean;
  system: string;
  reason: string;
  isDelegated?: boolean;
}

export function SodInboxView() {
  const user = useAuthStore((s) => s.user);
  const [tasks, setTasks] = useState<PendingTask[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [activeTab, setActiveTab] = useState<'pending' | 'handled'>('pending');
  const [actionNotice, setActionNotice] = useState<string | null>(null);
  const [errorNotice, setErrorNotice] = useState<string | null>(null);
  const [operatingTaskId, setOperatingTaskId] = useState<string | null>(null);

  const fetchInbox = useCallback(async () => {
    setIsLoading(true);
    setErrorNotice(null);
    try {
      const rawTasks = await sodApi.getInbox();
      const mapped: PendingTask[] = (rawTasks || []).map((r: any) => ({
        id: r.step_id,
        ticketId: r.ticket_id,
        stepId: r.step_id,
        ticketCode: r.ticket_code,
        title: r.system ? `Xử lý vi phạm / Quyền truy cập: ${r.system}` : (r.purpose || `Phiếu SoD ${r.ticket_code}`),
        requester: r.requester_name || 'Người dùng',
        roleRequired: r.role_code,
        stepAction: r.action === 'A' ? 'Phê duyệt (A)' : r.action === 'R' ? 'Rà soát kiểm soát (R)' : 'Chấp thuận (P)',
        stepIndex: (r.step_idx || 0) + 1,
        totalSteps: 3,
        slaRemainingHours: r.sla_hours || 24,
        isUrgent: r.priority === 'urgent',
        system: r.system || 'Data Lakehouse',
        reason: r.purpose || 'Thẩm tra tuân thủ dữ liệu Quarantine theo quy chế ITGC',
        isDelegated: Boolean(r.is_delegated),
      }));
      setTasks(mapped);
    } catch (err: any) {
      setErrorNotice(err.message || 'Không thể tải danh sách nhiệm vụ từ máy chủ.');
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchInbox();
  }, [fetchInbox, user?.role, user?.user_id]);

  const handleTaskAction = async (task: PendingTask, outcome: 'APPROVE' | 'REJECT' | 'RETURN') => {
    setOperatingTaskId(task.id);
    setActionNotice(null);
    setErrorNotice(null);
    try {
      const comment = outcome === 'APPROVE'
        ? 'Đã phê duyệt từ Hộp việc cá nhân'
        : outcome === 'RETURN'
        ? 'Yêu cầu kiểm tra & đối soát lại'
        : 'Từ chối yêu cầu';

      await sodApi.decideStep(task.ticketId, task.stepId, { outcome, comment });
      const actionText = outcome === 'APPROVE' ? 'Đã phê duyệt' : outcome === 'REJECT' ? 'Đã từ chối' : 'Đã yêu cầu bổ sung';
      setActionNotice(`${actionText} thành công cho phiếu ${task.ticketCode}!`);
      await fetchInbox();
    } catch (err: any) {
      setErrorNotice(err.message || 'Lỗi gửi quyết định phê duyệt');
    } finally {
      setOperatingTaskId(null);
    }
  };

  return (
    <div className="space-y-6">
      {actionNotice && (
        <div className="p-3.5 bg-emerald-50 border border-emerald-200 text-emerald-800 rounded-xl text-xs font-semibold flex items-center gap-2">
          <CheckCircle2 size={16} className="text-emerald-600 shrink-0" />
          <span>{actionNotice}</span>
        </div>
      )}

      {errorNotice && (
        <div className="p-3.5 bg-rose-50 border border-rose-200 text-rose-800 rounded-xl text-xs font-semibold flex items-center gap-2">
          <AlertTriangle size={16} className="text-rose-600 shrink-0" />
          <span>{errorNotice}</span>
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
              {tasks.length} nhiệm vụ chờ
            </span>
          </div>
          <p className="text-xs text-slate-500 mt-1">
            Dữ liệu thời gian thực từ PostgreSQL cho vai trò{' '}
            <strong className="text-slate-700">{user?.role}</strong> ({user?.fullName}).
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={fetchInbox}
            disabled={isLoading}
            className="p-2 rounded-xl border border-slate-200 hover:bg-slate-50 text-slate-600 text-xs font-semibold flex items-center gap-1.5 transition cursor-pointer"
            title="Tải lại hộp việc"
          >
            <RefreshCw size={14} className={isLoading ? 'animate-spin text-teal-600' : ''} />
            <span className="hidden sm:inline">Làm mới</span>
          </button>

          <div className="flex items-center gap-1 bg-slate-100 p-1 rounded-xl text-xs">
            <button
              type="button"
              onClick={() => setActiveTab('pending')}
              className={`px-3 py-1.5 rounded-lg transition font-semibold cursor-pointer ${
                activeTab === 'pending'
                  ? 'bg-white shadow-2xs text-slate-900'
                  : 'text-slate-500 hover:text-slate-800'
              }`}
            >
              Chờ xử lý ({tasks.length})
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
      </div>

      {/* Task Cards */}
      {activeTab === 'pending' && (
        <div className="space-y-4">
          {isLoading && tasks.length === 0 ? (
            <div className="bg-white rounded-2xl border border-slate-200 p-12 text-center space-y-3">
              <Loader2 size={24} className="animate-spin text-teal-600 mx-auto" />
              <p className="text-xs text-slate-500 font-semibold">Đang tải nhiệm vụ từ cơ sở dữ liệu SoD...</p>
            </div>
          ) : tasks.length > 0 ? (
            tasks.map((t) => (
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
                        {t.stepAction} ({t.roleRequired})
                      </span>
                      {t.isDelegated && (
                        <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-indigo-50 text-indigo-700 border border-indigo-200 flex items-center gap-1">
                          <UserCheck size={10} />
                          <span>Được ủy quyền</span>
                        </span>
                      )}
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
                      disabled={operatingTaskId === t.id}
                      onClick={() => handleTaskAction(t, 'APPROVE')}
                      className="px-3.5 py-1.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white font-bold text-xs flex items-center gap-1.5 transition cursor-pointer shadow-2xs"
                    >
                      {operatingTaskId === t.id ? <Loader2 size={13} className="animate-spin" /> : <CheckCircle2 size={13} />}
                      <span>Phê duyệt</span>
                    </button>
                    <button
                      type="button"
                      disabled={operatingTaskId === t.id}
                      onClick={() => handleTaskAction(t, 'RETURN')}
                      className="px-3 py-1.5 rounded-xl bg-amber-50 hover:bg-amber-100 disabled:opacity-50 text-amber-800 border border-amber-200 font-semibold text-xs flex items-center gap-1.5 transition cursor-pointer"
                    >
                      <RotateCcw size={13} />
                      <span>Trả lại</span>
                    </button>
                    <button
                      type="button"
                      disabled={operatingTaskId === t.id}
                      onClick={() => handleTaskAction(t, 'REJECT')}
                      className="px-3 py-1.5 rounded-xl bg-rose-50 hover:bg-rose-100 disabled:opacity-50 text-rose-700 border border-rose-200 font-semibold text-xs flex items-center gap-1.5 transition cursor-pointer"
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
                Tất cả các phiếu yêu cầu thuộc thẩm quyền vai trò {user?.role} đã được xử lý xong trên hệ thống.
              </p>
            </div>
          )}
        </div>
      )}

      {activeTab === 'handled' && (
        <div className="bg-white rounded-2xl border border-slate-200 p-8 text-center text-xs text-slate-500 space-y-2">
          <Clock size={20} className="mx-auto text-slate-400" />
          <p>Lịch sử các phiếu bạn đã phê duyệt hoặc từ chối đã được ghi nhận vào sổ cái kiểm toán bất biến (PostgreSQL).</p>
        </div>
      )}
    </div>
  );
}
