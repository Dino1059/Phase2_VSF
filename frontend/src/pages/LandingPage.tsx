import React, { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowRight, ArrowUpRight } from 'lucide-react';
import { AuthModal } from '../components/auth/AuthModal';
import { useAuthStore } from '../stores/authStore';
import { changeLanguage, i18n } from '../i18n';
import '../assets/landing.css';

const HERO_POSTER = '/landing/hero.poster.webp';
const MOTIF_TELE = '/landing/motif.telemetry.webp';
const MOTIF_VIN = '/landing/motif.vin-fabric.webp';
const HERO_BASE = (import.meta.env.VITE_LANDING_HERO_BASE as string | undefined)?.replace(/\/$/, '') || 'https://t086-cdn.w9.nu';
const HERO_WEBM = `${HERO_BASE}/P-086/landing/hero.webm`;
const HERO_MP4 = `${HERO_BASE}/P-086/landing/hero.mp4`;
const LIVE_T086 = 'https://t086.w9.nu/';
const LIVE_D086 = 'https://d086.w9.nu/';

/** Bold Q1=C: layered pointer follow ranges (Awwwards intensity) */
const PTR = {
  far: { t: 40, r: 10 },
  mid: { t: 32, r: 8 },
  near: { t: 22, r: 6 },
  copy: { t: 14, r: 4 },
} as const;

type Lang = 'vi' | 'en';

