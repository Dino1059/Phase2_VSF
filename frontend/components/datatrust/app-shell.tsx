'use client';

import { useState, useEffect } from 'react';
import { Link as RouterLink, useLocation } from 'react-router-dom';
import {
  CheckSquare,
  ChevronLeft,
  ChevronRight,
  LayoutGrid,
  ShieldCheck,
  Sparkles,
  UserCog,
  Workflow,
  X,
  Zap,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { useAgentStore, USER_ACCOUNTS, type AgentStoreState } from '@/lib/agent-store';
import { AiChatPane } from '@/components/datatrust/overview/ai-chat-pane';

interface NavItem {
  label: string;
  href: string;
  icon: typeof LayoutGrid;
}

// Bỏ tab "Kết quả", chỉ giữ Trang chủ, Lần chạy, Quy tắc & Chính sách
const navigation: NavItem[] = [
  { label: 'Trang chủ', href: '/overview', icon: LayoutGrid },
  { label: 'Lần chạy & Lineage', href: '/runs', icon: Workflow },
  { label: 'Quy tắc & Chính sách', href: '/rules', icon: CheckSquare },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = useLocation().pathname;
  const [isChatCollapsed, setIsChatCollapsed] = useState(false);
  const [isMobileChatOpen, setIsMobileChatOpen] = useState(false);

  const currentRole = useAgentStore((s: AgentStoreState) => s.currentRole);
  const setRole = useAgentStore((s: AgentStoreState) => s.setRole);
  const currentUser = USER_ACCOUNTS[currentRole];

  const homepageViewMode = useAgentStore((s: AgentStoreState) => s.homepageViewMode);
  const activeRunId = useAgentStore((s: AgentStoreState) => s.pipelineLevels.activeRunId);

  // Keyboard shortcut Alt + [ to toggle chat
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.altKey && e.key === '[') {
        e.preventDefault();
        setIsChatCollapsed((prev) => !prev);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  const getBreadcrumbTitle = () => {
    if (pathname.startsWith('/overview') || pathname === '/') {
      if (homepageViewMode === 'running_pipeline' || homepageViewMode === 'results_dashboard') {
        const shortId = activeRunId || 'RUN-20261007-021';
        return (
          <span className="flex items-center gap-1.5">
            <span className="text-slate-400 font-normal">Lần chạy</span>
            <span className="text-slate-300">/</span>
            <span className="font-bold text-slate-900 font-mono">{shortId}</span>
          </span>
        );
      }
      return 'TRANG CHỦ';
    }
    if (pathname.includes('/lineage')) return 'LẦN CHẠY & LINEAGE';
    if (pathname.startsWith('/runs')) return 'LẦN CHẠY & LINEAGE';
    if (pathname.startsWith('/rules')) return 'QUY TẮC & CHÍNH SÁCH';
    if (pathname.startsWith('/findings')) return 'VẤN ĐỀ PHÁT HIỆN';
    return 'TRANG CHỦ';
  };

  const getSectionIcon = () => {
    if (pathname.startsWith('/runs') || pathname.includes('/lineage')) return Workflow;
    if (pathname.startsWith('/rules')) return CheckSquare;
    return LayoutGrid;
  };

  const SectionIcon = getSectionIcon();

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-[#f7faf9] text-slate-900 font-sans">
      {/* ========================================================================= */}
      {/* 1. SLIM VERTICAL ICON RAIL (w-[68px])                                     */}
      {/* ========================================================================= */}
      <aside
        aria-label="Thanh điều hướng biểu tượng"
        className="w-[68px] shrink-0 border-r border-[#e2ece8] bg-white flex flex-col items-center justify-between py-4 z-40 select-none"
      >
        <div className="flex flex-col items-center gap-6 w-full">
          {/* Logo brand pill */}
          <RouterLink
            to="/overview"
            aria-label="DataTrust OS"
            title="DataTrust OS"
            className="grid size-11 place-items-center rounded-xl bg-slate-950 text-[#04D3D4] border border-[#04D3D4]/40 shadow-xs hover:scale-105 transition-all motion-reduce:transition-none focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-[#04D3D4] focus-visible:ring-offset-2"
          >
            <Zap size={20} className="text-[#04D3D4] fill-[#FFC402]" />
          </RouterLink>

          {/* Navigation icons */}
          <nav aria-label="Điều hướng chính" className="flex flex-col items-center gap-2.5 w-full px-2">
            {navigation.map((item) => {
              const active =
                pathname === item.href ||
                (item.href === '/overview' && pathname === '/') ||
                pathname.startsWith(item.href + '/');
              const Icon = item.icon;

              return (
                <RouterLink
                  key={item.href}
                  to={item.href}
                  aria-label={item.label}
                  title={item.label}
                  aria-current={active ? 'page' : undefined}
                  className={cn(
                    'group relative flex size-11 items-center justify-center rounded-xl transition-all motion-reduce:transition-none cursor-pointer',
                    'focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-[#04D3D4] focus-visible:ring-offset-2',
                    active
                      ? 'bg-[#04D3D4]/15 border border-[#04D3D4]/40 text-[#04D3D4] shadow-2xs font-bold'
                      : 'text-slate-500 hover:bg-slate-100 hover:text-slate-900 border border-transparent'
                  )}
                >
                  <Icon size={19} className={active ? 'text-[#04D3D4]' : 'text-slate-500 group-hover:text-slate-800'} />
                  {/* Tooltip on hover */}
                  <span
                    role="tooltip"
                    className="pointer-events-none absolute left-[calc(100%+8px)] hidden rounded-lg bg-slate-900 px-2.5 py-1 text-xs font-semibold text-white shadow-lg group-hover:block z-50 whitespace-nowrap"
                  >
                    {item.label}
                  </span>
                </RouterLink>
              );
            })}
          </nav>
        </div>

        {/* Footer GSM Badge */}
        <div className="flex flex-col items-center gap-3 w-full">
          {/* Mobile AI Chat toggle in rail */}
          <button
            type="button"
            onClick={() => setIsMobileChatOpen((v) => !v)}
            aria-label={isMobileChatOpen ? 'Đóng AI Chat' : 'Mở AI Chat'}
            aria-expanded={isMobileChatOpen}
            title="Bật/tắt AI Chat trên di động"
            className="lg:hidden grid size-10 place-items-center rounded-xl bg-teal-50 border border-teal-200 text-teal-700 hover:bg-teal-100 transition motion-reduce:transition-none focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-[#04D3D4]"
          >
            <Sparkles size={18} className="text-[#04D3D4] fill-[#04D3D4]" />
          </button>

          <div
            title="GSM Global · Chiến dịch V35 · 24 thị trường"
            className="grid size-9 place-items-center rounded-xl bg-[#04D3D4]/15 text-[10px] font-extrabold text-slate-900 border border-[#04D3D4]/30"
          >
            GSM
          </div>
        </div>
      </aside>

      {/* ========================================================================= */}
      {/* 2. PERSISTENT AI CHAT PANE (DUAL-PANE LEFT)                                */}
      {/* ========================================================================= */}
      {/* Mobile Backdrop */}
      {isMobileChatOpen && (
        <div
          role="button"
          tabIndex={0}
          aria-label="Đóng khung AI Chat"
          onClick={() => setIsMobileChatOpen(false)}
          onKeyDown={(e) => {
            if (e.key === 'Escape' || e.key === 'Enter') setIsMobileChatOpen(false);
          }}
          className="fixed inset-0 z-40 bg-slate-950/40 backdrop-blur-xs lg:hidden cursor-pointer"
        />
      )}

      {/* The Chat Container - Persistent in React tree across navigation */}
      <aside
        aria-label="Khung trợ lý DataTrust AI"
        data-testid="persistent-ai-chat-pane"
        className={cn(
          // Base shared styles
          'h-full flex flex-col bg-white border-r border-[#e2ece8] z-30 transition-all duration-300 ease-in-out motion-reduce:transition-none motion-reduce:transform-none',
          // Desktop styles: inline side-by-side with dynamic workspace
          'hidden lg:flex relative shrink-0',
          isChatCollapsed ? 'lg:w-0 lg:border-r-0 lg:overflow-hidden' : 'lg:w-[380px] xl:w-[410px] 2xl:w-[430px]',
          // Mobile styles: slide-over overlay drawer when open
          isMobileChatOpen && 'flex! fixed inset-y-0 left-[68px] z-50 w-[min(400px,calc(100vw-68px))] shadow-2xl'
        )}
      >
        {/* Mobile close header */}
        <div className="lg:hidden flex items-center justify-between border-b border-slate-100 bg-[#fafcfb] px-4 py-2 shrink-0">
          <span className="text-xs font-bold text-slate-700">Trợ lý AI Orchestrator</span>
          <button
            type="button"
            onClick={() => setIsMobileChatOpen(false)}
            aria-label="Đóng AI Chat"
            className="p-1 rounded-lg text-slate-400 hover:text-slate-700 hover:bg-slate-100 transition motion-reduce:transition-none"
          >
            <X size={16} />
          </button>
        </div>

        {/* The persistent AI Chat Component */}
        <div className="flex-1 min-h-0 h-full overflow-hidden">
          <AiChatPane />
        </div>
      </aside>

      {/* Desktop Chevron Toggle Button at Chat boundary */}
      <button
        type="button"
        onClick={() => setIsChatCollapsed((prev) => !prev)}
        aria-label={isChatCollapsed ? 'Mở rộng khung AI Chat' : 'Thu gọn khung AI Chat'}
        aria-expanded={!isChatCollapsed}
        title={isChatCollapsed ? 'Mở rộng khung AI Chat (Alt + [)' : 'Thu gọn khung AI Chat (Alt + [)'}
        className={cn(
          'hidden lg:flex fixed top-1/2 -translate-y-1/2 z-40 items-center justify-center size-6 rounded-full bg-white border border-slate-300 text-slate-600 shadow-md hover:text-slate-950 hover:border-[#04D3D4] hover:scale-110 transition-all motion-reduce:transition-none cursor-pointer',
          'focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-[#04D3D4]',
          isChatCollapsed ? 'left-[68px] translate-x-1.5' : 'left-[calc(68px+380px-12px)] xl:left-[calc(68px+410px-12px)] 2xl:left-[calc(68px+430px-12px)]'
        )}
      >
        {isChatCollapsed ? <ChevronRight size={14} /> : <ChevronLeft size={14} />}
      </button>

      {/* ========================================================================= */}
      {/* 3. DYNAMIC WORKSPACE CANVAS (DUAL-PANE RIGHT)                             */}
      {/* ========================================================================= */}
      <div className="flex-1 flex flex-col min-w-0 h-full overflow-hidden">
        {/* Topbar matching base_UI.png */}
        <header className="sticky top-0 z-20 flex h-14 sm:h-16 shrink-0 items-center justify-between border-b border-[#e2ece8] bg-white/95 px-4 sm:px-6 backdrop-blur-md">
          {/* Breadcrumb Title */}
          <div className="flex items-center gap-2.5 min-w-0">
            <span className="grid size-7 place-items-center rounded-lg bg-teal-50 text-[#008b74] border border-teal-200 shrink-0">
              <SectionIcon size={15} />
            </span>
            <div className="text-xs font-bold tracking-wider text-slate-800 uppercase truncate">
              {getBreadcrumbTitle()}
            </div>
          </div>

          {/* Right Action Bar */}
          <div className="flex items-center gap-3 shrink-0">
            {/* Mobile AI Chat summon button */}
            <button
              type="button"
              onClick={() => setIsMobileChatOpen((prev) => !prev)}
              aria-label="Bật/tắt khung AI Chat"
              aria-expanded={isMobileChatOpen}
              className="lg:hidden flex items-center gap-1.5 rounded-xl border border-teal-200 bg-teal-50 px-2.5 py-1.5 text-xs font-bold text-teal-800 shadow-2xs hover:bg-teal-100 transition motion-reduce:transition-none cursor-pointer focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-[#04D3D4]"
            >
              <Sparkles size={13} className="text-[#04D3D4] fill-[#04D3D4]" />
              <span>AI Chat</span>
            </button>

            {/* Interactive Role Switcher Pill */}
            <div
              role="group"
              aria-label="Chuyển đổi vai trò người dùng"
              className="flex items-center rounded-xl border border-[#d2e2dc] bg-[#f0f6f4] p-0.5 text-xs font-semibold"
            >
              <button
                type="button"
                onClick={() => setRole('auditor')}
                aria-pressed={currentRole === 'auditor'}
                className={cn(
                  'flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 transition text-xs cursor-pointer motion-reduce:transition-none',
                  'focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-[#04D3D4]',
                  currentRole === 'auditor'
                    ? 'bg-slate-950 text-[#04D3D4] shadow-2xs font-bold'
                    : 'text-slate-600 hover:text-slate-900'
                )}
                title="Chế độ Kiểm toán viên (Thẩm tra & Kiểm toán độc lập)"
              >
                <ShieldCheck size={14} className={currentRole === 'auditor' ? 'text-[#04D3D4]' : ''} />
                <span>Auditor</span>
              </button>
              <button
                type="button"
                onClick={() => setRole('admin')}
                aria-pressed={currentRole === 'admin'}
                className={cn(
                  'flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 transition text-xs cursor-pointer motion-reduce:transition-none',
                  'focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-[#04D3D4]',
                  currentRole === 'admin'
                    ? 'bg-[#04D3D4] text-slate-950 shadow-2xs font-bold'
                    : 'text-slate-600 hover:text-slate-900'
                )}
                title="Chế độ Quản trị viên hệ thống (Admin Controller)"
              >
                <UserCog size={14} />
                <span>Admin</span>
              </button>
            </div>

            {/* User Account Pill */}
            <div className="hidden sm:flex items-center gap-2.5 rounded-xl border border-[#e2ece8] bg-white px-3 py-1.5 text-xs shadow-2xs">
              <div className="grid size-7 place-items-center rounded-lg bg-slate-950 font-mono text-[11px] font-bold text-[#04D3D4] border border-[#04D3D4]/30">
                {currentUser.avatar}
              </div>
              <div className="flex flex-col text-left leading-tight">
                <span className="font-bold text-slate-900">{currentUser.name}</span>
                <span className="text-[10px] text-slate-500 font-medium">{currentUser.badge}</span>
              </div>
            </div>
          </div>
        </header>

        {/* Dynamic Workspace Scroll Canvas */}
        <main
          id="main-content"
          aria-label="Không gian làm việc"
          className="flex-1 min-w-0 h-full overflow-y-auto p-4 sm:p-6 lg:p-7"
        >
          {children}
        </main>
      </div>
    </div>
  );
}
