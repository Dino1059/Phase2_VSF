import { useTranslation } from 'react-i18next';
import { ShieldCheck, Check, X, Clock } from 'lucide-react';
import { useChatStore } from '../../stores/chatStore';

const STATUS_CONFIG = {
  pending: { icon: Clock, color: 'text-status-warning', bg: 'bg-status-warning/10', label: 'pending' },
  approved: { icon: Check, color: 'text-status-success', bg: 'bg-status-success/10', label: 'approved' },
  rejected: { icon: X, color: 'text-status-error', bg: 'bg-status-error/10', label: 'rejected' },
};

export function RuleWorkspace() {
  const { t } = useTranslation('rules');
  const { pendingProposals } = useChatStore();

  if (pendingProposals.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-text-muted p-8">
        <ShieldCheck className="w-12 h-12 mb-3 opacity-20" />
        <p className="text-sm">{t('title')}</p>
        <p className="text-xs mt-1 opacity-60">Quality rules will appear here for governance review.</p>
      </div>
    );
  }

  const grouped = {
    pending: pendingProposals.filter((r) => r.status === 'pending'),
    approved: pendingProposals.filter((r) => r.status === 'approved'),
    rejected: pendingProposals.filter((r) => r.status === 'rejected'),
  };

  return (
    <div className="p-4 space-y-4">
      {/* Summary counts */}
      <div className="flex gap-3">
        {(['pending', 'approved', 'rejected'] as const).map((status) => {
          const config = STATUS_CONFIG[status];
          const StatusIcon = config.icon;
          return (
            <div key={status} className={`flex items-center gap-2 px-3 py-2 rounded-lg border border-border ${config.bg}`}>
              <StatusIcon className={`w-4 h-4 ${config.color}`} />
              <span className={`text-lg font-semibold ${config.color}`}>{grouped[status].length}</span>
              <span className="text-xs text-text-muted">{t(config.label)}</span>
            </div>
          );
        })}
      </div>

      {/* Rules list */}
      <div className="space-y-2">
        {pendingProposals.map((rule) => {
          const config = STATUS_CONFIG[rule.status];
          const StatusIcon = config.icon;
          return (
            <div key={rule.id} className="flex items-center gap-3 px-3 py-2 bg-surface border border-border rounded-lg hover:bg-surface-hover transition-colors">
              <StatusIcon className={`w-4 h-4 shrink-0 ${config.color}`} />
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-xs font-mono font-semibold text-text-primary">{rule.column}</span>
                  <span className="text-[10px] text-text-muted">{rule.type}</span>
                </div>
                <code className="text-[11px] text-text-secondary font-mono truncate block">{rule.expression}</code>
              </div>
              <span className={`px-2 py-0.5 rounded-full text-[10px] font-medium ${config.bg} ${config.color}`}>
                {t(config.label)}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
