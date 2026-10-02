import type { DashboardData, DashboardDataSource, FindingSeverity, FindingState } from './dashboard-types';
import { apiBridge } from '../api-bridge';

export class LocalCsvDashboardDataSource implements DashboardDataSource {
  async getDashboardData(): Promise<DashboardData> {
    try {
      const overview = await apiBridge.fetchDashboardOverview();
      const quar = await apiBridge.fetchQuarantineRecords({ limit: 10 }).catch(() => ({ records: [] }));

      const recentFindings = (quar.records || []).map((r) => ({
        id: r.quarantine_id,
        title: `Vi phạm cách ly: ${r.violation_reason}`,
        domain: 'Data Integrity & Privacy',
        severity: (r.violation_severity || 'HIGH').toUpperCase() as FindingSeverity,
        status: (r.status === 'REMEDIATED' ? 'CLOSED' : 'OPEN') as FindingState,
        openedAt: r.quarantined_at || new Date().toISOString(),
      }));

      return {
        metrics: {
          total: overview.metrics.total_quarantine + overview.metrics.total_warning,
          resolved: overview.metrics.quarantine_resolved || 0,
          inProgress: overview.metrics.quarantine_open || 0,
          overdue: 0,
        },
        complianceScore: overview.compliance_score || 95,
        controls: [
          { name: 'Pass', value: overview.metrics.total_silver },
          { name: 'Fail', value: overview.metrics.total_quarantine },
          { name: 'Not Evaluated', value: overview.metrics.total_warning },
        ],
        findingsByDomain: [
          { name: 'Data Integrity', value: overview.metrics.total_quarantine },
          { name: 'Statistical Distribution', value: overview.metrics.total_warning },
        ],
        complianceTrend: [
          { date: '10-01', score: 94 },
          { date: '10-02', score: overview.compliance_score || 96 },
        ],
        recentFindings,
        generatedAt: new Date().toISOString(),
      };
    } catch (e) {
      console.warn('Failed to load live dashboard overview:', e);
      return {
        metrics: { total: 0, resolved: 0, inProgress: 0, overdue: 0 },
        complianceScore: 100,
        controls: [],
        findingsByDomain: [],
        complianceTrend: [],
        recentFindings: [],
        generatedAt: new Date().toISOString(),
      };
    }
  }
}

export const dashboardDataSource: DashboardDataSource = new LocalCsvDashboardDataSource();
