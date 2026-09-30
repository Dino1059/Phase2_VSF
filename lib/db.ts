import "server-only";
import { PrismaPg } from "@prisma/adapter-pg";
import { Prisma, PrismaClient } from "@/app/generated/prisma/client";

// Ứng dụng kết nối bằng sod_app: không có quyền UPDATE/DELETE trên audit_log.
const url = process.env.APP_DATABASE_URL;
if (!url) throw new Error("Thiếu APP_DATABASE_URL trong .env");

// timezone=UTC: driver gửi giờ dạng UTC không kèm múi giờ; nếu phiên dùng múi giờ máy chủ (Asia/Ho_Chi_Minh)
// thì Postgres hiểu sai, giờ do ứng dụng ghi lệch 7 tiếng so với now() trong trigger.
const PG_OPTIONS = "-c timezone=UTC";

// Chế độ dev giữ một kết nối qua các lần nạp lại code. Khi client Prisma được sinh lại (đổi schema)
// hoặc đổi tuỳ chọn kết nối thì bỏ kết nối cũ, tránh lỗi "prisma.<bảng mới> is undefined".
const KEY = `${PG_OPTIONS}|${Object.keys(Prisma.ModelName).join(",")}`;
const cache = globalThis as unknown as { prisma?: PrismaClient; prismaKey?: string };
const stale = cache.prisma && (!(cache.prisma instanceof PrismaClient) || cache.prismaKey !== KEY);
if (stale) void cache.prisma!.$disconnect();

export const prisma: PrismaClient =
  (!stale && cache.prisma) || new PrismaClient({ adapter: new PrismaPg({ connectionString: url, options: PG_OPTIONS }) });

if (process.env.NODE_ENV !== "production") Object.assign(cache, { prisma, prismaKey: KEY });

export type Tx = Parameters<Parameters<typeof prisma.$transaction>[0]>[0];
