import { notFound, redirect } from "next/navigation";
import { requireUser } from "@/lib/auth/session";
import { fmtTime } from "@/lib/format";
import { getTicket } from "@/lib/tickets/queries";
import CreateForm from "../../moi/create-form";

export const metadata = { title: "Bổ sung phiếu · SoD Flow" };

export default async function RevisePage({ params }: PageProps<"/yeu-cau/[id]/bo-sung">) {
  const user = await requireUser();
  const { id } = await params;
  const t = await getTicket(user, id);
  if (!t || t.requesterId !== user.id) notFound();
  if (t.status !== "RETURNED") redirect(`/yeu-cau/${t.id}`);
  const returned = t.steps.find((s) => s.decision?.outcome === "RETURN")?.decision;
  return (
    <>
      <h1>Bổ sung phiếu {t.code}</h1>
      <p className="sub">
        {returned
          ? `${returned.actor.fullName} trả lại lúc ${fmtTime(returned.decidedAt)}: “${returned.comment}”. `
          : ""}
        Sửa nội dung rồi gửi lại. Đổi phạm vi quyền thì các bước đã duyệt phải duyệt lại; đổi tầng dữ liệu, DLCN, ngoại lệ hoặc loại phiếu
        có thể làm đổi chuỗi duyệt, khi đó hệ thống tạo phiếu mới và huỷ phiếu này.
      </p>
      <CreateForm
        fullName={user.fullName}
        email={user.email}
        revise={{ ticketId: t.id, version: t.version, form: t.form }}
      />
    </>
  );
}
