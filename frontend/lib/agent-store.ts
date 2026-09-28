import { create } from 'zustand';
import { apiBridge, type ComplianceCheckRule, type DataTreatmentRule } from './api-bridge';

export type { ComplianceCheckRule, DataTreatmentRule };

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
  filename: string;
  title: string;
  records: number;
  anomalies: number | null;
  isProfiled?: boolean;
  zones?: string[];
  zoneCounts?: Record<string, number>;
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
    datasetId: 'ride_hailing_xanh_sm_trips.csv',
    datasetName: 'ride_hailing_xanh_sm_trips.csv',
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
    datasetId: 'acn_charging_mapped.csv',
    datasetName: 'acn_charging_mapped.csv',
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
    datasetId: 'synthetic_ev_telemetry_ved_ref.csv',
    datasetName: 'synthetic_ev_telemetry_ved_ref.csv',
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
    text: `Chào bạn! Tôi là **DataTrust AI Orchestrator**. Tôi sẽ đồng hành cùng bạn kiểm soát chất lượng dữ liệu, bảo vệ dữ liệu cá nhân (PII) và thẩm tra bằng chứng tuân thủ chuẩn IPO cho **3-Zone Pilot (VN, US, EU)**.

Để bắt đầu, hãy chọn 1 bộ dữ liệu thực tế để tôi quét profiling và chạy luồng kiểm soát từ **L1 đến L4**:`,
    timestamp: 'Vừa xong',
    quickActions: [
      { label: '📄 ride_hailing_xanh_sm_trips.csv (10,382)', actionType: 'SELECT_AND_RUN', payload: 'ride_hailing_xanh_sm_trips.csv' },
      { label: '📄 synthetic_ev_telemetry_ved_ref.csv (86,400)', actionType: 'SELECT_AND_RUN', payload: 'synthetic_ev_telemetry_ved_ref.csv' },
      { label: '📄 acn_charging_mapped.csv (1,331)', actionType: 'SELECT_AND_RUN', payload: 'acn_charging_mapped.csv' },
      { label: '📄 nlp_benchmark_uit_vsfc.csv (500)', actionType: 'SELECT_AND_RUN', payload: 'nlp_benchmark_uit_vsfc.csv' },
      { label: '📄 fleet_index.csv (60)', actionType: 'SELECT_AND_RUN', payload: 'fleet_index.csv' },
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

export const initialComplianceCheckRules: ComplianceCheckRule[] = [
  {
    rule_id: 'CHK-TRIP-FARE',
    dataset_id: 'ride_hailing_xanh_sm_trips.csv',
    column_name: 'fare_amount',
    rule_name: 'Thẩm tra doanh thu cước & cự ly chuyến đi',
    rule_code: 'VAL-FARE-01',
    expression: 'fare_amount > 0 AND trip_distance_km >= 0.1',
    description: 'Bảo đảm 100% cuốc xe phát sinh doanh thu hợp lệ, chống gian lận cước ảo',
    law_ref: 'IFRS 15 / SOX 404',
    severity: 'CRITICAL',
    on_fail_action: 'QUARANTINE',
    is_fixed: true,
    enforced_at: '2026-09-27T08:00:00Z',
  },
  {
    rule_id: 'CHK-TRIP-GPS',
    dataset_id: 'ride_hailing_xanh_sm_trips.csv',
    column_name: 'pickup_latitude',
    rule_name: 'Kiểm tra tọa độ GPS đón khách',
    rule_code: 'VAL-GPS-02',
    expression: 'pickup_latitude BETWEEN 8.0 AND 24.0 AND pickup_longitude BETWEEN 102.0 AND 110.0',
    description: 'Xác thực tọa độ đón khách nằm trong phạm vi lãnh thổ và vùng dịch vụ hợp lệ',
    law_ref: 'TCVN 12823:2020',
    severity: 'HIGH',
    on_fail_action: 'QUARANTINE',
    is_fixed: true,
    enforced_at: '2026-09-27T08:00:00Z',
  },
  {
    rule_id: 'CHK-TELEM-TEMP',
    dataset_id: 'synthetic_ev_telemetry_ved_ref.csv',
    column_name: 'battery_temp_c',
    rule_name: 'Ngưỡng nhiệt độ an toàn khối pin BMS',
    rule_code: 'VAL-TEMP-01',
    expression: 'battery_temp_c >= -10.0 AND battery_temp_c <= 60.0',
    description: 'Cảnh báo và cách ly các gói tin telemetry có nhiệt độ vượt ngưỡng an toàn nhiệt động học',
    law_ref: 'ISO 26262 ASIL-D',
    severity: 'CRITICAL',
    on_fail_action: 'QUARANTINE',
    is_fixed: true,
    enforced_at: '2026-09-27T08:00:00Z',
  },
  {
    rule_id: 'CHK-TELEM-SOC',
    dataset_id: 'synthetic_ev_telemetry_ved_ref.csv',
    column_name: 'battery_soc',
    rule_name: 'Giới hạn tỷ lệ sạc trạng thái pin (SoC)',
    rule_code: 'VAL-SOC-02',
    expression: 'battery_soc >= 0.0 AND battery_soc <= 100.0',
    description: 'Chỉ số phần trăm dung lượng pin bắt buộc nằm trong khoảng vật lý 0% - 100%',
    law_ref: 'UN R100 Rev 2',
    severity: 'HIGH',
    on_fail_action: 'QUARANTINE',
    is_fixed: true,
    enforced_at: '2026-09-27T08:00:00Z',
  },
  {
    rule_id: 'CHK-CHG-METER',
    dataset_id: 'acn_charging_mapped.csv',
    column_name: 'energy_kwh',
    rule_name: 'Đối soát điện năng sạc & chi phí thanh toán',
    rule_code: 'VAL-CHG-01',
    expression: 'energy_kwh > 0.0 AND cost_vnd >= 0.0',
    description: 'Xác thực phiên sạc hợp lệ có điện năng tiêu thụ thực tế và chi phí không âm',
    law_ref: 'Đo lường điện lực EVN / IEC 61851',
    severity: 'CRITICAL',
    on_fail_action: 'QUARANTINE',
    is_fixed: true,
    enforced_at: '2026-09-27T08:00:00Z',
  },
];

export const initialDataTreatmentRules: DataTreatmentRule[] = [
  {
    rule_id: 'TRT-TRIP-PHONE',
    dataset_id: 'ride_hailing_xanh_sm_trips.csv',
    column_name: 'customer_phone',
    operation_id: 'mask_phone',
    treatment_name: 'Che mờ số điện thoại khách hàng',
    params_json: { prefix_len: 3, suffix_len: 2, mask_char: '*' },
    expression_display: 'mask_phone(customer_phone)',
    description: 'Bảo vệ thông tin liên lạc khách hàng theo Nghị định 13/2023',
    is_ai_proposed: false,
    status: 'active',
    enforced_by: 'Nguyễn Quốc Bảo (Lead Platform)',
    created_at: '2026-09-27T08:00:00Z',
    updated_at: '2026-09-27T08:00:00Z',
  },
  {
    rule_id: 'TRT-TRIP-DRIVER',
    dataset_id: 'ride_hailing_xanh_sm_trips.csv',
    column_name: 'driver_id',
    operation_id: 'hash_sha256',
    treatment_name: 'Mã hóa một chiều định danh tài xế',
    params_json: { algorithm: 'sha256' },
    expression_display: 'hash_sha256(driver_id)',
    description: 'Bí danh hóa mã tài xế đối tác GSM',
    is_ai_proposed: false,
    status: 'active',
    enforced_by: 'Nguyễn Quốc Bảo (Lead Platform)',
    created_at: '2026-09-27T08:00:00Z',
    updated_at: '2026-09-27T08:00:00Z',
  },
  {
    rule_id: 'TRT-TRIP-GPS',
    dataset_id: 'ride_hailing_xanh_sm_trips.csv',
    column_name: 'pickup_latitude',
    operation_id: 'round_decimal',
    treatment_name: 'Làm tròn tọa độ GPS đón khách',
    params_json: { decimals: 2 },
    expression_display: 'round_decimal(pickup_latitude, 2)',
    description: 'Làm mờ tọa độ GPS đón khách độ chính xác ~1km bảo vệ nơi ở',
    is_ai_proposed: false,
    status: 'active',
    enforced_by: 'Nguyễn Quốc Bảo (Lead Platform)',
    created_at: '2026-09-27T08:00:00Z',
    updated_at: '2026-09-27T08:00:00Z',
  },
  {
    rule_id: 'TRT-PROP-PHONE',
    dataset_id: 'ride_hailing_xanh_sm_trips.csv',
    column_name: 'customer_phone',
    operation_id: 'mask_phone',
    treatment_name: 'Che mờ số điện thoại khách hàng (Cải tiến)',
    params_json: { prefix_len: 3, suffix_len: 2, mask_char: '*' },
    expression_display: 'mask_phone(customer_phone, prefix=3, suffix=2)',
    description: 'Che mờ số điện thoại khách đặt xe',
    is_ai_proposed: true,
    ai_rationale: 'AI phát hiện số điện thoại khách hàng dạng cleartext, đề xuất che mờ bảo vệ dữ liệu theo Nghị định 13/2023.',
    ai_confidence: 0.965,
    status: 'pending',
    enforced_by: 'AI Treatment Proposer',
    created_at: '2026-09-28T09:00:00Z',
    updated_at: '2026-09-28T09:00:00Z',
  },
  {
    rule_id: 'TRT-PROP-NAME',
    dataset_id: 'ride_hailing_xanh_sm_trips.csv',
    column_name: 'customer_name',
    operation_id: 'mask_name',
    treatment_name: 'Che mờ họ tên khách hàng',
    params_json: { keep_first: true, mask_char: '*' },
    expression_display: 'mask_name(customer_name)',
    description: 'Che mờ họ tên hành khách',
    is_ai_proposed: true,
    ai_rationale: 'Họ tên khách hàng cần được ẩn danh tên riêng theo quy định bảo vệ dữ liệu cá nhân.',
    ai_confidence: 0.940,
    status: 'pending',
    enforced_by: 'AI Treatment Proposer',
    created_at: '2026-09-28T09:00:00Z',
    updated_at: '2026-09-28T09:00:00Z',
  },
  {
    rule_id: 'TRT-PROP-VIN',
    dataset_id: 'synthetic_ev_telemetry_ved_ref.csv',
    column_name: 'vehicle_vin',
    operation_id: 'to_upper',
    treatment_name: 'Chuẩn hóa mã VIN in hoa',
    params_json: {},
    expression_display: 'to_upper(vehicle_vin)',
    description: 'Chuẩn hóa chuỗi ký tự mã VIN xe',
    is_ai_proposed: true,
    ai_rationale: 'AI phát hiện một số gói tin telemetry có mã VIN chữ thường, đề xuất chuẩn hóa in hoa chuẩn ISO 3779.',
    ai_confidence: 0.980,
    status: 'pending',
    enforced_by: 'AI Treatment Proposer',
    created_at: '2026-09-28T09:00:00Z',
    updated_at: '2026-09-28T09:00:00Z',
  },
];

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

  // Fixed Compliance Check Rules (Backend Only, Read-Only, No AI Proposals)
  complianceCheckRules: ComplianceCheckRule[];
  // Data Treatment Rules (Generic, AI Proposed Noted Separately, UI Editable)
  dataTreatmentRules: DataTreatmentRule[];
  rulesMainTab: 'treatments' | 'compliance_checks';
  setRulesMainTab: (tab: 'treatments' | 'compliance_checks') => void;
  updateTreatmentRuleExpression: (ruleId: string, newExpr: string, paramsJson?: any) => Promise<void>;
  approveTreatmentRule: (ruleId: string) => Promise<void>;
  rejectTreatmentRule: (ruleId: string, comments?: string) => Promise<void>;
  toggleTreatmentRuleStatus: (ruleId: string) => Promise<void>;

  // Backend Live Integration & Fallback
  isBackendLive: boolean;
  isSyncing: boolean;
  syncError: string | null;
  syncWithBackend: () => Promise<void>;
}

