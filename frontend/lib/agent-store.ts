import { create } from 'zustand';

export interface ProposedRule {
  id: string;
  name: string;
  expression: string;
  rationale: string;
  domain: 'Data Quality' | 'Privacy & Data Protection' | 'ITGC & Evidence';
  severity: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW';
  status: 'pending' | 'approved' | 'rejected';
  confidence: number;
  affectedRows: number;
  evidenceId: string;
  passRows: number;
  quarantineRows: number;
  compiledTarget: string;
  lawRef: string;
  approvedAt?: string;
  approvedBy?: string;
}

export interface DatasetItem {
  id: string;
  name: string;
  title: string;
  records: number;
  anomalies: number;
  proposedRulesCount: number;
  proposedRules: ProposedRule[];
}

export interface AgentStep {
  id: number;
  title: string;
  desc: string;
  status: 'done' | 'running' | 'pending';
}

export interface AgentStoreState {
  selectedDatasetId: string;
  agentStatus: 'idle' | 'running' | 'completed';
  stepIndex: number;
  datasets: Record<string, DatasetItem>;
  steps: AgentStep[];
  selectDataset: (id: string) => void;
  runAgent: () => void;
  approveRule: (ruleId: string) => void;
  rejectRule: (ruleId: string) => void;
  updateRuleExpression: (ruleId: string, expr: string) => void;
  getPendingRulesCount: () => number;
}

