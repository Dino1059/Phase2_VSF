"use client";

import { useActionState } from "react";
import { register } from "@/app/actions/auth";
import { Field, FormAlert, Submit } from "@/app/ui/form";

export default function RegisterForm() {
  const [state, action] = useActionState(register, {});
  return (
    <form action={action} noValidate>
      <FormAlert state={state} />
      <Field name="fullName" label="Họ và tên" state={state} autoComplete="name" autoFocus required />
      <Field name="email" label="Email công ty" type="email" state={state} autoComplete="email" required />
      <Field
        name="username"
        label="Tên đăng nhập"
        state={state}
        autoComplete="username"
        autoCapitalize="none"
        hint="Chữ thường không dấu, số, dấu chấm. Ví dụ: an.nguyen"
        required
      />
      <Field
        name="password"
        label="Mật khẩu"
        type="password"
        state={state}
        autoComplete="new-password"
        hint="Tối thiểu 10 ký tự, có chữ và số."
        required
      />
      <Field name="confirm" label="Nhập lại mật khẩu" type="password" state={state} autoComplete="new-password" required />
      <Submit pendingText="Đang gửi mã…">Đăng ký</Submit>
    </form>
  );
}
