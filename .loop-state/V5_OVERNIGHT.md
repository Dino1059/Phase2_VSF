# V5 overnight (2026-08-27)

Branch: `v5-integration` @ **`3a83bc1`**. **PR (open, not merged):** https://github.com/AI20K-Build-Phase-Cohort-3/P-086/pull/27 → `v5`

**MERGE VERDICT: NO.** N6=A still fails. HITL sandbox preview on d086 was not completed with an approved-rule run (queue empty). Frontend HTML still stamped `7070309` (one behind HEAD). Do not merge.

## P0 — d086-api 502 (fixed)

**Cause:** `datatrust-dev-backend-1` crash-loop (35 restarts, unhealthy). Native DuckDB **WAL replay abort** on `vingroup_pilot.db.wal` (413K, 00:58Z) after a bind-mount restart. Python never reached the WAL-delete handler in `src/db/connection.py` — process died in `WriteAheadLogReplayer`. Cloudflare 502 on `https://d086-api.w9.nu` (`/`, `/health`, `/docs`). Dest SHA file was already `3a83bc1` (not the stale `731c55c` note).

**Fix (no backend image rebuild, no t086):**
1. `docker stop datatrust-dev-backend-1` only.
2. Delete **`.wal` only** — keep `data_new/db/vingroup_pilot.db` (100M).
3. `docker compose -p datatrust-dev up -d --no-build --no-deps backend`

**Evidence after fix:**
- `GET https://d086-api.w9.nu/health` → **200** `{"status":"ok","app":"DataTrust OS",...}`
- `GET /` and `/docs` → **401** (auth), not 502
- Local `8001/health` 200; bind-mounts: `src`, `landing_data`, `eval`, `schemas`, `scripts`
- t086 StartedAt **unchanged:** backend `2026-08-25T08:32:58Z`, frontend `08:36:50Z`, cloudflared `2026-08-16T16:30:41Z`

## d086 frontend (already this era)

`https://d086.w9.nu` last-modified **Wed, 26 Aug 2026 22:24:04 GMT** (not Aug 21). HTML `<!-- d086-v5 7070309 -->`. One commit behind HEAD `3a83bc1` (ingestion empty-timeline guard is on bind-mounted `src`).

## HITL (not a 403 bug)

`POST /hitl/execute` **403** `"Execute off: HITL approve is not execute. Sandbox + authorize required."` is **design for every role including Admin**. Not CSRF/auth.

| Who | What |
|---|---|
| Missing JWT | **401** |
| Viewer POST | **403** read-only (role) |
| Admin execute | **403** execute-off (design) |
| Admin path | authorize + `POST /hitl/sandbox` + `GET /hitl/sandbox/{run_id}` on **`main.quarantine`** (`snapshot_id`), SandboxDiff. Never WAP `sandbox.*` |

UI on d086 Admin: Rules & HITL shows **Execute disabled · sandbox not run · quarantine=0**. Queue was empty this pass — **SandboxDiff preview not proven on live d086**. `7070309` authorize accepts `edited`. Viewer execute-off vs role-403: both OK.

## Eval scores (d086 Chrome + API)

LLM-judge **off**. 14 incidents. No “adapter TBD”.

| Metric | Realtime / batch |
|---|---|
| Detection P/R/F1 | 0.68 / 0.93 / **0.79** (tp=13, fn=1) |
| Location / time | 0.93 |
| RCA top-1 / top-3 | 0.93 |
| Hallucination FA | 0 |
| Unanswerable | 1.0 |
| Frozen RCA | **13/13** |

**INC_010 / F13:** known 13/14. Manifest: VF8VNF_0003 day 13 → 5 charging / 0 trips; parquet charging=1 trips=6. Shown on Eval vs GT panel. **Not cheap** (need landing parquet regen). Leave documented.

## Chrome smoke (`d086-battle`)

- Admin persona on `https://d086.w9.nu`
- `#/operations/eval`: numbers + INC_010 warning
- `#/workspace?dataset_key=ev_telemetry`: chat compose, Propose/Traces/HITL, profiler tables live after API recover
- Chat abort proven earlier (ABORT → EXECUTE)

## Commits on PR #27 this overnight

- `7070309` fix(hitl): Admin authorize accepts edited; execute-off is design
- `3a83bc1` fix(ingestion): empty timeline if `demo_ops.batch_run_log` missing

## Still open (blocks merge)

- HITL sandbox **preview** with approved rules + SandboxDiff on d086 (queue empty)
- Frontend stamp vs HEAD (`7070309` vs `3a83bc1`) — optional nginx refresh
- INC_010 F13 parquet mismatch
- N6=A: merge only after d086 battle-test **and** HITL sandbox actually works
