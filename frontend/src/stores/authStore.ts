import { create } from 'zustand';
import { readAuthToken, authApi, persistAuthToken } from '../services/api';

/**
 * Danh sách 14 vai trò theo chuẩn KE_HOACH_SOD_DATATRUST.md mục 2.
 * Hỗ trợ 3 phân nhóm quyền truy cập:
 * 1. Both: ADMIN, AUDITOR, DPO, SO -> Vào DataTrust (/overview) và kích hoạt Tab Phân quyền & SoD (/sod)
 * 2. SoD Only: REQ, LM, IAM, DEV, REL, OPS, CISO -> Vào SoD Standalone Workspace (/sod)
 * 3. DataTrust Only: DATA_STEWARD, ANALYST, VIEWER -> Vào DataTrust (/overview, ẩn tab SoD)
 */
export type UserRole =
  // Nhóm Cả hai (4)
  | 'ADMIN'
  | 'AUDITOR'
  | 'DPO'
  | 'SO'
  // Nhóm Chỉ SoD (7)
  | 'REQ'
  | 'LM'
  | 'IAM'
  | 'DEV'
  | 'REL'
  | 'OPS'
  | 'CISO'
  // Nhóm Chỉ DataTrust (3)
  | 'DATA_STEWARD'
  | 'ANALYST'
  | 'VIEWER';

export type SystemAccessType = 'both' | 'sod_only' | 'datatrust_only';

export interface PersonaAccount {
  id: string;
  username: string;
  fullName: string;
  shortName: string;
  roles: UserRole[];
  primaryRole: UserRole;
  email: string;
  avatar: string;
  badge: string;
  roleTitle: string;
  company: string;
  systemAccess: SystemAccessType;
  defaultRoute: string;
  description: string;
}

export interface UserProfile {
  user_id: string;
  username: string;
  fullName: string;
  role: UserRole; // primary role (backward compatibility)
  roles: UserRole[]; // Full list of assigned roles (multi-role support)
  systemAccess: SystemAccessType;
  is_global?: boolean;
  datasets?: string[];
  dept?: string;
  email?: string;
  avatar?: string;
  badge?: string;
}

export const BOTH_ROLES: ReadonlySet<UserRole> = new Set(['ADMIN', 'AUDITOR', 'DPO', 'SO']);
export const SOD_ROLES: ReadonlySet<UserRole> = new Set(['REQ', 'LM', 'IAM', 'DEV', 'REL', 'OPS', 'CISO']);
export const DATATRUST_ROLES: ReadonlySet<UserRole> = new Set(['DATA_STEWARD', 'ANALYST', 'VIEWER']);

/**
 * Chuẩn hóa chuỗi vai trò từ nhiều định dạng legacy hoặc chữ hoa/thường.
 */
export function normalizeUserRole(raw?: string | null): UserRole | null {
  const s = String(raw || '').trim().toUpperCase().replace(/[\s_-]+/g, '_');
  if (!s) return null;
  if (s === 'ADMIN' || s === 'ADMINISTRATOR') return 'ADMIN';
  if (s === 'AUDITOR' || s === 'AUD') return 'AUDITOR';
  if (s === 'DPO' || s === 'LEGAL' || s === 'COMPLIANCE') return 'DPO';
  if (s === 'SO' || s === 'SYSTEM_OWNER' || s === 'DATA_OWNER') return 'SO';
  if (s === 'REQ' || s === 'REQUESTOR') return 'REQ';
  if (s === 'LM' || s === 'LINE_MANAGER') return 'LM';
  if (s === 'IAM' || s === 'IAM_ADMIN') return 'IAM';
  if (s === 'DEV' || s === 'DEVELOPER') return 'DEV';
  if (s === 'REL' || s === 'RELEASE_MANAGER') return 'REL';
  if (s === 'OPS' || s === 'OPERATOR') return 'OPS';
  if (s === 'CISO' || s === 'SECURITY') return 'CISO';
  if (s === 'DATA_STEWARD' || s === 'STEWARD') return 'DATA_STEWARD';
  if (s === 'ANALYST') return 'ANALYST';
  if (s === 'VIEWER' || s === 'READ_ONLY') return 'VIEWER';
  return null;
}

