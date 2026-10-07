import "server-only";
import { prisma, type Tx } from "@/lib/db";

/** Ủy quyền còn hiệu lực mà `userId` là người nhận: được xử lý bước của `delegatorId` với vai trò `roleCode`. */
export type ActingFor = { delegatorId: string; roleCode: string };

export async function activeDelegationsTo(tx: Tx | typeof prisma, userId: string): Promise<ActingFor[]> {
  const now = new Date();
  const rows = await tx.delegation.findMany({
    where: { delegateId: userId, revokedAt: null, validFrom: { lte: now }, validTo: { gt: now } },
    select: { delegatorId: true, roleCode: true },
  });
  return rows;
}

/** Trang Ủy quyền: ủy quyền tôi đã giao, ủy quyền tôi nhận, và người có thể nhận theo từng vai trò của tôi. */
export async function delegationOverview(userId: string, roleCodes: string[]) {
  const now = new Date();
  const include = {
    delegator: { select: { fullName: true } },
    delegate: { select: { fullName: true } },
    role: { select: { name: true } },
  } as const;
  const [given, received, candidates] = await Promise.all([
    prisma.delegation.findMany({ where: { delegatorId: userId }, orderBy: { createdAt: "desc" }, take: 50, include }),
    prisma.delegation.findMany({ where: { delegateId: userId }, orderBy: { createdAt: "desc" }, take: 50, include }),
    prisma.user.findMany({
      where: {
        id: { not: userId },
        status: "ACTIVE",
        roles: { some: { roleCode: { in: roleCodes }, validFrom: { lte: now }, OR: [{ validTo: null }, { validTo: { gt: now } }] } },
      },
      orderBy: { fullName: "asc" },
      select: {
        id: true,
        fullName: true,
        roles: { where: { roleCode: { in: roleCodes }, validFrom: { lte: now }, OR: [{ validTo: null }, { validTo: { gt: now } }] }, select: { roleCode: true } },
      },
    }),
  ]);
  const byRole: Record<string, { id: string; fullName: string }[]> = {};
  for (const u of candidates) for (const r of u.roles) (byRole[r.roleCode] ??= []).push({ id: u.id, fullName: u.fullName });
  const live = (d: { revokedAt: Date | null; validFrom: Date; validTo: Date }) => !d.revokedAt && d.validFrom <= now && d.validTo > now;
  return { given, received, byRole, live };
}
export type DelegationOverview = Awaited<ReturnType<typeof delegationOverview>>;
