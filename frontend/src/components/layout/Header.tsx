import { useState, useEffect, useRef, useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate, useLocation } from 'react-router-dom';
import {
  Atom, Search, Moon, Sun, ChevronDown,
  IdCard, LogOut, X, Database,
  AlertTriangle, GitBranch, ShieldCheck,
  History, Camera, LayoutDashboard, MessageSquare, ArrowRight,
  RotateCcw, Globe, Sparkles, Shield, Zap, Menu,
} from 'lucide-react';
import { useTheme } from '../../contexts/ThemeContext';
import { searchApi, SearchHit, systemApi, getGlobalUseLlm, setGlobalUseLlm } from '../../services/api';

import { DOMAIN_LIST } from '../../stores/pipelineStore';
import { useAuthStore } from '../../stores/authStore';
import { useChatStore } from '../../stores/chatStore';
import { usePipelineStore } from '../../stores/pipelineStore';
import { useWorkspaceStore, wipeStewardBrowserKeys } from '../../stores/workspaceStore';
import { AuthModal } from '../auth/AuthModal';
import { changeLanguage } from '../../i18n';

interface StaticSearchResult {
  id: string;
  title: { en: string; vi: string };
  category: 'dataset' | 'operation' | 'action';
  description: { en: string; vi: string };
  path: string;
  icon: typeof Database;
}

const STATIC_OPERATIONS: StaticSearchResult[] = [
  { id: 'op-dashboard', title: { en: 'Executive Homepage', vi: 'Trang Chủ Điều Hành' }, category: 'operation', description: { en: 'Real-time KPI metrics, anomaly trends, and HITL governance', vi: 'Chỉ số KPI thời gian thực, xu hướng bất thường và quản trị HITL' }, path: '/dashboard', icon: LayoutDashboard },
  { id: 'op-new-chat', title: { en: 'New Agent Session', vi: 'Phiên Trò Chuyện Agent Mới' }, category: 'action', description: { en: 'Start AI Steward interactive analysis session', vi: 'Bắt đầu phiên phân tích tương tác với AI Steward' }, path: '/workspace', icon: MessageSquare },
  { id: 'op-alerts', title: { en: 'Alert Dashboard', vi: 'Bảng Cảnh Báo Điều Hành' }, category: 'operation', description: { en: 'Real-time threshold alerts and multi-layer triage', vi: 'Cảnh báo ngưỡng thời gian thực và phân loại đa tầng' }, path: '/operations/alerts', icon: AlertTriangle },
  { id: 'op-traces', title: { en: 'Agent Traces', vi: 'Dấu Vết Thực Thi Agent' }, category: 'operation', description: { en: 'ReAct agent execution trajectories and tool logs', vi: 'Quỹ đạo thực thi agent ReAct và nhật ký công cụ' }, path: '/operations/traces', icon: GitBranch },
  { id: 'op-governance', title: { en: 'Governance & Rules', vi: 'Quản Trị & Bộ Luật' }, category: 'operation', description: { en: 'Data quality rule policies and audit controls', vi: 'Chính sách luật chất lượng dữ liệu và kiểm toán' }, path: '/operations/governance', icon: ShieldCheck },
  { id: 'op-executions', title: { en: 'Execution History', vi: 'Lịch Sử Thực Thi' }, category: 'operation', description: { en: 'Quarantine and clean split transformation executions', vi: 'Lịch sử phân tách tập sạch và vùng cách ly' }, path: '/operations/executions', icon: History },
  { id: 'op-snapshots', title: { en: 'Data Snapshots', vi: 'Ảnh Chụp Dữ Liệu' }, category: 'operation', description: { en: 'Cryptographic schema state and row count manifests', vi: 'Trạng thái schema mã hóa và bản kê số hàng' }, path: '/operations/snapshots', icon: Camera },
];