/**
 * Xác định thẩm quyền truy cập hệ thống từ một hoặc nhiều vai trò (Multi-role support).
 * Nếu người dùng có bất kỳ vai trò nào thuộc nhóm BOTH, trả về 'both'.
 * Nếu có cả vai trò SoD và vai trò DataTrust, trả về 'both'.
 * Nếu chỉ có vai trò SoD, trả về 'sod_only'.
 * Nếu chỉ có vai trò DataTrust, trả về 'datatrust_only'.
 */
export function getSystemAccess(roles: (UserRole | string)[]): SystemAccessType {
  const norm = roles
    .map((r) => normalizeUserRole(r))
    .filter((r): r is UserRole => r !== null);

  if (norm.length === 0) return 'datatrust_only';

  const hasBoth = norm.some((r) => BOTH_ROLES.has(r));
  if (hasBoth) return 'both';

  const hasSod = norm.some((r) => SOD_ROLES.has(r));
  const hasDt = norm.some((r) => DATATRUST_ROLES.has(r));

  if (hasSod && hasDt) return 'both';
  if (hasSod) return 'sod_only';
  return 'datatrust_only';
}

/**
 * 14 Persona mẫu phục vụ Demo Mode (Phase 1).
 * Dữ liệu vai trò và người dùng thực tế từ seed của sod-production và DataTrust OS.
 */
