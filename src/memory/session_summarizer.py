"""
src/memory/session_summarizer.py

Purpose: Tầng 2 — deterministically compress a finished session's step-history
into one `SessionSummaryRecord`. This is a pure aggregation over data
`SessionStateTracker` (Workstream B) already recorded — it never re-reads raw
chat transcripts and never calls an LLM, so it is cheap, has zero external
failure surface, and is fully reproducible (the same step_history always
produces the same summary).

Role in the business flow: `SessionStateTracker.close_session()` calls
`SessionSummarizer.summarize()` at the compression trigger point (explicit
session end, or a timeout sweep) and persists the result via
`MemoryStore.insert_summary`. `UserMemoryConsolidator` (Tầng 3) later reads
these summaries as its only input.
"""
from __future__ import annotations

import uuid

from src.memory.schemas import SessionStateRecord, SessionStep, SessionSummaryRecord, utcnow_iso


class SessionSummarizer:
    """Purpose: single-responsibility compressor from `SessionStateRecord` to
    `SessionSummaryRecord`. Stateless — every method is a pure function of its
    input, no DB access, so it can be unit-tested without a database.
    """

    def summarize(self, state: SessionStateRecord) -> SessionSummaryRecord:
        """Purpose: build the Tầng 2 digest for one finished session.
        Input: a `SessionStateRecord` whose `step_history` has already been
        populated by `SessionStateTracker.record_step()` calls throughout the
        session's lifetime.
        Output: a `SessionSummaryRecord` with rule-decision counts, the
        distinct dataset_keys touched, the ordered list of steps taken, and a
        deterministic `outcome` label — ready for `MemoryStore.insert_summary`.
        """
        dataset_keys: list[str] = []
        if state.dataset_key and state.dataset_key not in dataset_keys:
            dataset_keys.append(state.dataset_key)

        steps_taken: list[SessionStep] = []
        rules_proposed = 0
        rules_approved = 0
        rules_rejected = 0
        rules_edited = 0

        for event in state.step_history:
            steps_taken.append(event.step)

            event_dataset_key = event.detail.get("dataset_key")
            if event_dataset_key and event_dataset_key not in dataset_keys:
                dataset_keys.append(event_dataset_key)

            if event.step == SessionStep.PROPOSE_RULE:
                rules_proposed += int(event.detail.get("rule_count", 1) or 1)
            elif event.step == SessionStep.RULE_APPROVED:
                rules_approved += 1
            elif event.step == SessionStep.RULE_REJECTED:
                rules_rejected += 1
            elif event.step == SessionStep.RULE_EDITED:
                rules_edited += 1

        outcome = self._infer_outcome(steps_taken, rules_approved, rules_rejected)

        return SessionSummaryRecord(
            summary_id=f"sum_{uuid.uuid4().hex[:16]}",
            session_id=state.session_id,
            user_id=state.user_id,
            dataset_keys=dataset_keys,
            steps_taken=steps_taken,
            rules_proposed=rules_proposed,
            rules_approved=rules_approved,
            rules_rejected=rules_rejected,
            rules_edited=rules_edited,
            outcome=outcome,
            started_at=state.started_at,
            ended_at=state.ended_at or utcnow_iso(),
        )

    @staticmethod
    def _infer_outcome(steps_taken: list[SessionStep], approved: int, rejected: int) -> str:
        """Purpose: label a session's terminal outcome from the steps it
        actually passed through, without fabricating a status the step_history
        does not evidence.
        Output: one of `executed`, `approved`, `rejected`,
        `pending_hitl_review`, `investigated_only`, or `incomplete`.
        """
        if SessionStep.EXECUTED in steps_taken:
            return "executed"
        if approved > 0:
            return "approved"
        if rejected > 0:
            return "rejected"
        if SessionStep.HITL_PENDING in steps_taken:
            return "pending_hitl_review"
        if SessionStep.INVESTIGATE in steps_taken or SessionStep.DETECT in steps_taken:
            return "investigated_only"
        return "incomplete"


session_summarizer = SessionSummarizer()
