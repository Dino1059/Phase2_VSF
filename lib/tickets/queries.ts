import "server-only";
import { prisma } from "@/lib/db";
import type { CurrentUser } from "@/lib/auth/session";
import { canViewTicket, seesAllTickets } from "@/lib/authz/policy";
import type { Prisma, TicketStatus } from "@/app/generated/prisma/client";
import type { Phase } from "@/lib/sod/chain";
import type { TicketForm } from "@/lib/sod/form";
import { activeDelegationsTo, type ActingFor } from "@/lib/delegations/queries";
import { parseConfigOrDefault } from "@/lib/config/queries";

/** Bước đang giao cho người dùng, hoặc cho người đã ủy quyền cho họ đúng vai trò */
const assignedToMe = (userId: string, acting: ActingFor[]) => ({
  OR: [{ assigneeId: userId }, ...acting.map((a) => ({ assigneeId: a.delegatorId, roleCode: a.roleCode }))],
});

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
export async function listTickets(user: CurrentUser, scope: TicketScope, status?: TicketStatus): Promise<TicketListItem[]> {
  if (scope === "all" && !seesAllTickets(user)) return [];
  const acting = scope === "inbox" ? await activeDelegationsTo(prisma, user.id) : [];
  const where: Prisma.TicketWhereInput = {
    mine: { requesterId: user.id },
    inbox: { status: "OPEN" as const, steps: { some: { status: "CURRENT" as const, idx: { gt: 0 }, ...assignedToMe(user.id, acting) } } },
    handled: { steps: { some: { idx: { gt: 0 }, decisions: { some: { actorId: user.id } } } } },
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
  const acting = await activeDelegationsTo(prisma, user.id);
  const [mineOpen, mineReturned, inbox, inboxOverdue] = await Promise.all([
    prisma.ticket.count({ where: { requesterId: user.id, status: "OPEN" } }),
    prisma.ticket.count({ where: { requesterId: user.id, status: "RETURNED" } }),
    prisma.ticketStep.count({ where: { ...assignedToMe(user.id, acting), status: "CURRENT", idx: { gt: 0 }, ticket: { status: "OPEN" } } }),
    prisma.ticketStep.count({ where: { ...assignedToMe(user.id, acting), status: "CURRENT", idx: { gt: 0 }, ticket: { status: "OPEN" }, dueAt: { lt: now } } }),
  ]);
  return { mineOpen, mineReturned, inbox, inboxOverdue };
}

/** Chi tiết ticket, hoặc null nếu không tồn tại / không có quyền xem (trang trả 404 cho cả hai). */
export async function getTicket(user: CurrentUser, id: string) {
  if (!/^[0-9a-f-]{36}$/i.test(id)) return null;
  const t = await prisma.ticket.findUnique({
    where: { id },
    include: {
      requester: { select: { fullName: true } },
      configVersion: { select: { config: true } },
      steps: {
        orderBy: { idx: "asc" },
        include: {
          assignee: { select: { fullName: true } },
          decisions: {
            orderBy: { rev: "desc" },
            take: 1,
            include: { actor: { select: { fullName: true } }, onBehalf: { select: { fullName: true } } },
          },
        },
      },
      revisions: { orderBy: { rev: "asc" }, select: { rev: true, createdAt: true, creator: { select: { fullName: true } } } },
    },
  });
  if (!t) return null;
  // Mỗi bước chỉ hiện quyết định còn hiệu lực: bước đã xong, hoặc bước vừa bị trả lại ở phiên bản nội dung hiện tại.
  // Bước phải duyệt lại (đã về Chờ) không còn hiện quyết định cũ.
  const steps = t.steps.map(({ decisions, ...s }) => {
    const last = decisions[0] ?? null;
    const live = last && (s.status === "DONE" || s.status === "REJECTED" || (last.outcome === "RETURN" && last.rev === t.rev));
    return { ...s, decision: live ? last : null };
  });
  // Số ngày bước hiện tại đã chờ, và ngưỡng "hết hạn" theo cấu hình lúc tạo phiếu (để Admin biết có đóng được không)
  const cur = t.steps.find((s) => s.status === "CURRENT" && s.idx > 0);
  const waitedDays = cur?.startedAt ? (Date.now() - cur.startedAt.getTime()) / 86_400_000 : 0;
  const staleDays = parseConfigOrDefault(t.configVersion.config).staleCloseDays;
  const ticket = { ...t, steps, waitedDays, staleDays, phases: t.phases as Phase[], form: t.form as TicketForm, overdue: t.status === "OPEN" && isOverdue(t.steps) };
  const acting = await activeDelegationsTo(prisma, user.id);
  return canViewTicket(user, ticket, acting) ? { ...ticket, acting } : null;
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

/** Người dùng đang hoạt động kèm vai trò còn hiệu lực — để chọn người được cấp / thu hồi vai trò trên phiếu RBAC. */
export async function rbacCandidates() {
  const now = new Date();
  const users = await prisma.user.findMany({
    where: { status: "ACTIVE" },
    orderBy: { fullName: "asc" },
    select: {
      id: true,
      fullName: true,
      username: true,
      roles: { where: { validFrom: { lte: now }, OR: [{ validTo: null }, { validTo: { gt: now } }] }, select: { roleCode: true } },
    },
  });
  return users.map((u) => ({ id: u.id, fullName: u.fullName, username: u.username, roles: u.roles.map((r) => r.roleCode) }));
}

/** Phiếu đang xử lý mà bước hiện tại đã quá hạn SLA — cho trang Quản trị (người xem được mọi phiếu). */
export async function overdueTickets(user: CurrentUser) {
  if (!seesAllTickets(user)) return [];
  const now = new Date();
  const rows = await prisma.ticketStep.findMany({
    where: { status: "CURRENT", idx: { gt: 0 }, dueAt: { lt: now }, ticket: { status: "OPEN" } },
    orderBy: { dueAt: "asc" },
    take: 50,
    select: {
      roleCode: true,
      startedAt: true,
      dueAt: true,
      assignee: { select: { fullName: true } },
      ticket: { select: { id: true, code: true, title: true, configVersion: { select: { config: true } } } },
    },
  });
  return rows.map((r) => ({
    id: r.ticket.id,
    code: r.ticket.code,
    title: r.ticket.title,
    roleCode: r.roleCode,
    assignee: r.assignee?.fullName ?? null,
    lateHours: (now.getTime() - r.dueAt!.getTime()) / 3_600_000,
    waitedDays: r.startedAt ? (now.getTime() - r.startedAt.getTime()) / 86_400_000 : 0,
    staleDays: parseConfigOrDefault(r.ticket.configVersion.config).staleCloseDays,
  }));
}
