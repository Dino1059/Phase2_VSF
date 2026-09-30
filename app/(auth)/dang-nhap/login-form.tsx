"use client";

import { useActionState } from "react";
import { login } from "@/app/actions/auth";
import { Field, FormAlert, Submit } from "@/app/ui/form";

export default function LoginForm() {
  const [state, action] = useActionState(login, {});
  return (
    <form action={action} noValidate>
      <FormAlert state={state} />
      <Field name="identifier" label="Email hoặc tên đăng nhập" state={state} autoComplete="username" autoFocus required />
      <Field name="password" label="Mật khẩu" type="password" state={state} autoComplete="current-password" required />
      <Submit pendingText="Đang đăng nhập…">Đăng nhập</Submit>
    </form>
  );
}
