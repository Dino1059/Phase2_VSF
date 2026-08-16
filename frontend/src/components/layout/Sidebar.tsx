import { useEffect, useState, useMemo } from 'react';
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
  X,
  Search,
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

function formatDatasetName(dataset: { key: string; filename?: string; path?: string }) {
  if (dataset.filename) return dataset.filename;
  if (dataset.path) {
    const fn = dataset.path.split('/').pop();
    if (fn) return fn;
  }
  return dataset.key.replace(/^uploaded_/, '').replace(/_/g, ' ');
}

const DS_ICONS: Record<string, React.ComponentType<{ size?: number | string; color?: string }>> = {
  ev: Car,
  vgreen: BatteryCharging,
  xanhsm: CarTaxiFront,
  nlp: MessageSquare,
};

export function Sidebar() {
  const [chatMenuOpen, setChatMenuOpen] = useState(false);
  const [activeShortcut, setActiveShortcut] = useState<string>('ev');
  const [datasetQuery, setDatasetQuery] = useState('');
  const { t, i18n } = useTranslation('pipeline');
  const isVi = i18n.language === 'vi';
  const navigate = useNavigate();
  const [uploadedDatasets, setUploadedDatasets] = useState<UploadedDataset[]>([]);

  useEffect(() => {
    let mounted = true;

    const loadUploadedDatasets = async () => {
      try {
        const response = await datasetsApi.list();
        if (!mounted) return;
        const builtinKeys = new Set(['vietnam_trips', 'vietnam_trips_dirty', 'vietnam_ecommerce_test']);
        setUploadedDatasets(
          response.datasets
            .filter((dataset) => !builtinKeys.has(dataset.key))
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

  // Filtered uploaded datasets
  const filteredUploadedDatasets = useMemo(() => {
    const q = datasetQuery.toLowerCase().trim();
    if (!q) return uploadedDatasets;
    return uploadedDatasets.filter(
      (dataset) =>
        dataset.name.toLowerCase().includes(q) ||
        dataset.key.toLowerCase().includes(q)
    );
  }, [datasetQuery, uploadedDatasets]);

  const hasAnyMatches = filteredSampleDatasets.length > 0 || filteredUploadedDatasets.length > 0;

  const handleSearchKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      if (filteredSampleDatasets.length > 0) {
        selectDomain(filteredSampleDatasets[0].shortcut);
      } else if (filteredUploadedDatasets.length > 0) {
        const key = filteredUploadedDatasets[0].key;
        setActiveShortcut(key);
        navigate(`/workspace?dataset_key=${encodeURIComponent(key)}`);
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
                  <div className="menu-label" style={{ fontSize: '10px', color: 'var(--neon-cyan)', letterSpacing: '1px', marginTop: '6px', padding: '0 4px' }}>
                    {t('sampleDatasets')}
                  </div>

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

              {filteredUploadedDatasets.length > 0 && (
                <>
                  <div className="menu-label" style={{ fontSize: '10px', color: 'var(--neon-cyan)', letterSpacing: '1px', marginTop: '8px', padding: '0 4px' }}>
                    {isVi ? 'TẬP DỮ LIỆU TẢI LÊN' : 'UPLOADED DATASETS'}
                  </div>
                  {filteredUploadedDatasets.map((dataset) => (
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
                </>
              )}
            </div>
          )}
        </div>

        <a href="#/workspace" className="menu-item" onClick={(event) => { event.preventDefault(); openNewChat(); }}>
          <CheckCircle size={18} />
          <span>{t('recentTasks')}</span>
        </a>

        <div className="menu-label" style={{ marginTop: '18px', paddingLeft: '14px' }}>
          {isVi ? 'VẬN HÀNH' : 'OPERATIONS'}
        </div>
        {[
          { key: 'alerts', label: isVi ? 'Bảng Cảnh Báo' : 'Alert Dashboard', icon: Bell, color: '#f43f5e' },
          { key: 'governance', label: isVi ? 'Quản Trị & Bộ Luật' : 'Governance & Rules', icon: CheckCircle, color: '#10b981' },
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
