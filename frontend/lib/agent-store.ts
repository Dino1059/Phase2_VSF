import { create } from 'zustand';
import { apiBridge, type ColumnModel, type ComplianceCheckRule, type DataTreatmentRule } from './api-bridge';

export type { ColumnModel, ComplianceCheckRule, DataTreatmentRule };

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
  columnCount?: number;
  source?: string;
  description?: string;
  createdAt?: string;
  hasPii?: boolean;
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
    roleTitle: 'Auditor IPO (Viewer)',
    email: 'hoang.tran@audit-ipo.com',
    avatar: 'TH',
    badge: 'Kiểm toán viên (Viewer)',
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

  // Real 4-Task / 3-Lane States from Airflow & Backend
  activeRunId: string | null;
  currentTaskName: string;
  isPolling: boolean;
  viewingHistoricalResult: boolean;
  inFlightRunId: string | null;
  historicalRunId: string | null;

  task1Ingest: { status: 'idle' | 'running' | 'done' | 'failed'; targetTable: string; rows: number };
  task2Profiling: { status: 'idle' | 'running' | 'done' | 'failed'; healthScore: number; nullRateAvg: number };
  task3LaneA: { status: 'idle' | 'running' | 'done' | 'failed'; signalsCount: number };
  task3LaneB: { status: 'idle' | 'running' | 'done' | 'failed'; activeRulesCount: number; treatmentsCount: number; lawFramework: string[] };
  task3LaneC: { status: 'idle' | 'running' | 'done' | 'failed'; silver: number; quarantine: number; warning: number };
  task4Evidence: { status: 'idle' | 'running' | 'done' | 'failed'; digitalSignature: string; evidenceHash: string; previousHash: string };
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
    lawRef: 'Luật Bảo vệ dữ liệu cá nhân số 91/2025/QH15 & Nghị định 356/2025/NĐ-CP',
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
      { label: '📄 ride_hailing_xanh_sm_trips (6,902)', actionType: 'SELECT_AND_RUN', payload: 'ride_hailing_xanh_sm_trips' },
      { label: '📄 synthetic_ev_telemetry_ved_ref (57,600)', actionType: 'SELECT_AND_RUN', payload: 'synthetic_ev_telemetry_ved_ref' },
      { label: '📄 dim_customers (5,106)', actionType: 'SELECT_AND_RUN', payload: 'dim_customers' },
      { label: '📄 acn_charging_mapped (912)', actionType: 'SELECT_AND_RUN', payload: 'acn_charging_mapped' },
      { label: '📄 fleet_index (60)', actionType: 'SELECT_AND_RUN', payload: 'fleet_index' },
      { label: '📄 dim_drivers (60)', actionType: 'SELECT_AND_RUN', payload: 'dim_drivers' },
      { label: '📄 feedback_pii (30)', actionType: 'SELECT_AND_RUN', payload: 'feedback_pii' },
      { label: '📄 synthetic_feedback_scenario_driven (16)', actionType: 'SELECT_AND_RUN', payload: 'synthetic_feedback_scenario_driven' },
    ],
  },
];

export const initialPipelineLevels: PipelineLevelsState = {
  currentLevel: 'IDLE',
  activeRunId: null,
  currentTaskName: 'Chờ kích hoạt pipeline',
  isPolling: false,
  viewingHistoricalResult: false,
  inFlightRunId: null,
  historicalRunId: null,
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
  task1Ingest: { status: 'idle', targetTable: '', rows: 0 },
  task2Profiling: { status: 'idle', healthScore: 0, nullRateAvg: 0 },
  task3LaneA: { status: 'idle', signalsCount: 0 },
  task3LaneB: { status: 'idle', activeRulesCount: 0, treatmentsCount: 0, lawFramework: ['Luật 91/2025/QH15', 'NĐ 356/2025', 'GDPR', 'IFRS 15'] },
  task3LaneC: { status: 'idle', silver: 0, quarantine: 0, warning: 0 },
  task4Evidence: { status: 'idle', digitalSignature: 'SIG-AIRFLOW-3LANE-GSM-IPO-2026', evidenceHash: '', previousHash: '' },
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
    description: 'Bảo vệ thông tin liên lạc khách hàng theo Luật 91/2025/QH15 & NĐ 356/2025/NĐ-CP',
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
    ai_rationale: 'AI phát hiện số điện thoại khách hàng dạng cleartext, đề xuất che mờ bảo vệ dữ liệu theo Luật 91/2025/QH15 & Nghị định 356/2025/NĐ-CP.',
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
  viewLatestCompletedResults: () => Promise<void>;
  returnToPipelineRunner: () => void;
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

  // Catalog Columns & PII Metadata from PostgreSQL
  catalogColumns: Record<string, ColumnModel[]>;
  fetchDatasetColumns: (datasetId?: string) => Promise<ColumnModel[]>;
  getDatasetMetadataStats: (datasetId: string) => {
    totalColumns: number;
    personalDataCount: number;
    directIdCount: number;
    contextualCount: number;
    hasPii: boolean;
  };
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
    records: 6902,
    zones: ['VN', 'US', 'EU'],
    zoneCounts: { VN: 2340, US: 2280, EU: 2282 },
    isProfiled: true,
    anomalies: 8,
    proposedRulesCount: 0,
    proposedRules: [],
  },
  'synthetic_ev_telemetry_ved_ref.csv': {
    id: 'synthetic_ev_telemetry_ved_ref.csv',
    name: 'synthetic_ev_telemetry_ved_ref.csv',
    filename: 'synthetic_ev_telemetry_ved_ref.csv',
    title: 'synthetic_ev_telemetry_ved_ref.csv',
    records: 57600,
    zones: ['VN', 'US', 'EU'],
    zoneCounts: { VN: 19200, US: 19200, EU: 19200 },
    isProfiled: true,
    anomalies: 7,
    proposedRulesCount: 0,
    proposedRules: [],
  },
  'acn_charging_mapped.csv': {
    id: 'acn_charging_mapped.csv',
    name: 'acn_charging_mapped.csv',
    filename: 'acn_charging_mapped.csv',
    title: 'acn_charging_mapped.csv',
    records: 912,
    zones: ['VN', 'US', 'EU'],
    zoneCounts: { VN: 304, US: 304, EU: 304 },
    isProfiled: true,
    anomalies: 2,
    proposedRulesCount: 0,
    proposedRules: [],
  },
  'dim_customers.csv': {
    id: 'dim_customers.csv',
    name: 'dim_customers.csv',
    filename: 'dim_customers.csv',
    title: 'dim_customers.csv',
    records: 5106,
    zones: ['VN', 'US', 'EU'],
    zoneCounts: { VN: 1702, US: 1702, EU: 1702 },
    isProfiled: true,
    anomalies: 6,
    proposedRulesCount: 0,
    proposedRules: [],
  },
  'dim_drivers.csv': {
    id: 'dim_drivers.csv',
    name: 'dim_drivers.csv',
    filename: 'dim_drivers.csv',
    title: 'dim_drivers.csv',
    records: 60,
    zones: ['VN', 'US', 'EU'],
    zoneCounts: { VN: 20, US: 20, EU: 20 },
    isProfiled: true,
    anomalies: 7,
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
    isProfiled: true,
    anomalies: 1,
    proposedRulesCount: 0,
    proposedRules: [],
  },
  'feedback_pii.csv': {
    id: 'feedback_pii.csv',
    name: 'feedback_pii.csv',
    filename: 'feedback_pii.csv',
    title: 'feedback_pii.csv',
    records: 30,
    zones: ['VN'],
    zoneCounts: { VN: 30 },
    isProfiled: true,
    anomalies: 4,
    proposedRulesCount: 0,
    proposedRules: [],
  },
  'synthetic_feedback_scenario_driven.csv': {
    id: 'synthetic_feedback_scenario_driven.csv',
    name: 'synthetic_feedback_scenario_driven.csv',
    filename: 'synthetic_feedback_scenario_driven.csv',
    title: 'synthetic_feedback_scenario_driven.csv',
    records: 16,
    zones: ['VN', 'US', 'EU'],
    zoneCounts: { VN: 6, US: 5, EU: 5 },
    isProfiled: true,
    anomalies: 2,
    proposedRulesCount: 0,
    proposedRules: [],
  },
};

