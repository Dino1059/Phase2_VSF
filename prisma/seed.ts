// Dữ liệu tạm: vai trò theo rule.md mục 1 và danh bạ mẫu trong ../data.js (DEFAULT_PEOPLE).
// Chạy lại nhiều lần được (upsert). Mật khẩu tạm lấy từ SEED_PASSWORD, bắt buộc đổi khi đăng nhập lần đầu.
import "dotenv/config";
import { PrismaPg } from "@prisma/adapter-pg";
import { PrismaClient } from "../app/generated/prisma/client";
import { hashPassword } from "../lib/auth/password";

const prisma = new PrismaClient({ adapter: new PrismaPg({ connectionString: process.env.DATABASE_URL!, options: "-c timezone=UTC" }) });

const ROLES = [
  { code: "REQ", name: "Requestor", shortName: "Req.", description: "Khởi tạo yêu cầu, mô tả mục đích và phạm vi truy cập" },
  { code: "LM", name: "Line Manager", shortName: "Line Mgr", description: "Xác nhận nhu cầu nghiệp vụ và phạm vi công việc" },
  { code: "DPO", name: "DPO/Compliance", shortName: "DPO", description: "Đánh giá căn cứ xử lý, PII, chuyển dữ liệu xuyên biên giới" },
  { code: "SO", name: "System Owner", shortName: "Sys Owner", description: "Chịu trách nhiệm nghiệp vụ và phê duyệt quyền trong hệ thống" },
  { code: "CISO", name: "CISO/Security", shortName: "CISO", description: "Đánh giá rủi ro kỹ thuật, quyền đặc quyền và ngoại lệ" },
  { code: "IAM", name: "IAM Administrator", shortName: "IAM", description: "Cấu hình role, group, policy và thực hiện provisioning" },
  { code: "DEV", name: "Developer", shortName: "Dev", description: "Phát triển và kiểm thử mã nguồn" },
  { code: "REL", name: "Release Manager", shortName: "Rel. Mgr", description: "Kiểm tra bằng chứng và phê duyệt phát hành" },
  { code: "OPS", name: "Production Operator", shortName: "Prod. Op.", description: "Triển khai hoặc vận hành thay đổi đã được phê duyệt" },
  { code: "AUD", name: "Auditor", shortName: "Auditor", description: "Kiểm tra độc lập và xác nhận bằng chứng" },
  { code: "ADMIN", name: "Quản trị SoD", shortName: "Admin", description: "Quản lý cấu hình và giám sát; không nằm trong chuỗi duyệt" },
];

// Giống DEFAULT_PEOPLE trong ../data.js
const PEOPLE: { name: string; roles: string[] }[] = [
  { name: "Nguyễn An", roles: ["REQ"] },
  { name: "Mai Oanh", roles: ["REQ", "LM"] },
  { name: "Trần Bình", roles: ["LM"] },
  { name: "Lê Chi", roles: ["DPO"] },
  { name: "Phạm Dũng", roles: ["SO"] },
  { name: "Hồ Sơn", roles: ["SO"] },
  { name: "Hoàng Giang", roles: ["CISO"] },
  { name: "Vũ Hà", roles: ["IAM"] },
  { name: "Tạ Phong", roles: ["IAM", "OPS"] },
  { name: "Đỗ Khoa", roles: ["REQ", "DEV"] },
  { name: "Lý Quân", roles: ["DEV", "OPS"] },
  { name: "Bùi Lan", roles: ["REL"] },
  { name: "Ngô Minh", roles: ["REQ", "OPS"] },
  { name: "Đặng Nam", roles: ["AUD"] },
  { name: "Quản trị SoD", roles: ["ADMIN"] },
];

const DOMAIN = process.env.SEED_EMAIL_DOMAIN || "sod.local";

/** "Nguyễn An" → "an.nguyen"; tài khoản quản trị → "admin" */
function usernameOf(name: string) {
  if (name === "Quản trị SoD") return "admin";
  const parts = name
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .replace(/đ/g, "d")
    .replace(/Đ/g, "D")
    .toLowerCase()
    .split(/\s+/);
  return `${parts.at(-1)}.${parts[0]}`;
}

async function main() {
  const seedPassword = process.env.SEED_PASSWORD;
  if (!seedPassword) throw new Error("Thiếu SEED_PASSWORD trong .env");

  for (const r of ROLES) {
    await prisma.role.upsert({ where: { code: r.code }, update: r, create: r });
  }

  const passwordHash = await hashPassword(seedPassword);
  for (const p of PEOPLE) {
    const username = usernameOf(p.name);
    const email = `${username}@${DOMAIN}`;
    const existing = await prisma.user.findUnique({ where: { username } });
    if (existing) {
      console.log(`  = ${username.padEnd(12)} đã có, bỏ qua`);
      continue;
    }
    await prisma.$transaction(async (tx) => {
      const user = await tx.user.create({
        data: {
          username,
          email,
          fullName: p.name,
          passwordHash,
          status: "ACTIVE",
          emailVerifiedAt: new Date(),
          mustChangePassword: true,
        },
      });
      await tx.userRole.createMany({
        data: p.roles.map((roleCode) => ({ userId: user.id, roleCode, note: "Dữ liệu tạm theo bản kế hoạch" })),
      });
      await tx.auditLog.create({
        data: {
          action: "seed.user.created",
          targetType: "user",
          targetId: user.id,
          actorEmail: email,
          details: { username, roles: p.roles, source: "prisma/seed.ts" },
        },
      });
    });
    console.log(`  + ${username.padEnd(12)} ${email.padEnd(24)} ${p.roles.join(", ")}`);
  }
}

main()
  .then(() => console.log("Seed xong."))
  .catch((e) => {
    console.error(e);
    process.exit(1);
  })
  .finally(() => prisma.$disconnect());