export const normalizeDatasetId = (id: string): string => {
  const map: Record<string, string> = {
    'trips': 'ride_hailing_xanh_sm_trips.csv',
    'ride_hailing_xanh_sm_trips': 'ride_hailing_xanh_sm_trips.csv',
    'ride_hailing_xanh_sm_trips.csv': 'ride_hailing_xanh_sm_trips.csv',
    'telemetry': 'synthetic_ev_telemetry_ved_ref.csv',
    'synthetic_ev_telemetry_ved_ref': 'synthetic_ev_telemetry_ved_ref.csv',
    'synthetic_ev_telemetry_ved_ref.csv': 'synthetic_ev_telemetry_ved_ref.csv',
    'charging': 'acn_charging_mapped.csv',
    'acn_charging_mapped': 'acn_charging_mapped.csv',
    'acn_charging_mapped.csv': 'acn_charging_mapped.csv',
    'nlp_feedback': 'nlp_benchmark_uit_vsfc.csv',
    'nlp_benchmark_uit_vsfc': 'nlp_benchmark_uit_vsfc.csv',
    'nlp_benchmark_uit_vsfc.csv': 'nlp_benchmark_uit_vsfc.csv',
    'fleet': 'fleet_index.csv',
    'fleet_index': 'fleet_index.csv',
    'fleet_index.csv': 'fleet_index.csv',
  };
  return map[id] || (id.endsWith('.csv') ? id : `${id}.csv`);
};