const COPY = {
  vi: {
    brand: 'DataTrust OS',
    navProblem: 'Vấn đề',
    navProduct: 'Sản phẩm',
    navHitl: 'HITL',
    navRoles: 'Quyền hạn',
    navProof: 'Bằng chứng',
    login: 'Đăng nhập',
    enter: 'Vào hệ thống',
    liveT086: 'Môi trường live',
    eyebrow: 'Nền tảng chất lượng dữ liệu vận hành',
    headline: 'Từ landing bẩn đến warehouse tin cậy — có người gác cổng.',
    sub: 'Ingest theo ngày, HITL trước khi ghi, ACL theo dataset. LLM tắt vẫn vận hành được.',
    subEn: 'Day-scoped quality · preview ≠ execute · humans decide.',
    problemK: 'Vấn đề',
    problemH: 'Telemetry bẩn → quyết định sai.',
    problemL: 'Thiếu lineage theo ngày, hàng lỗi biến mất thầm, không có cổng duyệt trước khi rule vào warehouse.',
    problemLEn: 'No day proof · silent drops · no human gate.',
    problems: [
      { t: 'Không chứng minh được ngày sạch', d: 'Batch trôi và schema lệch — chỉ COUNT theo ngày mới là bằng chứng.', en: 'Day-scoped COUNT' },
      { t: 'Quarantine bị bỏ quên', d: 'Corrupt rows cần tách clean/quarantine có hash, không được nuốt thầm.', en: 'Hashed quarantine' },
      { t: 'Đề xuất ≠ được phép chạy', d: 'Compile rule không qua HITL là rủi ro vận hành.', en: 'Preview ≠ execute' },
    ],
    productK: 'Sản phẩm',
    productH: 'Ingest → Gate → Trust',
    productL: 'Ba lớp đủ để vận hành chất lượng dữ liệu mỗi ngày.',
    productLEn: 'Day-bound ingest · HITL gate · clean/quarantine lineage.',
    products: [
      { n: '01', t: 'Ingest theo ngày', d: 'Landing day-scoped; promote có kiểm soát vào warehouse.', en: 'Landing → promote' },
      { n: '02', t: 'Agents đề xuất', d: 'Profile / anomaly / rule card — deterministic, không tự ghi.', en: 'Propose only' },
      { n: '03', t: 'Govern + lineage', d: 'Clean / quarantine + SHA-256 — warehouse đáng tin.', en: 'Cryptographic split' },
    ],
    diagramIngest: 'Landing → Warehouse',
    diagramHitl: 'Preview ≠ Execute',
    diagramAcl: 'Steward A ≠ B',
    diagramLlm: 'LLM ON / OFF — HITL vẫn chạy',
    diagramCount: 'Day-scoped COUNT',
    hitlK: 'HITL',
    hitlH: 'AI đề xuất. Steward quyết định.',
    hitlL: 'Preview sandbox ≠ execute warehouse. Remember giữ quyết định. Tắt LLM vẫn dùng HITL.',
    hitlLEn: 'Sandbox preview · Accept / Edit / Reject · Remember · LLM-off useful.',
    hitlSteps: [
      { t: 'Đề xuất', d: 'Rule card + evidence từ agent.' },
      { t: 'Preview', d: 'Sandbox — không ghi warehouse.' },
      { t: 'Duyệt', d: 'Accept / Edit / Reject.' },
      { t: 'Remember', d: 'Giữ quyết định; LLM off vẫn dùng được.' },
    ],
    rolesK: 'Quyền hạn',
    rolesH: 'Đúng người, đúng dataset.',
    rolesL: 'ACL theo dataset_key. Steward scoped; Admin xem catalog/aggregate — không execute warehouse.',
    rolesLEn: 'dataset_key ACL · Admin names-only · no cross-read.',
    roles: [
      { t: 'Steward', d: 'Promote, HITL execute/Remember, ingest trên dataset được gán.', en: 'Write + HITL' },
      { t: 'Analyst', d: 'Đọc và phân tích; không execute warehouse.', en: 'Read + ask' },
      { t: 'Admin', d: 'Catalog + aggregate; quản user/reset — không execute.', en: 'Names + aggregate' },
      { t: 'Viewer', d: 'Chỉ xem trong phạm vi được gán.', en: 'Read scoped' },
    ],
    proofK: 'Bằng chứng',
    proofH: 'Môi trường live và UI đã kiểm chứng.',
    proofL: 'Staging vận hành thật — không số liệu marketing giả.',
    proofLEn: 'Live staging · QA’d UI · no vanity metrics.',
    shots: [
      { src: '/landing/proof/ingestion.png', cap: 'Ingest theo ngày' },
      { src: '/landing/proof/hitl.png', cap: 'Rules & HITL' },
      { src: '/landing/proof/workspace.png', cap: 'Workspace + evidence' },
      { src: '/landing/proof/llm-off.png', cap: 'LLM OFF — HITL vẫn chạy' },
    ],
    techK: 'Nền tảng',
    techH: 'Deterministic trước generative.',
    techChips: ['React + Vite', 'FastAPI', 'DuckDB', 'HITL sandbox', 'LLM on/off', 'dataset ACL'],
    footH: 'Sẵn sàng vào hệ thống?',
    footL: 'Đăng nhập để xem workspace. Preview trước — execute sau.',
    footNote: '© 2026 DataTrust OS',
    stagingNote: 't086 live · d086 sandbox',
  },
  en: {
    brand: 'DataTrust OS',
    navProblem: 'Problem',
    navProduct: 'Product',
    navHitl: 'HITL',
    navRoles: 'Access',
    navProof: 'Proof',
    login: 'Log in',
    enter: 'Enter OS',
    liveT086: 'Live environment',
    eyebrow: 'Operational data-quality platform',
    headline: 'Dirty landing to trusted warehouse — with a human gate.',
    sub: 'Day-bound ingest, HITL before write, dataset ACL. Works with LLM off.',
    subEn: 'Day-scoped quality · preview ≠ execute · humans decide.',
    problemK: 'Problem',
    problemH: 'Dirty telemetry → blind decisions.',
    problemL: 'No day-bound lineage, silent row loss, no steward gate before rules hit the warehouse.',
    problemLEn: 'No day proof · silent drops · no human gate.',
    problems: [
      { t: 'Which day is clean?', d: 'Drifting batches need day-scoped COUNT as proof.', en: 'Day-scoped COUNT' },
      { t: 'Forgotten quarantine', d: 'Corrupt rows need hashed clean/quarantine — not vanish.', en: 'Hashed quarantine' },
      { t: 'Propose ≠ allowed run', d: 'Without HITL, rule compile is operational risk.', en: 'Preview ≠ execute' },
    ],
    productK: 'Product',
    productH: 'Ingest → Gate → Trust',
    productL: 'Three layers for day-to-day data quality operations.',
    productLEn: 'Day-bound ingest · HITL gate · clean/quarantine lineage.',
    products: [
      { n: '01', t: 'Day-bound ingest', d: 'Landing tables by day; controlled promote into warehouse.', en: 'Landing → promote' },
      { n: '02', t: 'Agents propose', d: 'Profile / anomaly / rule card — deterministic, never auto-write.', en: 'Propose only' },
      { n: '03', t: 'Govern + lineage', d: 'Clean / quarantine + SHA-256 — trusted warehouse.', en: 'Cryptographic split' },
    ],
    diagramIngest: 'Landing → Warehouse',
    diagramHitl: 'Preview ≠ Execute',
    diagramAcl: 'Steward A ≠ B',
    diagramLlm: 'LLM ON / OFF — HITL still works',
    diagramCount: 'Day-scoped COUNT',
    hitlK: 'HITL',
    hitlH: 'AI proposes. Steward decides.',
    hitlL: 'Sandbox preview ≠ warehouse execute. Remember keeps decisions. Useful with LLM off.',
    hitlLEn: 'Sandbox preview · Accept / Edit / Reject · Remember · LLM-off useful.',
    hitlSteps: [
      { t: 'Propose', d: 'Rule card + evidence from the agent.' },
      { t: 'Preview', d: 'Sandbox — no warehouse write.' },
      { t: 'Decide', d: 'Accept / Edit / Reject.' },
      { t: 'Remember', d: 'Keep the decision; LLM-off still useful.' },
    ],
    rolesK: 'Access',
    rolesH: 'Right people, right datasets.',
    rolesL: 'dataset_key ACL. Stewards are scoped; Admin sees catalog/aggregate — never warehouse execute.',
    rolesLEn: 'dataset_key ACL · Admin names-only · no cross-read.',
    roles: [
      { t: 'Steward', d: 'Promote, HITL execute/Remember, ingest on assigned datasets.', en: 'Write + HITL' },
      { t: 'Analyst', d: 'Read and analyze; no warehouse execute.', en: 'Read + ask' },
      { t: 'Admin', d: 'Catalog + aggregate; users/reset — no execute.', en: 'Names + aggregate' },
      { t: 'Viewer', d: 'Scoped view only.', en: 'Read scoped' },
    ],
    proofK: 'Proof',
    proofH: 'Live environments. QA’d UI.',
    proofL: 'Real staging — no vanity metrics.',
    proofLEn: 'Live staging · QA’d UI · no vanity metrics.',
    shots: [
      { src: '/landing/proof/ingestion.png', cap: 'Day-bound ingest' },
      { src: '/landing/proof/hitl.png', cap: 'Rules & HITL' },
      { src: '/landing/proof/workspace.png', cap: 'Workspace + evidence' },
      { src: '/landing/proof/llm-off.png', cap: 'LLM OFF — HITL still works' },
    ],
    techK: 'Platform',
    techH: 'Deterministic before generative.',
    techChips: ['React + Vite', 'FastAPI', 'DuckDB', 'HITL sandbox', 'LLM on/off', 'dataset ACL'],
    footH: 'Ready to enter?',
    footL: 'Log in to the workspace. Preview first — execute later.',
    footNote: '© 2026 DataTrust OS',
    stagingNote: 't086 live · d086 sandbox',
  },
} as const;

