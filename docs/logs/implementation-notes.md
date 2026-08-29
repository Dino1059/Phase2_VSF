# DataTrust OS v5 Operational Trust Console — Technical Implementation Notes & Developer Log

> **Target Audience:** Developers, Co-workers, and Future AI Agent Sessions  
> **Last Updated:** 2026-08-29

**2026-08-30 TH+Huyen merge:** HITL causal flow + Remember default ON (replay warehouse Execute). Huyen dashboard/60fps/stewardLabels kept. **LLM toggle kept** (grill 9A) — do not force LLM ON.

**2026-08-29 TH exclusive assignment:** Preview `per_rule_counts` and warehouse quarantine use first-failing primary rule (sum == Q). Incidents = unique `(dataset, day, entity_id, primary_rule)`. Warehouse Execute persists `warehouse_execute` so Rollback moves `clean.*` day rows back. Analyst chat Clean & Quarantine chip gated `canHitlWrite` (Steward warehouse Execute stays on Rules tab).

**2026-08-29 Steward Execute 403:** `RoleMiddleware` stored `UserRole` enum; `_require_steward_execute` used `str(role)` which is `"UserRole.STEWARD"` on Python 3.10, not JWT `"Steward"`. Compare `UserRole.STEWARD.value` (token role); middleware stores `.value`. Live d086 C=0 Q=39742 is COUNT (8 approved rules), not pytest 7/3. GET `/hitl/sandbox/{id}` 404 when preview COUNT writes no `main.quarantine` rows — not same-file one-liner.

**2026-08-29 TH chat/sandbox:** Heuristic matched `"dataset"` in Context JSON `dataset_key`, so edit-rule got the 4-dataset canned bubble; traces 10/150s were AgentTracesTab session-sum (profile/list/Algolia under DuckDB lock), not that bubble. Fix: match user task not Context JSON; edit-rule allowlist = `sandbox_preview` only; Preview (COUNT+sample, no write) before Approve; GET warehouse_clean_rows stays 0 (execute-off). e3b0c442 = SHA-256(""); VF8VNF_0001 is VIN used as row id.

**2026-08-29 Thanh+Huyền Then 6–8:** Search-all jumps to workspace `?tab=` with current `(dataset_key, day)`. `POST /ingestion/promote` no-ops when `landing.*` empty; Run All + day activate call it. Chat HITL Accept/Edit/Reject hidden; Rules tab owns write. Ops routes kept.

**2026-08-29 Sidebar Tactile Hover Shift Effect:** Added micro-interaction feedback on Sidebar menu items (`.menu-item`) and dataset shortcut pills (`.shortcut-item`). On hover, items shift smoothly to the right (`transform: translateX(4px)`) with icon scale (`scale(1.06)`) using GPU composited easing (`160ms cubic-bezier(0.16, 1, 0.3, 1)`), providing tactile, responsive feedback.

**2026-08-29 Executive Dashboard Typography & Layout Harmonization:** Unified Executive Dashboard styling with the clean standard of Data Ingestion: 1) Added structured page header (`.dash-page-header`) matching Data Ingestion header layout (`h1` title + subtitle + icon). 2) Scaled all typography up by ~15% (Page Title `26px`, Subtitle `15px`, Panel Headers `23px`, KPI values `37px`, KPI titles `14px`, badges `14px`, code `15px`, table and card bodies `15px`) for enhanced legibility and visual hierarchy.

**2026-08-29 Chat Stream Minimalist Polish — Clean Bubbles & Subdued User Theme:** Removed all clutter from chat messages (header bars, timestamps, "YOU", "ORCHESTRATOR AGENT" titles, and token context strips). Styled User questions as right-aligned bubbles with balanced padding (`16px 20px` matching AI message box exactly), zero-margin paragraphs, subtle grayish tint (`var(--pill-bg)`), max 2/3 width, and auto-scaling. Added subtle relative hover timestamp (e.g. `6 days ago`, `vừa xong`) that smoothly fades in directly below the user bubble on mouse hover. AI responses display clean markdown cards.

