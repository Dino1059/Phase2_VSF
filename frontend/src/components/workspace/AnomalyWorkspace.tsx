import { useTranslation } from 'react-i18next';
import { AlertTriangle, ShieldAlert, TrendingUp, Cpu } from 'lucide-react';
import { useChatStore } from '../../stores/chatStore';

interface AnomalyItem {
  column: string;
  metric: string;
  expected_range: string;
  observed_value: number | string;
  score: number;
  status: 'critical' | 'warning' | 'normal';
}

export function AnomalyWorkspace() {
  const { t } = useTranslation('agents');
  const anomalyData = useChatStore((s) => (s as any).anomalyData || s.workspaceData) as {
    status?: string;
    anomaly_score?: number;
    summary?: string;
    anomalies?: AnomalyItem[];
  } | null;

  const score = anomalyData?.anomaly_score ?? 0.0;
  const anomalies: AnomalyItem[] = anomalyData?.anomalies ?? [];

  return (
    <div className="p-4 space-y-4">
      {/* Header Metrics */}
      <div className="grid grid-cols-3 gap-3">
        <div className="bg-surface border border-border p-3 rounded-lg flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-status-warning/10 text-status-warning flex items-center justify-center shrink-0">
            <AlertTriangle className="w-5 h-5" />
          </div>
          <div>
            <div className="text-[10px] text-text-muted">{t('anomalyDetector')} Score</div>
            <div className="text-lg font-bold text-status-warning">{(score * 100).toFixed(0)}%</div>
          </div>
        </div>
        <div className="bg-surface border border-border p-3 rounded-lg flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-status-error/10 text-status-error flex items-center justify-center shrink-0">
            <ShieldAlert className="w-5 h-5" />
          </div>
          <div>
            <div className="text-[10px] text-text-muted">Detected Outliers</div>
            <div className="text-lg font-bold text-status-error">{anomalies.length}</div>
          </div>
        </div>
        <div className="bg-surface border border-border p-3 rounded-lg flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-agent-orchestrator/10 text-agent-orchestrator flex items-center justify-center shrink-0">
            <Cpu className="w-5 h-5" />
          </div>
          <div>
            <div className="text-[10px] text-text-muted">Detectors Active</div>
            <div className="text-xs font-semibold text-text-primary mt-0.5">Z-Score / IQR / IF</div>
          </div>
        </div>
      </div>

      {/* Summary card */}
      {anomalyData?.summary && (
        <div className="p-3 bg-surface border border-border rounded-lg text-xs text-text-secondary font-mono flex items-center gap-2">
          <TrendingUp className="w-4 h-4 text-status-warning shrink-0" />
          <span>{anomalyData.summary}</span>
        </div>
      )}

      {/* Anomalies Table */}
      <div className="border border-border rounded-lg overflow-hidden">
        <div className="px-3 py-2 bg-surface border-b border-border flex items-center justify-between">
          <span className="text-xs font-semibold text-text-primary">Detected Outliers & Schema Drift</span>
          <span className="text-[10px] text-text-muted font-mono">{anomalies.length} issues identified</span>
        </div>
        {anomalies.length === 0 ? (
          <div className="p-8 text-center text-xs text-text-muted">
            <ShieldAlert className="w-8 h-8 mx-auto mb-2 opacity-40 text-text-muted" />
            <p className="font-medium text-text-secondary">No Live Anomaly Data Available</p>
            <p className="text-[11px] mt-1 text-text-muted">Run profiling or an anomaly scan on a dataset to populate live observations.</p>
          </div>
        ) : (
          <table className="w-full text-xs">
            <thead>
              <tr className="bg-surface/50 border-b border-border text-text-muted font-medium">
                <th className="text-left px-3 py-2">Column</th>
                <th className="text-left px-3 py-2">Metric Check</th>
                <th className="text-left px-3 py-2">Expected Bounds</th>
                <th className="text-right px-3 py-2">Observed</th>
                <th className="text-center px-3 py-2">Severity</th>
              </tr>
            </thead>
            <tbody>
              {anomalies.map((item, idx) => (
                <tr key={idx} className="border-b border-border hover:bg-surface-hover transition-colors">
                  <td className="px-3 py-2 font-mono text-agent-anomaly-detector font-semibold">{item.column}</td>
                  <td className="px-3 py-2 text-text-secondary">{item.metric}</td>
                  <td className="px-3 py-2 font-mono text-text-muted">{item.expected_range}</td>
                  <td className="px-3 py-2 font-mono text-right text-status-error font-semibold">{item.observed_value}</td>
                  <td className="px-3 py-2 text-center">
                    <span className={`px-2 py-0.5 rounded-full text-[10px] font-medium ${
                      item.status === 'critical' ? 'bg-status-error/10 text-status-error' : 'bg-status-warning/10 text-status-warning'
                    }`}>
                      {item.status}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
