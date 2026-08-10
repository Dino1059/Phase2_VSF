# DataTrust OS v3 — Technical Implementation Notes & Developer Log

> **Target Audience:** Developers, Co-workers, and Future AI Agent Sessions  
> **Last Updated:** 2026-08-02  
> **Pytest Gate:** 125 / 125 Tests Passing (`54.34s`)  
> **Git Rule Constraint:** Commit locally; DO NOT execute `git push` unless explicitly ordered by user.

---

## 1. Project Context & Objectives (DATA-02)

DataTrust OS v3 is an autonomous AI data governance system built for the VinGroup enterprise ecosystem (VinFast EVs, Xanh SM Ride-Hailing, V-GREEN Charging Infrastructure, and Vietnamese Customer Feedback).

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
