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

export type CaseStatus = 'not_evaluated' | 'running' | 'passed' | 'failed';

export interface FindingItem {
  id: string;
  caseId: string;
  caseCode: string;
  title: string;
  datasetId: string;
  severity: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW';
  status: 'OPEN' | 'IN_REVIEW' | 'AUDITED';
  detectedAt: string;
  // 1. Phân tích nguyên nhân gốc rễ từ AI Agent
  rootCauseAnalysis: string;
  // 2. Bằng chứng thực tế bị bắt
  evidence: {
    hashSha256: string;
    previousHash: string;
    lawReference: string;
    quarantinedCount: number;
    samplePayload: Record<string, any>;
    digitalSignature: string;
  };
  // 3. Đề xuất xử lý từ AI Agent
  aiRemediation: {
    actionPlan: string[];
    proposedRuleName: string;
    proposedExpression: string;
    targetLane: string;
  };
}

export interface ComplianceCaseItem {
  id: string;
  code: string;
  name: string;
  datasetId: 'trips' | 'customers' | 'drivers' | 'charging' | 'telemetry';
  domain: string;
  lawStandard: string;
  description: string;
  expectedControl: string;
  status: CaseStatus;
  executionTimeMs?: number;
  evidenceHash?: string;
  findings: FindingItem[];
}

export interface PolicyItem {
  id: string;
  title: string;
  datasetId: string;
  sourceDoc: string;
  effectiveDate: string;
  rawPolicyText: string;
  aiAnalysisSummary: string;
  generatedRule: {
    name: string;
    expression: string;
    compiledTarget: string;
    confidence: number;
  };
  dryRunSimulation: {
    scannedRows: number;
    silverCleanRows: number;
    quarantinedRows: number;
    estimatedLatencyMs: number;
  };
  status: 'draft' | 'simulated' | 'approved' | 'rejected';
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

export interface ActiveRule {
  id: string;
  name: string;
  expression: string;
  domain: 'Data Quality' | 'Privacy & Data Protection' | 'ITGC & Evidence';
  datasetId: string;
  datasetName: string;
  severity: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW';
  targetLane: string;
  enforcedAt: string;
  enforcedBy: string;
  lawRef: string;
  scannedCount: number;
  quarantinedCount: number;
  engine: string;
  status: 'active' | 'paused';
}

export interface ChatMessageItem {
  id: string;
  sender: 'ai' | 'user';
  text: string;
  timestamp: string;
  quickActions?: { label: string; actionType: string; payload?: any }[];
  highlightRuleId?: string;
}

export type HomepageViewMode = 'welcome' | 'running_pipeline' | 'results_dashboard';

export interface PipelineLevelProgress {
  status: 'idle' | 'running' | 'done';
  progress: number;
  scanned: number;
  passed: number;
  failed: number;
  signalCount: number;
  algorithm: string;
  latencyMs: number;
}

export interface PipelineLevelsState {
  currentLevel: 'L1' | 'L2' | 'L3' | 'L4' | 'COMPLETED' | 'IDLE';
  l1: PipelineLevelProgress;
  l2: PipelineLevelProgress;
  l3: PipelineLevelProgress;
  l4: PipelineLevelProgress;
}

export const initialActiveRules: ActiveRule[] = [
  {
    id: 'ACT-TRIP-01',
    name: 'fare_amount_positive_threshold',
    expression: 'fare_amount > 0 AND trip_distance_km >= 0.1',
    domain: 'Data Quality',
    datasetId: 'trips',
    datasetName: 'trips',
    severity: 'CRITICAL',
    targetLane: 'Quarantine Lane / Ingestion Gate',
    enforcedAt: '2026-09-20T08:30:00Z',
    enforcedBy: 'Trần Minh Hoàng (Auditor IPO)',
    lawRef: 'IFRS 15 / SOX 404 Section 404',
    scannedCount: 12480,
    quarantinedCount: 18,
    engine: 'PySpark / SQL Stream Validator',
    status: 'active',
  },
  {
    id: 'ACT-CUST-01',
    name: 'mask_phone_cleartext_enforcement',
    expression: 'mask_phone(customer_phone) WHEN role != "Admin"',
    domain: 'Privacy & Data Protection',
    datasetId: 'customers',
    datasetName: 'customers',
    severity: 'HIGH',
    targetLane: 'Dynamic Masking Engine',
    enforcedAt: '2026-09-21T14:15:00Z',
    enforcedBy: 'Nguyễn Quốc Bảo (Lead Platform)',
    lawRef: 'Nghị định 13/2023/NĐ-CP & GDPR Art. 5',
    scannedCount: 10000,
    quarantinedCount: 7,
    engine: 'Presidio / Hash Masking Gateway',
    status: 'active',
  },
  {
    id: 'ACT-DRV-01',
    name: 'license_validity_dispatch_guard',
    expression: 'license_expiry_date > CURRENT_DATE()',
    domain: 'ITGC & Evidence',
    datasetId: 'drivers',
    datasetName: 'drivers',
    severity: 'CRITICAL',
    targetLane: 'Daily Dispatch Gate',
    enforcedAt: '2026-09-22T09:00:00Z',
    enforcedBy: 'Trần Minh Hoàng (Auditor IPO)',
    lawRef: 'Quy chuẩn An toàn Vận tải GSM 2024',
    scannedCount: 1200,
    quarantinedCount: 6,
    engine: 'HR / Telematics Webhook Guard',
    status: 'active',
  },
  {
    id: 'ACT-CHG-01',
    name: 'modbus_meter_delta_tolerance',
    expression: 'abs(meter_kwh_delta - bms_kwh_delta) <= 0.03 * meter_kwh_delta',
    domain: 'Data Quality',
    datasetId: 'charging',
    datasetName: 'charging',
    severity: 'HIGH',
    targetLane: 'Energy Billing Guard',
    enforcedAt: '2026-09-23T11:45:00Z',
    enforcedBy: 'Nguyễn Quốc Bảo (Lead Platform)',
    lawRef: 'SOX 404 & Chuẩn Đo lường Điện năng',
    scannedCount: 8500,
    quarantinedCount: 9,
    engine: 'IoT Edge Modbus Stream Filter',
    status: 'active',
  },
  {
    id: 'ACT-TEL-01',
    name: 'bms_cell_temp_critical_cutoff',
    expression: 'max_cell_temp_c <= 65.0 AND min_cell_temp_c >= -20.0',
    domain: 'Data Quality',
    datasetId: 'telemetry',
    datasetName: 'telemetry',
    severity: 'CRITICAL',
    targetLane: 'BMS Ingestion Gate',
    enforcedAt: '2026-09-24T16:20:00Z',
    enforcedBy: 'Hệ thống tự động kích hoạt (Auto-Enforce)',
    lawRef: 'UN ECE R100 Battery Safety Norms',
    scannedCount: 45000,
    quarantinedCount: 12,
    engine: 'CAN-bus MQTT Stream Processor',
    status: 'active',
  },
];

export const initialChatMessages: ChatMessageItem[] = [
  {
    id: 'MSG-01',
    sender: 'ai',
    text: `Chào bạn! Tôi là **DataTrust AI Orchestrator**. Tôi sẽ đồng hành cùng bạn kiểm soát chất lượng dữ liệu, bảo vệ dữ liệu cá nhân (PII) và thẩm tra bằng chứng tuân thủ chuẩn IPO.

Để bắt đầu, hãy chọn 1 bộ dữ liệu để tôi quét và chạy luồng kiểm soát từ **L1 đến L4**:`,
    timestamp: 'Vừa xong',
    quickActions: [
      { label: '🚖 trips', actionType: 'SELECT_AND_RUN', payload: 'trips' },
      { label: '👥 customers', actionType: 'SELECT_AND_RUN', payload: 'customers' },
      { label: '🚗 drivers', actionType: 'SELECT_AND_RUN', payload: 'drivers' },
      { label: '⚡ charging', actionType: 'SELECT_AND_RUN', payload: 'charging' },
      { label: '🔋 telemetry', actionType: 'SELECT_AND_RUN', payload: 'telemetry' },
    ],
  },
];

export const initialPipelineLevels: PipelineLevelsState = {
  currentLevel: 'IDLE',
  l1: {
    status: 'idle',
    progress: 0,
    scanned: 0,
    passed: 0,
    failed: 0,
    signalCount: 0,
    algorithm: 'Deterministic Range, Schema & Null check',
    latencyMs: 14,
  },
  l2: {
    status: 'idle',
    progress: 0,
    scanned: 0,
    passed: 0,
    failed: 0,
    signalCount: 0,
    algorithm: 'Median, MAD & Robust Z-Score',
    latencyMs: 22,
  },
  l3: {
    status: 'idle',
    progress: 0,
    scanned: 0,
    passed: 0,
    failed: 0,
    signalCount: 0,
    algorithm: 'Linear Regression Residuals (y = ax + b)',
    latencyMs: 38,
  },
  l4: {
    status: 'idle',
    progress: 0,
    scanned: 0,
    passed: 0,
    failed: 0,
    signalCount: 0,
    algorithm: 'CUSUM / PELT Regime Shift Detection',
    latencyMs: 45,
  },
};

export interface AgentStoreState {
  // Global Role & Dataset Selection
  currentRole: 'auditor' | 'admin';
  setRole: (role: 'auditor' | 'admin') => void;
  selectedDatasetId: string;
  selectDataset: (id: string) => void;

