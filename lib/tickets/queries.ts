import "server-only";
import { prisma } from "@/lib/db";
import type { CurrentUser } from "@/lib/auth/session";
import { canViewTicket, seesAllTickets } from "@/lib/authz/policy";
import type { Prisma } from "@/app/generated/prisma/client";
import type { Phase } from "@/lib/sod/chain";
import type { TicketForm } from "@/lib/sod/form";

const listSelect = {
  id: true,
  code: true,
  title: true,
  typeId: true,
  status: true,
  createdAt: true,
  steps: {
    where: { status: "CURRENT" },
    select: { roleCode: true, action: true, startedAt: true, dueAt: true, slaHours: true },
  },
} satisfies Prisma.TicketSelect;

const isOverdue = (steps: { status?: string; dueAt: Date | null }[], now = Date.now()) =>
  steps.some((s) => (s.status ?? "CURRENT") === "CURRENT" && !!s.dueAt && s.dueAt.getTime() < now);

export type TicketListItem = Prisma.TicketGetPayload<{ select: typeof listSelect }> & { overdue: boolean };
type TicketScope = "mine" | "inbox" | "handled" | "all";

/** Danh sách ticket theo phạm vi — chỉ những gì người dùng được xem. */
export async function listTickets(user: CurrentUser, scope: TicketScope, status?: "OPEN" | "DONE" | "REJECTED"): Promise<TicketListItem[]> {
  if (scope === "all" && !seesAllTickets(user)) return [];
  const where: Prisma.TicketWhereInput = {
    mine: { requesterId: user.id },
    inbox: { status: "OPEN" as const, steps: { some: { status: "CURRENT" as const, assigneeId: user.id, idx: { gt: 0 } } } },
    handled: { steps: { some: { idx: { gt: 0 }, decision: { actorId: user.id } } } },
    all: {},
  }[scope];
  const rows = await prisma.ticket.findMany({
    where: { ...where, ...(status && { status }) },
    orderBy: { createdAt: "desc" },
    take: 200,
    select: listSelect,
  });
  return rows.map((t) => ({ ...t, overdue: t.status === "OPEN" && isOverdue(t.steps) }));
}

export async function overviewCounts(user: CurrentUser) {
  const now = new Date();
  const [mineOpen, inbox, inboxOverdue] = await Promise.all([
    prisma.ticket.count({ where: { requesterId: user.id, status: "OPEN" } }),
    prisma.ticketStep.count({ where: { assigneeId: user.id, status: "CURRENT", idx: { gt: 0 } } }),
    prisma.ticketStep.count({ where: { assigneeId: user.id, status: "CURRENT", idx: { gt: 0 }, dueAt: { lt: now } } }),
  ]);
  return { mineOpen, inbox, inboxOverdue };
}

/** Chi tiết ticket, hoặc null nếu không tồn tại / không có quyền xem (trang trả 404 cho cả hai). */
export async function getTicket(user: CurrentUser, id: string) {
  if (!/^[0-9a-f-]{36}$/i.test(id)) return null;
  const t = await prisma.ticket.findUnique({
    where: { id },
    include: {
      requester: { select: { fullName: true } },
      steps: {
        orderBy: { idx: "asc" },
        include: {
          decision: { include: { actor: { select: { fullName: true } } } },
        },
      },
    },
  });
  if (!t) return null;
  const ticket = { ...t, phases: t.phases as Phase[], form: t.form as TicketForm, overdue: t.status === "OPEN" && isOverdue(t.steps) };
  return canViewTicket(user, ticket) ? ticket : null;
}
export type TicketDetail = NonNullable<Awaited<ReturnType<typeof getTicket>>>;

/** Nhật ký của một ticket, lấy từ audit_log (không lưu bản riêng). Lần thao tác bị chặn chỉ AUD / ADMIN thấy. */
export function ticketLog(user: CurrentUser, ticketId: string) {
  return prisma.auditLog.findMany({
    where: {
      targetType: "ticket",
      targetId: ticketId,
      ...(!seesAllTickets(user) && { action: { not: "ticket.decision.denied" } }),
    },
    orderBy: { id: "asc" },
    select: { id: true, occurredAt: true, actorEmail: true, action: true, details: true },
  });
}
