# V5 overnight (2026-08-27)

Branch: `v5-integration` (pushed). **PR (open, not merged):** https://github.com/AI20K-Build-Phase-Cohort-3/P-086/pull/27 → `v5`

N6=A: merge only when slice 1 + slice 2 complete, GT metrics scoring, HITL sandbox correct on canonical, d086 battle-tested. **Never t086.**

## Seeded identities (N5=A)

| Username | Role | Department label |
|---|---|---|
| `admin@datatrust.os` / `admin` | Admin | Operations |
| `analyst@datatrust.os` / `analyst` | Analyst | Fleet Analytics |
| `viewer@datatrust.os` / `viewer` | Viewer | Audit |
| `steward@datatrust.os` / `steward` | Steward | Data Quality (kept) |

Quick-switch in AuthModal. No new IAM. Reset stays Admin-only.

## Slice 1 (sandbox)

- Run sandbox: authorize + POST `/hitl/sandbox` + GET preview. **No** `hitlApi.execute` (403).
- Persist + preview on `main.quarantine` (`snapshot_id=sandbox:…`). SandboxDiff wired.
- d086 mapping: compose project **`datatrust-dev`** at `/opt/datatrust-os-dev`, host ports **3001/8001**. Tunnel is existing `datatrust-cloudflared` on **t086** compose — do not recreate. `d086.w9.nu` last-modified 21 Aug = stale `datatrust-dev-frontend`.

## Slice 2 (eval)

- `GET /api/v1/evaluation/gt` is an **adapter** over existing `GroundTruthMatcher` + `RCAGroundTruthMatcher` / frozen testset (same JSON `FrozenRCABenchmarkRunner` loads). No third BenchmarkHarness.
- Matcher now accepts Ngan `incidents[]`, canonical tables (`ev_telemetry` / `acn_charging`→`charging_sessions` / `ride_trips`→`trips`), `row_index`→`original_index`, `day_idx`. F17 in RCA specs.
- Local scores (LLM-judge **off**): realtime P/R/F1 **0.68 / 0.93 / 0.79**, tp=13/14, location+time 0.93, RCA top-1/top-3 0.93, hall=0, unanswerable 1.0, frozen RCA **13/13**.
- Memory already on this commit: `MemoryStore` + `SessionStateTracker` + `build_user_memory_context()` once at session-start in `POST /chat/send`. Not duplicated.
- **Blocker:** INC_010 F13 — manifest says 5 charging / 0 trips for `VF8VNF_0003` day 13; parquet has charging=1 trips=6 (extra sessions not in landing parquet).

## Deploy rule

- Slice 1 → d086 after sandbox-perfect (`docker compose -p datatrust-dev` only).
- Slice 2 on d086 only with real GT scores (no TBD panel).
- Confirm t086 `datatrust-os` StartedAt unchanged after any rebuild.
