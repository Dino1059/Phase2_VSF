'use client';
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Sparkles,
  ArrowUp,
  ShieldCheck,
  Search,
  Activity,
  FileText,
  Zap,
  BookOpen,
  ArrowRight,
  Database,
  CheckCircle2,
  Lock,
} from 'lucide-react';
import { useAgentStore } from '@/lib/agent-store';

export function AiLandingHub() {
  const navigate = useNavigate();
  const {
    currentUser,
    switchAccount,
    setActivePersona,
    setWorkspacePreviewTab,
    setWorkspaceInitialMessage,
  } = useAgentStore();

  const [query, setQuery] = useState('');
  const [selectedDatasetQuick, setSelectedDatasetQuick] = useState('trips');

  const isAuditor = currentUser.id === 'auditor';

  const handleStartWorkflow = (
    persona: 'auditor' | 'admin',
    tab: 'tests' | 'evidence' | 'telemetry' | 'adaptation',
    promptText: string
  ) => {
    setActivePersona(persona);
    setWorkspacePreviewTab(tab);
    setWorkspaceInitialMessage(promptText);
    navigate(`/workspace?persona=${persona}&tab=${tab}`);
  };

  const handleOmniboxSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const q = query.trim();
    if (!q) return;

    // Detect persona from query or fallback to current user
    const lower = q.toLowerCase();
    const querySuggestsAuditor =
      lower.includes('kiểm toán') ||
      lower.includes('audit') ||
      lower.includes('bằng chứng') ||
      lower.includes('evidence') ||
      lower.includes('sha-256') ||
      lower.includes('test case') ||
      lower.includes('tuân thủ') ||
      lower.includes('ipo');

    const persona = querySuggestsAuditor ? 'auditor' : currentUser.id;
    const tab =
      persona === 'auditor'
        ? lower.includes('evidence')
          ? 'evidence'
          : 'tests'
        : lower.includes('telemetry')
          ? 'telemetry'
          : 'adaptation';

    handleStartWorkflow(persona, tab, q);
  };

  return (
    <div className="page-enter mx-auto flex min-h-[calc(100vh-6rem)] max-w-5xl flex-col justify-between py-4 px-2 sm:px-4">
      {/* 1. Center Hero Section */}
      <div className="flex flex-col items-center text-center pt-2 sm:pt-6">
        {/* Animated Friendly Mascot Robot */}
        <div className="relative mb-5 flex size-24 items-center justify-center rounded-3xl bg-gradient-to-b from-[#0f3834] to-[#0a2724] shadow-xl border-2 border-amber-400/90 transition-transform duration-300 hover:scale-105">
          {/* Glowing pulse rings */}
          <div className="absolute -inset-1.5 rounded-3xl bg-amber-400/20 blur-sm animate-pulse" />
          
          {/* Mascot Face & Eyes */}
          <div className="relative flex flex-col items-center">
            {/* Golden Antenna with Sparkle */}
            <div className="absolute -top-6 flex flex-col items-center">
              <span className="size-2 rounded-full bg-amber-400 shadow-xs" />
              <span className="h-3 w-0.5 bg-amber-400" />
            </div>

            {/* Eyes */}
            <div className="flex items-center gap-3.5 pt-1">
              <span className="size-3.5 rounded-full bg-[#00d09c] shadow-[0_0_8px_#00d09c] animate-pulse" />
              <span className="size-3.5 rounded-full bg-[#00d09c] shadow-[0_0_8px_#00d09c] animate-pulse" />
            </div>
            
            {/* Friendly Smiling Mouth */}
            <div className="mt-2.5 h-1.5 w-6 rounded-full bg-amber-300/90" />
          </div>

          {/* Active online badge */}
          <span className="absolute -bottom-1 -right-1 flex size-5 items-center justify-center rounded-full bg-emerald-500 text-[10px] text-white ring-2 ring-white font-bold">
            ✓
          </span>
        </div>

        {/* Account indicator & quick switch banner */}
        <div className="mb-4 flex items-center gap-2 rounded-full border border-amber-300/80 bg-gradient-to-r from-amber-50 via-white to-emerald-50 px-3.5 py-1.5 text-xs shadow-2xs">
          <span className="text-slate-600 font-medium">
            Tài khoản: <strong className="text-slate-900 font-bold">{currentUser.name}</strong> ({currentUser.roleTitle})
          </span>
          <span className="text-slate-300">·</span>
        </div>

        {/* Title */}
        <h1 className="max-w-2xl text-2xl font-extrabold tracking-tight text-slate-900 sm:text-4xl">
          {isAuditor ? (
            <>
              Chào <span className="text-[#008b74]">anh Hoàng</span>, hôm nay anh muốn{' '}
              <span className="text-[#008b74]">kiểm thử tuân thủ</span> hay{' '}
              <span className="text-amber-600">tra cứu bằng chứng</span>?
            </>
          ) : (
            <>
              Chào <span className="text-amber-600">anh Bảo</span>, hôm nay anh muốn{' '}
              <span className="text-amber-600">giám sát pipeline</span> hay{' '}
              <span className="text-[#008b74]">thích ứng chính sách mới</span>?
            </>
          )}
        </h1>

        {/* Subtitle */}
        

        {/* 2. Central Omnibox Search (HubHome style) */}
        <div className="mt-7 w-full max-w-2xl">
          <form
            onSubmit={handleOmniboxSubmit}
            className="group relative rounded-2xl border-2 border-[#d2e4de] bg-white p-2.5 shadow-lg transition-all duration-200 hover:border-amber-400 focus-within:border-amber-400 focus-within:ring-4 focus-within:ring-amber-400/10"
          >
            <textarea
              rows={2}
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder={
                isAuditor
                  ? "Hỏi Agent về bằng chứng hoặc test case (VD: 'Tra cứu băm SHA-256 cuốc 0đ', 'Chạy test CCCD Nghị định 13')..."
                  : "Hỏi Agent về pipeline và rule mới (VD: 'Xem telemetry tỷ lệ lỗi Silver', 'Sinh rule cước đêm từ chính sách mới')..."
              }
              className="w-full resize-none border-0 bg-transparent px-3 py-1.5 text-xs sm:text-sm text-slate-800 placeholder:text-slate-400 focus:outline-none"
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  handleOmniboxSubmit(e);
                }
              }}
            />

            {/* Omnibox Footer Controls inside */}
            <div className="flex items-center justify-between pt-1 border-t border-slate-100 px-1">
              <div className="flex items-center gap-2">
                <span className="flex items-center gap-1 rounded-lg border border-slate-200 bg-slate-50 px-2 py-1 text-[11px] font-medium text-slate-600">
                  <Database size={11} className="text-[#008b74]" />
                  <select
                    value={selectedDatasetQuick}
                    onChange={(e) => setSelectedDatasetQuick(e.target.value)}
                    className="bg-transparent border-0 text-[11px] font-semibold text-slate-700 focus:outline-none cursor-pointer"
                  >
                    <option value="trips">trips</option>
                    <option value="customers">customers</option>
                    <option value="drivers">drivers</option>
                    <option value="charging">charging</option>
                    <option value="telemetry">telemetry</option>
                  </select>
                </span>

              </div>

              <button
                type="submit"
                disabled={!query.trim()}
                className="grid size-9 place-items-center rounded-xl bg-amber-500 hover:bg-amber-600 disabled:opacity-40 text-white shadow-sm transition active:scale-95 cursor-pointer"
                title="Gửi câu hỏi"
              >
                <ArrowUp size={16} />
              </button>
            </div>
          </form>
        </div>

        {/* 3. Action Cards Grid - Divided by 2 Personas */}
        <div className="mt-8 w-full max-w-4xl">
          <div className="flex items-center justify-between text-xs font-bold text-slate-600 mb-3.5 px-1">
            <div className="flex items-center gap-1.5">
              <Sparkles size={14} className="text-amber-500" />
              <span>
                {isAuditor
                  ? 'Kịch bản đề xuất cho Auditor IPO:'
                  : 'Kịch bản đề xuất cho System Admin:'}
              </span>
            </div>
          </div>

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4 text-left">
            {/* Card 1: Auditor Evidence */}
            <button
              onClick={() =>
                handleStartWorkflow(
                  'auditor',
                  'evidence',
                  'Tôi là Kiểm toán viên IPO, hãy cho tôi tra cứu bằng chứng bất biến SHA-256 cho 1.240 chuyến đi bất thường.'
                )
              }
              className={`group flex flex-col justify-between rounded-xl border bg-white p-4 shadow-xs transition hover:shadow-md cursor-pointer text-left ${
                isAuditor
                  ? 'border-[#008b74] ring-2 ring-[#008b74]/20 bg-gradient-to-b from-emerald-50/40 to-white'
                  : 'border-[#dcebe6] hover:border-[#008b74]'
              }`}
            >
              <div>
                <div className="flex items-center justify-between mb-2">
                  <div className="grid size-8 place-items-center rounded-lg bg-emerald-50 text-[#008b74] group-hover:bg-[#008b74] group-hover:text-white transition">
                    <Search size={16} />
                  </div>
                  <div className="flex items-center gap-1">
                    {isAuditor && (
                      <span className="rounded-full bg-emerald-600 px-1.5 py-0.5 text-[8px] font-bold text-white shadow-2xs">
                        Khuyên dùng
                      </span>
                    )}
                    <span className="rounded-full bg-emerald-50 border border-emerald-200 px-2 py-0.5 text-[9px] font-bold text-emerald-800">
                      Auditor IPO
                    </span>
                  </div>
                </div>
                <h4 className="text-xs font-bold text-slate-800 leading-snug group-hover:text-[#008b74] transition">
                  Tra cứu Bằng chứng Bất biến (SHA-256)
                </h4>
                <p className="mt-1 text-[11px] text-slate-500 leading-relaxed">
                  Kiểm tra chuỗi băm chứng cứ cho 1.240 cuốc xe cước 0đ phục vụ hồ sơ niêm yết Big 4.
                </p>
              </div>
              <span className="mt-3 flex items-center gap-1 text-[11px] font-semibold text-[#008b74]">
                Mở Evidence Store <ArrowRight size={11} />
              </span>
            </button>

            {/* Card 2: Auditor Test Runner */}
            <button
              onClick={() =>
                handleStartWorkflow(
                  'auditor',
                  'tests',
                  'Tôi muốn chạy các test case kiểm thử tuân thủ Nghị định 13 & GDPR xem hệ thống có bắt lỗi và cách ly đúng không.'
                )
              }
              className={`group flex flex-col justify-between rounded-xl border bg-white p-4 shadow-xs transition hover:shadow-md cursor-pointer text-left ${
                isAuditor
                  ? 'border-[#008b74] ring-2 ring-[#008b74]/20 bg-gradient-to-b from-emerald-50/40 to-white'
                  : 'border-[#dcebe6] hover:border-[#008b74]'
              }`}
            >
              <div>
                <div className="flex items-center justify-between mb-2">
                  <div className="grid size-8 place-items-center rounded-lg bg-emerald-50 text-[#008b74] group-hover:bg-[#008b74] group-hover:text-white transition">
                    <ShieldCheck size={16} />
                  </div>
                  <div className="flex items-center gap-1">
                    {isAuditor && (
                      <span className="rounded-full bg-emerald-600 px-1.5 py-0.5 text-[8px] font-bold text-white shadow-2xs">
                        Khuyên dùng
                      </span>
                    )}
                    <span className="rounded-full bg-emerald-50 border border-emerald-200 px-2 py-0.5 text-[9px] font-bold text-emerald-800">
                      Auditor IPO
                    </span>
                  </div>
                </div>
                <h4 className="text-xs font-bold text-slate-800 leading-snug group-hover:text-[#008b74] transition">
                  Chạy Test Case Kiểm thử Tuân thủ
                </h4>
                <p className="mt-1 text-[11px] text-slate-500 leading-relaxed">
                  Giả lập nạp dữ liệu lỗi (CCCD chưa che mờ, GPS ngoài vùng) để chứng thực tự động cách ly.
                </p>
              </div>
              <span className="mt-3 flex items-center gap-1 text-[11px] font-semibold text-[#008b74]">
                Mở Compliance Test Lab <ArrowRight size={11} />
              </span>
            </button>

            {/* Card 3: Admin Telemetry */}
            <button
              onClick={() =>
                handleStartWorkflow(
                  'admin',
                  'telemetry',
                  'Tôi là System Admin, hãy hiển thị telemetry hiệu năng luồng dữ liệu và tình trạng các làn cách ly (Quarantine).'
                )
              }
              className={`group flex flex-col justify-between rounded-xl border bg-white p-4 shadow-xs transition hover:shadow-md cursor-pointer text-left ${
                !isAuditor
                  ? 'border-amber-400 ring-2 ring-amber-400/25 bg-gradient-to-b from-amber-50/40 to-white'
                  : 'border-amber-200/80 hover:border-amber-400'
              }`}
            >
              <div>
                <div className="flex items-center justify-between mb-2">
                  <div className="grid size-8 place-items-center rounded-lg bg-amber-50 text-amber-700 group-hover:bg-amber-500 group-hover:text-white transition">
                    <Activity size={16} />
                  </div>
                  <div className="flex items-center gap-1">
                    {!isAuditor && (
                      <span className="rounded-full bg-amber-600 px-1.5 py-0.5 text-[8px] font-bold text-white shadow-2xs">
                        Khuyên dùng
                      </span>
                    )}
                    <span className="rounded-full bg-amber-50 border border-amber-200 px-2 py-0.5 text-[9px] font-bold text-amber-800">
                      System Admin
                    </span>
                  </div>
                </div>
                <h4 className="text-xs font-bold text-slate-800 leading-snug group-hover:text-amber-700 transition">
                  Giám sát Sức khỏe Pipeline & SLA
                </h4>
                <p className="mt-1 text-[11px] text-slate-500 leading-relaxed">
                  Theo dõi throughput TPS, tỷ lệ bản ghi sạch vào Silver vs Quarantine và độ trễ phân tán.
                </p>
              </div>
              <span className="mt-3 flex items-center gap-1 text-[11px] font-semibold text-amber-700">
                Xem Live Telemetry <ArrowRight size={11} />
              </span>
            </button>

            {/* Card 4: Admin Policy Adapt */}
            <button
              onClick={() =>
                handleStartWorkflow(
                  'admin',
                  'adaptation',
                  'GSM vừa ban hành chính sách cước phí mới, tôi muốn Agent phân tích và tự sinh rule thích ứng vào pipeline.'
                )
              }
              className={`group flex flex-col justify-between rounded-xl border bg-white p-4 shadow-xs transition hover:shadow-md cursor-pointer text-left ${
                !isAuditor
                  ? 'border-amber-400 ring-2 ring-amber-400/25 bg-gradient-to-b from-amber-50/40 to-white'
                  : 'border-amber-200/80 hover:border-amber-400'
              }`}
            >
              <div>
                <div className="flex items-center justify-between mb-2">
                  <div className="grid size-8 place-items-center rounded-lg bg-amber-50 text-amber-700 group-hover:bg-amber-500 group-hover:text-white transition">
                    <FileText size={16} />
                  </div>
                  <div className="flex items-center gap-1">
                    {!isAuditor && (
                      <span className="rounded-full bg-amber-600 px-1.5 py-0.5 text-[8px] font-bold text-white shadow-2xs">
                        Khuyên dùng
                      </span>
                    )}
                    <span className="rounded-full bg-amber-50 border border-amber-200 px-2 py-0.5 text-[9px] font-bold text-amber-800">
                      System Admin
                    </span>
                  </div>
                </div>
                <h4 className="text-xs font-bold text-slate-800 leading-snug group-hover:text-amber-700 transition">
                  Tự động Thích ứng Rule từ Chính sách
                </h4>
                <p className="mt-1 text-[11px] text-slate-500 leading-relaxed">
                  Dán thông tư, chính sách mới để Agent tự sinh SQL/PySpark và mô phỏng tác động trước khi deploy.
                </p>
              </div>
              <span className="mt-3 flex items-center gap-1 text-[11px] font-semibold text-amber-700">
                Mở Adaptation Engine <ArrowRight size={11} />
              </span>
            </button>
          </div>
        </div>
      </div>

      {/* 4. Footer Trust Banner & Direct Overview Shortcut */}
      <div className="mt-8 pt-6 border-t border-[#e2ece8] flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 text-xs text-slate-500">
        <div className="flex flex-wrap items-center gap-4">
          <span className="flex items-center gap-1 text-[#007460] font-semibold">
            <Lock size={13} className="text-[#008b74]" /> Bằng chứng SHA-256 bất biến
          </span>
          <span className="flex items-center gap-1 text-[#007460] font-semibold">
            <CheckCircle2 size={13} className="text-[#008b74]" /> Chuẩn kiểm toán IPO Big 4
          </span>
          <span className="flex items-center gap-1 text-[#007460] font-semibold">
            <Zap size={13} className="text-amber-500" /> Tự thích ứng L1–L4
          </span>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={() => navigate('/overview')}
            className="font-bold text-[#008b74] hover:underline flex items-center gap-1 cursor-pointer"
          >
            <span>Vào Dashboard Tổng quan (new_UI)</span>
            <ArrowRight size={13} />
          </button>
          <span className="text-slate-300">|</span>
          <button
            onClick={() => navigate('/results?tab=evidence')}
            className="text-slate-500 hover:text-slate-800 flex items-center gap-1 cursor-pointer"
          >
            <BookOpen size={12} /> Cẩm nang
          </button>
        </div>
      </div>
    </div>
  );
}