**2026-08-29 Frontend 60FPS Performance Polish (GPU Layer & Transition Tuning):** Eliminated UI stutter/jank when clicking New Agent Chat textarea and Sidebar navigation items. 1) Isolated `.dash-sidebar`, `.new-chat-composer`, and `.chat-input-bar` onto dedicated GPU compositing layers using `transform: translateZ(0)` and `contain: layout paint`. 2) Replaced layout-thrashing `transition: all` rules across menu items, shortcuts, and inputs with GPU-friendly transitions (`background-color`, `color`, `border-color`, `opacity`). 3) Stabilized New Chat route navigation with idempotent `?new=1` and memoized `NewChatLanding` event handlers.

**2026-08-27 HITL buttons missing:** Analyst can Propose (chat) but not `review_rules`, so Approve / Edit / Reject / Approve All were omitted with no explanation. Fix: subscribe to `user.role` via `roleCan()`, put Approve All next to the Proposed filter, show `hitl-role-gate` + Switch persona when 10 Proposed and the chip is Analyst/Viewer. API still 403 for Analyst. t086 untouched.

**2026-08-27 Approve All 504:** Workspace `Approve All` fired `Promise.all` of N `POST /hitl/approve` calls; each loaded the full table under the DuckDB singleton lock and Cloudflare returned 504 / WS 524. Fix: one `rulesApi.batchApprove` → `POST /rules/batch-approve` as a single status UPDATE (execute-off, `total_quarantined: 0`), quarantine sample cap 3000, HITL approve off the event loop, HITL poll 8s and skip when hidden. t086 untouched.

**2026-08-27 Run All hang:** Workspace `ev_telemetry` listed `clean.*` / `quarantine.*`. L1 skipped (“No signal config”), Propose re-ran detect + unsampled profile and never finished (0 HITL rules). Fix: `pipeline_target_tables` (canonical `main` only), no nested detect, LLM propose timeout → Ngan/heuristic rules, skip-trace inserts removed. `resolve_trace_rows` now drops stale `anomaly_detect` skip beats when real detect/propose rows exist. Live d086: Run All 66s → HITL 22 (`soc_range`, battery rules); traces hide `clean.trips`. Playwright **20 PASS / 0 FAIL**. t086 untouched.  
> **Pytest Gate:** 125 / 125 Tests Passing (`54.34s`)  
> **Git Rule Constraint:** Commit locally; DO NOT execute `git push` unless explicitly ordered by user.

---

## 1. Project Context & Objectives (DATA-02)

DataTrust OS v5 Operational Trust Console is an autonomous AI data governance system built for the VinGroup enterprise ecosystem (VinFast EVs, Xanh SM Ride-Hailing, V-GREEN Charging Infrastructure, and Vietnamese Customer Feedback).

### Key Architecture Components:
1. **Single Model Enforcement (`src/services/llm.py`)**: Uses strictly `gemma-4-26b-a4b-it` with 60s timeout and 3 exponential backoff retries.
2. **Native Tool Calling (`src/api/routes.py`)**: Passes `GOVERNANCE_TOOLS` schema to Google AI Studio API for native function calls (`profile_dataset`, `detect_anomalies`, `propose_quality_rules`, `diagnose_root_cause`, `clean_database`, `list_datasets`).
3. **VinGroup 4-Domain Datasets (`data/vingroup/` & `data/vingroup_real/`)**: Standardized datasets covering EV Telemetry, V-GREEN Chargers, Xanh SM Trips, and Vietnamese Feedback.
4. **Vietnamese NLP Aspect Extractor (`src/services/vietnamese_nlp.py`)**: Normalizes teen code (`"ko sac dc"`, `"app lag vl"`), extracts aspect entities (`Location`, `Component`), and cross-validates with V-GREEN telemetry logs.
5. **Composite Anomaly Scoring (`src/tools/anomaly.py`)**: $S_{composite} = w_1 \cdot \text{Sigmoid}(Z_{robust}) + w_2 \cdot S_{isolation\_forest}$.
6. **Clean DB Creation Pipeline**: Evaluates approved rules, creates Clean DB + Quarantine table, and generates SHA-256 cryptographic lineage hashes.

