import { useEffect, useState } from 'react';
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
  Bell,
  TriangleAlert,
  Activity,
  GitBranch,
  Shield,
  ListChecks,
  Camera,
} from 'lucide-react';
import { DOMAIN_LIST } from '../../stores/pipelineStore';
import { datasetsApi } from '../../services/api';

interface UploadedDataset {
  key: string;
  name: string;
}

interface DatasetUploadedEvent {
  dataset_key?: string;
  filename?: string;
}

function formatDatasetName(dataset: { key: string; filename?: string }) {
  if (dataset.filename) return dataset.filename;
  return dataset.key.replace(/^uploaded_/, '').replace(/_/g, ' ');
}

const DS_ICONS: Record<string, React.ComponentType<{ size?: number | string; color?: string }>> = {
  ev: Car,
  vgreen: BatteryCharging,
  xanhsm: CarTaxiFront,
  nlp: MessageSquare,
};

const OPERATIONS = [
  { key: 'alerts', label: 'Alert Center', icon: Bell, color: '#dc2626' },
  { key: 'incidents', label: 'Incidents', icon: TriangleAlert, color: '#d97706' },
  { key: 'signals', label: 'Signal Explorer', icon: Activity, color: '#7c3aed' },
  { key: 'traces', label: 'Agent Traces', icon: GitBranch, color: '#059669' },
  { key: 'governance', label: 'Governance & Admin', icon: Shield, color: '#1e293b' },
  { key: 'executions', label: 'Execution History', icon: ListChecks, color: '#1e293b' },
  { key: 'snapshots', label: 'Data Snapshots', icon: Camera, color: '#1e293b' },
];

export function Sidebar() {
  const [chatMenuOpen, setChatMenuOpen] = useState(false);
  const [activeShortcut, setActiveShortcut] = useState<string>('ev');
  const { t } = useTranslation('pipeline');
  const navigate = useNavigate();
  const [uploadedDatasets, setUploadedDatasets] = useState<UploadedDataset[]>([]);

  useEffect(() => {
    let mounted = true;

    const loadUploadedDatasets = async () => {
      try {
        const response = await datasetsApi.list();
        if (!mounted) return;
        setUploadedDatasets(
          response.datasets
            .filter((dataset) => dataset.key.startsWith('uploaded_'))
            .map((dataset) => ({ key: dataset.key, name: formatDatasetName(dataset) }))
        );
      } catch (error) {
        console.error('Failed to load uploaded datasets:', error);
      }
    };

    const handleDatasetUploaded = (event: Event) => {
      const detail = (event as CustomEvent<DatasetUploadedEvent>).detail;
      const key = detail?.dataset_key;
      if (!key) return;

      setChatMenuOpen(true);
      setActiveShortcut(key);
      setUploadedDatasets((current) => [
        ...current.filter((dataset) => dataset.key !== key),
        { key, name: formatDatasetName({ key, filename: detail.filename }) },
      ]);
      navigate(`/workspace?dataset_key=${encodeURIComponent(key)}`);
    };

    void loadUploadedDatasets();
    window.addEventListener('datatrust:dataset-uploaded', handleDatasetUploaded);

    return () => {
      mounted = false;
      window.removeEventListener('datatrust:dataset-uploaded', handleDatasetUploaded);
    };
  }, []);

  const selectDomain = (shortcut: string) => {
    setActiveShortcut(shortcut);
    navigate('/workspace');
  };

  const openNewChat = () => {
    setActiveShortcut('');
    navigate(`/workspace?new=${Date.now()}`);
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

              {uploadedDatasets.map((dataset) => (
                <a
                  key={dataset.key}
                  href="#/workspace"
                  className={`shortcut-item ${activeShortcut === dataset.key ? 'active' : ''}`}
                  onClick={(e) => {
                    e.preventDefault();
                    setActiveShortcut(dataset.key);
                    navigate(`/workspace?dataset_key=${encodeURIComponent(dataset.key)}`);
                  }}
                >
                  <div className="ds-icon"><Database size={14} /></div>
                  <span>{dataset.name}</span>
                </a>
              ))}
            </div>
          )}
        </div>

        <a href="#/workspace" className="menu-item" onClick={(event) => { event.preventDefault(); openNewChat(); }}>
          <CheckCircle size={18} />
          <span>{t('recentTasks')}</span>
        </a>

        <div className="menu-label" style={{ marginTop: '18px', paddingLeft: '14px' }}>Operations</div>
        {OPERATIONS.map(({ key, label, icon: Icon, color }) => (
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
