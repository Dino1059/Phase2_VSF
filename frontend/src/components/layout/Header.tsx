import { useState, useEffect, useRef, useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import {
  Atom, Search, Moon, Sun, ShieldAlert, ChevronDown,
  IdCard, SlidersHorizontal, LogOut, X, Database,
  AlertTriangle, Radio, GitBranch, ShieldCheck,
  History, Camera, LayoutDashboard, MessageSquare, ArrowRight,
} from 'lucide-react';
import { useTheme } from '../../contexts/ThemeContext';
import { searchApi, SearchHit } from '../../services/api';
import { DOMAIN_LIST } from '../../stores/pipelineStore';

interface StaticSearchResult {
  id: string;
  title: string;
  category: 'dataset' | 'operation' | 'action';
  description: string;
  path: string;
  icon: typeof Database;
}

const STATIC_OPERATIONS: StaticSearchResult[] = [
  { id: 'op-dashboard', title: 'Executive Homepage', category: 'operation', description: 'Real-time KPI metrics, anomaly trends, and HITL governance', path: '/dashboard', icon: LayoutDashboard },
  { id: 'op-new-chat', title: 'New Agent Chat Session', category: 'action', description: 'Start AI Steward interactive analysis session', path: '/workspace', icon: MessageSquare },
  { id: 'op-alerts', title: 'Alert Center', category: 'operation', description: 'Real-time threshold alerts and webhook dispatchers', path: '/operations/alerts', icon: AlertTriangle },
  { id: 'op-incidents', title: 'Incident Command', category: 'operation', description: 'Multi-layer anomaly incidents and causal hypotheses', path: '/operations/incidents', icon: ShieldAlert },
  { id: 'op-signals', title: 'Signal Explorer', category: 'operation', description: 'L1-L4 anomaly detection signals and statistical drift', path: '/operations/signals', icon: Radio },
  { id: 'op-traces', title: 'Agent Traces', category: 'operation', description: 'ReAct agent execution trajectories and tool logs', path: '/operations/traces', icon: GitBranch },
  { id: 'op-governance', title: 'Governance & Admin', category: 'operation', description: 'Data quality rule policies and audit controls', path: '/operations/governance', icon: ShieldCheck },
  { id: 'op-executions', title: 'Execution History', category: 'operation', description: 'Quarantine and clean split transformation executions', path: '/operations/executions', icon: History },
  { id: 'op-snapshots', title: 'Data Snapshots', category: 'operation', description: 'Cryptographic schema state and row count manifests', path: '/operations/snapshots', icon: Camera },
];

export function Header() {
  const [userDropdownOpen, setUserDropdownOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchOpen, setSearchOpen] = useState(false);
  const [backendHits, setBackendHits] = useState<SearchHit[]>([]);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [isSearching, setIsSearching] = useState(false);

  const { t } = useTranslation('pipeline');
  const { theme, toggleTheme } = useTheme();
  const modalInputRef = useRef<HTMLInputElement>(null);
  const modalBoxRef = useRef<HTMLDivElement>(null);
  const navigate = useNavigate();

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
    if (!q) return STATIC_OPERATIONS.slice(0, 6);

    const matchedOps = STATIC_OPERATIONS.filter(
      (op) => op.title.toLowerCase().includes(q) || op.description.toLowerCase().includes(q)
    );

    const matchedDatasets: StaticSearchResult[] = DOMAIN_LIST.filter(
      (d) => d.name.toLowerCase().includes(q) || d.id.toLowerCase().includes(q) || d.shortcut.toLowerCase().includes(q)
    ).map((d) => ({
      id: `dataset-${d.id}`,
      title: d.name,
      category: 'dataset',
      description: `Pilot dataset · ${d.shortcut}`,
      path: `/workspace?dataset_key=${encodeURIComponent(d.id)}`,
      icon: Database,
    }));

    return [...matchedDatasets, ...matchedOps];
  }, [searchQuery]);

  // Combined flattened items for keyboard navigation
  const allNavigableItems = useMemo(() => {
    const items: Array<{ id: string; title: string; subtitle?: string; path: string; category: string }> = [];

    localResults.forEach((item) => {
      items.push({
        id: item.id,
        title: item.title,
        subtitle: item.description,
        path: item.path,
        category: item.category,
      });
    });

    backendHits.forEach((hit, idx) => {
      const path = hit.entity_type === 'dataset' && hit.key
        ? `/workspace?dataset_key=${encodeURIComponent(hit.key)}`
        : hit.entity_type === 'alert'
        ? '/operations/alerts'
        : hit.entity_type === 'rule'
        ? '/operations/governance'
        : '/dashboard';

      items.push({
        id: hit.objectID || `backend-${idx}`,
        title: hit.name || hit.title || hit.key || 'Entity',
        subtitle: hit.description || hit.rule_expression || hit.path || hit.entity_type,
        path,
        category: hit.entity_type || 'result',
      });
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
          <button className="theme-toggle-btn" title="Toggle Dark/White Mode" onClick={toggleTheme}>
            {theme === 'tech-dark' ? <Sun size={18} /> : <Moon size={18} />}
          </button>
          <div className="user-profile-wrapper" onClick={() => setUserDropdownOpen(!userDropdownOpen)}>
            <div className="user-profile-btn">
              <div className="user-avatar-box"><ShieldAlert size={16} /></div>
              <div className="user-info-text">
                <span className="user-name-str">Huyen Vu</span>
                <span className="user-role-str">Steward Admin</span>
              </div>
              <ChevronDown className="dropdown-arrow" size={12} />
            </div>
            {userDropdownOpen && (
              <div className="user-dropdown-menu show" style={{ display: 'block' }}>
                <div className="dropdown-user-header">
                  <div className="dropdown-user-name">Huyen Vu</div>
                  <div className="dropdown-user-email">vuthuhuyen@enterprise.ai</div>
                </div>
                <div className="dropdown-divider"></div>
                <a href="#/operations/governance" className="dropdown-item" onClick={() => navigate('/operations/governance')}>
                  <IdCard size={14} /> {t('profileInfo')}
                </a>
                <a href="#/operations/governance" className="dropdown-item" onClick={() => navigate('/operations/governance')}>
                  <SlidersHorizontal size={14} /> {t('settings')}
                </a>
                <div className="dropdown-divider"></div>
                <a href="#" className="dropdown-item danger" onClick={(e) => { e.preventDefault(); setUserDropdownOpen(false); }}>
                  <LogOut size={14} /> {t('signOut')}
                </a>
              </div>
            )}
          </div>
        </div>
      </header>

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
