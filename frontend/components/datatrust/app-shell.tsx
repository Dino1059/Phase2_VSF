'use client';

import { useState, useEffect, useCallback } from 'react';
import { Link as RouterLink, useLocation, useNavigate } from 'react-router-dom';
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
  LogOut,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { useAgentStore, USER_ACCOUNTS, type AgentStoreState } from '@/lib/agent-store';
import { useAuthStore } from '@/src/stores/authStore';
import { AiChatPane } from '@/components/datatrust/overview/ai-chat-pane';
import { RoleSwitcherModal } from '@/src/components/auth/RoleSwitcherModal';

interface NavItem {
  label: string;
  href: string;
  icon: typeof LayoutGrid;
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const navigate = useNavigate();
  const pathname = useLocation().pathname;
  const [isRoleModalOpen, setIsRoleModalOpen] = useState(false);
  // Desktop chat width & drag resize state
  const [chatWidth, setChatWidth] = useState<number>(() => {
    try {
      const saved = localStorage.getItem('datatrust_ai_chat_width');
      if (saved) {
        const parsed = parseInt(saved, 10);
        if (!isNaN(parsed) && parsed >= 280 && parsed <= 850) return parsed;
      }
    } catch {}
    return 410;
  });
  const [isChatCollapsed, setIsChatCollapsed] = useState(false);
  const [isDragging, setIsDragging] = useState(false);
  const [isMobileChatOpen, setIsMobileChatOpen] = useState(false);

  // Drag-to-resize handlers
  const startResizing = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  const stopResizing = useCallback(() => {
    setIsDragging(false);
    try {
      localStorage.setItem('datatrust_ai_chat_width', String(chatWidth));
    } catch {}
  }, [chatWidth]);

  const resize = useCallback((e: MouseEvent) => {
    // 68px is the fixed left navigation bar width
    const rawWidth = e.clientX - 68;
    if (rawWidth < 160) {
      setIsChatCollapsed(true);
      return;
    }
    if (isChatCollapsed) {
      setIsChatCollapsed(false);
    }
    const maxWidth = Math.min(850, Math.max(380, window.innerWidth - 360));
    const clamped = Math.max(280, Math.min(rawWidth, maxWidth));
    setChatWidth(clamped);
  }, [isChatCollapsed]);

  useEffect(() => {
    if (isDragging) {
      window.addEventListener('mousemove', resize);
      window.addEventListener('mouseup', stopResizing);
      document.body.style.userSelect = 'none';
      document.body.style.cursor = 'col-resize';
    } else {
      document.body.style.userSelect = '';
      document.body.style.cursor = '';
    }
    return () => {
      window.removeEventListener('mousemove', resize);
      window.removeEventListener('mouseup', stopResizing);
      document.body.style.userSelect = '';
      document.body.style.cursor = '';
    };
  }, [isDragging, resize, stopResizing]);

  const currentRole = useAgentStore((s: AgentStoreState) => s.currentRole);

  const authUser = useAuthStore((s) => s.user);
  const authSystemAccess = useAuthStore((s) => s.systemAccess);
  const logout = useAuthStore((s) => s.logout);

  const currentUser = {
    avatar: authUser?.avatar || USER_ACCOUNTS[currentRole]?.avatar || 'AD',
    name: authUser?.fullName || USER_ACCOUNTS[currentRole]?.name || 'Quản trị viên',
    badge: authUser?.badge || (authSystemAccess === 'both' ? 'Cả hai hệ thống' : 'Chỉ DataTrust OS'),
  };

  const homepageViewMode = useAgentStore((s: AgentStoreState) => s.homepageViewMode);
  const activeRunId = useAgentStore((s: AgentStoreState) => s.pipelineLevels.activeRunId);

