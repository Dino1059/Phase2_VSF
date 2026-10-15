// Phiếu do DataTrust gửi sang (PLAN_NOI_SOD_DATATRUST.md bước 2): chuỗi duyệt theo ma trận, chống trùng, chặn dữ liệu cá nhân,
// chữ ký HMAC. Chạy trên DB sod_test.
import { after, before, test } from "node:test";
import assert from "node:assert/strict";
import { prisma } from "@/lib/db";
import type { CurrentUser } from "@/lib/auth/session";
import { TicketError, createDatatrustTicket, decideStep, returnTicket } from "@/lib/tickets/service";
import type { DtInput } from "@/lib/sod/datatrust";
import { MAX_SKEW_SECONDS, signPayload, verifyDatatrustRequest } from "@/lib/integrations/datatrust";
import { AuditAction, writeAudit } from "@/lib/audit";
import { evidenceCsv, loadEvidence } from "@/lib/tickets/evidence";
import { approveCurrent, asUser, meta, reload } from "./helpers";

let an: CurrentUser, nam: CurrentUser;
before(async () => {
  [an, nam] = await Promise.all(["an.nguyen", "nam.dang"].map(asUser)); // nam.dang là Auditor, không có vai trò REQ
});
after(() => prisma.$disconnect());

let seq = 0;
const input = (over: Partial<DtInput> = {}): DtInput => ({
  type: "dt_remediation",
  requesterUsername: "an.nguyen",
  externalRef: `PROP-REM-TEST${++seq}`,
  proposalHash: (seq.toString(16).padStart(2, "0")).repeat(32),
  dataset: "ride_hailing_xanh_sm_trips",
  column: "customer_contact",
  operation: "MASK_PHONE",
  expectedRows: 42,
  riskLevel: "MEDIUM",
  pii: false,
  reason: "Che số điện thoại dạng rõ theo luật bảo vệ dữ liệu cá nhân",
  ...over,
});

const create = async (user: CurrentUser, i: DtInput) => {
  const r = await createDatatrustTicket(user, i, meta);
  assert.ok(r.ok, JSON.stringify(r));
  return r;
};
const chainOf = async (id: string) => (await reload(id)).steps.map((s) => `${s.roleCode}:${s.action}`);

test("K2.2: dt_remediation theo dòng 13 — Release Manager, CISO rà soát; Line Manager, System Owner phê duyệt; không có bước P", async () => {
  const r = await create(an, input());
  assert.equal(r.created, true);
  const t = await reload(r.id);
  assert.equal(t.typeId, "dt_remediation");
  assert.deepEqual(await chainOf(r.id), ["REQ:P", "REL:R", "CISO:R", "LM:A", "SO:A"]);
  assert.ok(!t.steps.some((s) => s.idx > 0 && s.action === "P"), "dòng 13 không có bước P cho người khác");
  assert.ok(t.steps.every((s) => s.idx === 0 || s.assigneeId !== an.id), "người gửi duyệt không nằm trong chuỗi duyệt");
});

test("K2.3: có dữ liệu cá nhân thì thêm DPO", async () => {
  const r = await create(an, input({ pii: true }));
  const roles = await chainOf(r.id);
  assert.ok(roles.includes("DPO:R"), roles.join(","));
});

test("K2.4: dt_override đi dòng 16 (DPO, SO, CISO phê duyệt) rồi dòng 13", async () => {
  const r = await create(an, input({ type: "dt_override" }));
  const roles = await chainOf(r.id);
  for (const need of ["SO:A", "DPO:A", "CISO:A", "REL:R", "LM:A"]) assert.ok(roles.includes(need), `thiếu ${need} trong ${roles.join(",")}`);
  assert.equal(roles.filter((x) => x === "SO:A").length, 1, "bước trùng vai trò phải được gộp");
});

test("K2.6: gửi lại cùng externalRef + proposalHash trả cùng phiếu, không tạo phiếu thứ hai", async () => {
  const i = input();
  const a = await create(an, i);
  const before = await prisma.ticket.count();
  const b = await create(an, i);
  assert.equal(b.code, a.code);
  assert.equal(b.created, false);
  assert.equal(await prisma.ticket.count(), before);
});

test("K2.6b: cùng externalRef nhưng nội dung đổi (hash khác) thì tạo phiếu mới", async () => {
  const i = input();
  const a = await create(an, i);
  const b = await create(an, { ...i, proposalHash: "ab".repeat(32) });
  assert.notEqual(a.code, b.code);
});

test("K2.7: nội dung có số điện thoại / email / biển số bị chặn, không tạo phiếu", async () => {
  const before = await prisma.ticket.count();
  for (const reason of ["Liên hệ khách 0912345678 để xác nhận", "Gửi cho nguyen.van@example.com", "Xe 30A-123.45 bị lỗi", "CCCD 012345678901"]) {
    const r = await createDatatrustTicket(an, input({ reason }), meta);
    assert.equal(r.ok, false, reason);
  }
  assert.equal(await prisma.ticket.count(), before);
});

test("K2.9: người không có vai trò REQ không tạo được phiếu", async () => {
  await assert.rejects(createDatatrustTicket(nam, input(), meta), (e: unknown) => e instanceof TicketError);
});

test("K2.10: ghi nhật ký tạo phiếu qua tích hợp, kèm mã băm nội dung", async () => {
  const i = input();
  const r = await create(an, i);
  const log = await prisma.auditLog.findFirst({ where: { action: "ticket.submitted.via_integration", targetId: r.id } });
  assert.ok(log);
  assert.equal((log.details as { proposalHash?: string }).proposalHash, i.proposalHash);
  assert.equal((log.details as { via?: string }).via, "datatrust");
});