export const DataTrustLogo: React.FC<{ size?: number; className?: string }> = ({ size = 22, className = '' }) => {
  const path =
    'M 1.5,23 L 1.5,33 C 1.5,38.5 6,43 11.5,43 L 16.5,43 C 22,43 26.5,38.5 26.5,33 Q 28,28 33,26.5 C 38.5,26.5 43,22 43,16.5 L 43,11.5 C 43,6 38.5,1.5 33,1.5 L 23,1.5 Q 12,12 1.5,23 Z';
  return (
    <svg width={size} height={size} viewBox="-50 -50 100 100" className={className} fill="currentColor" aria-hidden>
      <path d={path} transform="rotate(0)" />
      <path d={path} transform="rotate(90)" />
      <path d={path} transform="rotate(180)" />
      <path d={path} transform="rotate(270)" />
    </svg>
  );
};

/* --- Project-relevant SVG diagrams (DataTrust OS, not generic AI) --- */

const DiagramIngest: React.FC<{ label: string }> = ({ label }) => (
  <figure className="dt-lp__diagram" aria-label={label}>
    <svg viewBox="0 0 360 88" className="dt-lp__diagram-svg" role="img">
      <rect className="dg-node" x="8" y="22" width="88" height="44" rx="8" />
      <text x="52" y="48" textAnchor="middle" className="dg-label">Landing</text>
      <path className="dg-flow" d="M104 44 H148" markerEnd="url(#dg-arrow)" />
      <rect className="dg-node dg-node--warn" x="152" y="22" width="72" height="44" rx="8" />
      <text x="188" y="42" textAnchor="middle" className="dg-label">HITL</text>
      <text x="188" y="56" textAnchor="middle" className="dg-sub">gate</text>
      <path className="dg-flow" d="M232 44 H276" markerEnd="url(#dg-arrow)" />
      <rect className="dg-node dg-node--ok" x="280" y="22" width="72" height="44" rx="8" />
      <text x="316" y="48" textAnchor="middle" className="dg-label">WH</text>
      <defs>
        <marker id="dg-arrow" markerWidth="6" markerHeight="6" refX="5" refY="3" orient="auto">
          <path d="M0 0 L6 3 L0 6 Z" fill="currentColor" opacity="0.55" />
        </marker>
      </defs>
    </svg>
    <figcaption>{label}</figcaption>
  </figure>
);

const DiagramHitl: React.FC<{ label: string }> = ({ label }) => (
  <figure className="dt-lp__diagram" aria-label={label}>
    <svg viewBox="0 0 360 88" className="dt-lp__diagram-svg" role="img">
      <rect className="dg-node" x="12" y="18" width="100" height="52" rx="8" />
      <text x="62" y="40" textAnchor="middle" className="dg-label">Preview</text>
      <text x="62" y="56" textAnchor="middle" className="dg-sub">sandbox</text>
      <text x="180" y="48" textAnchor="middle" className="dg-neq">≠</text>
      <rect className="dg-node dg-node--warn" x="248" y="18" width="100" height="52" rx="8" />
      <text x="298" y="40" textAnchor="middle" className="dg-label">Execute</text>
      <text x="298" y="56" textAnchor="middle" className="dg-sub">warehouse</text>
    </svg>
    <figcaption>{label}</figcaption>
  </figure>
);

