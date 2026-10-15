import "server-only";
import { prisma, type Tx } from "@/lib/db";
import type { Prisma } from "@/app/generated/prisma/client";
import { isDtForm, isDtType } from "@/lib/sod/datatrust";
import { signPayload } from "./datatrust";

// Gửi kết quả duyệt sang DataTrust. Sự kiện được ghi vào integration_outbox CÙNG transaction với quyết định duyệt, rồi gửi sau khi
// transaction commit (và gửi lại định kỳ bằng worker). DataTrust tắt thì sự kiện nằm chờ, không mất; DataTrust chống xử lý lặp theo event_id.

const TARGET = "datatrust";
const MAX_ATTEMPTS = 10;
export type ClosedStatus = "DONE" | "REJECTED" | "CANCELLED" | "EXPIRED";

/** Ghi sự kiện "phiếu đã đóng" nếu là phiếu DataTrust. Gọi trong transaction, sau khi đã cập nhật trạng thái phiếu. */
export async function enqueueTicketClosed(tx: Tx, ticketId: string, status: ClosedStatus): Promise<void> {
  const t = await tx.ticket.findUnique({
    where: { id: ticketId },
    include: {
      requester: { select: { username: true } },
      steps: {
        orderBy: { idx: "asc" },
        include: { decisions: { orderBy: { decidedAt: "asc" }, include: { actor: { select: { username: true } } } } },
      },
    },
  });
  if (!t || !isDtType(t.typeId) || !isDtForm(t.form)) return;
  const eventId = `${t.code}:${status}`;
  const payload = {
    event_id: eventId,
    ticket_code: t.code,
    type: t.typeId,
    status,
    external_ref: t.form.externalRef,
    proposal_hash: t.form.proposalHash,
    form_hash: t.formHash,
    requester_username: t.requester.username,
    closed_at: (t.closedAt ?? new Date()).toISOString(),
    approvers: t.steps
      .filter((s) => s.idx > 0)
      .flatMap((s) => s.decisions.map((d) => ({ role: s.roleCode, actor: d.actor.username, outcome: d.outcome, decided_at: d.decidedAt.toISOString() }))),
  };
  await tx.integrationOutbox.upsert({
    where: { eventId },
    create: { ticketId, eventId, target: TARGET, payload: payload as Prisma.InputJsonValue },
    update: {},
  });
}

type Claimed = { id: string; event_id: string; payload: unknown; attempts: number };

async function send(payload: unknown): Promise<string | null> {
  const base = process.env.DATATRUST_URL?.replace(/\/$/, "");
  const secret = process.env.DATATRUST_SHARED_SECRET;
  if (!base || !secret || secret.length < 32) return "not_configured";
  const path = "/api/integrations/sod/events";
  const body = JSON.stringify(payload);
  const ts = String(Math.floor(Date.now() / 1000));
  try {
    const res = await fetch(base + path, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Timestamp": ts, "X-Signature": signPayload(secret, ts, "POST", path, body) },
      body,
      signal: AbortSignal.timeout(5000),
    });
    return res.ok ? null : `HTTP ${res.status}`;
  } catch (e) {
    return e instanceof Error ? e.message.slice(0, 200) : "network_error";
  }
}

let flushing = false;

/**
 * Gửi các sự kiện đến hạn. "Nhận việc" bằng một UPDATE nguyên tử (FOR UPDATE SKIP LOCKED) đặt luôn lần thử kế tiếp theo
 * lịch lùi dần (30 giây, 2 phút, 10 phút, 1 giờ), nên hai tiến trình không gửi trùng và không cần giữ khoá khi gọi HTTP.
 */
export async function flushDatatrustOutbox(): Promise<{ sent: number; failed: number }> {
  if (flushing) return { sent: 0, failed: 0 };
  flushing = true;
  const result = { sent: 0, failed: 0 };
  try {
    const rows = await prisma.$queryRaw<Claimed[]>`
      UPDATE integration_outbox o
      SET attempts = o.attempts + 1,
          next_attempt_at = now() + (CASE LEAST(o.attempts, 3)
            WHEN 0 THEN interval '30 seconds' WHEN 1 THEN interval '2 minutes' WHEN 2 THEN interval '10 minutes' ELSE interval '1 hour' END)
      WHERE o.id IN (
        SELECT id FROM integration_outbox
        WHERE status = 'PENDING' AND target = ${TARGET} AND next_attempt_at <= now()
        ORDER BY created_at LIMIT 20 FOR UPDATE SKIP LOCKED
      )
      RETURNING o.id, o.event_id, o.payload, o.attempts`;
    for (const row of rows) {
      const error = await send(row.payload);
      if (!error) {
        await prisma.integrationOutbox.update({ where: { id: row.id }, data: { status: "SENT", sentAt: new Date(), lastError: null } });
        result.sent++;
      } else {
        await prisma.integrationOutbox.update({
          where: { id: row.id },
          data: { lastError: error.slice(0, 500), ...(row.attempts >= MAX_ATTEMPTS && { status: "FAILED" }) },
        });
        result.failed++;
      }
    }
  } finally {
    flushing = false;
  }
  return result;
}

/** Gửi ngay sau khi transaction commit, không chờ worker. Lỗi chỉ ghi log: sự kiện vẫn nằm trong outbox để thử lại. */
export function flushAfterCommit(): void {
  void flushDatatrustOutbox().catch((e) => console.error("[outbox] flush:", e));
}
