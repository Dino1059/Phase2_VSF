import "server-only";
import { prisma, type Tx } from "@/lib/db";
import { ConfigSchema, DEFAULT_CONFIG, type ConfigData } from "./schema";

export type ConfigVersionRef = { id: string; seq: number; config: ConfigData };

/** Phiên bản cấu hình đang hiệu lực (luôn có đúng một). Nội dung được kiểm lại bằng schema trước khi dùng. */
export async function activeConfig(tx: Tx | typeof prisma = prisma): Promise<ConfigVersionRef> {
  const row = await tx.configVersion.findFirstOrThrow({ where: { status: "ACTIVE" }, select: { id: true, seq: true, config: true } });
  return { id: row.id, seq: row.seq, config: ConfigSchema.parse(row.config) };
}

/** Phiên bản cấu hình của một ticket (cố định lúc tạo) */
export async function configById(tx: Tx | typeof prisma, id: string): Promise<ConfigVersionRef> {
  const row = await tx.configVersion.findUniqueOrThrow({ where: { id }, select: { id: true, seq: true, config: true } });
  return { id: row.id, seq: row.seq, config: ConfigSchema.parse(row.config) };
}

/** Dùng cho chỗ không được làm hỏng luồng chính nếu nội dung cấu hình lỗi: rơi về mặc định */
export const parseConfigOrDefault = (raw: unknown): ConfigData => {
  const r = ConfigSchema.safeParse(raw);
  return r.success ? r.data : DEFAULT_CONFIG;
};

export async function listConfigVersions(limit = 30) {
  const rows = await prisma.configVersion.findMany({
    orderBy: { seq: "desc" },
    take: limit,
    include: { proposer: { select: { fullName: true } }, decider: { select: { fullName: true } } },
  });
  return rows.map((r) => ({ ...r, config: ConfigSchema.parse(r.config) }));
}
export type ConfigVersionRow = Awaited<ReturnType<typeof listConfigVersions>>[number];
