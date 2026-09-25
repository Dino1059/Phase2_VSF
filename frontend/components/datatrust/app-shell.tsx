'use client';
import { useState } from 'react';
import type { ComponentProps } from 'react';
import { Link as RouterLink, useLocation } from 'react-router-dom';
import {
  CheckSquare,
  LayoutGrid,
  Menu,
  PanelLeftClose,
  PanelLeftOpen,
  RotateCw,
  ShieldCheck,
  TableProperties,
  UserCog,
  X,
} from 'lucide-react';
import { Brand } from './brand';
import { cn } from '@/lib/utils';
import { useAgentStore, USER_ACCOUNTS, type AgentStoreState } from '@/lib/agent-store';

interface NavItem {
  label: string;
  href: string;
  icon: typeof LayoutGrid;
  badge?: () => number | null;
}

const navigation: NavItem[] = [
  { label: 'Tổng quan', href: '/overview', icon: LayoutGrid },
  { label: 'Lần chạy', href: '/runs', icon: RotateCw },
  {
    label: 'Quản lý rule',
    href: '/rules',
    icon: CheckSquare,
    badge: () => {
      const count = useAgentStore.getState().getPendingRulesCount();
      return count > 0 ? count : null;
    },
  },
  { label: 'Kết quả', href: '/results', icon: TableProperties },
];

