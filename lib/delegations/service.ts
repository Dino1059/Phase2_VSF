import "server-only";
import { prisma } from "@/lib/db";
import { AuditAction, writeAudit, type RequestMeta } from "@/lib/audit";
import type { CurrentUser } from "@/lib/auth/session";
import { hasRole } from "@/lib/authz/policy";
import { ROLES, type RoleKey, type StepAction } from "@/lib/sod/catalog";
import { activeConfig } from "@/lib/config/queries";
import { conflictsFor } from "@/lib/sod/conflicts";
import { notify } from "@/lib/notify/service";
import { fmtDate } from "@/lib/format";
import { TicketError } from "@/lib/tickets/service";

/** Vai trò có thể được giao bước xử lý, nên mới có thể ủy quyền */
export const DELEGABLE_ROLES = ["LM", "DPO", "SO", "CISO", "IAM", "DEV", "REL", "OPS", "AUD"] as const;

const DAY = 86_400_000;

type Input = { roleCode: string; delegateId: string; validFrom: Date; validTo: Date; reason: string };

/**
 * Ủy quyền vắng mặt: người giữ vai trò `roleCode` cho người CÙNG vai trò xử lý thay trong một khoảng thời gian.
 * Từ chối khi: sai vai trò, người nhận không hợp lệ, quá dài, hoặc người nhận gây xung đột SoD
 * trên bất kỳ phiếu đang mở nào có bước giao cho người ủy quyền (KE_HOACH.md luồng 5).
 */
export async function createDelegation(user: CurrentUser, input: Input, meta: RequestMeta): Promise<void> {
  const reason = input.reason.trim().slice(0, 500);
  try {
    await prisma.$transaction(async (tx) => {
      if (!(DELEGABLE_ROLES as readonly string[]).includes(input.roleCode)) throw new TicketError("Vai trò này không có bước xử lý nên không ủy quyền được.");
      if (!hasRole(user, input.roleCode)) throw new TicketError(`Bạn không giữ vai trò ${ROLES[input.roleCode as RoleKey].name}.`);
      if (input.delegateId === user.id) throw new TicketError("Không thể tự ủy quyền cho chính mình.");
      if (!reason) throw new TicketError("Nhập lý do ủy quyền.");
      const now = Date.now();
      if (!(input.validFrom < input.validTo)) throw new TicketError("Ngày kết thúc phải sau ngày bắt đầu.");
      if (input.validTo.getTime() <= now) throw new TicketError("Ngày kết thúc đã qua.");
      const maxDays = (await activeConfig(tx)).config.delegationMaxDays;
      if (input.validTo.getTime() - input.validFrom.getTime() > maxDays * DAY) {
        throw new TicketError(`Ủy quyền tối đa ${maxDays} ngày.`);
      }

      const nowDate = new Date();
      const delegate = await tx.user.findFirst({
        where: {
          id: input.delegateId,
          status: "ACTIVE",
          roles: { some: { roleCode: input.roleCode, validFrom: { lte: nowDate }, OR: [{ validTo: null }, { validTo: { gt: nowDate } }] } },
        },
        select: { id: true, fullName: true },
      });
      if (!delegate) throw new TicketError("Chỉ ủy quyền được cho người đang hoạt động và cùng vai trò.");

      const dup = await tx.delegation.findFirst({
        where: {
          delegatorId: user.id,
          delegateId: delegate.id,
          roleCode: input.roleCode,
          revokedAt: null,
          validFrom: { lt: input.validTo },
          validTo: { gt: input.validFrom },
        },
      });
      if (dup) throw new TicketError("Đã có ủy quyền trùng thời gian cho người này. Thu hồi ủy quyền cũ trước.");

      // Kiểm lại SoD: người nhận có xử lý được các bước đang giao cho mình không?
      const tickets = await tx.ticket.findMany({
        where: { status: { in: ["OPEN", "RETURNED"] }, steps: { some: { assigneeId: user.id, roleCode: input.roleCode, status: { in: ["CURRENT", "WAITING"] } } } },
        select: { code: true, requesterId: true, steps: { orderBy: { idx: "asc" }, select: { idx: true, roleCode: true, action: true, assigneeId: true, status: true } } },
      });
      const problems: string[] = [];
      for (const t of tickets) {
        const chain = { requestor: t.requesterId, steps: t.steps.map((s) => ({ role: s.roleCode as RoleKey, action: s.action as StepAction, assignee: s.assigneeId })) };
        for (const s of t.steps) {
          if (s.assigneeId !== user.id || s.roleCode !== input.roleCode || s.status === "DONE") continue;
          for (const c of conflictsFor(chain, s.idx, delegate.id)) problems.push(`${t.code}: ${c}`);
        }
      }
      if (problems.length) {
        throw new TicketError(`${delegate.fullName} xung đột SoD trên phiếu đang mở nên không nhận ủy quyền được. ${[...new Set(problems)].join("; ")}.`);
      }

      const d = await tx.delegation.create({
        data: { delegatorId: user.id, delegateId: delegate.id, roleCode: input.roleCode, validFrom: input.validFrom, validTo: input.validTo, reason },
      });
      await notify(tx, [{
        userId: delegate.id,
        kind: "DELEGATION",
        level: "info",
        message: `${user.fullName} ủy quyền vai trò ${ROLES[input.roleCode as RoleKey].name} cho bạn từ ${fmtDate(input.validFrom)} đến ${fmtDate(input.validTo)}. Việc của họ sẽ hiện trong Hộp việc của bạn.`,
        dedupeKey: `delegation:${d.id}`,
      }]);
      await writeAudit(
        {
          action: AuditAction.DelegationCreated,
          actorUserId: user.id,
          actorEmail: user.email,
          targetType: "delegation",
          targetId: d.id,
          details: { role: input.roleCode, delegate: delegate.id, from: input.validFrom, to: input.validTo, reason },
          meta,
        },
        tx,
      );
    });
  } catch (e) {
    const msg = e instanceof TicketError ? e.message : e instanceof Error ? /SoD: [^\n"]+/.exec(e.message)?.[0] : undefined;
    if (!msg) throw e;
    await writeAudit({
      action: AuditAction.DelegationDenied,
      actorUserId: user.id,
      actorEmail: user.email,
      targetType: "delegation",
      details: { role: input.roleCode, delegate: input.delegateId, reason: msg },
      meta,
    });
    throw new TicketError(msg);
  }
}

/** Người ủy quyền thu hồi ủy quyền của mình. Quyết định đã ghi giữ nguyên. */
export async function revokeDelegation(user: CurrentUser, id: string, meta: RequestMeta): Promise<void> {
  await prisma.$transaction(async (tx) => {
    const d = await tx.delegation.findFirst({ where: { id, delegatorId: user.id, revokedAt: null } });
    if (!d) throw new TicketError("Không tìm thấy ủy quyền còn hiệu lực của bạn.");
    await tx.delegation.update({ where: { id }, data: { revokedAt: new Date() } });
    await writeAudit(
      {
        action: AuditAction.DelegationRevoked,
        actorUserId: user.id,
        actorEmail: user.email,
        targetType: "delegation",
        targetId: id,
        details: { role: d.roleCode, delegate: d.delegateId },
        meta,
      },
      tx,
    );
  });
}
