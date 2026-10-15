// Công cụ chạy thử đầu-cuối (không phải test tự động): duyệt hoặc từ chối một phiếu bằng đúng service mà giao diện dùng,
// theo từng người được giao bước. Dừng ở bước thực hiện của Prod. Op.: bước đó chỉ hoàn tất khi Executor chạy ở DataTrust.
// Dùng cho doc/KE_HOACH_SOD_DATATRUST.md mục 11, trên DB sod_test.
//   DATABASE_URL=... APP_DATABASE_URL=... npx tsx --conditions=react-server tests/e2e/datatrust-approve.ts <mã phiếu> approve|reject [số bước tối đa]
import { prisma } from "@/lib/db";
import { decideStep } from "@/lib/tickets/service";
import { flushDatatrustOutbox } from "@/lib/integrations/outbox";
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
    if (cur.action === "P" && mode === "approve") {
      const ops = await prisma.user.findUniqueOrThrow({ where: { id: cur.assigneeId! } });
      console.log(`chờ Executor: ${cur.roleCode}:P giao cho ${ops.username}, thực thi ở DataTrust`);
      break;
    }
    const who = await asUser((await prisma.user.findUniqueOrThrow({ where: { id: cur.assigneeId! } })).username);
    const approve = mode === "approve";
    await decideStep(who, { ticketId: t.id, stepId: cur.id, version: t.version, approve, comment: approve ? "" : "Không đồng ý (chạy thử)" }, meta);
    console.log(`${approve ? "duyệt" : "từ chối"}: ${cur.roleCode}:${cur.action} bởi ${who.username}`);
    if (!approve) break;
  }
  const end = await prisma.ticket.findUniqueOrThrow({ where: { id: ticket.id } });
  console.log(`TRẠNG THÁI ${end.code}: ${end.status}`);
  // Gửi hẳn các sự kiện đang chờ trước khi thoát (lần gửi ngay sau commit chạy nền, tiến trình thoát sớm thì bị bỏ dở)
  await new Promise((r) => setTimeout(r, 300));
  console.log("outbox:", JSON.stringify(await flushDatatrustOutbox()));
}
main().finally(() => prisma.$disconnect());
