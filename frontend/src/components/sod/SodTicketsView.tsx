import React, { useState, useMemo, useEffect, useCallback } from 'react';
import { useAuthStore } from '@/src/stores/authStore';
import { sodApi } from '@/src/services/api';
import {
  ROLES,
  DEFAULT_MATRIX,
  type RoleKey,
  type StepAction,
} from '@/src/lib/sod/catalog';
import { buildChain } from '@/src/lib/sod/chain';
import { emptyForm, type TicketForm } from '@/src/lib/sod/form';
import {
  FileText,
  PlusCircle,
  Clock,
  CheckCircle2,
  XCircle,
  RotateCcw,
  ChevronRight,
  Send,
  Eye,
  ArrowLeft,
  AlertTriangle,
  RefreshCw,
  Loader2,
} from 'lucide-react';

export interface SodTicketItem {
  id: string;
  code: string;
  title: string;
  requester: string;
  requesterRole: string;
  createdAt: string;
  status: 'OPEN' | 'RETURNED' | 'DONE' | 'REJECTED' | 'CANCELLED';
  currentStepIndex: number;
  steps: {
    id?: string;
    idx: number;
    role: RoleKey;
    action: StepAction;
    assigneeName: string;
    assigneeUsername: string;
    status: 'PENDING' | 'CURRENT' | 'APPROVED' | 'REJECTED' | 'RETURNED';
    slaHours: number;
    decisionNote?: string;
    decidedAt?: string;
  }[];
  form: {
    system: string;
    accessLevel: string;
    hasPii: boolean;
    isDbOrAdmin: boolean;
    reason: string;
    durationDays: number;
    finding_id?: string;
  };
  ticketType?: string;
  subject?: {
    finding_id?: string;
    proposal_id?: string;
    proposal_version?: number;
    dataset_id?: string;
    column_name?: string;
    source_hash?: string;
    dry_run_hash?: string;
    expected_rows?: number;
    metadata?: any;
  };
}

