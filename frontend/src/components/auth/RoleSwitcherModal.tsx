import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  X,
  Check,
  ShieldCheck,
  LayoutGrid,
  Lock,
  Loader2,
  Sparkles,
} from 'lucide-react';
import { useAuthStore, type UserRole } from '@/src/stores/authStore';

interface RoleSwitcherModalProps {
  isOpen: boolean;
  onClose: () => void;
}

interface RoleItemConfig {
  code: UserRole;
  title: string;
  name: string;
  desc: string;
  group: 'both' | 'sod_only' | 'datatrust_only';
  targetRoute: string;
  badge: string;
}

const ROLE_ITEMS: RoleItemConfig[] = [
  // --- NHÓM 1: CẢ HAI HỆ THỐNG (BOTH) ---
  {
    code: 'ADMIN',
    title: 'Lead Platform / Admin SoD',
    name: 'Nguyễn Quốc Bảo',
    desc: 'Toàn quyền DataTrust & SoD. Đề xuất ma trận, quản trị kết nối, chạy pipeline.',
    group: 'both',
    targetRoute: '/overview',
    badge: 'Both',
  },
  {
    code: 'AUDITOR',
    title: 'Kiểm toán viên độc lập (Big 4)',
    name: 'Trần Minh Hoàng',
    desc: 'Thẩm tra độc lập IPO Assurance, rà soát ma trận RACIX và audit evidence ledger.',
    group: 'both',
    targetRoute: '/overview',
    badge: 'Both',
  },
  {
    code: 'DPO',
    title: 'Data Protection Officer (Pháp chế)',
    name: 'Lê Chi',
    desc: 'Phê duyệt dữ liệu PII/DLCN, thẩm định Nghị định 13/2023/NĐ-CP và Luật BV dữ liệu.',
    group: 'both',
    targetRoute: '/overview',
    badge: 'Both',
  },
  {
    code: 'SO',
    title: 'Chủ quản Hệ thống (System Owner)',
    name: 'Hồ Sơn',
    desc: 'Chủ quản ứng dụng & database, phê duyệt quyền truy cập tài nguyên công nghệ.',
    group: 'both',
    targetRoute: '/overview',
    badge: 'Both',
  },

  // --- NHÓM 2: CHUYÊN TRÁCH SOD (SOD ONLY) ---
  {
    code: 'REQ',
    title: 'Người yêu cầu cấp quyền (Requestor)',
    name: 'Nguyễn An',
    desc: 'Khởi tạo phiếu xin cấp quyền, tra cứu tiến độ xử lý và bổ sung hồ sơ.',
    group: 'sod_only',
    targetRoute: '/sod',
    badge: 'SoD Standalone',
  },
  {
    code: 'LM',
    title: 'Quản lý trực tiếp (Line Manager)',
    name: 'Trần Bình',
    desc: 'Phê duyệt bước 1 tính hợp lý nghiệp vụ và nhu cầu công tác nhân viên.',
    group: 'sod_only',
    targetRoute: '/sod',
    badge: 'SoD Standalone',
  },
  {
    code: 'IAM',
    title: 'Quản trị Định danh & Truy cập',
    name: 'Vũ Hà',
    desc: 'Thực thi cấp quyền trên Identity Provider / LDAP / AWS IAM sau khi đủ chữ ký.',
    group: 'sod_only',
    targetRoute: '/sod',
    badge: 'SoD Standalone',
  },
  {
    code: 'DEV',
    title: 'Kỹ sư Phần mềm (Developer)',
    name: 'Đỗ Khoa',
    desc: 'Yêu cầu quyền truy cập source code & môi trường dev/staging (SoD Dev != Ops).',
    group: 'sod_only',
    targetRoute: '/sod',
    badge: 'SoD Standalone',
  },
  {
    code: 'REL',
    title: 'Quản lý Phát hành (Release Manager)',
    name: 'Bùi Lan',
    desc: 'Phê duyệt release checklist, kiểm tra UAT & SAST trước khi cho phép deploy.',
    group: 'sod_only',
    targetRoute: '/sod',
    badge: 'SoD Standalone',
  },
  {
    code: 'OPS',
    title: 'Kỹ sư Vận hành Hạ tầng (Operator)',
    name: 'Ngô Minh',
    desc: 'Triển khai bản vá lên môi trường Production, giám sát hệ thống thời gian thực.',
    group: 'sod_only',
    targetRoute: '/sod',
    badge: 'SoD Standalone',
  },
  {
    code: 'CISO',
    title: 'Giám đốc An toàn Thông tin',
    name: 'Hoàng Giang',
    desc: 'Phê duyệt thay đổi ma trận SoD 2-Person Rule và quyền truy cập rủi ro cao.',
    group: 'sod_only',
    targetRoute: '/sod',
    badge: 'SoD Standalone',
  },

  // --- NHÓM 3: CHUYÊN TRÁCH DATATRUST OS (DATATRUST ONLY) ---
  {
    code: 'DATA_STEWARD',
    title: 'Quản gia Dữ liệu (Data Steward)',
    name: 'Phạm Thu Trang',
    desc: 'Thiết lập quy tắc chất lượng dữ liệu, duyệt đề xuất AI HITL và phân loại dữ liệu.',
    group: 'datatrust_only',
    targetRoute: '/overview',
    badge: 'DataTrust Only',
  },
  {
    code: 'ANALYST',
    title: 'Chuyên viên Phân tích (Data Analyst)',
    name: 'Vũ Hoàng Nam',
    desc: 'Khai thác báo cáo, truy vấn dashboard phân tích chất lượng dữ liệu và lineage.',
    group: 'datatrust_only',
    targetRoute: '/overview',
    badge: 'DataTrust Only',
  },
  {
    code: 'VIEWER',
    title: 'Người xem Báo cáo (Business Viewer)',
    name: 'Khách tham quan / Stakeholder',
    desc: 'Truy cập chỉ đọc các chỉ số KPI chất lượng dữ liệu tổng quan.',
    group: 'datatrust_only',
    targetRoute: '/overview',
    badge: 'DataTrust Only',
  },
];

