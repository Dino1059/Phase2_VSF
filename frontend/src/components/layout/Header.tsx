import { useState, useEffect, useRef, type ChangeEvent } from 'react';
import { useTranslation } from 'react-i18next';
import {
  Atom, Search, Moon, Sun, CloudUpload, ShieldAlert, ChevronDown,
  IdCard, SlidersHorizontal, LogOut,
} from 'lucide-react';
import { useTheme } from '../../contexts/ThemeContext';
import { uploadDatasetFile } from '../../services/api';

export function Header() {
  const [userDropdownOpen, setUserDropdownOpen] = useState(false);
  const [uploadOpen, setUploadOpen] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const { t } = useTranslation('pipeline');
  const { theme, toggleTheme } = useTheme();
  const searchRef = useRef<HTMLInputElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileChange = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = '';
    if (!file) return;

    const extension = file.name.slice(file.name.lastIndexOf('.')).toLowerCase();
    if (!['.csv', '.db', '.json'].includes(extension)) {
      setUploadError('Only CSV, DB, and JSON files are supported.');
      return;
    }

    setUploadError(null);
    setIsUploading(true);
    try {
      const result = await uploadDatasetFile(file);
      window.dispatchEvent(new CustomEvent('datatrust:dataset-uploaded', { detail: result }));
      setUploadOpen(false);
    } catch (error) {
      setUploadError(error instanceof Error ? error.message : 'Unable to upload the file.');
    } finally {
      setIsUploading(false);
    }
  };

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
        <button className="nav-btn-upload" onClick={() => { setUploadError(null); setUploadOpen(true); }}>
          <CloudUpload size={16} style={{ display: 'inline', marginRight: '4px' }} /> Upload Database
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

      {uploadOpen && (
        <div className="modal-overlay active" onClick={() => setUploadOpen(false)}>
          <div className="modal-card" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <span className="modal-title"><CloudUpload size={16} style={{ display: 'inline', marginRight: 6 }} /> {t('uploadTitle')}</span>
              <button className="modal-close" onClick={() => setUploadOpen(false)}><SlidersHorizontal size={16} /></button>
            </div>
            <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 10 }} role={uploadError ? 'alert' : undefined}>
              {uploadError || t('uploadDesc')}
            </div>
            <input
              ref={fileInputRef}
              type="file"
              accept=".csv,.db,.json"
              onChange={handleFileChange}
              hidden
            />
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10 }}>
              <button className="hud-btn" onClick={() => setUploadOpen(false)}>{t('cancel')}</button>
              <button className="btn-accept" onClick={() => fileInputRef.current?.click()} disabled={isUploading}>
                <CloudUpload size={14} /> {t('selectPayload')}
              </button>
            </div>
          </div>
        </div>
      )}
    </header>
  );
}
