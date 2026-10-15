// Công cụ chạy thử đầu-cuối (không phải test tự động): duyệt hoặc từ chối một phiếu bằng đúng service mà giao diện dùng,
// theo từng người được giao bước. Dùng cho PLAN_NOI_SOD_DATATRUST.md bước 8, trên DB sod_test.
//   DATABASE_URL=... APP_DATABASE_URL=... npx tsx --conditions=react-server tests/e2e/datatrust-approve.ts <mã phiếu> approve|reject [số bước tối đa]
import { prisma } from "@/lib/db";
import { decideStep } from "@/lib/tickets/service";
import { asUser, meta } from "../security/helpers";

const [code, mode = "approve", maxArg] = process.argv.slice(2);
const max = Number(maxArg ?? 20);

async function main() {
  if (!/_test(\?|$)/.test(process.env.DATABASE_URL ?? "")) throw new Error("Chỉ chạy trên DB test (tên kết thúc bằng _test).");
  const ticket = await prisma.ticket.findUniqueOrThrow({ where: { code } });
  for (let i = 0; i < max; i++) {
    const t = await prisma.ticket.findUniqueOrThrow({ where: { id: ticket.id }, include: { steps: { orderBy: { idx: "asc" } } } });
    if (t.status !== "OPEN") break;
    const cur = t.steps.find((s) => s.status === "CURRENT" && s.idx > 0)!;
    const who = await asUser((await prisma.user.findUniqueOrThrow({ where: { id: cur.assigneeId! } })).username);
    const approve = mode === "approve";
    await decideStep(who, { ticketId: t.id, stepId: cur.id, version: t.version, approve, comment: approve ? "" : "Không đồng ý (chạy thử)" }, meta);
    console.log(`${approve ? "duyệt" : "từ chối"}: ${cur.roleCode}:${cur.action} bởi ${who.username}`);
    if (!approve) break;
  }
  const end = await prisma.ticket.findUniqueOrThrow({ where: { id: ticket.id } });
  console.log(`TRẠNG THÁI ${end.code}: ${end.status}`);
  // Chờ gửi webhook xong (gửi ngay sau commit, không chờ worker)
  await new Promise((r) => setTimeout(r, 2500));
}
main().finally(() => prisma.$disconnect());
