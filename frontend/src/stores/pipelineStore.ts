import { create } from 'zustand';
import type {
  DomainId,
  DomainInfo,
  PipelineStepId,
  PipelineStepDef,
  StepStatus,
  PipelineRunStatus,
  TimeFilter,
  TimeFilterSnapshot,
  SplitRow,
  RuleProposalBackend,
} from '../types';

// ── Static domain models (ported from ui_temp DOMAINS_DATA) ───────────────
export const DOMAINS: Record<DomainId, DomainInfo> = {
  ev_telemetry: {
    id: 'ev_telemetry',
    shortcut: 'ev',
    name: 'VinFast EV Telemetry',
    dbName: 'vinfast_ev_telemetry_v4',
    table: 'telemetry_pack_bms_v4',
    rows: '1,248,912,400',
    size: '4.2 TB',
    engine: 'ClickHouse / Trino',
    topic: 'ev-bms-stream',
    cleanRows: 1248500,
    quarantineRows: 412,
    anomalySummary: 'Thermal runaway risk detected on Pack ID #VF8-BMS-9941 (Temp > 64.2°C, Voltage Delta 0.48V)',
    defaultRule: 'IF battery_temp > 62.0 AND cell_voltage_delta > 0.40 THEN QUARANTINE(\'THERMAL_RUNAWAY_RISK\')',
  },
  vgreen_charging: {
    id: 'vgreen_charging',
    shortcut: 'vgreen',
    name: 'V-GREEN Charging',
    dbName: 'vgreen_charging_logs_db',
    table: 'charging_station_sessions_v2',
    rows: '348,110,900',
    size: '1.1 TB',
    engine: 'PostgreSQL / Timescale',
    topic: 'vgreen-grid-telemetry',
    cleanRows: 347950,
    quarantineRows: 160,
    anomalySummary: 'Grid harmonic distortion spike on Landmark 81 Charging Hub (Station #VG-H81-04)',
    defaultRule: 'IF connector_temp > 75.0 OR grid_pf < 0.88 THEN QUARANTINE(\'CONNECTOR_OVERHEAT\')',
  },
  xanhsm_trips: {
    id: 'xanhsm_trips',
    shortcut: 'xanhsm',
    name: 'Xanh SM Trips',
    dbName: 'xanhsm_trip_telemetry_db',
    table: 'driver_trips_telemetry',
    rows: '890,442,100',
    size: '2.8 TB',
    engine: 'ClickHouse',
    topic: 'xanhsm-fleet-stream',
    cleanRows: 890100,
    quarantineRows: 342,
    anomalySummary: 'Unusual kWh depletion rate vs GPS trajectory on Route SG-NB-92',
    defaultRule: 'IF energy_consumption_per_km > 0.35 AND avg_speed < 15 THEN QUARANTINE(\'ODOMETER_DESYNC\')',
  },
  customer_nlp: {
    id: 'customer_nlp',
    shortcut: 'nlp',
    name: 'Customer Feedback NLP',
    dbName: 'vin_feedback_nlp_db',
    table: 'app_reviews_sentiment_vector',
    rows: '52,100,000',
    size: '420 GB',
    engine: 'Milvus / PGVector',
    topic: 'vin-nlp-feedback',
    cleanRows: 52080,
    quarantineRows: 20,
    anomalySummary: 'Cluster spike in safety-related NLP keyword \'charging port click freeze\'',
    defaultRule: 'IF sentiment_score < -0.85 AND contains(safety_keywords) THEN QUARANTINE(\'CRITICAL_SAFETY_FEEDBACK\')',
  },
};

export const DOMAIN_LIST: DomainInfo[] = Object.values(DOMAINS);

export function normalizeDomainId(alias: string): DomainId {
  const match = DOMAIN_LIST.find((d) => d.shortcut === alias || d.id === alias);
  return match ? match.id : 'ev_telemetry';
}