export const PERSONA_ACCOUNTS: Record<string, PersonaAccount> = {
  // --- NHÓM 1: CẢ HAI HỆ THỐNG (BOTH) ---
  admin: {
    id: 'admin',
    username: 'admin',
    fullName: 'Nguyễn Quốc Bảo',
    shortName: 'anh Bảo',
    roles: ['ADMIN'],
    primaryRole: 'ADMIN',
    email: 'bao.nq@gsm.vn',
    avatar: 'QB',
    badge: 'Quản trị viên hệ thống / SoD',
    roleTitle: 'Lead Data Platform (GSM Global)',
    company: 'GSM Global Tech',
    systemAccess: 'both',
    defaultRoute: '/overview',
    description: 'Toàn quyền cấu hình DataTrust, đề xuất ma trận SoD, quản trị kết nối & pipelines.',
  },
  auditor: {
    id: 'auditor',
    username: 'auditor',
    fullName: 'Trần Minh Hoàng',
    shortName: 'anh Hoàng',
    roles: ['AUDITOR'],
    primaryRole: 'AUDITOR',
    email: 'hoang.tran@audit-ipo.com',
    avatar: 'TH',
    badge: 'Kiểm toán viên độc lập (Big 4)',
    roleTitle: 'Senior Auditor (IPO Assurance)',
    company: 'Big 4 Audit Consortium',
    systemAccess: 'both',
    defaultRoute: '/overview',
    description: 'Thẩm tra độc lập, chạy Audit Run, kiểm tra Merkle SHA-256 Ledger, rà soát kiểm soát (R) và xuất bằng chứng.',
  },
  dpo: {
    id: 'dpo',
    username: 'chi.le',
    fullName: 'Lê Chi',
    shortName: 'chị Chi',
    roles: ['DPO'],
    primaryRole: 'DPO',
    email: 'chi.le@company.vn',
    avatar: 'LC',
    badge: 'Bảo vệ Dữ liệu & Pháp chế',
    roleTitle: 'Data Protection Officer (DPO)',
    company: 'Phòng Pháp chế & Tuân thủ',
    systemAccess: 'both',
    defaultRoute: '/overview',
    description: 'Duyệt Maker-Checker cấp cao các đề xuất PII (GDPR Art 6, VN Decree 13), phê duyệt xuất dữ liệu PII và ngoại lệ SoD.',
  },
  so: {
    id: 'so',
    username: 'son.ho',
    fullName: 'Hồ Sơn',
    shortName: 'anh Sơn',
    roles: ['SO'],
    primaryRole: 'SO',
    email: 'son.ho@company.vn',
    avatar: 'HS',
    badge: 'Chủ quản Hệ thống & Dữ liệu',
    roleTitle: 'System Owner (ERP & Core Data)',
    company: 'Khối Công nghệ Thông tin',
    systemAccess: 'both',
    defaultRoute: '/overview',
    description: 'Xác nhận quy tắc dữ liệu nghiệp vụ, phê duyệt quyền truy cập ứng dụng và database nghiệp vụ.',
  },

  // --- NHÓM 2: CHỈ SOD FLOW (SOD ONLY) ---
  req: {
    id: 'req',
    username: 'an.nguyen',
    fullName: 'Nguyễn An',
    shortName: 'anh An',
    roles: ['REQ'],
    primaryRole: 'REQ',
    email: 'an.nguyen@company.vn',
    avatar: 'NA',
    badge: 'Người khởi tạo yêu cầu (Requestor)',
    roleTitle: 'Business Analyst',
    company: 'Khối Kinh doanh & Vận hành',
    systemAccess: 'sod_only',
    defaultRoute: '/sod',
    description: 'Lập phiếu xin cấp/đổi quyền truy cập, lập phiếu ngoại lệ kiểm soát. Bị chặn tự duyệt.',
  },
  lm: {
    id: 'lm',
    username: 'binh.tran',
    fullName: 'Trần Bình',
    shortName: 'anh Bình',
    roles: ['LM'],
    primaryRole: 'LM',
    email: 'binh.tran@company.vn',
    avatar: 'TB',
    badge: 'Quản lý trực tiếp (Line Manager)',
    roleTitle: 'Operations Manager',
    company: 'Bộ phận Vận hành',
    systemAccess: 'sod_only',
    defaultRoute: '/sod',
    description: 'Xác nhận nhu cầu công việc của nhân viên, phê duyệt bước đầu trong chuỗi cấp quyền.',
  },
  iam: {
    id: 'iam',
    username: 'ha.vu',
    fullName: 'Vũ Hà',
    shortName: 'chị Hà',
    roles: ['IAM'],
    primaryRole: 'IAM',
    email: 'ha.vu@company.vn',
    avatar: 'VH',
    badge: 'Quản trị Định danh (IAM Admin)',
    roleTitle: 'IAM Administrator',
    company: 'Phòng Hạ tầng An ninh',
    systemAccess: 'sod_only',
    defaultRoute: '/sod',
    description: 'Thực thi cấp/thu hồi tài khoản trên hệ thống IAM/PAM sau khi phiếu có đầy đủ chữ ký.',
  },
  dev: {
    id: 'dev',
    username: 'khoa.do',
    fullName: 'Đỗ Khoa',
    shortName: 'anh Khoa',
    roles: ['DEV'],
    primaryRole: 'DEV',
    email: 'khoa.do@company.vn',
    avatar: 'DK',
    badge: 'Lập trình viên (Developer)',
    roleTitle: 'Senior Software Engineer',
    company: 'Trung tâm Phát triển Phần mềm',
    systemAccess: 'sod_only',
    defaultRoute: '/sod',
    description: 'Yêu cầu thay đổi mã nguồn; bị chặn quyền Release Manager và Prod Deployer.',
  },
  rel: {
    id: 'rel',
    username: 'lan.bui',
    fullName: 'Bùi Lan',
    shortName: 'chị Lan',
    roles: ['REL'],
    primaryRole: 'REL',
    email: 'lan.bui@company.vn',
    avatar: 'BL',
    badge: 'Quản lý Phát hành (Release Manager)',
    roleTitle: 'Release Manager',
    company: 'Phòng Quản lý Chất lượng & Release',
    systemAccess: 'sod_only',
    defaultRoute: '/sod',
    description: 'Kiểm tra biên bản test UAT; phê duyệt phát hành phiên bản lên môi trường Production.',
  },
  ops: {
    id: 'ops',
    username: 'minh.ngo',
    fullName: 'Ngô Minh',
    shortName: 'anh Minh',
    roles: ['OPS'],
    primaryRole: 'OPS',
    email: 'minh.ngo@company.vn',
    avatar: 'NM',
    badge: 'Kỹ sư Vận hành (Prod Operator)',
    roleTitle: 'Site Reliability Engineer',
    company: 'Phòng Vận hành Hệ thống',
    systemAccess: 'sod_only',
    defaultRoute: '/sod',
    description: 'Triển khai hạ tầng và release Prod sau khi đã có phê duyệt của Release Manager.',
  },
  ciso: {
    id: 'ciso',
    username: 'giang.hoang',
    fullName: 'Hoàng Giang',
    shortName: 'anh Giang',
    roles: ['CISO'],
    primaryRole: 'CISO',
    email: 'giang.hoang@company.vn',
    avatar: 'HG',
    badge: 'Giám đốc An toàn Thông tin (CISO)',
    roleTitle: 'Chief Information Security Officer',
    company: 'Ban An toàn Thông tin Doanh nghiệp',
    systemAccess: 'sod_only',
    defaultRoute: '/sod',
    description: 'Phê duyệt cấu hình SoD do Admin đề xuất (Checker); duyệt ngoại lệ Level 3 và tài khoản đặc quyền.',
  },

  // --- NHÓM 3: CHỈ DATATRUST OS (DATATRUST ONLY) ---
  steward: {
    id: 'steward',
    username: 'steward.le',
    fullName: 'Lê Nam',
    shortName: 'anh Nam',
    roles: ['DATA_STEWARD'],
    primaryRole: 'DATA_STEWARD',
    email: 'steward.le@company.vn',
    avatar: 'LN',
    badge: 'Người bảo hộ dữ liệu (Data Steward)',
    roleTitle: 'Data Governance Lead',
    company: 'Khối Quản trị Dữ liệu Doanh nghiệp',
    systemAccess: 'datatrust_only',
    defaultRoute: '/overview',
    description: 'Duyệt quy tắc chất lượng dữ liệu, duyệt đề xuất khắc phục vi phạm (Maker-Checker), xử lý cách ly Quarantine.',
  },
  analyst: {
    id: 'analyst',
    username: 'analyst.vu',
    fullName: 'Vũ Mai',
    shortName: 'chị Mai',
    roles: ['ANALYST'],
    primaryRole: 'ANALYST',
    email: 'analyst.vu@company.vn',
    avatar: 'VM',
    badge: 'Chuyên viên Phân tích Dữ liệu',
    roleTitle: 'Data Quality Analyst',
    company: 'Trung tâm Phân tích Dữ liệu',
    systemAccess: 'datatrust_only',
    defaultRoute: '/overview',
    description: 'Khảo sát dữ liệu, phân tích Finding, đề xuất phương án khắc phục (chỉ đề xuất, không có quyền duyệt).',
  },
  viewer: {
    id: 'viewer',
    username: 'viewer.tran',
    fullName: 'Trần Đức',
    shortName: 'anh Đức',
    roles: ['VIEWER'],
    primaryRole: 'VIEWER',
    email: 'viewer.tran@company.vn',
    avatar: 'TD',
    badge: 'Người xem Báo cáo (Viewer)',
    roleTitle: 'Business Intelligence Viewer',
    company: 'Ban Giám đốc',
    systemAccess: 'datatrust_only',
    defaultRoute: '/overview',
    description: 'Xem dashboard tổng quan, chỉ số KPI tuân thủ, biểu đồ chất lượng. Quyền chỉ đọc.',
  },
};

