"use server";

// Server Actions của trang Ủy quyền: chỉ nhận form và gọi lib/delegations. Người thao tác lấy từ phiên đăng nhập.
import { revalidatePath } from "next/cache";
import * as z from "zod";
import { requestMeta } from "@/lib/audit";
import { requireUser } from "@/lib/auth/session";
import { createDelegation, revokeDelegation } from "@/lib/delegations/service";
import { TicketError } from "@/lib/tickets/service";
import type { FormState } from "@/app/actions/auth";

const VN = "+07:00"; // ngày nhập theo giờ Việt Nam
const DateStr = z.string().regex(/^\d{4}-\d{2}-\d{2}$/, "Chọn ngày");

const Schema = z.object({
  roleCode: z.string().min(1).max(10),
  delegateId: z.uuid("Chọn người nhận"),
  from: DateStr,
  to: DateStr,
  reason: z.string().max(500),
});

export async function createDelegationAction(_: FormState, fd: FormData): Promise<FormState> {
  const user = await requireUser();
  const values = Object.fromEntries(["roleCode", "delegateId", "from", "to", "reason"].map((k) => [k, String(fd.get(k) ?? "")]));
  const parsed = Schema.safeParse(values);
  if (!parsed.success) return { fieldErrors: parsed.error.flatten().fieldErrors, values };
  const { from, to, ...rest } = parsed.data;
  try {
    // Hiệu lực từ 00:00 ngày bắt đầu đến hết ngày kết thúc (giờ Việt Nam)
    await createDelegation(
      user,
      { ...rest, validFrom: new Date(`${from}T00:00:00${VN}`), validTo: new Date(new Date(`${to}T00:00:00${VN}`).getTime() + 86_400_000) },
      await requestMeta(),
    );
  } catch (e) {
    if (e instanceof TicketError) return { error: e.message, values };
    throw e;
  }
  revalidatePath("/uy-quyen");
  return { message: "Đã ủy quyền. Người nhận thấy việc của bạn trong Hộp việc của họ." };
}

export async function revokeDelegationAction(fd: FormData): Promise<void> {
  const user = await requireUser();
  const id = z.uuid().safeParse(fd.get("id"));
  if (!id.success) return;
  try {
    await revokeDelegation(user, id.data, await requestMeta());
  } catch (e) {
    if (!(e instanceof TicketError)) throw e;
  }
  revalidatePath("/uy-quyen");
}
