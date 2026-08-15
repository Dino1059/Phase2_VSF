import { useState, useEffect, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import {
  Atom, Search, Moon, Sun, ShieldAlert, ChevronDown,
  IdCard, SlidersHorizontal, LogOut,
} from 'lucide-react';
import { useTheme } from '../../contexts/ThemeContext';

export function Header() {
  const [userDropdownOpen, setUserDropdownOpen] = useState(false);
  const { t } = useTranslation('pipeline');
  const { theme, toggleTheme } = useTheme();
  const searchRef = useRef<HTMLInputElement>(null);

  // ⌘K / Ctrl-K focuses the global search bar (ui_temp initKeyboardShortcuts)
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        searchRef.current?.focus();
      }
    };
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, []);

  return (
    <header className="top-hud">
      <div className="brand-section">
        <div className="logo-badge">
          <div className="logo-icon-box"><Atom size={18} /></div>
          <span><span style={{ color: 'var(--text-main)' }}>DATATRUST OS AGENT</span></span>
        </div>
      </div>

      <div className="nav-search-bar">
        <Search className="search-icon" size={16} />
        <input ref={searchRef} type="text" id="globalSearchInput" placeholder={t('searchPlaceholder')} />
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
              <a href="#" className="dropdown-item"><IdCard size={14} /> {t('profileInfo')}</a>
              <a href="#" className="dropdown-item"><SlidersHorizontal size={14} />{t('settings')}</a>
              <div className="dropdown-divider"></div>
              <a href="#" className="dropdown-item danger"><LogOut size={14} />{t('signOut')}</a>
            </div>
          )}
        </div>
      </div>

    </header>
  );
}
