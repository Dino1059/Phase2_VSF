import { create } from 'zustand';
import { dashboardApi } from '../services/api';

export interface DashboardMetrics {
  totalAnomalies: number;
  anomalyRate: string;
  avgResolutionTime: string;
  cleanRecords: number;
  quarantinedRecords: number;
  passValidationRate: string;
  rulesExecuted: number;
  latestLedgerHash: string;
}

export interface DiagnosisInsight {
  id: string;
  title: string;
  confidence: string;
  rootCause: string;
  recommendedAction: string;
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
  loading: boolean;

  fetchDashboardData: () => Promise<void>;
}

export const useDashboardStore = create<DashboardState>((set) => ({
  metrics: {
    totalAnomalies: 412,
    anomalyRate: '0.03%',
    avgResolutionTime: '1.4 min',
    cleanRecords: 1248500,
    quarantinedRecords: 412,
    passValidationRate: '99.96%',
    rulesExecuted: 142,
    latestLedgerHash: '0x8f3a9e21b77c3094d1f2e864aa9124bb',
  },
  insights: [
    {
      id: 'rca-1',
      title: 'Connector Thermal Overheat Spike',
      confidence: '98.6%',
      rootCause: 'Grid harmonic distortion on Landmark 81 Charging Hub caused Connector Latch Voltage drop.',
      recommendedAction: 'Apply Rule #R-8091 to quarantine affected session logs & dispatch maintenance flag.',
    },
    {
      id: 'rca-2',
      title: 'BMS Cell Imbalance Delta',
      confidence: '94.2%',
      rootCause: 'Firmware v3.4 thermal offset calculation drift during DC fast charge cycle.',
      recommendedAction: 'Filter outlier pack telemetry and push firmware telemetry sync patch.',
    },
  ],
  activityFeed: [
    { id: '1', icon: 'user-check', color: 'purple', title: 'Steward Approved 2 Rules', time: '2 mins ago' },
    { id: '2', icon: 'microchip', color: 'danger', title: 'Diagnosis Agent completed RCA', time: '8 mins ago' },
    { id: '3', icon: 'exclamation-triangle', color: 'warning', title: 'Anomaly Detector found 189 anomalies', time: '15 mins ago' },
    { id: '4', icon: 'robot', color: 'primary', title: 'Rule Proposer generated 3 rules', time: '22 mins ago' },
    { id: '5', icon: 'chart-bar', color: 'green', title: 'Data Profiler completed analysis', time: '30 mins ago' },
  ],
  loading: false,

  fetchDashboardData: async () => {
    set({ loading: true });
    try {
      const data = await dashboardApi.getStats();
      if (data) {
        set((state) => ({
          metrics: data.metrics ? { ...state.metrics, ...data.metrics } : state.metrics,
          insights: data.insights && data.insights.length > 0 ? data.insights : state.insights,
          activityFeed: data.activityFeed && data.activityFeed.length > 0 ? data.activityFeed : state.activityFeed,
        }));
      }
    } catch (err) {
      console.warn('Dashboard stats backend sync warning:', err);
    } finally {
      set({ loading: false });
    }
  },
}));
