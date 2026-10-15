import "server-only";
import { createHmac, timingSafeEqual } from "node:crypto";
import { prisma } from "@/lib/db";
import type { CurrentUser } from "@/lib/auth/session";

// Tích hợp với DataTrust OS. Hai hệ thống là hai ứng dụng riêng, nói chuyện qua HTTP có ký HMAC-SHA256 bằng bí mật dùng chung
// DATATRUST_SHARED_SECRET. Chuỗi được ký: `${timestamp}\n${METHOD}\n${pathname}\n${body}`, nên chữ ký của một API không dùng lại được cho API khác.

export const MAX_SKEW_SECONDS = 300;

export const signPayload = (secret: string, timestamp: string, method: string, pathname: string, body: string) =>
  createHmac("sha256", secret).update(`${timestamp}\n${method.toUpperCase()}\n${pathname}\n${body}`).digest("hex");

export type Verified = { ok: true; body: string } | { ok: false; status: 401 | 503; reason: string };

/** Kiểm chữ ký và độ lệch thời gian của một request từ DataTrust. Trả về nội dung body đã đọc. */
export async function verifyDatatrustRequest(req: Request): Promise<Verified> {
  const secret = process.env.DATATRUST_SHARED_SECRET;
  if (!secret || secret.length < 32) return { ok: false, status: 503, reason: "integration_not_configured" };
  const timestamp = req.headers.get("x-timestamp") ?? "";
  const signature = req.headers.get("x-signature") ?? "";
  const body = await req.text();
  const age = Math.abs(Date.now() / 1000 - Number(timestamp));
  if (!/^\d{9,12}$/.test(timestamp) || !Number.isFinite(age) || age > MAX_SKEW_SECONDS) return { ok: false, status: 401, reason: "stale_or_missing_timestamp" };
  const expected = Buffer.from(signPayload(secret, timestamp, req.method, new URL(req.url).pathname, body), "hex");
  const given = /^[a-f0-9]{64}$/.test(signature) ? Buffer.from(signature, "hex") : Buffer.alloc(0);
  if (given.length !== expected.length || !timingSafeEqual(given, expected)) return { ok: false, status: 401, reason: "bad_signature" };
  return { ok: true, body };
}

/** Người dùng SoD đang hoạt động theo username, dựng như phiên đăng nhập (vai trò còn hiệu lực). */
export async function loadUserByUsername(username: string): Promise<CurrentUser | null> {
  const now = new Date();
  const u = await prisma.user.findFirst({
    where: { username, status: "ACTIVE" },
    include: { roles: { where: { validFrom: { lte: now }, OR: [{ validTo: null }, { validTo: { gt: now } }] }, include: { role: true } } },
  });
  if (!u) return null;
  return {
    id: u.id,
    username: u.username,
    email: u.email,
    fullName: u.fullName,
    mustChangePassword: false,
    lastLoginAt: u.lastLoginAt,
    roles: u.roles.map((r) => ({ code: r.roleCode, name: r.role.name })),
  };
}

/** Tóm tắt phiếu cho DataTrust: trạng thái, nội dung đã duyệt (mã băm) và từng quyết định. */
export async function ticketSummary(code: string) {
  const t = await prisma.ticket.findUnique({
    where: { code },
    include: {
      requester: { select: { username: true } },
      steps: {
        orderBy: { idx: "asc" },
        include: {
          assignee: { select: { username: true } },
          decisions: { orderBy: { decidedAt: "asc" }, include: { actor: { select: { username: true, fullName: true } }, onBehalf: { select: { username: true } } } },
        },
      },
    },
  });
  if (!t) return null;
  const f = (t.form ?? {}) as { externalRef?: string; proposalHash?: string };
  const exec = t.steps.find((s) => s.idx > 0 && s.action === "P");
  return {
    ticket_code: t.code,
    type: t.typeId,
    status: t.status,
    external_ref: f.externalRef ?? null,
    proposal_hash: f.proposalHash ?? null,
    form_hash: t.formHash,
    requester_username: t.requester.username,
    /** Prod. Op. được giao thực thi; awaiting_execution = đã duyệt xong, chờ Executor chạy ở DataTrust */
    executor_username: exec?.assignee?.username ?? null,
    awaiting_execution: t.status === "OPEN" && exec?.status === "CURRENT",
    created_at: t.createdAt.toISOString(),
    closed_at: t.closedAt?.toISOString() ?? null,
    steps: t.steps.map((s) => ({
      idx: s.idx,
      role: s.roleCode,
      action: s.action,
      status: s.status,
      assignee: s.assignee?.username ?? null,
      decisions: s.decisions.map((d) => ({
        outcome: d.outcome,
        actor: d.actor.username,
        actor_name: d.actor.fullName,
        on_behalf_of: d.onBehalf?.username ?? null,
        decided_at: d.decidedAt.toISOString(),
        form_hash: d.formHash,
        comment: d.comment,
      })),
    })),
  };
}