const initialDatasets: Record<string, DatasetItem> = {
  trips: {
    id: 'trips',
    name: 'Chuyến đi đa quốc gia · trips',
    title: 'Chuyến đi đa quốc gia',
    records: 12480,
    anomalies: 18,
    proposedRulesCount: 2,
    proposedRules: [
      {
        id: 'RULE-TRIP-01',
        name: 'trip_fare_and_distance_positive',
        expression: 'fare_amount >= 0 AND trip_distance_km > 0',
        rationale: 'Phát hiện 11 chuyến đi có cước âm hoặc cự ly bằng 0 (bất thường phát hiện đa tầng L1/L3 residual).',
        domain: 'Data Quality',
        severity: 'CRITICAL',
        status: 'pending',
        confidence: 98,
        affectedRows: 11,
        evidenceId: 'EVID-TRIP-VAL-01',
        passRows: 12469,
        quarantineRows: 11,
        compiledTarget: 'SQL / PySpark Quarantine Lane',
        lawRef: 'IPO Control DQ-01: Valid Revenue Recognition',
      },
      {
        id: 'RULE-TRIP-02',
        name: 'customer_phone_masking',
        expression: 'mask_phone(customer_phone) WHEN role != "Admin"',
        rationale: 'Phát hiện 7 bản ghi chuyến đi ghi nhận số điện thoại khách hàng dạng cleartext ở môi trường telemetry.',
        domain: 'Privacy & Data Protection',
        severity: 'HIGH',
        status: 'pending',
        confidence: 95,
        affectedRows: 7,
        evidenceId: 'EVID-PII-TRIP-02',
        passRows: 12473,
        quarantineRows: 7,
        compiledTarget: 'Dynamic Masking Engine',
        lawRef: 'GDPR Art. 5(1)(c) & Decree 13/2023/ND-CP',
      },
    ],
  },
  customers: {
    id: 'customers',
    name: 'Khách hàng toàn cầu · customers',
    title: 'Khách hàng toàn cầu',
    records: 10000,
    anomalies: 14,
    proposedRulesCount: 2,
    proposedRules: [
      {
        id: 'RULE-CUST-01',
        name: 'citizen_id_format_check',
        expression: 'length(citizen_id) IN (9, 12) AND is_numeric(citizen_id)',
        rationale: 'Phát hiện 8 số CCCD/ID khách hàng bị sai định dạng ký tự hoặc độ dài không hợp lệ.',
        domain: 'Data Quality',
        severity: 'HIGH',
        status: 'pending',
        confidence: 94,
        affectedRows: 8,
        evidenceId: 'EVID-CUST-01',
        passRows: 9992,
        quarantineRows: 8,
        compiledTarget: 'SQL Schema Checker',
        lawRef: 'IPO Control KYC-02',
      },
      {
        id: 'RULE-CUST-02',
        name: 'email_domain_whitelist',
        expression: 'email LIKE "%@%.%" AND email NOT LIKE "%@tempmail.%"',
        rationale: 'Phát hiện 6 tài khoản đăng ký bằng disposable email trong đợt chiến dịch V35.',
        domain: 'Data Quality',
        severity: 'MEDIUM',
        status: 'pending',
        confidence: 91,
        affectedRows: 6,
        evidenceId: 'EVID-CUST-02',
        passRows: 9994,
        quarantineRows: 6,
        compiledTarget: 'Ingestion Filter Gate',
        lawRef: 'Fraud Prevention Policy v2',
      },
    ],
  },
  drivers: {
    id: 'drivers',
    name: 'Tài xế & Đội xe · drivers',
    title: 'Tài xế & Đội xe',
    records: 1200,
    anomalies: 6,
    proposedRulesCount: 1,
    proposedRules: [
      {
        id: 'RULE-DRV-01',
        name: 'driver_license_expiration',
        expression: 'license_expiry_date > CURRENT_DATE()',
        rationale: 'Phát hiện 6 bằng lái của tài xế sắp hết hạn trong vòng 7 ngày nhưng vẫn mở ca.',
        domain: 'ITGC & Evidence',
        severity: 'CRITICAL',
        status: 'pending',
        confidence: 99,
        affectedRows: 6,
        evidenceId: 'EVID-DRV-01',
        passRows: 1194,
        quarantineRows: 6,
        compiledTarget: 'Daily Dispatch Gate',
        lawRef: 'GSM Transport Safety Standard',
      },
    ],
  },
  charging: {
    id: 'charging',
    name: 'Trạm sạc xe điện · acn_charging',
    title: 'Trạm sạc xe điện',
    records: 2500,
    anomalies: 9,
    proposedRulesCount: 2,
    proposedRules: [
      {
        id: 'RULE-CHG-01',
        name: 'station_temperature_bound',
        expression: 'station_temp_c BETWEEN -10 AND 85',
        rationale: 'Phát hiện 5 điểm sạc có cảm biến báo nhiệt độ đột biến > 92°C (L2 Anomaly Robust Z-score).',
        domain: 'Data Quality',
        severity: 'HIGH',
        status: 'pending',
        confidence: 96,
        affectedRows: 5,
        evidenceId: 'EVID-CHG-01',
        passRows: 2495,
        quarantineRows: 5,
        compiledTarget: 'IoT Ingestion Stream Filter',
        lawRef: 'Hardware Safety Control 08',
      },
      {
        id: 'RULE-CHG-02',
        name: 'power_kw_positive',
        expression: 'power_kw >= 0 AND kwh_consumed >= 0',
        rationale: 'Phát hiện 4 bản ghi điện áp ngược từ trụ sạc sạc nhanh DC.',
        domain: 'Data Quality',
        severity: 'HIGH',
        status: 'pending',
        confidence: 97,
        affectedRows: 4,
        evidenceId: 'EVID-CHG-02',
        passRows: 2496,
        quarantineRows: 4,
        compiledTarget: 'Energy Billing Check',
        lawRef: 'IPO Control Energy-01',
      },
    ],
  },
  telemetry: {
    id: 'telemetry',
    name: 'Viễn thông xe điện · ev_telemetry',
    title: 'Viễn thông xe điện & Pin',
    records: 50000,
    anomalies: 42,
    proposedRulesCount: 2,
    proposedRules: [
      {
        id: 'RULE-TEL-01',
        name: 'battery_soc_range',
        expression: 'battery_soc BETWEEN 0 AND 100',
        rationale: 'Phát hiện 28 gói tin telemetry báo SoC pin âm (-2%) hoặc vượt 104% do lỗi firmware BMS.',
        domain: 'Data Quality',
        severity: 'CRITICAL',
        status: 'pending',
        confidence: 99,
        affectedRows: 28,
        evidenceId: 'EVID-TEL-01',
        passRows: 49972,
        quarantineRows: 28,
        compiledTarget: 'BMS Telemetry Ingestion Gate',
        lawRef: 'Battery Fleet Health Spec 1.4',
      },
      {
        id: 'RULE-TEL-02',
        name: 'gps_coordinate_bounds',
        expression: 'latitude BETWEEN 8.0 AND 24.0 AND longitude BETWEEN 102.0 AND 110.0',
        rationale: 'Phát hiện 14 tọa độ GPS nhận giá trị 0.0, 0.0 (Null Island) khi xe đi vào hầm.',
        domain: 'Data Quality',
        severity: 'MEDIUM',
        status: 'pending',
        confidence: 93,
        affectedRows: 14,
        evidenceId: 'EVID-TEL-02',
        passRows: 49986,
        quarantineRows: 14,
        compiledTarget: 'GeoSpatial Validator',
        lawRef: 'Routing & Fare Accuracy Standard',
      },
    ],
  },
};

