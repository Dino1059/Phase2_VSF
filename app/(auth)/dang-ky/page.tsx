import Link from "next/link";
import { redirect } from "next/navigation";
import { getCurrentUser } from "@/lib/auth/session";
import { Brand } from "@/app/ui/form";
import RegisterForm from "./register-form";

export const metadata = { title: "Đăng ký · SoD Flow" };

export default async function RegisterPage() {
  if (await getCurrentUser()) redirect("/");
  return (
    <main className="auth">
      <div>
        <div className="card">
          <Brand />
          <h1>Đăng ký tài khoản</h1>
          <p className="muted">Chúng tôi sẽ gửi mã xác nhận 6 số tới email của bạn.</p>
          <RegisterForm />
        </div>
        <p className="auth-foot">
          Đã có tài khoản? <Link href="/dang-nhap">Đăng nhập</Link>
        </p>
      </div>
    </main>
  );
}
