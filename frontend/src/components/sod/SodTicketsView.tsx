import React, { useState, useMemo } from 'react';
import { useAuthStore } from '@/src/stores/authStore';
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
  };
}

const INITIAL_DEMO_TICKETS: SodTicketItem[] = [
  {
    id: 'tkt_001',
    code: 'TK-2026-089',
    title: 'Xin cấp quyền truy cập tập dữ liệu EV Telemetry & V-Green Charging',
    requester: 'Nguyễn An',
    requesterRole: 'REQ',
    createdAt: '2026-10-15 08:30',
    status: 'OPEN',
    currentStepIndex: 1,
    steps: [
      {
        idx: 0,
        role: 'REQ',
        action: 'P',
        assigneeName: 'Nguyễn An',
        assigneeUsername: 'an.nguyen',
        status: 'APPROVED',
        slaHours: 0,
        decisionNote: 'Khởi tạo yêu cầu cấp quyền',
        decidedAt: '2026-10-15 08:30',
      },
      {
        idx: 1,
        role: 'LM',
        action: 'A',
        assigneeName: 'Trần Bình',
        assigneeUsername: 'binh.tran',
        status: 'CURRENT',
        slaHours: 24,
      },
      {
        idx: 2,
        role: 'SO',
        action: 'A',
        assigneeName: 'Hồ Sơn',
        assigneeUsername: 'son.ho',
        status: 'PENDING',
        slaHours: 48,
      },
      {
        idx: 3,
        role: 'AUD',
        action: 'R',
        assigneeName: 'Trần Minh Hoàng',
        assigneeUsername: 'hoang.tran',
        status: 'PENDING',
        slaHours: 24,
      },
      {
        idx: 4,
        role: 'IAM',
        action: 'P',
        assigneeName: 'Vũ Hà',
        assigneeUsername: 'ha.vu',
        status: 'PENDING',
        slaHours: 12,
      },
    ],
    form: {
      system: 'BigQuery Telemetry Warehouse',
      accessLevel: 'Đọc dữ liệu phân tích (Read-only)',
      hasPii: false,
      isDbOrAdmin: false,
      reason: 'Phân tích dữ liệu sạc xe điện V-Green phục vụ tối ưu hóa trạm sạc khu vực Hà Nội.',
      durationDays: 60,
    },
  },
  {
    id: 'tkt_002',
    code: 'TK-2026-090',
    title: 'Cấp quyền truy xuất danh tính khách hàng Xanh SM (Chứa dữ liệu PII)',
    requester: 'Nguyễn Quốc Bảo',
    requesterRole: 'ADMIN',
    createdAt: '2026-10-14 14:15',
    status: 'OPEN',
    currentStepIndex: 2,
    steps: [
      {
        idx: 0,
        role: 'REQ',
        action: 'P',
        assigneeName: 'Nguyễn Quốc Bảo',
        assigneeUsername: 'admin',
        status: 'APPROVED',
        slaHours: 0,
        decidedAt: '2026-10-14 14:15',
      },
      {
        idx: 1,
        role: 'LM',
        action: 'A',
        assigneeName: 'Trần Bình',
        assigneeUsername: 'binh.tran',
        status: 'APPROVED',
        slaHours: 24,
        decisionNote: 'Xác nhận nhu cầu điều tra dữ liệu khách hàng theo yêu cầu IPO.',
        decidedAt: '2026-10-14 16:00',
      },
      {
        idx: 2,
        role: 'DPO',
        action: 'A',
        assigneeName: 'Lê Chi',
        assigneeUsername: 'chi.le',
        status: 'CURRENT',
        slaHours: 24,
      },
      {
        idx: 3,
        role: 'SO',
        action: 'A',
        assigneeName: 'Hồ Sơn',
        assigneeUsername: 'son.ho',
        status: 'PENDING',
        slaHours: 48,
      },
      {
        idx: 4,
        role: 'AUD',
        action: 'R',
        assigneeName: 'Trần Minh Hoàng',
        assigneeUsername: 'hoang.tran',
        status: 'PENDING',
        slaHours: 24,
      },
      {
        idx: 5,
        role: 'IAM',
        action: 'P',
        assigneeName: 'Vũ Hà',
        assigneeUsername: 'ha.vu',
        status: 'PENDING',
        slaHours: 12,
      },
    ],
    form: {
      system: 'DataTrust Customer Profile Store',
      accessLevel: 'Truy vấn bảng PII khách hàng (Masked)',
      hasPii: true,
      isDbOrAdmin: false,
      reason: 'Rà soát tuân thủ Nghị định 13/2023/NĐ-CP và chuẩn bị hồ sơ IPO.',
      durationDays: 30,
    },
  },
  {
    id: 'tkt_003',
    code: 'TK-2026-085',
    title: 'Phát hành bản vá bảo mật Hotfix pipeline Lane B (Production Deploy)',
    requester: 'Đỗ Khoa',
    requesterRole: 'DEV',
    createdAt: '2026-10-12 10:00',
    status: 'DONE',
    currentStepIndex: 4,
    steps: [
      {
        idx: 0,
        role: 'DEV',
        action: 'P',
        assigneeName: 'Đỗ Khoa',
        assigneeUsername: 'khoa.do',
        status: 'APPROVED',
        slaHours: 0,
        decidedAt: '2026-10-12 10:00',
      },
      {
        idx: 1,
        role: 'LM',
        action: 'A',
        assigneeName: 'Trần Bình',
        assigneeUsername: 'binh.tran',
        status: 'APPROVED',
        slaHours: 12,
        decidedAt: '2026-10-12 11:30',
      },
      {
        idx: 2,
        role: 'REL',
        action: 'A',
        assigneeName: 'Bùi Lan',
        assigneeUsername: 'lan.bui',
        status: 'APPROVED',
        slaHours: 12,
        decisionNote: 'Đã kiểm tra biên bản UAT và rà soát quét SAST đạt chuẩn.',
        decidedAt: '2026-10-12 14:00',
      },
      {
        idx: 3,
        role: 'AUD',
        action: 'R',
        assigneeName: 'Trần Minh Hoàng',
        assigneeUsername: 'hoang.tran',
        status: 'APPROVED',
        slaHours: 12,
        decisionNote: 'Rà soát chứng từ thay đổi mã nguồn trước khi deploy.',
        decidedAt: '2026-10-12 15:00',
      },
      {
        idx: 4,
        role: 'OPS',
        action: 'P',
        assigneeName: 'Ngô Minh',
        assigneeUsername: 'minh.ngo',
        status: 'APPROVED',
        slaHours: 6,
        decisionNote: 'Đã deploy thành công lên cụm Production không gián đoạn dịch vụ.',
        decidedAt: '2026-10-12 16:20',
      },
    ],
    form: {
      system: 'DataTrust Pipeline Core Engine',
      accessLevel: 'Deploy Production Release',
      hasPii: false,
      isDbOrAdmin: true,
      reason: 'Triển khai bản vá kiểm soát xung đột SoD và bổ sung policy IFRS-15.',
      durationDays: 1,
    },
  },
];