export function SodTicketsView() {
  const user = useAuthStore((s) => s.user);

  const [activeTab, setActiveTab] = useState<'list' | 'create'>('list');
  const [tickets, setTickets] = useState<SodTicketItem[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [selectedTicketId, setSelectedTicketId] = useState<string | null>(null);
  const [selectedTicketDetail, setSelectedTicketDetail] = useState<SodTicketItem | null>(null);
  const [isDetailLoading, setIsDetailLoading] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isDeciding, setIsDeciding] = useState(false);
  const [statusFilter, setStatusFilter] = useState<'ALL' | 'OPEN' | 'DONE' | 'REJECTED'>('ALL');

  // Form State for Ticket Creation
  const [formSystem, setFormSystem] = useState('DataTrust OS Data Lakehouse');
  const [formAccessLevel, setFormAccessLevel] = useState('read');
  const [formHasPii, setFormHasPii] = useState(false);
  const [formIsDbOrAdmin, setFormIsDbOrAdmin] = useState(false);
  const [formReason, setFormReason] = useState('');
  const [formDuration, setFormDuration] = useState('30');
  const [decisionComment, setDecisionComment] = useState('');
  const [actionSuccessMsg, setActionSuccessMsg] = useState('');

  const fetchTickets = useCallback(async () => {
    setIsLoading(true);
    setErrorMsg(null);
    try {
      const rawTickets = await sodApi.getTickets();
      const mapped: SodTicketItem[] = (rawTickets || []).map((t: any) => {
        const rawSteps = t.steps || [];
        const steps = rawSteps.map((s: any, idx: number) => ({
          id: s.id,
          idx: s.idx !== undefined ? s.idx : idx,
          role: (s.role || s.role_code || 'REQ') as RoleKey,
          action: (s.action || 'A') as StepAction,
          assigneeName: s.assignee_name || s.assigneeName || ROLES[s.role as RoleKey]?.name || s.role || 'Người xử lý',
          assigneeUsername: s.assignee_username || s.assigneeUsername || (s.role || '').toLowerCase(),
          status: s.status === 'DONE' ? 'APPROVED' : (s.status === 'WAITING' ? 'PENDING' : s.status || 'PENDING'),
          slaHours: s.sla_hours || s.slaHours || 24,
          decisionNote: s.decisionNote,
          decidedAt: s.decidedAt,
        }));

        return {
          id: t.id,
          code: t.code,
          title: t.purpose || `Yêu cầu: ${t.system || 'Hệ thống'} (${t.access_level || 'Truy cập'})`,
          requester: t.requester_name || 'Người dùng',
          requesterRole: t.level === 3 ? 'ADMIN' : 'REQ',
          createdAt: t.created_at ? new Date(t.created_at).toLocaleString('vi-VN') : '',
          status: t.status || 'OPEN',
          currentStepIndex: t.current_step_idx || 0,
          steps,
          form: {
            system: t.system || 'Data Lakehouse',
            accessLevel: t.access_level || 'Đọc (Read)',
            hasPii: Boolean(t.pii),
            isDbOrAdmin: t.level === 3,
            reason: t.purpose || 'Thẩm tra tuân thủ dữ liệu & khắc phục vi phạm',
            durationDays: 30,
            finding_id: t.finding_id,
          },
          ticketType: t.kind || (t.proposal_id ? 'remediation' : 'access'),
          subject: t.proposal_id ? {
            finding_id: t.finding_id,
            proposal_id: t.proposal_id,
            proposal_version: t.proposal_version,
            dataset_id: t.dataset_id,
            column_name: t.column_name,
            source_hash: t.source_hash,
            dry_run_hash: t.dry_run_hash,
          } : undefined,
        };
      });
      setTickets(mapped);
    } catch (err: any) {
      setErrorMsg(err.message || 'Không thể tải danh sách phiếu từ máy chủ.');
    } finally {
      setIsLoading(false);
    }
  }, []);

  const fetchTicketDetail = useCallback(async (ticketId: string) => {
    setIsDetailLoading(true);
    try {
      const t = await sodApi.getTicketDetail(ticketId);
      if (!t) return;
      const rawSteps = t.steps || [];
      const steps = rawSteps.map((s: any, idx: number) => ({
        id: s.id,
        idx: s.idx !== undefined ? s.idx : idx,
        role: (s.role || s.role_code || 'REQ') as RoleKey,
        action: (s.action || 'A') as StepAction,
        assigneeName: s.assignee_name || s.assigneeName || ROLES[s.role as RoleKey]?.name || s.role || 'Người xử lý',
        assigneeUsername: s.assignee_username || s.assigneeUsername || (s.role || '').toLowerCase(),
        status: s.status === 'DONE' ? 'APPROVED' : (s.status === 'WAITING' ? 'PENDING' : s.status || 'PENDING'),
        slaHours: s.sla_hours || s.slaHours || 24,
        decisionNote: s.decisionNote,
        decidedAt: s.decidedAt,
      }));

      const item: SodTicketItem = {
        id: t.id,
        code: t.code,
        title: t.form?.mucDich || `Yêu cầu: ${t.form?.rows?.[0]?.heThong || t.form?.system || 'Hệ thống'} (${t.form?.rows?.[0]?.mucQuyen || t.form?.access_level || 'Truy cập'})`,
        requester: t.requester_name || 'Người dùng',
        requesterRole: t.level === 3 ? 'ADMIN' : 'REQ',
        createdAt: t.created_at ? new Date(t.created_at).toLocaleString('vi-VN') : '',
        status: t.status || 'OPEN',
        currentStepIndex: t.current_step_idx || 0,
        steps,
        form: {
          system: t.form?.rows?.[0]?.heThong || t.form?.system || 'Data Lakehouse',
          accessLevel: t.form?.rows?.[0]?.mucQuyen || t.form?.access_level || 'Đọc (Read)',
          hasPii: Boolean(t.pii),
          isDbOrAdmin: t.level === 3,
          reason: t.form?.mucDich || t.form?.reason || 'Thẩm tra tuân thủ dữ liệu & khắc phục vi phạm',
          durationDays: 30,
          finding_id: t.subject?.finding_id || t.form?.finding_id,
        },
        ticketType: t.kind || (t.subject?.proposal_id ? 'remediation' : 'access'),
        subject: t.subject,
      };
      setSelectedTicketDetail(item);
    } catch (err: any) {
      console.error('Error fetching ticket detail:', err);
    } finally {
      setIsDetailLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchTickets();
  }, [fetchTickets, user?.role, user?.user_id]);

  useEffect(() => {
    if (selectedTicketId) {
      fetchTicketDetail(selectedTicketId);
    } else {
      setSelectedTicketDetail(null);
    }
  }, [selectedTicketId, fetchTicketDetail]);

  const selectedTicket = selectedTicketDetail || tickets.find((t) => t.id === selectedTicketId);

  // Dynamic Live Preview of the RACIX Approval Chain
  const localPreviewChain = useMemo(() => {
    const d: TicketForm = {
      ...emptyForm(user?.fullName || 'Người dùng', user?.email || 'user@company.vn'),
      loaiPhieu: 'new',
      khan: formDuration === '1' ? 'urgent' : 'normal',
      capBac: 'T3',
      thiTruong: 'vn',
      camKet: true,
      dlcn: formHasPii ? 'basic' : 'none',
      signature: 'data:image/png;base64,mock',
      rows: [
        {
          heThong: formSystem,
          taiNguyen: formReason || 'Yêu cầu cấp quyền công việc',
          mucQuyen: formIsDbOrAdmin ? 'Full' : formAccessLevel === 'write' ? 'RW' : 'RO',
          tang: formIsDbOrAdmin ? '3' : '2',
          thoiHan: formDuration === '1' ? '2026-12-31' : '2027-06-30',
        },
      ],
    };

    try {
      const people = [
        { id: 'an.nguyen', name: 'Nguyễn An', roles: ['REQ'] as RoleKey[] },
        { id: 'binh.tran', name: 'Trần Bình', roles: ['LM'] as RoleKey[] },
        { id: 'chi.le', name: 'Lê Chi', roles: ['DPO'] as RoleKey[] },
        { id: 'son.ho', name: 'Hồ Sơn', roles: ['SO'] as RoleKey[] },
        { id: 'giang.hoang', name: 'Hoàng Giang', roles: ['CISO'] as RoleKey[] },
        { id: 'ha.vu', name: 'Vũ Hà', roles: ['IAM'] as RoleKey[] },
        { id: 'khoa.do', name: 'Đỗ Khoa', roles: ['DEV'] as RoleKey[] },
        { id: 'lan.bui', name: 'Bùi Lan', roles: ['REL'] as RoleKey[] },
        { id: 'minh.ngo', name: 'Ngô Minh', roles: ['OPS'] as RoleKey[] },
        { id: 'hoang.tran', name: 'Trần Minh Hoàng', roles: ['AUDITOR'] as RoleKey[] },
      ];
      return buildChain(d, user?.username || 'an.nguyen', people, DEFAULT_MATRIX);
    } catch {
      return null;
    }
  }, [formSystem, formAccessLevel, formHasPii, formIsDbOrAdmin, formReason, formDuration, user]);
  const [serverPreviewChain, setServerPreviewChain] = useState<any>(null);
  const [previewError, setPreviewError] = useState('');
  useEffect(() => {
    const timer = window.setTimeout(() => {
      const form = {
        ...emptyForm(user?.fullName || '', user?.email || ''), loaiPhieu: 'new',
        khan: formDuration === '1' ? 'urgent' : 'normal', capBac: 'T3', thiTruong: 'vn', camKet: true,
        dlcn: formHasPii ? 'basic' : 'none', mucDich: formReason,
        rows: [{ heThong: formSystem, taiNguyen: formReason, mucQuyen: formIsDbOrAdmin ? 'Full' : formAccessLevel === 'write' ? 'RW' : 'RO', tang: formIsDbOrAdmin ? '3' : '2', thoiHan: '' }],
      };
      sodApi.previewChain({ form }).then(setServerPreviewChain)
        .catch((e) => { setServerPreviewChain(null); setPreviewError(e instanceof Error ? e.message : String(e)); });
    }, 300);
    return () => window.clearTimeout(timer);
  }, [formSystem, formAccessLevel, formHasPii, formIsDbOrAdmin, formReason, formDuration, user]);
  void localPreviewChain;
  void previewError;
  const previewChain = serverPreviewChain;

  const handleCreateTicketSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formReason.trim()) return;

    setIsSubmitting(true);
    setErrorMsg(null);
    try {
      const d: TicketForm = {
        ...emptyForm(user?.fullName || 'Người dùng', user?.email || 'user@company.vn'),
        loaiPhieu: 'new',
        khan: formDuration === '1' ? 'urgent' : 'normal',
        capBac: 'T3',
        thiTruong: 'vn',
        camKet: true,
        dlcn: formHasPii ? 'basic' : 'none',
        mucDich: formReason,
        signature: 'data:image/png;base64,mock',
        rows: [
          {
            heThong: formSystem,
            taiNguyen: formReason || 'Yêu cầu cấp quyền công việc',
            mucQuyen: formIsDbOrAdmin ? 'Full' : formAccessLevel === 'write' ? 'RW' : 'RO',
            tang: formIsDbOrAdmin ? '3' : '2',
            thoiHan: formDuration === '1' ? '2026-12-31' : '2027-06-30',
          },
        ],
      };

      const res = await sodApi.createTicket({ form: d });
      await fetchTickets();
      if (res?.id) {
        setSelectedTicketId(res.id);
      }
      setActiveTab('list');
      setActionSuccessMsg(`Đã tạo thành công phiếu ${res?.code || 'mới'}! Chuỗi phê duyệt tuần tự đã được kích hoạt trong PostgreSQL.`);
      setTimeout(() => setActionSuccessMsg(''), 4000);
    } catch (err: any) {
      setErrorMsg(err.message || 'Lỗi tạo phiếu yêu cầu cấp quyền trên hệ thống.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDecision = async (outcome: 'APPROVED' | 'REJECTED' | 'RETURNED') => {
    if (!selectedTicket) return;

    const currentStep = selectedTicket.steps.find((s) => s.status === 'CURRENT') || selectedTicket.steps[selectedTicket.currentStepIndex];
    if (!currentStep || !currentStep.id) {
      setErrorMsg('Không tìm thấy định danh bước duyệt cần xử lý.');
      return;
    }

    setIsDeciding(true);
    setErrorMsg(null);
    try {
      const backendOutcome = outcome === 'APPROVED' ? 'APPROVE' : outcome === 'REJECTED' ? 'REJECT' : 'RETURN';
      const comment = decisionComment || (outcome === 'APPROVED' ? 'Đồng ý phê duyệt' : outcome === 'RETURNED' ? 'Yêu cầu kiểm tra & đối soát lại' : 'Từ chối');

      await sodApi.decideStep(selectedTicket.id, currentStep.id, {
        outcome: backendOutcome,
        comment,
      });

      await fetchTicketDetail(selectedTicket.id);
      await fetchTickets();
      setDecisionComment('');
      setActionSuccessMsg(`Đã ghi nhận quyết định: ${outcome === 'APPROVED' ? 'Đã duyệt' : outcome === 'REJECTED' ? 'Đã từ chối' : 'Yêu cầu bổ sung'}`);
      setTimeout(() => setActionSuccessMsg(''), 3000);
    } catch (err: any) {
      setErrorMsg(err.message || 'Lỗi gửi quyết định phê duyệt tới máy chủ.');
    } finally {
      setIsDeciding(false);
    }
  };

  const filteredTickets = tickets.filter((t) => {
    if (statusFilter === 'ALL') return true;
    return t.status === statusFilter;
  });

  return (
    <div className="space-y-6">
      {actionSuccessMsg && (
        <div className="p-3.5 bg-emerald-50 border border-emerald-200 text-emerald-800 rounded-xl text-xs font-semibold flex items-center gap-2">
          <CheckCircle2 size={16} className="text-emerald-600 shrink-0" />
          <span>{actionSuccessMsg}</span>
        </div>
      )}

      {errorMsg && (
        <div className="p-3.5 bg-rose-50 border border-rose-200 text-rose-800 rounded-xl text-xs font-semibold flex items-center gap-2">
          <AlertTriangle size={16} className="text-rose-600 shrink-0" />
          <span>{errorMsg}</span>
        </div>
      )}

      {/* View Header with Sub-tabs */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-white p-4 rounded-2xl border border-slate-200 shadow-xs">
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={() => {
              setActiveTab('list');
              setSelectedTicketId(null);
            }}
            className={`px-3.5 py-2 rounded-xl text-xs font-bold transition cursor-pointer flex items-center gap-1.5 ${
              activeTab === 'list' && !selectedTicketId
                ? 'bg-slate-900 text-[#04D3D4] shadow-xs'
                : 'text-slate-600 hover:bg-slate-100'
            }`}
          >
            <FileText size={14} />
            <span>Tất cả Phiếu Yêu cầu ({tickets.length})</span>
          </button>
          <button
            type="button"
            onClick={() => {
              setActiveTab('create');
              setSelectedTicketId(null);
            }}
            className={`px-3.5 py-2 rounded-xl text-xs font-bold transition cursor-pointer flex items-center gap-1.5 ${
              activeTab === 'create'
                ? 'bg-[#04D3D4] text-slate-950 shadow-xs'
                : 'text-slate-600 hover:bg-slate-100'
            }`}
          >
            <PlusCircle size={14} />
            <span>Tạo Phiếu Cấp quyền Mới</span>
          </button>
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={fetchTickets}
            disabled={isLoading}
            className="p-2 rounded-xl border border-slate-200 hover:bg-slate-50 text-slate-600 text-xs font-semibold flex items-center gap-1.5 transition cursor-pointer disabled:opacity-50"
            title="Tải lại danh sách"
          >
            <RefreshCw size={14} className={isLoading ? 'animate-spin text-teal-600' : ''} />
            <span className="hidden sm:inline">Làm mới</span>
          </button>

          {activeTab === 'list' && !selectedTicketId && (
            <div className="flex items-center gap-1 bg-slate-100 p-1 rounded-xl text-xs">
              <button
                type="button"
                onClick={() => setStatusFilter('ALL')}
                className={`px-2.5 py-1 rounded-lg transition ${statusFilter === 'ALL' ? 'bg-white shadow-2xs font-bold text-slate-900' : 'text-slate-500'}`}
              >
                Tất cả
              </button>
              <button
                type="button"
                onClick={() => setStatusFilter('OPEN')}
                className={`px-2.5 py-1 rounded-lg transition ${statusFilter === 'OPEN' ? 'bg-white shadow-2xs font-bold text-blue-700' : 'text-slate-500'}`}
              >
                Đang xử lý
              </button>
              <button
                type="button"
                onClick={() => setStatusFilter('DONE')}
                className={`px-2.5 py-1 rounded-lg transition ${statusFilter === 'DONE' ? 'bg-white shadow-2xs font-bold text-emerald-700' : 'text-slate-500'}`}
              >
                Hoàn tất
              </button>
            </div>
          )}
        </div>
      </div>

      {/* TAB 1: TICKETS LIST & DETAIL */}
      {activeTab === 'list' && (
        <>
          {selectedTicket ? (
            /* DETAIL VIEW */
            <div className="space-y-6">
              <button
                type="button"
                onClick={() => setSelectedTicketId(null)}
                className="inline-flex items-center gap-1.5 text-xs font-semibold text-slate-600 hover:text-slate-900 transition cursor-pointer"
              >
                <ArrowLeft size={14} />
                <span>Quay lại danh sách phiếu</span>
              </button>

              <div className="bg-white rounded-2xl border border-slate-200 shadow-xs p-6 space-y-6">
                {/* Header of Ticket */}
                <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4 pb-4 border-b border-slate-200">
                  <div className="space-y-1.5">
                    <div className="flex items-center gap-2.5">
                      <span className="font-mono font-bold text-sm bg-slate-900 text-[#04D3D4] px-2.5 py-0.5 rounded-lg flex items-center gap-1.5">
                        <span>{selectedTicket.code}</span>
                        {isDetailLoading && <Loader2 size={13} className="animate-spin text-[#04D3D4]" />}
                      </span>
                      <span className={`text-[11px] font-bold px-2.5 py-0.5 rounded-full border ${
                        selectedTicket.status === 'OPEN'
                          ? 'bg-blue-50 text-blue-700 border-blue-200'
                          : selectedTicket.status === 'DONE'
                          ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                          : 'bg-rose-50 text-rose-700 border-rose-200'
                      }`}>
                        {selectedTicket.status === 'OPEN' ? 'Đang duyệt' : selectedTicket.status === 'DONE' ? 'Hoàn tất' : 'Từ chối'}
                      </span>
                    </div>
                    <h2 className="text-base font-bold text-slate-900">{selectedTicket.title}</h2>
                    <div className="flex items-center gap-4 text-xs text-slate-500">
                      <span>Người tạo: <strong className="text-slate-700">{selectedTicket.requester}</strong> ({selectedTicket.requesterRole})</span>
                      <span>Thời điểm: {selectedTicket.createdAt}</span>
                    </div>
                  </div>
                </div>

                {/* DataTrust Cross-System Finding Context Card */}
                {((selectedTicket as any).ticketType === 'remediation' || (selectedTicket as any).subject?.finding_id || (selectedTicket as any).form?.finding_id) && (
                  <div className="rounded-xl border border-teal-200 bg-teal-50/50 p-4 space-y-3 text-xs">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <span className="font-bold text-teal-800 uppercase tracking-wide text-[11px] flex items-center gap-1.5">
                          <CheckCircle2 size={14} className="text-teal-600" />
                          <span>Hồ Sơ Liên Kết DataTrust Finding & Đề Xuất Remediation</span>
                        </span>
                      </div>
                      <span className="font-mono text-[10px] bg-teal-100 text-teal-900 px-2 py-0.5 rounded font-bold">
                        Phase 3 Integration
                      </span>
                    </div>

                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 bg-white p-3 rounded-lg border border-teal-100 text-[11px]">
                      <div>
                        <span className="text-slate-400 block font-medium">Finding ID:</span>
                        <span className="font-mono font-bold text-slate-900">
                          {(selectedTicket as any).subject?.finding_id || (selectedTicket as any).form?.finding_id || 'FINDING-EV-001'}
                        </span>
                      </div>
                      <div>
                        <span className="text-slate-400 block font-medium">Proposal ID & Version:</span>
                        <span className="font-mono font-bold text-teal-800">
                          {(selectedTicket as any).subject?.proposal_id ? `${(selectedTicket as any).subject.proposal_id.slice(0, 8)}... (v${(selectedTicket as any).subject.proposal_version || 1})` : 'PRP-2026-v1'}
                        </span>
                      </div>
                      <div>
                        <span className="text-slate-400 block font-medium">Dữ liệu cách ly mục tiêu:</span>
                        <span className="font-mono text-slate-700">
                          {(selectedTicket as any).subject?.dataset_id || 'ev_telemetry'}.{(selectedTicket as any).subject?.column_name || 'driver_phone'}
                        </span>
                      </div>
                      {(selectedTicket as any).subject?.source_hash && (
                        <div className="sm:col-span-3 pt-1 border-t border-slate-100 text-[10px] text-slate-500 font-mono">
                          Source Snapshot Hash: {(selectedTicket as any).subject.source_hash}
                        </div>
                      )}
                    </div>
                  </div>
                )}

                {/* Form Metadata Box */}
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 bg-slate-50 p-4 rounded-xl border border-slate-200 text-xs">
                  <div>
                    <span className="text-slate-400 block font-medium">Hệ thống / Ứng dụng:</span>
                    <span className="font-bold text-slate-800">{selectedTicket.form.system}</span>
                  </div>
                  <div>
                    <span className="text-slate-400 block font-medium">Mức quyền yêu cầu:</span>
                    <span className="font-bold text-slate-800">{selectedTicket.form.accessLevel}</span>
                  </div>
                  <div>
                    <span className="text-slate-400 block font-medium">Thời hạn truy cập:</span>
                    <span className="font-bold text-slate-800">{selectedTicket.form.durationDays} ngày</span>
                  </div>
                  <div className="sm:col-span-3 pt-2 border-t border-slate-200">
                    <span className="text-slate-400 block font-medium">Lý do nghiệp vụ:</span>
                    <span className="text-slate-700">{selectedTicket.form.reason}</span>
                  </div>
                </div>

                {/* Sequential RACIX Timeline */}
                <div className="space-y-3">
                  <h3 className="text-xs font-bold uppercase tracking-wider text-slate-700 flex items-center gap-2">
                    <Clock size={14} className="text-teal-600" />
                    <span>Chuỗi Phê duyệt Tuần tự (Sequential RACIX Chain)</span>
                  </h3>

                  <div className="relative border-l-2 border-slate-200 ml-4 pl-5 space-y-5 py-2">
                    {selectedTicket.steps.map((st, i) => (
                      <div key={i} className="relative">
                        <div className={`absolute -left-[27px] top-0 size-6 rounded-full border-2 flex items-center justify-center font-bold text-[11px] ${
                          st.status === 'APPROVED'
                            ? 'bg-emerald-500 border-emerald-500 text-white'
                            : st.status === 'CURRENT'
                            ? 'bg-white border-[#04D3D4] text-slate-900 ring-4 ring-[#04D3D4]/20'
                            : st.status === 'REJECTED'
                            ? 'bg-rose-500 border-rose-500 text-white'
                            : 'bg-slate-100 border-slate-300 text-slate-400'
                        }`}>
                          {st.idx + 1}
                        </div>

                        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                          <div className="space-y-0.5">
                            <div className="flex items-center gap-2">
                              <span className="font-bold text-xs text-slate-900">
                                Bước {st.idx + 1}: {ROLES[st.role]?.name || st.role}
                              </span>
                              <span className="px-1.5 py-0.2 rounded text-[10px] font-mono font-bold bg-slate-100 text-slate-600">
                                {st.action === 'P' ? 'Thực thi' : st.action === 'A' ? 'Phê duyệt' : 'Rà soát'}
                              </span>
                              {st.status === 'CURRENT' && (
                                <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-50 text-amber-700 border border-amber-200 animate-pulse">
                                  Đang chờ xử lý
                                </span>
                              )}
                            </div>
                            <div className="text-xs text-slate-500">
                              Người xử lý: <strong className="text-slate-700">{st.assigneeName}</strong> ({st.assigneeUsername})
                            </div>
                            {st.decisionNote && (
                              <div className="text-xs text-slate-600 italic bg-slate-50 p-2 rounded-lg border border-slate-200 mt-1">
                                &ldquo;{st.decisionNote}&rdquo; — {st.decidedAt}
                              </div>
                            )}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Interactive Decision Box for Current User */}
                {selectedTicket.status === 'OPEN' && (
                  <div className="bg-slate-900 text-white rounded-xl p-5 space-y-4 border border-slate-800">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <CheckCircle2 size={16} className="text-[#04D3D4]" />
                        <h4 className="text-sm font-bold text-white">Xử lý Phiếu (Quyết định Bước Duyệt)</h4>
                      </div>
                      <span className="text-[11px] text-slate-400">
                        Đang đăng nhập: <strong>{user?.fullName}</strong> ({user?.role})
                      </span>
                    </div>

                    <div className="space-y-1.5">
                      <label className="text-xs text-slate-300 font-medium">Ý kiến xử lý / Ghi chú phê duyệt:</label>
                      <input
                        type="text"
                        value={decisionComment}
                        onChange={(e) => setDecisionComment(e.target.value)}
                        placeholder="Nhập ghi chú hoặc lý do phê duyệt / từ chối..."
                        className="w-full bg-slate-950 border border-slate-700 rounded-xl px-3.5 py-2 text-xs text-white placeholder:text-slate-500 focus:outline-hidden focus:border-[#04D3D4]"
                      />
                    </div>

                    <div className="flex items-center gap-2 pt-1">
                      <button
                        type="button"
                        disabled={isDeciding}
                        onClick={() => handleDecision('APPROVED')}
                        className="py-2 px-4 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-bold text-xs flex items-center gap-1.5 transition cursor-pointer disabled:opacity-50"
                      >
                        {isDeciding ? <Loader2 size={14} className="animate-spin" /> : <CheckCircle2 size={14} />}
                        <span>Phê duyệt Bước này</span>
                      </button>
                      <button
                        type="button"
                        disabled={isDeciding}
                        onClick={() => handleDecision('RETURNED')}
                        className="py-2 px-4 rounded-xl bg-amber-600 hover:bg-amber-500 text-white font-bold text-xs flex items-center gap-1.5 transition cursor-pointer disabled:opacity-50"
                      >
                        {isDeciding ? <Loader2 size={14} className="animate-spin" /> : <RotateCcw size={14} />}
                        <span>Yêu cầu bổ sung</span>
                      </button>
                      <button
                        type="button"
                        disabled={isDeciding}
                        onClick={() => handleDecision('REJECTED')}
                        className="py-2 px-4 rounded-xl bg-rose-600 hover:bg-rose-500 text-white font-bold text-xs flex items-center gap-1.5 transition cursor-pointer disabled:opacity-50"
                      >
                        {isDeciding ? <Loader2 size={14} className="animate-spin" /> : <XCircle size={14} />}
                        <span>Từ chối</span>
                      </button>
                    </div>
                  </div>
                )}
              </div>
            </div>
          ) : (
            /* LIST VIEW */
            <div className="space-y-3">
              {isLoading ? (
                <div className="p-12 text-center bg-white rounded-2xl border border-slate-200">
                  <Loader2 size={24} className="animate-spin mx-auto text-teal-600 mb-2" />
                  <p className="text-xs text-slate-500">Đang tải danh sách phiếu từ PostgreSQL...</p>
                </div>
              ) : filteredTickets.length === 0 ? (
                <div className="p-12 text-center bg-white rounded-2xl border border-slate-200 text-xs text-slate-500">
                  Không có phiếu yêu cầu nào phù hợp với bộ lọc hiện tại.
                </div>
              ) : (
                filteredTickets.map((t) => (
                  <div
                    key={t.id}
                    onClick={() => setSelectedTicketId(t.id)}
                    className="bg-white hover:bg-slate-50 border border-slate-200/90 rounded-2xl p-4 sm:p-5 transition-all shadow-xs hover:shadow-md cursor-pointer flex flex-col sm:flex-row sm:items-center justify-between gap-4"
                  >
                    <div className="space-y-2">
                      <div className="flex items-center gap-2.5">
                        <span className="font-mono font-bold text-xs bg-slate-900 text-[#04D3D4] px-2 py-0.5 rounded-md">
                          {t.code}
                        </span>
                        <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full border ${
                          t.status === 'OPEN'
                            ? 'bg-blue-50 text-blue-700 border-blue-200'
                            : t.status === 'DONE'
                            ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                            : 'bg-rose-50 text-rose-700 border-rose-200'
                        }`}>
                          {t.status === 'OPEN' ? 'Đang duyệt' : t.status === 'DONE' ? 'Hoàn tất' : 'Từ chối'}
                        </span>
                        <span className="text-xs text-slate-400">· {t.createdAt}</span>
                      </div>

                      <h3 className="font-bold text-sm text-slate-900">{t.title}</h3>

                      <div className="flex items-center gap-3 text-xs text-slate-500">
                        <span>Người tạo: <strong className="text-slate-700">{t.requester}</strong></span>
                        <span>Hệ thống: <strong className="text-slate-700">{t.form.system}</strong></span>
                        {t.form.hasPii && (
                          <span className="text-[10px] bg-purple-50 text-purple-700 border border-purple-200 px-1.5 py-0.5 rounded-md font-bold">
                            PII Data
                          </span>
                        )}
                      </div>
                    </div>

                    <div className="flex items-center gap-3 shrink-0">
                      <div className="text-right">
                        <span className="text-[11px] text-slate-400 block">Bước hiện tại</span>
                        <span className="text-xs font-bold text-slate-800">
                          {t.steps && t.steps[t.currentStepIndex] ? `${t.steps[t.currentStepIndex].role} (${ROLES[t.steps[t.currentStepIndex].role]?.name || t.steps[t.currentStepIndex].role})` : 'Hoàn tất'}
                        </span>
                      </div>
                      <ChevronRight size={16} className="text-slate-400" />
                    </div>
                  </div>
                ))
              )}
            </div>
          )}
        </>
      )}

      {/* TAB 2: CREATE NEW TICKET FORM */}
      {activeTab === 'create' && (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* Form Column */}
          <div className="lg:col-span-7 bg-white p-6 rounded-2xl border border-slate-200 shadow-xs space-y-5">
            <div>
              <h2 className="text-base font-bold text-slate-900">Khởi tạo Yêu cầu Cấp quyền Mới</h2>
              <p className="text-xs text-slate-500 mt-1">
                Nhập thông tin yêu cầu. Hệ thống sẽ áp dụng ma trận SoD RACIX để tính toán chuỗi phê duyệt theo thời gian thực.
              </p>
            </div>

            <form onSubmit={handleCreateTicketSubmit} className="space-y-4 text-xs">
              <div className="space-y-1.5">
                <label className="font-semibold text-slate-700">Hệ thống / Cơ sở dữ liệu:</label>
                <select
                  value={formSystem}
                  onChange={(e) => setFormSystem(e.target.value)}
                  className="w-full bg-white border border-slate-200 rounded-xl px-3 py-2 text-xs text-slate-800 focus:outline-hidden focus:border-[#04D3D4]"
                >
                  <option value="DataTrust OS Data Lakehouse">DataTrust OS Data Lakehouse</option>
                  <option value="VinFast EV Telemetry Warehouse">VinFast EV Telemetry Warehouse</option>
                  <option value="Xanh SM Trip Management Core">Xanh SM Trip Management Core</option>
                  <option value="Production Airflow DAG Scheduler">Production Airflow DAG Scheduler</option>
                  <option value="Core Banking & ERP System">Core Banking & ERP System</option>
                </select>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div className="space-y-1.5">
                  <label className="font-semibold text-slate-700">Mức quyền yêu cầu:</label>
                  <select
                    value={formAccessLevel}
                    onChange={(e) => setFormAccessLevel(e.target.value)}
                    className="w-full bg-white border border-slate-200 rounded-xl px-3 py-2 text-xs text-slate-800 focus:outline-hidden focus:border-[#04D3D4]"
                  >
                    <option value="read">Đọc dữ liệu (Read-only)</option>
                    <option value="write">Ghi / Cập nhật (Write / Modify)</option>
                    <option value="admin">Quản trị / DDL (Admin Privilege)</option>
                  </select>
                </div>

                <div className="space-y-1.5">
                  <label className="font-semibold text-slate-700">Thời hạn cấp quyền:</label>
                  <select
                    value={formDuration}
                    onChange={(e) => setFormDuration(e.target.value)}
                    className="w-full bg-white border border-slate-200 rounded-xl px-3 py-2 text-xs text-slate-800 focus:outline-hidden focus:border-[#04D3D4]"
                  >
                    <option value="1">1 ngày (Khẩn cấp / Break-glass)</option>
                    <option value="30">30 ngày (Tiêu chuẩn)</option>
                    <option value="90">90 ngày (Dài hạn)</option>
                  </select>
                </div>
              </div>

              {/* Special Flags */}
              <div className="space-y-2 p-3 bg-slate-50 rounded-xl border border-slate-200">
                <span className="text-[11px] font-bold uppercase tracking-wider text-slate-500 block">
                  Phạm vi Dữ liệu & Rủi ro Kiểm toán:
                </span>
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={formHasPii}
                    onChange={(e) => setFormHasPii(e.target.checked)}
                    className="rounded text-[#04D3D4]"
                  />
                  <span className="text-slate-800 font-medium">
                    Truy cập Dữ liệu cá nhân (PII) — Bắt buộc DPO/Legal phê duyệt (Nghị định 13/GDPR)
                  </span>
                </label>
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={formIsDbOrAdmin}
                    onChange={(e) => setFormIsDbOrAdmin(e.target.checked)}
                    className="rounded text-[#04D3D4]"
                  />
                  <span className="text-slate-800 font-medium">
                    Quyền đặc quyền cơ sở dữ liệu (DBA / IAM Admin / Production Access)
                  </span>
                </label>
              </div>

              <div className="space-y-1.5">
                <label className="font-semibold text-slate-700">Lý do nghiệp vụ (Bắt buộc):</label>
                <textarea
                  rows={3}
                  value={formReason}
                  onChange={(e) => setFormReason(e.target.value)}
                  placeholder="Ghi rõ mục đích công việc cần cấp quyền để phục vụ thẩm tra kiểm toán..."
                  className="w-full bg-white border border-slate-200 rounded-xl p-3 text-xs text-slate-800 focus:outline-hidden focus:border-[#04D3D4]"
                />
              </div>

              <button
                type="submit"
                disabled={isSubmitting}
                className="w-full py-2.5 px-4 rounded-xl bg-slate-900 hover:bg-slate-800 text-[#04D3D4] font-bold text-xs flex items-center justify-center gap-2 transition cursor-pointer shadow-md disabled:opacity-50"
              >
                {isSubmitting ? <Loader2 size={14} className="animate-spin" /> : <Send size={14} />}
                <span>{isSubmitting ? 'Đang gửi yêu cầu...' : 'Gửi Phiếu Yêu cầu'}</span>
              </button>
            </form>
          </div>

          {/* Real-time Preview Column */}
          <div className="lg:col-span-5 bg-gradient-to-b from-slate-50 to-white p-6 rounded-2xl border border-slate-200 shadow-xs space-y-4">
            <div className="flex items-center gap-2 text-slate-800 font-bold text-sm">
              <Eye size={16} className="text-teal-600" />
              <span>Xem trước Chuỗi Phê duyệt (Live Preview)</span>
            </div>
            <p className="text-xs text-slate-500">
              Chuỗi xử lý được sinh tự động theo thuật toán RACIX và ma trận SoD chuẩn:
            </p>

            {previewChain && previewChain.steps.length > 0 ? (
              <div className="space-y-3">
                <div className="relative border-l-2 border-teal-300 ml-3 pl-4 space-y-4 py-1">
                  {previewChain.steps.map((s: any, idx: number) => (
                    <div key={idx} className="relative">
                      <div className="absolute -left-[23px] top-0 size-5 rounded-full bg-white border-2 border-teal-600 text-teal-800 font-bold text-[10px] flex items-center justify-center">
                        {idx + 1}
                      </div>
                      <div className="bg-white p-2.5 rounded-xl border border-slate-200 shadow-2xs space-y-0.5">
                        <div className="flex items-center gap-1.5">
                          <span className="font-bold text-xs text-slate-900">{ROLES[s.role as RoleKey]?.name || s.role}</span>
                          <span className="px-1.5 py-0.2 rounded text-[9px] font-mono font-bold bg-slate-100 text-slate-700">
                            {s.action === 'P' ? 'Thực thi' : s.action === 'A' ? 'Phê duyệt' : 'Rà soát'}
                          </span>
                        </div>
                        <div className="text-[11px] text-slate-500">
                          Người xử lý: <strong className="text-slate-700">{s.assignee || 'Chờ chỉ định'}</strong>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>

                <div className="p-3 bg-teal-50/60 rounded-xl border border-teal-200 text-xs text-teal-800 space-y-1">
                  <div className="font-semibold flex items-center gap-1.5">
                    <CheckCircle2 size={13} className="text-teal-600" />
                    <span>Tuân thủ Kiểm soát SoD:</span>
                  </div>
                  <div className="text-[11px] text-teal-700">
                    Chuỗi phê duyệt tuân thủ chặt chẽ nguyên tắc R → A → P và ngăn chặn tự duyệt.
                  </div>
                </div>
              </div>
            ) : (
              <div className="text-xs text-slate-400 italic">Đang tính toán chuỗi phê duyệt...</div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
