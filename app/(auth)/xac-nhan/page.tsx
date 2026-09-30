import Link from "next/link";
import { Brand } from "@/app/ui/form";
import VerifyForm from "./verify-form";

export const metadata = { title: "Xác nhận email · SoD Flow" };

export default async function VerifyPage({ searchParams }: PageProps<"/xac-nhan">) {
  const { email, sent } = await searchParams;
  const addr = typeof email === "string" ? email : "";
  return (
    <main className="auth">
      <div>
        <div className="card">
          <Brand />
          <h1>Xác nhận email</h1>
          <p className="muted">
            {addr ? (
              <>
                Nhập mã 6 số {sent ? "vừa gửi" : "đã gửi"} tới <strong>{addr}</strong>. Mã có hiệu lực 10 phút.
              </>
            ) : (
              "Nhập email đã đăng ký và mã 6 số nhận được."
            )}
          </p>
          <VerifyForm email={addr} />
        </div>
        <p className="auth-foot">
          <Link href="/dang-ky">Đăng ký lại</Link> · <Link href="/dang-nhap">Đăng nhập</Link>
        </p>
      </div>
    </main>
  );
}