export const ROLE_PERMISSIONS: Record<UserRole, ReadonlySet<string>> = {
  ADMIN: new Set(['read', 'profile', 'propose_rules', 'review_rules', 'manage_schedule', 'clear_alerts', 'reset', 'manage_acl', 'start_run', 'sod_access', 'sod_admin']),
  AUDITOR: new Set(['read', 'review_rules', 'start_run', 'sod_access', 'sod_evidence']),
  DPO: new Set(['read', 'review_rules', 'sod_access', 'sod_dpo']),
  SO: new Set(['read', 'sod_access', 'sod_owner']),
  REQ: new Set(['sod_access', 'sod_create_ticket']),
  LM: new Set(['sod_access', 'sod_approve_step']),
  IAM: new Set(['sod_access', 'sod_provision']),
  DEV: new Set(['sod_access', 'sod_dev_request']),
  REL: new Set(['sod_access', 'sod_release_approve']),
  OPS: new Set(['sod_access', 'sod_deploy']),
  CISO: new Set(['sod_access', 'sod_ciso_approve']),
  DATA_STEWARD: new Set(['read', 'profile', 'propose_rules', 'review_rules', 'hitl_write', 'execute_transform', 'manage_schedule', 'create_alert', 'start_run']),
  ANALYST: new Set(['read', 'profile', 'propose_rules']),
  VIEWER: new Set(['read']),
};

export function roleCan(raw: string | null | undefined, action: string): boolean {
  const role = normalizeUserRole(raw);
  return !!role && ROLE_PERMISSIONS[role].has(action);
}