export function Header({ navOpen = false, onToggleNav }: { navOpen?: boolean; onToggleNav?: () => void } = {}) {
  const [userDropdownOpen, setUserDropdownOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchOpen, setSearchOpen] = useState(false);
  const [backendHits, setBackendHits] = useState<SearchHit[]>([]);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [isSearching, setIsSearching] = useState(false);
  const [resetLoading, setResetLoading] = useState(false);
  const [resetSuccess, setResetSuccess] = useState(false);
  const [resetConfirmOpen, setResetConfirmOpen] = useState(false);

  const { user, isAuthenticated, isAdmin, setAuthModalOpen, logout, login } = useAuthStore();
  const { t, i18n } = useTranslation('pipeline');
  const isVi = i18n.language === 'vi';
  const { theme, toggleTheme } = useTheme();

  const modalInputRef = useRef<HTMLInputElement>(null);
  const modalBoxRef = useRef<HTMLDivElement>(null);
  const navigate = useNavigate();
  const location = useLocation();

  // Confirm Reset toast must survive navigate('/workspace?new=1') Header remount.
  useEffect(() => {
    try {
      if (sessionStorage.getItem('dt-reset-toast')) {
        setResetSuccess(true);
        const timer = setTimeout(() => {
          setResetSuccess(false);
          try { sessionStorage.removeItem('dt-reset-toast'); } catch { /* ignore */ }
        }, 3500);
        return () => clearTimeout(timer);
      }
    } catch {
      /* ignore */
    }
    return undefined;
  }, [location.pathname, location.search]);

  const handleResetAll = async () => {
    // In-app modal already accepted. Do not re-login as steward after wipe.
    setResetLoading(true);
    const auth = useAuthStore.getState();
    const wasAdmin = auth.isAdmin();
    const keepToken = auth.token;
    const keepUser = auth.user;
    try {
      try {
        await systemApi.resetAll();
      } catch (first: any) {
        const msg = String(first?.message || '');
        if (msg.includes('401') || msg.includes('403') || msg.toLowerCase().includes('unauthorized') || msg.toLowerCase().includes('forbidden')) {
          await login('admin@datatrust.os', undefined, 'Admin');
          await systemApi.resetAll();
        } else {
          throw first;
        }
      }
      try {
        useChatStore.getState().clearMessages();
        useChatStore.getState().setSessionId('default');
        useWorkspaceStore.getState().resetStewardState();
        usePipelineStore.getState().resetPipeline();
        wipeStewardBrowserKeys();
        Object.keys(sessionStorage)
          .filter((k) => k.startsWith('dt-hitl') || k.startsWith('dt-warehouse') || k.startsWith('dt-split') || k.startsWith('dt-snap'))
          .forEach((k) => sessionStorage.removeItem(k));
      } catch {
        /* ignore */
      }
      if (wasAdmin && keepToken && keepUser) {
        useAuthStore.getState().restoreSession(keepToken, keepUser);
      }
      try {
        sessionStorage.setItem('dt-reset-toast', '1');
      } catch {
        /* ignore */
      }
      setResetSuccess(true);
      setTimeout(() => setResetSuccess(false), 3500);
      window.dispatchEvent(new CustomEvent('datatrust:db-reset'));
      navigate('/workspace?new=1');
    } catch (err: any) {
      alert(isVi ? `Đặt lại thất bại: ${err.message}` : `Reset failed: ${err.message}`);
    } finally {
      setResetLoading(false);
    }
  };

  const handleToggleLang = () => {
    const next = i18n.language === 'vi' ? 'en' : 'vi';
    changeLanguage(next);
  };

  const [useLlmMode, setUseLlmMode] = useState<boolean>(getGlobalUseLlm);

  const handleToggleLlmMode = () => {
    const next = !useLlmMode;
    setUseLlmMode(next);
    setGlobalUseLlm(next);
  };



  // ⌘K / Ctrl-K opens the centered search modal
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        setSearchOpen((prev) => {
          if (!prev) {
            setSearchQuery('');
            setSelectedIndex(0);
          }
          return !prev;
        });
      }
    };
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, []);

  // Auto-focus the centered input when modal opens
  useEffect(() => {
    if (searchOpen) {
      setTimeout(() => {
        modalInputRef.current?.focus();
      }, 50);
    }
  }, [searchOpen]);

  // Debounced backend search
  useEffect(() => {
    const trimmed = searchQuery.trim();
    if (!trimmed) {
      setBackendHits([]);
      setIsSearching(false);
      return;
    }

    setIsSearching(true);
    const timer = setTimeout(async () => {
      try {
        const resp = await searchApi.search(trimmed, undefined, 8);
        if (resp && Array.isArray(resp.results)) {
          setBackendHits(resp.results);
        } else {
          setBackendHits([]);
        }
      } catch {
        setBackendHits([]);
      } finally {
        setIsSearching(false);
      }
    }, 180);

    return () => clearTimeout(timer);
  }, [searchQuery]);

  // Filter local operations & sample datasets
  const localResults = useMemo(() => {
    const q = searchQuery.toLowerCase().trim();
    const curLang = isVi ? 'vi' : 'en';
    if (!q) {
      return STATIC_OPERATIONS.slice(0, 6).map((op) => ({
        id: op.id,
        title: op.title[curLang],
        category: op.category,
        description: op.description[curLang],
        path: op.path,
        icon: op.icon,
      }));
    }

    const matchedOps = STATIC_OPERATIONS.filter(
      (op) =>
        op.title.en.toLowerCase().includes(q) ||
        op.title.vi.toLowerCase().includes(q) ||
        op.description.en.toLowerCase().includes(q) ||
        op.description.vi.toLowerCase().includes(q)
    ).map((op) => ({
      id: op.id,
      title: op.title[curLang],
      category: op.category,
      description: op.description[curLang],
      path: op.path,
      icon: op.icon,
    }));

    const matchedDatasets = DOMAIN_LIST.filter(
      (d) => d.name.toLowerCase().includes(q) || d.id.toLowerCase().includes(q) || d.shortcut.toLowerCase().includes(q)
    ).map((d) => ({
      id: `dataset-${d.id}`,
      title: d.name,
      category: 'dataset' as const,
      description: isVi ? `Bộ dữ liệu thử nghiệm · ${d.shortcut}` : `Pilot dataset · ${d.shortcut}`,
      path: `/workspace?dataset_key=${encodeURIComponent(d.id)}`,
      icon: Database,
    }));

    return [...matchedDatasets, ...matchedOps];
  }, [searchQuery, isVi]);



  // Combined flattened items for keyboard navigation
  const allNavigableItems = useMemo(() => {
    const items: Array<{ id: string; title: string; subtitle?: string; path: string; category: string }> = [];
    const seenPaths = new Set<string>();
    const seenTitles = new Set<string>();

    localResults.forEach((item) => {
      const tLower = item.title.toLowerCase().trim();
      if (!seenPaths.has(item.path) && !seenTitles.has(tLower)) {
        seenPaths.add(item.path);
        seenTitles.add(tLower);
        items.push({
          id: item.id,
          title: item.title,
          subtitle: item.description,
          path: item.path,
          category: item.category,
        });
      }
    });

    backendHits.forEach((hit, idx) => {
      const path = hit.entity_type === 'dataset' && hit.key
        ? `/workspace?dataset_key=${encodeURIComponent(hit.key)}`
        : hit.entity_type === 'alert'
          ? '/operations/alerts'
          : hit.entity_type === 'rule'
            ? '/operations/governance'
            : '/dashboard';

      const title = hit.name || hit.title || hit.key || 'Entity';
      const tLower = title.toLowerCase().trim();
      if (!seenPaths.has(path) && !seenTitles.has(tLower)) {
        seenPaths.add(path);
        seenTitles.add(tLower);
        items.push({
          id: hit.objectID || `backend-${idx}`,
          title,
          subtitle: hit.description || hit.rule_expression || hit.path || hit.entity_type,
          path,
          category: hit.entity_type || 'result',
        });
      }
    });

    return items;
  }, [localResults, backendHits]);

  const handleSelectItem = (path: string) => {
    setSearchOpen(false);
    setSearchQuery('');
    navigate(path);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setSelectedIndex((prev) => (prev + 1) % Math.max(1, allNavigableItems.length));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setSelectedIndex((prev) => (prev - 1 + allNavigableItems.length) % Math.max(1, allNavigableItems.length));
    } else if (e.key === 'Enter') {
      e.preventDefault();
      if (allNavigableItems[selectedIndex]) {
        handleSelectItem(allNavigableItems[selectedIndex].path);
      }
    } else if (e.key === 'Escape') {
      setSearchOpen(false);
    }
  };

  return (
    <>
      <header className="top-hud">
        <button
          type="button"
          className="nav-hamburger"
          aria-label={navOpen ? 'Close navigation' : 'Open navigation'}
          aria-expanded={navOpen}
          onClick={() => onToggleNav?.()}
        >
          {navOpen ? <X size={18} /> : <Menu size={18} />}
        </button>
        <div className="brand-section">
          <div className="logo-badge" onClick={() => navigate('/dashboard')} style={{ cursor: 'pointer' }}>
            <div className="logo-icon-box"><Atom size={18} /></div>
            <span><span style={{ color: 'var(--text-main)' }}>DATATRUST OS AGENT</span></span>
          </div>
        </div>

        {/* Topbar Search Trigger */}
        <div
          className="nav-search-bar"
          onClick={() => {
            setSearchOpen(true);
          }}
          style={{ cursor: 'pointer' }}
          role="button"
          tabIndex={0}
          onKeyDown={(e) => {
            if (e.key === 'Enter' || e.key === ' ') {
              e.preventDefault();
              setSearchOpen(true);
            }
          }}
        >
          <Search className="search-icon" size={16} />
          <input
            type="text"
            id="globalSearchInput"
            readOnly
            placeholder={t('searchPlaceholder') || 'Search datasets, rules, pipelines... (⌘K)'}
            style={{ cursor: 'pointer', pointerEvents: 'none' }}
          />
          <span className="search-shortcut">⌘K</span>
        </div>

        <div className="hud-actions">
          {/* Landing Page Link (Only shown when logged out) */}
          {!isAuthenticated && (
            <button
              type="button"
              className="hud-action-pill"
              onClick={() => navigate('/landing')}
              title={isVi ? 'Xem Trang Giới Thiệu DataTrustOS' : 'View DataTrustOS Futuristic Landing Page'}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '6px',
                padding: '0 12px',
                height: '32px',
                borderRadius: '9999px',
                backgroundColor: 'rgba(255, 255, 255, 0.05)',
                border: '1px solid var(--glass-border)',
                color: 'var(--text-main)',
                fontSize: '12px',
                fontWeight: 500,
                cursor: 'pointer',
              }}
            >
              <Globe size={13} style={{ color: 'var(--warning-amber)' }} />
              <span>{isVi ? 'Trang Giới Thiệu' : 'Landing Page'}</span>
            </button>
          )}

          {/* Language Switcher Button */}
          <button
            type="button"
            className="hud-action-pill"
            onClick={handleToggleLang}
            title={isVi ? 'Chuyển đổi Tiếng Việt / Tiếng Anh' : 'Toggle Vietnamese / English Language'}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '6px',
              padding: '0 12px',
              height: '32px',
              borderRadius: '9999px',
              backgroundColor: 'rgba(255, 255, 255, 0.05)',
              border: '1px solid var(--glass-border)',
              color: 'var(--text-main)',
              fontSize: '12px',
              fontWeight: 600,
              cursor: 'pointer',
            }}
          >
            <Globe size={13} style={{ color: 'var(--neon-cyan)' }} />
            <span>{isVi ? 'VI' : 'EN'}</span>
          </button>

          {/* Global System-Wide LLM Toggle Button */}
          <button
            type="button"
            className="hud-action-pill"
            onClick={handleToggleLlmMode}
            title={
              useLlmMode
                ? (isVi ? 'Đang BẬT LLM toàn hệ thống (Test độ chính xác bằng Gemini ReAct). Click để TẮT.' : 'System-wide LLM ON (Live Gemini ReAct accuracy test). Click to turn OFF.')
                : (isVi ? 'Đang TẮT LLM toàn hệ thống (Test logic 0 token bằng Rule Engine). Click để BẬT.' : 'System-wide LLM OFF (Fast 0-token logic test via Rule Engine). Click to turn ON.')
            }
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '6px',
              padding: '0 12px',
              height: '32px',
              borderRadius: '9999px',
              backgroundColor: useLlmMode ? 'rgba(168, 85, 247, 0.18)' : 'rgba(234, 179, 8, 0.18)',
              border: useLlmMode ? '1px solid rgba(168, 85, 247, 0.45)' : '1px solid rgba(234, 179, 8, 0.45)',
              color: useLlmMode ? '#c084fc' : '#eab308',
              fontSize: '12px',
              fontWeight: 700,
              cursor: 'pointer',
              transition: 'all 0.2s ease',
            }}
          >
            {useLlmMode ? (
              <>
                <Sparkles size={13} style={{ color: '#c084fc' }} />
                <span>LLM ON</span>
              </>
            ) : (
              <>
                <Zap size={13} style={{ color: '#eab308' }} />
                <span>LLM OFF</span>
              </>
            )}
          </button>


          {/* Admin-Only DB & Baseline Reset Button */}
          {isAuthenticated && isAdmin() && (
            <button
              type="button"
              className="hud-action-pill danger"
              onClick={(e) => {
                e.preventDefault();
                e.stopPropagation();
                setResetConfirmOpen(true);
              }}
              disabled={resetLoading}
              title={isVi ? 'Quản trị viên: Đặt lại trạng thái runtime & khôi phục dữ liệu gốc VinGroup' : 'Admin Quick Reset: Wipe runtime state & restore VinGroup baseline'}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '6px',
                padding: '0 12px',
                height: '32px',
                borderRadius: '9999px',
                backgroundColor: resetSuccess ? 'rgba(16, 185, 129, 0.15)' : 'rgba(239, 68, 68, 0.12)',
                border: `1px solid ${resetSuccess ? 'var(--electric-green)' : 'rgba(239, 68, 68, 0.35)'}`,
                color: resetSuccess ? 'var(--electric-green)' : '#f87171',
                fontSize: '12px',
                fontWeight: 600,
                cursor: 'pointer',
                transition: 'all 150ms ease',
              }}
            >
              <RotateCcw size={13} className={resetLoading ? 'spinning' : ''} />
              <span>{resetSuccess ? (isVi ? 'Đã Đặt Lại!' : 'Reset OK!') : (isVi ? 'Đặt Lại DB' : 'Reset DB')}</span>
            </button>
          )}

          {/* Theme Toggle */}
          <button className="theme-toggle-btn" title={isVi ? 'Chuyển Đổi Sáng/Tối' : 'Toggle Dark/White Mode'} onClick={toggleTheme}>
            {theme === 'tech-dark' ? <Sun size={18} /> : <Moon size={18} />}
          </button>

          {/* User Profile & Persona Switcher */}
          {!isAuthenticated ? (
            <button
              type="button"
              className="hud-action-pill"
              onClick={() => setAuthModalOpen(true)}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '6px',
                padding: '0 14px',
                height: '32px',
                borderRadius: '9999px',
                backgroundColor: 'var(--neon-cyan)',
                color: '#ffffff',
                border: 'none',
                fontSize: '12px',
                fontWeight: 600,
                cursor: 'pointer',
              }}
            >
              {isVi ? 'Đăng Nhập' : 'Sign In'}
            </button>
          ) : (
            <div className="user-profile-wrapper" onClick={() => setUserDropdownOpen(!userDropdownOpen)}>
              <div className="user-profile-btn">
                <div
                  className="user-avatar-box"
                  style={{
                    backgroundColor: isAdmin() ? 'rgba(244, 63, 94, 0.15)' : 'rgba(14, 165, 233, 0.15)',
                    color: isAdmin() ? 'var(--alert-magenta)' : 'var(--neon-cyan)',
                  }}
                >
                  <Shield size={16} />
                </div>
                <div className="user-info-text">
                  <span className="user-name-str">{user?.username?.split('@')[0] || 'steward'}</span>
                  <span
                    className="user-role-str"
                    style={{
                      color: isAdmin() ? 'var(--alert-magenta)' : 'var(--neon-cyan)',
                      fontWeight: 600,
                    }}
                  >
                    {user?.role || 'Steward'}
                  </span>
                </div>
                <ChevronDown className="dropdown-arrow" size={12} />
              </div>

              {userDropdownOpen && (
                <div className="user-dropdown-menu show" style={{ display: 'block' }}>
                  <div className="dropdown-user-header">
                    <div className="dropdown-user-name">{user?.username}</div>
                    <div className="dropdown-user-email">{isVi ? 'Vai trò' : 'Role'}: {user?.role}</div>
                  </div>
                  <div className="dropdown-divider"></div>
                  <div
                    className="dropdown-item"
                    style={{ cursor: 'pointer', color: 'var(--neon-cyan)', fontWeight: 600 }}
                    onClick={() => {
                      setUserDropdownOpen(false);
                      setAuthModalOpen(true);
                    }}
                  >
                    <Sparkles size={14} /> {isVi ? 'Chuyển Đổi Vai Trò' : 'Switch Persona / Role'}
                  </div>
                  <a href="#/operations/governance" className="dropdown-item" onClick={() => navigate('/operations/governance')}>
                    <IdCard size={14} /> {t('profileInfo')}
                  </a>
                  <div className="dropdown-divider"></div>
                  <a
                    href="#"
                    className="dropdown-item danger"
                    onClick={(e) => {
                      e.preventDefault();
                      setUserDropdownOpen(false);
                      logout();
                      navigate('/landing');
                    }}
                  >
                    <LogOut size={14} /> {t('signOut')}
                  </a>
                </div>
              )}
            </div>
          )}
        </div>
      </header>


      {resetSuccess && (
        <div
          role="status"
          className="reset-toast"
          style={{
            position: 'fixed',
            top: 72,
            right: 16,
            zIndex: 80,
            background: 'rgba(16, 185, 129, 0.15)',
            border: '1px solid var(--electric-green)',
            color: 'var(--electric-green)',
            padding: '10px 14px',
            borderRadius: 8,
            fontSize: 12,
            fontWeight: 700,
            boxShadow: '0 8px 24px rgba(0,0,0,0.25)',
          }}
        >
          {isVi ? 'Toast: Đã đặt lại DB · HITL 0/0 · Split 0' : 'Toast: Database reset · HITL 0/0 · Split 0'}
        </div>
      )}

      {resetConfirmOpen && (
        <div
          className="modal-overlay active"
          role="dialog"
          aria-modal="true"
          aria-labelledby="reset-confirm-title"
          onClick={() => { if (!resetLoading) setResetConfirmOpen(false); }}
        >
          <div className="modal-card" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <span className="modal-title" id="reset-confirm-title">
                <AlertTriangle size={15} style={{ marginRight: 6 }} />
                {isVi ? 'Xác nhận đặt lại DB' : 'Confirm Reset DB'}
              </span>
              <button
                type="button"
                className="modal-close"
                onClick={() => setResetConfirmOpen(false)}
                disabled={resetLoading}
              >
                ✕
              </button>
            </div>
            <div className="modal-body" style={{ fontSize: 13, color: 'var(--text-main)', lineHeight: 1.5 }}>
              {isVi
                ? 'Đặt lại toàn bộ bảng DB, luật, vùng cách ly và bộ nhớ phiên về trạng thái ban đầu của VinGroup?'
                : 'Reset all DB tables, rules, quarantine, and conversation memory back to clean VinGroup baseline?'}
            </div>
            <div className="modal-actions" style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 12 }}>
              <button
                type="button"
                className="btn-modal-cancel"
                onClick={() => setResetConfirmOpen(false)}
                disabled={resetLoading}
              >
                {isVi ? 'Hủy' : 'Cancel'}
              </button>
              <button
                type="button"
                className="btn-modal-save"
                onClick={() => {
                  setResetConfirmOpen(false);
                  void handleResetAll();
                }}
                disabled={resetLoading}
              >
                {isVi ? 'Xác nhận đặt lại' : 'Confirm Reset'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Auth & Persona Switcher Modal */}
      <AuthModal />


      {/* Centered Command Palette Modal */}
      {searchOpen && (
        <div
          className="command-palette-backdrop"
          onClick={() => setSearchOpen(false)}
        >
          <div
            className="command-palette-modal"
            ref={modalBoxRef}
            onClick={(e) => e.stopPropagation()}
          >
            {/* Centered Large Search Input Header */}
            <div className="palette-input-wrapper">
              <Search className="palette-search-icon" size={18} />
              <input
                ref={modalInputRef}
                type="text"
                id="centeredCommandPaletteInput"
                className="palette-input"
                placeholder={t('searchPlaceholder') || 'Search datasets, rules, pipelines, operations...'}
                value={searchQuery}
                onChange={(e) => {
                  setSearchQuery(e.target.value);
                  setSelectedIndex(0);
                }}
                onKeyDown={handleKeyDown}
                autoComplete="off"
                autoFocus
              />
              <div className="palette-input-actions">
                {searchQuery ? (
                  <button
                    type="button"
                    className="search-clear-btn"
                    style={{ position: 'static' }}
                    onClick={() => {
                      setSearchQuery('');
                      setBackendHits([]);
                      modalInputRef.current?.focus();
                    }}
                    aria-label="Clear search"
                  >
                    <X size={15} />
                  </button>
                ) : null}
                <span className="palette-esc-badge">ESC</span>
              </div>
            </div>

            <div className="palette-header">
              <span>{searchQuery ? `Results for "${searchQuery}"` : 'Quick Navigation & Enterprise Datasets'}</span>
              {isSearching && <span className="palette-searching">Searching...</span>}
            </div>

            <div className="palette-list">
              {allNavigableItems.length === 0 && !isSearching && (
                <div className="palette-empty">
                  No matching datasets, operations, or rules found for "{searchQuery}".
                </div>
              )}

              {localResults.length > 0 && (
                <div className="palette-group">
                  <div className="palette-group-title">
                    {searchQuery ? 'Matching Workspaces & Operations' : 'Suggested Destinations'}
                  </div>
                  {localResults.map((item, idx) => {
                    const Icon = item.icon;
                    const isSelected = idx === selectedIndex;
                    return (
                      <div
                        key={item.id}
                        className={`palette-item ${isSelected ? 'selected' : ''}`}
                        onClick={() => handleSelectItem(item.path)}
                        onMouseEnter={() => setSelectedIndex(idx)}
                      >
                        <div className="palette-item-icon">
                          <Icon size={16} />
                        </div>
                        <div className="palette-item-info">
                          <div className="palette-item-title">{item.title}</div>
                          <div className="palette-item-sub">{item.description}</div>
                        </div>
                        <span className={`palette-badge ${item.category}`}>{item.category.toUpperCase()}</span>
                        <ArrowRight size={14} className="palette-arrow" />
                      </div>
                    );
                  })}
                </div>
              )}

              {backendHits.length > 0 && (
                <div className="palette-group">
                  <div className="palette-group-title">Backend Catalog & Database Hits</div>
                  {backendHits.map((hit, hIdx) => {
                    const globalIdx = localResults.length + hIdx;
                    const isSelected = globalIdx === selectedIndex;
                    const path = hit.entity_type === 'dataset' && hit.key
                      ? `/workspace?dataset_key=${encodeURIComponent(hit.key)}`
                      : hit.entity_type === 'alert'
                        ? '/operations/alerts'
                        : hit.entity_type === 'rule'
                          ? '/operations/governance'
                          : '/dashboard';

                    return (
                      <div
                        key={hit.objectID || `hit-${hIdx}`}
                        className={`palette-item ${isSelected ? 'selected' : ''}`}
                        onClick={() => handleSelectItem(path)}
                        onMouseEnter={() => setSelectedIndex(globalIdx)}
                      >
                        <div className="palette-item-icon">
                          {hit.entity_type === 'dataset' ? <Database size={16} /> : <ShieldCheck size={16} />}
                        </div>
                        <div className="palette-item-info">
                          <div className="palette-item-title">{hit.name || hit.title || hit.key}</div>
                          <div className="palette-item-sub">{hit.description || hit.rule_expression || hit.path}</div>
                        </div>
                        <span className="palette-badge entity">{(hit.entity_type || 'DATA').toUpperCase()}</span>
                        <ArrowRight size={14} className="palette-arrow" />
                      </div>
                    );
                  })}
                </div>
              )}
            </div>

            <div className="palette-footer">
              <span><kbd>↑</kbd> <kbd>↓</kbd> to navigate</span>
              <span><kbd>↵</kbd> to select</span>
              <span><kbd>esc</kbd> to dismiss</span>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
