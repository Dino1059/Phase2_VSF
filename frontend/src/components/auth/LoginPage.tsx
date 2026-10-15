import React, { useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useAuthStore, PERSONA_ACCOUNTS, type PersonaAccount, type SystemAccessType } from '@/src/stores/authStore';
import {
  Zap,
  ArrowRight,
  UserCheck,
  KeyRound,
  Info,
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
    const destination = loginWithPersona(p.id);
    // If redirect param matches user's allowed target, respect it, else go to persona's default
    const finalRoute = redirectTarget && isRouteAllowed(p.systemAccess, redirectTarget)
      ? decodeURIComponent(redirectTarget)
      : destination;

    setTimeout(() => {
      navigate(finalRoute);
    }, 250);
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
    <div className="min-h-screen bg-[#0f172a] text-slate-100 flex flex-col justify-between selection:bg-[#04D3D4] selection:text-slate-950 font-sans">
      {/* Background ambient lighting */}
      <div className="fixed inset-0 overflow-hidden pointer-events-none">
        <div className="absolute -top-40 -left-40 size-96 rounded-full bg-[#04D3D4]/10 blur-3xl" />
        <div className="absolute top-1/3 -right-40 size-96 rounded-full bg-teal-500/10 blur-3xl" />
        <div className="absolute -bottom-40 left-1/3 size-96 rounded-full bg-indigo-500/10 blur-3xl" />
      </div>

      {/* Top Header */}
      <header className="relative z-10 border-b border-slate-800/80 bg-slate-950/60 backdrop-blur-md px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="grid size-10 place-items-center rounded-xl bg-slate-900 border border-[#04D3D4]/50 text-[#04D3D4] shadow-xs">
            <Zap size={20} className="fill-[#FFC402] text-[#04D3D4]" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-extrabold tracking-tight text-white text-base">DataTrust OS</span>
              <span className="text-slate-500">×</span>
              <span className="font-bold text-teal-400 text-sm">SoD Flow</span>
              <span className="px-2 py-0.5 rounded-md text-[10px] font-bold bg-[#04D3D4]/15 text-[#04D3D4] border border-[#04D3D4]/30 uppercase tracking-wider">
                Phase 1 Demo
              </span>
            </div>
            <p className="text-[11px] text-slate-400">Cổng Đăng nhập Tập trung & Điều hướng Phân quyền RACIX</p>
          </div>
        </div>

        <div className="hidden sm:flex items-center gap-2 text-xs text-slate-400 bg-slate-900/80 px-3 py-1.5 rounded-lg border border-slate-800">
          <Shield size={14} className="text-[#04D3D4]" />
          <span>Segregation of Duties (14 Vai trò)</span>
        </div>
      </header>

      {/* Main Content Container */}
      <main className="relative z-10 flex-1 max-w-6xl w-full mx-auto px-4 py-8 sm:py-10 flex flex-col gap-6">
        {/* Banner Notice */}
        <div className="bg-slate-900/90 border border-slate-800 rounded-2xl p-4 sm:p-5 flex items-start gap-4 shadow-xl">
          <div className="size-10 rounded-xl bg-teal-950/80 border border-teal-800/60 text-teal-400 grid place-items-center shrink-0 mt-0.5">
            <Info size={18} />
          </div>
          <div className="space-y-1 text-xs leading-relaxed text-slate-300">
            <div className="font-semibold text-white flex items-center gap-2">
              <span>Cơ chế Xác thực Demo (Phase 1)</span>
              <span className="text-[10px] bg-amber-500/15 text-amber-300 border border-amber-500/30 px-2 py-0.5 rounded-full font-mono">
                Client Session · Zero-backend-dep
              </span>
            </div>
            <p>
              Hệ thống cung cấp sẵn 14 Persona mẫu tương ứng đầy đủ các vai trò trong tài liệu{' '}
              <span className="font-mono text-[#04D3D4]">KE_HOACH_SOD_DATATRUST.md mục 2</span>. Bạn có thể bấm chọn ngay một Persona để trải nghiệm luồng định tuyến tự động hoặc dùng form tài khoản tiêu chuẩn.
            </p>
          </div>
        </div>

        {/* Tab Switcher */}
        <div className="flex items-center justify-between border-b border-slate-800 pb-3">
          <div className="flex items-center gap-2 bg-slate-900/90 p-1 rounded-xl border border-slate-800">
            <button
              type="button"
              onClick={() => setActiveTab('personas')}
              className={`flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-xs font-semibold transition cursor-pointer ${
                activeTab === 'personas'
                  ? 'bg-[#04D3D4] text-slate-950 shadow-xs'
                  : 'text-slate-400 hover:text-white'
              }`}
            >
              <UserCheck size={14} />
              <span>Chọn Persona nhanh (14 Roles)</span>
            </button>
            <button
              type="button"
              onClick={() => setActiveTab('credentials')}
              className={`flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-xs font-semibold transition cursor-pointer ${
                activeTab === 'credentials'
                  ? 'bg-[#04D3D4] text-slate-950 shadow-xs'
                  : 'text-slate-400 hover:text-white'
              }`}
            >
              <KeyRound size={14} />
              <span>Đăng nhập Tài khoản</span>
            </button>
          </div>

          {activeTab === 'personas' && (
            <div className="hidden md:flex items-center gap-1.5 text-xs text-slate-400">
              <span className="text-[11px] uppercase tracking-wider text-slate-500 font-semibold mr-1">Lọc nhóm:</span>
              <button
                type="button"
                onClick={() => setSelectedGroupFilter('all')}
                className={`px-2.5 py-1 rounded-md transition cursor-pointer ${
                  selectedGroupFilter === 'all'
                    ? 'bg-slate-800 text-white font-bold'
                    : 'hover:bg-slate-900 text-slate-400'
                }`}
              >
                Tất cả (14)
              </button>
              <button
                type="button"
                onClick={() => setSelectedGroupFilter('both')}
                className={`px-2.5 py-1 rounded-md transition cursor-pointer ${
                  selectedGroupFilter === 'both'
                    ? 'bg-teal-950 text-teal-300 font-bold border border-teal-800/60'
                    : 'hover:bg-slate-900 text-slate-400'
                }`}
              >
                Cả hai (4)
              </button>
              <button
                type="button"
                onClick={() => setSelectedGroupFilter('sod_only')}
                className={`px-2.5 py-1 rounded-md transition cursor-pointer ${
                  selectedGroupFilter === 'sod_only'
                    ? 'bg-indigo-950 text-indigo-300 font-bold border border-indigo-800/60'
                    : 'hover:bg-slate-900 text-slate-400'
                }`}
              >
                Chỉ SoD (7)
              </button>
              <button
                type="button"
                onClick={() => setSelectedGroupFilter('datatrust_only')}
                className={`px-2.5 py-1 rounded-md transition cursor-pointer ${
                  selectedGroupFilter === 'datatrust_only'
                    ? 'bg-sky-950 text-sky-300 font-bold border border-sky-800/60'
                    : 'hover:bg-slate-900 text-slate-400'
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
            {/* NHÓM 1: CẢ HAI HỆ THỐNG */}
            {(selectedGroupFilter === 'all' || selectedGroupFilter === 'both') && (
              <section className="space-y-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="grid size-6 place-items-center rounded-md bg-teal-500/20 text-teal-400 text-xs font-bold">
                      <Layers size={13} />
                    </span>
                    <h3 className="text-sm font-bold text-white tracking-wide uppercase">
                      Nhóm 1: Cả hai hệ thống (Both)
                    </h3>
                    <span className="text-xs text-slate-400">· 4 vai trò tích hợp</span>
                  </div>
                  <span className="text-[11px] px-2.5 py-0.5 rounded-full bg-teal-500/10 text-teal-300 border border-teal-500/30 font-medium">
                    → Điều hướng: /overview + Tích hợp Tab Phân quyền & SoD
                  </span>
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
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="grid size-6 place-items-center rounded-md bg-indigo-500/20 text-indigo-400 text-xs font-bold">
                      <Shield size={13} />
                    </span>
                    <h3 className="text-sm font-bold text-white tracking-wide uppercase">
                      Nhóm 2: Hệ thống SoD Flow (SoD Only)
                    </h3>
                    <span className="text-xs text-slate-400">· 7 vai trò chuỗi RACIX</span>
                  </div>
                  <span className="text-[11px] px-2.5 py-0.5 rounded-full bg-indigo-500/10 text-indigo-300 border border-indigo-500/30 font-medium">
                    → Điều hướng: /sod (SoD Standalone Workspace)
                  </span>
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
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="grid size-6 place-items-center rounded-md bg-sky-500/20 text-sky-400 text-xs font-bold">
                      <Database size={13} />
                    </span>
                    <h3 className="text-sm font-bold text-white tracking-wide uppercase">
                      Nhóm 3: Hệ thống DataTrust OS (DataTrust Only)
                    </h3>
                    <span className="text-xs text-slate-400">· 3 vai trò dữ liệu</span>
                  </div>
                  <span className="text-[11px] px-2.5 py-0.5 rounded-full bg-sky-500/10 text-sky-300 border border-sky-500/30 font-medium">
                    → Điều hướng: /overview (3 Tabs tiêu chuẩn - Ẩn SoD)
                  </span>
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
          <div className="max-w-md w-full mx-auto bg-slate-900 border border-slate-800 rounded-2xl p-6 sm:p-7 shadow-2xl space-y-5">
            <div>
              <h2 className="text-base font-bold text-white">Đăng nhập bằng Tài khoản</h2>
              <p className="text-xs text-slate-400 mt-1">
                Nhập tên đăng nhập để hệ thống tự động nhận diện thẩm quyền vai trò.
              </p>
            </div>

            {errorMessage && (
              <div className="p-3 rounded-xl bg-rose-950/60 border border-rose-800/70 text-rose-300 text-xs font-medium">
                {errorMessage}
              </div>
            )}

            <form onSubmit={handleCredentialsSubmit} className="space-y-4">
              <div className="space-y-1.5">
                <label className="text-xs font-medium text-slate-300 flex items-center justify-between">
                  <span>Tên tài khoản (Username)</span>
                  <span className="text-[10px] text-slate-500">Ví dụ: admin, auditor, an.nguyen</span>
                </label>
                <div className="relative">
                  <input
                    type="text"
                    value={usernameInput}
                    onChange={(e) => setUsernameInput(e.target.value)}
                    placeholder="Nhập username..."
                    className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2.5 text-xs text-white placeholder:text-slate-600 focus:outline-hidden focus:border-[#04D3D4] focus:ring-1 focus:ring-[#04D3D4]"
                  />
                  <div className="absolute right-3 top-2.5 text-slate-600">
                    <UserCheck size={14} />
                  </div>
                </div>
              </div>

              <div className="space-y-1.5">
                <label className="text-xs font-medium text-slate-300 flex items-center justify-between">
                  <span>Mật khẩu</span>
                  <span className="text-[10px] text-slate-500 font-mono">Bất kỳ trong Demo</span>
                </label>
                <div className="relative">
                  <input
                    type="password"
                    value={passwordInput}
                    onChange={(e) => setPasswordInput(e.target.value)}
                    placeholder="••••••••"
                    className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2.5 text-xs text-white placeholder:text-slate-600 focus:outline-hidden focus:border-[#04D3D4] focus:ring-1 focus:ring-[#04D3D4]"
                  />
                  <div className="absolute right-3 top-2.5 text-slate-600">
                    <Lock size={14} />
                  </div>
                </div>
              </div>

              <button
                type="submit"
                className="w-full py-2.5 px-4 rounded-xl bg-[#04D3D4] hover:bg-[#04D3D4]/90 text-slate-950 font-bold text-xs flex items-center justify-center gap-2 transition cursor-pointer shadow-md shadow-[#04D3D4]/10"
              >
                <span>Xác nhận Đăng nhập</span>
                <ArrowRight size={14} />
              </button>
            </form>

            <div className="pt-2 border-t border-slate-800/80 space-y-2">
              <span className="text-[11px] text-slate-400 font-semibold block">Tài khoản Demo gợi ý nhanh:</span>
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
                    className="text-[11px] px-2 py-1 rounded-md bg-slate-800/70 hover:bg-slate-800 text-slate-300 border border-slate-700/60 font-mono transition cursor-pointer"
                  >
                    {item.label}
                  </button>
                ))}
              </div>
            </div>
          </div>
        )}
      </main>

      {/* Footer */}
      <footer className="relative z-10 border-t border-slate-800/80 bg-slate-950/40 px-6 py-3 text-center text-xs text-slate-500">
        DataTrust OS & SoD Flow · Segregation of Duties Integration · Phase 1: Unified UI & Authentication
      </footer>
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
  const themeStyles = {
    teal: {
      border: 'hover:border-teal-500/60',
      badge: 'bg-teal-500/10 text-teal-300 border-teal-500/30',
      avatar: 'bg-teal-950 border-teal-500/40 text-teal-300',
      arrow: 'group-hover:text-teal-400',
    },
    indigo: {
      border: 'hover:border-indigo-500/60',
      badge: 'bg-indigo-500/10 text-indigo-300 border-indigo-500/30',
      avatar: 'bg-indigo-950 border-indigo-500/40 text-indigo-300',
      arrow: 'group-hover:text-indigo-400',
    },
    sky: {
      border: 'hover:border-sky-500/60',
      badge: 'bg-sky-500/10 text-sky-300 border-sky-500/30',
      avatar: 'bg-sky-950 border-sky-500/40 text-sky-300',
      arrow: 'group-hover:text-sky-400',
    },
  }[colorTheme];

  return (
    <div
      onClick={onSelect}
      className={`group relative bg-slate-900/80 hover:bg-slate-800/90 border border-slate-800 ${themeStyles.border} rounded-2xl p-4 transition-all duration-200 cursor-pointer flex flex-col justify-between shadow-lg hover:shadow-xl hover:-translate-y-0.5`}
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
              <div className="font-bold text-white text-xs leading-snug group-hover:text-[#04D3D4] transition">
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
          <div className="text-[11px] font-semibold text-slate-300 leading-tight">
            {persona.badge}
          </div>
          <div className="text-[10px] text-slate-400 line-clamp-2 leading-relaxed">
            {persona.description}
          </div>
        </div>
      </div>

      {/* Card Action footer */}
      <div className="mt-4 pt-3 border-t border-slate-800/80 flex items-center justify-between text-[11px] text-slate-400">
        <span className="font-medium text-slate-400">
          {persona.systemAccess === 'both' ? 'DataTrust + Tab SoD' : persona.systemAccess === 'sod_only' ? 'SoD Standalone' : 'DataTrust OS'}
        </span>
        <span className={`flex items-center gap-1 font-semibold text-slate-300 ${themeStyles.arrow} transition`}>
          <span>{isLoading ? 'Đang nạp...' : 'Đăng nhập'}</span>
          <ArrowRight size={12} />
        </span>
      </div>
    </div>
  );
}
