# V5 leftovers (2026-08-27) — closed after PR #27 merge

Branch: `fix/v5-leftovers` @ `4179722` → `v5` (merge SHA `f427f0fe`, prior head `09f275a`).
**t086 untouched / not deployed.** Seeded logins: `admin@datatrust.os` / `analyst@datatrust.os` / `viewer@datatrust.os`.

## Leftovers

| Leftover | Status | Fix | Evidence |
|---|---|---|---|
| INC_010 F13 manifest vs parquet | **done** | Landing parquet now 5 charging / 0 trips for `VF8VNF_0003` day 13; manifest `charging_sessions=5` `completed_trips=0`; generator always pads + strips trips; `_gt_blockers` compares those counts. | Local + live `GET /evaluation/gt` **blockers `[]`**, detection tp=14 fn=0 F1=0.8, frozen RCA 13/13. |
| d086 SOC `-12.5` hack (12 tail rows) | **done** | Re-ingested warehouse from landing parquet SoT (1 labeled `battery_soc=-12.5`). No 12-row inject. Code still pulls `battery_soc < 0` before sample cap. | Seed: main.ev_telemetry 86400, charging 1344, trips 10376. Sandbox GET `sandbox:ev_telemetry:a5611cb63a76` **200**, `quarantine_rows=1`, `before.battery_soc=-12.5` (parquet INC_001, not tail hack). |
| 10k chat chip | **done** | Chip already `k/10k`. ChatRequest max 80k so cap can fire. Engine keeps prompt word count (no longer zeros tokens). | Live `POST /chat/send` session `leftover-10k-b`: `total_tokens=328` in HTTP + history metadata. Cap session `leftover-10k-cap-b`: **`status=token_budget_exceeded`**, tokens=10813, body `Stopped: 10k token cap (memory block counted).` Frontend stamp `<!-- d086-v5 f92793c leftovers -->`. |
| GET `/api/v1/memory` 404 | **done** | `GET /api/v1/memory` + `/stats` mounted before `/{user_id}`. Session-start inject already on `POST /chat/send`. | Unauth **401**. Admin **200** `{module:memory,user_id:usr_admin_01}`. `/stats` **200**. |
| t086 | **untouched** | — | backend StartedAt `2026-08-25T08:32:58.54858376Z`, frontend `2026-08-25T08:36:50.16998388Z`. Public t086 200. |

## Live d086

dest `/opt/datatrust-os-dev`, compose `-p datatrust-dev`, :3001/:8001. **No backend image rebuild.** Bind-mount `./src` + `./landing_data`. Frontend `docker cp` of `frontend/dist`. Public `https://d086.w9.nu/` last-modified **Thu, 27 Aug 2026 03:18:31 GMT**. d086 backend StartedAt `2026-08-27T03:25:23Z` then restart for 10k cap; healthy. Disk ~1.8G free.

Eval (live): detection P/R/F1 **0.667 / 1.0 / 0.8** (tp=14, fp=7, fn=0). Location/time 1.0. RCA 14/14. Frozen 13/13. LLM-judge off.

## Still blocked

None of the four leftovers. Do not deploy t086.

## Host / dest (no t086, no backend image rebuild)

- Compose `datatrust-dev` 3001/8001. Bind-mount `./src:/app/src`. Seed with existing image: stop `datatrust-dev-backend-1`, `docker run --rm --volumes-from ... --entrypoint /app/.venv/bin/python datatrust-dev-backend -c 'from src.db.seed import seed_database; seed_database()'`, start backend.
- If WAL replay abort: stop `datatrust-dev-backend-1` only, delete **`.wal` only**, never `.db`.
- Disk tight: no image rebuild.
