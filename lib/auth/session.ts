import "server-only";
import { cache } from "react";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { createHash, randomBytes } from "node:crypto";
import { prisma, type Tx } from "@/lib/db";
import type { RequestMeta } from "@/lib/audit";

const COOKIE = "sod_session";
const SESSION_HOURS = 12;

const sha256 = (s: string) => createHash("sha256").update(s).digest("hex");

export async function createSession(userId: string, meta: RequestMeta, tx: Tx = prisma): Promise<void> {
  const token = randomBytes(32).toString("base64url");
  const expiresAt = new Date(Date.now() + SESSION_HOURS * 3600_000);
  await tx.session.create({
    data: { userId, tokenHash: sha256(token), expiresAt, ip: meta.ip, userAgent: meta.userAgent },
  });
  (await cookies()).set(COOKIE, token, {
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
    path: "/",
    expires: expiresAt,
  });
}

/** Thu hồi phiên hiện tại, trả về userId nếu có. */
export async function destroySession(): Promise<string | null> {
  const store = await cookies();
  const token = store.get(COOKIE)?.value;
  store.delete(COOKIE);
  if (!token) return null;
  const session = await prisma.session.findUnique({ where: { tokenHash: sha256(token) } });
  if (!session || session.revokedAt) return null;
  await prisma.session.update({ where: { id: session.id }, data: { revokedAt: new Date() } });
  return session.userId;
}

export type CurrentUser = {
  id: string;
  username: string;
  email: string;
  fullName: string;
  mustChangePassword: boolean;
  lastLoginAt: Date | null;
  roles: { code: string; name: string }[];
};

/** Người dùng của request hiện tại (vai trò còn hiệu lực), hoặc null. */
export const getCurrentUser = cache(async (): Promise<CurrentUser | null> => {
  const token = (await cookies()).get(COOKIE)?.value;
  if (!token) return null;
  const now = new Date();
  const session = await prisma.session.findUnique({
    where: { tokenHash: sha256(token) },
    include: {
      user: {
        include: {
          roles: {
            where: { validFrom: { lte: now }, OR: [{ validTo: null }, { validTo: { gt: now } }] },
            include: { role: true },
          },
        },
      },
    },
  });
  if (!session || session.revokedAt || session.expiresAt <= now || session.user.status !== "ACTIVE") return null;
  const u = session.user;
  return {
    id: u.id,
    username: u.username,
    email: u.email,
    fullName: u.fullName,
    mustChangePassword: u.mustChangePassword,
    lastLoginAt: u.lastLoginAt,
    roles: u.roles.map((r) => ({ code: r.roleCode, name: r.role.name })),
  };
});

/** Bắt buộc đăng nhập; người dùng phải đổi mật khẩu tạm trước khi dùng các trang khác. */
export async function requireUser(opts: { allowMustChangePassword?: boolean } = {}): Promise<CurrentUser> {
  const user = await getCurrentUser();
  if (!user) redirect("/dang-nhap");
  if (user.mustChangePassword && !opts.allowMustChangePassword) redirect("/doi-mat-khau");
  return user;
}
