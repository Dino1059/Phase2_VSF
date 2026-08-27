# V5 overnight (2026-08-27) — battle-test FAIL fixes (not live-proven)

Branch: `v5-integration`. **PR (open, not merged):** https://github.com/AI20K-Build-Phase-Cohort-3/P-086/pull/27 → `v5`

**MERGE VERDICT: NO.** Do not merge PR #27 until both FAILs are re-proven on live d086. t086 untouched.

Seeded logins (username-only): `admin@datatrust.os` / `analyst@datatrust.os` / `viewer@datatrust.os`.

## This code pass (local)

| Item | Result | Evidence |
|---|---|---|
| FAIL 1 sandbox GET `main.quarantine` | **FIXED in code / not live-proven** | Sandbox sample is `load_sandbox_rows` from **`main.{table}`** (not WAP/`raw` LIMIT 3000). Pulls `WHERE NOT (rule)` + `battery_soc < 0` hint, then fills. SQL `BETWEEN` now evaluates in `safe_eval_rule`. GET still reads `main.quarantine WHERE snapshot_id=?`. Execute-off 403 unchanged. Tests: `test_load_sandbox_rows_includes_tail_soc_faults`, `test_between_rule_quarantines_negative_soc`, existing GET preview persist test. |
| FAIL 2 `/health` under Profiler | **FIXED in code / not live-proven** | Profiler `POST /datasets/.../profile` + chat tool executes run in `asyncio.to_thread`; default profile cap 3000; `/health` is sync + `health_fastpath` (no DuckDB). Master DuckDB `fetchdf` takes `_conn_lock`. WAL: still never delete `.db`. |
| Execute 403 (design) | **kept** | `POST /hitl/execute` still 403 execute-off. |
| t086 | **untouched** | No compose/image work on `/opt/datatrust-os`. |

## Why merge stays NO

Live d086 bind-mount + GET sandbox preview 200 with quarantine rows, and `/health` 200 while Profiler is `running`, are **not yet re-proven on this pass**. Code-only. N6=A needs that live evidence.

## Fixes (this SHA)

1. **Canonical sandbox sample** — `src/services/dataset_engine.py` `load_sandbox_rows`: query `main.ev_telemetry` (etc.) for rule violators so the 12 SOC<0 faults are in the 3000-cap sample. Persist still writes `main.quarantine` with `snapshot_id`.
2. **BETWEEN** — Ngan proposer rules (`battery_soc BETWEEN 0 AND 100`) used to fail-safe pass and write 0 quarantine even if faults were sampled.
3. **Profiler must not own the event loop** — `datasets.profile_dataset` offloaded; chat pipeline + missing-tool force-run offloaded; profile sample capped; health does not use DuckDB.

## Prior live numbers (pass 2, still the last live eval)

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

- Compose `datatrust-dev` 3001/8001. Bind-mount `./src:/app/src` then `docker compose -p datatrust-dev up -d --no-build --no-deps backend`.
- If WAL replay abort: stop `datatrust-dev-backend-1` only, delete **`.wal` only**, never `.db`.
- Disk tight: no image rebuild.

## Live re-check still required

```
POST /api/v1/hitl/sandbox  {dataset_key: ev_telemetry, sample_size: 3000}
GET  /api/v1/hitl/sandbox/{snapshot_id}  → 200, quarantine_rows>=1, execute=off
GET  /health while Profiler running → 200 within healthcheck timeout
```
