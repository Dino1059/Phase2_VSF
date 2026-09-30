// Quy tắc SoD theo rule.md — chuyển từ ../data.js của bản mẫu.
// Sau này chuyển thành bảng cấu hình có phiên bản (KE_HOACH.md 9.5).

export const ROLE_KEYS = ["REQ", "LM", "DPO", "SO", "CISO", "IAM", "DEV", "REL", "OPS", "AUD"] as const;
export type RoleKey = (typeof ROLE_KEYS)[number];

export const ROLES: Record<RoleKey, { name: string; short: string }> = {
  REQ: { name: "Requestor", short: "Req." },
  LM: { name: "Line Manager", short: "Line Mgr" },
  DPO: { name: "DPO/Compliance", short: "DPO" },
  SO: { name: "System Owner", short: "Sys Owner" },
  CISO: { name: "CISO/Security", short: "CISO" },
  IAM: { name: "IAM Administrator", short: "IAM" },
  DEV: { name: "Developer", short: "Dev" },
  REL: { name: "Release Manager", short: "Rel. Mgr" },
  OPS: { name: "Production Operator", short: "Prod. Op." },
  AUD: { name: "Auditor", short: "Auditor" },
};

export type Letter = "P" | "A" | "R" | "C" | "I" | "X";
export type StepAction = "P" | "R" | "A";

export const LETTERS: Record<Letter, string> = {
  P: "Được phép thực hiện",
  A: "Phê duyệt / chịu trách nhiệm cuối cùng",
  R: "Rà soát / xác nhận",
  C: "Được tham vấn",
  I: "Được thông báo",
  X: "Cấm kết hợp",
};

export const VERB: Record<StepAction, string> = { P: "Thực hiện", R: "Rà soát", A: "Phê duyệt" };

// Ma trận SoD — mỗi chuỗi 10 ký tự theo thứ tự ROLE_KEYS
// kind: approval = duyệt trước rồi mới thực thi (R → A → P); work = làm trước rồi rà soát (P → R → A)
type Activity = { id: number; name: string; kind: "approval" | "work"; m: string };
export const ACTIVITIES: Activity[] = [
  { id: 0, name: "Khởi tạo yêu cầu cấp quyền", kind: "work", m: "PXIIIXIIXI" },
  { id: 1, name: "Xác nhận nhu cầu nghiệp vụ", kind: "approval", m: "XACRIXXXXI" },
  { id: 2, name: "Phê duyệt quyền có truy cập PII", kind: "approval", m: "XAARCXXXXI" },
  { id: 3, name: "Phê duyệt quyền đặc quyền hoặc quyền DB", kind: "approval", m: "XCCAAXXXXI" },
  { id: 4, name: "Cấp quyền qua IAM/PAM", kind: "work", m: "XXXXRPXXXI" },
  { id: 5, name: "Thu hồi quyền khi nhân sự nghỉ việc", kind: "approval", m: "IAIRCPXXXR" },
  { id: 6, name: "Điều chuyển hoặc thay đổi vai trò", kind: "approval", m: "IACRIPXXXR" },
  { id: 7, name: "Tạo hoặc sửa RBAC role", kind: "approval", m: "XXCAAPXRXI" },
  { id: 8, name: "Phát triển mã nguồn", kind: "work", m: "XXXIRXPXXI" },
  { id: 9, name: "Kiểm thử và xác nhận kết quả", kind: "work", m: "XXCRRXPAXI" },
  { id: 10, name: "Phê duyệt phát hành Production", kind: "approval", m: "XXCRAXXAXI" },
  { id: 11, name: "Triển khai Production", kind: "work", m: "XXXIRXXXPI" },
  { id: 12, name: "Thay đổi giá, khuyến mại hoặc chính sách vận hành", kind: "approval", m: "PACARXXRPI" },
  { id: 13, name: "Truy vấn dữ liệu PII trực tiếp", kind: "approval", m: "PXAARPXXXI" },
  { id: 14, name: "Xuất dữ liệu PII", kind: "approval", m: "PAARRPXXXI" },
  { id: 15, name: "Phê duyệt ngoại lệ kiểm soát", kind: "approval", m: "XCAAAXXXXI" },
  { id: 16, name: "Điều tra sự cố bảo mật", kind: "work", m: "CICRAPCCPI" },
  { id: 17, name: "Đóng sự cố và xác nhận khắc phục", kind: "approval", m: "IICRAXXRRA" },
  { id: 18, name: "Rà soát quyền định kỳ", kind: "work", m: "IACRRPXXXA" },
];
export const EXCEPTION_ACTIVITY = 15;

