import { useTranslation } from 'react-i18next';
import { CheckCircle, XCircle } from 'lucide-react';

interface Props {
  approved: number;
  rejected: number;
  total: number;
}

export function ApprovalSummary({ approved, rejected, total }: Props) {
  const { t } = useTranslation('rules');

  return (
    <div className="flex items-center gap-4 px-4 py-3 bg-surface border border-border rounded-lg">
      <div className="flex items-center gap-1.5 text-status-success">
        <CheckCircle className="w-4 h-4" />
        <span className="text-sm font-medium">{approved}</span>
        <span className="text-xs text-text-muted">{t('approved')}</span>
      </div>
      {rejected > 0 && (
        <div className="flex items-center gap-1.5 text-status-error">
          <XCircle className="w-4 h-4" />
          <span className="text-sm font-medium">{rejected}</span>
          <span className="text-xs text-text-muted">{t('rejected')}</span>
        </div>
      )}
      <span className="text-xs text-text-muted ml-auto">
        {approved + rejected}/{total}
      </span>
    </div>
  );
}
