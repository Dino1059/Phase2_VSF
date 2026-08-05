import { useTranslation } from 'react-i18next';
import { FileText, Hash, Clock, CheckCircle, AlertCircle } from 'lucide-react';
import { useChatStore } from '../../stores/chatStore';
import { AGENTS } from '../../types';
import type { AgentId } from '../../types';

interface AuditEntry {
  id: string;
  timestamp: string;
  action: string;
  agentId: AgentId;
  status: 'success' | 'error';
  details?: string;
  manifestHash?: string;
}

export function AuditWorkspace() {
  const { t } = useTranslation('audit');
  const workspaceData = useChatStore((s) => s.workspaceData) as { entries?: AuditEntry[] } | null;
  const entries = workspaceData?.entries || [];

  if (entries.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-text-muted p-8">
        <FileText className="w-12 h-12 mb-3 opacity-20" />
        <p className="text-sm">{t('title')}</p>
        <p className="text-xs mt-1 opacity-60">{t('noAuditEntries')}</p>
      </div>
    );
  }

  return (
    <div className="p-4 space-y-2">
      <h3 className="text-sm font-semibold text-text-primary mb-3">{t('executionLog')}</h3>
      {entries.map((entry) => {
        const agent = AGENTS[entry.agentId];
        return (
          <div key={entry.id} className="flex items-start gap-3 px-3 py-2.5 bg-surface border border-border rounded-lg">
            <div className="shrink-0 mt-0.5">
              {entry.status === 'success' ? (
                <CheckCircle className="w-4 h-4 text-status-success" />
              ) : (
                <AlertCircle className="w-4 h-4 text-status-error" />
              )}
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <span className="text-xs font-medium text-text-primary">{entry.action}</span>
                <span className="text-[10px] font-medium" style={{ color: agent.color }}>
                  {t(agent.nameKey)}
                </span>
              </div>
              {entry.details && (
                <p className="text-[11px] text-text-muted mt-0.5">{entry.details}</p>
              )}
              {entry.manifestHash && (
                <div className="flex items-center gap-1 mt-1">
                  <Hash className="w-3 h-3 text-text-muted" />
                  <span className="text-[10px] font-mono text-text-muted">{entry.manifestHash}</span>
                </div>
              )}
            </div>
            <div className="flex items-center gap-1 shrink-0">
              <Clock className="w-3 h-3 text-text-muted" />
              <span className="text-[10px] text-text-muted">
                {new Date(entry.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
              </span>
            </div>
          </div>
        );
      })}
    </div>
  );
}