---

## 2. API Endpoints & Multi-Agent Operations

### Key Routes in `src/api/routes.py`:
- `POST /api/v1/chat/send`: Main chat endpoint. Parses commands, invokes `gemma-4-26b-a4b-it` tool calling, routes execution, broadcasts WebSocket updates, and stores messages in SQLite `data/conversations.db`.
- `GET /api/v1/chat/sessions`: Lists active chat sessions.
- `GET /api/v1/chat/history`: Fetches chat history for a session.
- `POST /api/v1/datasets/upload`: Uploads CSV/Parquet datasets and registers them dynamically.
- `GET /v3`: Serves compiled React + Vite + Tailwind frontend (`src/static_v3/index.html`).

---

## 3. Dataset Registry & Schemas (`src/config.py`)

Registered keys in `dataset_registry`:
- `vinfast_ev_telemetry_dirty`: `data/vingroup/vinfast_ev_telemetry_dirty.csv`
- `vgreen_charging_stations_dirty`: `data/vingroup/vgreen_charging_stations_dirty.csv`
- `xanh_sm_trips_dirty`: `data/vingroup/xanh_sm_trips_dirty.csv`
- `xanh_sm_customer_feedback_dirty`: `data/vingroup/xanh_sm_customer_feedback_dirty.csv`
- `real_vinfast_ev_telemetry`: `data/vingroup_real/real_vinfast_ev_telemetry.csv`
- `real_vgreen_charging_stations`: `data/vingroup_real/real_vgreen_charging_stations.csv`
- `real_xanh_sm_trips`: `data/vingroup_real/real_xanh_sm_trips.csv`
- `real_xanh_sm_customer_feedback`: `data/vingroup_real/real_xanh_sm_customer_feedback.csv`

---

## 4. Key Scripts & Tools

- `scripts/generate_vingroup_dataset.py`: Generates 4 synthetic VinGroup test datasets + ground-truth fault manifest (`vingroup_fault_manifest.json` with 123 fault entries across 9 fault families).
- `scripts/fetch_real_public_datasets.py`: Ingests real public datasets (ST-EVCDP, UIT-VSFC, Telemetry, Ride Hailing).
- `scripts/ingest_vingroup_real_data.py`: VinGroup Domain Schema Mapper converting raw public datasets to enterprise VinGroup schemas.

---

## 5. Verification & Test Suite

Run unit & integration tests using:
```bash
.venv/bin/python -m pytest tests/ -v
```
- **Total Tests**: 125 Passed cleanly.
- **Coverage**:
  - `tests/test_api.py`: FastAPI endpoints & tool routing.
  - `tests/test_vingroup.py`: VinGroup datasets, NLP aspect extractor, and composite anomaly scoring.
  - `tests/test_real_public_ingestion.py`: Real public dataset ingestion & schema mapping.

---

## 6. Guidelines for Future Agent Sessions & Co-workers

1. **Model Requirement**: Always use `gemma-4-26b-a4b-it` in `GoogleAIStudioLLM` with 60s timeout per call. Do NOT add model fallbacks.
2. **Git Rule**: Do NOT execute `git push` automatically. Always stage and commit changes locally (`git commit -m "..."`), and wait for the user to explicitly command "push".
3. **Pytest Gate**: Always run `.venv/bin/python -m pytest tests/ -v` to verify zero regressions before declaring task completion.

---

## 7. Sprint 2 (2026-08-09) — Vietnamese NLP Aspect Extractor & V-GREEN Cross-Validation (P0, Trần Tiến Dũng)

