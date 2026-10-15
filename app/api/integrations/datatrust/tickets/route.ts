import { requestMeta } from "@/lib/audit";
import { DtInputSchema } from "@/lib/sod/datatrust";
import { TicketError, createDatatrustTicket } from "@/lib/tickets/service";
import { loadUserByUsername, ticketSummary, verifyDatatrustRequest } from "@/lib/integrations/datatrust";

// DataTrust gửi một đề xuất xử lý dữ liệu sang để duyệt. Xác thực bằng chữ ký HMAC, không dùng phiên đăng nhập.
const json = (body: unknown, status: number) => Response.json(body, { status, headers: { "Cache-Control": "no-store" } });

export async function POST(request: Request) {
  const v = await verifyDatatrustRequest(request);
  if (!v.ok) return json({ error: v.reason }, v.status);

  let raw: unknown;
  try {
    raw = JSON.parse(v.body);
  } catch {
    return json({ error: "invalid_json" }, 422);
  }
  const parsed = DtInputSchema.safeParse(raw);
  if (!parsed.success) return json({ error: "invalid_payload", fields: parsed.error.issues.map((i) => i.path.join(".")) }, 422);

  const requester = await loadUserByUsername(parsed.data.requesterUsername);
  if (!requester) return json({ error: "requester_not_found" }, 422);

  try {
    const r = await createDatatrustTicket(requester, parsed.data, await requestMeta());
    if (!r.ok) return json({ error: "rejected", details: r.errors }, 422);
    const summary = await ticketSummary(r.code);
    return json({ ticket_id: r.id, ticket_code: r.code, status: r.status, created: r.created, steps: summary?.steps.map((s) => ({ idx: s.idx, role: s.role, action: s.action, status: s.status })) ?? [] }, r.created ? 201 : 200);
  } catch (e) {
    if (e instanceof TicketError) return json({ error: "forbidden", message: e.message }, 403);
    throw e;
  }
}