export function SodTicketsView() {
  const user = useAuthStore((s) => s.user);

  const [activeTab, setActiveTab] = useState<'list' | 'create'>('list');
  const [tickets, setTickets] = useState<SodTicketItem[]>(INITIAL_DEMO_TICKETS);
  const [selectedTicketId, setSelectedTicketId] = useState<string | null>(null);
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

  const selectedTicket = tickets.find((t) => t.id === selectedTicketId);

  // Dynamic Live Preview of the RACIX Approval Chain
  const previewChain = useMemo(() => {
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
        { id: 'hoang.tran', name: 'Trần Minh Hoàng', roles: ['AUD'] as RoleKey[] },
      ];
      return buildChain(d, user?.username || 'an.nguyen', people, DEFAULT_MATRIX);
    } catch {
      return null;
    }
  }, [formSystem, formAccessLevel, formHasPii, formIsDbOrAdmin, formReason, formDuration, user]);

  const handleCreateTicketSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!formReason.trim()) return;

    const newTicketId = `tkt_${Date.now()}`;
    const newCode = `TK-2026-${String(tickets.length + 91).padStart(3, '0')}`;

    const generatedSteps = previewChain?.steps.map((s: any, idx: number) => ({
      idx,
      role: s.role,
      action: s.action,
      assigneeName: s.assignee ? s.assignee.replace('.', ' ').toUpperCase() : ROLES[s.role as RoleKey]?.name || s.role,
      assigneeUsername: s.assignee || s.role.toLowerCase(),
      status: (idx === 0 ? 'APPROVED' : idx === 1 ? 'CURRENT' : 'PENDING') as any,
      slaHours: s.role === 'LM' ? 24 : s.role === 'DPO' ? 48 : 24,
      decidedAt: idx === 0 ? new Date().toLocaleString() : undefined,
    })) || [];

    const newTicket: SodTicketItem = {
      id: newTicketId,
      code: newCode,
      title: `Yêu cầu cấp quyền: ${formSystem} (${formAccessLevel.toUpperCase()})`,
      requester: user?.fullName || 'Người dùng',
      requesterRole: user?.role || 'REQ',
      createdAt: new Date().toLocaleString(),
      status: 'OPEN',
      currentStepIndex: 1,
      steps: generatedSteps,
      form: {
        system: formSystem,
        accessLevel: formAccessLevel === 'admin' ? 'Quản trị (Admin)' : formAccessLevel === 'write' ? 'Ghi / Sửa (Write)' : 'Đọc (Read)',
        hasPii: formHasPii,
        isDbOrAdmin: formIsDbOrAdmin,
        reason: formReason,
        durationDays: parseInt(formDuration, 10),
      },
    };

    setTickets([newTicket, ...tickets]);
    setSelectedTicketId(newTicket.id);
    setActiveTab('list');
    setActionSuccessMsg(`Đã tạo thành công phiếu ${newCode}! Chuỗi phê duyệt tuần tự đã được kích hoạt.`);
    setTimeout(() => setActionSuccessMsg(''), 4000);
  };

  const handleDecision = (outcome: 'APPROVED' | 'REJECTED' | 'RETURNED') => {
    if (!selectedTicket) return;

    const updatedTickets = tickets.map((t) => {
      if (t.id !== selectedTicket.id) return t;

      const currentStep = t.steps[t.currentStepIndex];
      const updatedSteps = [...t.steps];

      updatedSteps[t.currentStepIndex] = {
        ...currentStep,
        status: outcome,
        decisionNote: decisionComment || (outcome === 'APPROVED' ? 'Đồng ý phê duyệt' : 'Từ chối'),
        decidedAt: new Date().toLocaleString(),
      };

      const nextStepIndex = t.currentStepIndex + 1;
      let newTicketStatus = t.status;

      if (outcome === 'REJECTED') {
        newTicketStatus = 'REJECTED';
      } else if (outcome === 'RETURNED') {
        newTicketStatus = 'RETURNED';
      } else if (nextStepIndex >= t.steps.length) {
        newTicketStatus = 'DONE';
      } else {
        updatedSteps[nextStepIndex] = {
          ...updatedSteps[nextStepIndex],
          status: 'CURRENT',
        };
      }

      return {
        ...t,
        status: newTicketStatus,
        currentStepIndex: outcome === 'APPROVED' && nextStepIndex < t.steps.length ? nextStepIndex : t.currentStepIndex,
        steps: updatedSteps,
      };
    });

    setTickets(updatedTickets);
    setDecisionComment('');
    setActionSuccessMsg(`Đã ghi nhận quyết định: ${outcome === 'APPROVED' ? 'Đã duyệt' : outcome === 'REJECTED' ? 'Đã từ chối' : 'Yêu cầu bổ sung'}`);
    setTimeout(() => setActionSuccessMsg(''), 3000);
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
                      <span className="font-mono font-bold text-sm bg-slate-900 text-[#04D3D4] px-2.5 py-0.5 rounded-lg">
                        {selectedTicket.code}
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
                        onClick={() => handleDecision('APPROVED')}
                        className="py-2 px-4 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-bold text-xs flex items-center gap-1.5 transition cursor-pointer"
                      >
                        <CheckCircle2 size={14} />
                        <span>Phê duyệt Bước này</span>
                      </button>
                      <button
                        type="button"
                        onClick={() => handleDecision('RETURNED')}
                        className="py-2 px-4 rounded-xl bg-amber-600 hover:bg-amber-500 text-white font-bold text-xs flex items-center gap-1.5 transition cursor-pointer"
                      >
                        <RotateCcw size={14} />
                        <span>Yêu cầu bổ sung</span>
                      </button>
                      <button
                        type="button"
                        onClick={() => handleDecision('REJECTED')}
                        className="py-2 px-4 rounded-xl bg-rose-600 hover:bg-rose-500 text-white font-bold text-xs flex items-center gap-1.5 transition cursor-pointer"
                      >
                        <XCircle size={14} />
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
              {filteredTickets.map((t) => (
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
                        {t.steps[t.currentStepIndex]?.role} ({ROLES[t.steps[t.currentStepIndex]?.role]?.name})
                      </span>
                    </div>
                    <ChevronRight size={16} className="text-slate-400" />
                  </div>
                </div>
              ))}
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
                className="w-full py-2.5 px-4 rounded-xl bg-slate-900 hover:bg-slate-800 text-[#04D3D4] font-bold text-xs flex items-center justify-center gap-2 transition cursor-pointer shadow-md"
              >
                <Send size={14} />
                <span>Gửi Phiếu Yêu cầu</span>
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