  // Dynamic Navigation Items: Append Tab 4 (Phân quyền & SoD) if systemAccess is 'both'
  const navigationItems: NavItem[] = [
    { label: 'Trang chủ', href: '/overview', icon: LayoutGrid },
    { label: 'Lần chạy & Lineage', href: '/runs', icon: Workflow },
    { label: 'Quy tắc & Chính sách', href: '/rules', icon: CheckSquare },
    ...(authSystemAccess === 'both'
      ? [{ label: 'Phân quyền & SoD', href: '/sod', icon: ShieldCheck }]
      : []),
  ];

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
    if (pathname.startsWith('/sod')) return 'PHÂN QUYỀN & SOD';
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
    if (pathname.startsWith('/sod')) return ShieldCheck;
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
            {navigationItems.map((item) => {
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
                    'flex size-11 items-center justify-center rounded-xl transition-all focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-[#04D3D4] focus-visible:ring-offset-2',
                    active
                      ? 'bg-[#04D3D4]/15 text-[#04D3D4]'
                      : 'text-slate-500 hover:bg-slate-100'
                  )}
                >
                  <Icon
                    size={19}
                    className={active ? 'text-[#04D3D4]' : 'text-slate-500'}
                  />
                </RouterLink>
              );
            })}
          </nav>
        </div>

        {/* Footer GSM Badge */}
        <div className="flex flex-col items-center gap-3 w-full">
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
        style={{
          width: isChatCollapsed ? 0 : `${chatWidth}px`,
        }}
        className={cn(
          // Base shared styles
          'h-full flex flex-col bg-white border-r border-[#e2ece8] z-30',
          !isDragging && 'transition-[width] duration-200 ease-in-out motion-reduce:transition-none motion-reduce:transform-none',
          // Desktop styles: inline side-by-side with dynamic workspace
          'hidden lg:flex relative shrink-0',
          isChatCollapsed && 'lg:border-r-0 lg:overflow-hidden',
          // Mobile styles: slide-over overlay drawer when open
          isMobileChatOpen && 'flex! fixed inset-y-0 left-[68px] z-50 w-[min(400px,calc(100vw-68px))]! shadow-2xl'
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

        {/* Desktop Draggable Resize Handle */}
        {!isChatCollapsed && (
          <div
            onMouseDown={startResizing}
            role="separator"
            aria-orientation="vertical"
            title="Kéo sang trái/phải để tùy chỉnh kích thước khung chat"
            className={cn(
              'hidden lg:flex absolute top-0 -right-1 w-2.5 h-full cursor-col-resize z-40 items-center justify-center transition-colors select-none group',
              isDragging ? 'bg-[#04D3D4]/80' : 'hover:bg-[#04D3D4]/40'
            )}
          >
            <div
              className={cn(
                'w-1 h-9 rounded-full transition-colors',
                isDragging ? 'bg-white shadow-xs' : 'bg-slate-300 group-hover:bg-[#008b74]'
              )}
            />
          </div>
        )}
      </aside>

      {/* ========================================================================= */}
      {/* 3. DYNAMIC WORKSPACE CANVAS (DUAL-PANE RIGHT)                             */}
      {/* ========================================================================= */}
      <div className="flex-1 flex flex-col min-w-0 h-full overflow-hidden">
        {/* Topbar matching base_UI.png */}
        <header className="sticky top-0 z-20 flex h-14 sm:h-16 shrink-0 items-center justify-between border-b border-[#e2ece8] bg-white/95 px-4 sm:px-6 backdrop-blur-md">
          {/* Breadcrumb Title */}
          <div className="flex items-center gap-2.5 min-w-0">
            {/* Desktop Toggle Button for AI Chat (Collapse/Expand) */}
            <button
              type="button"
              onClick={() => setIsChatCollapsed((prev) => !prev)}
              aria-label={isChatCollapsed ? "Mở rộng khung AI Chat" : "Thu gọn khung AI Chat"}
              aria-expanded={!isChatCollapsed}
              title={isChatCollapsed ? "Mở rộng khung AI Chat (Alt + [)" : "Thu gọn khung AI Chat (Alt + [)"}
              className="hidden lg:grid size-7 place-items-center rounded-lg border border-[#e2ece8] bg-white text-slate-600 hover:text-slate-900 hover:bg-slate-50 transition cursor-pointer shrink-0 focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-[#04D3D4]"
            >
              {isChatCollapsed ? <ChevronRight size={14} /> : <ChevronLeft size={14} />}
            </button>

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

            {/* Role Switcher Modal Trigger */}
            <button
              type="button"
              onClick={() => setIsRoleModalOpen(true)}
              title="Đổi vai trò trong 14 vai trò ITGC"
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl border border-teal-200 bg-teal-50 hover:bg-teal-100 text-teal-900 transition text-xs font-bold cursor-pointer shadow-2xs"
            >
              <UserCog size={14} className="text-[#008b74]" />
              <span>Đổi vai trò</span>
            </button>

            {/* User Account Pill */}
            <div className="hidden lg:flex items-center gap-2 rounded-xl border border-[#e2ece8] bg-white px-3 py-1.5 text-xs shadow-2xs">
              <div className="grid size-7 place-items-center rounded-lg bg-slate-950 font-mono text-[11px] font-bold text-[#04D3D4] border border-[#04D3D4]/30">
                {currentUser.avatar}
              </div>
              <div className="flex flex-col text-left leading-tight">
                <span className="font-bold text-slate-900">{currentUser.name}</span>
                <span className="text-[10px] text-slate-500 font-medium">{currentUser.badge}</span>
              </div>
            </div>

            {/* Logout button */}
            <button
              type="button"
              onClick={() => {
                logout();
                navigate('/login', { replace: true });
              }}
              title="Đăng xuất khỏi hệ thống"
              className="grid size-8 place-items-center rounded-xl border border-[#e2ece8] bg-white text-slate-500 hover:text-rose-600 hover:bg-rose-50 transition cursor-pointer shadow-2xs"
            >
              <LogOut size={14} />
            </button>
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

      {/* Role Switcher Modal */}
      <RoleSwitcherModal
        isOpen={isRoleModalOpen}
        onClose={() => setIsRoleModalOpen(false)}
      />
    </div>
  );
}