**Ticket:** `[P0][Sprint 1][Dũng] Vietnamese NLP Aspect Extractor & Teen-code Normalizer from Customer Feedback Reviews`

### What changed
- **`src/services/vietnamese_nlp.py`**
  - Added `CrossValidationResult` dataclass, `STATION_TEMP_THRESHOLD_C = 85.5`, and `STATION_LOCATION_ALIASES` (maps free-text feedback locations — `"landmark 81"`, `"royal city"`, `"vincom ba trieu"`, `"ocean park"` — to V-GREEN `station_id`).
  - Added `resolve_station_id(location)`: resolves a feedback `Aspect.location` string to a known station via exact/substring alias match.
  - Added `cross_validate_with_station_logs(result, station_logs, threshold_c=None)`: takes an `NLPResult`, filters its `charger`-component aspects, resolves the station, and checks `vgreen_charging_stations_dirty.csv` rows for that station against the 85.5°C thermal threshold. Returns whether the complaint is corroborated by a real hardware fault (`confirmed_hardware_fault`), the max observed temp, and matching evidence rows.
  - Extended `compute_severity()` high-severity keywords with `"ngắt điện"` (sudden power cut) — present verbatim in real feedback text but previously unmatched (only `"mất điện"` was covered).
- **`src/data/ev_domain_ontology.json`**: added a `locations.vgreen_stations` group with accentless station name variants (`vincom ba trieu`, `vincom bà triệu`, `landmark 81`, `landmark81`, `royal city`, `ocean park`) so `extract_aspects()` can actually detect these V-GREEN station names in dirty/accentless feedback text — the prior `landmarks` list only had generic terms (`"Vincom"`, `"Vinhomes"`, ...).
- **`tests/test_vingroup.py`** (new): `test_vietnamese_nlp_aspect_extraction_and_cross_validation` loads the real `data/vingroup/xanh_sm_customer_feedback_dirty.csv` + `vgreen_charging_stations_dirty.csv`, asserts the teencode dict has 50+ entries (353 actual), that every charger complaint yields component/location/severity, and that cross-validation flags real `THERMAL_FAULT` rows. Plus two guard tests: non-charger complaints don't false-match a station, and sub-threshold temps aren't confirmed as faults.

### Decisions / tradeoffs
- **Threshold is inclusive (`>=`), not strict `>`.** The injected fault rows in `vgreen_charging_stations_dirty.csv` (`VGREEN_Thermal_Power_Drop` fault family) sit at exactly `85.5°C` with `status == "THERMAL_FAULT"` and `power_kw == 0.0`; a strict `>` would never fire against the actual dataset.
- **Location resolution is substring-based, not exact-match**, because `extract_aspects()` often only detects the generic ontology term `"Vincom"` (checked before the more specific `vgreen_stations` group) rather than the full `"Vincom Bà Triệu"` station name. Substring aliasing (`key in alias or alias in key`) still resolves correctly given only 4 known stations in this dataset; revisit if station name collisions appear (e.g. two different "Vincom ..." branches).
- **Cross-validation is scoped to `component == "charger"` aspects only** — battery/vehicle/app/driver complaints never attempt station resolution, matching the ticket's ask (cross-check against V-GREEN *charging* hardware logs specifically).

### Verification
- `tests/test_vingroup.py` (3 tests) + `tests/test_vietnamese_nlp.py` (33 tests): all pass.
- Full suite: `334 passed, 7 skipped` via `.venv/Scripts/python.exe -m pytest tests/ -q` — no regressions from the ontology/severity edits.
- Note: local `.venv` was missing `pytest`, `duckdb`, and other `requirements.txt` deps at session start; installed via `uv pip install -r requirements.txt --python .venv/Scripts/python.exe` and `uv pip install duckdb --python .venv/Scripts/python.exe` (plain `uv sync`/`uv venv` failed with "Access is denied" removing `.venv/Scripts`, likely a locked file).

