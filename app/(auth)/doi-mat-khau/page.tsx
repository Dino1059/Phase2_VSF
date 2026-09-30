import { requireUser } from "@/lib/auth/session";
import { Brand } from "@/app/ui/form";
import ChangePasswordForm from "./change-password-form";

export const metadata = { title: "Đổi mật khẩu · SoD Flow" };

export default async function ChangePasswordPage() {
  const user = await requireUser({ allowMustChangePassword: true });
  return (
    <main className="auth">
      <div className="card">
        <Brand />
        <h1>Đổi mật khẩu</h1>
        <p className="muted">
          {user.mustChangePassword
            ? "Bạn đang dùng mật khẩu tạm. Hãy đặt mật khẩu mới để tiếp tục."
            : "Sau khi đổi, các phiên đăng nhập khác sẽ bị đăng xuất."}
        </p>
        <ChangePasswordForm />
      </div>
    </main>
  );
}
