import Link from "next/link";
import { redirect } from "next/navigation";
import { getCurrentUser } from "@/lib/auth/session";
import { Brand } from "@/app/ui/form";
import LoginForm from "./login-form";

export const metadata = { title: "Đăng nhập · SoD Flow" };

export default async function LoginPage() {
  if (await getCurrentUser()) redirect("/");
  return (
    <main className="auth">
      <div>
        <div className="card">
          <Brand />
          <h1>Đăng nhập</h1>
          <p className="muted">Dùng email công ty hoặc tên đăng nhập.</p>
          <LoginForm />
        </div>
        <p className="auth-foot">
          Chưa có tài khoản? <Link href="/dang-ky">Đăng ký</Link>
        </p>
      </div>
    </main>
  );
}
