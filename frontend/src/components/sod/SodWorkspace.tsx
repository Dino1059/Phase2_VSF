import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuthStore } from '@/src/stores/authStore';
import { RoleSwitcherModal } from '@/src/components/auth/RoleSwitcherModal';
import { SodMatrixView } from './SodMatrixView';
import { SodTicketsView } from './SodTicketsView';
import { SodInboxView } from './SodInboxView';
import { SodDelegationView } from './SodDelegationView';
import { SodConfigAdminView } from './SodConfigAdminView';
import { SodEvidenceView } from './SodEvidenceView';
import {
  ShieldCheck,
  Grid,
  FileText,
  Inbox,
  UserCheck,
  Settings,
  FileCheck,
  LogOut,
} from 'lucide-react';
import '@/src/assets/sod.css';

interface SodWorkspaceProps {
  mode?: 'embedded' | 'standalone';
}

type SodTab = 'matrix' | 'tickets' | 'inbox' | 'delegations' | 'config' | 'evidence';

export function SodWorkspace({ mode = 'embedded' }: SodWorkspaceProps) {
  const navigate = useNavigate();
  const user = useAuthStore((s) => s.user);
  const logout = useAuthStore((s) => s.logout);

  const [activeTab, setActiveTab] = useState<SodTab>('matrix');
  const [isRoleModalOpen, setIsRoleModalOpen] = useState(false);

  const handleLogout = () => {
    logout();
    navigate('/login', { replace: true });
  };

  const navTabs: { id: SodTab; label: string; icon: typeof Grid; badge?: string }[] = [
    { id: 'matrix', label: 'Ma trận SoD (RACIX)', icon: Grid },
    { id: 'tickets', label: 'Phiếu Yêu cầu', icon: FileText, badge: '3' },
    { id: 'inbox', label: 'Hộp việc', icon: Inbox, badge: 'Mới' },
    { id: 'delegations', label: 'Ủy quyền', icon: UserCheck },
    { id: 'config', label: 'Quản trị Cấu hình', icon: Settings },
    { id: 'evidence', label: 'Bằng chứng Kiểm toán', icon: FileCheck },
  ];

  return (
    <div className={`sod-scope w-full flex flex-col font-sans ${mode === 'standalone' ? 'min-h-screen bg-[#f6f7fb]' : ''}`}>
      {/* 1. STANDALONE HEADER (Chỉ hiện khi mode === 'standalone' cho các vai trò SoD-only) */}
      {mode === 'standalone' && (
        <header className="sticky top-0 z-30 bg-white border-b border-[#e4e7ef] shadow-2xs px-4 sm:px-6">
          <div className="max-w-7xl mx-auto flex items-center justify-between h-14 sm:h-16 gap-4">
            {/* Brand Logo */}
            <div className="flex items-center gap-3">
              <div className="size-9 rounded-xl bg-slate-950 text-[#04D3D4] border border-[#04D3D4]/40 grid place-items-center shadow-xs">
                <ShieldCheck size={20} className="text-[#04D3D4]" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <span className="font-extrabold text-slate-900 text-sm tracking-tight">SoD Flow</span>
                  <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-indigo-50 text-indigo-700 border border-indigo-200">
                    Standalone Workspace
                  </span>
                </div>
                <div className="text-[10px] text-slate-400">Phân tách trách nhiệm · RACIX Governance</div>
              </div>
            </div>

            {/* User Profile & Quick Action */}
            <div className="flex items-center gap-3">
              {/* User Pill */}
              <div className="flex items-center gap-2.5 bg-slate-50 border border-slate-200 px-3 py-1.5 rounded-xl text-xs">
                <div className="size-6 rounded-lg bg-indigo-900 text-indigo-200 font-bold font-mono text-[10px] grid place-items-center">
                  {user?.avatar || 'US'}
                </div>
                <div className="flex flex-col text-left leading-tight">
                  <span className="font-bold text-slate-800 text-xs">{user?.fullName || user?.username}</span>
                  <span className="text-[10px] text-indigo-600 font-semibold">{user?.role}</span>
                </div>
              </div>

              {/* Role Switcher button */}
              <button
                type="button"
                onClick={() => setIsRoleModalOpen(true)}
                className="hidden sm:flex items-center gap-1.5 px-3 py-1.5 rounded-xl border border-indigo-200 bg-indigo-50 hover:bg-indigo-100 text-xs font-bold text-indigo-900 transition cursor-pointer shadow-2xs"
                title="Đổi vai trò trong 14 vai trò ITGC"
              >
                <UserCheck size={14} className="text-indigo-600" />
                <span>Đổi vai trò</span>
              </button>

              {/* Logout button */}
              <button
                type="button"
                onClick={handleLogout}
                className="p-2 rounded-xl border border-slate-200 hover:bg-rose-50 hover:text-rose-600 text-slate-500 transition cursor-pointer"
                title="Đăng xuất"
              >
                <LogOut size={15} />
              </button>
            </div>
          </div>
        </header>
      )}

      {/* 2. SUB-NAVIGATION TABS BAR */}
      <div className={`w-full ${mode === 'standalone' ? 'max-w-7xl mx-auto px-4 sm:px-6 pt-4' : 'mb-5'}`}>
        <div className="flex items-center gap-1.5 overflow-x-auto pb-1 scrollbar-none border-b border-slate-200/90">
          {navTabs.map((t) => {
            const active = activeTab === t.id;
            const Icon = t.icon;

            return (
              <button
                key={t.id}
                type="button"
                onClick={() => setActiveTab(t.id)}
                className={`flex items-center gap-2 px-3.5 py-2 rounded-xl text-xs font-bold transition whitespace-nowrap cursor-pointer ${
                  active
                    ? 'bg-slate-900 text-[#04D3D4] shadow-xs'
                    : 'text-slate-600 hover:bg-white hover:text-slate-900'
                }`}
              >
                <Icon size={14} className={active ? 'text-[#04D3D4]' : 'text-slate-500'} />
                <span>{t.label}</span>
                {t.badge && (
                  <span className={`text-[10px] px-1.5 py-0.2 rounded-full font-bold ${
                    active ? 'bg-[#04D3D4] text-slate-950' : 'bg-slate-200 text-slate-700'
                  }`}>
                    {t.badge}
                  </span>
                )}
              </button>
            );
          })}
        </div>
      </div>

      {/* 3. WORKSPACE BODY CANVAS */}
      <div className={`w-full ${mode === 'standalone' ? 'max-w-7xl mx-auto px-4 sm:px-6 py-6 flex-1' : ''}`}>
        {activeTab === 'matrix' && <SodMatrixView />}
        {activeTab === 'tickets' && <SodTicketsView />}
        {activeTab === 'inbox' && <SodInboxView />}
        {activeTab === 'delegations' && <SodDelegationView />}
        {activeTab === 'config' && <SodConfigAdminView />}
        {activeTab === 'evidence' && <SodEvidenceView />}
      </div>

      {/* Role Switcher Modal */}
      <RoleSwitcherModal
        isOpen={isRoleModalOpen}
        onClose={() => setIsRoleModalOpen(false)}
      />
    </div>
  );
}
