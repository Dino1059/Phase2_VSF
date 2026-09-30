import "server-only";
import { headers } from "next/headers";
import { prisma, type Tx } from "@/lib/db";
import type { Prisma } from "@/app/generated/prisma/client";

// Tên hành động dùng trong nhật ký. Thêm mới ở đây để cả hệ thống dùng chung.
export const AuditAction = {
  LoginSuccess: "auth.login.success",
  LoginFailure: "auth.login.failure",
  Logout: "auth.logout",
  AccountLocked: "auth.account.locked",
  Register: "auth.register",
  CodeSent: "auth.code.sent",
  VerifySuccess: "auth.verify.success",
  VerifyFailure: "auth.verify.failure",
  PasswordChanged: "auth.password.changed",
  AuditViewed: "audit.viewed",
  TicketSubmitted: "ticket.submitted",
  StepApproved: "ticket.step.approved",
  StepCompleted: "ticket.step.completed",
  StepRejected: "ticket.step.rejected",
  TicketDone: "ticket.done",
  DecisionDenied: "ticket.decision.denied",
} as const;
export type AuditAction = (typeof AuditAction)[keyof typeof AuditAction];

export type RequestMeta = { ip: string | null; userAgent: string | null };

export async function requestMeta(): Promise<RequestMeta> {
  const h = await headers();
  const ip = h.get("x-forwarded-for")?.split(",")[0]?.trim() || h.get("x-real-ip") || null;
  return { ip: ip?.slice(0, 64) ?? null, userAgent: h.get("user-agent")?.slice(0, 512) ?? null };
}

type Entry = {
  action: AuditAction;
  actorUserId?: string | null;
  actorEmail?: string | null;
  targetType?: string;
  targetId?: string;
  details?: Prisma.InputJsonValue;
  meta: RequestMeta;
};

// id, thời điểm và mã băm do trigger trong DB gán — ứng dụng không tự đặt được.
export async function writeAudit(entry: Entry, tx: Tx = prisma): Promise<void> {
  await tx.auditLog.create({
    data: {
      action: entry.action,
      actorUserId: entry.actorUserId ?? null,
      actorEmail: entry.actorEmail ?? null,
      targetType: entry.targetType,
      targetId: entry.targetId,
      details: entry.details,
      ip: entry.meta.ip,
      userAgent: entry.meta.userAgent,
    },
  });
}