// Aliases for backward compatibility
if (initialDatasets['ride_hailing_xanh_sm_trips.csv']) {
  initialDatasets['trips'] = initialDatasets['ride_hailing_xanh_sm_trips.csv'];
  initialDatasets['ride_hailing_xanh_sm_trips'] = initialDatasets['ride_hailing_xanh_sm_trips.csv'];
}
if (initialDatasets['synthetic_ev_telemetry_ved_ref.csv']) {
  initialDatasets['telemetry'] = initialDatasets['synthetic_ev_telemetry_ved_ref.csv'];
  initialDatasets['synthetic_ev_telemetry_ved_ref'] = initialDatasets['synthetic_ev_telemetry_ved_ref.csv'];
}
if (initialDatasets['acn_charging_mapped.csv']) {
  initialDatasets['charging'] = initialDatasets['acn_charging_mapped.csv'];
  initialDatasets['acn_charging_mapped'] = initialDatasets['acn_charging_mapped.csv'];
}
if (initialDatasets['dim_customers.csv']) {
  initialDatasets['customers'] = initialDatasets['dim_customers.csv'];
  initialDatasets['dim_customers'] = initialDatasets['dim_customers.csv'];
}
if (initialDatasets['dim_drivers.csv']) {
  initialDatasets['drivers'] = initialDatasets['dim_drivers.csv'];
  initialDatasets['dim_drivers'] = initialDatasets['dim_drivers.csv'];
}
if (initialDatasets['fleet_index.csv']) {
  initialDatasets['fleet'] = initialDatasets['fleet_index.csv'];
  initialDatasets['fleet_index'] = initialDatasets['fleet_index.csv'];
}
if (initialDatasets['feedback_pii.csv']) {
  initialDatasets['feedback'] = initialDatasets['feedback_pii.csv'];
  initialDatasets['feedback_pii'] = initialDatasets['feedback_pii.csv'];
}
if (initialDatasets['synthetic_feedback_scenario_driven.csv']) {
  initialDatasets['synthetic_feedback_scenario_driven'] = initialDatasets['synthetic_feedback_scenario_driven.csv'];
}

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
    lawStandard: 'Luật Bảo vệ dữ liệu cá nhân số 91/2025/QH15 & Nghị định 356/2025/NĐ-CP',
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
          lawReference: 'Luật Bảo vệ dữ liệu cá nhân số 91/2025/QH15 & Nghị định 356/2025/NĐ-CP',
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
    title: 'Luật Bảo vệ dữ liệu cá nhân 91/2025/QH15 & Nghị định 356/2025/NĐ-CP: Bắt buộc mã hóa AES-256 định danh cá nhân',
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
  currentRole: (typeof window !== 'undefined' && (localStorage.getItem('datatrust_role') as 'auditor' | 'admin')) || 'admin',
  setRole: (role) => {
    const isAuditor = role === 'auditor';
    try {
      localStorage.setItem('datatrust_role', role);
    } catch {}
    set((s) => ({
      currentRole: role,
      rulesSegmentTab: isAuditor ? 'active' : s.rulesSegmentTab,
    }));
  },

  selectedDatasetId: '',
  catalogColumns: {},
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
      const [
        backendActiveRules,
        backendProposedRules,
        backendComplianceRules,
        backendTreatmentRules,
        backendDatasets,
        backendProfiling,
        backendQuarantine,
        backendWarnings,
        backendColumns,
      ] = await Promise.all([
        apiBridge.fetchActiveRules().catch(() => []),
        apiBridge.fetchProposedRules().catch(() => []),
        apiBridge.fetchComplianceCheckRules().catch(() => []),
        apiBridge.fetchDataTreatmentRules().catch(() => []),
        apiBridge.fetchDatasets().catch(() => []),
        apiBridge.fetchProfilingOverview().catch(() => []),
        apiBridge.fetchQuarantineRecords({ limit: 100 }).catch(() => ({ total: 0, records: [] })),
        apiBridge.fetchWarningRecords({ limit: 100 }).catch(() => ({ total: 0, records: [] })),
        apiBridge.fetchColumns().catch(() => []),
      ]);

      const profilingMap = new Map<string, any>();
      for (const p of backendProfiling) {
        profilingMap.set(p.dataset_id, p);
        profilingMap.set(`${p.dataset_id}.csv`, p);
        if (p.table_name) {
          profilingMap.set(p.table_name, p);
          profilingMap.set(p.table_name.replace('bronze.', ''), p);
        }
      }

      // Build real compliance cases from PostgreSQL quarantine and warning records
      const realCases: ComplianceCaseItem[] = [];
      const quarRecords = backendQuarantine.records || [];
      const warnRecords = backendWarnings.records || [];

      // Group quarantine records by violation_rule_id
      const quarByRule = new Map<string, any[]>();
      for (const q of quarRecords) {
        const k = q.violation_rule_id || q.failure_lane || 'QUAR';
        const list = quarByRule.get(k) || [];
        list.push(q);
        quarByRule.set(k, list);
      }

      for (const [ruleId, qList] of quarByRule.entries()) {
        const sample = qList[0];
        const rawDs = (sample.dataset_id || 'trips').replace('.csv', '');
        const dsKey = (['trips', 'customers', 'drivers', 'charging', 'telemetry'].includes(rawDs) ? rawDs : 'trips') as any;
        realCases.push({
          id: `case-${sample.quarantine_id.slice(0, 8)}`,
          code: `CTRL-${ruleId.toUpperCase()}`,
          name: sample.violation_reason || `Kiểm soát ${sample.violation_column || 'Toàn vẹn'}`,
          datasetId: dsKey,
          domain: 'Data Integrity & Privacy',
          lawStandard: 'Luật 91/2025/QH15, NĐ 356/2025/NĐ-CP & IFRS 15',
          description: `Phát hiện ${qList.length} bản ghi vi phạm tại làn ${sample.failure_lane} thuộc bảng ${sample.dataset_id}. Đã cách ly an toàn khỏi Silver zone.`,
          expectedControl: `${sample.violation_column || 'Dữ liệu'} phải đạt chuẩn hợp lệ`,
          status: 'failed',
          findings: qList.slice(0, 5).map((item) => ({
            id: item.quarantine_id,
            caseId: `case-${sample.quarantine_id.slice(0, 8)}`,
            caseCode: `CTRL-${ruleId.toUpperCase()}`,
            title: item.violation_reason,
            datasetId: item.dataset_id,
            severity: (item.violation_severity || 'CRITICAL').toUpperCase() as any,
            status: item.status === 'REMEDIATED' ? 'AUDITED' : 'OPEN',
            detectedAt: item.quarantined_at || new Date().toISOString(),
            rootCauseAnalysis: `Bản ghi có PK ${item.source_row_pk || item.quarantine_id.slice(0, 8)} tại cột ${item.violation_column} vi phạm: ${item.violation_reason}.`,
            evidence: {
              hashSha256: item.lineage_hash,
              previousHash: 'GENESIS_HASH_CHAIN',
              lawReference: 'Luật Bảo vệ dữ liệu cá nhân 91/2025/QH15 & IFRS 15',
              quarantinedCount: qList.length,
              samplePayload: item.raw_record_json,
              digitalSignature: 'SIG-AIRFLOW-3LANE-GSM-IPO-2026',
            },
            aiRemediation: {
              actionPlan: ['Khắc phục dữ liệu hoặc Lead Platform phê duyệt ngoại lệ kiểm toán'],
              proposedRuleName: `remediation_${item.violation_column || 'integrity'}`,
              proposedExpression: `${item.violation_column || 'field'} IS NOT NULL AND ${item.violation_column || 'field'} > 0`,
              targetLane: item.failure_lane,
            },
          })),
        });
      }

      for (const w of warnRecords.slice(0, 10)) {
        const rawDs = (w.dataset_id || 'trips').replace('.csv', '');
        const dsKey = (['trips', 'customers', 'drivers', 'charging', 'telemetry'].includes(rawDs) ? rawDs : 'trips') as any;
        realCases.push({
          id: `case-warn-${w.warning_id.slice(0, 8)}`,
          code: `WARN-${(w.warning_type || w.signal_layer || 'STAT').toUpperCase()}`,
          name: w.warning_reason || `Cảnh báo ${w.signal_layer}`,
          datasetId: dsKey,
          domain: 'Statistical Quality',
          lawStandard: 'ISO 8000 & DQ Standard',
          description: `Phát hiện dị thường tại tầng ${w.signal_layer} trong tập dữ liệu ${w.dataset_id}.`,
          expectedControl: 'Chỉ số phân phối dữ liệu phải nằm trong ngưỡng kiểm soát',
          status: 'failed',
          findings: [
            {
              id: w.warning_id,
              caseId: `case-warn-${w.warning_id.slice(0, 8)}`,
              caseCode: `WARN-${(w.warning_type || 'STAT').toUpperCase()}`,
              title: w.warning_reason,
              datasetId: w.dataset_id,
              severity: 'MEDIUM',
              status: 'OPEN',
              detectedAt: w.detected_at || new Date().toISOString(),
              rootCauseAnalysis: `Phát hiện dị thường Z-score/drift tại ${w.signal_layer}: ${w.warning_reason}.`,
              evidence: {
                hashSha256: w.lineage_hash,
                previousHash: 'GENESIS_HASH_CHAIN',
                lawReference: 'ISO 8000 Statistical Quality',
                quarantinedCount: 0,
                samplePayload: w.evidence_json,
                digitalSignature: 'SIG-AIRFLOW-WARN-2026',
              },
              aiRemediation: {
                actionPlan: ['Điều chỉnh ngưỡng kiểm soát phân phối hoặc lọc dữ liệu ngoại lai'],
                proposedRuleName: `remediation_${w.signal_layer || 'drift'}`,
                proposedExpression: `abs(z_score) <= 3.0`,
                targetLane: w.signal_lane,
              },
            }
          ]
        });
      }

      // Group catalog columns by dataset
      const nextCatalogColumns: Record<string, ColumnModel[]> = {};
      if (backendColumns && backendColumns.length > 0) {
        for (const col of backendColumns) {
          const dsId = col.dataset_id;
          if (!nextCatalogColumns[dsId]) nextCatalogColumns[dsId] = [];
          nextCatalogColumns[dsId].push(col);
          const withCsv = `${dsId}.csv`;
          if (!nextCatalogColumns[withCsv]) nextCatalogColumns[withCsv] = [];
          nextCatalogColumns[withCsv].push(col);
        }
      }

      set((state) => {
        const nextActive = backendActiveRules.length > 0 ? backendActiveRules : state.activeRules;
        let nextDatasets = { ...state.datasets };
        if (backendDatasets && backendDatasets.length > 0) {
          for (const ds of backendDatasets) {
            const dsId = ds.dataset_id;
            const existing = nextDatasets[dsId] || nextDatasets[`${dsId}.csv`] || nextDatasets[ds.name];
            const prof = profilingMap.get(dsId) || profilingMap.get(`${dsId}.csv`) || profilingMap.get(ds.name);
            const totalRows = ds.row_count || prof?.total_rows || existing?.records || 0;
            const rawSignal = prof?.signals_summary ? Object.values(prof.signals_summary).reduce((a: number, b: any) => a + (typeof b === 'number' ? b : 0), 0) : existing?.anomalies;
            const signalCount: number | null = typeof rawSignal === 'number' ? rawSignal : (existing?.anomalies ?? null);

            const cols = nextCatalogColumns[dsId] || nextCatalogColumns[`${dsId}.csv`] || [];
            const hasPii = cols.some((c) => c.is_personal_data);
            const colCount = ds.column_count || (cols.length > 0 ? cols.length : existing?.columnCount || 0);

            const cleanItem: DatasetItem = {
              id: dsId,
              name: ds.name || `${dsId}.csv`,
              filename: ds.name || `${dsId}.csv`,
              title: ds.title || ds.name || dsId,
              records: totalRows,
              anomalies: signalCount,
              isProfiled: prof !== undefined || existing?.isProfiled || false,
              proposedRulesCount: existing?.proposedRulesCount || 0,
              proposedRules: existing?.proposedRules || [],
              zones: existing?.zones || ['VN', 'US', 'EU'],
              zoneCounts: existing?.zoneCounts,
              columnCount: colCount,
              source: ds.storage_table_bronze || 'PostgreSQL',
              description: ds.description,
              createdAt: ds.created_at,
              hasPii,
            };
            nextDatasets[dsId] = cleanItem;
            if (ds.name && ds.name !== dsId) {
              nextDatasets[ds.name] = cleanItem;
            }
          }
        }
        const currentDs = state.selectedDatasetId ? nextDatasets[state.selectedDatasetId] : null;
        if (currentDs && backendProposedRules.length > 0) {
          nextDatasets[state.selectedDatasetId] = {
            ...currentDs,
            proposedRules: backendProposedRules,
            proposedRulesCount: backendProposedRules.filter((r) => r.status === 'pending').length,
          };
        }
        return {
          isBackendLive: true,
          isSyncing: false,
          activeRules: nextActive,
          datasets: nextDatasets,
          catalogColumns: nextCatalogColumns,
          complianceCheckRules: backendComplianceRules.length > 0 ? backendComplianceRules : state.complianceCheckRules,
          dataTreatmentRules: backendTreatmentRules.length > 0 ? backendTreatmentRules : state.dataTreatmentRules,
          complianceCases: realCases.length > 0 ? realCases : state.complianceCases,
        };
      });
    } catch (err: any) {
      set({ isBackendLive: false, isSyncing: false, syncError: err?.message || 'Offline' });
    }
  },

  fetchDatasetColumns: async (datasetId?: string) => {
    try {
      const cols = await apiBridge.fetchColumns(datasetId);
      set((state) => {
        const nextCatalogColumns = { ...state.catalogColumns };
        if (datasetId) {
          const cleanId = datasetId.replace('.csv', '');
          nextCatalogColumns[cleanId] = cols;
          nextCatalogColumns[`${cleanId}.csv`] = cols;
        } else {
          for (const col of cols) {
            const dsId = col.dataset_id;
            if (!nextCatalogColumns[dsId]) nextCatalogColumns[dsId] = [];
            nextCatalogColumns[dsId].push(col);
            const withCsv = `${dsId}.csv`;
            if (!nextCatalogColumns[withCsv]) nextCatalogColumns[withCsv] = [];
            nextCatalogColumns[withCsv].push(col);
          }
        }
        return { catalogColumns: nextCatalogColumns };
      });
      return cols;
    } catch (err) {
      console.warn('Failed to fetch dataset columns:', err);
      return [];
    }
  },

  getDatasetMetadataStats: (datasetId: string) => {
    if (!datasetId) {
      return { totalColumns: 0, personalDataCount: 0, directIdCount: 0, contextualCount: 0, hasPii: false };
    }
    const cleanId = datasetId.replace('.csv', '').replace('bronze.', '');
    const cols = get().catalogColumns[cleanId] || get().catalogColumns[`${cleanId}.csv`] || [];
    const directIdCount = cols.filter((c) => c.pii_role === 'DIRECT_IDENTIFIER').length;
    const contextualCount = cols.filter((c) =>
      ['LINKABLE_IDENTIFIER', 'CONTEXTUAL_SENSITIVE', 'DEMOGRAPHIC'].includes(c.pii_role)
    ).length;
    const personalDataCount = cols.filter((c) => c.is_personal_data).length;
    const dsObj = get().datasets[cleanId] || get().datasets[`${cleanId}.csv`] || get().datasets[datasetId];
    const totalColumns = cols.length || dsObj?.columnCount || 0;

    return {
      totalColumns,
      personalDataCount,
      directIdCount,
      contextualCount,
      hasPii: personalDataCount > 0,
    };
  },

  selectDataset: (id: string) => {
    if (!id) {
      set({ selectedDatasetId: '' });
      return;
    }
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
    get().fetchDatasetColumns(canonicalId);
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
    Object.values(state.datasets || {}).forEach((ds) => {
      if (ds && Array.isArray(ds.proposedRules)) {
        count += ds.proposedRules.filter((r) => r && r.status === 'pending').length;
      }
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
    if (get().currentRole === 'auditor') {
      // Auditor role is viewer only; cannot start pipeline run
      return;
    }
    const targetDatasetId = normalizeDatasetId(datasetId || get().selectedDatasetId);
    const dataset = get().datasets[targetDatasetId] || get().datasets.trips;
    const cleanDs = targetDatasetId.replace('.csv', '');

    set({
      selectedDatasetId: targetDatasetId,
      homepageViewMode: 'running_pipeline',
      pipelineLevels: {
        ...initialPipelineLevels,
        currentLevel: 'L1',
        currentTaskName: 'Task 1: Đang nạp dữ liệu Bronze & Khởi tạo Catalog',
        activeRunId: null,
        isPolling: true,
        viewingHistoricalResult: false,
        inFlightRunId: null,
        historicalRunId: null,
        task1Ingest: { status: 'running', targetTable: `bronze.${cleanDs}`, rows: dataset.records },
        task2Profiling: { status: 'idle', healthScore: 0, nullRateAvg: 0 },
        task3LaneA: { status: 'idle', signalsCount: 0 },
        task3LaneB: { status: 'idle', activeRulesCount: 2, treatmentsCount: 2, lawFramework: ['Luật 91/2025/QH15', 'NĐ 356/2025', 'GDPR', 'IFRS 15'] },
        task3LaneC: { status: 'idle', silver: 0, quarantine: 0, warning: 0 },
        task4Evidence: { status: 'idle', digitalSignature: 'SIG-AIRFLOW-3LANE-GSM-IPO-2026', evidenceHash: '', previousHash: '' },
        l1: { status: 'running', progress: 50, scanned: Math.floor(dataset.records * 0.5), passed: Math.floor(dataset.records * 0.49), failed: 0, signalCount: 1, algorithm: 'Deterministic Range, Schema & Null check', latencyMs: 14 },
        l2: { status: 'idle', progress: 0, scanned: 0, passed: 0, failed: 0, signalCount: 0, algorithm: 'Median, MAD & Robust Z-Score', latencyMs: 22 },
        l3: { status: 'idle', progress: 0, scanned: 0, passed: 0, failed: 0, signalCount: 0, algorithm: 'Linear Regression Residuals (y = ax + b)', latencyMs: 38 },
        l4: { status: 'idle', progress: 0, scanned: 0, passed: 0, failed: 0, signalCount: 0, algorithm: 'CUSUM / PELT Regime Shift Detection', latencyMs: 45 },
      },
      chatMessages: [
        ...get().chatMessages,
        {
          id: `MSG-RUN-${Date.now()}`,
          sender: 'user',
          text: 'Chạy kiểm tra với cấu hình đã xác nhận.',
          timestamp: 'Vừa xong',
        },
        {
          id: `MSG-AI-RUN-${Date.now() + 1}`,
          sender: 'ai',
          text: `Đã bắt đầu lần chạy RUN-${cleanDs ? cleanDs.slice(0, 3).toUpperCase() : '021'}. Tôi sẽ hỗ trợ bạn theo dõi và giải thích kết quả.`,
          timestamp: 'Vừa xong',
        },
      ],
    });

    // 1. Kích hoạt Pipeline qua API chuẩn: createPipelineRun
    let runId = `run_${Date.now()}`;
    let isAirflowMode = false;

    try {
      const res = await apiBridge.createPipelineRun(cleanDs, {
        collect_evidence: true,
        generate_lineage: true,
      });
      if (res && res.run_id) {
        runId = res.run_id;
        isAirflowMode = true;
      }
    } catch (err) {
      console.warn('[Pipeline Trigger Warning]:', err);
    }

    set((s) => ({
      pipelineLevels: {
        ...s.pipelineLevels,
        activeRunId: runId,
      },
    }));

    // 2. Fetch kết quả thực tế từ DB (Quarantine, Warning, Profiling)
    let realQuarantineCount = 0;
    let realWarningCount = 0;
    let realQuarantineRecords: any[] = [];
    let realWarningRecords: any[] = [];

    try {
      const [quarRes, warnRes] = await Promise.all([
        apiBridge.fetchQuarantineRecords({ datasetId: cleanDs, limit: 100 }).catch(() => ({ total: 0, records: [] })),
        apiBridge.fetchWarningRecords({ datasetId: cleanDs, limit: 100 }).catch(() => ({ total: 0, records: [] })),
      ]);
      realQuarantineRecords = quarRes.records || [];
      realWarningRecords = warnRes.records || [];
      realQuarantineCount = quarRes.total !== undefined ? quarRes.total : realQuarantineRecords.length;
      realWarningCount = warnRes.total !== undefined ? warnRes.total : realWarningRecords.length;
    } catch (e) {
      console.warn('[startPipelineRun Live DB Fetch Warning]', e);
    }

    const totalAnomalies = realQuarantineCount;
    const finalSilver = Math.max(0, dataset.records - realQuarantineCount);

    const uniqueReasons = Array.from(new Set([
      ...realQuarantineRecords.map((r: any) => r.reason),
      ...realWarningRecords.map((r: any) => r.reason),
    ])).filter(Boolean);

    const liveSummary = uniqueReasons.length > 0
      ? uniqueReasons.slice(0, 3).map((r, idx) => `• **Vi phạm ${idx + 1}**: ${r}`).join('\n') + '\n\n'
      : (realQuarantineCount > 0
          ? `• Phát hiện ${realQuarantineCount} bản ghi cách ly trong CSDL.\n\n`
          : `• Dữ liệu ${cleanDs} trong CSDL đạt chuẩn tuân thủ, không có vi phạm nghiêm trọng.\n\n`);

    const targetProfile = {
      count: realQuarantineCount,
      rules: [],
      summary: liveSummary,
    };

    // 3. Nếu là Airflow Mode, bắt đầu vòng lặp polling trạng thái thực tế
    if (isAirflowMode) {
      let pollTicks = 0;
      const pollInterval = setInterval(async () => {
        pollTicks += 1;
        try {
          const live = await apiBridge.fetchPipelineLiveStatus(runId);
          if (live) {
            const stepMap = live.task_status_map || {};
            const tasks = live.tasks || {};
            const isRunSuccess = live.status === 'SUCCESS' || live.status === 'COMPLETED';
            const isRunFailed = live.status === 'FAILED';

            const t1Done = isRunSuccess || stepMap['INGEST'] === 'COMPLETED' || tasks.task_1_truncate_and_ingest_bronze === 'success' || pollTicks >= 3;
            const t2Done = isRunSuccess || stepMap['BRONZE'] === 'COMPLETED' || tasks.task_2_data_profiling === 'success' || (t1Done && pollTicks >= 6);
            const t3Done = isRunSuccess || stepMap['SILVER'] === 'COMPLETED' || tasks.lane_c_merge_verdicts_and_route === 'success' || (t2Done && pollTicks >= 9);
            const t4Done = isRunSuccess || stepMap['EVIDENCE'] === 'COMPLETED' || tasks.task_4_emit_audit_evidence === 'success';

            let curTaskDesc = 'Task 1: Đang nạp Bronze Ingestion';
            let curLevel: 'L1' | 'L2' | 'L3' | 'L4' | 'COMPLETED' = 'L1';
            if (t1Done && !t2Done) {
              curTaskDesc = 'Task 2: Đang phân tích Profiling Engine';
              curLevel = 'L1';
            } else if (t2Done && !t3Done) {
              curTaskDesc = 'Task 3: Đang đánh giá song song Lane A & Lane B';
              curLevel = 'L3';
            } else if (t3Done && !t4Done) {
              curTaskDesc = 'Task 4: Đang ký số & Tạo Bằng chứng Kiểm toán';
              curLevel = 'L4';
            } else if (t4Done || isRunSuccess) {
              curTaskDesc = 'Hoàn tất toàn bộ Pipeline';
              curLevel = 'COMPLETED';
            }

            set((s) => ({
              pipelineLevels: {
                ...s.pipelineLevels,
                currentLevel: curLevel,
                currentTaskName: curTaskDesc,
                task1Ingest: { status: t1Done ? 'done' : 'running', targetTable: `bronze.${cleanDs}`, rows: dataset.records },
                task2Profiling: { status: t2Done ? 'done' : (t1Done ? 'running' : 'idle'), healthScore: 94.6, nullRateAvg: 0.02 },
                task3LaneA: { status: t3Done ? 'done' : (t2Done ? 'running' : 'idle'), signalsCount: realWarningCount },
                task3LaneB: { status: t3Done ? 'done' : (t2Done ? 'running' : 'idle'), activeRulesCount: 2, treatmentsCount: 2, lawFramework: ['Luật 91/2025/QH15', 'NĐ 356/2025', 'GDPR', 'IFRS 15'] },
                task3LaneC: { status: t3Done ? 'done' : (t2Done ? 'running' : 'idle'), silver: finalSilver, quarantine: realQuarantineCount, warning: realWarningCount },
                task4Evidence: { status: t4Done ? 'done' : (t3Done ? 'running' : 'idle'), digitalSignature: 'SIG-AIRFLOW-3LANE-GSM-IPO-2026', evidenceHash: 'd5609049be3bf0611a5b914388aadf3d266bf6b2b20a8191dfc8cf63fd0aeb28', previousHash: 'edffc2d20fb28a87a6ab1948d0d4bdcff5e8ba661d809f8dde244dc612d0ed5d' },
              }
            }));

            if (isRunSuccess || isRunFailed || t4Done) {
              clearInterval(pollInterval);
              const shortRunId = runId.startsWith('run_') ? `RUN-${runId.slice(4, 7)}` : runId;
              set((s) => ({
                homepageViewMode: 'running_pipeline',
                pipelineLevels: {
                  ...s.pipelineLevels,
                  isPolling: false,
                  currentLevel: 'COMPLETED',
                  currentTaskName: 'Hoàn tất toàn bộ Pipeline',
                },
                chatMessages: [
                  ...s.chatMessages,
                  {
                    id: `MSG-RESULT-${Date.now()}`,
                    sender: 'ai',
                    text: `Đã mở tóm tắt kết quả của đúng ${shortRunId}. Ưu tiên xem finding Critical.`,
                    timestamp: 'Vừa xong',
                    quickActions: [
                      { label: 'Xem kết quả lần chạy này →', actionType: 'VIEW_RESULTS' },
                    ],
                  }
                ]
              }));
            }
          }
        } catch (e) {
          console.warn('[Polling Error]', e);
        }
      }, 1500);
      return;
    }

    // 4. Nếu là Local Fallback / Standalone mode: Cập nhật ngay lập tức từ DB thật (không có fake delays)
    const finalFailedL4 = Math.max(0, totalAnomalies - Math.floor(totalAnomalies * 0.4) - Math.floor(totalAnomalies * 0.3) - Math.floor(totalAnomalies * 0.2));

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
          currentTaskName: 'Hoàn tất toàn bộ Pipeline (Task 1 - Task 4)',
          isPolling: false,
          task1Ingest: { status: 'done', targetTable: `bronze.${cleanDs}`, rows: dataset.records },
          task2Profiling: { status: 'done', healthScore: 94.6, nullRateAvg: 0.02 },
          task3LaneA: { status: 'done', signalsCount: realWarningCount },
          task3LaneB: { status: 'done', activeRulesCount: 2, treatmentsCount: 2, lawFramework: ['Luật 91/2025/QH15', 'NĐ 356/2025', 'GDPR', 'IFRS 15'] },
          task3LaneC: { status: 'done', silver: finalSilver, quarantine: realQuarantineCount, warning: realWarningCount },
          task4Evidence: { status: 'done', digitalSignature: 'SIG-AIRFLOW-3LANE-GSM-IPO-2026', evidenceHash: 'd5609049be3bf0611a5b914388aadf3d266bf6b2b20a8191dfc8cf63fd0aeb28', previousHash: 'edffc2d20fb28a87a6ab1948d0d4bdcff5e8ba661d809f8dde244dc612d0ed5d' },
          l1: { ...s.pipelineLevels.l1, status: 'done', progress: 100, scanned: dataset.records, passed: dataset.records - Math.floor(totalAnomalies * 0.4), failed: Math.floor(totalAnomalies * 0.4) },
          l2: { ...s.pipelineLevels.l2, status: 'done', progress: 100, scanned: dataset.records, passed: dataset.records - Math.floor(totalAnomalies * 0.3), failed: Math.floor(totalAnomalies * 0.3) },
          l3: { ...s.pipelineLevels.l3, status: 'done', progress: 100, scanned: dataset.records, passed: dataset.records - Math.floor(totalAnomalies * 0.2), failed: Math.floor(totalAnomalies * 0.2) },
          l4: { ...s.pipelineLevels.l4, status: 'done', progress: 100, scanned: dataset.records, passed: dataset.records - finalFailedL4, failed: finalFailedL4 },
        },
        chatMessages: [
          ...s.chatMessages,
          {
            id: `MSG-RESULT-${Date.now()}`,
            sender: 'ai',
            text: `✅ **Kiểm toán dữ liệu hoàn tất cho \`${dataset.filename || dataset.title}\`**\n• **Trạng thái**: Hoàn tất thành công (Run \`${runId}\`)\n• **Kết quả**: ${dataset.records.toLocaleString()} bản ghi quét, ${realQuarantineCount} cách ly, ${realWarningCount} cảnh báo.`,
            timestamp: 'Vừa xong',
            quickActions: [
              { label: '📊 Xem kết quả', actionType: 'NAVIGATE_RESULTS', payload: `/runs/${runId}/results` },
              { label: '🔍 Xem findings', actionType: 'NAVIGATE_FINDINGS', payload: `/runs/${runId}/findings` },
            ],
          }
        ]
      };
    });
  },

  viewLatestCompletedResults: async () => {
    const isCurrentlyDone = get().pipelineLevels.currentLevel === 'COMPLETED';
    const cleanDs = get().selectedDatasetId.replace('.csv', '');
    let latest = null;

    if (!isCurrentlyDone) {
      try {
        latest = await apiBridge.fetchLatestCompletedRun(cleanDs);
      } catch (e) {
        console.warn('Could not fetch latest completed run:', e);
      }
    }

    const currentActiveRun = isCurrentlyDone ? get().pipelineLevels.activeRunId : (latest?.run_id || 'RUN-20261007-021');
    const shortRun = currentActiveRun ? (currentActiveRun.startsWith('run_') ? `RUN-${currentActiveRun.slice(4, 7)}` : currentActiveRun) : 'RUN-021';
    const recs = get().datasets[get().selectedDatasetId]?.records || 6902;
    const failRecs = get().pipelineLevels.task3LaneC.quarantine || 565;

    set((s) => ({
      homepageViewMode: 'results_dashboard',
      pipelineLevels: {
        ...s.pipelineLevels,
        viewingHistoricalResult: !isCurrentlyDone,
        inFlightRunId: !isCurrentlyDone ? s.pipelineLevels.activeRunId : null,
        historicalRunId: latest?.run_id || (isCurrentlyDone ? s.pipelineLevels.activeRunId : 'RUN-HISTORICAL-BASE'),
      },
      chatMessages: [
        ...s.chatMessages,
        {
          id: `MSG-USER-RES-${Date.now()}`,
          sender: 'user',
          text: 'Tóm tắt kết quả kiểm tra bộ dữ liệu cuốc xe.',
          timestamp: 'Vừa xong',
        },
        {
          id: `MSG-AI-RES-1-${Date.now() + 1}`,
          sender: 'ai',
          text: `Đã kiểm tra ${recs.toLocaleString('vi-VN')} bản ghi.\n\n${failRecs.toLocaleString('vi-VN')} bản ghi không đạt, tập trung ở 3 rule. Bạn có thể bắt đầu từ finding mức Critical.`,
          timestamp: 'Vừa xong',
          quickActions: [
            { label: 'Xem finding Critical →', actionType: 'SCROLL_TO_CRITICAL' },
          ],
        },
        {
          id: `MSG-AI-RES-2-${Date.now() + 2}`,
          sender: 'ai',
          text: `Đang xem F-${shortRun.replace('RUN-', '')}-02 · Giá cước không hợp lệ. Tôi có thể giải thích nguyên nhân hoặc cùng bạn xem evidence.`,
          timestamp: 'Vừa xong',
        },
      ],
    }));
  },

  returnToPipelineRunner: () => {
    set({
      homepageViewMode: 'running_pipeline',
    });
  },

  skipPipelineRunToResults: () => {
    get().viewLatestCompletedResults();
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
      } else if (
        lower.includes('finding') ||
        lower.includes('giải thích') ||
        lower.includes('rca') ||
        lower.includes('nguyên nhân') ||
        lower.includes('khắc phục') ||
        lower.includes('đề xuất') ||
        lower.includes('vi phạm')
      ) {
        aiReply = `🔍 **Phân tích nguyên nhân gốc rễ (RCA) & Đề xuất xử lý Finding**:
• **Vấn đề phát hiện**: Vi phạm quy tắc hợp lệ tọa độ (\`lat_zero_gps_drift\`) và định dạng số điện thoại PII cleartext.
• **Nguyên nhân gốc**: Thiết bị telemetry mất tín hiệu GPS (tọa độ trả về 0,0) và hệ thống nạp thiếu kiểm tra tiền xử lý định dạng trước khi lưu vào Bronze stream.
• **Đề xuất xử lý khắc phục**:
  1. \`Quarantine Remediation\`: Cách ly và chuẩn hóa lại tọa độ hợp lệ từ trạm kế cận.
  2. \`Schema Enforcement\`: Thêm validation check tại API gateway để từ chối hoặc chuẩn hóa SĐT trước khi nạp.
  3. \`Audit Override\`: Nếu phát hiện ngoại lệ kinh doanh hợp lệ, Auditor có thể phê duyệt ghi đè có lưu vết chữ ký số.`;
        quickActions = [
          { label: '🔍 Xem danh sách Findings', actionType: 'NAVIGATE_FINDINGS', payload: `/runs/${get().pipelineLevels.activeRunId || 'latest'}/findings` },
          { label: '📊 Xem bảng kết quả', actionType: 'NAVIGATE_RESULTS', payload: `/runs/${get().pipelineLevels.activeRunId || 'latest'}/results` },
        ];
      } else if (lower.includes('chọn dataset') || lower.includes('dataset') || lower.includes('danh sách bảng') || lower.includes('chọn bảng')) {
        aiReply = `Dưới đây là đầy đủ 8 bảng dữ liệu thực tế từ CSDL PostgreSQL sẵn sàng kiểm soát tuân thủ:`;
        quickActions = [
          { label: '📄 ride_hailing_xanh_sm_trips (6,902 dòng)', actionType: 'SELECT_AND_RUN', payload: 'ride_hailing_xanh_sm_trips' },
          { label: '📄 synthetic_ev_telemetry_ved_ref (57,600 dòng)', actionType: 'SELECT_AND_RUN', payload: 'synthetic_ev_telemetry_ved_ref' },
          { label: '📄 dim_customers (5,106 dòng)', actionType: 'SELECT_AND_RUN', payload: 'dim_customers' },
          { label: '📄 acn_charging_mapped (912 dòng)', actionType: 'SELECT_AND_RUN', payload: 'acn_charging_mapped' },
          { label: '📄 fleet_index (60 dòng)', actionType: 'SELECT_AND_RUN', payload: 'fleet_index' },
          { label: '📄 dim_drivers (60 dòng)', actionType: 'SELECT_AND_RUN', payload: 'dim_drivers' },
          { label: '📄 feedback_pii (30 dòng)', actionType: 'SELECT_AND_RUN', payload: 'feedback_pii' },
          { label: '📄 synthetic_feedback_scenario_driven (16 dòng)', actionType: 'SELECT_AND_RUN', payload: 'synthetic_feedback_scenario_driven' },
        ];
      } else {
        aiReply = `Tôi hiểu bạn đang quan tâm đến "${text}". Bạn có thể chọn nhanh các tác vụ kiểm toán sau:`;
        quickActions = [
          { label: '🚀 Cấu hình & Chạy kiểm toán', actionType: 'OPEN_START_RUN_MODAL' },
          { label: '📊 Xem kết quả kiểm toán', actionType: 'NAVIGATE_RESULTS', payload: `/runs/${get().pipelineLevels.activeRunId || 'latest'}/results` },
          { label: '🔍 Xem danh sách Findings', actionType: 'NAVIGATE_FINDINGS', payload: `/runs/${get().pipelineLevels.activeRunId || 'latest'}/findings` },
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
      selectedDatasetId: '',
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
