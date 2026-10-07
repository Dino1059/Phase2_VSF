import "server-only";
import { prisma, type Tx } from "@/lib/db";
import { AuditAction, writeAudit } from "@/lib/audit";
import { parseConfigOrDefault } from "@/lib/config/queries";
import { ROLES, type RoleKey, type StepAction } from "@/lib/sod/catalog";
import { conflictsFor } from "@/lib/sod/conflicts";
import { notify, type NewNotification } from "@/lib/notify/service";
import type { SlaLevel } from "@/app/generated/prisma/client";

const HOUR = 3_600_000;
const DAY = 24 * HOUR;
const roleName = (c: string) => ROLES[c as RoleKey]?.name ?? c;

/** Người đang giữ một vai trò, hoạt động tại thời điểm `now` */
const holders = (tx: Tx, roleCode: string, now: Date) =>
  tx.user.findMany({
    where: { status: "ACTIVE", roles: { some: { roleCode, validFrom: { lte: now }, OR: [{ validTo: null }, { validTo: { gt: now } }] } } },
    orderBy: { createdAt: "asc" },
    select: { id: true, fullName: true },
  });

/** Ghi mốc SLA. Trả true nếu đây là lần đầu (mốc chưa từng được ghi cho bước này ở phiên bản nội dung này). */
async function recordOnce(tx: Tx, e: { ticketId: string; stepId: string; rev: number; level: SlaLevel; pct: number }) {
  const r = await tx.slaEvent.createMany({ data: [e], skipDuplicates: true });
  return r.count === 1;
}

/**
 * Duyệt mọi bước đang chờ và xử lý các mốc SLA (BUILD_PLAN 4.5). Chạy lặp lại bao nhiêu lần cũng được: mỗi mốc chỉ xảy ra một lần.
 *   REMIND   ≥ remindPct    nhắc người được giao (và người đang được ủy quyền)
 *   OVERDUE  ≥ escalatePct  báo người dự phòng cùng vai trò (không xung đột SoD) và Admin
 *   CRITICAL ≥ criticalPct  báo CISO và Auditor, ghi nhận vào nhật ký
 *   STALE    ≥ staleCloseDays ngày  báo Admin: có thể đóng phiếu "hết hạn"
 * KHÔNG bao giờ duyệt, từ chối hay chuyển bước. Mốc lấy theo cấu hình lúc tạo phiếu.
 */
