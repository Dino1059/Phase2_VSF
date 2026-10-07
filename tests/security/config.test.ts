// S1 bước 4 (BUILD_PLAN 5.1): cấu hình có phiên bản, đề xuất ≠ duyệt — T04 và các kiểm tra liên quan, trên DB sod_test.
import { after, before, test } from "node:test";
import assert from "node:assert/strict";
import { prisma } from "@/lib/db";
import type { CurrentUser } from "@/lib/auth/session";
import { TicketError } from "@/lib/tickets/service";
import { decideConfig, proposeConfig, withdrawConfig } from "@/lib/config/service";
import { activeConfig } from "@/lib/config/queries";
import { DEFAULT_CONFIG, type ConfigData } from "@/lib/config/schema";
import { ROLE_KEYS } from "@/lib/sod/catalog";
import { asUser, meta, newTicket, ownerDb, reload } from "./helpers";

async function denied(p: Promise<unknown>, msg: RegExp) {
  await assert.rejects(p, (e: unknown) => e instanceof TicketError && msg.test(e.message), `phải bị chặn: ${msg}`);
}

let admin: CurrentUser, ciso: CurrentUser, an: CurrentUser, dual: CurrentUser;
before(async () => {
  const owner = ownerDb();
  if (!(await owner.user.findUnique({ where: { username: "dual.role" } }))) {
    const u = await owner.user.create({ data: { username: "dual.role", email: "dual.role@sod.local", fullName: "Vừa Admin Vừa CISO", passwordHash: "x", status: "ACTIVE" } });
    await owner.userRole.createMany({ data: ["ADMIN", "CISO"].map((roleCode) => ({ userId: u.id, roleCode, note: "test" })) });
  }
  await owner.$disconnect();
  [admin, ciso, an, dual] = await Promise.all(["admin", "giang.hoang", "an.nguyen", "dual.role"].map(asUser));
});

const clone = (c: ConfigData): ConfigData => JSON.parse(JSON.stringify(c));
const change = (c: ConfigData, f: (c: ConfigData) => void) => {
  const x = clone(c);
  f(x);
  return x;
};
const REASON = "Điều chỉnh theo yêu cầu";
const propose = (user: CurrentUser, c: ConfigData) => proposeConfig(user, c, REASON, meta);
const activeCount = () => prisma.configVersion.count({ where: { status: "ACTIVE" } });
const SO = ROLE_KEYS.indexOf("SO");

// Trả cấu hình về mặc định sau khi test xong, để các file test khác không bị ảnh hưởng
after(async () => {
  const cur = await activeConfig();
  if (JSON.stringify(cur.config) !== JSON.stringify(DEFAULT_CONFIG)) {
    const p = await propose(admin, DEFAULT_CONFIG);
    await decideConfig(ciso, p.id, true, "", meta);
  }
  // Dọn dấu vết để test của file khác không bị nhiễu: người dùng vừa Admin vừa CISO, thông báo cấu hình
  const owner = ownerDb();
  await owner.user.update({ where: { username: "dual.role" }, data: { status: "DISABLED" } });
  await owner.notification.deleteMany({ where: { kind: "CONFIG" } });
  await owner.$disconnect();
  await prisma.$disconnect();
});

test("T04: Admin tự đề xuất rồi tự duyệt → bị chặn; Admin không phải CISO nên không duyệt được", async () => {
  const base = (await activeConfig()).config;
  const p = await propose(admin, change(base, (c) => void (c.sla.R = 30)));
  await denied(decideConfig(admin, p.id, true, "", meta), /Chỉ CISO/);
  const row = await prisma.configVersion.findUniqueOrThrow({ where: { id: p.id } });
  assert.equal(row.status, "PROPOSED");
  await withdrawConfig(admin, p.id, meta);
});

test("T04: người vừa là Admin vừa là CISO tự duyệt đề xuất của mình → bị chặn ở service và ở DB", async () => {
  const base = (await activeConfig()).config;
  const p = await propose(dual, change(base, (c) => void (c.sla.R = 31)));
  await denied(decideConfig(dual, p.id, true, "", meta), /không được tự duyệt/);
  // Ghi thẳng vào DB bằng tài khoản ứng dụng cũng bị trigger chặn
  await assert.rejects(prisma.configVersion.update({ where: { id: p.id }, data: { status: "ACTIVE", decidedById: dual.id } }), /không được tự duyệt/);
  assert.equal(await activeCount(), 1);
  await withdrawConfig(dual, p.id, meta);
});

test("T04: người không phải Admin không đề xuất được; DB cũng chặn", async () => {
  const base = (await activeConfig()).config;
  await denied(propose(ciso, change(base, (c) => void (c.sla.R = 40))), /Chỉ Quản trị SoD/);
  await denied(propose(an, change(base, (c) => void (c.sla.R = 40))), /Chỉ Quản trị SoD/);
  await assert.rejects(
    prisma.configVersion.create({ data: { config: change(base, (c) => void (c.sla.R = 40)), reason: "x", baseSeq: 1, proposedById: ciso.id } }),
    /chỉ Quản trị SoD/,
  );
  // Tạo thẳng ở trạng thái đang hiệu lực
  await assert.rejects(
    prisma.configVersion.create({ data: { config: base, reason: "x", status: "ACTIVE", baseSeq: 1, proposedById: admin.id } }),
    /trạng thái đề xuất/,
  );
});

