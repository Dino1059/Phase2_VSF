import React, { useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useAuthStore, PERSONA_ACCOUNTS, type PersonaAccount, type SystemAccessType } from '@/src/stores/authStore';
import {
  Zap,
  ArrowRight,
  UserCheck,
  KeyRound,
  Layers,
  Shield,
  Database,
  Lock,
} from 'lucide-react';

export function LoginPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const redirectTarget = searchParams.get('redirect');

  const [activeTab, setActiveTab] = useState<'personas' | 'credentials'>('personas');
  const [selectedGroupFilter, setSelectedGroupFilter] = useState<'all' | 'both' | 'sod_only' | 'datatrust_only'>('all');
  const [usernameInput, setUsernameInput] = useState('');
  const [passwordInput, setPasswordInput] = useState('');
  const [errorMessage, setErrorMessage] = useState('');
  const [loadingPersonaId, setLoadingPersonaId] = useState<string | null>(null);

  const loginWithPersona = useAuthStore((s) => s.loginWithPersona);
  const loginWithCredentials = useAuthStore((s) => s.loginWithCredentials);

  const handleSelectPersona = (p: PersonaAccount) => {
    setLoadingPersonaId(p.id);
    setErrorMessage('');
    try {
      const destination = loginWithPersona(p.id);
      // If redirect param matches user's allowed target, respect it, else go to persona's default
      const finalRoute = redirectTarget && isRouteAllowed(p.systemAccess, redirectTarget)
        ? decodeURIComponent(redirectTarget)
        : destination;

      setTimeout(() => {
        navigate(finalRoute);
      }, 250);
    } catch (err: any) {
      console.error('Lỗi khi chọn persona:', err);
      setErrorMessage(err?.message || 'Không thể đăng nhập bằng vai trò này. Vui lòng thử lại.');
      setLoadingPersonaId(null);
    }
  };

  const handleCredentialsSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!usernameInput.trim()) {
      setErrorMessage('Vui lòng nhập tên tài khoản');
      return;
    }
    setErrorMessage('');
    try {
      const destination = await loginWithCredentials(usernameInput.trim(), passwordInput);
      const finalRoute = redirectTarget ? decodeURIComponent(redirectTarget) : destination;
      navigate(finalRoute);
    } catch {
      setErrorMessage('Đăng nhập không thành công. Vui lòng thử lại.');
    }
  };

  const isRouteAllowed = (access: SystemAccessType, route: string): boolean => {
    const norm = route.toLowerCase();
    if (access === 'both') return true;
    if (access === 'sod_only' && norm.startsWith('/sod')) return true;
    if (access === 'datatrust_only' && !norm.startsWith('/sod')) return true;
    return false;
  };

  const personasList = Object.values(PERSONA_ACCOUNTS);
  const bothPersonas = personasList.filter((p) => p.systemAccess === 'both');
  const sodPersonas = personasList.filter((p) => p.systemAccess === 'sod_only');
  const dtPersonas = personasList.filter((p) => p.systemAccess === 'datatrust_only');

  return (
    <div className="min-h-screen bg-[#f8fafb] text-slate-800 flex flex-col justify-between selection:bg-[#04D3D4]/30 selection:text-slate-900 font-sans relative overflow-x-hidden">
      {/* Background ambient lighting - Light mode soft gradients */}
      <div className="fixed inset-0 overflow-hidden pointer-events-none">
        <div className="absolute -top-40 -left-40 size-[450px] rounded-full bg-[#04D3D4]/12 blur-3xl" />
        <div className="absolute top-1/3 -right-40 size-[500px] rounded-full bg-[#008b74]/8 blur-3xl" />
        <div className="absolute -bottom-40 left-1/3 size-[450px] rounded-full bg-[#FFC402]/8 blur-3xl" />
      </div>

      {/* Top Header - Light Mode Clean GSM Branding */}
      <header className="relative z-10 border-b border-[#e2ece8] bg-white/90 backdrop-blur-md px-6 py-4 flex items-center justify-between shadow-2xs">
        <div className="flex items-center gap-3">
          <div className="grid size-10 place-items-center rounded-xl bg-slate-950 border border-slate-900 text-[#04D3D4] shadow-xs">
            <Zap size={20} className="fill-[#FFC402] text-[#04D3D4]" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-extrabold tracking-tight text-slate-900 text-base">USER LOGIN</span>
            </div>
            <p className="text-[11px] text-slate-500">Cổng Đăng nhập Tập trung & Điều hướng Phân quyền RACIX</p>
          </div>
        </div>
      </header>

      {/* Main Content Container */}
      <main className="relative z-10 flex-1 max-w-6xl w-full mx-auto px-4 py-8 sm:py-10 flex flex-col gap-6">
        {/* Tab Switcher & Filter Pills */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between border-b border-[#e2ece8] pb-3 gap-3">
          <div className="flex items-center gap-1.5 bg-slate-100/90 p-1 rounded-xl border border-slate-200/80 shadow-inner">
            <button
              type="button"
              onClick={() => setActiveTab('personas')}
              className={`flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-xs font-semibold transition cursor-pointer ${
                activeTab === 'personas'
                  ? 'bg-white text-slate-900 font-bold shadow-xs border border-slate-200/60'
                  : 'text-slate-600 hover:text-slate-900 hover:bg-white/60'
              }`}
            >
              <UserCheck size={14} className={activeTab === 'personas' ? 'text-[#008b74]' : 'text-slate-500'} />
              <span>Chọn Persona nhanh (14 Roles)</span>
            </button>
            <button
              type="button"
              onClick={() => setActiveTab('credentials')}
              className={`flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-xs font-semibold transition cursor-pointer ${
                activeTab === 'credentials'
                  ? 'bg-white text-slate-900 font-bold shadow-xs border border-slate-200/60'
                  : 'text-slate-600 hover:text-slate-900 hover:bg-white/60'
              }`}
            >
              <KeyRound size={14} className={activeTab === 'credentials' ? 'text-[#008b74]' : 'text-slate-500'} />
              <span>Đăng nhập Tài khoản</span>
            </button>
          </div>

          {activeTab === 'personas' && (
            <div className="flex items-center gap-1.5 text-xs text-slate-500 overflow-x-auto pb-1 sm:pb-0">
              <span className="text-[11px] uppercase tracking-wider text-slate-500 font-semibold mr-1 shrink-0">Lọc nhóm:</span>
              <button
                type="button"
                onClick={() => setSelectedGroupFilter('all')}
                className={`px-2.5 py-1 rounded-md transition cursor-pointer shrink-0 ${
                  selectedGroupFilter === 'all'
                    ? 'bg-white text-slate-900 border border-slate-300 font-bold shadow-2xs'
                    : 'hover:bg-white hover:text-slate-900 text-slate-600'
                }`}
              >
                Tất cả (14)
              </button>
              <button
                type="button"
                onClick={() => setSelectedGroupFilter('both')}
                className={`px-2.5 py-1 rounded-md transition cursor-pointer shrink-0 ${
                  selectedGroupFilter === 'both'
                    ? 'bg-teal-50 text-teal-900 font-bold border border-teal-300 shadow-2xs'
                    : 'hover:bg-teal-50/60 hover:text-teal-900 text-slate-600'
                }`}
              >
                Cả hai (4)
              </button>
              <button
                type="button"
                onClick={() => setSelectedGroupFilter('sod_only')}
                className={`px-2.5 py-1 rounded-md transition cursor-pointer shrink-0 ${
                  selectedGroupFilter === 'sod_only'
                    ? 'bg-indigo-50 text-indigo-900 font-bold border border-indigo-300 shadow-2xs'
                    : 'hover:bg-indigo-50/60 hover:text-indigo-900 text-slate-600'
                }`}
              >
                Chỉ SoD (7)
              </button>
              <button
                type="button"
                onClick={() => setSelectedGroupFilter('datatrust_only')}
                className={`px-2.5 py-1 rounded-md transition cursor-pointer shrink-0 ${
                  selectedGroupFilter === 'datatrust_only'
                    ? 'bg-amber-50 text-amber-900 font-bold border border-amber-300 shadow-2xs'
                    : 'hover:bg-amber-50/60 hover:text-amber-900 text-slate-600'
                }`}
              >
                Chỉ DataTrust (3)
              </button>
            </div>
          )}
        </div>

        {/* Tab 1: Personas Grid */}
        {activeTab === 'personas' && (
          <div className="space-y-8">
            {errorMessage && (
              <div className="p-3.5 rounded-xl bg-rose-50 border border-rose-200 text-rose-700 text-xs font-semibold shadow-xs">
                {errorMessage}
              </div>
            )}
            {/* NHÓM 1: CẢ HAI HỆ THỐNG */}
            {(selectedGroupFilter === 'all' || selectedGroupFilter === 'both') && (
              <section className="space-y-3">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <span className="grid size-6 place-items-center rounded-md bg-teal-50 text-[#008b74] border border-teal-200 text-xs font-bold shadow-2xs">
                      <Layers size={13} />
                    </span>
                    <h3 className="text-sm font-bold text-slate-900 tracking-wide uppercase">
                      Nhóm 1: Cả hai hệ thống (Both)
                    </h3>
                  </div>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3.5">
                  {bothPersonas.map((p) => (
                    <PersonaCard
                      key={p.id}
                      persona={p}
                      isLoading={loadingPersonaId === p.id}
                      onSelect={() => handleSelectPersona(p)}
                      colorTheme="teal"
                    />
                  ))}
                </div>
              </section>
            )}

            {/* NHÓM 2: CHỈ SOD FLOW */}
            {(selectedGroupFilter === 'all' || selectedGroupFilter === 'sod_only') && (
              <section className="space-y-3">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <span className="grid size-6 place-items-center rounded-md bg-indigo-50 text-indigo-700 border border-indigo-200 text-xs font-bold shadow-2xs">
                      <Shield size={13} />
                    </span>
                    <h3 className="text-sm font-bold text-slate-900 tracking-wide uppercase">
                      Nhóm 2: Hệ thống SoD Flow (SoD Only)
                    </h3>
                  </div>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3.5">
                  {sodPersonas.map((p) => (
                    <PersonaCard
                      key={p.id}
                      persona={p}
                      isLoading={loadingPersonaId === p.id}
                      onSelect={() => handleSelectPersona(p)}
                      colorTheme="indigo"
                    />
                  ))}
                </div>
              </section>
            )}

            {/* NHÓM 3: CHỈ DATATRUST OS */}
            {(selectedGroupFilter === 'all' || selectedGroupFilter === 'datatrust_only') && (
              <section className="space-y-3">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <span className="grid size-6 place-items-center rounded-md bg-amber-50 text-amber-700 border border-amber-200 text-xs font-bold shadow-2xs">
                      <Database size={13} />
                    </span>
                    <h3 className="text-sm font-bold text-slate-900 tracking-wide uppercase">
                      Nhóm 3: Hệ thống DataTrust OS (DataTrust Only)
                    </h3>
                  </div>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3.5">
                  {dtPersonas.map((p) => (
                    <PersonaCard
                      key={p.id}
                      persona={p}
                      isLoading={loadingPersonaId === p.id}
                      onSelect={() => handleSelectPersona(p)}
                      colorTheme="sky"
                    />
                  ))}
                </div>
              </section>
            )}
          </div>
        )}

        {/* Tab 2: Standard Credentials Login */}
        {activeTab === 'credentials' && (
          <div className="max-w-md w-full mx-auto bg-white border border-[#e2ece8] rounded-2xl p-6 sm:p-7 shadow-lg space-y-5 relative overflow-hidden">
            <div className="absolute top-0 left-0 right-0 h-1 bg-gradient-to-r from-[#04D3D4] via-[#008b74] to-[#FFC402]" />
            <div>
              <h2 className="text-base font-bold text-slate-900">Đăng nhập bằng Tài khoản</h2>
              <p className="text-xs text-slate-500 mt-1">
                Nhập tên đăng nhập để hệ thống tự động nhận diện thẩm quyền vai trò.
              </p>
            </div>

            {errorMessage && (
              <div className="p-3 rounded-xl bg-rose-50 border border-rose-200 text-rose-700 text-xs font-medium">
                {errorMessage}
              </div>
            )}

            <form onSubmit={handleCredentialsSubmit} className="space-y-4">
              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-slate-700 flex items-center justify-between">
                  <span>Tên tài khoản (Username)</span>
                  <span className="text-[10px] text-slate-400 font-mono">admin, auditor, an.nguyen...</span>
                </label>
                <div className="relative">
                  <input
                    type="text"
                    value={usernameInput}
                    onChange={(e) => setUsernameInput(e.target.value)}
                    placeholder="Nhập username..."
                    className="w-full bg-[#f8fafc] border border-slate-200 rounded-xl px-3.5 py-2.5 text-xs text-slate-900 placeholder:text-slate-400 focus:bg-white focus:outline-hidden focus:border-[#008b74] focus:ring-2 focus:ring-[#008b74]/20 transition"
                  />
                  <div className="absolute right-3 top-2.5 text-slate-400">
                    <UserCheck size={14} />
                  </div>
                </div>
              </div>

              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-slate-700 flex items-center justify-between">
                  <span>Mật khẩu</span>
                  <span className="text-[10px] text-slate-400 font-mono">Bất kỳ trong Demo</span>
                </label>
                <div className="relative">
                  <input
                    type="password"
                    value={passwordInput}
                    onChange={(e) => setPasswordInput(e.target.value)}
                    placeholder="••••••••"
                    className="w-full bg-[#f8fafc] border border-slate-200 rounded-xl px-3.5 py-2.5 text-xs text-slate-900 placeholder:text-slate-400 focus:bg-white focus:outline-hidden focus:border-[#008b74] focus:ring-2 focus:ring-[#008b74]/20 transition"
                  />
                  <div className="absolute right-3 top-2.5 text-slate-400">
                    <Lock size={14} />
                  </div>
                </div>
              </div>

              <button
                type="submit"
                className="w-full py-2.5 px-4 rounded-xl bg-slate-900 hover:bg-slate-800 text-[#04D3D4] font-extrabold text-xs flex items-center justify-center gap-2 transition cursor-pointer shadow-md hover:shadow-lg"
              >
                <span>Xác nhận Đăng nhập</span>
                <ArrowRight size={14} />
              </button>
            </form>

            <div className="pt-2 border-t border-slate-100 space-y-2">
              <span className="text-[11px] text-slate-500 font-semibold block">Tài khoản gợi ý nhanh:</span>
              <div className="flex flex-wrap gap-1.5">
                {[
                  { label: 'admin', role: 'Admin (Both)' },
                  { label: 'auditor', role: 'Auditor (Both)' },
                  { label: 'an.nguyen', role: 'Requestor (SoD)' },
                  { label: 'giang.hoang', role: 'CISO (SoD)' },
                  { label: 'steward.le', role: 'Steward (DataTrust)' },
                ].map((item) => (
                  <button
                    key={item.label}
                    type="button"
                    onClick={() => {
                      setUsernameInput(item.label);
                      setPasswordInput('demo123');
                    }}
                    className="text-[11px] px-2.5 py-1 rounded-lg bg-slate-100 hover:bg-slate-200 hover:text-slate-900 text-slate-700 border border-slate-200 font-mono transition cursor-pointer shadow-2xs"
                  >
                    {item.label}
                  </button>
                ))}
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}

interface PersonaCardProps {
  persona: PersonaAccount;
  isLoading: boolean;
  onSelect: () => void;
  colorTheme: 'teal' | 'indigo' | 'sky';
}

function PersonaCard({ persona, isLoading, onSelect, colorTheme }: PersonaCardProps) {
  // Light mode clean themes with GSM accents
  const themeStyles = {
    teal: {
      border: 'hover:border-[#04D3D4] hover:shadow-[0_8px_24px_rgba(4,211,212,0.18)]',
      badge: 'bg-teal-50 text-[#008b74] border border-teal-200 font-mono',
      avatar: 'bg-teal-50 border border-teal-200 text-[#008b74]',
      arrow: 'group-hover:text-[#008b74]',
      name: 'group-hover:text-[#008b74]',
    },
    indigo: {
      border: 'hover:border-indigo-400 hover:shadow-[0_8px_24px_rgba(99,102,241,0.15)]',
      badge: 'bg-indigo-50 text-indigo-700 border border-indigo-200 font-mono',
      avatar: 'bg-indigo-50 border border-indigo-200 text-indigo-700',
      arrow: 'group-hover:text-indigo-700',
      name: 'group-hover:text-indigo-700',
    },
    sky: {
      border: 'hover:border-amber-400 hover:shadow-[0_8px_24px_rgba(245,158,11,0.18)]',
      badge: 'bg-amber-50 text-amber-800 border border-amber-200 font-mono',
      avatar: 'bg-amber-50 border border-amber-200 text-amber-800',
      arrow: 'group-hover:text-amber-800',
      name: 'group-hover:text-amber-800',
    },
  }[colorTheme];

  return (
    <div
      onClick={onSelect}
      className={`group relative bg-white hover:bg-slate-50/80 border border-[#e2ece8] ${themeStyles.border} rounded-2xl p-4 transition-all duration-200 cursor-pointer flex flex-col justify-between shadow-xs hover:-translate-y-0.5`}
    >
      <div className="space-y-3">
        {/* Header with Avatar and Role Code */}
        <div className="flex items-start justify-between gap-2">
          <div className="flex items-center gap-2.5">
            <div
              className={`size-9 rounded-xl border flex items-center justify-center font-mono font-bold text-xs ${themeStyles.avatar}`}
            >
              {persona.avatar}
            </div>
            <div>
              <div className={`font-bold text-slate-900 text-xs leading-snug ${themeStyles.name} transition`}>
                {persona.fullName}
              </div>
              <div className="text-[10px] text-slate-400 font-mono">{persona.username}</div>
            </div>
          </div>

          <span className={`text-[10px] font-bold px-2 py-0.5 rounded-md border font-mono uppercase ${themeStyles.badge}`}>
            {persona.primaryRole}
          </span>
        </div>

        {/* Title & Badge */}
        <div className="space-y-1">
          <div className="text-[11px] font-semibold text-slate-700 leading-tight">
            {persona.badge}
          </div>
          <div className="text-[10px] text-slate-500 line-clamp-2 leading-relaxed">
            {persona.description}
          </div>
        </div>
      </div>

      {/* Card Action footer */}
      <div className="mt-4 pt-3 border-t border-slate-100 flex items-center justify-between text-[11px] text-slate-400">
        <span className={`flex items-center gap-1 font-semibold text-slate-600 ${themeStyles.arrow} group-hover:translate-x-0.5 transition`}>
          <span>{isLoading ? 'Đang nạp...' : 'Đăng nhập'}</span>
          <ArrowRight size={12} />
        </span>
      </div>
    </div>
  );
}
