import { requireUser } from "@/lib/auth/session";
import { seesAllTickets } from "@/lib/authz/policy";
import { listTickets } from "@/lib/tickets/queries";
import { Seg, TicketList } from "@/app/ui/badges";

export const metadata = { title: "Tickets · SoD Flow" };

const STATUSES = { OPEN: "Đang xử lý", RETURNED: "Chờ bổ sung", DONE: "Hoàn tất", REJECTED: "Từ chối", CANCELLED: "Đã huỷ", EXPIRED: "Hết hạn" } as const;
type Status = keyof typeof STATUSES;

export default async function MyTickets({ searchParams }: PageProps<"/yeu-cau">) {
  const user = await requireUser();
  const sp = await searchParams;
  const all = sp["pham-vi"] === "tat-ca" && seesAllTickets(user);
  const status = typeof sp["trang-thai"] === "string" && sp["trang-thai"] in STATUSES ? (sp["trang-thai"] as Status) : undefined;
  const tickets = await listTickets(user, all ? "all" : "mine", status);

  const base = all ? "/yeu-cau?pham-vi=tat-ca" : "/yeu-cau";
  const q = (s?: Status) => (s ? `${base}${all ? "&" : "?"}trang-thai=${s}` : base);
  return (
    <>
      <h1>{all ? "Tất cả ticket" : "Yêu cầu của tôi"}</h1>
      <p className="sub">{all ? "Chỉ đọc — dành cho Auditor và Quản trị." : "Các phiếu bạn đã gửi. Bấm vào một phiếu để xem tiến độ."}</p>
      <div className="row" style={{ marginBottom: 14 }}>
        {seesAllTickets(user) && (
          <Seg
            current={all ? "all" : "mine"}
            items={[["/yeu-cau", "Của tôi", "mine"], ["/yeu-cau?pham-vi=tat-ca", "Tất cả", "all"]]}
          />
        )}
        <Seg
          current={status ?? "any"}
          items={[[q(), "Tất cả trạng thái", "any"], ...(Object.entries(STATUSES) as [Status, string][]).map(([k, l]) => [q(k), l, k] as [string, string, string])]}
        />
      </div>
      <TicketList tickets={tickets} empty="Chưa có phiếu nào." />
    </>
  );
}
