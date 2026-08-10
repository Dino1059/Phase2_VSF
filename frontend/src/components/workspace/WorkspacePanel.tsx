import { useChatStore } from '../../stores/chatStore';
import { Database, ShieldCheck, AlertTriangle, FileText, GitCompare, LayoutDashboard } from 'lucide-react';
import type { WorkspaceView } from '../../types';
import { ProfileWorkspace } from './ProfileWorkspace';
import { RuleWorkspace } from './RuleWorkspace';
import { AuditWorkspace } from './AuditWorkspace';
import { AnomalyWorkspace } from './AnomalyWorkspace';

const VIEW_ICONS: Record<WorkspaceView, React.ComponentType<{ className?: string }>> = {
  empty: LayoutDashboard,
  profile: Database,
  rules: ShieldCheck,
  anomaly: AlertTriangle,
  audit: FileText,
  diff: GitCompare,
};

const VIEW_LABELS: Record<WorkspaceView, string> = {
  empty: 'Cockpit',
  profile: 'Data Profiler',
  rules: 'Quality Rules',
  anomaly: 'Anomaly Detector',
  audit: 'Audit Trail',
  diff: 'Diff View',
};

export function WorkspacePanel() {
  const { activeWorkspace, setWorkspace } = useChatStore();

  const views: WorkspaceView[] = ['profile', 'rules', 'anomaly', 'audit'];

  return (
    <div className="flex flex-col h-full bg-background">
      {/* Workspace header & view selector */}
      <div className="flex items-center justify-between px-4 h-10 bg-surface border-b border-border shrink-0">
        <div className="flex items-center gap-1">
          {views.map((v) => {
            const IconComp = VIEW_ICONS[v];
            const isActive = activeWorkspace === v;
            return (
              <button
                key={v}
                onClick={() => setWorkspace(v)}
                className={`flex items-center gap-1.5 px-2.5 py-1 rounded text-xs font-medium transition-colors ${
                  isActive
                    ? 'bg-surface-hover text-text-primary border border-border'
                    : 'text-text-muted hover:text-text-secondary hover:bg-surface-hover/50'
                }`}
              >
                {IconComp && <IconComp className="w-3.5 h-3.5" />}
                <span>{VIEW_LABELS[v]}</span>
              </button>
            );
          })}
        </div>
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
          <AnomalyWorkspace />
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
  const { setWorkspace } = useChatStore();
  return (
    <div className="flex flex-col items-center justify-center h-full text-text-muted p-6">
      <LayoutDashboard className="w-12 h-12 mb-3 opacity-30 text-agent-orchestrator" />
      <p className="text-sm font-semibold text-text-primary">Reliability Operations Cockpit</p>
      <p className="text-xs mt-1 text-text-muted max-w-sm text-center">
        Monitor data reliability, review proposed quality rules, analyze incident root causes, and verify audit records.
      </p>
      <div className="flex items-center gap-2 mt-4">
        <button
          onClick={() => setWorkspace('profile')}
          className="px-3 py-1.5 bg-surface border border-border text-text-primary rounded text-xs hover:bg-surface-hover transition-colors font-medium flex items-center gap-1.5"
        >
          <Database className="w-3.5 h-3.5 text-agent-profiler" /> Dataset Profile
        </button>
        <button
          onClick={() => setWorkspace('rules')}
          className="px-3 py-1.5 bg-surface border border-border text-text-primary rounded text-xs hover:bg-surface-hover transition-colors font-medium flex items-center gap-1.5"
        >
          <ShieldCheck className="w-3.5 h-3.5 text-agent-validator" /> Quality Rules
        </button>
        <button
          onClick={() => setWorkspace('anomaly')}
          className="px-3 py-1.5 bg-surface border border-border text-text-primary rounded text-xs hover:bg-surface-hover transition-colors font-medium flex items-center gap-1.5"
        >
          <AlertTriangle className="w-3.5 h-3.5 text-status-warning" /> Incidents
        </button>
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
