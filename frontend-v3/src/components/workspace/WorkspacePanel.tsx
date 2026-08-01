import { useTranslation } from 'react-i18next';
import { useChatStore } from '../../stores/chatStore';
import { Database, ShieldCheck, AlertTriangle, FileText, GitCompare, LayoutDashboard } from 'lucide-react';
import type { WorkspaceView } from '../../types';
import { ProfileWorkspace } from './ProfileWorkspace';
import { RuleWorkspace } from './RuleWorkspace';
import { AuditWorkspace } from './AuditWorkspace';

const VIEW_ICONS: Record<WorkspaceView, React.ComponentType<{ className?: string }>> = {
  empty: LayoutDashboard,
  profile: Database,
  rules: ShieldCheck,
  anomaly: AlertTriangle,
  audit: FileText,
  diff: GitCompare,
};

const VIEW_LABELS: Record<WorkspaceView, string> = {
  empty: 'common:appName',
  profile: 'profiler:title',
  rules: 'rules:title',
  anomaly: 'agents:anomalyDetector',
  audit: 'audit:title',
  diff: 'Diff View',
};

export function WorkspacePanel() {
  const { t } = useTranslation();
  const { activeWorkspace } = useChatStore();
  const Icon = VIEW_ICONS[activeWorkspace];

  return (
    <div className="flex flex-col h-full bg-background">
      {/* Workspace header */}
      <div className="flex items-center gap-2 px-4 h-10 bg-surface border-b border-border shrink-0">
        {Icon && <Icon className="w-4 h-4 text-text-secondary" />}
        <span className="text-xs font-medium text-text-secondary">
          {t(VIEW_LABELS[activeWorkspace])}
        </span>
      </div>

      {/* Workspace content */}
      <div className="flex-1 overflow-auto">
        {activeWorkspace === 'empty' ? (
          <EmptyWorkspace />
        ) : activeWorkspace === 'profile' ? (
          <ProfileWorkspace />
        ) : activeWorkspace === 'rules' ? (
          <RuleWorkspace />
        ) : activeWorkspace === 'anomaly' ? (
          <AnomalyPlaceholder />
        ) : activeWorkspace === 'audit' ? (
          <AuditWorkspace />
        ) : (
          <DiffPlaceholder />
        )}
      </div>
    </div>
  );
}

function EmptyWorkspace() {
  const { t } = useTranslation();
  return (
    <div className="flex flex-col items-center justify-center h-full text-text-muted">
      <LayoutDashboard className="w-16 h-16 mb-4 opacity-20" />
      <p className="text-sm font-medium">{t('common:appSubtitle')}</p>
      <p className="text-xs mt-2 opacity-60 max-w-xs text-center">
        Agent workspace will appear here as they process your data.
        Start by typing a command in the chat.
      </p>
    </div>
  );
}

function AnomalyPlaceholder() {
  const { t } = useTranslation('agents');
  return (
    <div className="p-6">
      <div className="border border-border rounded-lg p-8 text-center text-text-muted">
        <AlertTriangle className="w-10 h-10 mx-auto mb-3 opacity-30" />
        <p className="text-sm">{t('anomalyDetector')}</p>
        <p className="text-xs mt-1 opacity-60">Anomaly timeline will appear here</p>
      </div>
    </div>
  );
}

function DiffPlaceholder() {
  return (
    <div className="p-6">
      <div className="border border-border rounded-lg p-8 text-center text-text-muted">
        <GitCompare className="w-10 h-10 mx-auto mb-3 opacity-30" />
        <p className="text-sm">Diff View</p>
        <p className="text-xs mt-1 opacity-60">Before/after data comparison will appear here</p>
      </div>
    </div>
  );
}
