import "server-only";
import { prisma } from "@/lib/db";
import { AuditAction, writeAudit, type RequestMeta } from "@/lib/audit";
import type { CurrentUser } from "@/lib/auth/session";
import { activeConfig } from "@/lib/config/queries";
import { buildChainFor } from "@/lib/sod/chain";
import { violations } from "@/lib/sod/conflicts";
import { OPS_TYPE_LABEL, classifyOps, type OpsForm, type ReviewSnapshot } from "@/lib/sod/ops";
import type { TicketForm } from "@/lib/sod/form";
import { activePeople, persistTicket } from "./service";

/** Tài khoản hệ thống mở phiếu rà soát định kỳ. Có vai trò REQ, status DISABLED nên không đăng nhập được (xem prisma/seed.ts). */
export const SYSTEM_USERNAME = "system";
const SNAPSHOT_MAX_ROWS = 500;
/** Hệ số SLA của phiếu rà soát: với SLA mặc định (P 8h, R/A 24h) thành P 5 ngày, R/A 15 ngày */
export const REVIEW_SLA_FACTOR = 15;
const meta: RequestMeta = { ip: null, userAgent: "scheduler" };

/** Quý theo giờ Việt Nam, ví dụ "2026-Q4" */
export function periodOf(now: Date): string {
  const vn = new Date(now.getTime() + 7 * 3_600_000);
  return `${vn.getUTCFullYear()}-Q${Math.floor(vn.getUTCMonth() / 3) + 1}`;
}

export type ReviewResult = { created: true; id: string; code: string; period: string } | { created: false; period: string; reason: string };

/**
 * Mở phiếu rà soát quyền định kỳ của quý hiện tại nếu chưa có (mọi trạng thái đều tính, nên đóng / huỷ rồi cũng không tự mở lại).
 * Chạy lặp bao nhiêu lần cũng chỉ tạo một phiếu mỗi quý. Ảnh chụp quyền đang có nằm trong phiếu, mã băm phiếu bao gồm nó.
 */
export async function openQuarterlyReview(now = new Date()): Promise<ReviewResult> {
  const period = periodOf(now);
  const sys = await prisma.user.findUnique({
    where: { username: SYSTEM_USERNAME },
    include: { roles: { where: { roleCode: "REQ", validFrom: { lte: now }, OR: [{ validTo: null }, { validTo: { gt: now } }] } } },
  });
  if (!sys || !sys.roles.length) return { created: false, period, reason: `Chưa có tài khoản hệ thống “${SYSTEM_USERNAME}” (chạy lại prisma db seed).` };
  const user: CurrentUser = { id: sys.id, username: sys.username, email: sys.email, fullName: sys.fullName, mustChangePassword: false, lastLoginAt: null, roles: [{ code: "REQ", name: "Requestor" }] };

  return prisma.$transaction(async (tx): Promise<ReviewResult> => {
    await tx.$executeRaw`SELECT pg_advisory_xact_lock(hashtext(${`review:${period}`}))`;
    const exists = await tx.ticket.findFirst({ where: { typeId: "review", form: { path: ["fields", "ky"], equals: period } }, select: { code: true } });
    if (exists) return { created: false, period, reason: `Quý ${period} đã có phiếu ${exists.code}.` };

    const snapshot = await snapshotOf(tx, now, period);
    const cfg = await activeConfig(tx);
    const chain = buildChainFor(classifyOps({ type: "review", pii: false }, cfg.config.matrix), user.id, await activePeople(tx), cfg.config.matrix);
    if (chain.steps.some((s, i) => i > 0 && !s.assignee)) return { created: false, period, reason: "Thiếu người giữ một vai trò trong chuỗi rà soát." };
    if (violations(chain).length) return { created: false, period, reason: "Chuỗi rà soát vi phạm SoD với những người hiện có." };

    const form: OpsForm = {
      kind: "ops",
      type: "review",
      title: `Quý ${period}`,
      system: "Toàn bộ hệ thống",
      urgent: false,
      pii: false,
      reason: "Rà soát quyền định kỳ hằng quý (rule.md, dòng 19). Người rà soát đối chiếu danh sách quyền đính kèm; quyền không còn cần thì mở phiếu thu hồi.",
      fields: { ky: period, soQuyen: String(snapshot.grants.length), soVaiTro: String(snapshot.roles.length) },
      snapshot,
    };
    const created = await persistTicket(
      tx, user, chain,
      { snapshot: form, title: `${OPS_TYPE_LABEL.review} – ${period}`, system: form.system, priority: "normal", exception: false, conflicts: [], waived: new Set(), slaFactor: REVIEW_SLA_FACTOR },
      cfg, meta,
    );
    await writeAudit(
      { action: AuditAction.TicketScheduled, actorUserId: user.id, actorEmail: user.email, targetType: "ticket", targetId: created.id, details: { code: created.code, type: "review", period, grants: snapshot.grants.length, roles: snapshot.roles.length }, meta },
      tx,
    );
    return { created: true, id: created.id, code: created.code, period };
  });
}