function Link({ href, ...props }: Omit<ComponentProps<typeof RouterLink>, 'to'> & { href: string }) {
  return <RouterLink to={href} {...props} />;
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = useLocation().pathname;
  const [open, setOpen] = useState(false);
  const pendingCount = useAgentStore((s: AgentStoreState) => s.getPendingRulesCount());
  const currentRole = useAgentStore((s: AgentStoreState) => s.currentRole);
  const setRole = useAgentStore((s: AgentStoreState) => s.setRole);
  const isSidebarCollapsed = useAgentStore((s: AgentStoreState) => s.isSidebarCollapsed);
  const toggleSidebarCollapse = useAgentStore((s: AgentStoreState) => s.toggleSidebarCollapse);
  const currentUser = USER_ACCOUNTS[currentRole];

  const getBreadcrumbTitle = () => {
    if (pathname.startsWith('/overview') || pathname === '/') return 'Tổng quan';
    if (pathname.startsWith('/runs')) return 'Lần chạy';
    if (pathname.startsWith('/rules')) return 'Quản lý rule';
    if (pathname.startsWith('/results')) return 'Kết quả';
    return 'Tổng quan';
  };

  return (
    <div className="min-h-screen bg-[#f7faf9] text-slate-900">
      {open && (
        <button
          aria-label="Close navigation"
          className="fixed inset-0 z-30 bg-slate-950/30 backdrop-blur-xs lg:hidden"
          onClick={() => setOpen(false)}
        />
      )}

      {/* Collapsible Sidebar */}
      <aside
        className={cn(
          'fixed inset-y-0 left-0 z-40 flex flex-col border-r border-[#e2ece8] bg-white text-slate-700 shadow-xs transition-all duration-300 ease-in-out lg:translate-x-0',
          isSidebarCollapsed ? 'w-[72px] px-2.5 py-4' : 'w-[236px] px-3.5 py-5',
          open ? 'translate-x-0' : '-translate-x-full'
        )}
      >
        {/* Brand & Collapse Toggle */}
        <div className="flex items-center justify-between px-1">
          <Brand collapsed={isSidebarCollapsed} />
        </div>

        {/* Section title (only when expanded) */}
        {!isSidebarCollapsed ? (
          <div className="mt-8 px-2.5">
            <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400">
              Không gian làm việc
            </span>
          </div>
        ) : null}

        {/* Navigation list */}
        <nav className="mt-5 flex flex-1 flex-col gap-1.5">
          {navigation.map((item) => {
            const active =
              pathname === item.href ||
              (item.href === '/overview' && pathname === '/') ||
              pathname.startsWith(item.href + '/');
            const Icon = item.icon;
            const badgeValue = item.href === '/rules' && currentRole === 'admin' ? pendingCount : null;

            return (
              <Link
                key={item.label}
                href={item.href}
                onClick={() => setOpen(false)}
                title={isSidebarCollapsed ? item.label : undefined}
                className={cn(
                  'flex h-10 items-center rounded-xl transition-all',
                  isSidebarCollapsed ? 'justify-center px-0' : 'gap-3 px-3 text-[13px]',
                  active
                    ? 'bg-[#04D3D4]/15 border border-[#04D3D4]/40 font-bold text-slate-950 shadow-2xs'
                    : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900 font-medium'
                )}
              >
                <div className="relative flex items-center justify-center">
                  <Icon
                    size={17}
                    className={active ? 'text-[#04D3D4]' : 'text-slate-400 group-hover:text-slate-600'}
                  />
                  {isSidebarCollapsed && badgeValue ? (
                    <span className="absolute -top-1.5 -right-2 size-2 rounded-full bg-[#FFC402] ring-2 ring-white" />
                  ) : null}
                </div>

                {!isSidebarCollapsed && (
                  <>
                    <span className="flex-1">{item.label}</span>
                    {badgeValue ? (
                      <span className="rounded-full bg-[#FFC402] px-2 py-0.5 text-[10px] font-extrabold text-slate-950 shadow-2xs">
                        {badgeValue}
                      </span>
                    ) : null}
                  </>
                )}
              </Link>
            );
          })}
        </nav>

        {/* GSM Footer tag */}
        <div className="border-t border-[#e2ece8] pt-3">
          {isSidebarCollapsed ? (
            <div className="flex justify-center" title="GSM Global · Chiến dịch V35">
              <span className="grid size-8 place-items-center rounded-xl bg-[#04D3D4]/15 text-[10px] font-extrabold text-slate-900 border border-[#04D3D4]/30">
                GSM
              </span>
            </div>
          ) : (
            <div className="flex items-center gap-2.5 px-2">
              <span className="grid size-8 shrink-0 place-items-center rounded-xl bg-[#04D3D4]/15 text-[10px] font-extrabold text-slate-900 border border-[#04D3D4]/30">
                GSM
              </span>
              <span className="leading-tight overflow-hidden">
                <strong className="block text-xs font-bold text-slate-800">GSM Global</strong>
                <small className="block truncate text-[10px] text-slate-400">V35 · 24 thị trường</small>
              </span>
            </div>
          )}
        </div>
      </aside>

      {/* Main Content Area */}
      <div
        className={cn(
          'transition-all duration-300 ease-in-out',
          isSidebarCollapsed ? 'lg:pl-[72px]' : 'lg:pl-[236px]'
        )}
      >
        {/* Topbar */}
        <header className="sticky top-0 z-20 flex h-16 items-center justify-between border-b border-[#e2ece8] bg-white/95 px-5 backdrop-blur-md md:px-8">
          <div className="flex items-center gap-3">
            <button
              className="grid size-9 place-items-center rounded-lg border border-slate-200 lg:hidden text-slate-600"
              onClick={() => setOpen((v) => !v)}
            >
              {open ? <X size={18} /> : <Menu size={18} />}
            </button>

            {/* Desktop collapse quick toggle button */}
            <button
              onClick={toggleSidebarCollapse}
              title={isSidebarCollapsed ? 'Mở rộng sidebar' : 'Thu gọn sidebar'}
              className="hidden lg:grid size-8 place-items-center rounded-lg border border-slate-200 bg-white text-slate-500 hover:border-[#04D3D4] hover:text-[#04D3D4] transition"
            >
              {isSidebarCollapsed ? <PanelLeftOpen size={15} /> : <PanelLeftClose size={15} />}
            </button>

            <div className="text-xs font-medium text-slate-500">
              <span className="hover:text-slate-800 transition">DataTrust OS</span>
              <span className="mx-1.5 text-slate-300">/</span>
              <span className="font-bold text-slate-900">{getBreadcrumbTitle()}</span>
            </div>
          </div>

          <div className="flex items-center gap-3">
            {/* Interactive Role Switcher Toggle Pill */}
            <div className="flex items-center rounded-xl border border-[#d2e2dc] bg-[#f0f6f4] p-0.5 text-xs font-semibold">
              <button
                type="button"
                onClick={() => setRole('auditor')}
                className={cn(
                  'flex items-center gap-1.5 rounded-lg px-3 py-1.5 transition text-xs',
                  currentRole === 'auditor'
                    ? 'bg-slate-950 text-[#04D3D4] shadow-2xs font-bold'
                    : 'text-slate-600 hover:text-slate-900'
                )}
                title="Chế độ Kiểm toán viên IPO"
              >
                <ShieldCheck size={14} className={currentRole === 'auditor' ? 'text-[#04D3D4]' : ''} />
                <span>Auditor</span>
              </button>
              <button
                type="button"
                onClick={() => setRole('admin')}
                className={cn(
                  'flex items-center gap-1.5 rounded-lg px-3 py-1.5 transition text-xs',
                  currentRole === 'admin'
                    ? 'bg-[#04D3D4] text-slate-950 shadow-2xs font-bold'
                    : 'text-slate-600 hover:text-slate-900'
                )}
                title="Chế độ Quản trị viên hệ thống"
              >
                <UserCog size={14} />
                <span>Admin</span>
              </button>
            </div>

            {/* User Account Pill */}
            <div className="hidden sm:flex items-center gap-2 rounded-xl border border-[#e2ece8] bg-white px-2.5 py-1 text-xs">
              <div className="grid size-6 place-items-center rounded-lg bg-slate-950 font-mono text-[10px] font-bold text-[#04D3D4]">
                {currentUser.avatar}
              </div>
              <div className="flex flex-col text-left leading-none">
                <span className="font-semibold text-slate-800">{currentUser.name}</span>
                <span className="text-[10px] text-slate-400">{currentUser.badge}</span>
              </div>
            </div>

          </div>
        </header>

        {/* Content body */}
        <main className="p-4 sm:p-6 lg:p-7">{children}</main>
      </div>
    </div>
  );
}
