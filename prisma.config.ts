import "dotenv/config";
import { defineConfig } from "prisma/config";

// CLI (migrate, seed) chạy bằng tài khoản chủ sở hữu schema.
// Ứng dụng khi chạy dùng APP_DATABASE_URL (xem lib/db.ts).
export default defineConfig({
  schema: "prisma/schema.prisma",
  migrations: {
    path: "prisma/migrations",
    seed: "tsx prisma/seed.ts",
  },
  datasource: {
    url: process.env["DATABASE_URL"],
  },
});
