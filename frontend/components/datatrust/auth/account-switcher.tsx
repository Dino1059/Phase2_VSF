'use client';
import { useState, useRef, useEffect } from 'react';
import {
  ShieldCheck,
  Activity,
  Check,
  ArrowRightLeft,
  ChevronDown,
  Building2,
  Mail,
  UserCheck,
} from 'lucide-react';
import { useAgentStore, USER_ACCOUNTS, type UserAccount } from '@/lib/agent-store';
import { cn } from '@/lib/utils';

export function AccountSwitcher() {
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const { currentUser, switchAccount } = useAgentStore();

  const isAuditor = currentUser.id === 'auditor';
  const otherAccount: UserAccount = isAuditor ? USER_ACCOUNTS.admin : USER_ACCOUNTS.auditor;

  // Handle click outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleSwitch = (id: 'auditor' | 'admin') => {
    switchAccount(id);
    setOpen(false);
  };

  return (
    <div className="relative" ref={containerRef}>
      {/* Trigger Button in Header Topbar */}
      <button
        onClick={() => setOpen((prev) => !prev)}
        className="flex items-center gap-2.5 rounded-xl border border-slate-200 bg-white px-2.5 py-1.5 shadow-2xs hover:border-slate-300 hover:bg-slate-50/80 transition active:scale-98 cursor-pointer text-left"
        aria-label="Chuyển đổi tài khoản người dùng"
        title="Bấm để đổi giữa tài khoản Kiểm toán viên IPO và Quản trị viên"
      >
        {/* Avatar with role color */}
        <div
          className={cn(
            'relative grid size-8 place-items-center rounded-lg text-xs font-bold text-white shadow-xs',
            isAuditor ? 'bg-[#0f3834] ring-1 ring-emerald-400' : 'bg-[#78350f] ring-1 ring-amber-400'
          )}
        >
          {currentUser.avatar}
          <span
            className={cn(
              'absolute -top-0.5 -right-0.5 size-2 rounded-full ring-1 ring-white',
              isAuditor ? 'bg-emerald-400' : 'bg-amber-400'
            )}
          />
        </div>

        {/* User Info */}
        <div className="hidden sm:block leading-tight">
          <div className="flex items-center gap-1.5">
            <strong className="text-xs font-bold text-slate-800">{currentUser.name}</strong>
            <span
              className={cn(
                'rounded-md px-1.5 py-0.2 text-[9px] font-bold uppercase tracking-wider',
                isAuditor
                  ? 'bg-emerald-50 text-[#007460] border border-emerald-200'
                  : 'bg-amber-50 text-amber-800 border border-amber-200'
              )}
            >
              {currentUser.badge}
            </span>
          </div>
          <small className="block text-[10px] text-slate-400 truncate max-w-[140px]">
            {currentUser.email}
          </small>
        </div>

        <ChevronDown size={14} className={cn('text-slate-400 transition-transform', open && 'rotate-180')} />
      </button>

      {/* Account Popover Dropdown */}
      {open && (
        <div className="absolute right-0 top-full mt-2 w-80 rounded-2xl border border-[#dcebe6] bg-white p-3 shadow-2xl z-50 animate-in fade-in zoom-in-95 duration-150">
          <div className="flex items-center justify-between pb-2 border-b border-slate-100 text-[11px] text-slate-500 font-semibold px-1">
            <span>Tài khoản đang đăng nhập</span>
            <span className="flex items-center gap-1 text-[#008b74]">
              <UserCheck size={12} /> GSM IAM
            </span>
          </div>

          {/* Current Active Account Box */}
          <div className="mt-2.5 rounded-xl border border-emerald-200 bg-emerald-50/50 p-3 space-y-1.5">
            <div className="flex items-start justify-between">
              <div className="flex items-center gap-2">
                <div
                  className={cn(
                    'grid size-8 place-items-center rounded-lg text-xs font-bold text-white shadow-2xs',
                    isAuditor ? 'bg-[#0f3834]' : 'bg-[#78350f]'
                  )}
                >
                  {currentUser.avatar}
                </div>
                <div>
                  <strong className="block text-xs font-bold text-slate-900">{currentUser.name}</strong>
                  <span className="block text-[10px] text-slate-500">{currentUser.role}</span>
                </div>
              </div>
              <span className="inline-flex items-center gap-1 rounded-full bg-emerald-100 px-2 py-0.5 text-[9px] font-bold text-emerald-800">
                <Check size={10} /> Đang dùng
              </span>
            </div>

            <div className="space-y-0.5 pt-1 text-[10px] text-slate-500 border-t border-emerald-200/60">
              <div className="flex items-center gap-1.5">
                <Mail size={11} className="text-slate-400" />
                <span>{currentUser.email}</span>
              </div>
              <div className="flex items-center gap-1.5">
                <Building2 size={11} className="text-slate-400" />
                <span>{currentUser.company}</span>
              </div>
            </div>
          </div>

          {/* Switch Target Section */}
          <div className="mt-3 pt-2.5 border-t border-slate-100">
            <span className="block text-[10px] font-bold uppercase tracking-wider text-slate-400 mb-2 px-1">
              Chuyển sang tài khoản khác:
            </span>

            <button
              onClick={() => handleSwitch(otherAccount.id)}
              className="w-full flex items-center justify-between rounded-xl border border-slate-200 bg-[#fbfdfc] p-2.5 hover:border-amber-400 hover:bg-amber-50/50 transition cursor-pointer text-left group"
            >
              <div className="flex items-center gap-2.5">
                <div
                  className={cn(
                    'grid size-8 place-items-center rounded-lg text-xs font-bold text-white shadow-2xs group-hover:scale-105 transition',
                    otherAccount.id === 'auditor' ? 'bg-[#0f3834]' : 'bg-[#78350f]'
                  )}
                >
                  {otherAccount.avatar}
                </div>
                <div>
                  <div className="flex items-center gap-1.5">
                    <strong className="text-xs font-bold text-slate-900">{otherAccount.name}</strong>
                    <span
                      className={cn(
                        'rounded px-1.5 py-0.2 text-[8px] font-bold uppercase',
                        otherAccount.id === 'auditor'
                          ? 'bg-emerald-50 text-[#007460] border border-emerald-200'
                          : 'bg-amber-50 text-amber-800 border border-amber-200'
                      )}
                    >
                      {otherAccount.badge}
                    </span>
                  </div>
                  <span className="block text-[10px] text-slate-500">{otherAccount.role}</span>
                </div>
              </div>

              <div className="flex items-center gap-1 text-[11px] font-bold text-[#008b74] group-hover:text-amber-700">
                <ArrowRightLeft size={13} />
              </div>
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