export function domainToBackendKey(domain: DomainInfo): string {
  // Map mock domain names to real registered dataset keys on the backend.
  const map: Record<DomainId, string> = {
    ev_telemetry: 'vinfast_ev_telemetry_dirty',
    vgreen_charging: 'vgreen_charging_stations_dirty',
    xanhsm_trips: 'xanh_sm_trips_dirty',
    customer_nlp: 'xanh_sm_customer_feedback_dirty',
  };
  return map[domain.id];
}

// ── Pipeline steps (ported from ui_temp STEPS) ────────────────────────────
export const PIPELINE_STEPS: PipelineStepDef[] = [
  { id: 1, name: 'Read Metadata', agent: 'orchestrator', tab: 'tab-manifest', desc: 'Ingests ClickHouse catalog table metadata, checks database schemas & Kafka streaming topics.' },
  { id: 2, name: 'Profile Dataset', agent: 'profiler', tab: 'tab-manifest', desc: 'Computes statistical distributions, null ratios, thermal averages, and voltage delta variance across all data rows.' },
  { id: 3, name: 'Detect Anomalies', agent: 'anomaly', tab: 'tab-telemetry', desc: 'Runs Isolation Forest & Z-Score anomaly detection algorithm to flag out-of-bound sensor records.' },
  { id: 4, name: 'Proposing Rules', agent: 'proposer', tab: 'tab-rca', desc: 'Synthesizes SQL/Python cleaning rules and submits to Governance Review Checkpoint.' },
  { id: 5, name: 'Waiting Human Review', agent: 'human', tab: 'tab-rca', isReviewStep: true, desc: 'Human-in-the-Loop checkpoint. Auto-pauses pipeline until Steward approves or edits rule conditions.' },
  { id: 6, name: 'Generate Tests', agent: 'executor', tab: 'tab-split', desc: 'Synthesizes 125 dynamic Pytest integration assertion test suites to verify rule accuracy.' },
  { id: 7, name: 'Execute Pipeline', agent: 'executor', tab: 'tab-manifest', desc: 'Applies cleaning rules, routes clean/quarantine records, and locks SHA-256 Merkle Audit Manifest.' },
];

// Time filter snapshots (historical audit data for the stream pills)
export const TIME_FILTERS: Record<TimeFilter, TimeFilterSnapshot> = {
  'Today': { date: 'Aug 04, 2026 (Live)', quarantineCount: 412, cleanCount: 1248500, hash: '0x8f3a9e21b77c3094d1f2e864aa9124bb', pytestPass: '125 / 125' },
  '3d': { date: 'Aug 01, 2026 (Historical)', quarantineCount: 189, cleanCount: 1241100, hash: '0x3b1c9902e88a104f77c2e011ee4911aa', pytestPass: '125 / 125' },
  '7d': { date: 'Jul 28, 2026 (Historical)', quarantineCount: 94, cleanCount: 1235000, hash: '0x11ff88ab664192003c2100df66bc9921', pytestPass: '125 / 125' },
  'This Week': { date: 'Jul 28 - Aug 04, 2026 (Cumulative)', quarantineCount: 840, cleanCount: 1248500, hash: '0x9922aacc551100ff8844cc2211bb3388', pytestPass: '125 / 125' },
  'This Month': { date: 'August 2026 (Month-to-Date)', quarantineCount: 1420, cleanCount: 1248500, hash: '0xfe99882211aacc445500998811223344', pytestPass: '125 / 125' },
};

// ── Pipeline zustand store ────────────────────────────────────────────────
interface PipelineState {
  domainId: DomainId;
  currentStepIndex: number;
  stepStatuses: Record<PipelineStepId, StepStatus>;
  runStatus: PipelineRunStatus;
  runId: string | null;
  timeFilter: TimeFilter;
  activeSplitView: 'clean' | 'quarantine';
  activeRightTab: 'tab-rca' | 'tab-telemetry' | 'tab-split' | 'tab-manifest';
  currentRuleLogic: string;
  ruleStatus: 'pending' | 'accepted' | 'rejected';
  proposals: RuleProposalBackend[];
  cleanRows: number;
  quarantineRows: number;
  manifestHash: string;
  domainError: string | null;