const initialSteps: AgentStep[] = [
  { id: 1, title: 'Đọc dữ liệu & profiling', desc: 'Kiểm tra cấu trúc, giá trị thiếu và phân bố dữ liệu', status: 'done' },
  { id: 2, title: 'Phát hiện bất thường', desc: 'Đối chiếu dữ liệu với dấu hiệu bất thường và policy', status: 'done' },
  { id: 3, title: 'Đề xuất rule', desc: 'Soạn điều kiện kiểm tra, phạm vi và căn cứ', status: 'done' },
  { id: 4, title: 'Kiểm tra và tổng hợp kết quả', desc: 'Lưu kết quả, evidence và vấn đề cần theo dõi', status: 'done' },
];

export const useAgentStore = create<AgentStoreState>((set, get) => ({
  selectedDatasetId: 'trips',
  agentStatus: 'completed',
  stepIndex: 4,
  datasets: initialDatasets,
  steps: initialSteps,

  selectDataset: (id: string) => {
    set({
      selectedDatasetId: id,
      agentStatus: 'idle',
      stepIndex: 0,
      steps: [
        { id: 1, title: 'Đọc dữ liệu & profiling', desc: 'Kiểm tra cấu trúc, giá trị thiếu và phân bố dữ liệu', status: 'pending' },
        { id: 2, title: 'Phát hiện bất thường', desc: 'Đối chiếu dữ liệu với dấu hiệu bất thường và policy', status: 'pending' },
        { id: 3, title: 'Đề xuất rule', desc: 'Soạn điều kiện kiểm tra, phạm vi và căn cứ', status: 'pending' },
        { id: 4, title: 'Kiểm tra và tổng hợp kết quả', desc: 'Lưu kết quả, evidence và vấn đề cần theo dõi', status: 'pending' },
      ],
    });
  },

  runAgent: () => {
    set({ agentStatus: 'running', stepIndex: 0 });

    const stepIntervals = [
      { step: 1, delay: 350 },
      { step: 2, delay: 900 },
      { step: 3, delay: 1500 },
      { step: 4, delay: 2100 },
    ];

    stepIntervals.forEach(({ step, delay }) => {
      setTimeout(() => {
        set((state) => ({
          stepIndex: step,
          steps: state.steps.map((s) => {
            if (s.id < step) return { ...s, status: 'done' };
            if (s.id === step) return { ...s, status: 'running' };
            return { ...s, status: 'pending' };
          }),
        }));
      }, delay);
    });

    setTimeout(() => {
      set((state) => ({
        agentStatus: 'completed',
        stepIndex: 4,
        steps: state.steps.map((s) => ({ ...s, status: 'done' })),
      }));
    }, 2700);
  },

  approveRule: (ruleId: string) => {
    set((state) => {
      const currentDs = state.datasets[state.selectedDatasetId];
      if (!currentDs) return state;

      const updatedRules = currentDs.proposedRules.map((r) =>
        r.id === ruleId
          ? { ...r, status: 'approved' as const, approvedAt: new Date().toISOString(), approvedBy: 'Steward (HITL)' }
          : r
      );

      return {
        datasets: {
          ...state.datasets,
          [state.selectedDatasetId]: {
            ...currentDs,
            proposedRules: updatedRules,
          },
        },
      };
    });
  },

  rejectRule: (ruleId: string) => {
    set((state) => {
      const currentDs = state.datasets[state.selectedDatasetId];
      if (!currentDs) return state;

      const updatedRules = currentDs.proposedRules.map((r) =>
        r.id === ruleId ? { ...r, status: 'rejected' as const } : r
      );

      return {
        datasets: {
          ...state.datasets,
          [state.selectedDatasetId]: {
            ...currentDs,
            proposedRules: updatedRules,
          },
        },
      };
    });
  },

  updateRuleExpression: (ruleId: string, expr: string) => {
    set((state) => {
      const currentDs = state.datasets[state.selectedDatasetId];
      if (!currentDs) return state;

      const updatedRules = currentDs.proposedRules.map((r) =>
        r.id === ruleId ? { ...r, expression: expr } : r
      );

      return {
        datasets: {
          ...state.datasets,
          [state.selectedDatasetId]: {
            ...currentDs,
            proposedRules: updatedRules,
          },
        },
      };
    });
  },

  getPendingRulesCount: () => {
    const state = get();
    let count = 0;
    Object.values(state.datasets).forEach((ds) => {
      count += ds.proposedRules.filter((r) => r.status === 'pending').length;
    });
    return count;
  },
}));
