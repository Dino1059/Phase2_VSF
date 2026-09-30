"use client";

import { useActionState } from "react";
import { changePassword } from "@/app/actions/auth";
import { Field, FormAlert, Submit } from "@/app/ui/form";

export default function ChangePasswordForm() {
  const [state, action] = useActionState(changePassword, {});
  return (
    <form action={action} noValidate>
      <FormAlert state={state} />
      <Field name="current" label="Mật khẩu hiện tại" type="password" state={state} autoComplete="current-password" autoFocus required />
      <Field
        name="password"
        label="Mật khẩu mới"
        type="password"
        state={state}
        autoComplete="new-password"
        hint="Tối thiểu 10 ký tự, có chữ và số."
        required
      />
      <Field name="confirm" label="Nhập lại mật khẩu mới" type="password" state={state} autoComplete="new-password" required />
      <Submit>Lưu mật khẩu</Submit>
    </form>
  );
}
