import { create } from 'zustand';
import { dashboardApi, signalsApi, incidentsApi, auditApi, SignalInfo, IncidentInfo, AuditEntry } from '../services/api';

export interface DashboardMetrics {
  totalAnomalies: number;
  anomalyRate: string;
  avgResolutionTime: string;
  cleanRecords: number;
  quarantinedRecords: number;
  passValidationRate: string;
  rulesExecuted: number;
  latestLedgerHash: string;
  activeIncidentsCount: number;
}

export interface DiagnosisInsight {
  id: string;
  title: string;
  confidence: string;
  rootCause: string;
  recommendedAction: string;
  severity: string;
}

export interface ActivityFeedItem {
  id: string;
  icon: string;
  color: 'purple' | 'danger' | 'warning' | 'primary' | 'green';
  title: string;
  time: string;
}

interface DashboardState {
  metrics: DashboardMetrics;
  insights: DiagnosisInsight[];
  activityFeed: ActivityFeedItem[];
  signals: SignalInfo[];
  incidents: IncidentInfo[];
  auditLogs: AuditEntry[];
  loading: boolean;

  fetchDashboardData: () => Promise<void>;
}

export const useDashboardStore = create<DashboardState>((set) => ({
  metrics: {
    totalAnomalies: 0,
    anomalyRate: '0.00%',
    avgResolutionTime: '< 1 min',
    cleanRecords: 0,
    quarantinedRecords: 0,
    passValidationRate: '100.0%',
    rulesExecuted: 0,
    latestLedgerHash: '0x00000000000000000000000000000000',
    activeIncidentsCount: 0,
  },
  insights: [],
  activityFeed: [],
  signals: [],
  incidents: [],
  auditLogs: [],
  loading: false,

  fetchDashboardData: async () => {
    set({ loading: true });
    try {
      const [statsRes, signalsRes, incidentsRes, auditRes] = await Promise.allSettled([
        dashboardApi.getStats(),
        signalsApi.list('proj-vingroup-pilot'),
        incidentsApi.list('proj-vingroup-pilot'),
        auditApi.list(20),
      ]);

      const stats = statsRes.status === 'fulfilled' ? statsRes.value : {};
      const signals = signalsRes.status === 'fulfilled' ? signalsRes.value : [];
      const incidents = incidentsRes.status === 'fulfilled' ? incidentsRes.value : [];
      const auditLogs = auditRes.status === 'fulfilled' ? auditRes.value : [];

      const totalDataRecords = stats.total_data_records || 0;
      const quarantinedCount = stats.quarantined || 0;
      const totalAnomaliesCount = signals.length > 0 ? signals.length : quarantinedCount;
      const anomalyRateCalc = totalDataRecords > 0
        ? ((totalAnomaliesCount / totalDataRecords) * 100).toFixed(2) + '%'
        : (totalAnomaliesCount > 0 ? `${totalAnomaliesCount} detected` : '0.00%');
      
      const cleanRecordsCalc = Math.max(0, totalDataRecords - quarantinedCount);
      const qualityScoreCalc = stats.quality_score !== undefined ? `${stats.quality_score}%` : '100.0%';
      const rulesExecutedCalc = stats.rule_stats
        ? Object.values(stats.rule_stats).reduce((a, b) => a + b, 0)
        : (stats.tables?.quality_rules || 0);

      const latestHash = (auditLogs.length > 0 && auditLogs[0].event_hash)
        ? auditLogs[0].event_hash
        : (stats.tables?.audit_log ? `0x${stats.tables.audit_log.toString(16).padStart(32, '0')}` : '0x00000000000000000000000000000000');

      const activeIncidents = incidents.filter((i) => i.status !== 'CLOSED' && i.status !== 'RESOLVED');

      const formattedInsights: DiagnosisInsight[] = incidents.map((inc) => ({
        id: inc.incident_id,
        title: inc.admission_reason || `Incident ${inc.incident_id}`,
        confidence: `Severity: ${inc.severity || 'MEDIUM'}`,
        rootCause: `Entity Targets: ${inc.entity_ids?.join(', ') || 'N/A'} | Signals: ${inc.signal_ids?.join(', ') || 'None'}`,
        recommendedAction: `Status: ${inc.status}. Execute automated investigation (R0/C1/A1) or trigger control.`,
        severity: inc.severity || 'MEDIUM',
      }));

      const formattedActivityFeed: ActivityFeedItem[] = auditLogs.map((entry) => ({
        id: entry.id,
        icon: entry.action.includes('RULE') ? 'user-check' : entry.action.includes('INCIDENT') ? 'exclamation-triangle' : 'microchip',
        color: entry.action.includes('INCIDENT') ? 'danger' : entry.action.includes('RULE') ? 'purple' : 'primary',
        title: `${entry.actor || 'System'} - ${entry.action} on ${entry.target_table || 'system'}`,
        time: entry.timestamp ? new Date(entry.timestamp).toLocaleTimeString() : 'Just now',
      }));

      set({
        metrics: {
          totalAnomalies: totalAnomaliesCount,
          anomalyRate: anomalyRateCalc,
          avgResolutionTime: '< 1 min',
          cleanRecords: cleanRecordsCalc,
          quarantinedRecords: quarantinedCount,
          passValidationRate: qualityScoreCalc,
          rulesExecuted: rulesExecutedCalc,
          latestLedgerHash: latestHash,
          activeIncidentsCount: activeIncidents.length,
        },
        insights: formattedInsights,
        activityFeed: formattedActivityFeed,
        signals,
        incidents,
        auditLogs,
      });
    } catch (err) {
      console.warn('Dashboard stats backend sync error:', err);
    } finally {
      set({ loading: false });
    }
  },
}));