const DiagramAcl: React.FC<{ label: string }> = ({ label }) => (
  <figure className="dt-lp__diagram" aria-label={label}>
    <svg viewBox="0 0 360 88" className="dt-lp__diagram-svg" role="img">
      <rect className="dg-node dg-node--ok" x="20" y="14" width="120" height="60" rx="8" />
      <text x="80" y="38" textAnchor="middle" className="dg-label">Steward A</text>
      <text x="80" y="54" textAnchor="middle" className="dg-sub">dataset_a ✓</text>
      <text x="180" y="48" textAnchor="middle" className="dg-neq">≠</text>
      <rect className="dg-node" x="220" y="14" width="120" height="60" rx="8" />
      <text x="280" y="38" textAnchor="middle" className="dg-label">Steward B</text>
      <text x="280" y="54" textAnchor="middle" className="dg-sub">dataset_b ✓</text>
      <line className="dg-block" x1="140" y1="70" x2="220" y2="70" />
      <text x="180" y="82" textAnchor="middle" className="dg-sub">ACL block cross-read</text>
    </svg>
    <figcaption>{label}</figcaption>
  </figure>
);

const DiagramLlmChip: React.FC<{ label: string }> = ({ label }) => (
  <figure className="dt-lp__diagram dt-lp__diagram--chips" aria-label={label}>
    <div className="dt-lp__llm-row">
      <span className="dt-lp__llm-chip dt-lp__llm-chip--on">LLM ON</span>
      <span className="dt-lp__llm-chip dt-lp__llm-chip--off">LLM OFF</span>
      <span className="dt-lp__llm-chip dt-lp__llm-chip--hitl">HITL still works</span>
    </div>
    <figcaption>{label}</figcaption>
  </figure>
);

const DiagramDayCount: React.FC<{ label: string }> = ({ label }) => (
  <figure className="dt-lp__diagram" aria-label={label}>
    <svg viewBox="0 0 360 88" className="dt-lp__diagram-svg" role="img">
      {[0, 1, 2, 3, 4, 5, 6].map((i) => {
        const h = 18 + ((i * 11) % 37);
        const active = i === 4;
        return (
          <g key={i}>
            <rect
              className={active ? 'dg-bar dg-bar--active' : 'dg-bar'}
              x={28 + i * 46}
              y={72 - h}
              width="28"
              height={h}
              rx="4"
            />
            <text x={42 + i * 46} y="84" textAnchor="middle" className="dg-sub">
              D{i + 9}
            </text>
          </g>
        );
      })}
      <text x="212" y="28" textAnchor="middle" className="dg-label dg-count">
        COUNT 30 528
      </text>
    </svg>
    <figcaption>{label}</figcaption>
  </figure>
);

function useMotionAllowed(): boolean {
  const [ok, setOk] = useState(true);
  useEffect(() => {
    const q = window.matchMedia('(prefers-reduced-motion: reduce)');
    const sync = () => setOk(!q.matches);
    sync();
    q.addEventListener('change', sync);
    return () => q.removeEventListener('change', sync);
  }, []);
  return ok;
}

function useStaticHeroPreferred(): boolean {
  const [staticHero, setStaticHero] = useState(true);
  useEffect(() => {
    const motionQ = window.matchMedia('(prefers-reduced-motion: reduce)');
    const coarseQ = window.matchMedia('(pointer: coarse)');
    const sync = () => setStaticHero(motionQ.matches || coarseQ.matches);
    sync();
    motionQ.addEventListener('change', sync);
    coarseQ.addEventListener('change', sync);
    return () => {
      motionQ.removeEventListener('change', sync);
      coarseQ.removeEventListener('change', sync);
    };
  }, []);
  return staticHero;
}

