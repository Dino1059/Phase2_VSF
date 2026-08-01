import { useTranslation } from 'react-i18next';
import { Check, X, Pencil, ShieldCheck, AlertTriangle, Info } from 'lucide-react';
import { useChatStore } from '../../stores/chatStore';
import type { RuleProposal } from '../../types';

const SEVERITY_CONFIG = {
  critical: { icon: AlertTriangle, color: 'text-status-error', bg: 'bg-status-error/10' },
  warning: { icon: AlertTriangle, color: 'text-status-warning', bg: 'bg-status-warning/10' },
  info: { icon: Info, color: 'text-status-info', bg: 'bg-status-info/10' },
};

export function RuleProposalCard({ proposal }: { proposal: RuleProposal }) {
  const { t } = useTranslation('rules');
  const updateProposalStatus = useChatStore((s) => s.updateProposalStatus);
  const sevKey = (proposal.severity || 'warning').toLowerCase();
  const severity = SEVERITY_CONFIG[sevKey as keyof typeof SEVERITY_CONFIG] || SEVERITY_CONFIG.warning;
  const SeverityIcon = severity.icon;

  if (proposal.status !== 'pending') {
    return (
      <div className={`flex items-center gap-2 px-3 py-2 rounded-lg text-xs ${
        proposal.status === 'approved' ? 'bg-status-success/10 text-status-success' : 'bg-status-error/10 text-status-error'
      }`}>
        {proposal.status === 'approved' ? <Check className="w-3.5 h-3.5" /> : <X className="w-3.5 h-3.5" />}
        <span className="font-mono">{proposal.column}</span>
        <span className="opacity-60">—</span>
        <span>{proposal.status === 'approved' ? t('approvedSuccess') : t('rejectedSuccess')}</span>
      </div>
    );
  }

  return (
    <div className="border border-border rounded-lg bg-surface overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-border">
        <div className="flex items-center gap-2">
          <ShieldCheck className="w-4 h-4 text-agent-rule-proposer" />
          <span className="text-xs font-semibold text-text-primary">{proposal.column}</span>
          <span className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium ${severity.bg} ${severity.color}`}>
            <SeverityIcon className="w-3 h-3" />
            {t(proposal.severity)}
          </span>
        </div>
        <span className="text-[10px] text-text-muted font-mono">{proposal.type}</span>
      </div>

      {/* Body */}
      <div className="px-3 py-2 space-y-1">
        <p className="text-xs text-text-secondary">{proposal.description}</p>
        <code className="block text-[11px] text-agent-rule-proposer bg-background px-2 py-1 rounded font-mono">
          {proposal.expression}
        </code>
      </div>

      {/* Actions */}
      <div className="flex items-center gap-2 px-3 py-2 border-t border-border bg-background">
        <button
          onClick={() => updateProposalStatus(proposal.id, 'approved')}
          className="flex items-center gap-1 px-3 py-1.5 text-xs font-medium text-white bg-status-success hover:bg-status-success/80 rounded-md transition-colors"
        >
          <Check className="w-3.5 h-3.5" />
          {t('approve')}
        </button>
        <button
          onClick={() => updateProposalStatus(proposal.id, 'rejected')}
          className="flex items-center gap-1 px-3 py-1.5 text-xs font-medium text-status-error hover:bg-status-error/10 rounded-md transition-colors"
        >
          <X className="w-3.5 h-3.5" />
          {t('reject')}
        </button>
        <button className="flex items-center gap-1 px-3 py-1.5 text-xs font-medium text-text-secondary hover:bg-surface-hover rounded-md transition-colors ml-auto">
          <Pencil className="w-3.5 h-3.5" />
          {t('edit')}
        </button>
      </div>
    </div>
  );
}
