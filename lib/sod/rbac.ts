// Phiếu cấp / thu hồi vai trò SoD Flow (loại "Tạo / sửa RBAC role", dòng 7 ma trận). KE_HOACH.md luồng 6.
// Chuỗi duyệt: Release Manager rà soát → System Owner, CISO phê duyệt → IAM thực hiện. Người được cấp không nằm trong chuỗi.
import * as z from "zod";
import { ROLES, ticketType, type RoleKey } from "./catalog";
import type { Classification } from "./classify";

/** Vai trò cấp được qua phiếu. REQ không cần phiếu (tự có khi xác nhận email). */
export const RBAC_ROLES = ["LM", "DPO", "SO", "CISO", "IAM", "DEV", "REL", "OPS", "AUD", "ADMIN"] as const satisfies readonly (Exclude<RoleKey, "REQ"> | "ADMIN")[];
export const roleLabel = (code: string) => (code === "ADMIN" ? "Quản trị SoD (Admin)" : (ROLES[code as RoleKey]?.name ?? code));

export const RBAC_OPS = { grant: "Cấp vai trò", revoke: "Thu hồi vai trò" } as const;

export const RbacInputSchema = z.object({
  op: z.enum(["grant", "revoke"]),
  targetUserId: z.uuid(),
  roleCode: z.enum(RBAC_ROLES),
  /** Hạn của vai trò (YYYY-MM-DD), để trống = không thời hạn. Chỉ dùng khi cấp. */
  validTo: z.union([z.literal(""), z.string().regex(/^\d{4}-\d{2}-\d{2}$/)]),
  reason: z.string().trim().min(1).max(1000),
});
export type RbacInput = z.infer<typeof RbacInputSchema>;

/** Nội dung lưu trong tickets.form của phiếu RBAC. Trigger DB đọc op / targetUserId / roleCode. */
export type RbacForm = RbacInput & { kind: "rbac"; targetName: string };

export const isRbacForm = (f: unknown): f is RbacForm => !!f && typeof f === "object" && (f as { kind?: unknown }).kind === "rbac";

export function classifyRbac(): Classification {
  return {
    type: ticketType("rbac"),
    acts: [7],
    mods: {},
    reasons: ["Phiếu cấp / thu hồi vai trò → “Tạo hoặc sửa RBAC role” (dòng 7 ma trận): Release Manager rà soát, System Owner và CISO phê duyệt, IAM thực hiện. Người được cấp không nằm trong chuỗi."],
    level: 3,
    pii: false,
    breakGlass: false,
  };
}
