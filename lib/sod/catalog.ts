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
// Auditor R luôn chen ngay trước P (kiểm tra trước khi thực hiện).
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
  { id: 12, name: "Thay đổi giá, khuyến mại hoặc chính sách vận hành", kind: "approval", m: "PACARXXRII" },
  { id: 13, name: "Truy vấn dữ liệu PII nghiệp vụ (khách hàng) trực tiếp", kind: "approval", m: "PXAARXXXXI" },
  { id: 14, name: "Xuất dữ liệu PII nghiệp vụ (khách hàng)", kind: "approval", m: "PAARRXXXXI" },
  { id: 15, name: "Phê duyệt ngoại lệ kiểm soát", kind: "approval", m: "XCAAAXXXXI" },
  { id: 16, name: "Điều tra sự cố bảo mật", kind: "work", m: "CICRACCCPI" },
  { id: 17, name: "Đóng sự cố và xác nhận khắc phục", kind: "approval", m: "IICRAXXRRR" },
  { id: 18, name: "Rà soát quyền định kỳ", kind: "work", m: "IACPRIXXXR" },
];
export const EXCEPTION_ACTIVITY = 15;

/** Ma trận chuẩn theo rule.md (đã điều chỉnh 10/2026, xem MATRIX_NOTES). Phiên bản đang hiệu lực nằm trong bảng config_versions:
 *  muốn áp dụng ma trận chuẩn thì Admin đề xuất ở trang Quản trị và CISO duyệt. */
export const DEFAULT_MATRIX: readonly string[] = ACTIVITIES.map((a) => a.m);

/** Số thứ tự dòng hiển thị (bắt đầu từ 1) */
export const rowNo = (actId: number) => actId + 1;

// Quy tắc đọc ma trận (đã chốt khi rà soát ma trận, 10/2026)
export const MATRIX_RULES: string[] = [
  "Nhiều A trên một dòng = AND: tất cả người giữ A đều phải phê duyệt, lần lượt từ cấp thấp đến cấp cao.",
  "Mỗi dòng có tối đa một P (một người thực hiện).",
  "Auditor R = kiểm tra request có bị cấm hoặc vượt quyền không, ngay trước bước thực hiện (P). Auditor không giữ A.",
  "Hai loại dữ liệu: IAM được đọc dữ liệu định danh nhân viên (mã NV, họ tên, email công vụ, phòng ban, chức danh, trạng thái làm việc) để cấp / đổi / thu hồi account (dòng 5, 6, 7). IAM không đọc dữ liệu nghiệp vụ / PII khách hàng (dòng 14, 15). Không xem lương, CCCD, sức khỏe, đánh giá nhân sự.",
];

// Ghi chú các ô đã sửa, theo id hoạt động. roles = cột liên quan (được tô nổi trên ma trận).
export const MATRIX_NOTES: Record<number, { roles: RoleKey[]; text: string }> = {
  4: { roles: ["IAM"], text: "IAM được đọc dữ liệu định danh nhân viên (mã NV, phòng ban, chức danh, trạng thái làm việc) để mở account. Không đọc dữ liệu nghiệp vụ / khách hàng." },
  5: { roles: ["IAM", "AUD"], text: "IAM đọc trạng thái nghỉ việc của nhân viên để thu hồi account, không đọc dữ liệu nghiệp vụ. Auditor giữ R: kiểm tra yêu cầu thu hồi có bị cấm / vượt quyền không, trước khi IAM thực hiện." },
  6: { roles: ["IAM", "AUD"], text: "IAM đọc phòng ban / chức danh mới của nhân viên để đổi quyền, không đọc dữ liệu nghiệp vụ. Auditor giữ R: kiểm tra yêu cầu điều chuyển có bị cấm / vượt quyền không, trước khi IAM thực hiện." },
  12: { roles: ["OPS"], text: "Bỏ P thứ hai: chỉ Requestor thực hiện sau khi được duyệt; Prod. Op. P → I." },
  13: { roles: ["IAM"], text: "IAM P → X với dữ liệu khách hàng. IAM vẫn đọc dữ liệu định danh nhân viên để mở account ở dòng 5 (PAM/JIT), được nối sau bước duyệt; rồi Requestor mới truy vấn." },
  14: { roles: ["IAM"], text: "IAM P → X với dữ liệu khách hàng. IAM vẫn đọc dữ liệu định danh nhân viên để mở account ở dòng 5 (PAM/JIT), được nối sau bước duyệt; rồi Requestor mới xuất dữ liệu." },
  16: { roles: ["IAM"], text: "Bỏ P thứ hai: Prod. Op. điều tra; IAM P → C (cung cấp log truy cập, thông tin account)." },
  17: { roles: ["AUD"], text: "Auditor A → R: Auditor không phê duyệt đóng sự cố, chỉ kiểm tra; CISO duyệt cuối." },
  18: { roles: ["SO", "IAM", "AUD"], text: "Sys Owner R → P (thực hiện rà soát); IAM P → I (nhận kết quả để thu hồi, không tự rà soát quyền mình cấp); Auditor A → R." },
};

/** Mã hoạt động: số = dòng ma trận, 'init' = khởi tạo ticket, 'bg' = hậu kiểm break-glass */
export type ActKey = number | "init" | "bg";
export const actName = (a: ActKey) =>
  a === "bg" ? "Hậu kiểm break-glass" : a === "init" ? "Khởi tạo ticket" : ACTIVITIES[a].name;
export const letter = (actId: number, role: RoleKey, matrix: readonly string[] = DEFAULT_MATRIX) =>
  matrix[actId][ROLE_KEYS.indexOf(role)] as Letter;

// Loại ticket → chuỗi hoạt động (KE_HOACH.md mục 3). Phiếu hiện tại dùng 'access' và 'offboard'.
const TICKET_TYPES = [
  { id: "offboard", name: "Thu hồi quyền (nghỉ việc)", acts: [5] },
  { id: "incident", name: "Sự cố bảo mật", acts: [16, 17] },
  { id: "pii_export", name: "Xuất dữ liệu PII nghiệp vụ (khách hàng)", acts: [14, 4] },
  { id: "pii_query", name: "Truy vấn dữ liệu PII nghiệp vụ (khách hàng) trực tiếp", acts: [13, 4] },
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
  delegationMaxDays: 30, // ủy quyền vắng mặt tối đa [Cần chốt]
  staleCloseDays: 7, // quá số ngày này không ai xử lý thì Admin đóng phiếu "hết hạn" (BUILD_PLAN 4.5)
  // Cấp thẩm quyền: số nhỏ duyệt trước, số lớn chốt sau
  rank: { REQ: 0, DEV: 1, OPS: 1, IAM: 2, LM: 3, REL: 3, SO: 4, DPO: 5, CISO: 6, AUD: 9 } as Record<RoleKey, number>,
};

export const PRIORITY_LABEL: Record<Priority, string> = { urgent: "Khẩn cấp", high: "Cao", normal: "Trung bình", low: "Thấp" };
