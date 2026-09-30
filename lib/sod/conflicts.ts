// Kiểm SoD trên một chuỗi xử lý (chuyển từ conflictsFor() / autoAssign() của bản mẫu).
// Chạy ở server khi gửi phiếu, khi gán người và ngay lúc bấm duyệt; trigger DB kiểm lại lần cuối.
import { ROLES, type RoleKey, type StepAction } from "./catalog";
import type { Chain } from "./chain";

export type Person = { id: string; name: string; roles: RoleKey[] };
/** Phần tối thiểu của chuỗi để kiểm SoD — dùng được cho cả chuỗi mới dựng lẫn ticket đã lưu */
type Assigned = { requestor: string; steps: { role: RoleKey; action: StepAction; assignee: string | null }[] };

const PAIR_NAMES: Record<string, string> = {
  "DEV|REL": "Developer ↔ Production Approver",
  "DEV|OPS": "Developer ↔ Production Deployer",
  "CISO|DEV": "Developer ↔ Production Approver",
  "DPO|SO": "DPO ↔ System Owner",
};

function pairName(a: RoleKey, b: RoleKey) {
  if (a === "AUD" || b === "AUD") return "Auditor ↔ Control Operator";
  if (a === "IAM" || b === "IAM") return "Approver ↔ IAM Provisioner";
  return PAIR_NAMES[[a, b].sort().join("|")] ?? `${ROLES[a].name} ↔ ${ROLES[b].name}`;
}

/** Người đi trước (Requestor) chỉ được làm bước P không phải cấp quyền / triển khai. */
const requestorMayAct = (step: { action: StepAction; role: RoleKey }) =>
  step.action === "P" && step.role !== "IAM" && step.role !== "OPS";

/** Các xung đột nếu giao bước i cho người pid. Rỗng = hợp lệ. */
export function conflictsFor(t: Assigned, i: number, pid: string | null): string[] {
  if (!pid) return ["Không có người đủ điều kiện cho vai trò này"];
  const s = t.steps[i];
  const out: string[] = [];
  if (i > 0 && pid === t.requestor && !requestorMayAct(s)) {
    out.push(s.action === "P" ? `Requestor ↔ ${ROLES[s.role].name}` : "Requestor ↔ Approver (tự duyệt yêu cầu của mình)");
  }
  t.steps.forEach((o, j) => {
    if (j === 0 || j === i || o.assignee !== pid || o.role === s.role) return;
    const n = pairName(s.role, o.role);
    if (!out.includes(n)) out.push(n);
  });
  return out;
}

export function autoAssign(t: Chain, people: Person[]) {
  t.steps.forEach((s, i) => {
    if (i === 0) return;
    const cands = people.filter((p) => p.roles.includes(s.role));
    s.assignee = cands.find((p) => conflictsFor(t, i, p.id).length === 0)?.id ?? cands[0]?.id ?? null;
  });
}

export const violations = (t: Assigned) =>
  t.steps.flatMap((s, i) => (i === 0 ? [] : conflictsFor(t, i, s.assignee).map((c) => ({ i, c }))));