const initialDatasets: Record<string, DatasetItem> = {
  'ride_hailing_xanh_sm_trips.csv': {
    id: 'ride_hailing_xanh_sm_trips.csv',
    name: 'ride_hailing_xanh_sm_trips.csv',
    filename: 'ride_hailing_xanh_sm_trips.csv',
    title: 'ride_hailing_xanh_sm_trips.csv',
    records: 10382,
    zones: ['VN', 'US', 'EU'],
    zoneCounts: { VN: 3515, US: 3444, EU: 3423 },
    isProfiled: false,
    anomalies: null,
    proposedRulesCount: 0,
    proposedRules: [],
  },
  'synthetic_ev_telemetry_ved_ref.csv': {
    id: 'synthetic_ev_telemetry_ved_ref.csv',
    name: 'synthetic_ev_telemetry_ved_ref.csv',
    filename: 'synthetic_ev_telemetry_ved_ref.csv',
    title: 'synthetic_ev_telemetry_ved_ref.csv',
    records: 86400,
    zones: ['VN', 'US', 'EU'],
    zoneCounts: { VN: 28800, US: 28800, EU: 28800 },
    isProfiled: false,
    anomalies: null,
    proposedRulesCount: 0,
    proposedRules: [],
  },
  'acn_charging_mapped.csv': {
    id: 'acn_charging_mapped.csv',
    name: 'acn_charging_mapped.csv',
    filename: 'acn_charging_mapped.csv',
    title: 'acn_charging_mapped.csv',
    records: 1331,
    zones: ['VN', 'US', 'EU'],
    zoneCounts: { VN: 445, US: 446, EU: 440 },
    isProfiled: false,
    anomalies: null,
    proposedRulesCount: 0,
    proposedRules: [],
  },
  'nlp_benchmark_uit_vsfc.csv': {
    id: 'nlp_benchmark_uit_vsfc.csv',
    name: 'nlp_benchmark_uit_vsfc.csv',
    filename: 'nlp_benchmark_uit_vsfc.csv',
    title: 'nlp_benchmark_uit_vsfc.csv',
    records: 500,
    zones: ['VN'],
    zoneCounts: { VN: 500 },
    isProfiled: false,
    anomalies: null,
    proposedRulesCount: 0,
    proposedRules: [],
  },
  'fleet_index.csv': {
    id: 'fleet_index.csv',
    name: 'fleet_index.csv',
    filename: 'fleet_index.csv',
    title: 'fleet_index.csv',
    records: 60,
    zones: ['VN', 'US', 'EU'],
    zoneCounts: { VN: 20, US: 20, EU: 20 },
    isProfiled: false,
    anomalies: null,
    proposedRulesCount: 0,
    proposedRules: [],
  },
};

