// NƠI DUY NHẤT quyết định ai được làm gì (KE_HOACH.md 9.3.2).
// Trang và Server Action gọi các hàm ở đây; trigger DB kiểm lại quyết định lần cuối.
import type { CurrentUser } from "@/lib/auth/session";
import { conflictsFor } from "@/lib/sod/conflicts";
import type { Phase } from "@/lib/sod/chain";
import type { RoleKey, StepAction } from "@/lib/sod/catalog";

export const hasRole = (u: CurrentUser, code: string) => u.roles.some((r) => r.code === code);

/** Người xem được mọi ticket (chỉ đọc) */
export const seesAllTickets = (u: CurrentUser) => hasRole(u, "AUD") || hasRole(u, "ADMIN");
export const canSubmitTicket = (u: CurrentUser) => hasRole(u, "REQ");
export const canViewAuditLog = (u: CurrentUser) => hasRole(u, "AUD");

type StepLike = { idx: number; roleCode: string; action: StepAction; assigneeId: string | null; status: string; sodWaived: boolean };
type TicketLike = { requesterId: string; status: string; phases: Phase[]; steps: StepLike[] };

export function canViewTicket(u: CurrentUser, t: TicketLike): boolean {
  if (t.requesterId === u.id || seesAllTickets(u)) return true;
  if (t.steps.some((s) => s.assigneeId === u.id)) return true;
  // Người được tham vấn (C) / nhận thông báo (I) của ticket
  const ci = new Set(t.phases.flatMap((p) => [...p.C, ...p.I]));
  return u.roles.some((r) => ci.has(r.code as RoleKey));
}

/** Lý do người dùng KHÔNG được quyết định bước đang xử lý. Rỗng = được phép. */
export function decisionBlockers(u: CurrentUser, t: TicketLike, step: StepLike | undefined): string[] {
  if (t.status !== "OPEN") return ["Ticket đã đóng."];
  if (!step || step.status !== "CURRENT" || step.idx === 0) return ["Bước này không ở trạng thái chờ xử lý."];
  const out: string[] = [];
  if (step.assigneeId !== u.id) out.push("Bạn không phải người được giao bước này.");
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
