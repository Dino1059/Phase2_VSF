# V5 TH ordered-cut next — exclusive assignment

**When:** 2026-08-29 ~21:30 ICT  
**Branch:** `feat/th-hitl-causal-flow` → **v5**  
**HEAD:** `3e72d76` (Steward chat → `/hitl/execute`) · docs `cd624bb` · product `149334e` · exclusive `9461a95`  
**PR:** https://github.com/AI20K-Build-Phase-Cohort-3/P-086/pull/36  
**Do not merge. Do not t086. Do not cloudflared.**  
**CI:** wait BTC only. Not a P-086 action.

Treat prior audit “1–7 PASS” as **unproven until this HEAD is live-smoked**. Pytest below is local. Live d086 smoked after `149334e` rsync.

## Proven this turn

`PYTEST_DUCKDB_PATH=data/datatrust_test_thcut.duckdb uv run pytest tests/test_sandbox_split.py tests/test_th_hitl_causal_flow.py tests/test_qa_t086_gates.py` → **80 passed** (+ cluster fallback test).

| Item | Verdict | Evidence |
|---|---|---|
| Exclusive per-rule COUNT | PASS (pytest) | `test_per_rule_counts_are_exclusive`: 11 scoped, C=7 Q=4, soc=3 speed=1, sum==Q |
| Incident = (dataset, day, entity, primary rule) | PASS (pytest + live) | Exclusive VIN+rule pytest; live d086 GET `/hitl/incidents?dataset_key=ev_telemetry&calendar_day=2026-01-11` → **7 unique** stories (entity+`cluster` while quarantine table empty). |
| Remember default OFF | PASS (code+pytest) | `RememberRequest.remember = False`; UI empty Set; `test_remember_request_defaults_off` |
| Rollback last clean rows | PASS (pytest) | row-id path `test_rollback_supersedes_clean_decision`; warehouse path `test_rollback_warehouse_moves_clean_rows` (7 clean → 0) |
| Steward warehouse Execute | PASS (pytest) | `test_commit_warehouse_split_writes_clean_and_quarantine`; Admin/Analyst 403 |
| Analyst Clean & Quarantine chip | PASS (source) | gated `canHitlWrite && canExecute`; `data-testid=chat-clean-chip-steward`; Analyst propose chips stay |
| Chat smalltalk / edit-rule / history | PASS (existing pytest) | `test_greeting_*` / `test_edit_rule_*` / `_llm_turns` unchanged this turn |
| Search-all / landing ingest / hide Accept-Edit-Reject | PASS (existing pytest) | `test_then6_search_and_then8_hide_are_wired` + Then-7 tests |

## Shipped this turn

Highest-value remaining product gap was **Must #3 exclusive assignment** (audit listed it as never landed). Also closed related Execute/Rollback + Analyst chip collision.

1. **Preview + warehouse quarantine:** first failing rule is primary. `per_rule_counts` no longer double-count a row. Execute writes `rule_id` = that primary, not `'execute'`.
2. **Incidents:** unique `(dataset_key, calendar_day, entity_id, primary_rule_id)` from quarantine (VIN/station), then incidents table only if that key is new. Ops Alerts passes current table+day into `GET /hitl/incidents`.
3. **Rollback after Steward Execute:** persist `warehouse_execute`; Rollback moves **those** `clean.{table}` day rows back to quarantine.
4. **Analyst chat chip:** “Clean & Quarantine” is Steward-only (`canHitlWrite`). Warehouse Execute remains Steward on Rules tab. Analyst still Propose.

## Live d086 (this cut)

- Backend StartedAt **`2026-08-29T14:45:36Z`** healthy. Frontend stamp `<!-- d086-v5 th-hitl 9461a95 -->` (container StartedAt `2026-08-21T18:16:49Z`, not recreated).
- t086 backend `2026-08-27T05:33:09Z` / frontend `05:33:40Z`. cloudflared `2026-08-16T16:30:41Z`. Untouched.
- Analyst `POST /hitl/execute` **403**. Day-count `ev_telemetry` `2026-01-11` = **47441**.
- Incidents **7 unique** (entity, cluster). Exclusive VIN+primary-rule rows appear after Steward Execute writes quarantine `rule_id`.

## Still open (product)

- Live COUNT follows **which rules are approved** (not pytest fixture 7/3).
- Exclusive VIN+primary-rule Alerts need Steward Execute so quarantine has `rule_id` (now cluster while Q table empty).
- No t086 Playwright. No merge.

## CI — wait BTC only

Self-hosted Quality Gate is **BTC (organizers)**. Do not hunt vm-runner / eph-vmrunner / hosted billing. Hosted Probe is dispatch-only. Not a P-086 action.

## Out of scope

Ngân `fault_manifest`, Dũng benchmark, t086, AI-on-rejects, merge to `v5`/`main`.

---

# Append — Steward chat warehouse execute (2026-08-29 ~21:50 ICT)

**HEAD product:** `3e72d76` · stamp `<!-- d086-v5 th-hitl 3e72d76 -->`  
**Steward chat now hits `POST /hitl/execute`:** **YES**

## Shipped

Steward chat **Clean & Quarantine** chip (`data-testid=chat-clean-chip-steward`) calls `hitlApi.executeWarehouse` — same `POST /hitl/execute` path as Rules tab **Execute warehouse (Steward)**. No more `executePrompt('clean database')`. Preview-before-approve unchanged. Chip still `canHitlWrite && canExecute`. Analyst execute **403**.

## Proven

`PYTEST_DUCKDB_PATH=data/datatrust_test_thcut.duckdb uv run pytest tests/test_sandbox_split.py tests/test_th_hitl_causal_flow.py tests/test_qa_t086_gates.py` → **82 passed**. `pnpm exec tsc --noEmit` clean.

| Item | Verdict | Evidence |
|---|---|---|
| Chat Clean → warehouse execute | PASS (source) | `handleWarehouseExecute` + `hitlApi.executeWarehouse`; chip onClick has no `executePrompt` / `clean database` |
| Analyst `POST /hitl/execute` | PASS (pytest + live) | `test_analyst_warehouse_execute_is_403`; d086 Analyst **403** `HITL write is Data Steward only` |
| Steward gate | PASS (live) | missing-ds execute is **403 not-approved**, not role-deny |
| Preview before approve | PASS | `hitl-preview-before-approve` still in Rules tab |

## Live d086 (this append)

- Backend StartedAt **`2026-08-29T14:45:36Z`** healthy (rsync `src/` bind-mount, **no restart** — UI-only).
- Frontend stamp `<!-- d086-v5 th-hitl 3e72d76 -->` (`docker cp` dist; container StartedAt `2026-08-21T18:16:49Z`, not recreated). Public `https://d086.w9.nu/` **200**.
- t086 backend `2026-08-27T05:33:09Z` / frontend `05:33:40Z`. cloudflared `2026-08-16T16:30:41Z`. Untouched.
- Day-count `ev_telemetry` `2026-01-11` = **47441**.
- Did **not** Steward-execute live warehouse (no write). Chip path is source+API; Analyst 403 proved.

**Do not merge. Do not t086. CI wait BTC only.**
