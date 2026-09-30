"use client";

import { useActionState } from "react";
import { resendCode, verifyEmail } from "@/app/actions/auth";
import { Field, FormAlert, Submit } from "@/app/ui/form";

export default function VerifyForm({ email }: { email: string }) {
  const [state, action] = useActionState(verifyEmail, {});
  const [resent, resend] = useActionState(resendCode, {});
  return (
    <>
      <form action={action} noValidate>
        <FormAlert state={state} />
        {email ? (
          <input type="hidden" name="email" value={email} />
        ) : (
          <Field name="email" label="Email" type="email" state={state} autoComplete="email" required />
        )}
        <Field
          name="code"
          label="Mã xác nhận"
          state={state}
          className="code-input"
          inputMode="numeric"
          autoComplete="one-time-code"
          maxLength={6}
          pattern="\d{6}"
          autoFocus
          required
        />
        <Submit pendingText="Đang xác nhận…">Xác nhận</Submit>
      </form>
      {email && (
        <form action={resend} style={{ marginTop: 12, textAlign: "center" }}>
          <FormAlert state={resent} />
          <input type="hidden" name="email" value={email} />
          <span className="muted">Không nhận được mã? </span>
          <Submit className="btn link" pendingText="Đang gửi…">
            Gửi lại mã
          </Submit>
        </form>
      )}
    </>
  );
}