// Aliases for backward compatibility
initialDatasets['trips'] = initialDatasets['ride_hailing_xanh_sm_trips.csv'];
initialDatasets['telemetry'] = initialDatasets['synthetic_ev_telemetry_ved_ref.csv'];
initialDatasets['charging'] = initialDatasets['acn_charging_mapped.csv'];
initialDatasets['nlp_feedback'] = initialDatasets['nlp_benchmark_uit_vsfc.csv'];
initialDatasets['fleet'] = initialDatasets['fleet_index.csv'];
initialDatasets['ride_hailing_xanh_sm_trips'] = initialDatasets['ride_hailing_xanh_sm_trips.csv'];
initialDatasets['synthetic_ev_telemetry_ved_ref'] = initialDatasets['synthetic_ev_telemetry_ved_ref.csv'];
initialDatasets['acn_charging_mapped'] = initialDatasets['acn_charging_mapped.csv'];
initialDatasets['nlp_benchmark_uit_vsfc'] = initialDatasets['nlp_benchmark_uit_vsfc.csv'];
initialDatasets['fleet_index'] = initialDatasets['fleet_index.csv'];

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
  setHomepageViewMode: (mode) => set({ homepageViewMode: mode }),
  pipelineLevels: initialPipelineLevels,
  chatMessages: initialChatMessages,
  activeRules: initialActiveRules,
  rulesSegmentTab: 'active',
  setRulesSegmentTab: (tab) => set({ rulesSegmentTab: tab }),

  // Fixed Compliance Check Rules (Backend Only, Read-Only, No AI Proposals)
  complianceCheckRules: initialComplianceCheckRules,
  // Data Treatment Rules (Generic, AI Proposed Noted Separately, UI Editable)
  dataTreatmentRules: initialDataTreatmentRules,
  rulesMainTab: 'treatments',
  setRulesMainTab: (tab) => set({ rulesMainTab: tab }),

  // Backend Live Integration & Fallback
  isBackendLive: false,
  isSyncing: false,
  syncError: null,

  syncWithBackend: async () => {
    set({ isSyncing: true, syncError: null });
    try {
      const isLive = await apiBridge.checkHealth();
      if (!isLive) {
        set({ isBackendLive: false, isSyncing: false });
        return;
      }
      const [backendActiveRules, backendProposedRules, backendComplianceRules, backendTreatmentRules] = await Promise.all([
        apiBridge.fetchActiveRules().catch(() => []),
        apiBridge.fetchProposedRules().catch(() => []),
        apiBridge.fetchComplianceCheckRules().catch(() => []),
        apiBridge.fetchDataTreatmentRules().catch(() => []),
      ]);

      set((state) => {
        const nextActive = backendActiveRules.length > 0 ? backendActiveRules : state.activeRules;
        const currentDs = state.datasets[state.selectedDatasetId];
        let nextDatasets = state.datasets;
        if (currentDs && backendProposedRules.length > 0) {
          nextDatasets = {
            ...state.datasets,
            [state.selectedDatasetId]: {
              ...currentDs,
              proposedRules: backendProposedRules,
              proposedRulesCount: backendProposedRules.filter((r) => r.status === 'pending').length,
            },
          };
        }
        return {
          isBackendLive: true,
          isSyncing: false,
          activeRules: nextActive,
          datasets: nextDatasets,
          complianceCheckRules: backendComplianceRules.length > 0 ? backendComplianceRules : state.complianceCheckRules,
          dataTreatmentRules: backendTreatmentRules.length > 0 ? backendTreatmentRules : state.dataTreatmentRules,
        };
      });
    } catch (err: any) {
      set({ isBackendLive: false, isSyncing: false, syncError: err?.message || 'Offline' });
    }
  },

  selectDataset: (id: string) => {
    const canonicalId = normalizeDatasetId(id);
    set({
      selectedDatasetId: canonicalId,
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

    // Call backend API if live
    if (get().isBackendLive) {
      apiBridge.approveRule(ruleId, 'Nguyễn Quốc Bảo (Admin)', 'ADMIN').catch((err) => {
        console.warn('Backend approve warning:', err);
      });
    }

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

    if (get().isBackendLive) {
      apiBridge.rejectRule(ruleId, 'Nguyễn Quốc Bảo (Admin)', 'ADMIN', 'Từ chối bởi Admin').catch((err) => {
        console.warn('Backend reject warning:', err);
      });
    }

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
    const targetDatasetId = normalizeDatasetId(datasetId || get().selectedDatasetId);
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

    // Kích hoạt luồng chạy trên Apache Airflow qua Backend API (nếu Backend đang online)
    if (get().isBackendLive) {
      apiBridge.triggerAirflow(targetDatasetId).then((res) => {
        console.log('[Airflow/Backend Trigger Result]:', res);
      }).catch((err) => {
        console.warn('[Airflow Trigger Warning]:', err);
      });
    }

    // Step L1
    const verifiedMap: Record<string, { count: number; rules: ProposedRule[]; summary: string }> = {
      ride_hailing_xanh_sm_trips: {
        count: 18,
        summary: `• **TC-REV-01**: 11 cuốc xe cước 0đ / cự ly âm (vi phạm IFRS 15 / SOX 404).\n• **TC-PII-02**: 7 số điện thoại khách hàng dạng cleartext (vi phạm Nghị định 13/2023 & GDPR).\n\n`,
        rules: [
          {
            id: 'RULE-TRIP-01',
            name: 'trip_fare_and_distance_positive',
            expression: 'fare_amount > 0 AND trip_distance_km >= 0.1',
            rationale: 'Phát hiện 11 chuyến đi có cước âm hoặc cự ly bằng 0 trong ride_hailing_xanh_sm_trips.csv.',
            domain: 'Data Quality',
            severity: 'CRITICAL',
            status: 'pending',
            confidence: 98,
            affectedRows: 11,
            evidenceId: 'EVID-TRIP-VAL-01',
            passRows: 10371,
            quarantineRows: 11,
            compiledTarget: 'SQL / PySpark Quarantine Lane',
            lawRef: 'IFRS 15 / SOX 404 Revenue Recognition',
          },
          {
            id: 'RULE-TRIP-02',
            name: 'customer_phone_masking',
            expression: 'mask_phone(customer_phone) WHEN role != "Admin"',
            rationale: 'Phát hiện 7 bản ghi chuyến đi ghi nhận số điện thoại khách hàng dạng cleartext (Nghị định 13/2023/NĐ-CP).',
            domain: 'Privacy & Data Protection',
            severity: 'HIGH',
            status: 'pending',
            confidence: 95,
            affectedRows: 7,
            evidenceId: 'EVID-PII-TRIP-02',
            passRows: 10375,
            quarantineRows: 7,
            compiledTarget: 'Dynamic Masking Engine',
            lawRef: 'Nghị định 13/2023/NĐ-CP & GDPR Art. 5',
          },
        ],
      },
      synthetic_ev_telemetry_ved_ref: {
        count: 28,
        summary: `• **TC-TEL-01**: 28 gói tin telemetry pin có nhiệt độ cell > 65°C hoặc SoC âm trong synthetic_ev_telemetry_ved_ref.csv.\n\n`,
        rules: [
          {
            id: 'RULE-TEL-01',
            name: 'battery_soc_and_temp_range',
            expression: 'battery_soc BETWEEN 0 AND 100 AND battery_temp_c <= 65',
            rationale: 'Phát hiện 28 gói tin cảm biến pin BMS quá nhiệt (>65°C) hoặc SoC âm trong 86,400 bản ghi telemetry.',
            domain: 'Data Quality',
            severity: 'CRITICAL',
            status: 'pending',
            confidence: 99,
            affectedRows: 28,
            evidenceId: 'EVID-TEL-01',
            passRows: 86372,
            quarantineRows: 28,
            compiledTarget: 'BMS Telemetry Ingestion Gate',
            lawRef: 'UN ECE R100 Battery Safety Standard',
          },
        ],
      },
      acn_charging_mapped: {
        count: 9,
        summary: `• **TC-CHG-01**: 9 phiên sạc công tơ Modbus sai lệch vượt 3% trong acn_charging_mapped.csv.\n\n`,
        rules: [
          {
            id: 'RULE-CHG-01',
            name: 'modbus_meter_delta_tolerance',
            expression: 'abs(meter_kwh_delta - bms_kwh_delta) <= 0.03 * meter_kwh_delta',
            rationale: 'Phát hiện 9 phiên sạc có chênh lệch công tơ trụ sạc và BMS vượt ngưỡng 3% chuẩn đo lường.',
            domain: 'Data Quality',
            severity: 'HIGH',
            status: 'pending',
            confidence: 96,
            affectedRows: 9,
            evidenceId: 'EVID-CHG-01',
            passRows: 1322,
            quarantineRows: 9,
            compiledTarget: 'Energy Billing Filter',
            lawRef: 'SOX 404 & Chuẩn Đo lường V-GREEN',
          },
        ],
      },
      nlp_benchmark_uit_vsfc: {
        count: 6,
        summary: `• **TC-NLP-01**: 6 phản hồi khách hàng chứa số điện thoại cá nhân dạng thô trong nlp_benchmark_uit_vsfc.csv.\n\n`,
        rules: [
          {
            id: 'RULE-NLP-01',
            name: 'redact_pii_customer_reviews',
            expression: 'mask_phone(sentence) WHEN contains_phone(sentence)',
            rationale: 'Phát hiện 6 phản hồi tự do của khách hàng chứa số điện thoại cần che giấu.',
            domain: 'Privacy & Data Protection',
            severity: 'HIGH',
            status: 'pending',
            confidence: 94,
            affectedRows: 6,
            evidenceId: 'EVID-NLP-01',
            passRows: 494,
            quarantineRows: 6,
            compiledTarget: 'NLP Anonymizer Gate',
            lawRef: 'Nghị định 13/2023/NĐ-CP Điều 17',
          },
        ],
      },
      fleet_index: {
        count: 0,
        summary: `• Toàn bộ 60 xe điện VinFast pilot phân bổ 3 vùng đều hợp lệ và sẵn sàng vận hành.\n\n`,
        rules: [],
      },
    };

    // Alias lookups
    verifiedMap['ride_hailing_xanh_sm_trips.csv'] = verifiedMap['ride_hailing_xanh_sm_trips'];
    verifiedMap['synthetic_ev_telemetry_ved_ref.csv'] = verifiedMap['synthetic_ev_telemetry_ved_ref'];
    verifiedMap['acn_charging_mapped.csv'] = verifiedMap['acn_charging_mapped'];
    verifiedMap['nlp_benchmark_uit_vsfc.csv'] = verifiedMap['nlp_benchmark_uit_vsfc'];
    verifiedMap['fleet_index.csv'] = verifiedMap['fleet_index'];
    verifiedMap['trips'] = verifiedMap['ride_hailing_xanh_sm_trips'];
    verifiedMap['telemetry'] = verifiedMap['synthetic_ev_telemetry_ved_ref'];
    verifiedMap['charging'] = verifiedMap['acn_charging_mapped'];
    verifiedMap['nlp_feedback'] = verifiedMap['nlp_benchmark_uit_vsfc'];
    verifiedMap['fleet'] = verifiedMap['fleet_index'];

    const targetProfile = verifiedMap[targetDatasetId] || verifiedMap['ride_hailing_xanh_sm_trips.csv'];
    const totalAnomalies = targetProfile.count;

    await new Promise((r) => setTimeout(r, 650));
    set((s) => ({
      pipelineLevels: {
        ...s.pipelineLevels,
        currentLevel: 'L2',
        l1: { ...s.pipelineLevels.l1, status: 'done', progress: 100, scanned: dataset.records, passed: dataset.records - Math.floor(totalAnomalies * 0.4), failed: Math.floor(totalAnomalies * 0.4) },
        l2: { ...s.pipelineLevels.l2, status: 'running', progress: 35, scanned: Math.floor(dataset.records * 0.4), passed: Math.floor(dataset.records * 0.38), failed: 0, signalCount: 2 },
      }
    }));

    // Step L2
    await new Promise((r) => setTimeout(r, 700));
    set((s) => ({
      pipelineLevels: {
        ...s.pipelineLevels,
        currentLevel: 'L3',
        l2: { ...s.pipelineLevels.l2, status: 'done', progress: 100, scanned: dataset.records, passed: dataset.records - Math.floor(totalAnomalies * 0.3), failed: Math.floor(totalAnomalies * 0.3) },
        l3: { ...s.pipelineLevels.l3, status: 'running', progress: 40, scanned: Math.floor(dataset.records * 0.4), passed: Math.floor(dataset.records * 0.38), failed: 0, signalCount: 3 },
      }
    }));

    // Step L3
    await new Promise((r) => setTimeout(r, 700));
    set((s) => ({
      pipelineLevels: {
        ...s.pipelineLevels,
        currentLevel: 'L4',
        l3: { ...s.pipelineLevels.l3, status: 'done', progress: 100, scanned: dataset.records, passed: dataset.records - Math.floor(totalAnomalies * 0.2), failed: Math.floor(totalAnomalies * 0.2) },
        l4: { ...s.pipelineLevels.l4, status: 'running', progress: 50, scanned: Math.floor(dataset.records * 0.5), passed: Math.floor(dataset.records * 0.48), failed: 0, signalCount: 4 },
      }
    }));

    // Step L4 & finish
    await new Promise((r) => setTimeout(r, 800));
    const finalFailedL4 = Math.max(0, totalAnomalies - Math.floor(totalAnomalies * 0.4) - Math.floor(totalAnomalies * 0.3) - Math.floor(totalAnomalies * 0.2));
    const isAuditor = get().currentRole === 'auditor';

    set((s) => {
      const updatedDs: DatasetItem = {
        ...dataset,
        isProfiled: true,
        anomalies: totalAnomalies,
        proposedRulesCount: targetProfile.rules.length,
        proposedRules: targetProfile.rules,
      };

      const nextDatasets = {
        ...s.datasets,
        [targetDatasetId]: updatedDs,
      };

      return {
        datasets: nextDatasets,
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
            text: `🚨 **Luồng L1-L4 đã hoàn tất! Phát hiện ${totalAnomalies} vi phạm bất thường trên bộ dữ liệu ${dataset.filename || dataset.title}**:\n` +
              targetProfile.summary +
              (isAuditor
                ? `👉 Dữ liệu vi phạm đã tự động được cách ly vào Quarantine. Canvas bên phải đã chuyển sang **Dashboard Kết quả** để bạn kiểm tra chi tiết các vi phạm và bằng chứng kiểm toán.`
                : `👉 Tôi đã chuyển Canvas bên phải sang **Dashboard Kết quả** và đưa ra **${targetProfile.rules.length} Đề xuất giải pháp khắc phục (Rule Proposals)**. Mời bạn thẩm định và duyệt (Human-in-the-Loop)!`),
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
      };
    });
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
        get().startPipelineRun('ride_hailing_xanh_sm_trips.csv');
        return;
      } else if (lower.includes('charging') || lower.includes('trạm sạc')) {
        get().startPipelineRun('acn_charging_mapped.csv');
        return;
      } else if (lower.includes('telemetry') || lower.includes('pin') || lower.includes('viễn thông')) {
        get().startPipelineRun('synthetic_ev_telemetry_ved_ref.csv');
        return;
      } else if (lower.includes('nlp') || lower.includes('đánh giá') || lower.includes('phản hồi')) {
        get().startPipelineRun('nlp_benchmark_uit_vsfc.csv');
        return;
      } else if (lower.includes('fleet') || lower.includes('đội xe')) {
        get().startPipelineRun('fleet_index.csv');
        return;
      } else if (lower.includes('test case') || lower.includes('auditor') || lower.includes('kiểm toán') || lower.includes('sinh test case')) {
        aiReply = `📋 **Bộ kịch bản kiểm toán đề xuất cho Auditor (Chuẩn IPO / SOX 404 & IFRS 15)**:\n\n1. **TC-REV-01 (Hiện hữu & Đo lường doanh thu)**: Thẩm tra 100% cuốc xe có \`fare_amount > 0\` và \`trip_distance_km >= 0.1\`. Khóa chặn rủi ro ghi nhận doanh thu khống.\n2. **TC-PII-02 (Bảo vệ dữ liệu cá nhân Nghị định 13/2023)**: Thẩm tra các trường SĐT/CCCD xem đã được hash salt và dynamic masking trước khi vào Silver stream chưa.\n3. **TC-CUTOFF-03 (Tính đúng kỳ Cut-off)**: Thẩm tra timestamp cuốc xe theo múi giờ 24 quốc gia để tránh lệch kỳ báo cáo tài chính.\n4. **TC-IOT-04 (Chất lượng Telemetry xe điện)**: Kiểm toán tín hiệu SoC và nhiệt độ cell pin BMS, lọc sạch gói tin nhiễu trước khi đối soát trạm sạc.`;
        quickActions = [
          { label: '🚀 Chạy ride_hailing_xanh_sm_trips.csv', actionType: 'SELECT_AND_RUN', payload: 'ride_hailing_xanh_sm_trips.csv' },
          { label: '🔄 Đặt lại luồng', actionType: 'RESET_FLOW' },
        ];
      } else if (lower.includes('policy') || lower.includes('chính sách') || lower.includes('luật') || lower.includes('rule mới') || lower.includes('giải pháp') || lower.includes('đề xuất rule')) {
        if (role === 'auditor') {
          aiReply = `⚠️ **Thông báo phân quyền (Auditor - Viewer)**:\n\nBạn đang đăng nhập với vai trò **Auditor**. Ở vai trò này:\n• Bạn có quyền **yêu cầu sinh Test Case kiểm toán** (hãy gõ *"sinh test case"* hoặc click nút bên dưới).\n• **AI sẽ không đề xuất giải pháp/rule** và bạn không có quyền phê duyệt rule.\n\n👉 Vui lòng chuyển sang tài khoản **Admin** ở thanh trên cùng để mở khóa tính năng đề xuất giải pháp và phê duyệt rule!`;
          quickActions = [
            { label: '📋 Yêu cầu sinh Test Case Auditor', actionType: 'TRIGGER_AUDIT_TESTCASES' },
            { label: '🚀 Chạy ride_hailing_xanh_sm_trips.csv', actionType: 'SELECT_AND_RUN', payload: 'ride_hailing_xanh_sm_trips.csv' },
            { label: '🔄 Đặt lại luồng', actionType: 'RESET_FLOW' },
          ];
        } else {
          aiReply = `📜 **Đề xuất Rule tự động từ Văn bản Chính sách (Policy Ingestion)**:\n\n• **Chính sách nguồn**: *Nghị định 13/2023/NĐ-CP & GDPR Điều 5*\n• **Ràng buộc trích xuất**: Dữ liệu PII của khách hàng không được lưu trữ plain text ở môi trường Analytics.\n• **Đề xuất Rule**: \`mask_phone(customer_phone) WHEN role != 'Admin'\`\n• **Làn triển khai**: Dynamic Masking Gateway.\n\nBạn có thể duyệt nhanh quy tắc này ở tab **Quản lý Rule**!`;
          quickActions = [
            { label: '📜 Đề xuất Rule từ Policy mới', actionType: 'TRIGGER_POLICY_RULE' },
            { label: '🚀 Chạy ride_hailing_xanh_sm_trips.csv', actionType: 'SELECT_AND_RUN', payload: 'ride_hailing_xanh_sm_trips.csv' },
            { label: '🔄 Đặt lại luồng', actionType: 'RESET_FLOW' },
          ];
        }
      } else if (lower.includes('chọn dataset') || lower.includes('dataset') || lower.includes('danh sách bảng') || lower.includes('chọn bảng')) {
        aiReply = `Dưới đây là danh sách các bộ dữ liệu sẵn sàng kiểm soát tuân thủ. Hãy chọn 1 bảng để tôi quét luồng L1 -> L4:`;
        quickActions = [
          { label: '📄 ride_hailing_xanh_sm_trips.csv', actionType: 'SELECT_AND_RUN', payload: 'ride_hailing_xanh_sm_trips.csv' },
          { label: '📄 synthetic_ev_telemetry_ved_ref.csv', actionType: 'SELECT_AND_RUN', payload: 'synthetic_ev_telemetry_ved_ref.csv' },
          { label: '📄 acn_charging_mapped.csv', actionType: 'SELECT_AND_RUN', payload: 'acn_charging_mapped.csv' },
          { label: '📄 nlp_benchmark_uit_vsfc.csv', actionType: 'SELECT_AND_RUN', payload: 'nlp_benchmark_uit_vsfc.csv' },
          { label: '📄 fleet_index.csv', actionType: 'SELECT_AND_RUN', payload: 'fleet_index.csv' },
        ];
      } else {
        aiReply = `Tôi hiểu bạn đang quan tâm đến "${text}". Bạn có thể chọn nhanh các tác vụ điều phối sau:`;
        quickActions = role === 'auditor'
          ? [
              { label: '📋 Yêu cầu sinh Test Case Auditor', actionType: 'TRIGGER_AUDIT_TESTCASES' },
              { label: '🚀 Chạy ride_hailing_xanh_sm_trips.csv', actionType: 'SELECT_AND_RUN', payload: 'ride_hailing_xanh_sm_trips.csv' },
              { label: '🔄 Đặt lại luồng', actionType: 'RESET_FLOW' },
            ]
          : [
              { label: '🚀 Chạy ride_hailing_xanh_sm_trips.csv', actionType: 'SELECT_AND_RUN', payload: 'ride_hailing_xanh_sm_trips.csv' },
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

  updateTreatmentRuleExpression: async (ruleId: string, newExpr: string, paramsJson?: any) => {
    if (get().currentRole === 'auditor') return;
    if (get().isBackendLive) {
      try {
        await apiBridge.updateTreatmentRuleExpression(ruleId, newExpr, paramsJson);
      } catch (e) {
        console.warn('Backend update treatment error:', e);
      }
    }
    set((s) => ({
      dataTreatmentRules: s.dataTreatmentRules.map((r) =>
        r.rule_id === ruleId
          ? { ...r, expression_display: newExpr, ...(paramsJson ? { params_json: paramsJson } : {}), updated_at: new Date().toISOString() }
          : r
      ),
    }));
  },

  approveTreatmentRule: async (ruleId: string) => {
    if (get().currentRole === 'auditor') return;
    if (get().isBackendLive) {
      try {
        await apiBridge.approveTreatmentRule(ruleId, 'Nguyễn Quốc Bảo', 'ADMIN');
      } catch (e) {
        console.warn('Backend approve treatment error:', e);
      }
    }
    set((s) => ({
      dataTreatmentRules: s.dataTreatmentRules.map((r) =>
        r.rule_id === ruleId
          ? { ...r, status: 'active', enforced_by: 'Nguyễn Quốc Bảo (Lead Platform)', updated_at: new Date().toISOString() }
          : r
      ),
    }));
  },

  rejectTreatmentRule: async (ruleId: string, comments?: string) => {
    if (get().currentRole === 'auditor') return;
    if (get().isBackendLive) {
      try {
        await apiBridge.rejectTreatmentRule(ruleId, 'Nguyễn Quốc Bảo', 'ADMIN', comments);
      } catch (e) {
        console.warn('Backend reject treatment error:', e);
      }
    }
    set((s) => ({
      dataTreatmentRules: s.dataTreatmentRules.map((r) =>
        r.rule_id === ruleId
          ? { ...r, status: 'rejected', updated_at: new Date().toISOString() }
          : r
      ),
    }));
  },

  toggleTreatmentRuleStatus: async (ruleId: string) => {
    if (get().currentRole === 'auditor') return;
    if (get().isBackendLive) {
      try {
        await apiBridge.toggleTreatmentRule(ruleId);
      } catch (e) {
        console.warn('Backend toggle treatment error:', e);
      }
    }
    set((s) => ({
      dataTreatmentRules: s.dataTreatmentRules.map((r) => {
        if (r.rule_id === ruleId) {
          const nextStatus = r.status === 'active' ? 'paused' : 'active';
          return { ...r, status: nextStatus, updated_at: new Date().toISOString() };
        }
        return r;
      }),
    }));
  },
}));
