import "server-only";
import { prisma, type Tx } from "@/lib/db";
import { SOD_CONFIG } from "@/lib/sod/catalog";
import { fmtDur } from "@/lib/format";
import type { NotificationKind } from "@/app/generated/prisma/client";

export type NewNotification = {
  userId: string;
  ticketId: string;
  kind: NotificationKind;
  level: "info" | "warn" | "danger" | "ok";
  message: string;
  dedupeKey: string;
};

/** Ghi thông báo trong cùng transaction với sự kiện gây ra nó. Trùng dedupeKey thì bỏ qua. */
export async function notify(tx: Tx, items: NewNotification[]) {
  if (items.length) await tx.notification.createMany({ data: items.map((n) => ({ ...n, message: n.message.slice(0, 500) })), skipDuplicates: true });
}

/**
 * Tạo thông báo SLA (sắp hết hạn / quá hạn) cho các bước đang chờ người dùng.
 * Chạy mỗi lần chuông tải dữ liệu vì chưa có job nền; bước 7 chuyển sang pg-boss và gọi lại hàm này.
 */
export async function syncSlaNotifications(userId: string) {
  const steps = await prisma.ticketStep.findMany({
    where: { assigneeId: userId, status: "CURRENT", idx: { gt: 0 }, ticket: { status: "OPEN" }, dueAt: { not: null } },
    select: { id: true, startedAt: true, dueAt: true, ticket: { select: { id: true, code: true } } },
  });
  const now = Date.now();
  const items: NewNotification[] = [];
  for (const s of steps) {
    const start = s.startedAt!.getTime();
    const due = s.dueAt!.getTime();
    const pct = ((now - start) / Math.max(1, due - start)) * 100;
    const base = { userId, ticketId: s.ticket.id };
    if (pct >= SOD_CONFIG.escalatePct) {
      items.push({ ...base, kind: "SLA_OVERDUE", level: "danger", message: `${s.ticket.code} đã quá hạn SLA`, dedupeKey: `sla-overdue:${s.id}` });
    } else if (pct >= SOD_CONFIG.remindPct) {
      items.push({
        ...base,
        kind: "SLA_REMIND",
        level: "warn",
        message: `${s.ticket.code} sắp hết SLA — còn ${fmtDur(due - now)}`,
        dedupeKey: `sla-remind:${s.id}`,
      });
    }
  }
  await notify(prisma, items);
}

export async function listNotifications(userId: string) {
  const [items, unread] = await Promise.all([
    prisma.notification.findMany({
      where: { userId },
      orderBy: { createdAt: "desc" },
      take: 30,
      select: { id: true, ticketId: true, level: true, message: true, createdAt: true, readAt: true },
    }),
    prisma.notification.count({ where: { userId, readAt: null } }),
  ]);
  return { items, unread };
}
export type NotificationList = Awaited<ReturnType<typeof listNotifications>>;

/** Đánh dấu đã đọc — chỉ thông báo của chính người dùng. Không truyền id = tất cả. */
export async function markRead(userId: string, id?: string) {
  await prisma.notification.updateMany({ where: { userId, readAt: null, ...(id && { id }) }, data: { readAt: new Date() } });
}