test("phiếu từ DataTrust không trả lại để bổ sung được; từ chối thì phiếu REJECTED", async () => {
  const r = await create(an, input());
  const t = await reload(r.id);
  const cur = t.steps.find((s) => s.status === "CURRENT")!;
  const who = await asUser((await prisma.user.findUniqueOrThrow({ where: { id: cur.assigneeId! } })).username);
  await assert.rejects(
    returnTicket(who, { ticketId: r.id, stepId: cur.id, version: t.version, comment: "cần thêm thông tin" }, meta),
    (e: unknown) => e instanceof TicketError && /không trả lại/.test(e.message),
  );
  await decideStep(who, { ticketId: r.id, stepId: cur.id, version: t.version, approve: false, comment: "Không đồng ý" }, meta);
  assert.equal((await reload(r.id)).status, "REJECTED");
});

test("duyệt hết chuỗi thì phiếu DONE ngay, không còn bước thực hiện nào chờ", async () => {
  const r = await create(an, input());
  for (let i = 0; i < 8; i++) {
    if ((await reload(r.id)).status !== "OPEN") break;
    await approveCurrent(r.id);
  }
  const t = await reload(r.id);
  assert.equal(t.status, "DONE");
  assert.ok(t.closedAt);
});

// ---------------------------------------------------------------- Chữ ký HMAC (K2.5)

const SECRET = "x".repeat(40);
const PATH = "/api/integrations/datatrust/tickets";
const req = (over: { ts?: string; sig?: string; body?: string; method?: string } = {}) => {
  const ts = over.ts ?? String(Math.floor(Date.now() / 1000));
  const body = over.body ?? '{"a":1}';
  const method = over.method ?? "POST";
  const sig = over.sig ?? signPayload(SECRET, ts, method, PATH, body);
  return new Request(`http://localhost:3000${PATH}`, { method, body: method === "GET" ? undefined : body, headers: { "x-timestamp": ts, "x-signature": sig } });
};

test("K2.5: chữ ký đúng được chấp nhận; sai chữ ký, sai nội dung, quá hạn, thiếu bí mật đều bị từ chối", async () => {
  process.env.DATATRUST_SHARED_SECRET = SECRET;
  assert.equal((await verifyDatatrustRequest(req())).ok, true);
  const bad = await verifyDatatrustRequest(req({ sig: "0".repeat(64) }));
  assert.deepEqual([bad.ok, !bad.ok && bad.status], [false, 401]);
  // chữ ký của body này không dùng được cho body khác
  const ts = String(Math.floor(Date.now() / 1000));
  const tampered = await verifyDatatrustRequest(req({ ts, body: '{"a":2}', sig: signPayload(SECRET, ts, "POST", PATH, '{"a":1}') }));
  assert.equal(tampered.ok, false);
  // chữ ký của POST không dùng lại được cho GET
  const replayOtherMethod = await verifyDatatrustRequest(req({ ts, method: "GET", body: "", sig: signPayload(SECRET, ts, "POST", PATH, "") }));
  assert.equal(replayOtherMethod.ok, false);
  const old = String(Math.floor(Date.now() / 1000) - MAX_SKEW_SECONDS - 5);
  assert.equal((await verifyDatatrustRequest(req({ ts: old }))).ok, false);
  assert.equal((await verifyDatatrustRequest(req({ ts: "" }))).ok, false);
  delete process.env.DATATRUST_SHARED_SECRET;
  const none = await verifyDatatrustRequest(req());
  assert.deepEqual([none.ok, !none.ok && none.status], [false, 503]);
});

// ---------------------------------------------------------------- Bằng chứng (bước 6)

test("K6: bằng chứng lọc được phiếu DataTrust; CSV có mã băm đề xuất, người duyệt từng bước và việc thực thi", async () => {
  const i = input({ pii: true });
  const r = await create(an, i);
  for (let k = 0; k < 10; k++) {
    if ((await reload(r.id)).status !== "OPEN") break;
    await approveCurrent(r.id);
  }
  assert.equal((await reload(r.id)).status, "DONE");
  const aud = nam; // Auditor
  // Trước khi DataTrust báo: chưa có thông tin thực thi
  let ev = await loadEvidence(aud, { type: "dt_remediation" });
  let t = ev.tickets.find((x) => x.code === r.code)!;
  assert.ok(t, "phiếu DataTrust phải có trong bằng chứng khi lọc theo loại");
  assert.equal(t.dt?.proposalHash, i.proposalHash);
  assert.equal(t.dt?.executedAt, null);
  assert.ok(t.decisions.length >= 2 && t.decisions.every((d) => d.formHash.length === 64), "có từng quyết định kèm mã băm");
  // DataTrust báo đã thực thi (route ghi nhật ký này)
  const requester = await prisma.user.findUniqueOrThrow({ where: { username: "an.nguyen" } });
  await writeAudit({ action: AuditAction.ExternalExecuted, actorUserId: requester.id, actorEmail: requester.email, targetType: "ticket", targetId: r.id, details: { code: r.code, executedBy: "an.nguyen", proposalHash: i.proposalHash }, meta });
  ev = await loadEvidence(aud, { type: "dt_remediation" });
  t = ev.tickets.find((x) => x.code === r.code)!;
  assert.ok(t.dt?.executedAt);
  assert.equal(t.dt?.executedBy, "an.nguyen");
  const csv = evidenceCsv(ev);
  assert.ok(csv.includes(i.proposalHash) && csv.includes(i.externalRef), "CSV phải có mã băm và mã đề xuất DataTrust");
  assert.ok(csv.includes("DataTrust thực thi lúc"));
  // Lọc loại khác không lẫn phiếu DataTrust
  assert.equal((await loadEvidence(aud, { type: "rbac" })).tickets.some((x) => x.code === r.code), false);
});
