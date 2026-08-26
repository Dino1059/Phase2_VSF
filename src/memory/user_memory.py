"""
src/memory/user_memory.py

Purpose: Tầng 3 — incrementally consolidate a user's `SessionSummaryRecord`s
(Tầng 2) into one durable, cross-session `UserMemoryProfile`. This is the
"long-term semantic memory" layer: it never re-reads already-merged summaries
(the `last_consolidated_at` cursor on the profile makes each run O(new
summaries only), not O(all history)), and it only aggregates data the
summaries already contain — it never fabricates a preference the sessions did
not evidence.

Role in the business flow: called lazily by `MemoryContextProvider` right
before it builds a new session's injected context (so the profile a session
sees is always at most one consolidation run stale), and can equally be called
by a periodic job/scheduler for pre-warming. `UserMemoryProfile` is the only
input `MemoryContextProvider` reads.
"""
from __future__ import annotations

from src.memory.schemas import SessionSummaryRecord, UserMemoryProfile, utcnow_iso
from src.memory.store import MemoryStore, memory_store

_TOP_DATASETS_CAP = 10


class UserMemoryConsolidator:
    """Purpose: single-responsibility merge engine for Tầng 3. Stateless
    besides the `MemoryStore` dependency — every merge decision is a pure
    function of "existing profile" + "new summaries since the cursor".
    """

    def __init__(self, store: MemoryStore | None = None) -> None:
        self._store = store or memory_store

    def consolidate(self, user_id: str) -> UserMemoryProfile:
        """Purpose: merge every `SessionSummaryRecord` created since the
        user's last consolidation into their `UserMemoryProfile`.
        Input: `user_id`.
        Output: the updated (and persisted) `UserMemoryProfile`. If the user
        has no new summaries since the last run, the existing profile is
        returned unchanged (no wasted write); if the user has never been
        consolidated before, an empty baseline profile is created first.
        """
        existing = self._store.get_profile(user_id)
        if existing is None:
            existing = UserMemoryProfile(user_id=user_id, narrative="")

        new_summaries = self._store.list_summaries_for_user(
            user_id, since_iso=existing.last_consolidated_at
        )
        if not new_summaries:
            return existing

        merged = self._merge(existing, new_summaries)
        self._store.upsert_profile(merged)
        return merged

    def _merge(
        self, profile: UserMemoryProfile, new_summaries: list[SessionSummaryRecord]
    ) -> UserMemoryProfile:
        dataset_counts: dict[str, int] = {
            entry["dataset_key"]: entry["count"] for entry in profile.top_datasets
        }
        decisions = dict(profile.rule_decision_pattern)
        decisions.setdefault("approved", 0)
        decisions.setdefault("rejected", 0)
        decisions.setdefault("edited", 0)

        for summary in new_summaries:
            for dataset_key in summary.dataset_keys:
                dataset_counts[dataset_key] = dataset_counts.get(dataset_key, 0) + 1
            decisions["approved"] += summary.rules_approved
            decisions["rejected"] += summary.rules_rejected
            decisions["edited"] += summary.rules_edited

        top_datasets = [
            {"dataset_key": key, "count": count}
            for key, count in sorted(dataset_counts.items(), key=lambda kv: kv[1], reverse=True)
        ][:_TOP_DATASETS_CAP]

        decided = decisions["approved"] + decisions["rejected"]
        approval_rate = round(decisions["approved"] / decided, 4) if decided > 0 else None

        sessions_observed = profile.sessions_observed + len(new_summaries)
        latest_summary = max(new_summaries, key=lambda s: s.created_at)

        return UserMemoryProfile(
            user_id=profile.user_id,
            sessions_observed=sessions_observed,
            top_datasets=top_datasets,
            rule_decision_pattern=decisions,
            approval_rate=approval_rate,
            narrative=self._render_narrative(sessions_observed, top_datasets, decisions, approval_rate),
            last_consolidated_session_id=latest_summary.session_id,
            last_consolidated_at=latest_summary.created_at,
            updated_at=utcnow_iso(),
        )

    @staticmethod
    def _render_narrative(
        sessions_observed: int,
        top_datasets: list[dict[str, object]],
        decisions: dict[str, int],
        approval_rate: float | None,
    ) -> str:
        """Purpose: turn the aggregated statistics into one compact,
        deterministic sentence — no LLM call, so this has zero external
        failure surface and is 100% reproducible from the same inputs, which
        matters because it is injected straight into another LLM's context by
        `MemoryContextProvider`.
        """
        parts = [f"{sessions_observed} phiên làm việc đã ghi nhận."]

        if top_datasets:
            top_str = ", ".join(f"{d['dataset_key']} ({d['count']}x)" for d in top_datasets[:5])
            parts.append(f"Dataset hay thao tác: {top_str}.")

        decided = decisions.get("approved", 0) + decisions.get("rejected", 0)
        if decided > 0 or decisions.get("edited", 0) > 0:
            rate_str = f"{approval_rate * 100:.0f}%" if approval_rate is not None else "N/A"
            parts.append(
                f"Quyết định rule: {decisions.get('approved', 0)} approved, "
                f"{decisions.get('rejected', 0)} rejected, {decisions.get('edited', 0)} edited "
                f"(approval rate {rate_str})."
            )

        return " ".join(parts)


user_memory_consolidator = UserMemoryConsolidator()
