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
  evidenceHash?: string;
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

export interface TestCaseItem {
  id: string;
  code: string;
  name: string;
  domain: 'Data Quality' | 'Privacy PII' | 'ITGC & Security' | 'IoT Telemetry';
  description: string;
  injectedAnomaly: string;
  expectedRule: string;
  lawStandard: string;
  status: 'idle' | 'running' | 'passed' | 'failed';
  evidenceHash?: string;
  executionTimeMs?: number;
  quarantinedCount?: number;
}

export interface PolicyAdaptationItem {
  id: string;
  title: string;
  sourceDoc: string;
  effectiveDate: string;
  rawText: string;
  generatedRuleName: string;
  generatedExpression: string;
  compiledTarget: string;
  confidence: number;
  simulatedImpact: {
    scannedRows: number;
    silverCleanRows: number;
    quarantinedRows: number;
    estimatedLatencyMs: number;
  };
  status: 'draft' | 'simulated' | 'deployed';
}

export interface UserAccount {
  id: 'auditor' | 'admin';
  name: string;
  shortName: string;
  role: string;
  roleTitle: string;
  email: string;
  avatar: string;
  badge: string;
  company: string;
}

export const USER_ACCOUNTS: Record<'auditor' | 'admin', UserAccount> = {
  auditor: {
    id: 'auditor',
    name: 'Trần Minh Hoàng',
    shortName: 'anh Hoàng',
    role: 'Senior Auditor (Big 4 / IPO Assurance)',
    roleTitle: 'Auditor IPO',
    email: 'hoang.tran@audit-ipo.com',
    avatar: 'TH',
    badge: 'Kiểm toán viên IPO',
    company: 'Big 4 Audit Consortium',
  },
  admin: {
    id: 'admin',
    name: 'Nguyễn Quốc Bảo',
    shortName: 'anh Bảo',
    role: 'Lead Data Platform (GSM Global)',
    roleTitle: 'System Admin',
    email: 'bao.nq@gsm.vn',
    avatar: 'QB',
    badge: 'Quản trị viên hệ thống',
    company: 'GSM Global Tech',
  },
};

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
  isChatOpen: boolean;
  openChat: () => void;
  closeChat: () => void;
  toggleChat: () => void;
  chatInitialPrompt: string | null;
  openChatWithPrompt: (prompt: string) => void;
  clearChatInitialPrompt: () => void;
  // Account management
  currentUser: UserAccount;
  switchAccount: (accountId: 'auditor' | 'admin') => void;
  // Persona & Hub Workspace additions
  activePersona: 'auditor' | 'admin' | 'general';
  setActivePersona: (persona: 'auditor' | 'admin' | 'general') => void;
  testCases: TestCaseItem[];
  runTestCase: (testId: string) => Promise<void>;
  runAllTestCases: () => Promise<void>;
  policies: PolicyAdaptationItem[];
  adaptPolicy: (policyId: string) => Promise<void>;
  deployPolicyRule: (policyId: string) => void;
  workspacePreviewTab: 'tests' | 'evidence' | 'telemetry' | 'adaptation';
  setWorkspacePreviewTab: (tab: 'tests' | 'evidence' | 'telemetry' | 'adaptation') => void;
  workspaceInitialMessage: string | null;
  setWorkspaceInitialMessage: (msg: string | null) => void;
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

  isChatOpen: false,
  chatInitialPrompt: null,
  openChat: () => set({ isChatOpen: true }),
  closeChat: () => set({ isChatOpen: false }),
  toggleChat: () => set((state) => ({ isChatOpen: !state.isChatOpen })),
  openChatWithPrompt: (prompt: string) => set({ isChatOpen: true, chatInitialPrompt: prompt }),
  clearChatInitialPrompt: () => set({ chatInitialPrompt: null }),

  // Account management
  currentUser: USER_ACCOUNTS.auditor,
  switchAccount: (accountId) => {
    const acc = USER_ACCOUNTS[accountId];
    set({
      currentUser: acc,
      activePersona: accountId,
      workspacePreviewTab: accountId === 'auditor' ? 'tests' : 'telemetry',
    });
  },

  // Persona & Hub Workspace Implementation
  activePersona: 'auditor',
  setActivePersona: (persona) =>
    set({
      activePersona: persona,
      workspacePreviewTab: persona === 'auditor' ? 'tests' : 'telemetry',
      currentUser: persona === 'admin' ? USER_ACCOUNTS.admin : USER_ACCOUNTS.auditor,
    }),

  workspacePreviewTab: 'tests',
  setWorkspacePreviewTab: (tab) => set({ workspacePreviewTab: tab }),

  workspaceInitialMessage: null,
  setWorkspaceInitialMessage: (msg) => set({ workspaceInitialMessage: msg }),

  testCases: [
    {
      id: 'TC-01',
      code: 'TC-REV-01',
      name: 'Kiểm thử bắt cuốc xe cước 0đ và quãng đường âm',
      domain: 'Data Quality',
      description: 'Bơm 5 cuốc xe giả lập cước phí 0đ và cự ly -2.4km vào stream dữ liệu để xác minh cơ chế cách ly doanh thu ảo.',
      injectedAnomaly: '{ "trip_id": "SIM-TRIP-9901", "fare_amount": 0, "distance_km": -2.4, "status": "COMPLETED" }',
      expectedRule: 'fare_amount > 0 AND distance_km >= 0.1',
      lawStandard: 'IPO Control DQ-01: Valid Revenue Recognition',
      status: 'idle',
      quarantinedCount: 5,
    },
    {
      id: 'TC-02',
      code: 'TC-PII-02',
      name: 'Kiểm thử chặn số CCCD và SĐT không mã hóa AES-256',
      domain: 'Privacy PII',
      description: 'Bơm 10 hồ sơ khách hàng mang số định danh CCCD 12 số dạng plain-text chưa qua che mờ (masking).',
      injectedAnomaly: '{ "cust_id": "SIM-CUST-8812", "citizen_id": "001201012345", "phone": "0912345678", "phone_encrypted": false }',
      expectedRule: 'mask_phone(phone) AND is_encrypted(citizen_id)',
      lawStandard: 'Nghị định 13/2023/NĐ-CP & GDPR Art. 5(1)(c)',
      status: 'idle',
      quarantinedCount: 10,
    },
    {
      id: 'TC-03',
      code: 'TC-CHG-03',
      name: 'Kiểm thử chênh lệch điện năng nạp trụ sạc VinFast',
      domain: 'Data Quality',
      description: 'Bơm 3 phiên sạc có kWh nạp thực tế nhỏ hơn chỉ số công tơ điện chênh lệch vượt ngưỡng an toàn > 5%.',
      injectedAnomaly: '{ "session_id": "SIM-CHG-7721", "meter_delta_kwh": 45.2, "billed_kwh": 52.0, "pole_id": "VF-PL-09" }',
      expectedRule: 'ABS(meter_delta_kwh - billed_kwh) <= 0.5',
      lawStandard: 'GSM EV Asset Control 03 & Audit Revenue Proof',
      status: 'idle',
      quarantinedCount: 3,
    },
    {
      id: 'TC-04',
      code: 'TC-GEO-04',
      name: 'Kiểm thử định vị GPS hành khách ngoài biên giới phục vụ',
      domain: 'Privacy PII',
      description: 'Bơm 4 gói tin tọa độ đón khách có vĩ độ/kinh độ nằm ngoài lãnh thổ 24 thị trường GSM Global.',
      injectedAnomaly: '{ "trip_id": "SIM-GEO-004", "pickup_lat": 82.1124, "pickup_lon": -140.2311 }',
      expectedRule: 'is_within_service_boundary(lat, lon)',
      lawStandard: 'Geographic Compliance & Passenger Safety V35',
      status: 'idle',
      quarantinedCount: 4,
    },
    {
      id: 'TC-05',
      code: 'TC-SEC-05',
      name: 'Kiểm thử chặn tài xế có giấy phép lái xe hết hạn',
      domain: 'ITGC & Security',
      description: 'Bơm 2 hồ sơ tài xế có bằng lái B2 hết hiệu lực từ ngày 15/08/2026 nhưng vẫn nhận lệnh điều phối.',
      injectedAnomaly: '{ "driver_id": "SIM-DRV-441", "license_type": "B2", "license_expiry": "2026-08-15" }',
      expectedRule: 'license_expiry >= CURRENT_DATE AND license_type IN ("B2","D")',
      lawStandard: 'Bộ GTVT Quyết định 28/2024 & SOX ITGC Access Control',
      status: 'idle',
      quarantinedCount: 2,
    },
    {
      id: 'TC-06',
      code: 'TC-IOT-06',
      name: 'Kiểm thử cảnh báo quá nhiệt cell pin xe điện (>65°C)',
      domain: 'IoT Telemetry',
      description: 'Bơm gói tin viễn thông BMS từ xe VF8 gửi thông số nhiệt độ cell pin đạt 72.4°C.',
      injectedAnomaly: '{ "vin": "VF8-VN-99214", "battery_temp_c": 72.4, "soc_pct": 88, "status": "fast_charging" }',
      expectedRule: 'battery_temp_c <= 65.0 AND speed_kmh <= 140',
      lawStandard: 'GSM Fleet Battery Safety Standard L4',
      status: 'idle',
      quarantinedCount: 1,
    },
  ],

  runTestCase: async (testId: string) => {
    set((state) => ({
      testCases: state.testCases.map((tc) =>
        tc.id === testId ? { ...tc, status: 'running' as const } : tc
      ),
    }));

    await new Promise((r) => setTimeout(r, 900));

    const randomHash =
      'sha256:' +
      Array.from({ length: 64 }, () =>
        Math.floor(Math.random() * 16).toString(16)
      ).join('');

    set((state) => ({
      testCases: state.testCases.map((tc) =>
        tc.id === testId
          ? {
              ...tc,
              status: 'passed' as const,
              evidenceHash: randomHash,
              executionTimeMs: Math.floor(Math.random() * 40) + 25,
            }
          : tc
      ),
    }));
  },

  runAllTestCases: async () => {
    set((state) => ({
      testCases: state.testCases.map((tc) => ({ ...tc, status: 'running' as const })),
    }));

    await new Promise((r) => setTimeout(r, 1400));

    set((state) => ({
      testCases: state.testCases.map((tc) => ({
        ...tc,
        status: 'passed' as const,
        evidenceHash:
          'sha256:' +
          Array.from({ length: 64 }, () =>
            Math.floor(Math.random() * 16).toString(16)
          ).join(''),
        executionTimeMs: Math.floor(Math.random() * 35) + 20,
      })),
    }));
  },

  policies: [
    {
      id: 'POL-01',
      title: 'Nghị định 13/2023/NĐ-CP sửa đổi: Bắt buộc mã hóa AES-256 định danh cá nhân trên taxi công nghệ',
      sourceDoc: 'Chính phủ & Bộ Công An · Thông tư hướng dẫn 02/2026/BCA',
      effectiveDate: '01/10/2026',
      rawText: 'Mọi thông tin cá nhân bao gồm số căn cước công dân (CCCD/eID), số điện thoại di động và dữ liệu sinh trắc học của hành khách phải được che mờ (masking) hoặc mã hóa theo chuẩn AES-256 trước khi lưu trữ hoặc truyền qua hệ thống telemetry.',
      generatedRuleName: 'RULE-PII-AUTO-01: mandate_aes256_passenger_identifier',
      generatedExpression: 'is_aes256_encrypted(citizen_id) AND is_masked(phone_number)',
      compiledTarget: 'Dynamic Masking Engine / PySpark Crypto UDF',
      confidence: 99,
      simulatedImpact: {
        scannedRows: 1250000,
        silverCleanRows: 1246580,
        quarantinedRows: 3420,
        estimatedLatencyMs: 14,
      },
      status: 'simulated',
    },
    {
      id: 'POL-02',
      title: 'Chính sách Cước phí Động GSM V35: Cước tối thiểu 1km & Chống cuốc xe ảo gian lận khuyến mãi',
      sourceDoc: 'GSM Global Strategy Directive · Q3/2026',
      effectiveDate: '15/09/2026',
      rawText: 'Tất cả cuốc xe hợp lệ phải có giá cước tối thiểu 14.000 VNĐ và quãng đường di chuyển thực tế từ 0.5km trở lên (hoặc thời gian đón trả trên 2 phút). Các cuốc vi phạm lập tức chuyển sang làn Quarantine để kiểm tra đối soát trước khi ghi nhận doanh thu.',
      generatedRuleName: 'RULE-FRAUD-AUTO-02: minimum_fare_and_distance_threshold',
      generatedExpression: 'fare_amount >= 14000 AND (distance_km >= 0.5 OR trip_duration_sec >= 120)',
      compiledTarget: 'SQL Quarantine Lane / Real-time Flink Job',
      confidence: 97,
      simulatedImpact: {
        scannedRows: 1250000,
        silverCleanRows: 1248760,
        quarantinedRows: 1240,
        estimatedLatencyMs: 8,
      },
      status: 'draft',
    },
    {
      id: 'POL-03',
      title: 'Quy chuẩn Nạp điện Siêu nhanh VinFast V4: Kiểm soát xung điện áp và sai lệch công tơ',
      sourceDoc: 'VinFast Energy Infrastructure Specification V4',
      effectiveDate: '01/08/2026',
      rawText: 'Trụ sạc nhanh công suất đỉnh 250kW-300kW phải duy trì độ lệch giữa công tơ nguồn và điện năng nạp thực tế dưới 3%. Nếu công tơ chỉ số cuối nhỏ hơn chỉ số đầu hoặc kWh delivered âm, ngắt cổng thanh toán và cách ly bản ghi nạp điện.',
      generatedRuleName: 'RULE-CHG-AUTO-03: ultra_charging_meter_tolerance',
      generatedExpression: 'peak_kw <= 300 AND meter_end >= meter_start AND power_loss_ratio < 0.03',
      compiledTarget: 'IoT Streaming Aggregator & Billing Guard',
      confidence: 96,
      simulatedImpact: {
        scannedRows: 3200,
        silverCleanRows: 3144,
        quarantinedRows: 56,
        estimatedLatencyMs: 5,
      },
      status: 'draft',
    },
  ],

  adaptPolicy: async (policyId: string) => {
    await new Promise((r) => setTimeout(r, 700));
    set((state) => ({
      policies: state.policies.map((p) =>
        p.id === policyId ? { ...p, status: 'simulated' as const } : p
      ),
    }));
  },

  deployPolicyRule: (policyId: string) => {
    set((state) => {
      const targetPolicy = state.policies.find((p) => p.id === policyId);
      if (!targetPolicy) return state;

      const updatedPolicies = state.policies.map((p) =>
        p.id === policyId ? { ...p, status: 'deployed' as const } : p
      );

      // Add to proposed rules in trips dataset
      const curDs = state.datasets[state.selectedDatasetId] || state.datasets.trips;
      const newRule: ProposedRule = {
        id: `ADAPT-${targetPolicy.id}`,
        name: targetPolicy.generatedRuleName,
        expression: targetPolicy.generatedExpression,
        rationale: `Tự động thích ứng từ chính sách: ${targetPolicy.title}. Độ tin cậy AI: ${targetPolicy.confidence}%.`,
        domain: targetPolicy.id === 'POL-01' ? 'Privacy & Data Protection' : 'Data Quality',
        severity: 'HIGH',
        status: 'approved',
        confidence: targetPolicy.confidence,
        affectedRows: targetPolicy.simulatedImpact.quarantinedRows,
        evidenceHash: 'ev_adapt_' + Date.now().toString(36),
        evidenceId: 'EVID-ADAPT-' + targetPolicy.id,
        passRows: targetPolicy.simulatedImpact.silverCleanRows,
        quarantineRows: targetPolicy.simulatedImpact.quarantinedRows,
        compiledTarget: targetPolicy.compiledTarget,
        lawRef: targetPolicy.sourceDoc,
        approvedAt: new Date().toISOString(),
        approvedBy: 'System Admin (Auto-Adapt Engine)',
      };

      return {
        policies: updatedPolicies,
        datasets: {
          ...state.datasets,
          [state.selectedDatasetId]: {
            ...curDs,
            proposedRules: [newRule, ...curDs.proposedRules],
          },
        },
      };
    });
  },
}));

