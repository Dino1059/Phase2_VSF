# V5 TH ordered-cut audit — PR #36

**When:** 2026-08-29 ~20:26 ICT  
**Branch:** `feat/th-hitl-causal-flow` → **v5**  
**PR:** https://github.com/AI20K-Build-Phase-Cohort-3/P-086/pull/36  
**HEAD:** `afa9826` (feature `b73008a`, stamp `afa9826`)  
**Inspected:** git HEAD, PR commits, `src/` + `frontend/`, targeted pytest, live d086 — not memory.  
**Do not merge. Do not t086. Do not restart cloudflared.**  
**Overnight lock:** 08:40 AM ICT 29 Aug 2026 (not 20:40). This is the full ordered cut, not the 20:05 mini-cut.

Pre-fix tip was `deded2c`. Remaining ordered-cut GAPS closed in `b73008a`.

### d086 stamp (this cut)

- Frontend: `<!-- d086-v5 th-hitl b73008a -->` (`docker cp` dist; container StartedAt `2026-08-21T18:16:49Z`, not recreated)
- Backend StartedAt `2026-08-29T13:26:21Z` healthy (rsync `src/` bind-mount + restart `datatrust-dev-backend-1` only)
- Live preview `ev_telemetry` `2026-01-11`: **C=47439 Q=2 S=47441** `counts_kind=preview` warehouse **0/0** — not 3000/0
- GET `/hitl/sandbox/{snap}` **200** same COUNT; missing id **404**
- Analyst POST `/hitl/execute` **403** `HITL write is Data Steward only`
- t086 backend `2026-08-27T05:33:09Z` / frontend `05:33:40Z`. cloudflared `2026-08-16T16:30:41Z`. Untouched.

---

## 1. Chat = `(dataset_key, ICT calendar day as run_id)` — **PASS**

Workspace owns DB + day. History dropdown lists only that pair. ICT day **is** `run_id`.

| Check | Verdict | Evidence |
|---|---|---|
| Day idx 10 = `2026-01-11` = run_id | PASS | `tests/test_th_hitl_causal_flow.py:21-24`; `th_hitl_flow.py:13-24` |
| Workspace binds pair on URL | PASS | `AgentChatWorkspace.tsx:177-180` `bindAxis(datasetKey, calendarDay)` |
| Session list filters pair | PASS | `routes/__init__.py:1278-1280` `GET /chat/sessions?dataset_key=&calendar_day=`; `chatStore.ts:253-265` maps only returned sessions |
| Pair API test | PASS | `test_chat_sessions_api_filters_pair` / `test_chat_sessions_filter_by_pair` |
| Run Id chip = ICT day | PASS | `SourceIngestionRunFilter.tsx:166` `data-testid="run-id-chip"`; ingestion day click `dfe6abb` |
| URL day survives pipeline reset | PASS | `pipelineStore.resetPipeline` keeps `selectedDayIdx` / `sourceIngestionRunId` (`test_must_ui_still_binds_axis`) |
| Latest session follows pair | PASS | `test_latest_session_follows_table_day_pair` |

No remaining product GAP on this item.

---

## 2. Incident parent + Remember OFF + Rollback — **PASS**

| Check | Verdict | Evidence |
|---|---|---|
| Incident = (dataset, day, entity_id, primary rule) | PASS | `th_hitl_flow.py:670-718` `incident_stories`; `GET /hitl/incidents` `hitl.py:891-896`; copy `suspected` / `because` / `recommend` |
| Causal API test | PASS | `test_incident_stories_are_causal_not_signal_dump` |
| Quarantine fallback scoped to day | PASS (this cut) | `th_hitl_flow.py:723-738` `TRY_CAST` day_idx / assigned_day_index / `source_ingestion_run_id` |
| Remember key `(dataset_key, rule_id)` | PASS | PK `rule_memory` `th_hitl_flow.py:88-96` |
| Default **OFF** | PASS | Schema `remembered BOOLEAN DEFAULT FALSE`; UI `QualityRulesTab.tsx:241` empty `Set`; API `RememberRequest.remember: bool = False` `hitl.py:859`; `test_remember_request_defaults_off` |
| Change-mind expires memory only | PASS | `expire_memory` `th_hitl_flow.py:554-562`; `test_remember_and_expire_memory_only` |
| Rollback last clean rows | PASS | `rollback_last_clean` `th_hitl_flow.py:597-667`; `POST /hitl/rollback` `hitl.py:883-888`; UI `btn-rule-rollback`; `test_rollback_supersedes_clean_decision` |