export function userCanAccessDataset(
  user: UserProfile | null | undefined,
  datasetKey?: string | null,
): boolean {
  if (!datasetKey) return true;
  if (!user) return false;
  if (user.is_global || (user.datasets || []).includes('*')) return true;
  const key = String(datasetKey).split('::')[0];
  const aliases: Record<string, string> = {
    vinfast_ev_telemetry: 'ev_telemetry',
    vin_ev_ops: 'ev_telemetry',
    ev: 'ev_telemetry',
    vgreen: 'charging_sessions',
    xanhsm: 'trips',
    vin_trips_nlp: 'trips',
    nlp: 'nlp_feedback',
  };
  const norm = aliases[key] || key;
  return (user.datasets || []).includes(norm) || (user.datasets || []).includes(key);
}

export function filterDatasetsByAcl<T extends { key?: string; dataset_key?: string }>(
  items: T[],
  user: UserProfile | null | undefined,
): T[] {
  if (!user || user.is_global || (user.datasets || []).includes('*')) return items;
  return items.filter((d) => userCanAccessDataset(user, d.key || d.dataset_key));
}

// ============================================================================
// STORAGE & SESSION MANAGEMENT
// ============================================================================
// [P0 NOTICE]: Trong Phase 1, localStorage được dùng CHỈ CHO MỤC ĐÍCH DEMO / PROTOTYPE.
// Tuyệt đối không coi token/role trong localStorage là xác thực bảo mật server-side!
const DEMO_SESSION_KEY = 'datatrust_demo_session_v1';
const LEGACY_USER_KEY = 'datatrust_user_profile';
const TOKEN_KEY = 'datatrust_jwt_token';
const LOGGED_OUT_KEY = 'datatrust_logged_out';

interface AuthState {
  isDemoMode: boolean;
  token: string | null;
  user: UserProfile | null;
  currentPersona: PersonaAccount | null;
  systemAccess: SystemAccessType;
  isAuthenticated: boolean;
  isAuthModalOpen: boolean;

  setAuthModalOpen: (open: boolean) => void;
  loginWithPersona: (personaId: string) => string; // returns target redirect route
  loginWithCredentials: (username: string, password?: string) => Promise<string>;
  quickSwitchPersona: (personaId: string) => string;
  switchPersona: (personaId: string) => string;
  switchRoleViaBackend: (role: UserRole) => Promise<string>;
  restoreSession: () => boolean;
  logout: () => void;
  resetSessionState: () => void;

  // Backward compatibility methods
  isAdmin: () => boolean;
  isStewardOrAdmin: () => boolean;
  hasPermission: (action: string) => boolean;
  canReviewRules: () => boolean;
  canHitlWrite: () => boolean;
  canPropose: () => boolean;
  canExecute: () => boolean;
  canAccessDataset: (datasetKey?: string | null) => boolean;
}

function personaToProfile(p: PersonaAccount): UserProfile {
  return {
    user_id: `usr_${p.id}_01`,
    username: p.username,
    fullName: p.fullName,
    role: p.primaryRole,
    roles: p.roles,
    systemAccess: p.systemAccess,
    is_global: p.primaryRole === 'ADMIN' || p.primaryRole === 'AUDITOR',
    datasets: ['*'],
    dept: p.company,
    email: p.email,
    avatar: p.avatar,
    badge: p.badge,
  };
}

function loadInitialSession(): {
  user: UserProfile | null;
  persona: PersonaAccount | null;
  systemAccess: SystemAccessType;
  isAuthenticated: boolean;
} {
  if (typeof window === 'undefined') {
    return { user: null, persona: null, systemAccess: 'datatrust_only', isAuthenticated: false };
  }

  // If user explicitly logged out, keep them logged out (do NOT auto-login)
  try {
    if (localStorage.getItem(LOGGED_OUT_KEY) === 'true') {
      return { user: null, persona: null, systemAccess: 'datatrust_only', isAuthenticated: false };
    }
  } catch {}

  try {
    const raw = localStorage.getItem(DEMO_SESSION_KEY);
    if (raw) {
      const parsed = JSON.parse(raw);
      if (parsed && parsed.personaId && PERSONA_ACCOUNTS[parsed.personaId]) {
        const persona = PERSONA_ACCOUNTS[parsed.personaId];
        return {
          user: personaToProfile(persona),
          persona,
          systemAccess: persona.systemAccess,
          isAuthenticated: true,
        };
      }
    }
  } catch {}

  // Fallback to default persona for initial developer demo experience if never logged out
  const defaultPersona = PERSONA_ACCOUNTS.admin;
  return {
    user: personaToProfile(defaultPersona),
    persona: defaultPersona,
    systemAccess: defaultPersona.systemAccess,
    isAuthenticated: true,
  };
}