/** Mã hoạt động: số = dòng ma trận, 'init' = khởi tạo ticket, 'bg' = hậu kiểm break-glass */
export type ActKey = number | "init" | "bg";
export const actName = (a: ActKey) =>
  a === "bg" ? "Hậu kiểm break-glass" : a === "init" ? "Khởi tạo ticket" : ACTIVITIES[a].name;
export const letter = (actId: number, role: RoleKey) => ACTIVITIES[actId].m[ROLE_KEYS.indexOf(role)] as Letter;

// Loại ticket → chuỗi hoạt động (KE_HOACH.md mục 3). Phiếu hiện tại dùng 'access' và 'offboard'.
const TICKET_TYPES = [
  { id: "offboard", name: "Thu hồi quyền (nghỉ việc)", acts: [5] },
  { id: "incident", name: "Sự cố bảo mật", acts: [16, 17] },
  { id: "pii_export", name: "Xuất dữ liệu PII", acts: [14] },
  { id: "pii_query", name: "Truy vấn dữ liệu PII trực tiếp", acts: [13] },
  { id: "exception", name: "Ngoại lệ kiểm soát", acts: [15] },
  { id: "pricing", name: "Thay đổi giá / khuyến mại / chính sách", acts: [12] },
  { id: "change", name: "Thay đổi mã nguồn → Production", acts: [8, 9, 10, 11] },
  { id: "rbac", name: "Tạo / sửa RBAC role", acts: [7] },
  { id: "transfer", name: "Điều chuyển / thay đổi vai trò", acts: [6] },
  { id: "review", name: "Rà soát quyền định kỳ", acts: [18] },
  { id: "access", name: "Cấp quyền truy cập", acts: [0, 1, 4] },
] as const;
export type TicketType = (typeof TICKET_TYPES)[number];
export const ticketType = (id: TicketType["id"]) => TICKET_TYPES.find((t) => t.id === id)!;

// Các cặp xung đột bắt buộc (rule.md mục 4)
export const CONFLICT_PAIRS: [string, string][] = [
  ["Requestor ↔ Approver", "Người tạo yêu cầu không được tự phê duyệt yêu cầu."],
  ["Approver ↔ IAM Provisioner", "Người phê duyệt không được tự cấp quyền."],
  ["Developer ↔ Production Approver", "Không tự phê duyệt phát hành mã do mình tạo."],
  ["Developer ↔ Production Deployer", "Không tự triển khai thay đổi lên Production."],
  ["Data Exporter ↔ Data Approver", "Người xuất PII không tự phê duyệt việc xuất."],
  ["Incident Investigator ↔ Closure Approver", "Người điều tra không tự xác nhận đóng sự cố."],
  ["IAM Administrator ↔ Access Reviewer", "Người cấp quyền không tự rà soát quyền."],
  ["Auditor ↔ Control Operator", "Kiểm toán viên không thực hiện hoạt động mình kiểm toán."],
];

// Cấu hình SLA — giá trị bản mẫu, chờ chốt (KE_HOACH.md mục 8). Admin sửa ở bước 6.
export type Priority = "urgent" | "high" | "normal" | "low";
export const SOD_CONFIG = {
  sla: { P: 8, R: 24, A: 24 } as Record<StepAction, number>, // giờ cho mỗi bước
  breakGlassHours: 24, // hậu kiểm break-glass (QT 5.5)
  priority: { urgent: 0.25, high: 0.5, normal: 1, low: 2 } as Record<Priority, number>,
  remindPct: 75,
  escalatePct: 100,
  criticalPct: 200,
  retentionDays: 1825,
  // Cấp thẩm quyền: số nhỏ duyệt trước, số lớn chốt sau
  rank: { REQ: 0, DEV: 1, OPS: 1, IAM: 2, LM: 3, REL: 3, SO: 4, DPO: 5, CISO: 6, AUD: 9 } as Record<RoleKey, number>,
};

export const PRIORITY_LABEL: Record<Priority, string> = { urgent: "Khẩn cấp", high: "Cao", normal: "Trung bình", low: "Thấp" };
