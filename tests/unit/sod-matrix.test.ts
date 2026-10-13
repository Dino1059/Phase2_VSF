// Quy tắc ma trận đã chốt 10/2026: mỗi dòng tối đa một P, Auditor R kiểm tra trước P, IAM không truy cập dữ liệu PII.
import { test } from "node:test";
import assert from "node:assert/strict";
import { ACTIVITIES, DEFAULT_MATRIX, MATRIX_NOTES, ROLE_KEYS, letter, ticketType } from "@/lib/sod/catalog";
import { phaseSteps } from "@/lib/sod/chain";
import { matrixRuleProblems } from "@/lib/config/schema";

const roles = (actId: number) => phaseSteps(actId).seq.map(([r, l]) => `${r}:${l}`);

test("ma trận chuẩn không vi phạm quy tắc", () => {
  assert.deepEqual(matrixRuleProblems(DEFAULT_MATRIX), []);
});

test("bắt được dòng có hai P hoặc Auditor giữ A", () => {
  const m = [...DEFAULT_MATRIX];
  m[12] = "PACARXXRPI"; // dòng 13 cũ: Req và Prod. Op. cùng P
  m[17] = "IICRAXXRRA"; // dòng 18 cũ: Auditor A
  const out = matrixRuleProblems(m);
  assert.equal(out.length, 2);
  assert.match(out[0], /Dòng 13.*một P/);
  assert.match(out[1], /Dòng 18.*Auditor/);
});

test("Auditor R đứng ngay trước P", () => {
  assert.deepEqual(roles(5), ["SO:R", "LM:A", "AUD:R", "IAM:P"]); // dòng 6: thu hồi
  assert.deepEqual(roles(6), ["SO:R", "LM:A", "AUD:R", "IAM:P"]); // dòng 7: điều chuyển
  assert.deepEqual(roles(18), ["AUD:R", "SO:P", "CISO:R", "LM:A"]); // dòng 19: rà soát định kỳ
  assert.equal(roles(17).at(-1), "AUD:R"); // dòng 18: không có P thì Auditor đứng cuối
});

test("IAM không truy cập dữ liệu PII, account mở ở dòng 5", () => {
  for (const id of [13, 14]) assert.equal(letter(id, "IAM"), "X");
  assert.deepEqual(ticketType("pii_query").acts, [13, 4]);
  assert.deepEqual(ticketType("pii_export").acts, [14, 4]);
  assert.deepEqual(roles(4), ["IAM:P", "CISO:R"]);
});

test("ghi chú chỉ trỏ tới vai trò có thật", () => {
  for (const n of Object.values(MATRIX_NOTES)) for (const r of n.roles) assert.ok(ROLE_KEYS.includes(r));
});

test("IAM đọc dữ liệu định danh nhân viên (dòng 5, 6, 7), không đọc dữ liệu khách hàng (dòng 14, 15)", () => {
  for (const id of [4, 5, 6]) {
    assert.equal(letter(id, "IAM"), "P");
    assert.ok(MATRIX_NOTES[id].roles.includes("IAM"));
    assert.match(MATRIX_NOTES[id].text, /nhân viên/);
  }
  for (const id of [13, 14]) assert.match(ACTIVITIES[id].name, /khách hàng/);
});
