import { useEffect, useState, useMemo } from 'react';
import { NavLink, useNavigate, useSearchParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import {
  PieChart,
  MessageSquare,
  ChevronDown,
  Car,
  BatteryCharging,
  CarTaxiFront,
  CheckCircle,
  Database,
  Bell,
  X,
  Search,
  ShieldCheck,
  ShieldAlert,
  Play,
  Sparkles,
} from 'lucide-react';
import { DOMAIN_LIST } from '../../stores/pipelineStore';

const DS_ICONS: Record<string, React.ComponentType<{ size?: number | string; color?: string }>> = {
  pilot: Sparkles,
  ev: Car,
  vgreen: BatteryCharging,
  xanhsm: CarTaxiFront,
  nlp: MessageSquare,
};

export function Sidebar() {
  const [chatMenuOpen, setChatMenuOpen] = useState(false);
  const [activeShortcut, setActiveShortcut] = useState<string>('pilot');
  const [datasetQuery, setDatasetQuery] = useState('');
  const { t, i18n } = useTranslation('pipeline');
  const isVi = i18n.language === 'vi';
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const currentDatasetKey = searchParams.get('dataset_key');

  useEffect(() => {
    if (currentDatasetKey) {
      const domain = DOMAIN_LIST.find((d) => d.id === currentDatasetKey || d.shortcut === currentDatasetKey);
      if (domain) {
        setActiveShortcut(domain.shortcut);
      } else {
        setActiveShortcut(currentDatasetKey);
      }
    }
  }, [currentDatasetKey]);

  useEffect(() => {
    const handleDbReset = () => {
      setActiveShortcut('ev');
    };

    window.addEventListener('datatrust:db-reset', handleDbReset);

    return () => {
      window.removeEventListener('datatrust:db-reset', handleDbReset);
    };
  }, []);

  const selectDomain = (shortcut: string) => {
    setActiveShortcut(shortcut);
    const domain = DOMAIN_LIST.find((d) => d.shortcut === shortcut);
    const datasetKey = domain ? domain.id : shortcut;
    navigate(`/workspace?dataset_key=${encodeURIComponent(datasetKey)}`);
  };

  const openNewChat = () => {
    setActiveShortcut('');
    navigate(`/workspace?new=${Date.now()}`);
  };

  // Filtered sample datasets
  const filteredSampleDatasets = useMemo(() => {
    const q = datasetQuery.toLowerCase().trim();
    if (!q) return DOMAIN_LIST;
    return DOMAIN_LIST.filter(
      (domain) =>
        domain.name.toLowerCase().includes(q) ||
        domain.id.toLowerCase().includes(q) ||
        domain.shortcut.toLowerCase().includes(q)
    );
  }, [datasetQuery]);

  const hasAnyMatches = filteredSampleDatasets.length > 0;

  const handleSearchKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      if (filteredSampleDatasets.length > 0) {
        selectDomain(filteredSampleDatasets[0].shortcut);
      }
    }
  };

  return (
    <aside className="dash-sidebar">
      <div className="sidebar-section">
        <NavLink
          to="/dashboard"
          className={({ isActive }: { isActive: boolean }) => `menu-item ${isActive ? 'active' : ''}`}
        >
          <PieChart size={18} />
          <span>{t('execHome')}</span>
        </NavLink>



        <div className="agent-chat-menu-wrapper">
          <div
            className="menu-item"
            onClick={() => {
              setChatMenuOpen((o) => !o);
              openNewChat();
            }}
          >
            <MessageSquare size={18} color="var(--neon-cyan)" />
            <span>{t('newChat')}</span>
            <ChevronDown size={14} className="sub-arrow" style={{ transform: chatMenuOpen ? 'rotate(180deg)' : 'none' }} />
          </div>

          {chatMenuOpen && (
            <div className="agent-chat-subpanel show" style={{ display: 'block' }}>
              <div className="subpanel-header" style={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
                <Search size={13} style={{ position: 'absolute', left: '10px', color: 'var(--text-muted)' }} />
                <input
                  type="text"
                  className="search-box"
                  style={{ paddingLeft: '28px', paddingRight: datasetQuery ? '28px' : '10px' }}
                  placeholder={isVi ? 'Lọc tập dữ liệu...' : (t('searchPlaceholder') || 'Filter datasets...')}
                  value={datasetQuery}
                  onChange={(e) => setDatasetQuery(e.target.value)}
                  onKeyDown={handleSearchKeyDown}
                  autoFocus
                />
                {datasetQuery && (
                  <button
                    type="button"
                    onClick={() => setDatasetQuery('')}
                    style={{
                      position: 'absolute',
                      right: '8px',
                      background: 'none',
                      border: 'none',
                      color: 'var(--text-muted)',
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      padding: 2,
                    }}
                    title={isVi ? 'Xóa bộ lọc' : 'Clear filter'}
                  >
                    <X size={12} />
                  </button>
                )}
              </div>

              {!hasAnyMatches && (
                <div style={{ padding: '12px 8px', fontSize: '11px', color: 'var(--text-muted)', textAlign: 'center' }}>
                  {isVi ? `Không tìm thấy tập dữ liệu "${datasetQuery}"` : `No datasets match "${datasetQuery}"`}
                </div>
              )}

              {filteredSampleDatasets.length > 0 && (
                <>

                  {filteredSampleDatasets.map((domain) => {
                    const Icon = DS_ICONS[domain.shortcut] || Database;
                    return (
                      <a
                        key={domain.id}
                        href="#/workspace"
                        className={`shortcut-item ${activeShortcut === domain.shortcut ? 'active' : ''}`}
                        onClick={(e) => {
                          e.preventDefault();
                          selectDomain(domain.shortcut);
                        }}
                      >
                        <div className={`ds-icon ${domain.shortcut}`}><Icon size={14} /></div>
                        <span>{domain.name}</span>
                      </a>
                    );
                  })}
                </>
              )}
            </div>
          )}
        </div>

        <a href="#/workspace" className="menu-item" onClick={(event) => { event.preventDefault(); openNewChat(); }}>
          <CheckCircle size={18} />
          <span>{t('recentTasks')}</span>
        </a>

        <NavLink
          to="/dashboard/ingestion"
          className={({ isActive }: { isActive: boolean }) => `menu-item ${isActive ? 'active' : ''}`}
        >
          <Play size={18} color="var(--neon-cyan)" />
          <span>{isVi ? 'Data Ingestion' : 'Data Ingestion'}</span>
        </NavLink>

        <div className="menu-label" style={{ marginTop: '18px', paddingLeft: '14px' }}>
          {isVi ? 'VẬN HÀNH & BỘ LUẬT' : 'OPERATIONS & RULES'}
        </div>
        {[
          { key: 'alerts', label: isVi ? 'Bảng Cảnh Báo' : 'Alert Dashboard', icon: Bell, color: '#f43f5e' },
          { key: 'rules', label: isVi ? 'Bộ Luật Đang Áp Dụng' : 'Active Quality Rules', icon: ShieldCheck, color: '#10b981' },
          { key: 'quarantine', label: isVi ? 'Khu Vực Cách Ly' : 'Quarantine Zone', icon: ShieldAlert, color: '#f43f5e' },
          { key: 'governance', label: isVi ? 'Quản Trị & Sổ Cái' : 'Governance & Policies', icon: CheckCircle, color: '#38bdf8' },
        ].map(({ key, label, icon: Icon, color }) => (
          <NavLink
            key={key}
            to={`/operations/${key}`}
            className={({ isActive }: { isActive: boolean }) => `menu-item ${isActive ? 'active' : ''}`}
          >
            <Icon size={18} color={color} />
            <span>{label}</span>
          </NavLink>
        ))}
      </div>

      <div className="sidebar-footer" style={{ marginTop: '12px' }}>
        <div className="dataset-lib-badge" onClick={() => navigate('/workspace')} style={{ cursor: 'pointer' }}>
          <Database size={18} />
          <div>
            <div className="lib-title">{t('datasetLibrary')}</div>
            <div className="lib-count">{t('datasetCount')}</div>
          </div>
        </div>
      </div>
    </aside>
  );
}
