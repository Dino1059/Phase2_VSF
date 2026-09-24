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
  setRole: (role) => set({ currentRole: role }),

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
}));
