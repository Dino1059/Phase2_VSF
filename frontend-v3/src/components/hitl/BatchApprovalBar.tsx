import { useTranslation } from 'react-i18next';
import { CheckCheck, X } from 'lucide-react';
import { useChatStore } from '../../stores/chatStore';

export function BatchApprovalBar() {
  const { t } = useTranslation('rules');
  const { pendingProposals, updateProposalStatus } = useChatStore();
  const pending = pendingProposals.filter((p) => p.status === 'pending');

  if (pending.length === 0) return null;

  const approveAll = () => {
    pending.forEach((p) => updateProposalStatus(p.id, 'approved'));
  };

  const rejectAll = () => {
    pending.forEach((p) => updateProposalStatus(p.id, 'rejected'));
  };

  return (
    <div className="sticky top-0 z-10 flex items-center justify-between px-4 py-2 bg-agent-rule-proposer/10 border-b border-agent-rule-proposer/20 backdrop-blur-sm">
      <span className="text-xs font-medium text-agent-rule-proposer">
        {t('pending')}: {pending.length}
      </span>
      <div className="flex items-center gap-2">
        <button
          onClick={approveAll}
          className="flex items-center gap-1 px-3 py-1 text-xs font-medium text-white bg-status-success hover:bg-status-success/80 rounded-md transition-colors"
        >
          <CheckCheck className="w-3.5 h-3.5" />
          {t('approveAll', { count: pending.length })}
        </button>
        <button
          onClick={rejectAll}
          className="flex items-center gap-1 px-2 py-1 text-xs font-medium text-status-error hover:bg-status-error/10 rounded-md transition-colors"
        >
          <X className="w-3.5 h-3.5" />
        </button>
      </div>
    </div>
  );
}