test("T04: cấu hình không hợp lệ hoặc không đổi gì → bị chặn", async () => {
  const base = (await activeConfig()).config;
  await denied(propose(admin, base), /không có thay đổi/);
  await denied(propose(admin, change(base, (c) => void (c.sla.P = 0))), /không hợp lệ/);
  await denied(propose(admin, change(base, (c) => void (c.remindPct = 150))), /không hợp lệ/);
  await denied(propose(admin, change(base, (c) => void (c.priority.urgent = 5))), /Hệ số ưu tiên/);
  await denied(propose(admin, change(base, (c) => void (c.matrix[1] = "AXXXXXXXXX"))), /Requestor không được/);
  await denied(propose(admin, change(base, (c) => void (c.matrix[2] = "XAA"))), /không hợp lệ/);
  await denied(proposeConfig(admin, change(base, (c) => void (c.sla.R = 30)), "  ", meta), /Nhập lý do/);
});

test("T04: CISO duyệt thì có hiệu lực cho phiếu tạo sau; phiếu đang chạy giữ cấu hình cũ", async () => {
  const before = await activeConfig();
  const oldTicket = await newTicket(an);
  const p = await propose(admin, change(before.config, (c) => {
    c.sla.R = 12;
    c.matrix[1] = c.matrix[1].slice(0, SO) + "C" + c.matrix[1].slice(SO + 1); // System Owner chỉ còn được tham vấn ở "Xác nhận nhu cầu"
  }));
  // Chưa duyệt: chưa có hiệu lực
  assert.equal((await activeConfig()).seq, before.seq);
  await denied(decideConfig(ciso, p.id, false, " ", meta), /Nhập lý do từ chối/);
  await decideConfig(ciso, p.id, true, "Đồng ý", meta);

  const after = await activeConfig();
  assert.equal(after.seq, p.seq);
  assert.equal(after.config.sla.R, 12);
  assert.equal(await activeCount(), 1);
  assert.equal((await prisma.configVersion.findUniqueOrThrow({ where: { id: before.id } })).status, "SUPERSEDED");

  const newTicketRow = await newTicket(an);
  assert.equal(newTicketRow.configVersionId, after.id);
  assert.ok(!newTicketRow.steps.some((s) => s.roleCode === "SO" && s.action === "R"), "ma trận mới: SO không còn rà soát");
  const rStep = newTicketRow.steps.find((s) => s.action === "R")!;
  assert.equal(rStep.slaHours, 12);

  const stillOld = await reload(oldTicket.id);
  assert.equal(stillOld.configVersionId, before.id, "phiếu cũ giữ phiên bản cấu hình lúc tạo");
  assert.ok(stillOld.steps.some((s) => s.roleCode === "SO" && s.action === "R"));
  assert.equal(stillOld.steps.find((s) => s.action === "R")!.slaHours, 24);

  // Phiên bản cấu hình của phiếu không đổi được, kể cả ghi thẳng DB
  await assert.rejects(prisma.$executeRaw`UPDATE tickets SET config_version_id = ${after.id}::uuid WHERE id = ${oldTicket.id}::uuid`, /không được đổi/);
});

test("T04: đề xuất đã cũ (có phiên bản khác lên thay) không duyệt được; rút đề xuất chỉ người đề xuất", async () => {
  const base = (await activeConfig()).config;
  const a = await propose(admin, change(base, (c) => void (c.sla.A = 20)));
  const b = await propose(admin, change(base, (c) => void (c.sla.A = 22)));
  await decideConfig(ciso, a.id, true, "", meta);
  await denied(decideConfig(ciso, b.id, true, "", meta), /đã có hiệu lực/);
  await denied(withdrawConfig(ciso, b.id, meta), /Không tìm thấy đề xuất/);
  await withdrawConfig(admin, b.id, meta);
  assert.equal((await prisma.configVersion.findUniqueOrThrow({ where: { id: b.id } })).status, "CANCELLED");
});

test("T04: từ chối giữ nguyên cấu hình; nội dung đã đề xuất không sửa được", async () => {
  const cur = await activeConfig();
  const p = await propose(admin, change(cur.config, (c) => void (c.escalatePct = 120)));
  await assert.rejects(prisma.configVersion.update({ where: { id: p.id }, data: { config: change(cur.config, (c) => void (c.escalatePct = 300)) } }), /không được sửa/);
  await decideConfig(ciso, p.id, false, "Chưa cần", meta);
  const row = await prisma.configVersion.findUniqueOrThrow({ where: { id: p.id } });
  assert.equal(row.status, "REJECTED");
  assert.equal(row.decidedById, ciso.id);
  assert.equal((await activeConfig()).seq, cur.seq);
  // Đã quyết định rồi thì không đổi lại được
  await assert.rejects(prisma.configVersion.update({ where: { id: p.id }, data: { status: "ACTIVE", decidedById: ciso.id } }), /không chuyển được/);
  // Không tự thay thế phiên bản đang hiệu lực mà không có phiên bản khác được duyệt
  await assert.rejects(prisma.configVersion.update({ where: { id: cur.id }, data: { status: "SUPERSEDED" } }), /không chuyển được/);
});
