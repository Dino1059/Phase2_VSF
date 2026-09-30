import type { ReactNode } from "react";
import { requireUser } from "@/lib/auth/session";
import Topbar from "@/app/ui/topbar";

// Layout không chạy lại khi chuyển trang phía client, nên mỗi trang / action vẫn tự gọi requireUser().
export default async function AppLayout({ children }: { children: ReactNode }) {
  const user = await requireUser();
  return (
    <>
      <Topbar user={user} />
      <main className="wrap" style={{ paddingBottom: 40 }}>
        {children}
      </main>
    </>
  );
}
