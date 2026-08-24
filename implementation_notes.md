# Implementation Notes - Realtime Day Auto-Advance (Only On Batch Completion)

## Business Logic Clarification
- **Realtime Stream 100% Completion**: When Realtime ticks reach 100% of rows for Day N, the stream **holds at 100%** on Day N ("Waiting for incoming telemetry packets..."). It does NOT auto-advance by itself.
- **Batch Day N Completion**: Triggering and completing **Batch Day N** represents the official end of operational day N. ONLY upon Batch Day N completion will the Realtime live stream automatically advance to stream Day N+1!

## Key Changes
- **`src/services/ingestion/realtime_runner.py`**:
  - Reverted auto-advance inside `_tick()` when `df.empty`. When Realtime stream reaches 100% of Day N, it holds position at Day N with `status="completed"`.
- **`src/api/ingestion.py`**:
  - `activate_day(day_idx=N)`: When Batch Day N finishes running, updates `demo_state.current_day_idx = N + 1`, switches `RealtimeRunner` to Day N+1, and broadcasts `datatrust:realtime-day-advanced` WebSocket event.
  - `activate_warmup()`: When Warmup (Day 0-9) finishes, updates `demo_state.current_day_idx = 10`, switches `RealtimeRunner` to Day 10, and broadcasts `datatrust:realtime-day-advanced`.
- **`frontend/src/stores/ingestionStore.ts`**:
  - `handleDayAdvance`: Updates `demoState` and `realtimeStatus` to `new_day` when WebSocket notifies batch completion.
  - `handleAgentTrace` & `activateDay`: Enhanced to dynamically transition `executionStage` (Step 1 -> 2 -> 3 -> 4) in real-time based on WebSocket `agent.trace` progress events, preventing the UI stepper from remaining stuck at Step 2 while backend LLM rule proposal and batch processing execute.

---

# Implementation Notes - Canonical Table Name Normalization & SQL Remediation

## Business & Schema Requirement
- The modernized schema consists of 4 canonical datasets: `ev_telemetry`, `charging_sessions`, `trips`, and `nlp_feedback`.
- Legacy references (e.g. `vinfast_bms`, `vgreen_telemetry`, `xanhsm_trips`, `xanhsm_feedback`) or rule-prefixed table strings (`ev_telemetry__rule_anom_raw.ev_telemetry_22`) generated invalid SQL suggestions (e.g., `UPDATE vinfast_bms ...`).

## Key Changes
- **`src/utils/table_utils.py`**:
  - Created `normalize_table_name()` to map legacy aliases & composite rule prefixes to canonical dataset names.
  - Created `resolve_db_table_name()` to query `information_schema.tables` in `main` schema (with support for `DuckDBManager` and raw `DuckDBPyConnection`), ensuring existing DB tables in legacy test fixtures remain compatible.
- **`src/tools/rule_executor.py`**:
  - Inferred table logic maps column names to canonical datasets (`ev_telemetry`, `charging_sessions`, `trips`, `nlp_feedback`).
  - Calls `resolve_db_table_name(spec.table, conn)` before running rule execution and inserting quarantine entries.
- **`src/api/quarantine_api.py`**:
  - `synthesize_remediation_sql()` normalizes `source_table` so all AI-suggested HITL remediation queries reference the canonical table (`UPDATE ev_telemetry SET battery_soc = 0.0 WHERE battery_soc < 0.0;`).
- **`src/tools/rule_proposer.py` & `src/reliability/investigation/tools.py`**:
  - Standardized dataset default fallbacks to canonical names.
- **`src/api/hitl.py` & API Routes**:
  - Updated API route endpoints and LLM fallback descriptions to list the canonical 4 datasets.

## Verification
- Unit test suite [`tests/test_table_utils.py`](file:///c:/Users/ngant/P-086/tests/test_table_utils.py), [`tests/test_quarantine_remediation.py`](file:///c:/Users/ngant/P-086/tests/test_quarantine_remediation.py), [`tests/test_tools.py`](file:///c:/Users/ngant/P-086/tests/test_tools.py) verified: 43 passed (100%).
