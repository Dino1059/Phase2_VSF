import "server-only";
import { createHash, randomInt, timingSafeEqual } from "node:crypto";
import { prisma } from "@/lib/db";
import { sendMail } from "@/lib/mail";
import { AuditAction, writeAudit, type RequestMeta } from "@/lib/audit";

const CODE_TTL_MINUTES = 10;
const CODE_MAX_ATTEMPTS = 5;
const RESEND_COOLDOWN_SECONDS = 60;

const hashCode = (userId: string, code: string) => createHash("sha256").update(`${userId}:${code}`).digest("hex");

export class CooldownError extends Error {
  constructor(public secondsLeft: number) {
    super(`Vui lòng chờ ${secondsLeft} giây rồi gửi lại mã.`);
  }
}

/** Tạo mã 6 số mới (vô hiệu mã cũ) và gửi tới email người dùng. */
export async function issueRegisterCode(user: { id: string; email: string; fullName: string }, meta: RequestMeta) {
  const last = await prisma.verificationCode.findFirst({
    where: { userId: user.id, purpose: "REGISTER" },
    orderBy: { createdAt: "desc" },
  });
  if (last) {
    const elapsed = (Date.now() - last.createdAt.getTime()) / 1000;
    if (elapsed < RESEND_COOLDOWN_SECONDS) throw new CooldownError(Math.ceil(RESEND_COOLDOWN_SECONDS - elapsed));
  }

  const code = randomInt(0, 1_000_000).toString().padStart(6, "0");
  const now = new Date();
  await prisma.$transaction(async (tx) => {
    await tx.verificationCode.updateMany({
      where: { userId: user.id, purpose: "REGISTER", consumedAt: null, expiresAt: { gt: now } },
      data: { expiresAt: now },
    });
    await tx.verificationCode.create({
      data: {
        userId: user.id,
        purpose: "REGISTER",
        codeHash: hashCode(user.id, code),
        expiresAt: new Date(now.getTime() + CODE_TTL_MINUTES * 60_000),
      },
    });
    await writeAudit(
      { action: AuditAction.CodeSent, actorUserId: user.id, actorEmail: user.email, details: { purpose: "REGISTER" }, meta },
      tx,
    );
  });

  await sendMail(
    user.email,
    `Mã xác nhận SoD Flow: ${code}`,
    `Chào ${user.fullName},\n\nMã xác nhận đăng ký tài khoản SoD Flow của bạn là: ${code}\n` +
      `Mã có hiệu lực trong ${CODE_TTL_MINUTES} phút. Không chia sẻ mã này với bất kỳ ai.\n\n` +
      `Nếu bạn không đăng ký, hãy bỏ qua email này.`,
  );
}

type CheckResult = "ok" | "wrong" | "expired" | "too_many_attempts";

/** Kiểm tra mã đăng ký. Đúng thì đánh dấu đã dùng. */
export async function checkRegisterCode(userId: string, code: string): Promise<CheckResult> {
  const now = new Date();
  const current = await prisma.verificationCode.findFirst({
    where: { userId, purpose: "REGISTER", consumedAt: null },
    orderBy: { createdAt: "desc" },
  });
  if (!current || current.expiresAt <= now) return "expired";

  // Tính lượt thử trước khi so sánh, có điều kiện trong DB để request song song không vượt giới hạn
  const { count: allowed } = await prisma.verificationCode.updateMany({
    where: { id: current.id, attempts: { lt: CODE_MAX_ATTEMPTS } },
    data: { attempts: { increment: 1 } },
  });
  if (allowed === 0) return "too_many_attempts";

  const a = Buffer.from(hashCode(userId, code));
  const b = Buffer.from(current.codeHash);
  if (a.length === b.length && timingSafeEqual(a, b)) {
    // Điều kiện consumedAt: null chặn việc dùng cùng một mã hai lần song song
    const { count } = await prisma.verificationCode.updateMany({
      where: { id: current.id, consumedAt: null },
      data: { consumedAt: now },
    });
    return count === 1 ? "ok" : "expired";
  }
  return current.attempts + 1 >= CODE_MAX_ATTEMPTS ? "too_many_attempts" : "wrong";
}