export function RoleSwitcherModal({ isOpen, onClose }: RoleSwitcherModalProps) {
  const navigate = useNavigate();
  const currentRole = useAuthStore((s) => s.user?.role || 'ADMIN');
  const switchRoleViaBackend = useAuthStore((s) => s.switchRoleViaBackend);
  const [selectedGroup, setSelectedGroup] = useState<'all' | 'both' | 'sod_only' | 'datatrust_only'>('all');
  const [isSwitching, setIsSwitching] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleSelectRole = async (roleItem: RoleItemConfig) => {
    try {
      setIsSwitching(roleItem.code);
      const targetRoute = await switchRoleViaBackend(roleItem.code);
      onClose();
      navigate(targetRoute);
    } catch (err) {
      console.error('Error switching role:', err);
    } finally {
      setIsSwitching(null);
    }
  };

  const filteredRoles = ROLE_ITEMS.filter((r) => {
    if (selectedGroup === 'all') return true;
    return r.group === selectedGroup;
  });

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/70 backdrop-blur-sm animate-in fade-in duration-200"
      onClick={onClose}
    >
      <div
        className="bg-white rounded-3xl max-w-4xl w-full border border-slate-200 shadow-2xl overflow-hidden flex flex-col max-h-[90vh] animate-in zoom-in-95 duration-200"
        onClick={(e) => e.stopPropagation()}
      >
        {/* MODAL HEADER */}
        <div className="bg-gradient-to-r from-slate-900 via-slate-800 to-slate-900 text-white p-5 sm:p-6 shrink-0 border-b border-slate-700/60">
          <div className="flex items-center justify-between gap-4">
            <div className="flex items-center gap-3">
              <div className="size-11 rounded-2xl bg-teal-500/20 text-[#04D3D4] border border-[#04D3D4]/40 grid place-items-center shadow-inner">
                <Sparkles size={22} className="text-[#04D3D4]" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <h2 className="text-base sm:text-lg font-bold text-white tracking-tight">
                    Chuyển đổi Vai trò Hệ thống (Role Switcher)
                  </h2>
                </div>
              </div>
            </div>

            <button
              type="button"
              onClick={onClose}
              className="size-8 rounded-xl bg-slate-800/80 hover:bg-slate-700 text-slate-400 hover:text-white transition grid place-items-center cursor-pointer"
            >
              <X size={16} />
            </button>
          </div>

          {/* FILTER GROUP BUTTONS */}
          <div className="flex items-center gap-2 mt-4 pt-4 border-t border-slate-700/50 overflow-x-auto scrollbar-none text-xs">
            <button
              type="button"
              onClick={() => setSelectedGroup('all')}
              className={`px-3 py-1.5 rounded-xl font-bold transition cursor-pointer flex items-center gap-1.5 ${
                selectedGroup === 'all'
                  ? 'bg-[#04D3D4] text-slate-950 shadow-sm'
                  : 'bg-slate-800 text-slate-300 hover:bg-slate-700 hover:text-white'
              }`}
            >
              <span>Tất cả (14)</span>
            </button>
            <button
              type="button"
              onClick={() => setSelectedGroup('both')}
              className={`px-3 py-1.5 rounded-xl font-bold transition cursor-pointer flex items-center gap-1.5 ${
                selectedGroup === 'both'
                  ? 'bg-teal-400 text-slate-950 shadow-sm'
                  : 'bg-slate-800 text-slate-300 hover:bg-slate-700 hover:text-white'
              }`}
            >
              <ShieldCheck size={13} />
              <span>Cả hai hệ thống (4)</span>
            </button>
            <button
              type="button"
              onClick={() => setSelectedGroup('sod_only')}
              className={`px-3 py-1.5 rounded-xl font-bold transition cursor-pointer flex items-center gap-1.5 ${
                selectedGroup === 'sod_only'
                  ? 'bg-indigo-400 text-slate-950 shadow-sm'
                  : 'bg-slate-800 text-slate-300 hover:bg-slate-700 hover:text-white'
              }`}
            >
              <Lock size={13} />
              <span>Chuyên trách SoD (7)</span>
            </button>
            <button
              type="button"
              onClick={() => setSelectedGroup('datatrust_only')}
              className={`px-3 py-1.5 rounded-xl font-bold transition cursor-pointer flex items-center gap-1.5 ${
                selectedGroup === 'datatrust_only'
                  ? 'bg-amber-400 text-slate-950 shadow-sm'
                  : 'bg-slate-800 text-slate-300 hover:bg-slate-700 hover:text-white'
              }`}
            >
              <LayoutGrid size={13} />
              <span>Chuyên trách DataTrust (3)</span>
            </button>
          </div>
        </div>

        {/* ROLE CARDS GRID */}
        <div className="p-5 sm:p-6 overflow-y-auto max-h-[60vh] space-y-3 bg-[#f8fafc]">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5">
            {filteredRoles.map((roleItem) => {
              const isActive = currentRole === roleItem.code;
              const isBusy = isSwitching === roleItem.code;

              return (
                <div
                  key={roleItem.code}
                  onClick={() => !isBusy && handleSelectRole(roleItem)}
                  className={`relative p-4 rounded-2xl border transition-all cursor-pointer flex flex-col justify-between gap-3 text-left ${
                    isActive
                      ? 'bg-teal-50/70 border-teal-500 shadow-sm ring-2 ring-teal-500/20'
                      : 'bg-white border-slate-200/90 hover:border-teal-400 hover:shadow-md'
                  }`}
                >
                  <div className="space-y-1.5">
                    {/* TOP LINE: ROLE CODE + BADGE */}
                    <div className="flex items-center justify-between gap-2">
                      <div className="flex items-center gap-2">
                        <span
                          className={`font-mono font-extrabold text-xs px-2.5 py-1 rounded-lg ${
                            isActive
                              ? 'bg-teal-600 text-white'
                              : 'bg-slate-900 text-[#04D3D4]'
                          }`}
                        >
                          {roleItem.code}
                        </span>
                        <span
                          className={`text-[10px] font-bold px-2 py-0.5 rounded-md border ${
                            roleItem.group === 'both'
                              ? 'bg-teal-50 text-teal-800 border-teal-200'
                              : roleItem.group === 'sod_only'
                              ? 'bg-indigo-50 text-indigo-800 border-indigo-200'
                              : 'bg-amber-50 text-amber-800 border-amber-200'
                          }`}
                        >
                          {roleItem.badge}
                        </span>
                      </div>

                      {isActive && (
                        <div className="flex items-center gap-1 text-[11px] font-bold text-teal-700 bg-teal-100/80 px-2 py-0.5 rounded-full">
                          <Check size={12} className="stroke-[3]" />
                          <span>Đang kích hoạt</span>
                        </div>
                      )}
                    </div>

                    {/* NAME & TITLE */}
                    <div>
                      <h3 className="font-bold text-sm text-slate-900 leading-snug">{roleItem.title}</h3>
                      <div className="text-xs font-semibold text-slate-600 mt-0.5">
                        Mẫu đại diện: <span className="text-teal-700">{roleItem.name}</span>
                      </div>
                    </div>

                    {/* DESCRIPTION */}
                    <p className="text-xs text-slate-500 leading-relaxed pt-1">{roleItem.desc}</p>
                  </div>

                  {/* BOTTOM ACTION */}
                  <div className="flex items-center justify-end pt-2 border-t border-slate-100 text-[11px]">
                    <button
                      type="button"
                      disabled={isBusy}
                      className={`font-bold px-3 py-1 rounded-lg transition flex items-center gap-1.5 ${
                        isActive
                          ? 'text-teal-800 bg-teal-100'
                          : 'text-slate-700 bg-slate-100 hover:bg-teal-500 hover:text-white'
                      }`}
                    >
                      {isBusy ? (
                        <>
                          <Loader2 size={12} className="animate-spin" />
                          <span>Đang chuyển...</span>
                        </>
                      ) : isActive ? (
                        <span>Hiện hành</span>
                      ) : (
                        <span>Chọn vai trò này →</span>
                      )}
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* MODAL FOOTER */}
        <div className="p-4 bg-white border-t border-slate-200 flex flex-col sm:flex-row sm:items-center justify-end gap-3 text-xs text-slate-500 shrink-0">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 font-bold transition cursor-pointer self-end sm:self-auto"
          >
            Đóng
          </button>
        </div>
      </div>
    </div>
  );
}
