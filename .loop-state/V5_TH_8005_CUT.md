# V5 TH 20:05 cut — preview counts + Steward Execute warehouse

**Date:** 2026-08-29 ~20:00 ICT  
**Branch:** `feat/th-hitl-causal-flow` · PR #36 base `v5`  
**Do not merge. Do not t086. Do not restart cloudflared.**

**SHA:** `e269152` (counts+execute `c4984fc`, UI tsc `e269152`)  
**d086 stamp:** `<!-- d086-v5 th-hitl b9d11cf -->` · backend StartedAt `2026-08-29T12:52:07Z` healthy · frontend container not recreated (`2026-08-21T18:16:49Z`) · t086 + cloudflared StartedAt unchanged

## Landed

1. **Preview headlines = SQL COUNT over (table, ICT day)** via `preview_split_counts`.
   - `clean` = pass all approved/edited SQL-safe rules
   - `quarantine` = `scoped - clean`
   - Day `OR`s are parenthesized so they do not leak past `AND` rule predicates.
2. **GET `/hitl/sandbox/{run_id}`** no longer hardcodes `clean_rows: 0`. Reads `sandbox_preview_meta`.
3. **Preview persist cap `PREVIEW_ROW_CAP=50`** example rows only. Not SANDBOX_SAMPLE_CAP=3000 as warehouse.
4. **1B Steward Execute ON.** `POST /hitl/execute` and `/hitl/execute/{id}` work for Steward only (`hitl_write` + handler). Admin/Analyst/Viewer/Auditor → 403.
5. **`commit_warehouse_split`** writes **both** `clean.{table}` and `main.quarantine` (`rule_version_id='execute'`) for the scoped table+day. Counts_kind `warehouse`.
6. UI: preview pills until Execute; after Steward Execute, lineage uses **Clean Warehouse / Quarantine** committed counts.

## Did not land

- Day filter on `load_sandbox_rows` example pull (headlines are SQL).
- Per-rule exclusive assignment (a row can increment multiple rules).
- Frontend e2e Playwright / full `pnpm` typecheck (build for d086 if time).
- Chat-edit polish (sibling `prompt_intent` / `sandboxPreview`).

## SQL sketch

```sql
-- preview + execute counts (same predicates)
SELECT COUNT(*) FROM main.{table}
 WHERE (assigned_day_index = ? OR day_idx = ?
        OR CAST(source_ingestion_run_id AS VARCHAR) = ?);

SELECT COUNT(*) FROM main.{table}
 WHERE (day-clause) AND (expr1) AND (expr2);
-- quarantine = scoped - clean

-- execute persist
INSERT INTO clean.{table} BY NAME
SELECT * FROM main.{table} WHERE (day-clause) AND (pass_all);

INSERT INTO main.quarantine (...)
SELECT ... FROM main.{table} src WHERE (day-clause) AND NOT (pass_all);
```

## API fields

| Field | Preview (sandbox) | After Steward Execute |
|---|---|---|
| `clean_rows` / `quarantine_rows` | SQL preview | SQL warehouse (same numbers, committed) |
| `counts_kind` | `preview` | `warehouse` |
| `warehouse_clean_rows` | 0 | committed clean |
| `warehouse_quarantine_rows` | 0 | committed quarantine |
| `execute` | `off` | `on` |
| persist | ≤50 example Q rows | full clean.* + execute quarantine |

## UI strings

**Before Execute (preview)**  
EN: `Preview estimate (table + day): {C} clean · {Q} quarantined / {S} in-scope`  
EN pills: `Preview quarantine (N)` · `Preview clean (N)`  
EN: `Preview estimate for this table + day — not warehouse after Execute. Committed warehouse: Clean 0 · Quarantine 0.`  
EN button: `Execute warehouse (Steward)`  
VI: `Ước lượng xem trước (bảng + ngày)` · `Cách ly xem trước` · `Sạch xem trước` · `Execute kho (Steward)`  
VI: `Kho đã ghi: Sạch 0 · Cách ly 0.`

**After Steward Execute (warehouse)**  
EN pills: `Quarantine (N)` · `Clean Warehouse (N)`  
EN: `Warehouse after Execute (table + day): Clean {C} · Quarantine {Q}.`  
VI: `Khu Vực Cách Ly` · `Kho Dữ Liệu Sạch`  
VI: `Kho sau Execute (bảng + ngày): Sạch {C} · Cách ly {Q}.`

## Tests

`uv run pytest tests/test_sandbox_split.py` + governance unapproved execute: PASS.  
Fixture: day 10 / 2026-01-11 → clean 7 · quarantine 3 written to `clean.ev_telemetry` and execute quarantine.

## Deploy

d086: rsync `src/` bind-mount, restart `datatrust-dev-backend-1` only; frontend `docker cp` dist if built. No t086. No cloudflared.
