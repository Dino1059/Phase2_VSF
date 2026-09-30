// Phân loại phiếu → các hoạt động kiểm soát trong ma trận (chuyển từ classify() của bản mẫu).
import { ACTIVITIES, ROLES, SOD_CONFIG, VERB, actName, letter, ticketType, type Letter, type RoleKey, type TicketType } from "./catalog";
import { LOAI_PHIEU, formLevel, formPii, type TicketForm } from "./form";

/** Nâng vai trò trong một hoạt động theo quy tắc ngoại lệ: { actId: { role: letter } } */
export type Mods = Record<number, Partial<Record<RoleKey, Letter>>>;

export type Classification = {
  type: TicketType;
  acts: number[];
  mods: Mods;
  reasons: string[];
  level: number;
  pii: boolean;
  breakGlass: boolean;
};

export function classify(d: TicketForm): Classification {
  const revoke = d.loaiPhieu === "revoke";
  const type = ticketType(revoke ? "offboard" : "access");
  const acts: number[] = [...type.acts];
  const level = formLevel(d);
  const pii = formPii(d);
  const breakGlass = d.loaiPhieu === "bg";
  const loai = d.loaiPhieu ? LOAI_PHIEU[d.loaiPhieu] : "chưa chọn";
  const reasons = [`Loại phiếu “${loai}” → ${revoke ? "Thu hồi quyền (dòng gần nhất trong ma trận)" : "Cấp quyền truy cập"}`];
  const mods: Mods = {};

  if (!revoke && pii) {
    acts.splice(acts.indexOf(1) + 1, 0, 2);
    reasons.push("Có DLCN → thêm “Phê duyệt quyền có truy cập PII”");
  }
  if (!revoke && level === 3) {
    acts.splice(acts.indexOf(4), 0, 3);
    reasons.push("Tầng dữ liệu 3 → thêm “Phê duyệt quyền đặc quyền hoặc quyền DB”");
  }
  if (d.exception) {
    const i = acts.indexOf(0);
    acts.splice(i >= 0 ? i + 1 : 0, 0, 15);
    reasons.push("Xin ngoại lệ SoD → thêm “Phê duyệt ngoại lệ kiểm soát” trước khi thực thi");
  }

  // QT 5.4: Level 2 hoặc PII cần DPO rà soát; Level 3 cần CISO phê duyệt
  const ensure = (role: RoleKey, need: string, why: string) => {
    if (acts.some((a) => need.includes(letter(a, role)) || need.includes(mods[a]?.[role] ?? "-"))) return;
    const target =
      acts.find((a) => ACTIVITIES[a].kind === "approval" && !"XP".includes(letter(a, role))) ??
      acts.find((a) => !"XP".includes(letter(a, role)));
    if (target === undefined) return;
    (mods[target] ??= {})[role] = need[0] as Letter;
    reasons.push(`${why} → ${ROLES[role].name} ${VERB[need[0] as "R" | "A"].toLowerCase()} ở “${actName(target)}”`);
  };
  if (pii || level >= 2) ensure("DPO", "RA", "QT 5.4: Tầng 2 / DLCN cần DPO rà soát");
  if (level === 3) ensure("CISO", "A", "QT 5.4: Tầng 3 cần CISO phê duyệt");
  if (d.dlcn === "sensitive") reasons.push("DLCN nhạy cảm → bắt buộc lý do nghiệp vụ và ý kiến DPO");
  if (breakGlass) reasons.push(`Break-glass → ghi log, giám sát phiên, Auditor hậu kiểm trong ${SOD_CONFIG.breakGlassHours}h`);

  return { type, acts, mods, reasons, level, pii, breakGlass };
}