const initial = loadInitialSession();

export const useAuthStore = create<AuthState>((set, get) => ({
  isDemoMode: true,
  token: initial.isAuthenticated ? (readAuthToken() || 'demo_token_phase1') : null,
  user: initial.user,
  currentPersona: initial.persona,
  systemAccess: initial.systemAccess,
  isAuthenticated: initial.isAuthenticated,
  isAuthModalOpen: false,

  setAuthModalOpen: (open) => set({ isAuthModalOpen: open }),

  /**
   * Đăng nhập nhanh bằng Persona mẫu (1-click Quick Persona Picker).
   * Reset sạch state cũ trước khi nạp persona mới.
   */
  loginWithPersona: (personaOrUsername: string) => {
    const norm = String(personaOrUsername || '').trim().toLowerCase();
    const persona =
      PERSONA_ACCOUNTS[norm] ||
      Object.values(PERSONA_ACCOUNTS).find(
        (p) => p.username.toLowerCase() === norm || p.id.toLowerCase() === norm
      ) ||
      PERSONA_ACCOUNTS.admin;
    get().resetSessionState();

    const profile = personaToProfile(persona);
    try {
      localStorage.removeItem(LOGGED_OUT_KEY);
      localStorage.setItem(DEMO_SESSION_KEY, JSON.stringify({ personaId: persona.id, role: persona.primaryRole }));
      localStorage.setItem(LEGACY_USER_KEY, JSON.stringify(profile));
      localStorage.setItem('datatrust-role', persona.primaryRole.toLowerCase());
    } catch {}

    set({
      user: profile,
      currentPersona: persona,
      systemAccess: persona.systemAccess,
      isAuthenticated: true,
      token: `demo_token_${persona.id}`,
    });

    return persona.defaultRoute;
  },

  /**
   * Đăng nhập bằng username và password (form tiêu chuẩn).
   */
  loginWithCredentials: async (username: string, _password?: string) => {
    const normUser = String(username || '').trim().toLowerCase();
    // Tìm persona phù hợp với username
    const foundEntry = Object.entries(PERSONA_ACCOUNTS).find(
      ([, p]) => p.username.toLowerCase() === normUser || p.id.toLowerCase() === normUser
    );

    if (foundEntry) {
      return get().loginWithPersona(foundEntry[0]);
    }

    // Nếu không khớp sẵn, tạo profile tự động dựa trên username
    get().resetSessionState();
    const fallbackPersona = PERSONA_ACCOUNTS.admin;
    const profile: UserProfile = {
      user_id: `usr_${normUser}`,
      username: normUser,
      fullName: username,
      role: 'ADMIN',
      roles: ['ADMIN'],
      systemAccess: 'both',
      is_global: true,
      datasets: ['*'],
      dept: 'Data Platform',
      email: `${normUser}@company.vn`,
      avatar: normUser.slice(0, 2).toUpperCase(),
      badge: 'Quản trị viên hệ thống',
    };

    try {
      localStorage.removeItem(LOGGED_OUT_KEY);
      localStorage.setItem(DEMO_SESSION_KEY, JSON.stringify({ personaId: 'admin', customUser: normUser }));
      localStorage.setItem(LEGACY_USER_KEY, JSON.stringify(profile));
    } catch {}

    set({
      user: profile,
      currentPersona: fallbackPersona,
      systemAccess: 'both',
      isAuthenticated: true,
      token: 'demo_token_custom',
    });

    return '/overview';
  },

  /**
   * Chuyển Persona nhanh trong Demo Mode.
   * Reset toàn bộ dữ liệu tạm của persona trước.
   */
  quickSwitchPersona: (personaId: string) => {
    return get().loginWithPersona(personaId);
  },

  switchPersona: (personaId: string) => {
    return get().loginWithPersona(personaId);
  },

  /**
   * Chuyển đổi vai trò thông qua Backend API /api/auth/switch-role.
   * Cập nhật session_version và JWT token mới, hỗ trợ multi-party workflow context.
   */
  switchRoleViaBackend: async (role: UserRole) => {
    get().resetSessionState();
    try {
      const res = await authApi.switchRole(role);
      if (res && res.token) {
        persistAuthToken(res.token, res.user.active_role);
        const normRole = (normalizeUserRole(res.user.active_role) || role) as UserRole;
        const matchingPersona =
          Object.values(PERSONA_ACCOUNTS).find((p) => p.primaryRole === normRole) ||
          PERSONA_ACCOUNTS[normRole.toLowerCase()] ||
          PERSONA_ACCOUNTS.admin;

        const profile: UserProfile = {
          user_id: res.user.id,
          username: res.user.username,
          fullName: res.user.full_name,
          role: normRole,
          roles: [normRole],
          systemAccess: res.user.system_access,
          is_global: normRole === 'ADMIN' || normRole === 'AUDITOR',
          datasets: ['*'],
          dept: matchingPersona.company,
          email: matchingPersona.email,
          avatar: matchingPersona.avatar,
          badge: matchingPersona.badge,
        };

        try {
          localStorage.removeItem(LOGGED_OUT_KEY);
          localStorage.setItem(DEMO_SESSION_KEY, JSON.stringify({ personaId: matchingPersona.id, role: normRole }));
          localStorage.setItem(LEGACY_USER_KEY, JSON.stringify(profile));
          localStorage.setItem('datatrust-role', normRole.toLowerCase());
        } catch {}

        set({
          user: profile,
          currentPersona: matchingPersona,
          systemAccess: res.user.system_access,
          isAuthenticated: true,
          token: res.token,
        });

        return res.redirect || (res.user.system_access === 'sod_only' ? '/sod' : '/overview');
      }
    } catch (err) {
      console.warn('Backend switch-role call failed, falling back to local persona switch:', err);
    }
    // Fallback if backend API is offline
    const targetPersona = Object.values(PERSONA_ACCOUNTS).find((p) => p.primaryRole === role);
    return get().loginWithPersona(targetPersona ? targetPersona.id : 'admin');
  },

  /**
   * Khôi phục phiên làm việc từ localStorage khi F5 reload trang.
   */
  restoreSession: () => {
    const { user, persona, systemAccess } = loadInitialSession();
    if (user && persona) {
      set({
        user,
        currentPersona: persona,
        systemAccess,
        isAuthenticated: true,
      });
      return true;
    }
    return false;
  },

  /**
   * Làm sạch toàn bộ trạng thái phiên làm việc (state reset on switch).
   */
  resetSessionState: () => {
    try {
      sessionStorage.removeItem('sod_active_ticket_draft');
      sessionStorage.removeItem('sod_active_tab');
      sessionStorage.removeItem('sod_search_keyword');
    } catch {}
  },

  /**
   * Đăng xuất: Xóa phiên và đưa về trạng thái chưa xác thực.
   */
  logout: () => {
    get().resetSessionState();
    try {
      localStorage.setItem(LOGGED_OUT_KEY, 'true');
      localStorage.removeItem(DEMO_SESSION_KEY);
      localStorage.removeItem(LEGACY_USER_KEY);
      localStorage.removeItem(TOKEN_KEY);
      localStorage.removeItem('datatrust-token');
      localStorage.removeItem('datatrust_jwt_token');
      localStorage.removeItem('datatrust_user_profile');
      localStorage.removeItem('datatrust-role');
      sessionStorage.clear();
    } catch {}

    // Invalidate backend session asynchronously if reachable
    try {
      authApi.logout().catch(() => {});
    } catch {}

    set({
      token: null,
      user: null,
      currentPersona: null,
      systemAccess: 'datatrust_only',
      isAuthenticated: false,
    });
  },

  isAdmin: () => {
    const role = get().user?.role;
    return role === 'ADMIN';
  },

  isStewardOrAdmin: () => {
    const role = get().user?.role;
    return role === 'ADMIN' || role === 'DATA_STEWARD';
  },

  hasPermission: (action: string) => {
    const u = get().user;
    if (!u || !get().isAuthenticated) return false;
    return (u.roles || [u.role]).some((r) => roleCan(r, action));
  },

  canReviewRules: () => get().hasPermission('review_rules'),
  canHitlWrite: () => get().hasPermission('hitl_write'),
  canPropose: () => get().hasPermission('propose_rules'),
  canExecute: () => get().hasPermission('execute_transform'),
  canAccessDataset: (datasetKey) => get().isAuthenticated && userCanAccessDataset(get().user, datasetKey),
}));
