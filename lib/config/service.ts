import "server-only";
import { prisma } from "@/lib/db";
import type { Prisma } from "@/app/generated/prisma/client";
import { AuditAction, writeAudit, type AuditAction as AuditActionName, type RequestMeta } from "@/lib/audit";
import type { CurrentUser } from "@/lib/auth/session";
import { canDecideConfig, canProposeConfig } from "@/lib/authz/policy";
import { notify } from "@/lib/notify/service";
import { TicketError } from "@/lib/tickets/service";
import { activeConfig } from "./queries";
import { ConfigSchema, diffConfig } from "./schema";

/** Chuyển lỗi DB "SoD: …" thành TicketError, ghi nhật ký bị chặn. Lỗi khác ném tiếp. */
async function denied(e: unknown, user: CurrentUser, details: Prisma.InputJsonObject, meta: RequestMeta): Promise<never> {
  const reason = e instanceof TicketError ? e.message : e instanceof Error ? /SoD: [^\n"]+/.exec(e.message)?.[0] : undefined;
  if (!reason) throw e;
  await writeAudit({ action: AuditAction.ConfigDenied, actorUserId: user.id, actorEmail: user.email, targetType: "config", details: { ...details, reason }, meta });
  throw new TicketError(reason);
}

const audit = (action: AuditActionName, user: CurrentUser, id: string, details: Prisma.InputJsonObject, meta: RequestMeta) =>
  ({ action, actorUserId: user.id, actorEmail: user.email, targetType: "config", targetId: id, details, meta });

/** Admin đề xuất một phiên bản cấu hình mới. Chưa có hiệu lực cho tới khi CISO (người khác) duyệt. */
export async function proposeConfig(user: CurrentUser, input: unknown, reason: string, meta: RequestMeta): Promise<{ id: string; seq: number }> {
  try {
    if (!canProposeConfig(user)) throw new TicketError("Chỉ Quản trị SoD mới đề xuất đổi cấu hình.");
    const parsed = ConfigSchema.safeParse(input);
    if (!parsed.success) throw new TicketError(`Cấu hình không hợp lệ: ${[...new Set(parsed.error.issues.map((i) => i.message))].slice(0, 3).join("; ")}.`);
    const why = reason.trim().slice(0, 1000);
    if (!why) throw new TicketError("Nhập lý do đề xuất.");
    return await prisma.$transaction(async (tx) => {
      const base = await activeConfig(tx);
      const changes = diffConfig(base.config, parsed.data);
      if (!changes.length) throw new TicketError("Đề xuất không có thay đổi nào so với phiên bản đang hiệu lực.");
      const row = await tx.configVersion.create({
        data: { config: parsed.data, reason: why, baseSeq: base.seq, proposedById: user.id },
        select: { id: true, seq: true },
      });
      const cisos = await tx.user.findMany({
        where: { status: "ACTIVE", id: { not: user.id }, roles: { some: { roleCode: "CISO", validFrom: { lte: new Date() }, OR: [{ validTo: null }, { validTo: { gt: new Date() } }] } } },
        select: { id: true },
      });
      await notify(tx, cisos.map((c) => ({
        userId: c.id,
        kind: "CONFIG" as const,
        level: "info" as const,
        message: `${user.fullName} đề xuất đổi cấu hình (phiên bản ${row.seq}, ${changes.length} thay đổi). Vào Quản trị để duyệt.`,
        dedupeKey: `config:${row.id}`,
      })));
      await writeAudit(audit(AuditAction.ConfigProposed, user, row.id, { seq: row.seq, baseSeq: base.seq, changes, reason: why }, meta), tx);
      return row;
    });
  } catch (e) {
    return denied(e, user, { action: "propose" }, meta);
  }
}

/** CISO duyệt hoặc từ chối đề xuất. Người đề xuất không tự duyệt được; đề xuất đã cũ (có phiên bản khác lên thay) không duyệt được. */
export async function decideConfig(user: CurrentUser, id: string, approve: boolean, note: string, meta: RequestMeta): Promise<void> {
  try {
    if (!canDecideConfig(user)) throw new TicketError("Chỉ CISO mới duyệt thay đổi cấu hình.");
    const why = note.trim().slice(0, 1000);
    if (!approve && !why) throw new TicketError("Nhập lý do từ chối.");
    await prisma.$transaction(async (tx) => {
      await tx.$queryRaw`SELECT id FROM config_versions WHERE id = ${id}::uuid FOR UPDATE`;
      const row = await tx.configVersion.findUnique({ where: { id } });
      if (!row || row.status !== "PROPOSED") throw new TicketError("Không tìm thấy đề xuất đang chờ duyệt.");
      if (row.proposedById === user.id) throw new TicketError("Người đề xuất không được tự duyệt thay đổi cấu hình của mình.");
      const base = await activeConfig(tx);
      if (approve && row.baseSeq !== base.seq) throw new TicketError(`Đề xuất dựa trên phiên bản ${row.baseSeq} nhưng phiên bản ${base.seq} đã có hiệu lực. Admin cần đề xuất lại.`);
      await tx.configVersion.update({
        where: { id },
        data: { status: approve ? "ACTIVE" : "REJECTED", decidedById: user.id, decisionNote: why || null },
      });
      if (row.proposedById) {
        await notify(tx, [{
          userId: row.proposedById,
          kind: "CONFIG",
          level: approve ? "ok" : "warn",
          message: `Đề xuất cấu hình phiên bản ${row.seq} đã ${approve ? "được duyệt và có hiệu lực" : `bị từ chối: ${why}`} (${user.fullName}).`,
          dedupeKey: `config-result:${id}`,
        }]);
      }
      await writeAudit(audit(approve ? AuditAction.ConfigApproved : AuditAction.ConfigRejected, user, id, { seq: row.seq, note: why }, meta), tx);
    });
  } catch (e) {
    return denied(e, user, { action: approve ? "approve" : "reject", id }, meta);
  }
}

/** Người đề xuất rút lại đề xuất đang chờ */
export async function withdrawConfig(user: CurrentUser, id: string, meta: RequestMeta): Promise<void> {
  try {
    await prisma.$transaction(async (tx) => {
      const row = await tx.configVersion.findFirst({ where: { id, status: "PROPOSED", proposedById: user.id } });
      if (!row) throw new TicketError("Không tìm thấy đề xuất đang chờ của bạn.");
      await tx.configVersion.update({ where: { id }, data: { status: "CANCELLED", decidedById: user.id } });
      await writeAudit(audit(AuditAction.ConfigWithdrawn, user, id, { seq: row.seq }, meta), tx);
    });
  } catch (e) {
    return denied(e, user, { action: "withdraw", id }, meta);
  }
}