type Db = Parameters<Parameters<typeof prisma.$transaction>[0]>[0];

/** Quyền đang có: phiếu cấp quyền đã xong, còn hạn, chưa bị phiếu thu hồi xong sau đó; cùng các vai trò SoD Flow còn hiệu lực. */
async function snapshotOf(tx: Db, now: Date, period: string): Promise<ReviewSnapshot> {
  const today = new Date(now.getTime() + 7 * 3_600_000).toISOString().slice(0, 10);
  const [granted, revoked, roles] = await Promise.all([
    tx.ticket.findMany({ where: { typeId: "access", status: "DONE" }, select: { code: true, form: true, closedAt: true }, orderBy: { closedAt: "asc" } }),
    tx.ticket.findMany({ where: { typeId: "offboard", status: "DONE" }, select: { form: true, closedAt: true } }),
    tx.userRole.findMany({
      where: { validFrom: { lte: now }, OR: [{ validTo: null }, { validTo: { gt: now } }], user: { status: "ACTIVE" } },
      select: { roleCode: true, validTo: true, user: { select: { fullName: true } } },
      orderBy: [{ user: { fullName: "asc" } }, { roleCode: "asc" }],
    }),
  ]);
  // Phiếu thu hồi chỉ bỏ đúng hệ thống / tài nguyên đã thu hồi của người đó, đóng sau phiếu cấp
  const key = (email: string, system: string, resource: string) => [email, system, resource].map((x) => (x ?? "").trim().toLowerCase()).join("|");
  const revokedAt = new Map<string, number>();
  for (const r of revoked) {
    const f = r.form as TicketForm;
    if (!r.closedAt || !f.email) continue;
    for (const row of f.rows ?? []) {
      const k = key(f.email, row.heThong, row.taiNguyen);
      revokedAt.set(k, Math.max(revokedAt.get(k) ?? 0, r.closedAt.getTime()));
    }
  }
  const grants: ReviewSnapshot["grants"] = [];
  for (const t of granted) {
    const f = t.form as TicketForm;
    if (!t.closedAt) continue;
    for (const r of f.rows ?? []) {
      if (!r.heThong.trim() || (r.thoiHan && r.thoiHan < today)) continue;
      if ((revokedAt.get(key(f.email, r.heThong, r.taiNguyen)) ?? 0) > t.closedAt.getTime()) continue;
      grants.push({ ticket: t.code, user: f.hoTen, email: f.email, system: r.heThong, resource: r.taiNguyen, permission: r.mucQuyen, until: r.thoiHan });
    }
  }
  const rows = roles.map((r) => ({ user: r.user.fullName, role: r.roleCode, until: r.validTo ? r.validTo.toISOString().slice(0, 10) : "" }));
  return {
    period,
    generatedAt: now.toISOString(),
    grants: grants.slice(0, SNAPSHOT_MAX_ROWS),
    roles: rows.slice(0, SNAPSHOT_MAX_ROWS),
    truncated: grants.length > SNAPSHOT_MAX_ROWS || rows.length > SNAPSHOT_MAX_ROWS,
  };
}
