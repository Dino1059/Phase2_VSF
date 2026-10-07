// NƠI DUY NHẤT quyết định ai được làm gì (KE_HOACH.md 9.3.2).
// Trang và Server Action gọi các hàm ở đây; trigger DB kiểm lại quyết định lần cuối.
import type { CurrentUser } from "@/lib/auth/session";
import type { ActingFor } from "@/lib/delegations/queries";
import { conflictsFor } from "@/lib/sod/conflicts";
import type { Phase } from "@/lib/sod/chain";
import type { RoleKey, StepAction } from "@/lib/sod/catalog";

export const hasRole = (u: CurrentUser, code: string) => u.roles.some((r) => r.code === code);

/** Người xem được mọi ticket (chỉ đọc) */
export const seesAllTickets = (u: CurrentUser) => hasRole(u, "AUD") || hasRole(u, "ADMIN");
export const canSubmitTicket = (u: CurrentUser) => hasRole(u, "REQ");
export const canViewAuditLog = (u: CurrentUser) => hasRole(u, "AUD");
/** Cấu hình có phiên bản: Admin đề xuất, CISO duyệt (người khác nhau), Auditor chỉ xem. KE_HOACH.md 1.1. */
export const canProposeConfig = (u: CurrentUser) => hasRole(u, "ADMIN");
export const canDecideConfig = (u: CurrentUser) => hasRole(u, "CISO");
export const canViewConfig = (u: CurrentUser) => hasRole(u, "ADMIN") || hasRole(u, "CISO") || hasRole(u, "AUD");

type StepLike = { idx: number; roleCode: string; action: StepAction; assigneeId: string | null; status: string; sodWaived: boolean };
type TicketLike = { requesterId: string; status: string; phases: Phase[]; steps: StepLike[]; typeId?: string; form?: unknown };

/** Lý do người dùng KHÔNG huỷ được phiếu. Rỗng = được phép. Chỉ người yêu cầu, và chỉ khi chưa tới bước thực hiện (P). */
export function cancelBlockers(u: CurrentUser, t: TicketLike): string[] {
  if (t.requesterId !== u.id) return ["Chỉ người yêu cầu mới huỷ được phiếu."];
  if (t.status !== "OPEN" && t.status !== "RETURNED") return ["Ticket đã đóng."];
  if (t.steps.some((s) => s.idx > 0 && s.action === "P" && (s.status === "CURRENT" || s.status === "DONE"))) {
    return ["Phiếu đã tới bước thực hiện nên không huỷ được. Muốn dừng thì mở phiếu thu hồi."];
  }
  return [];
}

/** `acting` = các ủy quyền còn hiệu lực mà u là người nhận: u xem được ticket có bước giao cho người ủy quyền. */
export function canViewTicket(u: CurrentUser, t: TicketLike, acting: ActingFor[] = []): boolean {
  if (t.requesterId === u.id || seesAllTickets(u)) return true;
  if (t.steps.some((s) => s.assigneeId === u.id || acting.some((a) => a.delegatorId === s.assigneeId && a.roleCode === s.roleCode))) return true;
  // Người được tham vấn (C) / nhận thông báo (I) của ticket
  const ci = new Set(t.phases.flatMap((p) => [...p.C, ...p.I]));
  return u.roles.some((r) => ci.has(r.code as RoleKey));
}

/** Lý do người dùng KHÔNG được quyết định bước đang xử lý. Rỗng = được phép. */
export function decisionBlockers(u: CurrentUser, t: TicketLike, step: StepLike | undefined, acting: ActingFor[] = []): string[] {
  if (t.status === "RETURNED") return ["Ticket đang chờ người yêu cầu bổ sung."];
  if (t.status !== "OPEN") return ["Ticket đã đóng."];
  if (!step || step.status !== "CURRENT" || step.idx === 0) return ["Bước này không ở trạng thái chờ xử lý."];
  const out: string[] = [];
  // Phiếu RBAC: người được cấp / bị thu hồi vai trò không được xử lý phiếu của chính mình
  if (t.typeId === "rbac" && (t.form as { targetUserId?: string } | undefined)?.targetUserId === u.id) {
    out.push("Người được cấp hoặc bị thu hồi vai trò không được xử lý phiếu này.");
  }
  // Người được giao, hoặc người được người đó ủy quyền (đúng vai trò của bước, còn hạn). Không ủy quyền cho bước 0.
  const delegated = acting.some((a) => a.delegatorId === step.assigneeId && a.roleCode === step.roleCode);
  if (step.assigneeId !== u.id && !delegated) out.push("Bạn không phải người được giao bước này.");
  if (!hasRole(u, step.roleCode)) out.push(`Bạn không còn giữ vai trò ${step.roleCode}.`);
  if (!step.sodWaived) {
    // Kiểm SoD theo người sẽ thao tác (không tin vào lúc gán)
    const chain = {
      requestor: t.requesterId,
      steps: t.steps.map((s) => ({ role: s.roleCode as RoleKey, action: s.action, assignee: s.assigneeId })),
    };
    out.push(...conflictsFor(chain, step.idx, u.id).map((c) => `Xung đột SoD: ${c}.`));
  }
  return out;
}
