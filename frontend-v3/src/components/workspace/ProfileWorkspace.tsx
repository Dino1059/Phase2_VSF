import { useTranslation } from 'react-i18next';
import { Database } from 'lucide-react';
import { useChatStore } from '../../stores/chatStore';

interface ColumnProfile {
  name: string;
  type: string;
  nullRate: number;
  uniqueRate: number;
  min?: string;
  max?: string;
  mean?: number;
  health: 'healthy' | 'warning' | 'critical';
}

const HEALTH_COLORS = {
  healthy: 'text-status-success bg-status-success/10',
  warning: 'text-status-warning bg-status-warning/10',
  critical: 'text-status-error bg-status-error/10',
};

export function ProfileWorkspace() {
  const { t } = useTranslation('profiler');
  const workspaceData = useChatStore((s) => s.workspaceData) as { columns?: ColumnProfile[]; totalRows?: number } | null;

  const columns = workspaceData?.columns || [];
  const totalRows = workspaceData?.totalRows || 0;

  if (columns.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-text-muted p-8">
        <Database className="w-12 h-12 mb-3 opacity-20" />
        <p className="text-sm">{t('title')}</p>
        <p className="text-xs mt-1 opacity-60">Profile results will appear here when an agent scans a dataset.</p>
      </div>
    );
  }

  return (
    <div className="p-4 space-y-4">
      {/* Summary bar */}
      <div className="flex items-center gap-4 px-4 py-2 bg-surface rounded-lg border border-border">
        <div className="text-xs"><span className="text-text-muted">{t('rows')}:</span> <span className="font-mono text-text-primary">{totalRows.toLocaleString()}</span></div>
        <div className="text-xs"><span className="text-text-muted">{t('columns')}:</span> <span className="font-mono text-text-primary">{columns.length}</span></div>
        <div className="text-xs"><span className="text-text-muted">{t('issues', { count: columns.filter(c => c.health !== 'healthy').length })}</span></div>
      </div>

      {/* Column table */}
      <div className="border border-border rounded-lg overflow-hidden">
        <table className="w-full text-xs">
          <thead>
            <tr className="bg-surface border-b border-border">
              <th className="text-left px-3 py-2 text-text-muted font-medium">Column</th>
              <th className="text-left px-3 py-2 text-text-muted font-medium">{t('dataType')}</th>
              <th className="text-right px-3 py-2 text-text-muted font-medium">{t('nullRate')}</th>
              <th className="text-right px-3 py-2 text-text-muted font-medium">{t('uniqueRate')}</th>
              <th className="text-center px-3 py-2 text-text-muted font-medium">{t('health')}</th>
            </tr>
          </thead>
          <tbody>
            {columns.map((col, i) => (
              <tr key={col.name} className={`border-b border-border hover:bg-surface-hover transition-colors ${i % 2 === 0 ? 'bg-background' : 'bg-surface/30'}`}>
                <td className="px-3 py-2 font-mono text-text-primary">{col.name}</td>
                <td className="px-3 py-2 text-text-secondary">{col.type}</td>
                <td className="px-3 py-2 text-right font-mono">
                  <span className={col.nullRate > 0.1 ? 'text-status-warning' : 'text-text-secondary'}>
                    {(col.nullRate * 100).toFixed(1)}%
                  </span>
                </td>
                <td className="px-3 py-2 text-right font-mono text-text-secondary">{(col.uniqueRate * 100).toFixed(1)}%</td>
                <td className="px-3 py-2 text-center">
                  <span className={`px-2 py-0.5 rounded-full text-[10px] font-medium ${HEALTH_COLORS[col.health]}`}>
                    {t(col.health)}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
