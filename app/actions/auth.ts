"use server";

import { redirect } from "next/navigation";
import { prisma } from "@/lib/db";
import { AuditAction, requestMeta, writeAudit } from "@/lib/audit";
import { burnPasswordCheck, hashPassword, verifyPassword } from "@/lib/auth/password";
import { createSession, destroySession, requireUser } from "@/lib/auth/session";
import { CooldownError, checkRegisterCode, issueRegisterCode } from "@/lib/auth/verification";
import {
  ChangePasswordSchema,
  LoginSchema,
  RegisterSchema,
  VerifySchema,
  emailDomainAllowed,
} from "@/lib/validation";

export type FormState = {
  error?: string;
  message?: string;
  fieldErrors?: Record<string, string[] | undefined>;
  values?: Record<string, string>;
};

const MAX_FAILED_LOGINS = 5;
const LOCK_MINUTES = 15;

const text = (fd: FormData, k: string) => String(fd.get(k) ?? "");
const verifyUrl = (email: string, sent = true) =>
  `/xac-nhan?email=${encodeURIComponent(email)}${sent ? "&sent=1" : ""}`;

// ---------------------------------------------------------------- Đăng nhập

export async function login(_: FormState, fd: FormData): Promise<FormState> {
  const parsed = LoginSchema.safeParse({ identifier: text(fd, "identifier"), password: text(fd, "password") });
  const values = { identifier: text(fd, "identifier") };
  if (!parsed.success) return { fieldErrors: parsed.error.flatten().fieldErrors, values };

  const { identifier, password } = parsed.data;
  const byEmail = identifier.includes("@");
  const meta = await requestMeta();
  const user = await prisma.user.findUnique({ where: byEmail ? { email: identifier } : { username: identifier } });
  const fail = (reason: string, extra: object = {}) =>
    writeAudit({
      action: AuditAction.LoginFailure,
      actorUserId: user?.id,
      actorEmail: user?.email ?? (byEmail ? identifier : null),
      details: { reason, identifier, method: byEmail ? "email" : "username", ...extra },
      meta,
    });
  const generic = "Sai email/tên đăng nhập hoặc mật khẩu.";

  if (!user) {
    await burnPasswordCheck(password);
    await fail("unknown_user");
    return { error: generic, values };
  }

  if (user.lockedUntil && user.lockedUntil > new Date()) {
    await fail("locked", { lockedUntil: user.lockedUntil.toISOString() });
    return { error: `Tài khoản tạm khoá do nhập sai nhiều lần. Thử lại sau ${fmtTime(user.lockedUntil)}.`, values };
  }

  if (!(await verifyPassword(password, user.passwordHash))) {
    const updated = await prisma.user.update({
      where: { id: user.id },
      data: { failedLoginCount: { increment: 1 } },
    });
    await fail("bad_password", { failedCount: updated.failedLoginCount });
    if (updated.failedLoginCount >= MAX_FAILED_LOGINS) {
      const lockedUntil = new Date(Date.now() + LOCK_MINUTES * 60_000);
      await prisma.user.update({ where: { id: user.id }, data: { lockedUntil, failedLoginCount: 0 } });
      await writeAudit({
        action: AuditAction.AccountLocked,
        actorUserId: user.id,
        actorEmail: user.email,
        details: { lockedUntil: lockedUntil.toISOString(), afterFailures: MAX_FAILED_LOGINS },
        meta,
      });
      return { error: `Nhập sai ${MAX_FAILED_LOGINS} lần. Tài khoản tạm khoá ${LOCK_MINUTES} phút.`, values };
    }
    return { error: generic, values };
  }

  if (user.status === "DISABLED") {
    await fail("disabled");
    return { error: "Tài khoản đã bị vô hiệu hoá. Liên hệ quản trị.", values };
  }

  if (user.status === "PENDING") {
    await fail("email_not_verified");
    let sent = true;
    try {
      await issueRegisterCode(user, meta);
    } catch (e) {
      if (!(e instanceof CooldownError)) throw e;
      sent = false; // mã vừa gửi còn dùng được
    }
    redirect(verifyUrl(user.email, sent));
  }

  await prisma.$transaction(async (tx) => {
    await tx.user.update({
      where: { id: user.id },
      data: { failedLoginCount: 0, lockedUntil: null, lastLoginAt: new Date() },
    });
    await createSession(user.id, meta, tx);
    await writeAudit(
      {
        action: AuditAction.LoginSuccess,
        actorUserId: user.id,
        actorEmail: user.email,
        details: { method: byEmail ? "email" : "username" },
        meta,
      },
      tx,
    );
  });
  redirect(user.mustChangePassword ? "/doi-mat-khau" : "/");
}