---

## 3. Roles: Steward write / watch / Analyst propose / Steward Execute — **PASS**

Latest lock **1B Steward Execute ON** writes warehouse. Admin/Analyst execute **403**. Do not fight `15619dc` `.value`.

| Check | Verdict | Evidence |
|---|---|---|
| `hitl_write` Steward only | PASS | `auth.py:36-51` Admin/Analyst/Auditor lack `hitl_write`; Steward has it |
| Middleware HITL write 403 | PASS | `auth.py:313-317` `"HITL write is Data Steward only"`; `_REVIEW_MARKERS` includes approve/reject/edit/remember/rollback/confirm-patch/execute |
| Steward Execute JWT `.value` | PASS | `hitl.py:450-456` compare `UserRole.STEWARD.value` (`"Steward"`), not `str(enum)`; `test_steward_execute_uses_token_role_value_not_enum_str` |
| Admin/Analyst/Viewer Execute 403 | PASS | `_require_steward_execute`; `test_execute_off_is_design_not_csrf_or_auth`; d086 20:05 QA Admin/Analyst 403 |
| UI Execute warehouse Steward | PASS | `QualityRulesTab.tsx:638` `canHitlWrite`; chip `Execute warehouse (Steward)` |
| Analyst propose | PASS | Analyst `propose_rules`; HITL write hidden `!canHitlWrite` |
| Admin/Auditor watch | PASS | Admin has `review_rules` but not `hitl_write`; Auditor `review_rules` only |

**Remaining (not warehouse HITL):** Analyst still has `execute_transform` so chat `ChatInput.tsx:147-168` shows **Clean & Quarantine**. That is not `POST /hitl/execute`. Warehouse Execute stays 403.

---

## 4. Then: search-all, landing ingest, hide extra buttons — **PASS**

| Check | Verdict | Evidence |
|---|---|---|
| ⌘K → workspace `(table, day)` inspector | PASS | `Header.tsx:15,297,787` `searchHitWorkspacePath`; empty ⌘K `bindWs` + `location.search` (`test_then6_search_and_then8_hide_are_wired`) |
| `?tab=` opens inspector | PASS | `AgentChatWorkspace.tsx:183-187` |
| Live ingest → `landing.*` | PASS | item 7 |
| Chat Accept/Edit/Reject hidden | PASS | `AgentChatWorkspace.tsx:772` `hidden data-testid="chat-hitl-hidden"`; routes kept |
| HITL write on Rules tab | PASS | Approve/Remember/Rollback/Execute behind `canHitlWrite` |

---

## 5. Sandbox preview → Approve = rule; Execute = warehouse — **PASS** (gaps closed)

Never Approve→sandbox→Approve as write path. Preview = real SQL COUNT table+day **before** Approve. Execute writes clean+quarantine.

| Check | Verdict | Evidence |
|---|---|---|
| Preview headlines = SQL COUNT | PASS | `preview_split_counts` `th_hitl_flow.py:318-406`; parenthesized day OR; `counts_kind: preview`; warehouse 0 |
| Sample rows day-scoped | PASS (this cut) | `load_sandbox_rows(..., calendar_day, day_idx)` `dataset_engine.py:300-`; `hitl.py:628-629`; `chat_tools.py` preview path; `test_load_sandbox_rows_respects_table_day` |
| Preview before Approve | PASS | `QualityRulesTab.tsx:394-397` / batch `440-443`; `handleApprove` does not call sandbox/execute (`test_handle_sandbox_execute_calls_clean...`) |
| Approve stamps rule only | PASS | `approve_rule` `"quarantined_count": 0` `"execute": "off"` (`test_preview_before_approve_does_not_write_warehouse`) |
| Execute writes clean.* + quarantine | PASS | `commit_warehouse_split` `th_hitl_flow.py:409-531`; `counts_kind: warehouse`; fixture 7/3 `test_commit_warehouse_split_writes_clean_and_quarantine` |
| GET `/hitl/sandbox/{id}` meta-first | PASS (this cut) | `hitl.py:707-725` load meta **before** 404; empty quarantine + meta → **200**; missing both → 404; `test_get_sandbox_run_uses_meta_when_quarantine_empty` |
| GET warehouse fields from meta | PASS | `kind == "warehouse"` → `execute: on` and warehouse counts; preview still warehouse 0 |

