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

## Verification
- Python syntax verified with `py_compile`.
- Frontend TypeScript type check verified with `pnpm tsc --noEmit` (0 errors).
