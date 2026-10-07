"use server";

// Server Actions của trang Quản trị: chỉ nhận dữ liệu và gọi lib/config. Người thao tác lấy từ phiên đăng nhập.
import { revalidatePath } from "next/cache";
import * as z from "zod";
import { requestMeta } from "@/lib/audit";
import { requireUser } from "@/lib/auth/session";
import { decideConfig, proposeConfig, withdrawConfig } from "@/lib/config/service";
import { TicketError } from "@/lib/tickets/service";

export async function proposeConfigAction(config: unknown, reason: string): Promise<{ error?: string }> {
  const user = await requireUser();
  try {
    await proposeConfig(user, config, String(reason ?? ""), await requestMeta());
  } catch (e) {
    if (e instanceof TicketError) return { error: e.message };
    throw e;
  }
  revalidatePath("/quan-tri");
  return {};
}

const Decision = z.object({ id: z.uuid(), decision: z.enum(["approve", "reject"]), note: z.string().max(1000) });

export async function decideConfigAction(fd: FormData): Promise<void> {
  const user = await requireUser();
  const p = Decision.safeParse({ id: fd.get("id"), decision: fd.get("decision"), note: fd.get("note") ?? "" });
  if (!p.success) return;
  try {
    await decideConfig(user, p.data.id, p.data.decision === "approve", p.data.note, await requestMeta());
  } catch (e) {
    if (!(e instanceof TicketError)) throw e;
    // Lỗi nghiệp vụ đã được ghi nhật ký; trang hiện lại trạng thái hiện tại
  }
  revalidatePath("/quan-tri");
}

export async function withdrawConfigAction(fd: FormData): Promise<void> {
  const user = await requireUser();
  const id = z.uuid().safeParse(fd.get("id"));
  if (!id.success) return;
  try {
    await withdrawConfig(user, id.data, await requestMeta());
  } catch (e) {
    if (!(e instanceof TicketError)) throw e;
  }
  revalidatePath("/quan-tri");
}