export async function logout(): Promise<void> {
  const meta = await requestMeta();
  const userId = await destroySession();
  if (userId) {
    const user = await prisma.user.findUnique({ where: { id: userId }, select: { email: true } });
    await writeAudit({ action: AuditAction.Logout, actorUserId: userId, actorEmail: user?.email, meta });
  }
  redirect("/dang-nhap");
}

// ---------------------------------------------------------------- Đăng ký

export async function register(_: FormState, fd: FormData): Promise<FormState> {
  const raw = {
    fullName: text(fd, "fullName"),
    username: text(fd, "username"),
    email: text(fd, "email"),
    password: text(fd, "password"),
    confirm: text(fd, "confirm"),
  };
  const values = { fullName: raw.fullName, username: raw.username, email: raw.email };
  const parsed = RegisterSchema.safeParse(raw);
  if (!parsed.success) return { fieldErrors: parsed.error.flatten().fieldErrors, values };
  const { fullName, username, email, password } = parsed.data;

  if (!emailDomainAllowed(email)) {
    return { fieldErrors: { email: ["Chỉ dùng email công ty để đăng ký."] }, values };
  }

  const [byEmail, byUsername] = await Promise.all([
    prisma.user.findUnique({ where: { email } }),
    prisma.user.findUnique({ where: { username } }),
  ]);
  if (byEmail && byEmail.status !== "PENDING") {
    return { fieldErrors: { email: ["Email đã được đăng ký. Hãy đăng nhập."] }, values };
  }
  if (byUsername && byUsername.id !== byEmail?.id) {
    return { fieldErrors: { username: ["Tên đăng nhập đã có người dùng."] }, values };
  }

  const meta = await requestMeta();
  const passwordHash = await hashPassword(password);
  let user;
  try {
    // Email đã đăng ký nhưng chưa xác nhận: cho đăng ký lại (ghi đè thông tin, gửi mã mới)
    user = byEmail
      ? await prisma.user.update({ where: { id: byEmail.id }, data: { fullName, username, passwordHash } })
      : await prisma.user.create({ data: { fullName, username, email, passwordHash, status: "PENDING" } });
  } catch (e) {
    if ((e as { code?: string }).code === "P2002") {
      return { error: "Email hoặc tên đăng nhập vừa được người khác dùng. Thử lại.", values };
    }
    throw e;
  }
  await writeAudit({
    action: AuditAction.Register,
    actorUserId: user.id,
    actorEmail: email,
    details: { username, reRegister: Boolean(byEmail) },
    meta,
  });

  let sent = true;
  try {
    await issueRegisterCode(user, meta);
  } catch (e) {
    if (!(e instanceof CooldownError)) throw e;
    sent = false;
  }
  redirect(verifyUrl(email, sent));
}

// ---------------------------------------------------------------- Xác nhận mã