  setDomain: (domainId: DomainId) => void;
  setStepIndex: (idx: number) => void;
  setStepStatus: (id: PipelineStepId, status: StepStatus) => void;
  setRunStatus: (status: PipelineRunStatus) => void;
  setRunId: (runId: string | null) => void;
  setTimeFilter: (filter: TimeFilter) => void;
  setSplitView: (view: 'clean' | 'quarantine') => void;
  setRightTab: (tab: PipelineState['activeRightTab']) => void;
  setRuleLogic: (logic: string) => void;
  setRuleStatus: (status: 'pending' | 'accepted' | 'rejected') => void;
  setProposals: (proposals: RuleProposalBackend[]) => void;
  setCounts: (clean: number, quarantine: number) => void;
  setManifestHash: (hash: string) => void;
  setDomainError: (error: string | null) => void;
  resetPipeline: () => void;
}

export const usePipelineStore = create<PipelineState>((set) => ({
  domainId: 'ev_telemetry',
  currentStepIndex: 0,
  stepStatuses: {
    1: 'pending', 2: 'pending', 3: 'pending', 4: 'pending', 5: 'pending', 6: 'pending', 7: 'pending',
  },
  runStatus: 'idle',
  runId: null,
  timeFilter: 'Today',
  activeSplitView: 'clean',
  activeRightTab: 'tab-rca',
  currentRuleLogic: DOMAINS.ev_telemetry.defaultRule,
  ruleStatus: 'pending',
  proposals: [],
  cleanRows: DOMAINS.ev_telemetry.cleanRows,
  quarantineRows: DOMAINS.ev_telemetry.quarantineRows,
  manifestHash: TIME_FILTERS['Today'].hash,
  domainError: null,

  setDomain: (domainId) =>
    set((state) => {
      const domain = DOMAINS[domainId];
      return {
        domainId,
        currentRuleLogic: domain.defaultRule,
        ruleStatus: 'pending',
        currentStepIndex: 0,
        runStatus: 'idle',
        runId: null,
        cleanRows: domain.cleanRows,
        quarantineRows: domain.quarantineRows,
        proposals: [],
        domainError: null,
        stepStatuses: {
          1: 'pending', 2: 'pending', 3: 'pending', 4: 'pending', 5: 'pending', 6: 'pending', 7: 'pending',
        },
        ...(state.activeRightTab ? {} : {}),
      };
    }),
  setStepIndex: (currentStepIndex) => set({ currentStepIndex }),
  setStepStatus: (id, status) =>
    set((state) => ({ stepStatuses: { ...state.stepStatuses, [id]: status } })),
  setRunStatus: (runStatus) => set({ runStatus }),
  setRunId: (runId) => set({ runId }),
  setTimeFilter: (timeFilter) => set({ timeFilter }),
  setSplitView: (activeSplitView) => set({ activeSplitView }),
  setRightTab: (activeRightTab) => set({ activeRightTab }),
  setRuleLogic: (currentRuleLogic) => set({ currentRuleLogic }),
  setRuleStatus: (ruleStatus) => set({ ruleStatus }),
  setProposals: (proposals) => set({ proposals }),
  setCounts: (cleanRows, quarantineRows) => set({ cleanRows, quarantineRows }),
  setManifestHash: (manifestHash) => set({ manifestHash }),
  setDomainError: (domainError) => set({ domainError }),
  resetPipeline: () =>
    set((state) => {
      const domain = DOMAINS[state.domainId];
      return {
        currentStepIndex: 0,
        runStatus: 'idle',
        runId: null,
        ruleStatus: 'pending',
        proposals: [],
        cleanRows: domain.cleanRows,
        quarantineRows: domain.quarantineRows,
        manifestHash: TIME_FILTERS['Today'].hash,
        stepStatuses: {
          1: 'pending', 2: 'pending', 3: 'pending', 4: 'pending', 5: 'pending', 6: 'pending', 7: 'pending',
        },
      };
    }),
}));

