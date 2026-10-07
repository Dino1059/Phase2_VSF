"use server";

// Server Actions chỉ nhận dữ liệu và gọi lib/tickets — không chứa luật nghiệp vụ.
// Người thao tác luôn lấy từ phiên đăng nhập, không bao giờ từ dữ liệu gửi lên.
import { redirect } from "next/navigation";
import * as z from "zod";
import { requestMeta } from "@/lib/audit";
import { requireUser } from "@/lib/auth/session";
import { TicketError, cancelTicket, createRbacTicket, expireTicket, parseRbac, decideStep, parseForm, previewTicket, returnTicket, reviseTicket, submitTicket, type Preview } from "@/lib/tickets/service";
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
  decision: z.enum(["approve", "reject", "return"]),
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
    const meta = await requestMeta();
    if (decision === "return") await returnTicket(user, d, meta);
    else await decideStep(user, { ...d, approve: decision === "approve" }, meta);
  } catch (e) {
    if (e instanceof TicketError) return { error: e.message, values: { comment: d.comment } };
    throw e;
  }
  // Ô thao tác biến mất sau khi quyết định, nên thông báo hiện ở đầu trang chi tiết
  redirect(`/yeu-cau/${d.ticketId}?ket-qua=${decision}`);
}

const ReviseIds = z.object({ ticketId: z.uuid(), version: z.coerce.number().int().min(0) });

/** Người yêu cầu gửi bản bổ sung cho phiếu bị trả lại. */
export async function reviseAction(ticketId: string, version: number, input: unknown): Promise<{ errors: [string, string][] }> {
  const user = await requireUser();
  const ids = ReviseIds.safeParse({ ticketId, version });
  if (!ids.success) return { errors: [["", "Dữ liệu không hợp lệ."]] };
  let result;
  try {
    result = await reviseTicket(user, { ...ids.data, form: parseForm(input) }, await requestMeta());
  } catch (e) {
    if (e instanceof TicketError) return { errors: [["", e.message]] };
    throw e;
  }
  if (!result.ok) return { errors: result.errors };
  redirect(`/yeu-cau/${result.id}?ket-qua=${result.supersededCode ? "superseded" : "revised"}`);
}

const CancelSchema = z.object({ ticketId: z.uuid(), version: z.coerce.number().int().min(0), reason: z.string().max(2000) });

export async function cancelAction(_: FormState, fd: FormData): Promise<FormState> {
  const user = await requireUser();
  const parsed = CancelSchema.safeParse({ ticketId: fd.get("ticketId"), version: fd.get("version"), reason: fd.get("reason") ?? "" });
  if (!parsed.success) return { error: "Dữ liệu không hợp lệ." };
  try {
    await cancelTicket(user, parsed.data, await requestMeta());
  } catch (e) {
    if (e instanceof TicketError) return { error: e.message, values: { reason: parsed.data.reason } };
    throw e;
  }
  redirect(`/yeu-cau/${parsed.data.ticketId}?ket-qua=cancelled`);
}

/** Phiếu cấp / thu hồi vai trò SoD Flow. */
export async function submitRbacAction(input: unknown): Promise<{ errors: [string, string][] }> {
  const user = await requireUser();
  let result;
  try {
    result = await createRbacTicket(user, parseRbac(input), await requestMeta());
  } catch (e) {
    if (e instanceof TicketError) return { errors: [["", e.message]] };
    throw e;
  }
  if (!result.ok) return { errors: result.errors };
  redirect(`/yeu-cau/${result.id}`);
}

export async function expireAction(_: FormState, fd: FormData): Promise<FormState> {
  const user = await requireUser();
  const parsed = CancelSchema.safeParse({ ticketId: fd.get("ticketId"), version: fd.get("version"), reason: fd.get("reason") ?? "" });
  if (!parsed.success) return { error: "Dữ liệu không hợp lệ." };
  try {
    await expireTicket(user, parsed.data, await requestMeta());
  } catch (e) {
    if (e instanceof TicketError) return { error: e.message, values: { reason: parsed.data.reason } };
    throw e;
  }
  redirect(`/yeu-cau/${parsed.data.ticketId}?ket-qua=expired`);
}
