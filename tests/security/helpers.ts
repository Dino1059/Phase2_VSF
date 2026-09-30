// Dữ liệu dựng sẵn cho test bảo mật (chạy trên DB sod_test).
import assert from "node:assert/strict";
import { prisma } from "@/lib/db";
import type { CurrentUser } from "@/lib/auth/session";
import { submitTicket } from "@/lib/tickets/service";
import { emptyForm, type TicketForm } from "@/lib/sod/form";

export const meta = { ip: "127.0.0.1", userAgent: "security-test" };

/** Dựng CurrentUser như phiên đăng nhập của `username` */
export async function asUser(username: string): Promise<CurrentUser> {
  const u = await prisma.user.findUniqueOrThrow({ where: { username }, include: { roles: { include: { role: true } } } });
  return {
    id: u.id,
    username: u.username,
    email: u.email,
    fullName: u.fullName,
    mustChangePassword: false,
    lastLoginAt: null,
    roles: u.roles.map((r) => ({ code: r.roleCode, name: r.role.name })),
  };
}

/** Người được giao một bước, dưới dạng CurrentUser */
export async function assigneeOf(step: { assigneeId: string | null }) {
  return asUser((await prisma.user.findUniqueOrThrow({ where: { id: step.assigneeId! } })).username);
}

export const form = (over: Partial<TicketForm> = {}): TicketForm => ({
  ...emptyForm("Nguyễn An", "an.nguyen@sod.local"),
  loaiPhieu: "new", khan: "normal", maNV: "NV001", phongBan: "Vận hành", chucDanh: "Chuyên viên", capBac: "T3",
  viTri: "Vận hành hệ thống", thiTruong: "vn", mucDich: "Dự án kiểm thử", dlcn: "none", camKet: true, kyTen: "Nguyễn An",
  rows: [{ heThong: "CRM", taiNguyen: "Báo cáo", tang: "1", mucQuyen: "RO", thoiHan: "2026-12-31" }],
  ...over,
});

export const reload = (id: string) =>
  prisma.ticket.findUniqueOrThrow({ where: { id }, include: { steps: { orderBy: { idx: "asc" } } } });

export async function newTicket(requester: CurrentUser, f = form()) {
  const r = await submitTicket(requester, f, meta);
  assert.ok(r.ok, JSON.stringify(r));
  return reload(r.id);
}

export const current = (t: Awaited<ReturnType<typeof reload>>) => t.steps.find((s) => s.status === "CURRENT")!;
