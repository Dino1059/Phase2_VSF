import { test } from "node:test";
import assert from "node:assert/strict";
import { fmtDur } from "@/lib/format";

test("fmtDur không bao giờ ra 60 phút / 24 giờ", () => {
  const MIN = 60_000;
  assert.equal(fmtDur(30_000), "30s");
  assert.equal(fmtDur(59.6 * MIN), "1h 0m");
  assert.equal(fmtDur(24 * 60 * MIN - 10_000), "1 ngày 0h");
  assert.equal(fmtDur(23 * 60 * MIN + 59.7 * MIN), "1 ngày 0h");
  assert.equal(fmtDur(-(2 * 60 + 5) * MIN), "2h 5m");
});
