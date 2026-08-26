"""
src/memory/store.py

Purpose: single owner of every DuckDB table the Multi-tier User Memory module
writes to, and the only file in `src/memory/` that speaks raw SQL. Every other
file in this package (identity, state_tracker, session_summarizer, user_memory,
context_provider, routes) goes through `MemoryStore` instead of touching the
database directly, so the schema has exactly one place it can drift from.

Role in the business flow: reuses the existing DuckDB singleton from
`src/db/connection.py` (the same embedded database every other DataTrust OS
module writes to) instead of opening a second connection/file. Tables are
created lazily and idempotently (`CREATE TABLE IF NOT EXISTS`) the first time
`MemoryStore()` is constructed, mirroring the lazy-schema pattern already used
by `src/services/conversation_store.py`.
"""
from __future__ import annotations

import json
from typing import Any

from src.db.connection import get_db
from src.memory.schemas import (
    SessionStateRecord,
    SessionStatus,
    SessionSummaryRecord,
    StepEvent,
    UserMemoryProfile,
    utcnow_iso,
)


class MemoryStore:
    """Purpose: DuckDB-backed persistence layer for the memory module's 4 tables
    (`memory_session_identity`, `memory_session_state`,
    `memory_session_summaries`, `memory_user_profile`).
    Input: none beyond the shared DuckDB connection resolved via `get_db()`.
    Output/Role: typed CRUD methods returning the Pydantic models from
    `schemas.py`; every higher-level class in this package depends on an
    instance of this store instead of writing SQL itself.
    """

    def __init__(self, db: Any = None) -> None:
        self._db = db
        self._schema_ready = False
        self._ensure_schema()

    @property
    def db(self):
        if self._db is None:
            self._db = get_db()
        return self._db

    def _ensure_schema(self) -> None:
        """Purpose: idempotently create the 4 memory tables + their indexes.
        Called once per `MemoryStore` instance construction; safe to call more
        than once because every statement is `IF NOT EXISTS`.
        """
        if self._schema_ready:
            return
        conn = self.db.get_connection()
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS memory_session_identity (
                session_id VARCHAR PRIMARY KEY,
                user_id VARCHAR NOT NULL,
                role VARCHAR,
                created_at VARCHAR NOT NULL
            );
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS memory_session_state (
                session_id VARCHAR PRIMARY KEY,
                user_id VARCHAR NOT NULL,
                dataset_key VARCHAR,
                current_step VARCHAR NOT NULL,
                status VARCHAR NOT NULL,
                step_history VARCHAR NOT NULL,
                started_at VARCHAR NOT NULL,
                updated_at VARCHAR NOT NULL,
                ended_at VARCHAR
            );
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_memory_session_state_user "
            "ON memory_session_state(user_id, status);"
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS memory_session_summaries (
                summary_id VARCHAR PRIMARY KEY,
                session_id VARCHAR NOT NULL,
                user_id VARCHAR NOT NULL,
                dataset_keys VARCHAR NOT NULL,
                steps_taken VARCHAR NOT NULL,
                rules_proposed INTEGER NOT NULL DEFAULT 0,
                rules_approved INTEGER NOT NULL DEFAULT 0,
                rules_rejected INTEGER NOT NULL DEFAULT 0,
                rules_edited INTEGER NOT NULL DEFAULT 0,
                outcome VARCHAR NOT NULL,
                started_at VARCHAR NOT NULL,
                ended_at VARCHAR NOT NULL,
                created_at VARCHAR NOT NULL
            );
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_memory_session_summaries_user "
            "ON memory_session_summaries(user_id, created_at);"
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS memory_user_profile (
                user_id VARCHAR PRIMARY KEY,
                sessions_observed INTEGER NOT NULL DEFAULT 0,
                top_datasets VARCHAR NOT NULL,
                rule_decision_pattern VARCHAR NOT NULL,
                approval_rate DOUBLE,
                narrative VARCHAR NOT NULL,
                last_consolidated_session_id VARCHAR,
                last_consolidated_at VARCHAR,
                updated_at VARCHAR NOT NULL
            );
            """
        )
        self._schema_ready = True

    # ------------------------------------------------------------------
    # Workstream A — session identity
    # ------------------------------------------------------------------

    def bind_identity(self, session_id: str, user_id: str, role: str | None = None) -> None:
        """Purpose: bind a chat/investigation session to the authenticated user
        that owns it (Workstream A). Idempotent upsert (DELETE-then-INSERT, the
        same pattern `conversation_store.save_message` already uses in this
        codebase) so re-binding the same session_id never duplicates rows.
        """
        conn = self.db.get_connection()
        conn.execute("DELETE FROM memory_session_identity WHERE session_id = ?", [session_id])
        conn.execute(
            "INSERT INTO memory_session_identity (session_id, user_id, role, created_at) "
            "VALUES (?, ?, ?, ?)",
            [session_id, user_id, role, utcnow_iso()],
        )

    def resolve_identity(self, session_id: str) -> dict[str, str] | None:
        """Purpose: reverse-lookup the owning user of a session_id.
        Output: `{"user_id": ..., "role": ...}` or `None` if never bound.
        """
        rows = self.db.execute(
            "SELECT user_id, role FROM memory_session_identity WHERE session_id = ?",
            [session_id],
        )
        if not rows:
            return None
        return {"user_id": rows[0][0], "role": rows[0][1]}

    # ------------------------------------------------------------------
    # Workstream B — session state
    # ------------------------------------------------------------------

    def upsert_state(self, record: SessionStateRecord) -> None:
        """Purpose: persist the full `SessionStateRecord` (idempotent upsert).
        Called by `SessionStateTracker` after every step transition.
        """
        conn = self.db.get_connection()
        conn.execute("DELETE FROM memory_session_state WHERE session_id = ?", [record.session_id])
        conn.execute(
            """
            INSERT INTO memory_session_state
                (session_id, user_id, dataset_key, current_step, status,
                 step_history, started_at, updated_at, ended_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                record.session_id,
                record.user_id,
                record.dataset_key,
                record.current_step.value,
                record.status.value,
                json.dumps([e.model_dump(mode="json") for e in record.step_history]),
                record.started_at,
                record.updated_at,
                record.ended_at,
            ],
        )

    def get_state(self, session_id: str) -> SessionStateRecord | None:
        """Purpose: fetch the current pipeline progress of one session.
        Output: `None` when the session has never recorded a step yet.
        """
        rows = self.db.execute(
            "SELECT session_id, user_id, dataset_key, current_step, status, "
            "step_history, started_at, updated_at, ended_at "
            "FROM memory_session_state WHERE session_id = ?",
            [session_id],
        )
        if not rows:
            return None
        return self._row_to_state(rows[0])

    def list_active_sessions_before(self, cutoff_iso: str) -> list[SessionStateRecord]:
        """Purpose: find every `ACTIVE` session whose `updated_at` is older than
        `cutoff_iso`. Output feeds `SessionStateTracker.sweep_idle_sessions`,
        the timeout-triggered path of the Tầng 2 compression trigger.
        """
        rows = self.db.execute(
            "SELECT session_id, user_id, dataset_key, current_step, status, "
            "step_history, started_at, updated_at, ended_at "
            "FROM memory_session_state WHERE status = ? AND updated_at < ?",
            [SessionStatus.ACTIVE.value, cutoff_iso],
        )
        return [self._row_to_state(r) for r in rows]

    @staticmethod
    def _row_to_state(row: Any) -> SessionStateRecord:
        raw_history = json.loads(row[5]) if row[5] else []
        return SessionStateRecord(
            session_id=row[0],
            user_id=row[1],
            dataset_key=row[2],
            current_step=row[3],
            status=row[4],
            step_history=[StepEvent(**e) for e in raw_history],
            started_at=row[6],
            updated_at=row[7],
            ended_at=row[8],
        )

    # ------------------------------------------------------------------
    # Tầng 2 — session summaries
    # ------------------------------------------------------------------

    def insert_summary(self, record: SessionSummaryRecord) -> None:
        """Purpose: persist one Tầng 2 compressed session digest. Idempotent on
        `summary_id` (DELETE-then-INSERT) so re-summarizing a session (e.g. a
        retried timeout sweep) never leaves duplicate rows behind.
        """
        conn = self.db.get_connection()
        conn.execute("DELETE FROM memory_session_summaries WHERE summary_id = ?", [record.summary_id])
        conn.execute(
            """
            INSERT INTO memory_session_summaries
                (summary_id, session_id, user_id, dataset_keys, steps_taken,
                 rules_proposed, rules_approved, rules_rejected, rules_edited,
                 outcome, started_at, ended_at, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                record.summary_id,
                record.session_id,
                record.user_id,
                json.dumps(record.dataset_keys),
                json.dumps([s.value for s in record.steps_taken]),
                record.rules_proposed,
                record.rules_approved,
                record.rules_rejected,
                record.rules_edited,
                record.outcome,
                record.started_at,
                record.ended_at,
                record.created_at,
            ],
        )

    def list_summaries_for_user(
        self, user_id: str, since_iso: str | None = None, limit: int = 200
    ) -> list[SessionSummaryRecord]:
        """Purpose: read back a user's episodic memory, optionally only the
        summaries created after `since_iso`. Two callers: `UserMemoryConsolidator`
        (incremental merge cursor) and the Workstream C transparency API
        (full history view).
        """
        if since_iso:
            rows = self.db.execute(
                "SELECT summary_id, session_id, user_id, dataset_keys, steps_taken, "
                "rules_proposed, rules_approved, rules_rejected, rules_edited, "
                "outcome, started_at, ended_at, created_at "
                "FROM memory_session_summaries "
                "WHERE user_id = ? AND created_at > ? ORDER BY created_at ASC LIMIT ?",
                [user_id, since_iso, limit],
            )
        else:
            rows = self.db.execute(
                "SELECT summary_id, session_id, user_id, dataset_keys, steps_taken, "
                "rules_proposed, rules_approved, rules_rejected, rules_edited, "
                "outcome, started_at, ended_at, created_at "
                "FROM memory_session_summaries "
                "WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
                [user_id, limit],
            )
        return [self._row_to_summary(r) for r in rows]

    def get_summary(self, summary_id: str) -> SessionSummaryRecord | None:
        rows = self.db.execute(
            "SELECT summary_id, session_id, user_id, dataset_keys, steps_taken, "
            "rules_proposed, rules_approved, rules_rejected, rules_edited, "
            "outcome, started_at, ended_at, created_at "
            "FROM memory_session_summaries WHERE summary_id = ?",
            [summary_id],
        )
        if not rows:
            return None
        return self._row_to_summary(rows[0])

    def delete_summary(self, summary_id: str, user_id: str) -> bool:
        """Purpose: Workstream C "forget this session" control. Scoped by
        `user_id` as well as `summary_id` so one user can never delete another
        user's episodic memory through an ID guess.
        Output: `True` if a row was actually deleted.
        """
        conn = self.db.get_connection()
        existing = self.db.execute(
            "SELECT summary_id FROM memory_session_summaries WHERE summary_id = ? AND user_id = ?",
            [summary_id, user_id],
        )
        if not existing:
            return False
        conn.execute(
            "DELETE FROM memory_session_summaries WHERE summary_id = ? AND user_id = ?",
            [summary_id, user_id],
        )
        return True

    def delete_all_summaries_for_user(self, user_id: str) -> None:
        conn = self.db.get_connection()
        conn.execute("DELETE FROM memory_session_summaries WHERE user_id = ?", [user_id])

    @staticmethod
    def _row_to_summary(row: Any) -> SessionSummaryRecord:
        return SessionSummaryRecord(
            summary_id=row[0],
            session_id=row[1],
            user_id=row[2],
            dataset_keys=json.loads(row[3]) if row[3] else [],
            steps_taken=json.loads(row[4]) if row[4] else [],
            rules_proposed=row[5],
            rules_approved=row[6],
            rules_rejected=row[7],
            rules_edited=row[8],
            outcome=row[9],
            started_at=row[10],
            ended_at=row[11],
            created_at=row[12],
        )

    # ------------------------------------------------------------------
    # Tầng 3 — user memory profile
    # ------------------------------------------------------------------

    def upsert_profile(self, profile: UserMemoryProfile) -> None:
        """Purpose: persist the consolidated long-term memory for one user.
        Called only by `UserMemoryConsolidator.consolidate()` and by the
        Workstream C edit/delete endpoints.
        """
        conn = self.db.get_connection()
        conn.execute("DELETE FROM memory_user_profile WHERE user_id = ?", [profile.user_id])
        conn.execute(
            """
            INSERT INTO memory_user_profile
                (user_id, sessions_observed, top_datasets, rule_decision_pattern,
                 approval_rate, narrative, last_consolidated_session_id,
                 last_consolidated_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                profile.user_id,
                profile.sessions_observed,
                json.dumps(profile.top_datasets),
                json.dumps(profile.rule_decision_pattern),
                profile.approval_rate,
                profile.narrative,
                profile.last_consolidated_session_id,
                profile.last_consolidated_at,
                profile.updated_at,
            ],
        )

    def get_profile(self, user_id: str) -> UserMemoryProfile | None:
        """Purpose: read the current long-term memory for one user.
        Output: `None` when the user has no consolidated memory yet (e.g. a
        brand-new user, or one whose memory was just deleted).
        """
        rows = self.db.execute(
            "SELECT user_id, sessions_observed, top_datasets, rule_decision_pattern, "
            "approval_rate, narrative, last_consolidated_session_id, "
            "last_consolidated_at, updated_at "
            "FROM memory_user_profile WHERE user_id = ?",
            [user_id],
        )
        if not rows:
            return None
        row = rows[0]
        return UserMemoryProfile(
            user_id=row[0],
            sessions_observed=row[1],
            top_datasets=json.loads(row[2]) if row[2] else [],
            rule_decision_pattern=json.loads(row[3]) if row[3] else {},
            approval_rate=row[4],
            narrative=row[5],
            last_consolidated_session_id=row[6],
            last_consolidated_at=row[7],
            updated_at=row[8],
        )

    def delete_profile(self, user_id: str) -> bool:
        """Purpose: Workstream C "forget me entirely" control for Tầng 3.
        Output: `True` if a profile existed and was deleted.
        """
        existing = self.get_profile(user_id)
        if existing is None:
            return False
        conn = self.db.get_connection()
        conn.execute("DELETE FROM memory_user_profile WHERE user_id = ?", [user_id])
        return True


memory_store = MemoryStore()
