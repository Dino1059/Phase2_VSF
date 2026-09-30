// So kết quả lib/sod với bản mẫu ../app.js trên mọi tổ hợp phiếu × người yêu cầu.
// Bản mẫu được chạy nguyên trạng trong vm với DOM giả tối thiểu.
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import vm from "node:vm";
import { ACTIVITIES, type RoleKey } from "@/lib/sod/catalog";
import { buildChain, phaseSteps } from "@/lib/sod/chain";
import { violations, type Person } from "@/lib/sod/conflicts";
import { emptyForm, emptyRow, validateForm, type TicketForm } from "@/lib/sod/form";

const ROOT = join(process.cwd(), "..");

function loadPrototype() {
  const el = (): Record<string, unknown> => ({
    classList: { toggle() {}, add() {}, remove() {} },
    style: {},
    querySelector: () => el(),
    querySelectorAll: () => [],
    appendChild() {},
    addEventListener() {},
  });
  const ctx = vm.createContext({
    document: { querySelector: () => el(), querySelectorAll: () => [], addEventListener() {}, body: el() },
    window: { addEventListener() {} },
    location: { hash: "" },
    localStorage: { getItem: () => null, setItem() {} },
    setInterval() {},
    structuredClone,
    crypto,
    console,
  });
  for (const f of ["data.js", "app.js"]) vm.runInContext(readFileSync(join(ROOT, f), "utf8"), ctx, { filename: f });
  return vm.runInContext("({ buildTicket, violations, phaseSteps, validateForm, DEFAULT_PEOPLE })", ctx);
}

const proto = loadPrototype();
const people: Person[] = proto.DEFAULT_PEOPLE.map((p: { id: string; name: string; roles: RoleKey[] }) => ({ ...p }));
const plain = <T>(v: T): T => JSON.parse(JSON.stringify(v));

// Bản mẫu có lỗi đặt tên cặp: khoá 'DEV|CISO' không bao giờ khớp vì code sắp xếp thành 'CISO|DEV'.
// Bản mới sửa lỗi đó, nên chuẩn hoá tên cặp này trước khi so.
const fixProtoName = (c: string) =>
  c === "CISO/Security ↔ Developer" || c === "Developer ↔ CISO/Security" ? "Developer ↔ Production Approver" : c;

test("phaseSteps giống bản mẫu cho cả 19 hoạt động", () => {
  for (const a of ACTIVITIES) assert.deepEqual(plain(phaseSteps(a.id)), plain(proto.phaseSteps(a.id)), a.name);
});

test("chuỗi xử lý, người được gán và vi phạm SoD giống bản mẫu", () => {
  let cases = 0;
  for (const loaiPhieu of ["new", "adjust", "extend", "revoke", "bg"] as const)
    for (const dlcn of ["none", "basic", "sensitive"] as const)
      for (const tang of ["1", "2", "3"] as const)
        for (const exception of [false, true])
          for (const req of people) {
            const form: TicketForm = { ...emptyForm(), loaiPhieu, dlcn, exception, rows: [{ ...emptyRow(), tang }] };
            const mine = buildChain(form, req.id, people);
            const theirs = proto.buildTicket({ ...form, requestor: req.id, overrides: {} });
            const label = `${loaiPhieu}/${dlcn}/tầng ${tang}/ngoại lệ ${exception}/${req.name}`;

            const { type, ...cl } = mine.classification;
            const { type: protoType, ...protoCl } = theirs.classification;
            assert.equal(type.id, protoType.id, label);
            assert.deepEqual(plain(cl), plain(protoCl), label);
            assert.deepEqual(plain(mine.phases), plain(theirs.phases), label);
            assert.deepEqual(
              plain(mine.steps),
              plain(theirs.steps).map((s: object) => Object.fromEntries(Object.entries(s).filter(([k]) => k !== "status"))),
              label,
            );
            assert.deepEqual(
              violations(mine),
              plain(proto.violations(theirs)).map((v: { i: number; c: string }) => ({ ...v, c: fixProtoName(v.c) })),
              label,
            );
            cases++;
          }
  assert.equal(cases, 5 * 3 * 3 * 2 * people.length);
});

test("kiểm tra phiếu giống bản mẫu", () => {
  const filled: TicketForm = {
    ...emptyForm("Nguyễn An", "an@congty.vn"),
    loaiPhieu: "new", khan: "urgent", maNV: "NV1", phongBan: "IT", chucDanh: "Kỹ sư", capBac: "T3",
    viTri: "Vận hành", thiTruong: "intl", mucDich: "Dự án X", dlcn: "sensitive", camKet: true, kyTen: "Nguyễn An",
    rows: [{ heThong: "CRM", taiNguyen: "bảng KH", tang: "2", mucQuyen: "RO", thoiHan: "" }, emptyRow()],
    exception: true, exFrom: "2026-10-02T09:00", exTo: "2026-10-01T09:00", nhapThay: true,
  };
  for (const f of [emptyForm(), filled, { ...filled, loaiPhieu: "revoke" as const }]) {
    assert.deepEqual(validateForm(f), plain(proto.validateForm({ ...f, requestor: "u1" })));
  }
});
