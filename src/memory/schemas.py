"""
src/memory/schemas.py

Purpose: Canonical Pydantic data contracts for the Multi-tier User Memory module.
Every table owned by `src/memory/store.py` and every payload returned by
`src/memory/routes.py` is described here, so the identity registry, the state
tracker, the summarizer, the consolidator and the API layer all share one typed
vocabulary instead of passing raw dicts across module boundaries.

Role in the business flow: this file has no side effects (no DB access, no I/O).
It is the shared "shape of truth" imported by every other file in `src/memory/`.
"""
from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


def utcnow_iso() -> str:
    """Purpose: single source of truth for "now" across the memory module so
    every timestamp written to DuckDB is UTC ISO-8601 and directly comparable
    with simple string ordering (no timezone-naive drift between callers).
    Input: none. Output: current UTC time as an ISO-8601 string.
    """
    return datetime.now(UTC).isoformat()


class SessionStep(str, Enum):
    """Purpose: fixed vocabulary of pipeline stages a chat/investigation session
    can occupy, mirrored 1:1 from the escalation ladder documented in
    ARCHITECTURE.md (INGESTION -> DETECTION -> FUSION -> INVESTIGATION ->
    HITL GOVERNANCE). Workstream B step-tracking only ever stores one of these
    values, so Tầng 2 (SessionSummarizer) never has to fuzzy-match free text.
    """

    INGEST = "INGEST"
    PROFILE = "PROFILE"
    DETECT = "DETECT"
    FUSE = "FUSE"
    INVESTIGATE = "INVESTIGATE"
    PROPOSE_RULE = "PROPOSE_RULE"
    HITL_PENDING = "HITL_PENDING"
    RULE_APPROVED = "RULE_APPROVED"
    RULE_REJECTED = "RULE_REJECTED"
    RULE_EDITED = "RULE_EDITED"
    EXECUTED = "EXECUTED"
    CLOSED = "CLOSED"


class SessionStatus(str, Enum):
    """Purpose: lifecycle flag for a `SessionStateRecord`.
    Role: `ACTIVE` sessions are eligible for `sweep_idle_sessions`; `CLOSED`
    and `TIMED_OUT` sessions are terminal and already have a Tầng 2 summary.
    """

    ACTIVE = "active"
    CLOSED = "closed"
    TIMED_OUT = "timed_out"


class StepEvent(BaseModel):
    """Purpose: one immutable entry in a session's step-history ledger.
    Input: produced by `SessionStateTracker.record_step()`.
    Output/Role: persisted as one JSON element inside
    `memory_session_state.step_history`; later read verbatim by
    `SessionSummarizer` to build the deterministic Tầng 2 digest.
    """

    step: SessionStep
    detail: dict[str, Any] = Field(default_factory=dict)
    recorded_at: str = Field(default_factory=utcnow_iso)


class SessionStateRecord(BaseModel):
    """Purpose: full snapshot of one session's progress through the pipeline
    (Workstream B). Role: the single source of truth callers query to answer
    "which step is this session on right now" without replaying the raw
    `agent_traces` log — this is what makes a session resumable.
    """

    session_id: str
    user_id: str
    dataset_key: str | None = None
    current_step: SessionStep
    status: SessionStatus = SessionStatus.ACTIVE
    step_history: list[StepEvent] = Field(default_factory=list)
    started_at: str = Field(default_factory=utcnow_iso)
    updated_at: str = Field(default_factory=utcnow_iso)
    ended_at: str | None = None


class SessionSummaryRecord(BaseModel):
    """Purpose: Tầng 2 episodic memory — one deterministically compressed record
    per finished session. Role: (a) the input unit `UserMemoryConsolidator`
    merges into Tầng 3, and (b) a directly human-readable record exposed by the
    Workstream C transparency API.
    """

    summary_id: str
    session_id: str
    user_id: str
    dataset_keys: list[str] = Field(default_factory=list)
    steps_taken: list[SessionStep] = Field(default_factory=list)
    rules_proposed: int = 0
    rules_approved: int = 0
    rules_rejected: int = 0
    rules_edited: int = 0
    outcome: str = "incomplete"
    started_at: str
    ended_at: str
    created_at: str = Field(default_factory=utcnow_iso)


class UserMemoryProfile(BaseModel):
    """Purpose: Tầng 3 long-term semantic memory — one row per user, built by
    incrementally merging `SessionSummaryRecord` rows across every session that
    user has ever had. Role: read by `MemoryContextProvider` at the start of a
    new session and injected into the agent's LLM context so behaviour adapts
    to that specific user across sessions, not just within one.
    """

    user_id: str
    sessions_observed: int = 0
    top_datasets: list[dict[str, Any]] = Field(default_factory=list)
    rule_decision_pattern: dict[str, int] = Field(
        default_factory=lambda: {"approved": 0, "rejected": 0, "edited": 0}
    )
    approval_rate: float | None = None
    narrative: str = ""
    last_consolidated_session_id: str | None = None
    last_consolidated_at: str | None = None
    updated_at: str = Field(default_factory=utcnow_iso)


class MemoryEditRequest(BaseModel):
    """Purpose: Workstream C payload for a user-initiated correction to their
    own long-term memory. Role: lets a user override a narrative that misreads
    their intent, or reset the rule-decision pattern counters, without an
    engineer touching the database by hand.
    """

    narrative: str | None = None
    reset_rule_decision_pattern: bool = False
    edited_by: str = "self"
