"use server";

// Server Actions chỉ nhận dữ liệu và gọi lib/tickets — không chứa luật nghiệp vụ.
// Người thao tác luôn lấy từ phiên đăng nhập, không bao giờ từ dữ liệu gửi lên.
import { redirect } from "next/navigation";
import * as z from "zod";
import { requestMeta } from "@/lib/audit";
import { requireUser } from "@/lib/auth/session";
import { TicketError, decideStep, parseForm, previewTicket, submitTicket, type Preview } from "@/lib/tickets/service";
import type { FormState } from "@/app/actions/auth";

export async function previewAction(input: unknown): Promise<Preview | null> {
  const user = await requireUser();
  try {
    return await previewTicket(user, parseForm(input));
  } catch (e) {
    if (e instanceof TicketError) return null;
    throw e;
  }
}

export async function submitAction(input: unknown): Promise<{ errors: [string, string][] }> {
  const user = await requireUser();
  let result;
  try {
    result = await submitTicket(user, parseForm(input), await requestMeta());
  } catch (e) {
    if (e instanceof TicketError) return { errors: [["", e.message]] };
    throw e;
  }
  if (!result.ok) return { errors: result.errors };
  redirect(`/yeu-cau/${result.id}`);
}

const DecisionSchema = z.object({
  ticketId: z.uuid(),
  stepId: z.uuid(),
  version: z.coerce.number().int().min(0),
  decision: z.enum(["approve", "reject"]),
  comment: z.string().max(2000),
});

export async function decideAction(_: FormState, fd: FormData): Promise<FormState> {
  const user = await requireUser();
  const parsed = DecisionSchema.safeParse({
    ticketId: fd.get("ticketId"),
    stepId: fd.get("stepId"),
    version: fd.get("version"),
    decision: fd.get("decision"),
    comment: fd.get("comment") ?? "",
  });
  if (!parsed.success) return { error: "Dữ liệu không hợp lệ." };
  const { decision, ...d } = parsed.data;
  try {
    await decideStep(user, { ...d, approve: decision === "approve" }, await requestMeta());
  } catch (e) {
    if (e instanceof TicketError) return { error: e.message, values: { comment: d.comment } };
    throw e;
  }
  // Ô thao tác biến mất sau khi quyết định, nên thông báo hiện ở đầu trang chi tiết
  redirect(`/yeu-cau/${d.ticketId}?ket-qua=${decision}`);
}
