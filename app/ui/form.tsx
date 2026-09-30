"use client";

import { useFormStatus } from "react-dom";
import type { FormState } from "@/app/actions/auth";
import type { InputHTMLAttributes, ReactNode } from "react";

type FieldProps = InputHTMLAttributes<HTMLInputElement> & {
  name: string;
  label: string;
  state?: FormState;
  hint?: ReactNode;
};

export function Field({ name, label, state, hint, defaultValue, ...input }: FieldProps) {
  const errors = state?.fieldErrors?.[name];
  const id = `f-${name}`;
  return (
    <div className="field">
      <label htmlFor={id}>{label}</label>
      <input
        id={id}
        name={name}
        defaultValue={state?.values?.[name] ?? defaultValue}
        aria-invalid={errors ? true : undefined}
        aria-describedby={errors ? `${id}-err` : undefined}
        {...input}
      />
      {errors ? (
        <p className="err" id={`${id}-err`}>
          {errors[0]}
        </p>
      ) : (
        hint && <p className="hint">{hint}</p>
      )}
    </div>
  );
}

export function FormAlert({ state }: { state?: FormState }) {
  if (state?.error) return <div className="alert bad" role="alert">{state.error}</div>;
  if (state?.message) return <div className="alert ok" role="status">{state.message}</div>;
  return null;
}

export function Submit({ children, pendingText, className = "btn primary block" }: { children: ReactNode; pendingText?: string; className?: string }) {
  const { pending } = useFormStatus();
  return (
    <button type="submit" className={className} disabled={pending}>
      {pending ? (pendingText ?? "Đang xử lý…") : children}
    </button>
  );
}

export function Brand() {
  return (
    <div className="brand">
      <span className="logo">S</span>SoD Flow
    </div>
  );
}