export async function verifyEmail(_: FormState, fd: FormData): Promise<FormState> {
  const values = { email: text(fd, "email") };
  const parsed = VerifySchema.safeParse({ email: text(fd, "email"), code: text(fd, "code") });
  if (!parsed.success) return { fieldErrors: parsed.error.flatten().fieldErrors, values };
  const { email, code } = parsed.data;

  const meta = await requestMeta();
  const user = await prisma.user.findUnique({ where: { email } });
  if (!user) return { error: "Không có đăng ký nào đang chờ xác nhận với email này.", values };
  if (user.status !== "PENDING") return { error: "Email này đã được xác nhận. Hãy đăng nhập.", values };

  const result = await checkRegisterCode(user.id, code);
  if (result !== "ok") {
    await writeAudit({
      action: AuditAction.VerifyFailure,
      actorUserId: user.id,
      actorEmail: email,
      details: { reason: result },
      meta,
    });
    const msg = {
      wrong: "Mã không đúng.",
      expired: "Mã đã hết hạn. Bấm “Gửi lại mã”.",
      too_many_attempts: "Nhập sai quá nhiều lần. Bấm “Gửi lại mã” để nhận mã mới.",
    }[result];
    return { error: msg, values };
  }

  await prisma.$transaction(async (tx) => {
    const now = new Date();
    await tx.user.update({
      where: { id: user.id },
      data: { status: "ACTIVE", emailVerifiedAt: now, lastLoginAt: now, failedLoginCount: 0, lockedUntil: null },
    });
    // Mọi nhân viên đều là Người yêu cầu (KE_HOACH.md mục 1). Vai trò khác cấp qua ticket RBAC.
    await tx.userRole.create({ data: { userId: user.id, roleCode: "REQ", note: "Tự cấp khi xác nhận email" } });
    await writeAudit({ action: AuditAction.VerifySuccess, actorUserId: user.id, actorEmail: email, meta }, tx);
    await createSession(user.id, meta, tx);
    await writeAudit(
      {
        action: AuditAction.LoginSuccess,
        actorUserId: user.id,
        actorEmail: email,
        details: { method: "email_verification" },
        meta,
      },
      tx,
    );
  });
  redirect("/");
}

export async function resendCode(_: FormState, fd: FormData): Promise<FormState> {
  const email = text(fd, "email").trim().toLowerCase();
  const values = { email };
  const user = email ? await prisma.user.findUnique({ where: { email } }) : null;
  if (!user || user.status !== "PENDING") {
    return { error: "Không có đăng ký nào đang chờ xác nhận với email này.", values };
  }
  try {
    await issueRegisterCode(user, await requestMeta());
  } catch (e) {
    if (e instanceof CooldownError) return { error: e.message, values };
    throw e;
  }
  return { message: "Đã gửi mã mới. Kiểm tra hộp thư của bạn.", values };
}

// ---------------------------------------------------------------- Đổi mật khẩu

export async function changePassword(_: FormState, fd: FormData): Promise<FormState> {
  const me = await requireUser({ allowMustChangePassword: true });
  const parsed = ChangePasswordSchema.safeParse({
    current: text(fd, "current"),
    password: text(fd, "password"),
    confirm: text(fd, "confirm"),
  });
  if (!parsed.success) return { fieldErrors: parsed.error.flatten().fieldErrors };

  const user = await prisma.user.findUniqueOrThrow({ where: { id: me.id } });
  if (!(await verifyPassword(parsed.data.current, user.passwordHash))) {
    return { fieldErrors: { current: ["Mật khẩu hiện tại không đúng."] } };
  }

  const meta = await requestMeta();
  const passwordHash = await hashPassword(parsed.data.password);
  await prisma.$transaction(async (tx) => {
    await tx.user.update({ where: { id: me.id }, data: { passwordHash, mustChangePassword: false } });
    // Đăng xuất mọi phiên khác, rồi cấp phiên mới cho phiên hiện tại
    await tx.session.updateMany({ where: { userId: me.id, revokedAt: null }, data: { revokedAt: new Date() } });
    await createSession(me.id, meta, tx);
    await writeAudit({ action: AuditAction.PasswordChanged, actorUserId: me.id, actorEmail: me.email, meta }, tx);
  });
  redirect("/");
}

function fmtTime(d: Date) {
  return d.toLocaleTimeString("vi-VN", { hour: "2-digit", minute: "2-digit", timeZone: "Asia/Ho_Chi_Minh" });
}
