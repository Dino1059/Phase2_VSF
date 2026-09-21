import { NavLink } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import {
  LayoutDashboard, ClipboardList, Database, Bot, ShieldCheck,
  FileCheck2, FolderCheck, Workflow, Settings, Building2,
} from 'lucide-react';

const items = [
  { to: '/dashboard', vi: 'Dashboard', en: 'Dashboard', icon: LayoutDashboard },
  { to: '/operations/incidents', vi: 'Findings', en: 'Findings', icon: ClipboardList, badge: '12' },
  { to: '/workspace?tab=tab-profiler', vi: 'Chất lượng dữ liệu', en: 'Data Quality', icon: Database },
  { to: '/workspace', vi: 'Trợ lý AI', en: 'AI Assistant', icon: Bot, tag: 'MỚI' },
  { to: '/operations/governance', vi: 'Riêng tư & Bảo vệ', en: 'Privacy & Protection', icon: ShieldCheck },
  { to: '/operations/rules', vi: 'Kiểm soát (ITGC)', en: 'Controls (ITGC)', icon: FileCheck2 },
  { to: '/operations/snapshots', vi: 'Bằng chứng', en: 'Evidence', icon: FolderCheck },
  { to: '/dashboard/ingestion', vi: 'Luồng dữ liệu', en: 'Data Pipeline', icon: Workflow },
  { to: '/operations/governance', vi: 'Quản trị', en: 'Administration', icon: Settings },
];

export function Sidebar({ onNavigate }: { onNavigate?: () => void } = {}) {
  const { i18n } = useTranslation();
  const isVi = i18n.language === 'vi';

  return (
    <aside className="dash-sidebar new-ui-sidebar">
      <nav className="sidebar-section" aria-label="Main navigation">
        {items.map(({ to, vi, en, icon: Icon, badge, tag }) => (
          <NavLink
            key={`${to}-${en}`}
            to={to}
            onClick={onNavigate}
            className={({ isActive }) => `menu-item ${isActive ? 'active' : ''}`}
          >
            <Icon size={17} />
            <span>{isVi ? vi : en}</span>
            {badge && <em className="nav-count">{badge}</em>}
            {tag && <em className="nav-new">{tag}</em>}
          </NavLink>
        ))}
      </nav>
      <div className="sidebar-tenant">
        <span className="tenant-mark"><Building2 size={15} /></span>
        <span><strong>GSM Global</strong><small>v1.0.0</small></span>
      </div>
    </aside>
  );
}
