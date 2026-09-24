'use client';
import { useState } from 'react';
import type { ComponentProps } from 'react';
import { Link as RouterLink, useLocation } from 'react-router-dom';
import {
  CheckSquare,
  Layers,
  LayoutGrid,
  Menu,
  RotateCw,
  Sparkles,
  TableProperties,
  X,
} from 'lucide-react';
import { Brand } from './brand';
import { cn } from '@/lib/utils';
import { useAgentStore, type AgentStoreState } from '@/lib/agent-store';
import { AccountSwitcher } from '@/components/datatrust/auth/account-switcher';

interface NavItem {
  label: string;
  href: string;
  icon: typeof LayoutGrid;
  badge?: () => number | null;
}

const navigation: NavItem[] = [
  { label: 'AI Hub (Trang chủ)', href: '/', icon: Sparkles },
  { label: 'Không gian AI', href: '/workspace', icon: Layers },
  { label: 'Tổng quan', href: '/overview', icon: LayoutGrid },
  { label: 'Lần chạy', href: '/runs', icon: RotateCw },
  {
    label: 'Duyệt rule',
    href: '/rules',
    icon: CheckSquare,
    badge: () => {
      const count = useAgentStore.getState().getPendingRulesCount();
      return count > 0 ? count : null;
    },
  },
  { label: 'Kết quả & Evidence', href: '/results', icon: TableProperties },
];

function Link({ href, ...props }: Omit<ComponentProps<typeof RouterLink>, 'to'> & { href: string }) {
  return <RouterLink to={href} {...props} />;
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = useLocation().pathname;
  const [open, setOpen] = useState(false);
  const pendingCount = useAgentStore((s: AgentStoreState) => s.getPendingRulesCount());
  const openChat = useAgentStore((s: AgentStoreState) => s.openChat);

  const getBreadcrumbTitle = () => {
    if (pathname === '/' || pathname === '/hub') return 'AI Hub (Trang chủ)';
    if (pathname.startsWith('/workspace')) return 'Không gian làm việc AI';
    if (pathname.startsWith('/overview')) return 'Tổng quan';
    if (pathname.startsWith('/runs')) return 'Lần chạy';
    if (pathname.startsWith('/rules')) return 'Duyệt rule';
    if (pathname.startsWith('/results')) return 'Kết quả';
    return 'Tổng quan';
  };

  return (
    <div className="min-h-screen bg-[#f4f8f7] text-slate-900">
      {open && (
        <button
          aria-label="Close navigation"
          className="fixed inset-0 z-30 bg-slate-950/30 backdrop-blur-xs lg:hidden"
          onClick={() => setOpen(false)}
        />
      )}

      {/* Sidebar matching new_UI.png */}
      <aside
        className={cn(
          'fixed inset-y-0 left-0 z-40 flex w-[236px] flex-col border-r border-[#e2ece8] bg-white px-3.5 py-5 text-slate-700 shadow-xs transition-transform lg:translate-x-0',
          open ? 'translate-x-0' : '-translate-x-full'
        )}
      >
        <div className="px-2 pt-1">
          <Brand />
        </div>

        <div className="mt-8 px-2.5">
          <span className="text-[11px] font-semibold text-slate-400">Không gian làm việc</span>
        </div>

        <nav className="mt-2.5 flex flex-1 flex-col gap-1">
          {navigation.map((item) => {
            const active =
              item.href === '/'
                ? pathname === '/' || pathname === '/hub'
                : pathname === item.href || pathname.startsWith(item.href + '/');
            const Icon = item.icon;
            const badgeValue = item.href === '/rules' ? pendingCount : null;

            return (
              <Link
                key={item.label}
                href={item.href}
                onClick={() => setOpen(false)}
                className={cn(
                  'flex h-10 items-center gap-3 rounded-lg px-3 text-[13px] font-medium transition-colors',
                  active
                    ? 'bg-[#e6f4f1] font-semibold text-[#007460]'
                    : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900'
                )}
              >
                <Icon size={16} className={active ? 'text-[#008b74]' : 'text-slate-400'} />
                <span className="flex-1">{item.label}</span>
                {badgeValue ? (
                  <span className="rounded-full bg-amber-500 px-1.5 py-0.2 text-[10px] font-bold text-white">
                    {badgeValue}
                  </span>
                ) : null}
              </Link>
            );
          })}
        </nav>

        {/* GSM Footer tag */}
        <div className="flex items-center gap-3 border-t border-[#e2ece8] px-2 pt-4">
          <span className="grid size-8 place-items-center rounded-lg bg-[#e6f6f2] text-[10px] font-bold text-[#007460]">
            GSM
          </span>
          <span className="leading-tight">
            <strong className="block text-xs font-semibold text-slate-800">GSM Global</strong>
            <small className="text-[10px] text-slate-400">Chiến dịch V35 · 24 thị trường</small>
          </span>
        </div>
      </aside>

      {/* Main Container */}
      <div className="lg:pl-[236px]">
        {/* Topbar matching new_UI.png */}
        <header className="sticky top-0 z-20 flex h-16 items-center justify-between border-b border-[#e2ece8] bg-white/90 px-5 backdrop-blur-md md:px-8">
          <div className="flex items-center gap-3">
            <button
              className="grid size-9 place-items-center rounded-md border border-slate-200 lg:hidden text-slate-600"
              onClick={() => setOpen((v) => !v)}
            >
              {open ? <X size={18} /> : <Menu size={18} />}
            </button>
            <div className="text-xs font-medium text-slate-500">
              <span>DataTrust OS</span>
              <span className="mx-1.5 text-slate-300">/</span>
              <span className="font-semibold text-slate-800">{getBreadcrumbTitle()}</span>
            </div>
          </div>

          <div className="flex items-center gap-2.5 sm:gap-3">
            <div className="hidden h-5 w-px bg-slate-200" />
            {/* User Account Switcher (Auditor IPO vs System Admin) */}
            <AccountSwitcher />
          </div>
        </header>

        {/* Page Content */}
        <main className="min-h-[calc(100vh-4rem)] p-4 md:p-8">{children}</main>

      </div>
    </div>
  );
}

