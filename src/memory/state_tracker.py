"""
src/memory/state_tracker.py

Purpose: Workstream B — track which pipeline step a session is currently on,
and keep an append-only ledger of every step it has passed through. This is
the data source Tầng 2 (`SessionSummarizer`) compresses from, and the
resumability primitive an agent (or the UI timeline) queries to answer
"what has this session already done" without replaying `agent_traces`.

Role in the business flow: any tool/route that advances a session through the
escalation ladder (profile -> detect -> propose -> HITL -> execute) calls
`record_step()` once per transition. When a session ends — explicitly, or
because it went idle past a timeout — `close_session()` / `sweep_idle_sessions()`
fire the Tầng 2 compression trigger and persist the resulting
`SessionSummaryRecord` via `MemoryStore`.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from src.memory.identity import SessionIdentityRegistry, session_identity_registry
from src.memory.schemas import (
    SessionStateRecord,
    SessionStatus,
    SessionStep,
    SessionSummaryRecord,
    StepEvent,
    utcnow_iso,
)
from src.memory.session_summarizer import SessionSummarizer, session_summarizer
from src.memory.store import MemoryStore, memory_store


class SessionStateTracker:
    """Purpose: single-responsibility state machine driver for Workstream B.
    Owns no SQL itself (delegates to `MemoryStore`) and owns no compression
    logic itself (delegates to `SessionSummarizer`) — its job is exactly the
    step transitions and the timing/trigger rules around them.
    """

    def __init__(
        self,
        store: MemoryStore | None = None,
        identity: SessionIdentityRegistry | None = None,
        summarizer: SessionSummarizer | None = None,
    ) -> None:
        self._store = store or memory_store
        self._identity = identity or session_identity_registry
        self._summarizer = summarizer or session_summarizer

    def start_session(
        self, session_id: str, user_id: str, dataset_key: str | None = None
    ) -> SessionStateRecord:
        """Purpose: begin (or resume) tracking a session.
        Input: `session_id`; `user_id` (also bound into
        `SessionIdentityRegistry` so later calls can resolve it without the
        caller re-supplying it); optional `dataset_key` the session targets.
        Output: the existing `SessionStateRecord` unchanged if the session was
        already started (resuming must never reset progress already made), or
        a freshly created one at `SessionStep.INGEST`.
        """
        self._identity.bind(session_id, user_id)
        existing = self._store.get_state(session_id)
        if existing is not None:
            return existing

        now = utcnow_iso()
        record = SessionStateRecord(
            session_id=session_id,
            user_id=user_id,
            dataset_key=dataset_key,
            current_step=SessionStep.INGEST,
            status=SessionStatus.ACTIVE,
            step_history=[StepEvent(step=SessionStep.INGEST, detail={}, recorded_at=now)],
            started_at=now,
            updated_at=now,
        )
        self._store.upsert_state(record)
        return record

    def record_step(
        self, session_id: str, step: SessionStep, detail: dict[str, Any] | None = None
    ) -> SessionStateRecord:
        """Purpose: append one step transition to a session's ledger.
        Input: `step` — one of the fixed `SessionStep` values; `detail` — a
        small JSON-serializable dict describing the step (e.g.
        `{"rule_count": 3, "dataset_key": "vinfast_ev_telemetry_dirty"}`),
        never raw row data (mirrors the metadata-only guarantee already
        enforced by `src/agents/context.py::ContextBuilder`).
        Output: the updated `SessionStateRecord`.
        Raises: `LookupError` if the session was never started with
        `start_session()` and has no known owner — a step can never be
        attributed to an unknown user.
        """
        record = self._store.get_state(session_id)
        if record is None:
            owner = self._identity.resolve(session_id)
            if owner is None:
                raise LookupError(
                    f"Cannot record step '{step.value}' for unknown session '{session_id}': "
                    "call start_session() first so the session has a known owner."
                )
            user_id, _role = owner
            record = self.start_session(session_id, user_id)

        record.step_history.append(StepEvent(step=step, detail=detail or {}))
        record.current_step = step
        record.updated_at = utcnow_iso()
        if step == SessionStep.CLOSED:
            record.status = SessionStatus.CLOSED
            record.ended_at = record.updated_at

        self._store.upsert_state(record)
        return record

    def get_state(self, session_id: str) -> SessionStateRecord | None:
        """Purpose: read-only accessor for a session's current progress.
        Output: `None` if the session has never recorded a step."""
        return self._store.get_state(session_id)

    def close_session(self, session_id: str) -> SessionSummaryRecord | None:
        """Purpose: explicit "session end" compression trigger.
        Output: the persisted `SessionSummaryRecord`, or `None` if the session
        had no tracked state to summarize (nothing was ever recorded for it).
        """
        record = self._store.get_state(session_id)
        if record is None:
            return None
        return self._close_and_summarize(record, SessionStatus.CLOSED)

    def sweep_idle_sessions(self, idle_minutes: int = 30) -> list[SessionSummaryRecord]:
        """Purpose: timeout-based compression trigger. Intended to be invoked
        periodically (e.g. by the existing scheduler infrastructure in
        `src/services/scheduler.py`, or an API endpoint a cron hits) rather
        than by a background thread this module starts itself.
        Input: `idle_minutes` — a session with no step recorded in this window
        is considered abandoned.
        Output: the list of `SessionSummaryRecord`s produced for every session
        that was swept and closed.
        """
        cutoff = (datetime.now(UTC) - timedelta(minutes=idle_minutes)).isoformat()
        stale_sessions = self._store.list_active_sessions_before(cutoff)
        summaries: list[SessionSummaryRecord] = []
        for record in stale_sessions:
            summary = self._close_and_summarize(record, SessionStatus.TIMED_OUT)
            if summary is not None:
                summaries.append(summary)
        return summaries

    def _close_and_summarize(
        self, record: SessionStateRecord, terminal_status: SessionStatus
    ) -> SessionSummaryRecord | None:
        record.status = terminal_status
        record.ended_at = record.ended_at or utcnow_iso()
        record.updated_at = record.ended_at
        self._store.upsert_state(record)

        summary = self._summarizer.summarize(record)
        self._store.insert_summary(summary)
        return summary


session_state_tracker = SessionStateTracker()