---

## 8. Sprint 2 Follow-up (2026-08-10) — Aspect-Based Severity/Sentiment, Pricing Component, Diacritic-Insensitive Matching, Accuracy Eval

Follow-up upgrade to §7, triggered by user request to push the Vietnamese NLP extractor further. Scoped to two concrete, evidence-backed gaps found by actually running the extractor against the real `xanh_sm_customer_feedback_dirty.csv` ground-truth columns, rather than speculative polish.

### What changed
- **`src/services/vietnamese_nlp.py`**
  - **Per-aspect severity + sentiment (ABSA)**: previously `compute_severity()`/`compute_sentiment()` ran once on the *whole* feedback text and that single result was stamped onto every extracted `Aspect`. A feedback mixing a critical charger fault with a minor app gripe ("trạm sạc cháy nổ nguy hiểm, nhưng app thì vẫn ổn") gave every aspect `severity="critical"`. Added `split_clauses()` (factored out of the existing `compute_sentiment` clause-splitting regex) and rewrote `extract_aspects()` to locate the clause containing each component's matched keyword and score severity/sentiment on that clause only. Added `Aspect.sentiment: float` field for this (previously sentiment only existed at the whole-`NLPResult` level).
  - **Diacritic-insensitive severity matching**: `compute_severity()`'s keyword lists (`critical_kw`/`high_kw`/`medium_kw`) are written with full Vietnamese diacritics, but real dirty feedback is frequently accentless (`"ngat dien"`, `"bao loi"`) and the teencode dictionary only restores accents for known slang/abbreviations, not arbitrary full words — so these keywords silently never matched accentless input. Added `strip_diacritics()` (NFD decompose + drop combining marks, `đ/Đ` handled manually) and rewrote the three severity tiers to compare stripped text against stripped keywords via new `_keyword_present()`/`_keyword_negated()` helpers.
    - **Bug caught during this fix**: naive `stripped_keyword in stripped_text` substring checks produced false positives once diacritics were gone — `"nổ"` → `"no"` is a raw substring of `"nóng"` → `"nong"`; `"hỏng"` → `"hong"` is a raw substring of `"không"` → `"khong"`. This flipped two existing tests in `tests/test_nlp_eval.py` (`test_severity_precedence_high`, `test_severity_precedence_negated_fault`) from pass to fail. Fixed by anchoring both helpers to word boundaries (`(?:^|(?<=\W))kw(?:$|(?=\W))`), matching the boundary-anchoring style already used elsewhere in this file (`normalize()`, `find_teencode()`). Both tests pass again after the fix — **lesson: any future diacritic-stripping work in this file must go through `_keyword_present()`, never a raw `in` check.**
  - Extraction scope was deliberately **not** extended to diacritic-insensitive component/location matching — the eval script (below) already showed 100% accuracy there on real data, so there was no demonstrated gap to fix, and short component keywords (e.g. `"tài"`) are more collision-prone once stripped.
- **`src/data/ev_domain_ontology.json`**
  - Added a `pricing` component (`"giá cước"`, `"cước phí"`, `"cước"`, ...) — the real feedback dataset's `extracted_component` ground truth includes `"Giá cước"` (fare/pricing complaints), which had no matching internal component at all before this and would have silently fallen through to `service`.
  - Removed `"Xanh SM"` from the `app` component's keyword list. It's the ride-hailing brand name, mentioned in nearly every review regardless of topic (driver praise, pricing, etc.), so it was spuriously tagging unrelated feedback as an `app` complaint. `app`/`ứng dụng`/`phần mềm`/`đặt xe` already anchor genuine app issues; brand mentions alone no longer do.
