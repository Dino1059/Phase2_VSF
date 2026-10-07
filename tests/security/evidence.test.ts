// S1 bước 6 (BUILD_PLAN 5.1): trang kiểm toán, xuất bằng chứng — T08 trên DB sod_test.
import { after, before, test } from "node:test";
import assert from "node:assert/strict";
import { prisma } from "@/lib/db";
import type { CurrentUser } from "@/lib/auth/session";
import { TicketError } from "@/lib/tickets/service";
import { csvCell, evidenceCsv, exportEvidenceCsv, loadEvidence, logEvidence, parseEvidenceFilter } from "@/lib/tickets/evidence";
import { approveCurrent, asUser, assigneeOf, current, form, meta, newTicket } from "./helpers";

async function denied(p: Promise<unknown>, msg: RegExp) {
  await assert.rejects(p, (e: unknown) => e instanceof TicketError && msg.test(e.message), `phải bị chặn: ${msg}`);
}

let an: CurrentUser, aud: CurrentUser, admin: CurrentUser, ciso: CurrentUser;
before(async () => {
  [an, aud, admin, ciso] = await Promise.all(["an.nguyen", "nam.dang", "admin", "giang.hoang"].map(asUser));
});
after(() => prisma.$disconnect());

const exportLogs = (actorId: string) => prisma.auditLog.findMany({ where: { action: "evidence.exported", actorUserId: actorId }, orderBy: { id: "asc" } });

test("T08: Auditor xuất bằng chứng một kỳ → có người duyệt, thời điểm, mã băm; có dòng nhật ký cho lần xuất", async () => {
  const t = await newTicket(an, form({ mucDich: "Bằng chứng kỳ thử" }));
  const who = await approveCurrent(t.id, "Đã xác minh phạm vi");
  const day = new Date().toLocaleDateString("sv-SE", { timeZone: "Asia/Ho_Chi_Minh" });
  const filter = parseEvidenceFilter({ from: day, to: day });

  const before = (await exportLogs(aud.id)).length;
  const out = await exportEvidenceCsv(aud, filter, meta);
  assert.match(out.filename, /^bang-chung_\d{8}\.csv$/);
  assert.ok(out.body.startsWith("\uFEFF"), "CSV UTF-8 có BOM");
  const lines = out.body.trim().split("\r\n");
  const mine = lines.filter((l) => l.includes(`"${t.code}"`));
  assert.equal(mine.length, 2, "một dòng gửi phiếu và một dòng duyệt");
  const approval = mine.find((l) => l.includes("Đồng ý"))!;
  assert.ok(approval.includes(`"${who.fullName}"`), "có tên người duyệt");
  assert.ok(approval.includes("Đã xác minh phạm vi"), "có ghi chú");
  assert.match(approval, /"\d{4}-\d\d-\d\d \d\d:\d\d:\d\d"/, "có thời điểm");
  assert.ok(approval.includes(`"${t.formHash}"`), "có mã băm nội dung đã duyệt");

  const logs = await exportLogs(aud.id);
  assert.equal(logs.length, before + 1, "mỗi lần xuất có một dòng nhật ký");
  const d = logs.at(-1)!.details as { format: string; tickets: number; rows: number };
  assert.equal(d.format, "csv");
  assert.equal(d.tickets, out.tickets);
  assert.equal(d.rows, out.rows);
  // Nhật ký vẫn nguyên vẹn
  assert.equal((await prisma.$queryRaw<unknown[]>`SELECT * FROM audit_log_verify()`).length, 0);
});

test("T08: bộ lọc theo kỳ, trạng thái và loại phiếu", async () => {
  const t = await newTicket(an);
  const past = await loadEvidence(aud, parseEvidenceFilter({ from: "2000-01-01", to: "2000-01-31" }));
  assert.equal(past.tickets.length, 0, "kỳ trong quá khứ không có phiếu");
  const day = new Date().toLocaleDateString("sv-SE", { timeZone: "Asia/Ho_Chi_Minh" });
  const open = await loadEvidence(aud, parseEvidenceFilter({ from: day, to: day, status: "OPEN" }));
  assert.ok(open.tickets.some((x) => x.code === t.code));
  const done = await loadEvidence(aud, parseEvidenceFilter({ from: day, to: day, status: "DONE", type: "rbac" }));
  assert.ok(!done.tickets.some((x) => x.code === t.code), "lọc theo trạng thái và loại làm phiếu này biến mất");
  // Giá trị lọc sai bị bỏ qua thay vì làm lỗi
  assert.deepEqual(parseEvidenceFilter({ from: "hôm qua", status: "XOA", type: "x" }), {});
});

test("T08: chỉ Auditor xem và xuất được; người khác bị từ chối và không có dòng nhật ký xuất", async () => {
  for (const u of [an, admin, ciso]) {
    await denied(loadEvidence(u, {}), /Chỉ Auditor/);
    await denied(exportEvidenceCsv(u, {}, meta), /Chỉ Auditor/);
    assert.equal((await exportLogs(u.id)).length, 0);
  }
});

test("T08: nhật ký ghi cả lần xem lẫn lần in PDF; quyết định thay mặt và phiếu bị trả lại đều có trong bằng chứng", async () => {
  const t = await newTicket(an);
  const step = current(t);
  const assignee = await assigneeOf(step);
  const { returnTicket } = await import("@/lib/tickets/service");
  await returnTicket(assignee, { ticketId: t.id, stepId: step.id, version: t.version, comment: "Thiếu tài nguyên" }, meta);
  const ev = await loadEvidence(aud, {});
  const row = ev.tickets.find((x) => x.code === t.code)!;
  assert.ok(row.decisions.some((d) => d.outcome === "RETURN" && d.comment === "Thiếu tài nguyên"));

  await logEvidence(aud, "viewed", {}, ev, meta);
  await logEvidence(aud, "pdf", {}, ev, meta);
  const fmt = async (action: string) => prisma.auditLog.findFirst({ where: { action, actorUserId: aud.id }, orderBy: { id: "desc" } });
  assert.ok(await fmt("evidence.viewed"));
  assert.equal(((await fmt("evidence.exported"))!.details as { format: string }).format, "pdf");
});

test("T08: CSV chống chèn công thức (=, +, -, @) và thoát dấu nháy kép", () => {
  assert.equal(csvCell("=HYPERLINK(\"x\")"), `"'=HYPERLINK(""x"")"`);
  assert.equal(csvCell("+1+1"), `"'+1+1"`);
  assert.equal(csvCell("-2"), `"'-2"`);
  assert.equal(csvCell("@SUM(A1)"), `"'@SUM(A1)"`);
  assert.equal(csvCell("bình thường"), `"bình thường"`);
  assert.equal(csvCell(null), `""`);
  assert.equal(csvCell(5), `"5"`);
  assert.ok(evidenceCsv({ tickets: [], rows: 0, truncated: false }).includes("Mã phiếu"), "luôn có dòng tiêu đề");
});
