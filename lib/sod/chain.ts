// Sinh chuỗi xử lý từ phân loại (chuyển từ phaseSteps() / buildTicket() của bản mẫu).
//   approval: R → A → P (duyệt xong mới được thực thi)
//   work:     P → R → A (làm xong thì rà soát, nghiệm thu)
//   Trong R và A: cấp thấp → cao, người cao nhất chốt cuối. Auditor luôn cuối mỗi hoạt động.
import { ACTIVITIES, DEFAULT_MATRIX, ROLE_KEYS, SOD_CONFIG, actName, letter, type ActKey, type RoleKey, type StepAction } from "./catalog";
import { classify, type Classification, type Mods } from "./classify";
import { autoAssign, type Person } from "./conflicts";
import type { TicketForm } from "./form";

type ChainStep = {
  key: string;
  role: RoleKey;
  action: StepAction;
  acts: ActKey[];
  phase: number;
  assignee: string | null;
  breakGlass?: boolean;
};
export type Phase = { act: ActKey; name: string; C: RoleKey[]; I: RoleKey[] };
export type Chain = { requestor: string; steps: ChainStep[]; phases: Phase[]; classification: Classification };

export function phaseSteps(actId: number, mods: Mods[number] = {}, matrix: readonly string[] = DEFAULT_MATRIX) {
  const L = (r: RoleKey) => mods[r] ?? letter(actId, r, matrix);
  const byRank = (a: RoleKey, b: RoleKey) => SOD_CONFIG.rank[a] - SOD_CONFIG.rank[b];
  const pick = (l: StepAction) =>
    ROLE_KEYS.filter((r) => r !== "AUD" && L(r) === l && !(l === "P" && r === "REQ")).sort(byRank);
  const [P, R, A] = [pick("P"), pick("R"), pick("A")];
  const aud: [RoleKey, StepAction][] = "RA".includes(L("AUD")) ? [["AUD", L("AUD") as StepAction]] : [];
  const tag = (l: StepAction) => (r: RoleKey): [RoleKey, StepAction] => [r, l];
  const seq =
    ACTIVITIES[actId].kind === "approval"
      ? [...R.map(tag("R")), ...A.map(tag("A")), ...P.map(tag("P"))]
      : [...P.map(tag("P")), ...R.map(tag("R")), ...A.map(tag("A"))];
  return {
    seq: [...seq, ...aud],
    C: ROLE_KEYS.filter((r) => L(r) === "C"),
    I: ROLE_KEYS.filter((r) => L(r) === "I"),
  };
}

/** Dựng chuỗi xử lý và tự gán người không xung đột. `people` = người dùng đang có hiệu lực, theo thứ tự ưu tiên. */
export const buildChain = (d: TicketForm, requestor: string, people: Person[], matrix: readonly string[] = DEFAULT_MATRIX): Chain =>
  buildChainFor(classify(d, matrix), requestor, people, matrix);

/** Như buildChain nhưng từ một phân loại có sẵn (phiếu RBAC không đi qua classify của phiếu cấp quyền). */
export function buildChainFor(cl: Classification, requestor: string, people: Person[], matrix: readonly string[] = DEFAULT_MATRIX): Chain {
  const steps: ChainStep[] = [{ key: "init", role: "REQ", action: "P", acts: ["init"], phase: 0, assignee: requestor }];
  const phases: Phase[] = [{ act: "init", name: actName("init"), C: [], I: [] }];
  let prev: ChainStep[] = [];
  let prevKind: string | null = null;
  for (const a of cl.acts) {
    const kind = ACTIVITIES[a].kind;
    const ps = phaseSteps(a, cl.mods[a], matrix);
    const phase = phases.push({ act: a, name: actName(a), C: ps.C, I: ps.I }) - 1;
    const cur: ChainStep[] = [];
    for (const [role, action] of ps.seq) {
      // Gộp với hoạt động liền trước nếu cùng vai trò và hành động (A chỉ gộp khi cả hai đều là hoạt động phê duyệt)
      const canMerge = action !== "A" || (kind === "approval" && prevKind === "approval");
      const dup = canMerge && prev.find((s) => s.role === role && s.action === action);
      if (dup) {
        dup.acts.push(a);
        continue;
      }
      const s: ChainStep = { key: `${a}-${role}-${action}`, role, action, acts: [a], phase, assignee: null };
      steps.push(s);
      cur.push(s);
    }
    prev = cur;
    prevKind = kind;
  }
  if (cl.breakGlass) {
    const phase = phases.push({ act: "bg", name: actName("bg"), C: ["CISO"], I: ["DPO"] }) - 1;
    steps.push({ key: "bg-AUD-R", role: "AUD", action: "R", acts: ["bg"], phase, assignee: null, breakGlass: true });
  }
  const chain: Chain = { requestor, steps, phases, classification: cl };
  autoAssign(chain, people);
  return chain;
}

/** Số giờ SLA của một bước */
export const slaHours = (step: Pick<ChainStep, "action" | "breakGlass">, priorityFactor: number, sla: Record<StepAction, number> = SOD_CONFIG.sla) =>
  step.breakGlass ? SOD_CONFIG.breakGlassHours : sla[step.action] * priorityFactor;

/** Vai trò chỉ nhận thông báo khi ticket hoàn tất */
export const informedRoles = (phases: Phase[]) => [...new Set(phases.flatMap((p) => p.I))];
