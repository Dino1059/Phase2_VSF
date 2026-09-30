import * as z from "zod";

const USERNAME_RE = /^[a-z0-9][a-z0-9._-]{2,49}$/;

const password = z
  .string()
  .min(10, { error: "Mật khẩu tối thiểu 10 ký tự." })
  .max(128, { error: "Mật khẩu tối đa 128 ký tự." })
  .regex(/[A-Za-z]/, { error: "Mật khẩu cần có chữ cái." })
  .regex(/[0-9]/, { error: "Mật khẩu cần có chữ số." });

export const LoginSchema = z.object({
  identifier: z.string().trim().toLowerCase().min(1, { error: "Nhập email hoặc tên đăng nhập." }).max(254),
  password: z.string().min(1, { error: "Nhập mật khẩu." }).max(128),
});

export const RegisterSchema = z
  .object({
    fullName: z.string().trim().min(2, { error: "Họ tên tối thiểu 2 ký tự." }).max(150),
    username: z
      .string()
      .trim()
      .toLowerCase()
      .regex(USERNAME_RE, { error: "3–50 ký tự: chữ thường không dấu, số, dấu chấm, gạch dưới, gạch ngang." }),
    email: z.string().trim().toLowerCase().pipe(z.email({ error: "Email không hợp lệ." }).max(254)),
    password,
    confirm: z.string(),
  })
  .refine((v) => v.password === v.confirm, { path: ["confirm"], error: "Mật khẩu nhập lại không khớp." });

export const VerifySchema = z.object({
  email: z.string().trim().toLowerCase().pipe(z.email({ error: "Email không hợp lệ." })),
  code: z.string().trim().regex(/^\d{6}$/, { error: "Mã gồm 6 chữ số." }),
});

export const ChangePasswordSchema = z
  .object({ current: z.string().min(1, { error: "Nhập mật khẩu hiện tại." }), password, confirm: z.string() })
  .refine((v) => v.password === v.confirm, { path: ["confirm"], error: "Mật khẩu nhập lại không khớp." })
  .refine((v) => v.password !== v.current, { path: ["password"], error: "Mật khẩu mới phải khác mật khẩu hiện tại." });

/** Danh sách tên miền được phép đăng ký (ALLOWED_EMAIL_DOMAINS, cách nhau dấu phẩy). Rỗng = cho phép tất cả. */
export function emailDomainAllowed(email: string): boolean {
  const allowed = (process.env.ALLOWED_EMAIL_DOMAINS || "")
    .split(",")
    .map((d) => d.trim().toLowerCase())
    .filter(Boolean);
  return allowed.length === 0 || allowed.includes(email.split("@")[1]);
}
