# Implementation notes

## 2026-08-19 — Production reset: data_new + Algolia

- `POST /api/v1/system/reset-all` now: wipe runtime tables + `messages`, delete `uploaded_%`, purge `data/uploads`, reload warehouse from `data_new/vingroup_faulty_pilot_dataset` on the live DuckDB connection, `clear_index()` + `seed_all_entities()`.
- Ingest accepts `con=` so reset does not open a second DuckDB lock.
- Sidebar "uploaded" list is only `uploaded_*` keys (was almost the whole registry).
- Live reset: telemetry 86400, charging 1513, trips 10382, faults 2079; Algolia cleared+31 seeded; search `uploaded` = 0; HITL empty then demo proposes `vingroup_pilot__R1_A1`.

## 2026-08-19 — Live QA: uploaded HITL / traces / wrong dataset

- C1 ghost card profiled `vgreen_charging_stations` because `normalizeDatasetKey` stripped `uploaded_` → bundled `vingroup_pilot` DuckDB. Keep uploaded keys; drop local profile fallback.
- Chat 99% / `unknown` dtypes: formatter read `dtype`/`health_score` (missing). Use `data_type` / measured health or `—`.
- HITL empty: rule ids `R1_A1` collided globally. Namespace `{dataset}__R1_A1`, persist `proposed` + `dataset_key`.
- Ghost `telemetry_coverage` / `accel_z >= 0`: skip signed physical cols and coverage/flag constants.
- Triple YOU prompt: bootstrap skips if history already has proposals.
- Leftover `vietnam_trips_dirty` list: only append when user asked to list datasets.
- Traces FINISH-only: truncated JSON failed DuckDB JSON insert. `json_preview()` stores valid JSON; React keys by index+action not `step_index`.
- LLM often FINISHed after profile. `missing_requested_tools()` runs `propose_quality_rules` if the prompt asked for rules. HITL now gets `uploaded_*__R1_A1`.
- Chrome 9222: profile dtypes STRING/FLOAT; HITL 1 rule `soc_pct >= 0`; Approve → 1 Approved, nothing cleaned. Profiler shows telemetry 10 cols, not vgreen.

## 2026-08-19 — ReAct loop: remaining PLAN P0

- `_log_trace`: empty thought, actor_kind from action.
- Chat WS `agent.trace` is summary-only.
- Upload proposal = `HITL_PREFIX` / profile+propose; RuleProposalCard sends session+dataset, no Accept & Execute.
- `DATATRUST_DEMO_SEED` gates taxi seed. Domain names tagged `(DEMO)`.
- `schemas/workflow-event.schema.json` (PLAN §9). GET `/traces` omits thought unless `include_thought=1`.

## 2026-08-19 — Wave 6a honesty pass + PLAN lock

- PLAN.md: §14.4/16.3/16.4/19.5/27.1 + Wave 6a. Grill lock: Q1C Q2B Q3C Q4A Q5 A then B.
- Traces: no synthesis; map `tool_name`/`tokens_used`/`observation`; WS `agent.trace`; jump-to-chat uses `.chat-stream`.
- HITL queue filter `?dataset_key=`; `quality_rules.dataset_key`.
- New Chat: VinGroup live demo, JSONL replay, upload. Auto-run stops at HITL.
- Actor labels: Orchestrator / L1–L4 / C1 / Steward. No 99% health default.

## 2026-08-19 — Grok AI log (request + response only)

- Added `.grok/hooks/ai-log.json`: `UserPromptSubmit` + `Stop` only (no `PreToolUse`/`PostToolUse`).
- `scripts/log_hook.py --tool=grok` writes prompt + `lastAssistantMessage`; drops tool events, thoughts, subagents, Stop continuations, and session-end Stop.
- Pre-push hook already submits `.ai-log/session.jsonl`. Trust project hooks once via `/hooks-trust`.

## 2026-08-15 — Upload session and dataset profiling

- Upload declarations now use the stable message ID `upload:{dataset_key}` and session `dataset:{dataset_key}`. Re-uploading the same logical dataset replaces the existing declaration instead of creating another chat row.
- Selecting an uploaded dataset runs the real profiling endpoint with a 50,000-row sample before the pipeline bootstrap starts.
- The chat stream reports profiling start, completion, and API failure; no profile/demo fallback was added.
- Verification: backend Python syntax check and frontend TypeScript/build pass.

## 2026-08-20 — Happy/unhappy demo switch (data_new only)

- `/` now redirects to Workspace `story=happy`. `/landing` stays marketing; 99.8% RCA tile removed (172 / 8 OPEN / 60 VIN).
- Real switch: `POST /api/v1/system/demo-snapshot?mode=happy|unhappy`.
  - happy = ingest `data_new/vingroup_pilot_dataset` (clean CSVs, no fault_manifest). Clears live incidents/rules/quarantine.
  - unhappy = ingest `data_new/vingroup_faulty_pilot_dataset` and restore the 8 OPEN fused incidents from `fixtures/demo/unhappy_incidents.json` if the queue is empty.
- Do not treat `raw.datasets.fault_injected=False` as Happy — those rows can still point at nested faulty paths.
- Gold RCA seed removed from IncidentService startup and system reset (eval stays on /evaluation).
- DOMAIN_LIST / Operations / Overview steward queue use measured 86400 / 1331 / 10382 and 172 / 131 / 8 / 0. No Kafka / 1.2B / AGENT_HEALTH ms.
- HITL: Approve stays; Execute disabled; sandbox not run; quarantine=0.
- Batch window labeled 2026-01-01 → 2026-01-15. Same detectors, different ingress. Not a live stream.
- Hollow `charging_rate_kw` / `fault_code` dropped from the vinfast_bms view (they were always NULL).

