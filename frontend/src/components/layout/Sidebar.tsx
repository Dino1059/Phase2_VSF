import { useEffect, useMemo, useState } from 'react';
import { NavLink, useNavigate, useSearchParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import {
  BarChart3,
  BatteryCharging,
  Bell,
  Car,
  CarTaxiFront,
  CheckCircle,
  ChevronDown,
  Database,
  FlaskConical,
  MessageSquare,
  PieChart,
  Search,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  X,
} from 'lucide-react';
import { DOMAIN_LIST } from '../../stores/pipelineStore';

const DS_ICONS: Record<string, React.ComponentType<{ size?: number | string }>> = {
  pilot: Sparkles,
  ev: Car,
  vgreen: BatteryCharging,
  xanhsm: CarTaxiFront,
  nlp: MessageSquare,
};

export function Sidebar({ onNavigate }: { onNavigate?: () => void } = {}) {
  const [activeShortcut, setActiveShortcut] = useState('ev');
  const [datasetQuery, setDatasetQuery] = useState('');
  const { i18n } = useTranslation('pipeline');
  const isVi = i18n.language === 'vi';
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const currentDatasetKey = searchParams.get('dataset_key');

  useEffect(() => {
    if (!currentDatasetKey) return;
    const domain = DOMAIN_LIST.find((item) => item.id === currentDatasetKey || item.shortcut === currentDatasetKey);
    setActiveShortcut(domain?.shortcut ?? currentDatasetKey);
  }, [currentDatasetKey]);

  useEffect(() => {
    const handleDbReset = () => setActiveShortcut('ev');
    window.addEventListener('datatrust:db-reset', handleDbReset);
    return () => window.removeEventListener('datatrust:db-reset', handleDbReset);
  }, []);

  const selectDomain = (shortcut: string) => {
    setActiveShortcut(shortcut);
    const domain = DOMAIN_LIST.find((item) => item.shortcut === shortcut);
    const day = searchParams.get('day') || searchParams.get('day_idx') || '';
    const query = new URLSearchParams({ dataset_key: domain?.id ?? shortcut });
    if (day) {
      query.set('day', day);
      query.set('run_id', day);
    }
    navigate(`/workspace?${query.toString()}`);
    onNavigate?.();
  };

  const filteredDatasets = useMemo(() => {
    const query = datasetQuery.toLowerCase().trim();
    if (!query) return DOMAIN_LIST;
    return DOMAIN_LIST.filter((domain) =>
      [domain.name, domain.id, domain.shortcut].some((value) => value.toLowerCase().includes(query))
    );
  }, [datasetQuery]);

  return (
    <aside className="dash-sidebar">
      <div className="sidebar-section">
        <NavLink
          to="/dashboard"
          onClick={onNavigate}
          className={({ isActive }) => `menu-item sidebar-home ${isActive ? 'active' : ''}`}
        >
          <PieChart size={18} />
          <span>{isVi ? 'Tổng quan' : 'Overview'}</span>
        </NavLink>

        <div className="menu-label workflow-label">{isVi ? 'QUY TRÌNH CHÍNH' : 'MAIN WORKFLOW'}</div>
        <NavLink
          to="/dashboard/ingestion"
          onClick={onNavigate}
          className={({ isActive }) => `menu-item workflow-item ${isActive ? 'active' : ''}`}
        >
          <span className="workflow-number">1</span>
          <span>{isVi ? 'Nạp dữ liệu' : 'Ingest data'}</span>
        </NavLink>
        <NavLink
          to="/workspace"
          onClick={onNavigate}
          className={({ isActive }) => `menu-item workflow-item ${isActive ? 'active' : ''}`}
        >
          <span className="workflow-number">2</span>
          <span>{isVi ? 'Phân tích' : 'Analyze'}</span>
        </NavLink>
        <NavLink
          to="/operations/rules"
          onClick={onNavigate}
          className={({ isActive }) => `menu-item workflow-item ${isActive ? 'active' : ''}`}
        >
          <span className="workflow-number">3</span>
          <span>{isVi ? 'Duyệt kết quả' : 'Review results'}</span>
        </NavLink>

        <details className="sidebar-advanced">
          <summary>
            <span>{isVi ? 'Nâng cao' : 'Advanced'}</span>
            <ChevronDown size={15} />
          </summary>
          <div className="sidebar-advanced-content">
            <button
              type="button"
              className="menu-item sidebar-button"
              onClick={() => {
                navigate('/workspace?new=1');
                onNavigate?.();
              }}
            >
              <MessageSquare size={17} />
              <span>{isVi ? 'Phân tích mới' : 'New analysis'}</span>
            </button>

            <div className="dataset-picker">
              <label htmlFor="sidebar-dataset-search">{isVi ? 'Chọn tập dữ liệu' : 'Choose dataset'}</label>
              <div className="dataset-search">
                <Search size={14} />
                <input
                  id="sidebar-dataset-search"
                  value={datasetQuery}
                  onChange={(event) => setDatasetQuery(event.target.value)}
                  placeholder={isVi ? 'Tìm tập dữ liệu…' : 'Find a dataset…'}
                />
                {datasetQuery && (
                  <button type="button" onClick={() => setDatasetQuery('')} aria-label={isVi ? 'Xóa tìm kiếm' : 'Clear search'}>
                    <X size={13} />
                  </button>
                )}
              </div>
              <div className="dataset-options">
                {filteredDatasets.map((domain) => {
                  const Icon = DS_ICONS[domain.shortcut] || Database;
                  return (
                    <button
                      type="button"
                      key={domain.id}
                      className={`shortcut-item ${activeShortcut === domain.shortcut ? 'active' : ''}`}
                      onClick={() => selectDomain(domain.shortcut)}
                    >
                      <Icon size={14} />
                      <span>{domain.name}</span>
                    </button>
                  );
                })}
              </div>
            </div>

            <div className="advanced-links">
              {[
                { key: 'alerts', vi: 'Cảnh báo', en: 'Alerts', icon: Bell },
                { key: 'quarantine', vi: 'Dữ liệu cách ly', en: 'Quarantine', icon: ShieldAlert },
                { key: 'eval', vi: 'Đánh giá mô hình', en: 'Evaluation', icon: FlaskConical },
                { key: 'governance', vi: 'Quản trị', en: 'Governance', icon: ShieldCheck },
              ].map(({ key, vi, en, icon: Icon }) => (
                <NavLink
                  key={key}
                  to={`/operations/${key}`}
                  onClick={onNavigate}
                  className={({ isActive }) => `menu-item ${isActive ? 'active' : ''}`}
                >
                  <Icon size={17} />
                  <span>{isVi ? vi : en}</span>
                </NavLink>
              ))}
            </div>

            <div className="sidebar-flow-hint">
              <BarChart3 size={15} />
              <span>{isVi ? 'Dùng các mục này khi cần kiểm tra sâu.' : 'Use these tools for deeper inspection.'}</span>
              <CheckCircle size={15} />
            </div>
          </div>
        </details>
      </div>
    </aside>
  );
}