  // Pipeline Engine Status
  agentStatus: 'idle' | 'running' | 'completed';
  stepIndex: number;
  datasets: Record<string, DatasetItem>;
  steps: AgentStep[];
  runAgent: () => void;
  approveRule: (ruleId: string) => void;
  rejectRule: (ruleId: string) => void;
  updateRuleExpression: (ruleId: string, expr: string) => void;
  getPendingRulesCount: () => number;

  // Auditor Compliance Cases & Findings
  complianceCases: ComplianceCaseItem[];
  selectedFindingModal: FindingItem | null;
  runComplianceCase: (caseId: string) => Promise<void>;
  runAllComplianceCasesForDataset: () => Promise<void>;
  openFindingModal: (findingId: string) => void;
  closeFindingModal: () => void;
  markFindingAudited: (findingId: string) => void;

  // Admin Policy Adaptation Engine
  policies: PolicyItem[];
  selectedPolicyId: string;
  selectPolicy: (policyId: string) => void;
  simulatePolicyDryRun: (policyId: string) => Promise<void>;
  approvePolicyRule: (policyId: string) => void;
  rejectPolicyRule: (policyId: string) => void;
  addNewPolicyText: (title: string, rawText: string) => void;

  // Homepage Dual-Pane & Real-time Flow
  isSidebarCollapsed: boolean;
  toggleSidebarCollapse: () => void;
  homepageViewMode: HomepageViewMode;
  isChatCollapsed: boolean;
  toggleChatCollapse: () => void;
  setHomepageViewMode: (mode: HomepageViewMode) => void;
  pipelineLevels: PipelineLevelsState;
  chatMessages: ChatMessageItem[];
  activeRules: ActiveRule[];
  rulesSegmentTab: 'active' | 'proposed';
  setRulesSegmentTab: (tab: 'active' | 'proposed') => void;
  startPipelineRun: (datasetId?: string) => Promise<void>;
  skipPipelineRunToResults: () => void;
  sendUserChatMessage: (text: string) => void;
  resetHomepageFlow: () => void;
  simulateDryRun: (ruleId: string) => Promise<void>;
  toggleActiveRuleStatus: (ruleId: string) => void;
}

const initialDatasets: Record<string, DatasetItem> = {
  trips: {
    id: 'trips',
    name: 'trips',
    title: 'trips',
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
    name: 'customers',
    title: 'customers',
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
    name: 'drivers',
    title: 'drivers',
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
    name: 'charging',
    title: 'charging',
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
    name: 'telemetry',
    title: 'telemetry',
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

const initialComplianceCases: ComplianceCaseItem[] = [
  {
    id: 'CASE-TRIP-01',
    code: 'TC-REV-01',
    name: 'Kiểm soát Doanh thu & Cước phí Chuyến đi (Chống cước 0đ / Âm)',
    datasetId: 'trips',
    domain: 'Data Quality & Revenue Assurance',
    lawStandard: 'IFRS 15 & SOX ITGC Control DQ-01',
    description: 'Thẩm tra tính hợp lệ của việc ghi nhận doanh thu cuốc xe taxi GSM, đảm bảo không có giao dịch ảo hoặc cự ly bằng 0.',
    expectedControl: 'fare_amount > 0 AND trip_distance_km >= 0.1',
    status: 'failed',
    executionTimeMs: 38,
    evidenceHash: 'sha256:7f83b1657ff1fc53b92dc18148a1d65dfc2d4b1fa3d677284addd200126d9069',
    findings: [
      {
        id: 'FND-TRIP-001',
        caseId: 'CASE-TRIP-01',
        caseCode: 'TC-REV-01',
        title: '18 cuốc xe ghi nhận cước 0đ hoặc cự ly <= 0km không hợp lệ',
        datasetId: 'trips',
        severity: 'CRITICAL',
        status: 'OPEN',
        detectedAt: 'Hôm nay, 10:14:22',
        rootCauseAnalysis: 'AI Agent phân tích: Lỗi xảy ra tại các client mobile app driver phiên bản v3.2.1 khi mất kết nối mạng (offline mode). Khi tài xế bấm kết thúc cuốc lúc offline, hệ thống tự động gán fare_amount = 0 và không áp dụng voucher hợp lệ khi gửi payload lên server Bronze stream.',
        evidence: {
          hashSha256: 'sha256:7f83b1657ff1fc53b92dc18148a1d65dfc2d4b1fa3d677284addd200126d9069',
          previousHash: 'sha256:004381ab9c21ee481023dc81023912daef841289410294104231802931201928',
          lawReference: 'IFRS 15 (Doanh thu từ hợp đồng với khách hàng) & SOX ITGC Section 404',
          quarantinedCount: 18,
          samplePayload: {
            trip_id: 'TRIP-VN-90812',
            fare_amount: 0,
            distance_km: -2.4,
            driver_id: 'DRV-8812',
            vehicle_id: 'VF8-29A-12891',
            payment_method: 'CASH_0VND',
            status: 'COMPLETED',
            client_version: 'v3.2.1-offline',
          },
          digitalSignature: 'SIG-ED25519-GSM-IPO-991A8F',
        },
        aiRemediation: {
          actionPlan: [
            'Tự động cách ly 18 bản ghi sang làn Quarantine, ngăn chặn ghi nhận vào doanh thu Silver',
            'Kích hoạt rule kiểm soát `fare_amount > 0 AND trip_distance_km >= 0.1` trên Ingestion Stream',
            'Thông báo đội kỹ thuật Mobile vá lỗi offline cache trên client v3.2.1',
          ],
          proposedRuleName: 'trip_fare_and_distance_positive',
          proposedExpression: 'fare_amount > 0 AND trip_distance_km >= 0.1',
          targetLane: 'Quarantine Lane / Ingestion Gate',
        },
      },
    ],
  },
  {
    id: 'CASE-TRIP-02',
    code: 'TC-PII-02',
    name: 'Bảo vệ Dữ liệu Cá nhân & Che mờ Số điện thoại Khách hàng',
    datasetId: 'trips',
    domain: 'Privacy & Data Protection',
    lawStandard: 'Nghị định 13/2023/NĐ-CP & GDPR Art. 5(1)(c)',
    description: 'Kiểm tra tuân thủ bảo vệ dữ liệu PII, phát hiện các bản ghi để lộ số điện thoại dạng văn bản thô (cleartext).',
    expectedControl: 'is_masked(customer_phone) WHEN role != "Admin"',
    status: 'failed',
    executionTimeMs: 29,
    evidenceHash: 'sha256:9b12a832f09c64b5849547d2d14b4344d57a2f588c26786a345bf94821a81234',
    findings: [
      {
        id: 'FND-TRIP-002',
        caseId: 'CASE-TRIP-02',
        caseCode: 'TC-PII-02',
        title: '7 bản ghi chuyến đi để lộ số điện thoại dạng cleartext trong telemetry',
        datasetId: 'trips',
        severity: 'HIGH',
        status: 'OPEN',
        detectedAt: 'Hôm nay, 10:14:23',
        rootCauseAnalysis: 'AI Agent phân tích: Endpoint log telemetry chuyến đi nhận trực tiếp trường `customer_phone` từ dispatch engine mà không qua thư viện che mờ PII Dynamic Masking.',
        evidence: {
          hashSha256: 'sha256:9b12a832f09c64b5849547d2d14b4344d57a2f588c26786a345bf94821a81234',
          previousHash: 'sha256:7f83b1657ff1fc53b92dc18148a1d65dfc2d4b1fa3d677284addd200126d9069',
          lawReference: 'Nghị định 13/2023/NĐ-CP Điều 9 (Bảo vệ dữ liệu cá nhân cơ bản)',
          quarantinedCount: 7,
          samplePayload: {
            trip_id: 'TRIP-VN-77142',
            customer_id: 'CUST-9921',
            customer_phone: '0912345678',
            masked: false,
            telemetry_source: 'dispatch_realtime',
          },
          digitalSignature: 'SIG-ED25519-GSM-IPO-224C71',
        },
        aiRemediation: {
          actionPlan: [
            'Mã hóa che mờ tức thời số điện thoại thành dạng 091****678',
            'Áp dụng Dynamic Masking UDF vào PySpark Silver transformation',
          ],
          proposedRuleName: 'customer_phone_masking',
          proposedExpression: 'mask_phone(customer_phone) WHEN role != "Admin"',
          targetLane: 'Dynamic Masking Engine',
        },
      },
    ],
  },
  {
    id: 'CASE-CUST-01',
    code: 'TC-KYC-01',
    name: 'Kiểm tra Định dạng & Tính Hợp lệ Số CCCD/eID Khách hàng',
    datasetId: 'customers',
    domain: 'Data Quality & KYC Governance',
    lawStandard: 'Luật Căn cước 2023 & Chuẩn KYC GSM Global',
    description: 'Thẩm tra định dạng số CCCD 12 số hoặc CMND 9 số, đảm bảo không có ký tự đặc biệt hoặc độ dài sai lệch.',
    expectedControl: 'length(citizen_id) IN (9, 12) AND is_numeric(citizen_id)',
    status: 'failed',
    executionTimeMs: 34,
    evidenceHash: 'sha256:3a77d4c2b98e1f0a245582d90875c7e1124fa682e44d320984baacdd20485671',
    findings: [
      {
        id: 'FND-CUST-001',
        caseId: 'CASE-CUST-01',
        caseCode: 'TC-KYC-01',
        title: '14 số định danh cá nhân sai độ dài hoặc chứa ký tự đặc biệt',
        datasetId: 'customers',
        severity: 'HIGH',
        status: 'OPEN',
        detectedAt: 'Hôm nay, 09:30:15',
        rootCauseAnalysis: 'AI Agent phân tích: Khách hàng nhập liệu từ giao diện web đăng ký đối tác GSM quốc tế không áp dụng regex validator độ dài 9 hoặc 12 chữ số.',
        evidence: {
          hashSha256: 'sha256:3a77d4c2b98e1f0a245582d90875c7e1124fa682e44d320984baacdd20485671',
          previousHash: 'sha256:9b12a832f09c64b5849547d2d14b4344d57a2f588c26786a345bf94821a81234',
          lawReference: 'Luật Căn cước 2023 & IPO Control KYC-02',
          quarantinedCount: 14,
          samplePayload: {
            cust_id: 'CUST-INT-102',
            citizen_id: '001290XYZ12',
            country: 'VN',
            id_type: 'CCCD',
          },
          digitalSignature: 'SIG-ED25519-GSM-IPO-776F10',
        },
        aiRemediation: {
          actionPlan: [
            'Cách ly 14 hồ sơ khách hàng vào hàng đợi đối soát thủ công KYC',
            'Áp dụng Schema Check regex vào cổng Ingestion API',
          ],
          proposedRuleName: 'citizen_id_format_check',
          proposedExpression: 'length(citizen_id) IN (9, 12) AND is_numeric(citizen_id)',
          targetLane: 'SQL Schema Checker',
        },
      },
    ],
  },
  {
    id: 'CASE-DRV-01',
    code: 'TC-DRV-01',
    name: 'Kiểm soát Hiệu lực Giấy phép Lái xe (GPLX) Tài xế Đội xe',
    datasetId: 'drivers',
    domain: 'ITGC & Operational Safety',
    lawStandard: 'Luật An toàn Giao thông 2024 & Quyết định 28/2024 Bộ GTVT',
    description: 'Thẩm định điều kiện mở ca điều phối, chặn tài xế có bằng lái B2 hết hạn nhận lệnh đón khách.',
    expectedControl: 'license_expiry_date > CURRENT_DATE()',
    status: 'failed',
    executionTimeMs: 25,
    evidenceHash: 'sha256:5c81d892a0149bb41098ef1a0293810294102938102938102938102938102938',
    findings: [
      {
        id: 'FND-DRV-001',
        caseId: 'CASE-DRV-01',
        caseCode: 'TC-DRV-01',
        title: '6 tài xế có GPLX hết hạn trong 7 ngày nhưng vẫn mở ca trực',
        datasetId: 'drivers',
        severity: 'CRITICAL',
        status: 'OPEN',
        detectedAt: 'Hôm nay, 08:45:11',
        rootCauseAnalysis: 'AI Agent phân tích: Hệ thống điều phối dispatch không đồng bộ dữ liệu gia hạn GPLX từ cơ sở dữ liệu nhân sự tài xế theo thời gian thực.',
        evidence: {
          hashSha256: 'sha256:5c81d892a0149bb41098ef1a0293810294102938102938102938102938102938',
          previousHash: 'sha256:3a77d4c2b98e1f0a245582d90875c7e1124fa682e44d320984baacdd20485671',
          lawReference: 'Luật Trật tự an toàn giao thông đường bộ 2024',
          quarantinedCount: 6,
          samplePayload: {
            driver_id: 'DRV-VN-4401',
            license_no: 'B2-790182',
            expiry_date: '2026-09-18',
            shift_status: 'ACTIVE',
          },
          digitalSignature: 'SIG-ED25519-GSM-IPO-330D12',
        },
        aiRemediation: {
          actionPlan: [
            'Tạm khóa ca điều phối của 6 tài xế có bằng lái hết hạn',
            'Tự động gửi cảnh báo SMS yêu cầu cập nhật GPLX mới',
          ],
          proposedRuleName: 'driver_license_expiration',
          proposedExpression: 'license_expiry_date > CURRENT_DATE()',
          targetLane: 'Daily Dispatch Gate',
        },
      },
    ],
  },
  {
    id: 'CASE-CHG-01',
    code: 'TC-CHG-01',
    name: 'Kiểm soát Sai lệch Công tơ Điện & Nạp Trụ Sạc VinFast',
    datasetId: 'charging',
    domain: 'Data Quality & Energy Billing',
    lawStandard: 'GSM EV Asset Control 03 & Kiểm toán Năng lượng',
    description: 'Kiểm tra độ lệch giữa công tơ nguồn và điện năng nạp thực tế vào xe điện, khống chế ngưỡng sai số <= 3%.',
    expectedControl: 'ABS(meter_delta_kwh - billed_kwh) / billed_kwh <= 0.03',
    status: 'failed',
    executionTimeMs: 42,
    evidenceHash: 'sha256:6e19203810293810293810293810293810293810293810293810293810293810',
    findings: [
      {
        id: 'FND-CHG-001',
        caseId: 'CASE-CHG-01',
        caseCode: 'TC-CHG-01',
        title: '9 phiên sạc có chênh lệch công tơ nguồn và kWh nạp thực tế vượt ngưỡng 3%',
        datasetId: 'charging',
        severity: 'HIGH',
        status: 'OPEN',
        detectedAt: 'Hôm qua, 18:20:00',
        rootCauseAnalysis: 'AI Agent phân tích: Trụ sạc nhanh DC 250kW tại trạm Landmark 81 bị xung điện áp tạm thời, dẫn đến sai số đọc công tơ Modbus.',
        evidence: {
          hashSha256: 'sha256:6e19203810293810293810293810293810293810293810293810293810293810',
          previousHash: 'sha256:5c81d892a0149bb41098ef1a0293810294102938102938102938102938102938',
          lawReference: 'Quy chuẩn Đo lường Năng lượng Điện VN & SOX Section 404',
          quarantinedCount: 9,
          samplePayload: {
            pole_id: 'VF-LM81-PL04',
            session_id: 'CHG-99214',
            meter_start: 1240.2,
            meter_end: 1298.5,
            billed_kwh: 52.1,
            delta_ratio: 0.098,
          },
          digitalSignature: 'SIG-ED25519-GSM-IPO-441A99',
        },
        aiRemediation: {
          actionPlan: [
            'Tạm ngắt thanh toán tự động cho 9 phiên sạc nghi vấn',
            'Áp dụng rule kiểm soát sai số công tơ vào cổng thanh toán',
          ],
          proposedRuleName: 'station_meter_delta_tolerance',
          proposedExpression: 'ABS(meter_delta_kwh - billed_kwh) / billed_kwh <= 0.03',
          targetLane: 'Energy Billing Guard',
        },
      },
    ],
  },
  {
    id: 'CASE-TEL-01',
    code: 'TC-IOT-01',
    name: 'Cảnh báo Giới hạn Nhiệt độ Cell Pin BMS Xe Điện VF8',
    datasetId: 'telemetry',
    domain: 'IoT Telemetry & Fleet Safety',
    lawStandard: 'GSM Fleet Battery Safety Standard L4 & UN ECE R100',
    description: 'Theo dõi liên tục gói tin viễn thông BMS, cảnh báo quá nhiệt cell pin trên ngưỡng 65°C.',
    expectedControl: 'battery_temp_c <= 65.0',
    status: 'failed',
    executionTimeMs: 27,
    evidenceHash: 'sha256:8a12938102938102938102938102938102938102938102938102938102938102',
    findings: [
      {
        id: 'FND-TEL-001',
        caseId: 'CASE-TEL-01',
        caseCode: 'TC-IOT-01',
        title: '12 gói tin telemetry gửi nhiệt độ cell pin đạt 71.8°C (vượt ngưỡng 65°C)',
        datasetId: 'telemetry',
        severity: 'CRITICAL',
        status: 'OPEN',
        detectedAt: 'Hôm nay, 11:05:40',
        rootCauseAnalysis: 'AI Agent phân tích: Xe VF8 vận hành liên tục dưới thời tiết nắng nóng 41°C kèm sạc nhanh DC công suất tối đa, làm quạt tản nhiệt BMS kích hoạt chậm 15 giây.',
        evidence: {
          hashSha256: 'sha256:8a12938102938102938102938102938102938102938102938102938102938102',
          previousHash: 'sha256:6e19203810293810293810293810293810293810293810293810293810293810',
          lawReference: 'Quy chuẩn An toàn Pin Xe điện Quốc tế UN ECE R100',
          quarantinedCount: 12,
          samplePayload: {
            vin: 'VF8-VN-99214',
            battery_temp_c: 71.8,
            soc_pct: 88,
            coolant_flow_lpm: 4.2,
            status: 'FAST_CHARGING',
          },
          digitalSignature: 'SIG-ED25519-GSM-IPO-882E44',
        },
        aiRemediation: {
          actionPlan: [
            'Tự động phát tín hiệu điều chỉnh giảm dòng sạc về mức an toàn',
            'Gửi cảnh báo đến Trung tâm Điều hành Đội xe (Fleet Command Center)',
          ],
          proposedRuleName: 'battery_temperature_bound',
          proposedExpression: 'battery_temp_c <= 65.0',
          targetLane: 'IoT Ingestion Stream Filter',
        },
      },
    ],
  },
];

const initialPolicies: PolicyItem[] = [
  {
    id: 'POL-01',
    title: 'Nghị định 13/2023/NĐ-CP sửa đổi: Bắt buộc mã hóa AES-256 định danh cá nhân trên taxi công nghệ',
    datasetId: 'trips',
    sourceDoc: 'Bộ Công An & Cục An ninh mạng · Thông tư hướng dẫn 02/2026/BCA',
    effectiveDate: '01/10/2026',
    rawPolicyText: 'Mọi thông tin cá nhân bao gồm số căn cước công dân (CCCD/eID), số điện thoại di động và dữ liệu sinh trắc học của hành khách phải được che mờ (masking) hoặc mã hóa theo chuẩn AES-256 trước khi lưu trữ hoặc truyền qua hệ thống telemetry.',
    aiAnalysisSummary: 'AI Agent phân tích: Chính sách yêu cầu mã hóa bắt buộc 100% trường SĐT và CCCD. Đề xuất tạo Rule mã hóa AES-256 trên tầng Ingestion Stream.',
    generatedRule: {
      name: 'RULE-PII-AUTO-01: mandate_aes256_passenger_identifier',
      expression: 'is_aes256_encrypted(citizen_id) AND is_masked(customer_phone)',
      compiledTarget: 'Dynamic Masking Engine / PySpark Crypto UDF',
      confidence: 99,
    },
    dryRunSimulation: {
      scannedRows: 1250000,
      silverCleanRows: 1246580,
      quarantinedRows: 3420,
      estimatedLatencyMs: 14,
    },
    status: 'simulated',
  },
  {
    id: 'POL-02',
    title: 'Chính sách Cước phí Động GSM V35: Cước tối thiểu 14.000đ & Chống cuốc xe ảo gian lận khuyến mãi',
    datasetId: 'trips',
    sourceDoc: 'GSM Global Strategy Directive · Q3/2026',
    effectiveDate: '15/09/2026',
    rawPolicyText: 'Tất cả cuốc xe hợp lệ phải có giá cước tối thiểu 14.000 VNĐ và quãng đường di chuyển thực tế từ 0.5km trở lên (hoặc thời gian đón trả trên 2 phút). Các cuốc vi phạm lập tức chuyển sang làn Quarantine để kiểm tra đối soát trước khi ghi nhận doanh thu.',
    aiAnalysisSummary: 'AI Agent phân tích: Cần chốt chặn doanh thu ảo cước nhỏ hơn 14k hoặc cự ly < 0.5km. Ngăn chặn gian lận voucher khuyến mãi.',
    generatedRule: {
      name: 'RULE-FRAUD-AUTO-02: minimum_fare_and_distance_threshold',
      expression: 'fare_amount >= 14000 AND (distance_km >= 0.5 OR trip_duration_sec >= 120)',
      compiledTarget: 'SQL Quarantine Lane / Real-time Flink Job',
      confidence: 97,
    },
    dryRunSimulation: {
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
    datasetId: 'charging',
    sourceDoc: 'VinFast Energy Infrastructure Specification V4',
    effectiveDate: '01/08/2026',
    rawPolicyText: 'Trụ sạc nhanh công suất đỉnh 250kW-300kW phải duy trì độ lệch giữa công tơ nguồn và điện năng nạp thực tế dưới 3%. Nếu công tơ chỉ số cuối nhỏ hơn chỉ số đầu hoặc kWh delivered âm, ngắt cổng thanh toán và cách ly bản ghi nạp điện.',
    aiAnalysisSummary: 'AI Agent phân tích: Đảm bảo độ lệch công tơ <= 3% và không cho phép chỉ số điện âm.',
    generatedRule: {
      name: 'RULE-CHG-AUTO-03: ultra_charging_meter_tolerance',
      expression: 'peak_kw <= 300 AND meter_end >= meter_start AND power_loss_ratio < 0.03',
      compiledTarget: 'IoT Streaming Aggregator & Billing Guard',
      confidence: 96,
    },
    dryRunSimulation: {
      scannedRows: 3200,
      silverCleanRows: 3144,
      quarantinedRows: 56,
      estimatedLatencyMs: 5,
    },
    status: 'draft',
  },
];

export const useAgentStore = create<AgentStoreState>((set, get) => ({
  currentRole: 'auditor',
  setRole: (role) => {
    const isAuditor = role === 'auditor';
    set((s) => ({
      currentRole: role,
      rulesSegmentTab: isAuditor ? 'active' : s.rulesSegmentTab,
    }));
  },

  selectedDatasetId: 'trips',
  agentStatus: 'completed',
  stepIndex: 4,
  datasets: initialDatasets,
  steps: initialSteps,

  // Homepage Dual-Pane & Real-time Flow
  isSidebarCollapsed: false,
  toggleSidebarCollapse: () => set((s) => ({ isSidebarCollapsed: !s.isSidebarCollapsed })),
  homepageViewMode: 'welcome',
  isChatCollapsed: false,
  toggleChatCollapse: () => set((s) => ({ isChatCollapsed: !s.isChatCollapsed })),
  setHomepageViewMode: (mode) => set({ homepageViewMode: mode }),
  pipelineLevels: initialPipelineLevels,
  chatMessages: initialChatMessages,
  activeRules: initialActiveRules,
  rulesSegmentTab: 'active',
  setRulesSegmentTab: (tab) => set({ rulesSegmentTab: tab }),

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
    if (get().currentRole === 'auditor') return; // Auditor is viewer only and cannot approve rules

    set((state) => {
      const currentDs = state.datasets[state.selectedDatasetId];
      if (!currentDs) return state;

      let approvedRuleTarget: ProposedRule | undefined;
      const updatedRules = currentDs.proposedRules.map((r) => {
        if (r.id === ruleId) {
          approvedRuleTarget = {
            ...r,
            status: 'approved' as const,
            approvedAt: new Date().toISOString(),
            approvedBy: state.currentRole === 'auditor' ? 'Trần Minh Hoàng (Auditor IPO)' : 'Nguyễn Quốc Bảo (Admin)',
          };
          return approvedRuleTarget;
        }
        return r;
      });

      let updatedActiveRules = state.activeRules;
      if (approvedRuleTarget) {
        const newActive: ActiveRule = {
          id: `ACT-${approvedRuleTarget.id}`,
          name: approvedRuleTarget.name,
          expression: approvedRuleTarget.expression,
          domain: approvedRuleTarget.domain,
          datasetId: state.selectedDatasetId,
          datasetName: currentDs.title,
          severity: approvedRuleTarget.severity,
          targetLane: approvedRuleTarget.compiledTarget,
          enforcedAt: new Date().toISOString(),
          enforcedBy: state.currentRole === 'auditor' ? 'Trần Minh Hoàng (Auditor IPO)' : 'Nguyễn Quốc Bảo (Admin)',
          lawRef: approvedRuleTarget.lawRef,
          scannedCount: currentDs.records,
          quarantinedCount: approvedRuleTarget.affectedRows,
          engine: 'PySpark / SQL Stream Validator',
          status: 'active',
        };
        if (!updatedActiveRules.some((a) => a.id === newActive.id)) {
          updatedActiveRules = [newActive, ...updatedActiveRules];
        }
      }

      const ruleName = approvedRuleTarget?.name || ruleId;
      const newAiMsg: ChatMessageItem = {
        id: `MSG-APP-${Date.now()}`,
        sender: 'ai',
        text: `✅ **Đã phê duyệt Rule thành công!**\nRule **${ruleName}** đã được kích hoạt vào danh sách **Rule đang áp dụng (Active in Production)**.\n• **Căn cứ**: *${approvedRuleTarget?.lawRef || 'IPO Control'}*\n• **Làn xử lý**: *${approvedRuleTarget?.compiledTarget || 'Quarantine Lane'}*\n• **Tác động bảo vệ**: Đã chuyển các bản ghi vi phạm vào luồng cách ly để bảo toàn doanh thu sạch (Silver lane).`,
        timestamp: 'Vừa xong',
      };

      return {
        datasets: {
          ...state.datasets,
          [state.selectedDatasetId]: {
            ...currentDs,
            proposedRules: updatedRules,
          },
        },
        activeRules: updatedActiveRules,
        chatMessages: [...state.chatMessages, newAiMsg],
      };
    });
  },

  rejectRule: (ruleId: string) => {
    if (get().currentRole === 'auditor') return; // Auditor is viewer only and cannot reject rules

    set((state) => {
      const currentDs = state.datasets[state.selectedDatasetId];
      if (!currentDs) return state;

      let rejectedRule: ProposedRule | undefined;
      const updatedRules = currentDs.proposedRules.map((r) => {
        if (r.id === ruleId) {
          rejectedRule = { ...r, status: 'rejected' as const };
          return rejectedRule;
        }
        return r;
      });

      const newAiMsg: ChatMessageItem = {
        id: `MSG-REJ-${Date.now()}`,
        sender: 'ai',
        text: `⚠️ Bạn đã **từ chối** áp dụng Rule **${rejectedRule?.name || ruleId}**. Dữ liệu liên quan sẽ tiếp tục được theo dõi ở mức cảnh báo và chưa đưa vào chặn tự động.`,
        timestamp: 'Vừa xong',
      };

      return {
        datasets: {
          ...state.datasets,
          [state.selectedDatasetId]: {
            ...currentDs,
            proposedRules: updatedRules,
          },
        },
        chatMessages: [...state.chatMessages, newAiMsg],
      };
    });
  },

  updateRuleExpression: (ruleId: string, expr: string) => {
    if (get().currentRole === 'auditor') return; // Auditor is viewer only and cannot edit rules

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

  // Auditor Compliance Cases & Findings
  complianceCases: initialComplianceCases,
  selectedFindingModal: null,

  runComplianceCase: async (caseId: string) => {
    set((state) => ({
      complianceCases: state.complianceCases.map((c) =>
        c.id === caseId ? { ...c, status: 'running' as const } : c
      ),
    }));

    await new Promise((r) => setTimeout(r, 900));

    const randomHash =
      'sha256:' +
      Array.from({ length: 64 }, () => Math.floor(Math.random() * 16).toString(16)).join('');

    set((state) => ({
      complianceCases: state.complianceCases.map((c) => {
        if (c.id !== caseId) return c;
        return {
          ...c,
          status: 'failed' as const, // Highlights finding with root cause for auditor review
          evidenceHash: randomHash,
          executionTimeMs: Math.floor(Math.random() * 30) + 20,
        };
      }),
    }));
  },

  runAllComplianceCasesForDataset: async () => {
    const currentDataset = get().selectedDatasetId;
    set((state) => ({
      complianceCases: state.complianceCases.map((c) =>
        c.datasetId === currentDataset ? { ...c, status: 'running' as const } : c
      ),
    }));

    await new Promise((r) => setTimeout(r, 1200));

    set((state) => ({
      complianceCases: state.complianceCases.map((c) => {
        if (c.datasetId !== currentDataset) return c;
        const randomHash =
          'sha256:' +
          Array.from({ length: 64 }, () => Math.floor(Math.random() * 16).toString(16)).join('');
        return {
          ...c,
          status: 'failed' as const,
          evidenceHash: randomHash,
          executionTimeMs: Math.floor(Math.random() * 30) + 20,
        };
      }),
    }));
  },

  openFindingModal: (findingId: string) => {
    const state = get();
    for (const c of state.complianceCases) {
      const f = c.findings.find((item) => item.id === findingId);
      if (f) {
        set({ selectedFindingModal: f });
        return;
      }
    }
  },

  closeFindingModal: () => {
    set({ selectedFindingModal: null });
  },

  markFindingAudited: (findingId: string) => {
    set((state) => ({
      complianceCases: state.complianceCases.map((c) => ({
        ...c,
        findings: c.findings.map((f) =>
          f.id === findingId ? { ...f, status: 'AUDITED' as const } : f
        ),
      })),
      selectedFindingModal:
        state.selectedFindingModal?.id === findingId
          ? { ...state.selectedFindingModal, status: 'AUDITED' as const }
          : state.selectedFindingModal,
    }));
  },

  // Admin Policy Engine
  policies: initialPolicies,
  selectedPolicyId: 'POL-01',

  selectPolicy: (policyId: string) => {
    set({ selectedPolicyId: policyId });
  },

  simulatePolicyDryRun: async (policyId: string) => {
    await new Promise((r) => setTimeout(r, 700));
    set((state) => ({
      policies: state.policies.map((p) =>
        p.id === policyId ? { ...p, status: 'simulated' as const } : p
      ),
    }));
  },

  approvePolicyRule: (policyId: string) => {
    if (get().currentRole === 'auditor') return;

    set((state) => {
      const targetPolicy = state.policies.find((p) => p.id === policyId);
      if (!targetPolicy) return state;

      const updatedPolicies = state.policies.map((p) =>
        p.id === policyId ? { ...p, status: 'approved' as const } : p
      );

      const curDs = state.datasets[state.selectedDatasetId] || state.datasets.trips;
      const newRule: ProposedRule = {
        id: `RULE-POL-${targetPolicy.id}`,
        name: targetPolicy.generatedRule.name,
        expression: targetPolicy.generatedRule.expression,
        rationale: `Tự động thích ứng từ: ${targetPolicy.title}. Phân tích bởi AI Agent.`,
        domain: 'Data Quality',
        severity: 'HIGH',
        status: 'approved',
        confidence: targetPolicy.generatedRule.confidence,
        affectedRows: targetPolicy.dryRunSimulation.quarantinedRows,
        evidenceId: `EVID-POL-${targetPolicy.id}`,
        passRows: targetPolicy.dryRunSimulation.silverCleanRows,
        quarantineRows: targetPolicy.dryRunSimulation.quarantinedRows,
        compiledTarget: targetPolicy.generatedRule.compiledTarget,
        lawRef: targetPolicy.sourceDoc,
        approvedAt: new Date().toISOString(),
        approvedBy: 'System Admin (HITL)',
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

  rejectPolicyRule: (policyId: string) => {
    if (get().currentRole === 'auditor') return;

    set((state) => ({
      policies: state.policies.map((p) =>
        p.id === policyId ? { ...p, status: 'rejected' as const } : p
      ),
    }));
  },

  addNewPolicyText: (title: string, rawText: string) => {
    const newId = `POL-${Date.now().toString().slice(-4)}`;
    const curDataset = get().selectedDatasetId;
    const newPolicy: PolicyItem = {
      id: newId,
      title: title || 'Chính sách mới được dán',
      datasetId: curDataset,
      sourceDoc: 'Chính sách nội bộ vừa cập nhật',
      effectiveDate: new Date().toLocaleDateString('vi-VN'),
      rawPolicyText: rawText,
      aiAnalysisSummary: `AI Agent đã phân tích: Đã trích xuất các điều kiện ràng buộc dữ liệu từ văn bản và tạo biểu thức logic phù hợp với bộ dữ liệu ${curDataset}.`,
      generatedRule: {
        name: `RULE-ADAPT-${newId}: custom_enforced_control`,
        expression: 'is_valid_format(data_payload) AND status == "VERIFIED"',
        compiledTarget: 'SQL Quarantine Lane / PySpark Filter',
        confidence: 95,
      },
      dryRunSimulation: {
        scannedRows: 12000,
        silverCleanRows: 11982,
        quarantinedRows: 18,
        estimatedLatencyMs: 6,
      },
      status: 'simulated',
    };

    set((state) => ({
      policies: [newPolicy, ...state.policies],
      selectedPolicyId: newId,
    }));
  },

  startPipelineRun: async (datasetId?: string) => {
    const targetDatasetId = datasetId || get().selectedDatasetId;
    const dataset = get().datasets[targetDatasetId] || get().datasets.trips;
    
    set({
      selectedDatasetId: targetDatasetId,
      homepageViewMode: 'running_pipeline',
      pipelineLevels: {
        currentLevel: 'L1',
        l1: { status: 'running', progress: 30, scanned: Math.floor(dataset.records * 0.3), passed: Math.floor(dataset.records * 0.29), failed: 0, signalCount: 1, algorithm: 'Deterministic Range, Schema & Null check', latencyMs: 14 },
        l2: { status: 'idle', progress: 0, scanned: 0, passed: 0, failed: 0, signalCount: 0, algorithm: 'Median, MAD & Robust Z-Score', latencyMs: 22 },
        l3: { status: 'idle', progress: 0, scanned: 0, passed: 0, failed: 0, signalCount: 0, algorithm: 'Linear Regression Residuals (y = ax + b)', latencyMs: 38 },
        l4: { status: 'idle', progress: 0, scanned: 0, passed: 0, failed: 0, signalCount: 0, algorithm: 'CUSUM / PELT Regime Shift Detection', latencyMs: 45 },
      },
      chatMessages: [
        ...get().chatMessages,
        {
          id: `MSG-RUN-${Date.now()}`,
          sender: 'user',
          text: `Bắt đầu kiểm tra bộ dữ liệu **${dataset.title}** (${dataset.records.toLocaleString()} bản ghi).`,
          timestamp: 'Vừa xong',
        },
        {
          id: `MSG-AI-RUN-${Date.now() + 1}`,
          sender: 'ai',
          text: `Tôi đang kích hoạt luồng kiểm soát tuân thủ **L1 -> L4** cho **${dataset.title}**. Bạn hãy theo dõi luồng phân tích trực tiếp trên Canvas bên phải.`,
          timestamp: 'Vừa xong',
        },
      ],
    });

    // Step L1
    await new Promise((r) => setTimeout(r, 650));
    set((s) => ({
      pipelineLevels: {
        ...s.pipelineLevels,
        currentLevel: 'L2',
        l1: { ...s.pipelineLevels.l1, status: 'done', progress: 100, scanned: dataset.records, passed: dataset.records - Math.floor(dataset.anomalies * 0.4), failed: Math.floor(dataset.anomalies * 0.4) },
        l2: { ...s.pipelineLevels.l2, status: 'running', progress: 35, scanned: Math.floor(dataset.records * 0.4), passed: Math.floor(dataset.records * 0.38), failed: 0, signalCount: 2 },
      }
    }));

    // Step L2
    await new Promise((r) => setTimeout(r, 700));
    set((s) => ({
      pipelineLevels: {
        ...s.pipelineLevels,
        currentLevel: 'L3',
        l2: { ...s.pipelineLevels.l2, status: 'done', progress: 100, scanned: dataset.records, passed: dataset.records - Math.floor(dataset.anomalies * 0.3), failed: Math.floor(dataset.anomalies * 0.3) },
        l3: { ...s.pipelineLevels.l3, status: 'running', progress: 40, scanned: Math.floor(dataset.records * 0.4), passed: Math.floor(dataset.records * 0.38), failed: 0, signalCount: 3 },
      }
    }));

    // Step L3
    await new Promise((r) => setTimeout(r, 700));
    set((s) => ({
      pipelineLevels: {
        ...s.pipelineLevels,
        currentLevel: 'L4',
        l3: { ...s.pipelineLevels.l3, status: 'done', progress: 100, scanned: dataset.records, passed: dataset.records - Math.floor(dataset.anomalies * 0.2), failed: Math.floor(dataset.anomalies * 0.2) },
        l4: { ...s.pipelineLevels.l4, status: 'running', progress: 50, scanned: Math.floor(dataset.records * 0.5), passed: Math.floor(dataset.records * 0.48), failed: 0, signalCount: 4 },
      }
    }));

    // Step L4 & finish
    await new Promise((r) => setTimeout(r, 800));
    const finalFailedL4 = Math.max(1, dataset.anomalies - Math.floor(dataset.anomalies * 0.4) - Math.floor(dataset.anomalies * 0.3) - Math.floor(dataset.anomalies * 0.2));
    const isAuditor = get().currentRole === 'auditor';

    set((s) => ({
      homepageViewMode: 'results_dashboard',
      pipelineLevels: {
        ...s.pipelineLevels,
        currentLevel: 'COMPLETED',
        l4: { ...s.pipelineLevels.l4, status: 'done', progress: 100, scanned: dataset.records, passed: dataset.records - finalFailedL4, failed: finalFailedL4 },
      },
      chatMessages: [
        ...s.chatMessages,
        {
          id: `MSG-RESULT-${Date.now()}`,
          sender: 'ai',
          text: `🚨 **Luồng L1-L4 đã hoàn tất! Phát hiện ${dataset.anomalies} vi phạm bất thường trên bộ dữ liệu ${dataset.title}**:\n` +
            (targetDatasetId === 'trips'
              ? `• **TC-REV-01**: 18 cuốc xe cước 0đ / cự ly âm (vi phạm IFRS 15).\n• **TC-PII-02**: 7 số điện thoại khách hàng dạng cleartext (vi phạm Nghị định 13/2023).\n\n`
              : targetDatasetId === 'customers'
              ? `• **TC-KYC-01**: 14 số CCCD/eID sai độ dài hoặc định dạng (Luật Căn cước).\n• 6 tài khoản disposable email.\n\n`
              : targetDatasetId === 'drivers'
              ? `• **TC-DRV-01**: 6 tài xế có GPLX hết hạn nhưng vẫn mở ca trực điều phối.\n\n`
              : targetDatasetId === 'charging'
              ? `• **TC-CHG-01**: 9 phiên sạc công tơ Modbus sai lệch vượt 3%.\n\n`
              : `• **TC-IOT-01**: 12 gói tin IoT nhiệt độ cell pin BMS vượt 65°C và 28 lỗi SoC âm.\n\n`) +
            (isAuditor
              ? `👉 Dữ liệu vi phạm đã tự động được cách ly khỏi luồng. Canvas bên phải đã chuyển sang **Dashboard Kết quả** để bạn kiểm tra chi tiết các vi phạm và bằng chứng kiểm toán.`
              : `👉 Tôi đã chuyển Canvas bên phải sang **Dashboard Kết quả** và đưa ra **${dataset.proposedRules.length} Đề xuất giải pháp khắc phục (Rule Proposals)**. Mời bạn thẩm định và duyệt (Human-in-the-Loop)!`),
          timestamp: 'Vừa xong',
          quickActions: isAuditor
            ? [
                { label: '📋 Yêu cầu sinh Test Case Auditor', actionType: 'TRIGGER_AUDIT_TESTCASES' },
                { label: '🔄 Đặt lại luồng', actionType: 'RESET_FLOW' },
              ]
            : [
                { label: '📋 Đề xuất Test Case Auditor', actionType: 'TRIGGER_AUDIT_TESTCASES' },
                { label: '📜 Đề xuất Rule từ Policy mới', actionType: 'TRIGGER_POLICY_RULE' },
                { label: '🔄 Đặt lại luồng', actionType: 'RESET_FLOW' },
              ],
        }
      ]
    }));
  },

  skipPipelineRunToResults: () => {
    const dataset = get().datasets[get().selectedDatasetId] || get().datasets.trips;
    set((s) => ({
      homepageViewMode: 'results_dashboard',
      pipelineLevels: {
        currentLevel: 'COMPLETED',
        l1: { ...s.pipelineLevels.l1, status: 'done', progress: 100, scanned: dataset.records, passed: dataset.records - 7, failed: 7 },
        l2: { ...s.pipelineLevels.l2, status: 'done', progress: 100, scanned: dataset.records, passed: dataset.records - 5, failed: 5 },
        l3: { ...s.pipelineLevels.l3, status: 'done', progress: 100, scanned: dataset.records, passed: dataset.records - 4, failed: 4 },
        l4: { ...s.pipelineLevels.l4, status: 'done', progress: 100, scanned: dataset.records, passed: dataset.records - 2, failed: 2 },
      },
    }));
  },

  sendUserChatMessage: (text: string) => {
    const userMsg: ChatMessageItem = {
      id: `USER-${Date.now()}`,
      sender: 'user',
      text,
      timestamp: 'Vừa xong',
    };
    set((s) => ({ chatMessages: [...s.chatMessages, userMsg] }));

    const lower = text.toLowerCase();
    setTimeout(() => {
      let aiReply = '';
      let quickActions = undefined;
      const role = get().currentRole;

      if (lower.includes('trips') || lower.includes('chuyến đi') || lower.includes('chọn trips')) {
        get().startPipelineRun('trips');
        return;
      } else if (lower.includes('customers') || lower.includes('khách hàng')) {
        get().startPipelineRun('customers');
        return;
      } else if (lower.includes('drivers') || lower.includes('tài xế')) {
        get().startPipelineRun('drivers');
        return;
      } else if (lower.includes('charging') || lower.includes('trạm sạc')) {
        get().startPipelineRun('charging');
        return;
      } else if (lower.includes('telemetry') || lower.includes('pin') || lower.includes('viễn thông')) {
        get().startPipelineRun('telemetry');
        return;
      } else if (lower.includes('test case') || lower.includes('auditor') || lower.includes('kiểm toán') || lower.includes('sinh test case')) {
        aiReply = `📋 **Bộ kịch bản kiểm toán đề xuất cho Auditor (Chuẩn IPO / SOX 404 & IFRS 15)**:\n\n1. **TC-REV-01 (Hiện hữu & Đo lường doanh thu)**: Thẩm tra 100% cuốc xe có \`fare_amount > 0\` và \`trip_distance_km >= 0.1\`. Khóa chặn rủi ro ghi nhận doanh thu khống.\n2. **TC-PII-02 (Bảo vệ dữ liệu cá nhân Nghị định 13/2023)**: Thẩm tra các trường SĐT/CCCD xem đã được hash salt và dynamic masking trước khi vào Silver stream chưa.\n3. **TC-CUTOFF-03 (Tính đúng kỳ Cut-off)**: Thẩm tra timestamp cuốc xe theo múi giờ 24 quốc gia để tránh lệch kỳ báo cáo tài chính.\n4. **TC-IOT-04 (Chất lượng Telemetry xe điện)**: Kiểm toán tín hiệu SoC và nhiệt độ cell pin BMS, lọc sạch gói tin nhiễu trước khi đối soát trạm sạc.`;
        quickActions = [
          { label: '🚀 Chạy kiểm soát trips', actionType: 'SELECT_AND_RUN', payload: 'trips' },
          { label: '🔄 Đặt lại luồng', actionType: 'RESET_FLOW' },
        ];
      } else if (lower.includes('policy') || lower.includes('chính sách') || lower.includes('luật') || lower.includes('rule mới') || lower.includes('giải pháp') || lower.includes('đề xuất rule')) {
        if (role === 'auditor') {
          aiReply = `⚠️ **Thông báo phân quyền (Auditor - Viewer)**:\n\nBạn đang đăng nhập với vai trò **Auditor**. Ở vai trò này:\n• Bạn có quyền **yêu cầu sinh Test Case kiểm toán** (hãy gõ *"sinh test case"* hoặc click nút bên dưới).\n• **AI sẽ không đề xuất giải pháp/rule** và bạn không có quyền phê duyệt rule.\n\n👉 Vui lòng chuyển sang tài khoản **Admin** ở thanh trên cùng để mở khóa tính năng đề xuất giải pháp và phê duyệt rule!`;
          quickActions = [
            { label: '📋 Yêu cầu sinh Test Case Auditor', actionType: 'TRIGGER_AUDIT_TESTCASES' },
            { label: '🚀 Chạy kiểm soát trips', actionType: 'SELECT_AND_RUN', payload: 'trips' },
            { label: '🔄 Đặt lại luồng', actionType: 'RESET_FLOW' },
          ];
        } else {
          aiReply = `📜 **Đề xuất Rule tự động từ Văn bản Chính sách (Policy Ingestion)**:\n\n• **Chính sách nguồn**: *Nghị định 13/2023/NĐ-CP & GDPR Điều 5*\n• **Ràng buộc trích xuất**: Dữ liệu PII của khách hàng không được lưu trữ plain text ở môi trường Analytics.\n• **Đề xuất Rule**: \`mask_phone(customer_phone) WHEN role != 'Admin'\`\n• **Làn triển khai**: Dynamic Masking Gateway.\n\nBạn có thể duyệt nhanh quy tắc này ở tab **Quản lý Rule**!`;
          quickActions = [
            { label: '📜 Đề xuất Rule từ Policy mới', actionType: 'TRIGGER_POLICY_RULE' },
            { label: '🚀 Chạy kiểm soát trips', actionType: 'SELECT_AND_RUN', payload: 'trips' },
            { label: '🔄 Đặt lại luồng', actionType: 'RESET_FLOW' },
          ];
        }
      } else if (lower.includes('chọn dataset') || lower.includes('dataset') || lower.includes('danh sách bảng') || lower.includes('chọn bảng')) {
        aiReply = `Dưới đây là danh sách các bộ dữ liệu sẵn sàng kiểm soát tuân thủ. Hãy chọn 1 bảng để tôi quét luồng L1 -> L4:`;
        quickActions = [
          { label: '🚖 trips', actionType: 'SELECT_AND_RUN', payload: 'trips' },
          { label: '👥 customers', actionType: 'SELECT_AND_RUN', payload: 'customers' },
          { label: '🚗 drivers', actionType: 'SELECT_AND_RUN', payload: 'drivers' },
          { label: '⚡ charging', actionType: 'SELECT_AND_RUN', payload: 'charging' },
          { label: '🔋 telemetry', actionType: 'SELECT_AND_RUN', payload: 'telemetry' },
        ];
      } else {
        aiReply = `Tôi hiểu bạn đang quan tâm đến "${text}". Bạn có thể chọn nhanh các tác vụ điều phối sau:`;
        quickActions = role === 'auditor'
          ? [
              { label: '📋 Yêu cầu sinh Test Case Auditor', actionType: 'TRIGGER_AUDIT_TESTCASES' },
              { label: '🚀 Chạy kiểm soát trips', actionType: 'SELECT_AND_RUN', payload: 'trips' },
              { label: '🔄 Đặt lại luồng', actionType: 'RESET_FLOW' },
            ]
          : [
              { label: '🚀 Chạy kiểm soát trips', actionType: 'SELECT_AND_RUN', payload: 'trips' },
              { label: '📋 Đề xuất Test Case Auditor', actionType: 'TRIGGER_AUDIT_TESTCASES' },
              { label: '📜 Đề xuất Rule từ Policy mới', actionType: 'TRIGGER_POLICY_RULE' },
              { label: '🔄 Đặt lại luồng', actionType: 'RESET_FLOW' },
            ];
      }

      set((s) => ({
        chatMessages: [
          ...s.chatMessages,
          {
            id: `AI-${Date.now()}`,
            sender: 'ai',
            text: aiReply,
            timestamp: 'Vừa xong',
            quickActions,
          },
        ],
      }));
    }, 450);
  },

  resetHomepageFlow: () => {
    set({
      homepageViewMode: 'welcome',
      pipelineLevels: initialPipelineLevels,
      chatMessages: initialChatMessages,
    });
  },

  simulateDryRun: async (ruleId: string) => {
    await new Promise((r) => setTimeout(r, 600));
    set((s) => ({
      chatMessages: [
        ...s.chatMessages,
        {
          id: `DRY-${Date.now()}`,
          sender: 'ai',
          text: `🧪 **Kết quả chạy thử nghiệm (Dry-Run)** cho Rule \`${ruleId}\`:\n• **Dữ liệu quét**: 12,480 bản ghi mẫu\n• **Dữ liệu sạch (Silver Clean)**: 12,469 bản ghi (99.91%)\n• **Cách ly an toàn (Quarantine)**: 11 bản ghi (0.09%)\n• **Độ trễ gia tăng (Latency Overhead)**: +1.2ms (Hoàn toàn đạt chuẩn SLA real-time).`,
          timestamp: 'Vừa xong',
        }
      ]
    }));
  },

  toggleActiveRuleStatus: (ruleId: string) => {
    if (get().currentRole === 'auditor') return;

    set((s) => ({
      activeRules: s.activeRules.map((r) =>
        r.id === ruleId ? { ...r, status: r.status === 'active' ? 'paused' : 'active' } : r
      )
    }));
  },
}));