- **`eval/eval_vietnamese_nlp.py`** (new): standalone accuracy script — not wired into `eval/run_suite.py` since it evaluates a different thing (NLP field-extraction accuracy vs. dataset ground truth) than that suite's C0/C1/A1 fault-detection tiers. Loads `xanh_sm_customer_feedback_dirty.csv`, runs `analyze()` on every row, and scores:
  - **Component accuracy**: does the ground-truth Vietnamese label (mapped to our internal component name) appear in the row's predicted component set (multi-label, since one feedback can legitimately span multiple components).
  - **Location accuracy**: only scored on rows where the ground-truth location string actually appears in the raw comment text (many rows have a `extracted_location` value — e.g. `"Hà Nội"` — that isn't mentioned in the comment at all, apparently assigned from session metadata in the synthetic generator; those rows are intentionally excluded rather than padding the score, and reported as `location_gradeable_rows`).
  - **Severity tier accuracy**: ground truth uses a 3-tier business scale (`CRITICAL`/`WARNING`/`INFO`) while we use a 4-tier technical scale (`critical`/`high`/`medium`/`low`) — not 1:1, so each ground-truth tier accepts an adjacent pair of ours (`CRITICAL→{critical,high}`, `WARNING→{medium,high}`, `INFO→{low,medium}`) rather than forcing a false exact mapping.
  - Run: `python eval/eval_vietnamese_nlp.py`. Current result on the real dataset: **100% component / 100% location (25/25 gradeable) / 100% severity-tier accuracy** (100 rows, 8 distinct templates).
- **Tests**: added `test_aspect_severity_not_blended_across_components`, `test_aspect_sentiment_not_blended_across_components`, `test_severity_diacritic_insensitive`, `test_extract_pricing_aspect` to `tests/test_vietnamese_nlp.py`; added `test_eval_accuracy_gate_against_ground_truth` to `tests/test_vingroup.py` (imports `eval.eval_vietnamese_nlp.evaluate()`, asserts ≥90% on all three fields as a regression gate — loose enough to not be flaky, tight enough to catch a real ontology/keyword regression).

### Verification
- `tests/test_vietnamese_nlp.py` (37 tests) + `tests/test_vingroup.py` (4 tests): all pass.
- Full suite: `345 passed, 7 skipped` via `.venv/Scripts/python.exe -m pytest tests/ -q` — confirmed via a full run *after* the word-boundary fix (the pre-fix version broke 2 tests in `test_nlp_eval.py`, caught by running the full suite rather than just the new/touched test files — don't skip that step even when a change looks locally contained).

---

## 9. Module relocation (2026-08-10) — `src/services/vietnamese_nlp.py` → `src/teencode/vietnamese_nlp.py`

Per user request, moved the Vietnamese NLP/teencode service into its own top-level `src/teencode/` package instead of living under the generic `src/services/`. Pure move (`git mv`, no logic changes) plus import-path updates in every caller: `src/agents/baselines.py`, `src/tools/nlp_extractor.py`, `tests/test_vietnamese_nlp.py`, `tests/test_vingroup.py`, `tests/test_nlp_eval.py`, `tests/test_e2e.py`, `eval/eval_vietnamese_nlp.py`, `eval/benchmark.py`, and the diagram/table references in `ARCHITECTURE.md`. `VietnameseNLPService`'s internal base-path resolution (`os.path.dirname` × 3 from `__file__`) still resolves correctly since `src/teencode/` sits at the same depth as `src/services/`.

**Note:** `.venv/Scripts` lost most of its installed packages (pytest, fastapi, httpx, duckdb, etc.) mid-session when `uv run` attempted to sync/rebuild the venv and hit its known "Access is denied removing .venv/Scripts" failure (see §7) partway through — this silently deleted files before erroring rather than leaving the venv untouched. Recovered via `uv pip install -r requirements.txt --python .venv/Scripts/python.exe` + `uv pip install duckdb --python .venv/Scripts/python.exe`. **Lesson: never run `uv run` in this repo's venv — always invoke `.venv/Scripts/python.exe` directly — until the underlying file lock is root-caused.**

### Verification
- Full suite: `345 passed, 7 skipped` via `.venv/Scripts/python.exe -m pytest tests/ -q` — identical pass count to before the move, confirming no regressions.

---

## 10. v5 leftovers after PR #27 (2026-08-27)

- **INC_010 F13:** landing parquet was 1 charging / 6 trips while the manifest claimed 5 / 0 (generator skipped injection when the VIN already had a session). Patched `landing_data/vingroup_pilot_landing_demo.parquet` to 5 charging / 0 trips for `VF8VNF_0003` day 13; generator now always pads + strips trips. `_gt_blockers` compares parquet counts to manifest `charging_sessions` / `completed_trips`. Local eval: blockers `[]`, detection tp=14 fn=0 F1=0.8.
- **Landing SoT path:** default `LANDING_PARQUET_PATH` is `landing_data/vingroup_pilot_landing_demo.parquet`; seed walks landing_data then data_demo then data_new.
- **Memory HTTP:** `GET /api/v1/memory` and `GET /api/v1/memory/stats` (registered before `/{user_id}`) so the index is 200/401 instead of 404/405. Session-start inject on `POST /chat/send` was already present.
- **10k cap:** ReAct preflight already hard-stops; mid-loop breaks now set `final_answer`. `POST /chat/send` returns `total_tokens`. Meta strip shows `k/10k` from real metadata totals.

---

## 11. QA t086 not-ship-ok blockers (2026-08-27)

Fixes on `fix/v5-qa-t086-ship-blockers` (PR into `v5`). Not applied on t086.

- **A-01 mobile 375:** off-canvas sidebar + hamburger; header pills icon-only; inspector collapsed under 900px.
- **A-02 Eval vs GT:** normalize `batch` or top-level `detection`; paint F1; 45s abort; cache GT scores.
- **A-03/A-04 RBAC:** UI hides Approve/Batch/Reset/Execute by `ROLE_PERMISSIONS`. Analyst `POST /hitl/approve` is 403 (`review_rules`).
- **A-05 Profiler:** health `—` / Unknown when 0 rows; no fake Excellent.
- **A-06 HITL:** queue aliases (`vinfast_ev_telemetry`↔`ev_telemetry`) + hydrate traces without session_id match; `datatrust:hitl-proposed`.
- **A-07:** `docker-compose.yml` `APP_ENV=production` (os/t086). d086 example override keeps `APP_ENV=development`. `/health` version uses `GIT_SHA` when set.
- **MEDIUM cheap:** 768 KPI 2-col wrap; rules `th` wrap.

### Verification
- `uv run pytest tests/test_qa_t086_gates.py tests/test_hitl.py tests/test_ngan_gt_eval.py tests/test_v2_features.py tests/test_reset_wipe.py -q`

---

## 12. QA t086 remaining MEDIUM/LOW + PONG (2026-08-27)

- **PONG / Trục B:** `is_pong_ping` short-circuits `/chat/send` — LLM ON → `PONG`, OFF → 4-dataset inventory. No ReAct, no dataset_key inject, no inventory append.
- **A-08/A-09:** KPI wrap at 768; rules `TARGET COLUMN` / `QUARANTINED ROWS` wider + wrap.
- **A-10:** session switcher title + tooltip; workspace send passes `lang`.
- **A-11:** alerts empty + dashboard hint cite GT pack 14.
- **A-12–A-16:** Not signed in ghost; login labels; Sign In `#0369a1`; `RULE_DET_` when synth OFF; Reset DB gap from LLM toggle.

---

## 13. QA loop close on d086 (2026-08-27)

- Eval is its own ops `mainGroup` (no Governance KPI first paint). `EvalVsGtPanel` binds `detection` onto `batch`.
- Alerts always show Ngan GT pack banner (14 / F1=0.8) even when live cases exist.
- Playwright on **d086 only**: 16 PASS / 0 FAIL. t086 not deployed.


