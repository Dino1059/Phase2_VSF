# V5 overnight (2026-08-27) — FAIL 1 + FAIL 2 live-proven on d086

Branch: `v5-integration` @ `6d933ff`. **PR (open, not merged):** https://github.com/AI20K-Build-Phase-Cohort-3/P-086/pull/27 → `v5`

**MERGE VERDICT: NO.** Do not merge PR #27 (explicit gate). FAIL 1 and FAIL 2 are live PASS on d086. t086 untouched.

Seeded logins (username-only): `admin@datatrust.os` / `analyst@datatrust.os` / `viewer@datatrust.os`.

## Live d086 (2026-08-27, dest `/opt/datatrust-os-dev`, compose `-p datatrust-dev`, :3001/:8001)

| Item | Result | Evidence |
|---|---|---|
| FAIL 1 GET `/hitl/sandbox/{id}` | **LIVE PASS** | After bind-mount src + backend restart: `POST /hitl/sandbox` 200 `quarantine_rows=17` `sampled_rows=2995` `execute=off`. `GET /api/v1/hitl/sandbox/sandbox:ev_telemetry:4ade8835747f` **200**, `quarantine_rows=17`, `n_items=17`, `execute=off`, `dataset_key=ev_telemetry`. Rows from **`main.quarantine`** (`snapshot_id`). |
| Execute-off 403 | **kept / live** | `POST /hitl/execute` 403 `Execute off: HITL approve is not execute.` |
| FAIL 2 `/health` under Profiler | **LIVE PASS** | `POST /datasets/ev_telemetry/profile?table=ev_telemetry&sample_size=8000` 200 in 0.078s while `/health` polls all 200 (max 0.002s). Container `datatrust-dev-backend-1` **healthy**. Fastpath `/health` 0.000s in logs (no DuckDB). |
| t086 | **untouched** | backend StartedAt `2026-08-25T08:32:58.54858376Z` (unchanged). |

d086 backend StartedAt after this pass: `2026-08-27T02:49:35.82974172Z` (restart only `datatrust-dev-backend-1`). Image not rebuilt.

### Warehouse note (why GET was 404 before inject)

Live `main.ev_telemetry` (~9.5k) and `raw.ev_telemetry` (86400) had **`battery_soc < 0` count = 0** (min ~26.1). Sandbox cannot persist quarantine rows that are not in the warehouse. Stopped **d086 backend only**, set **12** tail `main` + `raw` rows to `battery_soc=-12.5`, started backend. DuckDB opened clean (no WAL delete). Did **not** delete `.db`.

## Code (PR #27)

1. **`load_sandbox_rows`** — fault-hint (`battery_soc < 0`) **first** from `main.*` then `raw.*`; `WHERE NOT (rule)` cannot fill the 3000 cap and drop the 12 SOC faults. Persist still `main.quarantine` + `snapshot_id`. GET still `FROM main.quarantine WHERE snapshot_id=?`.
2. **`safe_eval_rule`** — SQL `BETWEEN` rewrite; `col >= a AND col <= b` (Ngan proposer form); numpy/NA coerced.
3. **Profiler off the event loop** — `POST /datasets/.../profile` + chat pipeline in `asyncio.to_thread`; sample cap 3000 (max 8000); sync `/health` + `health_fastpath` (no DuckDB).

SHA: `2acaba2` (first fix) + `6d933ff` (hint-first so over-range rows cannot crowd out SOC<0).

Tests: `rtk uv run pytest tests/test_sandbox_split.py tests/test_api.py::test_health_endpoint tests/test_api.py::test_health_stays_ok_while_worker_holds_gil_briefly` → **18 passed**.

## Prior live eval (unchanged this pass)

| Metric | Batch / realtime |
|---|---|
| Detection P/R/F1 | 0.684 / 0.929 / **0.788** (tp=13, fp=6, fn=1) |
| Location / time | 0.929 |
| RCA top-1 / top-3 | 0.929 |
| Hallucination FA | 0 |
| Unanswerable | 1.0 |
| Frozen RCA | **13/13** |

**INC_010 / F13:** manifest 5 charging / 0 trips vs parquet charging=1 trips=6. Leave documented.

## Host / dest (no t086, no backend image rebuild)

- Compose `datatrust-dev` 3001/8001. Bind-mount `./src:/app/src` then `docker compose -p datatrust-dev up -d --no-build --no-deps backend` (or `docker restart datatrust-dev-backend-1` after rsync).
- If WAL replay abort: stop `datatrust-dev-backend-1` only, delete **`.wal` only**, never `.db`.
- Disk tight: no image rebuild.
