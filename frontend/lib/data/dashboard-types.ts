export type FindingSeverity = 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW';
export type FindingState = 'OPEN' | 'IN_REVIEW' | 'REMEDIATED' | 'CLOSED';

export interface RecentFinding {
  id: string;
  title: string;
  domain: string;
  severity: FindingSeverity;
  status: FindingState;
  openedAt: string;
}

export interface DashboardData {
  metrics: { total: number; resolved: number; inProgress: number; overdue: number };
  complianceScore: number;
  controls: Array<{ name: 'Pass' | 'Fail' | 'Not Evaluated'; value: number }>;
  findingsByDomain: Array<{ name: string; value: number }>;
  complianceTrend: Array<{ date: string; score: number }>;
  recentFindings: RecentFinding[];
  generatedAt: string;
}

export interface DashboardDataSource {
  getDashboardData(): Promise<DashboardData>;
}