## 2026-08-20 — Propose traces beat missing (under-count)

- Live GET `/traces/dataset:vingroup_pilot` had Profile done + two nameless `running` rows. Chat had a Propose chip; HITL had 3 rules. Frontend drops rows without action/tool_name → MEASURED STEPS 1.
- Cause: Gemini/OpenAI tool_calls nest `function.name`. Engine read `tc.get("name")` → `""`, logged `Now: running tool…`, then session_id+step_index upsert clobbered a later Propose beat. `missing_requested_tools` was tested but not implemented, so FINISH-after-profile also skipped the write.
- Fix: unwrap nested tool_calls; skip empty/FINISH trace writes; upsert by tool_name; after chat run, force+log missing profile/propose.

## 2026-08-20 — Duplicate Propose traces beat (over-count)

- Live click on 7c40468: MEASURED STEPS 3 = Profile + Propose + Propose (same 3 rules).
- Cause: chat/send `missing_requested_tools` force-ran Propose after the LLM already persisted a named Propose beat (executed_so_far missed the exact name, or a prior Propose row already existed). Re-log of executed tools could also double if the beat check was exact-string only.
- Fix: skip force-run and re-log when `_session_has_tool_beat` finds tool_name/action propose_quality_rules (case/alias). Profile-only FINISH still force-runs Propose once. Do not remove missing_requested_tools.

## 2026-08-20 — Right-panel tabs stay mounted

- Workspace remounted Profiler/Traces/Rules/Split on tab click (`rightTab === &&`) and unmounted the aside on collapse (`rightPanelOpen &&`). That wiped Unhappy 172/8, Happy 99.1, STEPS, HITL, split counts.
- Fix: keep all four tabs mounted (`hidden={rightTab !== …}`); collapse via CSS width/transform. Tab onClick is only `setRightTab` — no loadSnapshot / story reset.

## 2026-08-20 — Tab round-trip: duplicate Propose + stale Rules queue

- Live after keep-mounted: STEPS 2 (Profile + Propose) drifted to 3 after Profiler→Rules→Split→Traces. Duplicate Propose beat (842ms, "3 rules"). Rules header "0 Proposed / 0 Approved" with 2 pending cards vs trail 3 rules.
- Cause (1): Unhappy `forceLive` stripped `dt-hitl-boot` and React StrictMode remounted the workspace, so bootstrap POSTed chat/send a second time. LLM re-executed Propose. `missing_requested_tools` only skipped the force-run, not the engine tool call. Tab show itself is GET-only; the extra beat landed while the steward was clicking tabs.
- Cause (2): QualityRulesTab now mounts hidden at boot, `hitlApi.queue` returns empty, never refetches. Propose writes status `pending`; header counted only `=== 'proposed'`.
- Fix: module-level `hitlBootsInFlight` (sync, before send); keep bootKey including story/demo; engine `_skip_duplicate_propose` skips execute+log when a Propose beat exists. Rules GET-refetch on `active`, `datatrust:agent-trace`, and 2s poll. Header counts pending/proposed/draft. Keep-mounted `hidden=` stays. Tab onClick still only `setRightTab`.

## 2026-08-20 — Unhappy Profiler stuck Not measured (hidden-mount hold)

- Hidden-mounted Profiler fetched once (Happy / empty). `holdUnhappyHealth` stayed true until `warehouse_*` > 0; profile `data_health_score=None` mapped to "Not measured" instead of Critical. Banner already had measured SoC<0 / OPEN.
- Fix: snapshot event + `dt-warehouse` overlay carry DuckDB counts; hold releases when faults arrive; KPI shows `— · Critical · SoC<0 = N · OPEN = M`. Happy still 99.1 Excellent when warehouse is clean. No 99.1 flash on Unhappy.
- Traces Found: stored `health 99.1` is sample leakage. Overlay/warehouse faults → omit sample %, say Critical + counts. AgentTracesTab / keep-mounted / STEPS 2 / stop-at-HITL untouched.

## 2026-08-25 — FaultCorrelationEngine (Phase 1 & 2)

- Phase 1 (Model Extensions):
  - `Signal`: Added optional `source_table: Optional[str] = None` and `violation_direction: Optional[str] = None`.
  - `Incident`: Added `correlation_key: Optional[str] = None`, `occurrence_count: int = 1`, and `representative_signal_ids: List[str] = Field(default_factory=list)`.
- Phase 2 (FaultCorrelationEngine Core):
  - Created `src/reliability/fusion/correlation.py` with `FaultCorrelationEngine`.
  - Computes deterministic SHA-256 hash `correlation_key` based on `(project_id, source_table, detector, signal_type, metric_or_relationship, violation_direction)`.
  - Groups signals strictly by `correlation_key` into 1 Incident per group, populating `occurrence_count`, top-3 `representative_signal_ids`, max severity, entity union, and evidence references.
  - Added export to `src/reliability/fusion/__init__.py`.
  - Created `tests/reliability/test_fault_correlation.py` covering 5 key scenarios (100 signals single key compression, multiple rules separation, mixed signals, empty signals, missing optional fields backward compatibility).
- Verification: 67/67 tests passed in `tests/reliability/`.