**Honest (not a cut FAIL):** live d086 COUNT follows **which rules are approved** (1-of-3 → 39742/0; 8-rule → 0/39742). Pytest fixture 7/3 is not live. Per-rule exclusive assignment not landed.

---

## 6. Chat utterance is the task — **PASS**

| Check | Verdict | Evidence |
|---|---|---|
| `hi` / `what can you do?` = smalltalk, no profile/list | PASS | `deded2c`; `is_smalltalk_prompt` before ReAct `routes/__init__.py:738`; `test_greeting_*` / `test_capabilities_*` boom if tools run |
| Heuristic skips SYSTEM_PROMPT + Context JSON | PASS | `heuristic_user_task` `prompt_intent.py:158-169` skip `role==system` and `Context:` |
| History passed | PASS | `_llm_turns` `routes/__init__.py:615-630`; `react_engine.run(..., history=)` |
| `edit rule:` = sandbox preview only | PASS | `5d21b77`; `EDIT_RULE_ALLOWED_TOOLS={"sandbox_preview"}` `prompt_intent.py:21`; refuse profile/list `engine.py:677-691`; `test_edit_rule_chat_send_does_not_list_datasets` |
| Dataset Ready banner not the Task | PASS | `V5_TH_CHAT_HI_WHY.md`; ChatInput sends typed utterance |

---

## 7. Landing ingest → promote; seed landing-then-promote; VIN UNION — **PASS**

Names: **`vingroup_pilot`** (not vtaxi).

| Check | Verdict | Evidence |
|---|---|---|
| Live ingest writes `landing.*` only | PASS | `streaming_worker` / `telemetry.py` INSERT landing, not main (`test_then7_live_paths_do_not_insert_main`) |
| Promote `landing.*` → `main.*` | PASS | `POST /ingestion/promote` `ingestion.py:919-921`; Run All / day activate call `promote_landing_day` (≥3); no-op if empty `test_promote_landing_is_noop_without_landing` |
| Seed landing-then-promote | PASS | `seed.py` INSERT landing + `promote_landing_all`; no INSERT main fact tables (`test_leftover_seed_is_landing_then_promote`) |
| VIN search UNION landing | PASS | `algolia_search.py:271-274`; `test_leftover_vin_search_unions_landing` |
| Then-7 d086 smoke | PASS | `.loop-state/V5_TH_THEN_DONE.md` VIN landing=1 main=0 then promote |

---

## Pre-fix GAPS closed this turn

| GAP | Was | Now |
|---|---|---|
| GET `/hitl/sandbox/{id}` 404 when Q=0 | Quarantine lookup **before** meta (`hitl.py` old `:720`) | Meta-first; 200 with SQL COUNT headlines |
| Sample rows ignored day | `load_sandbox_rows` unscoped SELECT | Day clause on every sample SELECT; no unscoped `load_dataset` fallback when day set |
| Remember API default ON | `RememberRequest.remember = True` | `False` — product default OFF |

---

## Remaining after this cut (not merge-blocking; not 08:40 Must FAILs)

1. Live warehouse/preview COUNT ≠ pytest **7/3** — d086 this smoke **C=47439 Q=2 S=47441** (approved-rule set), not fixture 7/3.
2. Per-rule exclusive assignment (row can increment multiple rules) — never in this cut.
3. Analyst chat **Clean & Quarantine** chip (`execute_transform`) — not `POST /hitl/execute`.
4. **CI Hosted Probe** red (~2s billing). Sibling agent. Not a merge gate. **Do not merge.**
5. No t086 Playwright. Stamp live `<!-- d086-v5 th-hitl b73008a -->`.

---

## Tests

```
PYTEST_DUCKDB_PATH=data/datatrust_test_thcut.duckdb
uv run pytest tests/test_sandbox_split.py tests/test_th_hitl_causal_flow.py
```

**58 passed** (includes new meta-GET, day-scoped sample, remember-default-off).

---

## Out of scope (unchanged)

Ngân `fault_manifest`, Dũng benchmark, t086, AI-on-rejects, merge to `v5`/`main`.
