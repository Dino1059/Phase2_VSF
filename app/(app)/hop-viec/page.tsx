import { requireUser } from "@/lib/auth/session";
import { listTickets } from "@/lib/tickets/queries";
import { Seg, TicketList } from "@/app/ui/badges";

export const metadata = { title: "Hộp việc · SoD Flow" };

export default async function Inbox({ searchParams }: PageProps<"/hop-viec">) {
  const user = await requireUser();
  const handled = (await searchParams).tab === "da-xu-ly";
  const tickets = await listTickets(user, handled ? "handled" : "inbox");
  return (
    <>
      <h1>Hộp việc</h1>
      <p className="sub">Chỉ hiện ticket có bước được giao cho bạn.</p>
      <div className="row" style={{ marginBottom: 14 }}>
        <Seg current={handled ? "done" : "wait"} items={[["/hop-viec", "Chờ tôi xử lý", "wait"], ["/hop-viec?tab=da-xu-ly", "Đã xử lý", "done"]]} />
      </div>
      <TicketList tickets={tickets} empty={handled ? "Bạn chưa xử lý ticket nào." : "Không có việc nào đang chờ bạn."} />
    </>
  );
}