export const LandingPage: React.FC = () => {
  const navigate = useNavigate();
  const { isAuthenticated, setAuthModalOpen } = useAuthStore();
  const [lang, setLang] = useState<Lang>(() => ((i18n.language || 'vi').startsWith('vi') ? 'vi' : 'en'));
  const t = COPY[lang];
  const motionOk = useMotionAllowed();
  const staticHero = useStaticHeroPreferred();
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const pendingSeek = useRef<number | null>(null);
  const [videoReady, setVideoReady] = useState(false);
  const [heavyReady, setHeavyReady] = useState(false);

  const rootRef = useRef<HTMLDivElement | null>(null);
  const heroRef = useRef<HTMLElement | null>(null);
  const ptrTarget = useRef({ x: 0, y: 0 });
  const ptrCurrent = useRef({ x: 0, y: 0 });
  const scrollProgress = useRef(0);
  const heroOnScreen = useRef(true);
  const rafPtr = useRef(0);
  const rafScroll = useRef(0);

  useEffect(() => {
    const onLang = (lng: string) => setLang(lng.startsWith('vi') ? 'vi' : 'en');
    i18n.on('languageChanged', onLang);
    return () => {
      i18n.off('languageChanged', onLang);
    };
  }, []);

  useEffect(() => {
    if (!isAuthenticated) return;
    navigate('/dashboard/ingestion', { replace: true });
  }, [isAuthenticated, navigate]);

  /* Defer heavy motif layers until after first paint / LCP poster */
  useEffect(() => {
    if (!motionOk) return;
    let cancelled = false;
    const arm = () => {
      if (!cancelled) setHeavyReady(true);
    };
    const w = window as Window & {
      requestIdleCallback?: (cb: () => void, opts?: { timeout: number }) => number;
      cancelIdleCallback?: (id: number) => void;
    };
    let idleId: number | null = null;
    let timeoutId: number | null = null;
    if (w.requestIdleCallback) {
      idleId = w.requestIdleCallback(arm, { timeout: 1200 });
    } else {
      timeoutId = window.setTimeout(arm, 400);
    }
    return () => {
      cancelled = true;
      if (idleId != null && w.cancelIdleCallback) w.cancelIdleCallback(idleId);
      if (timeoutId != null) window.clearTimeout(timeoutId);
    };
  }, [motionOk]);

  /* IO reveals */
  useEffect(() => {
    const root = rootRef.current;
    if (!root) return;
    const nodes = Array.from(root.querySelectorAll<HTMLElement>('.dt-lp__reveal'));
    if (!nodes.length) return;

    if (!motionOk) {
      nodes.forEach((el) => el.classList.add('in-view'));
      return;
    }

    if (typeof IntersectionObserver === 'undefined') {
      nodes.forEach((el) => el.classList.add('in-view'));
      return;
    }

    const io = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (!entry.isIntersecting) continue;
          entry.target.classList.add('in-view');
          io.unobserve(entry.target);
        }
      },
      { root: null, rootMargin: '0px 0px -8% 0px', threshold: 0.12 },
    );
    nodes.forEach((el) => io.observe(el));
    return () => io.disconnect();
  }, [lang, motionOk]);

  /* Pause pointer when hero off-screen */
  useEffect(() => {
    const hero = heroRef.current;
    if (!hero || !motionOk) return;
    const io = new IntersectionObserver(
      ([e]) => {
        heroOnScreen.current = e.isIntersecting;
        if (!e.isIntersecting) {
          ptrTarget.current = { x: 0, y: 0 };
        }
      },
      { threshold: 0.05 },
    );
    io.observe(hero);
    return () => io.disconnect();
  }, [motionOk]);

  /* Pointer parallax rAF loop — bold layered follow */
  useEffect(() => {
    if (!motionOk) return;
    const root = rootRef.current;
    if (!root) return;

    const tick = () => {
      const cur = ptrCurrent.current;
      const tgt = ptrTarget.current;
      cur.x += (tgt.x - cur.x) * 0.12;
      cur.y += (tgt.y - cur.y) * 0.12;

      const x = cur.x;
      const y = cur.y;
      const s = scrollProgress.current;

      root.style.setProperty('--ptr-x', x.toFixed(4));
      root.style.setProperty('--ptr-y', y.toFixed(4));
      root.style.setProperty(
        '--ptr-far',
        `translate3d(${(x * PTR.far.t).toFixed(2)}px, ${(y * PTR.far.t * 0.7).toFixed(2)}px, 0) rotateX(${(-y * PTR.far.r).toFixed(2)}deg) rotateY(${(x * PTR.far.r).toFixed(2)}deg)`,
      );
      root.style.setProperty(
        '--ptr-mid',
        `translate3d(${(x * PTR.mid.t).toFixed(2)}px, ${(y * PTR.mid.t * 0.65).toFixed(2)}px, 0) rotateX(${(-y * PTR.mid.r).toFixed(2)}deg) rotateY(${(x * PTR.mid.r).toFixed(2)}deg)`,
      );
      root.style.setProperty(
        '--ptr-near',
        `translate3d(${(x * PTR.near.t).toFixed(2)}px, ${(y * PTR.near.t * 0.6).toFixed(2)}px, 0) rotateX(${(-y * PTR.near.r).toFixed(2)}deg) rotateY(${(x * PTR.near.r).toFixed(2)}deg)`,
      );
      root.style.setProperty(
        '--ptr-copy',
        `translate3d(${(x * PTR.copy.t).toFixed(2)}px, ${(y * PTR.copy.t * 0.5).toFixed(2)}px, 0) rotateX(${(-y * PTR.copy.r).toFixed(2)}deg) rotateY(${(x * PTR.copy.r).toFixed(2)}deg)`,
      );
      /* Scroll-linked hero depth (scale + Y) — scrub feel without video seek thrash */
      const depthScale = 1.02 + s * 0.1;
      const depthY = s * -48;
      root.style.setProperty('--scroll-depth', `translate3d(0, ${depthY.toFixed(1)}px, 0) scale(${depthScale.toFixed(4)})`);
      root.style.setProperty('--scroll-p', s.toFixed(4));

      rafPtr.current = requestAnimationFrame(tick);
    };
    rafPtr.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(rafPtr.current);
  }, [motionOk]);

  /* Scroll progress + section parallax (rAF throttled) */
  useEffect(() => {
    if (!motionOk) return;
    const root = rootRef.current;
    if (!root) return;
    let pending = false;

    const apply = () => {
      pending = false;
      const doc = document.documentElement;
      const max = Math.max(1, doc.scrollHeight - window.innerHeight);
      const p = Math.min(1, Math.max(0, window.scrollY / max));
      scrollProgress.current = p;
      root.style.setProperty('--scroll-p', p.toFixed(4));

      root.querySelectorAll<HTMLElement>('.dt-lp__parallax').forEach((el) => {
        const rect = el.getBoundingClientRect();
        const vh = window.innerHeight;
        const mid = rect.top + rect.height * 0.5;
        const norm = (mid - vh * 0.5) / vh; // -1..1-ish
        const speed = Number(el.dataset.speed || 24);
        const ty = Math.max(-56, Math.min(56, -norm * speed));
        const op = Math.max(0.55, Math.min(1, 1 - Math.abs(norm) * 0.25));
        el.style.transform = `translate3d(0, ${ty.toFixed(1)}px, 0)`;
        el.style.opacity = op.toFixed(3);
      });
    };

    const onScroll = () => {
      if (pending) return;
      pending = true;
      rafScroll.current = requestAnimationFrame(apply);
    };

    window.addEventListener('scroll', onScroll, { passive: true });
    apply();
    return () => {
      window.removeEventListener('scroll', onScroll);
      cancelAnimationFrame(rafScroll.current);
    };
  }, [motionOk, lang]);

  const onHeroPointer = (e: React.PointerEvent<HTMLElement>) => {
    if (!motionOk || !heroOnScreen.current) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const nx = ((e.clientX - rect.left) / rect.width) * 2 - 1;
    const ny = ((e.clientY - rect.top) / rect.height) * 2 - 1;
    ptrTarget.current = {
      x: Math.max(-1, Math.min(1, nx)),
      y: Math.max(-1, Math.min(1, ny)),
    };
  };

  const onHeroLeave = () => {
    ptrTarget.current = { x: 0, y: 0 };
  };

  const scrollTo = (id: string) => document.getElementById(id)?.scrollIntoView({ behavior: 'smooth' });

  const toggleLang = () => {
    const next: Lang = lang === 'vi' ? 'en' : 'vi';
    void changeLanguage(next);
    setLang(next);
  };

  const openLogin = () => {
    if (isAuthenticated) {
      navigate('/dashboard/ingestion');
      return;
    }
    setAuthModalOpen(true);
  };

  const ensureVideo = useCallback(() => {
    if (staticHero || videoReady || !motionOk) return;
    const video = videoRef.current;
    if (!video) return;
    if (!video.querySelector('source')) {
      const webm = document.createElement('source');
      webm.src = HERO_WEBM;
      webm.type = 'video/webm';
      const mp4 = document.createElement('source');
      mp4.src = HERO_MP4;
      mp4.type = 'video/mp4';
      video.appendChild(webm);
      video.appendChild(mp4);
      video.load();
    }
    setVideoReady(true);
  }, [staticHero, videoReady, motionOk]);

  const onHeroMove = (e: React.MouseEvent<HTMLElement>) => {
    if (staticHero || !motionOk) return;
    ensureVideo();
    const video = videoRef.current;
    if (!video || !video.duration || Number.isNaN(video.duration)) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const x = Math.min(1, Math.max(0, (e.clientX - rect.left) / rect.width));
    /* Mix pointer X with scroll progress for pronounced scrub */
    const mix = Math.min(1, Math.max(0, x * 0.75 + scrollProgress.current * 0.25));
    const target = mix * video.duration;
    if (video.seeking) {
      pendingSeek.current = target;
      return;
    }
    try {
      video.currentTime = target;
    } catch {
      /* ignore */
    }
  };

  const onSeeked = () => {
    if (pendingSeek.current !== null && videoRef.current) {
      const next = pendingSeek.current;
      pendingSeek.current = null;
      videoRef.current.currentTime = next;
    }
  };

  return (
    <div className={`dt-lp${motionOk ? ' dt-lp--motion' : ' dt-lp--reduced'}`} ref={rootRef}>
      <div className="dt-lp__progress" aria-hidden>
        <div className="dt-lp__progress-bar" />
      </div>

      <nav className="dt-lp__nav" aria-label="Primary">
        <button type="button" className="dt-lp__brand" onClick={() => scrollTo('section-hero')}>
          <DataTrustLogo size={18} />
          {t.brand}
        </button>
        <div className="dt-lp__nav-links">
          <button type="button" onClick={() => scrollTo('section-problem')}>{t.navProblem}</button>
          <button type="button" onClick={() => scrollTo('section-product')}>{t.navProduct}</button>
          <button type="button" onClick={() => scrollTo('section-hitl')}>{t.navHitl}</button>
          <button type="button" onClick={() => scrollTo('section-roles')}>{t.navRoles}</button>
          <button type="button" onClick={() => scrollTo('section-proof')}>{t.navProof}</button>
        </div>
        <div className="dt-lp__nav-actions">
          <button type="button" className="dt-lp__lang" onClick={toggleLang} aria-label="Language">
            {lang === 'vi' ? 'EN' : 'VI'}
          </button>
          <a className="dt-lp__btn dt-lp__btn--ghost" href={LIVE_T086} target="_blank" rel="noreferrer">
            {t.liveT086}
            <ArrowUpRight size={14} />
          </a>
          <button type="button" className="dt-lp__btn dt-lp__btn--primary" onClick={openLogin}>
            {isAuthenticated ? t.enter : t.login}
          </button>
        </div>
      </nav>

      <header
        id="section-hero"
        ref={heroRef}
        className="dt-lp__hero"
        onPointerEnter={ensureVideo}
        onPointerMove={onHeroPointer}
        onPointerLeave={onHeroLeave}
        onMouseMove={onHeroMove}
      >
        <div className={`dt-lp__hero-media${videoReady && !staticHero ? ' is-video-ready' : ''}`}>
          <div className="dt-lp__hero-layer dt-lp__hero-layer--far" aria-hidden>
            <img src={HERO_POSTER} alt="" width={1920} height={1080} decoding="async" fetchPriority="high" />
          </div>
          {!staticHero && (
            <div className="dt-lp__hero-layer dt-lp__hero-layer--mid" aria-hidden>
              <video ref={videoRef} muted playsInline preload="none" poster={HERO_POSTER} onSeeked={onSeeked} />
            </div>
          )}
          {heavyReady && motionOk && (
            <div className="dt-lp__hero-layer dt-lp__hero-layer--motif" aria-hidden>
              <img src={MOTIF_TELE} alt="" width={1280} height={720} loading="lazy" decoding="async" />
            </div>
          )}
        </div>
        <div className="dt-lp__hero-scrub dt-lp__hero-layer--near" />
        <div className="dt-lp__hero-copy">
          <p className="dt-lp__eyebrow">{t.eyebrow}</p>
          <h1 className="dt-lp__brand-hero">{t.brand}</h1>
          <p className="dt-lp__headline">{t.headline}</p>
          <p className="dt-lp__sub">
            {t.sub}
            <br />
            <em>{t.subEn}</em>
          </p>
          <div className="dt-lp__cta-row">
            <button type="button" className="dt-lp__btn dt-lp__btn--primary dt-lp__btn--lg" onClick={openLogin}>
              {isAuthenticated ? t.enter : t.login}
              <ArrowRight size={16} />
            </button>
            <a className="dt-lp__btn dt-lp__btn--ghost dt-lp__btn--lg" href={LIVE_T086} target="_blank" rel="noreferrer">
              {t.liveT086}
              <ArrowUpRight size={16} />
            </a>
          </div>
          <p className="dt-lp__cta-note">{t.stagingNote} · <a href={LIVE_D086}>{LIVE_D086.replace('https://', '')}</a></p>
        </div>
      </header>


      <section id="section-problem" className="dt-lp__section">
        <div className="dt-lp__inner dt-lp__reveal dt-lp__parallax" data-speed="36">
          <p className="dt-lp__kicker">{t.problemK}</p>
          <h2 className="dt-lp__h2">{t.problemH}</h2>
          <p className="dt-lp__lead">
            {t.problemL}
            <span className="en">{t.problemLEn}</span>
          </p>
          <div className="dt-lp__grid dt-lp__grid--3">
            {t.problems.map((p) => (
              <article key={p.t} className="dt-lp__tile">
                <h3>{p.t}</h3>
                <p>
                  {p.d}
                  <span className="en">{p.en}</span>
                </p>
              </article>
            ))}
          </div>
          <div className="dt-lp__diagram-row">
            <DiagramDayCount label={t.diagramCount} />
          </div>
        </div>
      </section>

      <section
        id="section-product"
        className="dt-lp__section dt-lp__section--motif"
        style={heavyReady ? { backgroundImage: `url(${MOTIF_VIN})` } : { backgroundImage: 'url(/landing/atmos.calm.webp)' }}
      >
        <div className="dt-lp__inner dt-lp__reveal dt-lp__parallax dt-lp__inner--glass" data-speed="32">
          <p className="dt-lp__kicker">{t.productK}</p>
          <h2 className="dt-lp__h2">{t.productH}</h2>
          <p className="dt-lp__lead">
            {t.productL}
            <span className="en">{t.productLEn}</span>
          </p>
          <DiagramIngest label={t.diagramIngest} />
          <div className="dt-lp__grid dt-lp__grid--3">
            {t.products.map((p) => (
              <article key={p.n} className="dt-lp__tile">
                <div className="dt-lp__num">{p.n}</div>
                <h3>{p.t}</h3>
                <p>
                  {p.d}
                  <span className="en">{p.en}</span>
                </p>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section id="section-hitl" className="dt-lp__section">
        <div className="dt-lp__inner dt-lp__reveal dt-lp__parallax" data-speed="34">
          <p className="dt-lp__kicker">{t.hitlK}</p>
          <h2 className="dt-lp__h2">{t.hitlH}</h2>
          <p className="dt-lp__lead">
            {t.hitlL}
            <span className="en">{t.hitlLEn}</span>
          </p>
          <DiagramHitl label={t.diagramHitl} />
          <div className="dt-lp__flow">
            {t.hitlSteps.map((s, i) => (
              <div key={s.t} className="dt-lp__flow-step">
                <div className="dt-lp__num">{String(i + 1).padStart(2, '0')}</div>
                <strong>{s.t}</strong>
                <p style={{ margin: 0, color: 'var(--lp-muted)', fontSize: '0.9rem' }}>{s.d}</p>
              </div>
            ))}
          </div>
          <DiagramLlmChip label={t.diagramLlm} />
        </div>
      </section>

      <section id="section-roles" className="dt-lp__section">
        <div className="dt-lp__inner dt-lp__reveal dt-lp__parallax" data-speed="28">
          <p className="dt-lp__kicker">{t.rolesK}</p>
          <h2 className="dt-lp__h2">{t.rolesH}</h2>
          <p className="dt-lp__lead">
            {t.rolesL}
            <span className="en">{t.rolesLEn}</span>
          </p>
          <DiagramAcl label={t.diagramAcl} />
          <div className="dt-lp__grid dt-lp__grid--4">
            {t.roles.map((r) => (
              <article key={r.t} className="dt-lp__tile">
                <h3>{r.t}</h3>
                <p>
                  {r.d}
                  <span className="en">{r.en}</span>
                </p>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section id="section-proof" className="dt-lp__section">
        <div className="dt-lp__inner dt-lp__reveal dt-lp__parallax" data-speed="24">
          <p className="dt-lp__kicker">{t.proofK}</p>
          <h2 className="dt-lp__h2">{t.proofH}</h2>
          <p className="dt-lp__lead">
            {t.proofL}
            <span className="en">{t.proofLEn}</span>
          </p>
          <div className="dt-lp__shots">
            {t.shots.map((s) => (
              <figure key={s.src} className="dt-lp__shot">
                <img src={s.src} alt={s.cap} loading="lazy" width={720} height={180} />
                <figcaption>{s.cap}</figcaption>
              </figure>
            ))}
          </div>
        </div>
      </section>

      <section id="section-tech" className="dt-lp__section">
        <div className="dt-lp__inner dt-lp__reveal">
          <p className="dt-lp__kicker">{t.techK}</p>
          <h2 className="dt-lp__h2">{t.techH}</h2>
          <div className="dt-lp__stack">
            {t.techChips.map((c) => (
              <span key={c} className="dt-lp__chip">{c}</span>
            ))}
          </div>
        </div>
      </section>

      <section className="dt-lp__footer-cta">
        <h2>{t.footH}</h2>
        <p>{t.footL}</p>
        <div className="dt-lp__cta-row" style={{ justifyContent: 'center' }}>
          <button type="button" className="dt-lp__btn dt-lp__btn--primary dt-lp__btn--lg" onClick={openLogin}>
            {isAuthenticated ? t.enter : t.login}
            <ArrowRight size={16} />
          </button>
          <a className="dt-lp__btn dt-lp__btn--ghost dt-lp__btn--lg" href={LIVE_T086} target="_blank" rel="noreferrer">
            {t.liveT086}
            <ArrowUpRight size={16} />
          </a>
        </div>
      </section>

      <footer className="dt-lp__legal">
        <span>{t.footNote}</span>
        <span>
          <a href={LIVE_D086}>d086</a> · <a href={LIVE_T086}>t086</a>
        </span>
      </footer>

      <AuthModal />
    </div>
  );
};

export default LandingPage;
