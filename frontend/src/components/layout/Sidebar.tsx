import { useState } from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
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
} from 'lucide-react';
import { DOMAIN_LIST } from '../../stores/pipelineStore';

const DS_ICONS: Record<string, React.ComponentType<{ size?: number | string; color?: string }>> = {
  ev: Car,
  vgreen: BatteryCharging,
  xanhsm: CarTaxiFront,
  nlp: MessageSquare,
};

export function Sidebar() {
  const [chatMenuOpen, setChatMenuOpen] = useState(false);
  const [activeShortcut, setActiveShortcut] = useState<string>('ev');
  const { t } = useTranslation('pipeline');
  const navigate = useNavigate();

  const selectDomain = (shortcut: string) => {
    setActiveShortcut(shortcut);
    navigate('/workspace');
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
              navigate('/workspace');
            }}
          >
            <MessageSquare size={18} color="var(--neon-cyan)" />
            <span>{t('newChat')}</span>
            <ChevronDown size={14} className="sub-arrow" style={{ transform: chatMenuOpen ? 'rotate(180deg)' : 'none' }} />
          </div>

          {chatMenuOpen && (
            <div className="agent-chat-subpanel show" style={{ display: 'block' }}>
              <div className="subpanel-header">
                <input type="text" className="search-box" placeholder={t('searchPlaceholder')} />
              </div>
              <div className="menu-label" style={{ fontSize: '10px', color: 'var(--neon-cyan)', letterSpacing: '1px', marginTop: '6px', padding: '0 4px' }}>{t('sampleDatasets')}</div>

              {DOMAIN_LIST.map((domain) => {
                const Icon = DS_ICONS[domain.shortcut] || Database;
                return (
                  <a
                    key={domain.id}
                    href={`#/workspace`}
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
            </div>
          )}
        </div>

        <a href="#/workspace" className="menu-item" onClick={() => navigate('/workspace')}>
          <CheckCircle size={18} />
          <span>{t('recentTasks')}</span>
        </a>
      </div>

      <div className="sidebar-footer" style={{ marginTop: '12px' }}>
        <div className="dataset-lib-badge">
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