// Sample split-DB rows (demo fallback when backend quarantine is empty)
export const SPLIT_SAMPLES: Record<DomainId, { clean: SplitRow[]; quarantine: SplitRow[] }> = {
  ev_telemetry: {
    clean: [
      { id: 'EV-100284', timestamp: '02:31:05', vehicleId: 'VF8-VN-8849', battTemp: '32.4°C', vDelta: '0.04V', status: 'CLEAN', code: 'PASS_0' },
      { id: 'EV-100285', timestamp: '02:31:08', vehicleId: 'VF9-VN-9921', battTemp: '34.1°C', vDelta: '0.05V', status: 'CLEAN', code: 'PASS_0' },
      { id: 'EV-100286', timestamp: '02:31:12', vehicleId: 'VF6-VN-1102', battTemp: '31.8°C', vDelta: '0.03V', status: 'CLEAN', code: 'PASS_0' },
      { id: 'EV-100287', timestamp: '02:31:19', vehicleId: 'VF8-VN-4401', battTemp: '33.6°C', vDelta: '0.06V', status: 'CLEAN', code: 'PASS_0' },
      { id: 'EV-100288', timestamp: '02:31:25', vehicleId: 'VF7-VN-7732', battTemp: '32.9°C', vDelta: '0.04V', status: 'CLEAN', code: 'PASS_0' },
    ],
    quarantine: [
      { id: 'EV-ERR-941', timestamp: '02:29:44', vehicleId: 'VF8-VN-9941', battTemp: '64.8°C', vDelta: '0.48V', status: 'QUARANTINED', code: 'TEMP_RUNAWAY_RISK' },
      { id: 'EV-ERR-942', timestamp: '02:28:11', vehicleId: 'VF9-VN-2041', battTemp: '63.2°C', vDelta: '0.42V', status: 'QUARANTINED', code: 'VOLTAGE_SAG_SPIKE' },
      { id: 'EV-ERR-943', timestamp: '02:24:50', vehicleId: 'VF5-VN-0098', battTemp: '66.1°C', vDelta: '0.51V', status: 'QUARANTINED', code: 'CAN_BUS_CORRECTED' },
    ],
  },
  vgreen_charging: {
    clean: [
      { id: 'VG-88102', timestamp: '02:30:10', vehicleId: 'VG-STN-01', battTemp: '38.0°C', vDelta: '0.01V', status: 'CLEAN', code: 'PASS_GRID' },
      { id: 'VG-88103', timestamp: '02:30:45', vehicleId: 'VG-STN-04', battTemp: '41.2°C', vDelta: '0.02V', status: 'CLEAN', code: 'PASS_GRID' },
    ],
    quarantine: [
      { id: 'VG-ERR-04', timestamp: '02:22:15', vehicleId: 'VG-STN-88', battTemp: '78.4°C', vDelta: '0.85V', status: 'QUARANTINED', code: 'CONNECTOR_OVERHEAT' },
    ],
  },
  xanhsm_trips: {
    clean: [
      { id: 'TRIP-7710', timestamp: '02:29:01', vehicleId: 'XSM-DRIVER-44', battTemp: '29.5°C', vDelta: '0.02V', status: 'CLEAN', code: 'PASS_ROUTE' },
    ],
    quarantine: [
      { id: 'TRIP-ERR-99', timestamp: '02:15:00', vehicleId: 'XSM-DRIVER-12', battTemp: '45.0°C', vDelta: '0.33V', status: 'QUARANTINED', code: 'ODOMETER_DESYNC' },
    ],
  },
  customer_nlp: {
    clean: [
      { id: 'NLP-4401', timestamp: '02:28:10', vehicleId: 'USER-9941', battTemp: 'N/A', vDelta: 'N/A', status: 'CLEAN', code: 'POSITIVE_SENTIMENT' },
    ],
    quarantine: [
      { id: 'NLP-ERR-01', timestamp: '02:10:22', vehicleId: 'USER-0012', battTemp: 'N/A', vDelta: 'N/A', status: 'QUARANTINED', code: 'CRITICAL_SAFETY_FEEDBACK' },
    ],
  },
};