export async function processSla(now = new Date()): Promise<{ events: number }> {
  const steps = await prisma.ticketStep.findMany({
    where: { status: "CURRENT", idx: { gt: 0 }, ticket: { status: "OPEN" }, startedAt: { not: null }, dueAt: { not: null } },
    select: {
      id: true,
      idx: true,
      roleCode: true,
      action: true,
      assigneeId: true,
      startedAt: true,
      dueAt: true,
      assignee: { select: { fullName: true } },
      ticket: {
        select: {
          id: true,
          code: true,
          rev: true,
          requesterId: true,
          configVersion: { select: { config: true } },
          steps: { orderBy: { idx: "asc" }, select: { roleCode: true, action: true, assigneeId: true } },
        },
      },
    },
  });

  let events = 0;
  for (const s of steps) {
    const cfg = parseConfigOrDefault(s.ticket.configVersion.config);
    const start = s.startedAt!.getTime();
    const due = s.dueAt!.getTime();
    const pct = ((now.getTime() - start) / Math.max(1, due - start)) * 100;
    const reached: SlaLevel[] = [];
    if (pct >= cfg.remindPct) reached.push("REMIND");
    if (pct >= cfg.escalatePct) reached.push("OVERDUE");
    if (pct >= cfg.criticalPct) reached.push("CRITICAL");
    if (now.getTime() - start >= cfg.staleCloseDays * DAY) reached.push("STALE");
    if (!reached.length) continue;

    await prisma.$transaction(async (tx) => {
      const t = s.ticket;
      const base = { ticketId: t.id };
      const who = s.assignee?.fullName ?? "chưa giao";
      const late = `${t.code}: bước ${roleName(s.roleCode)} (${who})`;
      const key = (name: string) => `${name}:${s.id}:${t.rev}`;
      const out: NewNotification[] = [];
      const chain = { requestor: t.requesterId, steps: t.steps.map((x) => ({ role: x.roleCode as RoleKey, action: x.action as StepAction, assignee: x.assigneeId })) };

      for (const level of reached) {
        if (!(await recordOnce(tx, { ticketId: t.id, stepId: s.id, rev: t.rev, level, pct }))) continue;
        events++;

        if (level === "REMIND" && !reached.includes("OVERDUE")) {
          // Người được giao và người đang được ủy quyền (cùng khoá với thông báo khi mở trang, nên không báo trùng)
          const delegates = await tx.delegation.findMany({
            where: { delegatorId: s.assigneeId ?? "", roleCode: s.roleCode, revokedAt: null, validFrom: { lte: now }, validTo: { gt: now } },
            select: { delegateId: true },
          });
          for (const uid of [s.assigneeId, ...delegates.map((d) => d.delegateId)].filter((x): x is string => !!x)) {
            out.push({ ...base, userId: uid, kind: "SLA_REMIND", level: "warn", message: `${t.code} sắp hết SLA: đã dùng ${Math.round(pct)}% thời hạn`, dedupeKey: key("sla-remind") });
          }
        }

        if (level === "OVERDUE") {
          const delegates = await tx.delegation.findMany({
            where: { delegatorId: s.assigneeId ?? "", roleCode: s.roleCode, revokedAt: null, validFrom: { lte: now }, validTo: { gt: now } },
            select: { delegateId: true },
          });
          const direct = [s.assigneeId, ...delegates.map((d) => d.delegateId)].filter((x): x is string => !!x);
          for (const uid of direct) {
            out.push({ ...base, userId: uid, kind: "SLA_OVERDUE", level: "danger", message: `${t.code} đã quá hạn SLA`, dedupeKey: key("sla-overdue") });
          }
          // Người dự phòng: cùng vai trò, không xung đột SoD với phiếu này. Chỉ để biết, không tự nhận việc.
          const backups = (await holders(tx, s.roleCode, now)).filter(
            (h) => !direct.includes(h.id) && h.id !== t.requesterId && conflictsFor(chain, s.idx, h.id).length === 0,
          );
          for (const b of backups) {
            out.push({ ...base, userId: b.id, kind: "SLA_OVERDUE", level: "warn", message: `${late} đã quá hạn. Bạn là người dự phòng cùng vai trò.`, dedupeKey: key("sla-backup") });
          }
          for (const a of await holders(tx, "ADMIN", now)) {
            out.push({ ...base, userId: a.id, kind: "SLA_OVERDUE", level: "warn", message: `${late} đã quá hạn SLA.`, dedupeKey: key("sla-admin") });
          }
        }

        if (level === "CRITICAL") {
          const people = new Map<string, string>();
          for (const role of ["CISO", "AUD"]) for (const h of await holders(tx, role, now)) people.set(h.id, h.fullName);
          for (const uid of people.keys()) {
            out.push({ ...base, userId: uid, kind: "SLA_OVERDUE", level: "danger", message: `${late} đã dùng ${Math.round(pct)}% thời hạn SLA (quá mốc nghiêm trọng).`, dedupeKey: key("sla-critical") });
          }
          await writeAudit(
            { action: AuditAction.SlaCritical, targetType: "ticket", targetId: t.id, details: { code: t.code, step: s.idx, role: s.roleCode, assignee: s.assigneeId, pct: Math.round(pct) }, meta: { ip: null, userAgent: "sla-worker" } },
            tx,
          );
        }

        if (level === "STALE") {
          for (const a of await holders(tx, "ADMIN", now)) {
            out.push({ ...base, userId: a.id, kind: "SLA_OVERDUE", level: "danger", message: `${late} đã chờ hơn ${cfg.staleCloseDays} ngày không ai xử lý. Admin có thể đóng phiếu "hết hạn".`, dedupeKey: key("sla-stale") });
          }
        }
      }
      await notify(tx, out);
    });
  }
  return { events };
}
