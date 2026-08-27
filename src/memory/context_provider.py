"""
src/memory/context_provider.py

Purpose: Tầng 3 injection — the class that turns a user's consolidated
`UserMemoryProfile` into a compact text block ready to be prepended to an
agent's LLM prompt when a new session starts. This name is deliberately
`MemoryContextProvider`, never `ContextBuilder`, per the naming-collision
lesson recorded in `implementation-notes.md` (2026-08-24 dead-code removal):
`ContextBuilder` already has exactly one definition, in
`src/agents/context.py`, and stays scoped to per-dataset profile context. This
class is scoped to per-user cross-session memory context — a different
responsibility that must never share the same class name.

Role in the business flow: called once at the start of a new session (before
the first LLM call of that session), typically composed alongside
`src.agents.context.ContextBuilder.build_context()` — the two outputs are
concatenated by the caller, not merged internally, so each stays independently
testable and independently owned.
"""
from __future__ import annotations

from src.memory.store import MemoryStore, memory_store
from src.memory.user_memory import UserMemoryConsolidator, user_memory_consolidator

_MAX_NARRATIVE_CHARS = 800


class MemoryContextProvider:
    """Purpose: single-responsibility reader/renderer for Tầng 3 memory.
    Never writes to the store itself (that is `UserMemoryConsolidator`'s job);
    it only triggers a consolidation pass so the context it renders is never
    more than one run stale, then formats the result.
    """

    def __init__(
        self,
        store: MemoryStore | None = None,
        consolidator: UserMemoryConsolidator | None = None,
    ) -> None:
        self._store = store or memory_store
        self._consolidator = consolidator or user_memory_consolidator

    def build_user_memory_context(self, user_id: str, refresh: bool = True) -> str:
        """Purpose: produce the text block to inject into a new session's
        agent context.
        Input: `user_id` — resolved from the authenticated session via
        `SessionIdentityRegistry`, never taken from free-text user input;
        `refresh` — when `True` (default), runs `UserMemoryConsolidator`
        first so any sessions closed since the last read are folded in.
        Output: an empty string for a brand-new user with no session history
        yet (deliberately no fabricated "getting to know you" filler — an
        empty block costs zero prompt tokens and is not a bug), otherwise a
        `[SECURITY NOTICE]`-tagged block containing only the aggregated
        statistics and narrative already computed by `UserMemoryConsolidator`
        — never raw messages, never raw telemetry rows, matching the
        metadata-only guarantee `src/agents/context.py::ContextBuilder`
        enforces for dataset profiles.
        """
        if not user_id:
            return ""

        profile = (
            self._consolidator.consolidate(user_id)
            if refresh
            else self._store.get_profile(user_id)
        )
        if profile is None or profile.sessions_observed == 0:
            return ""

        narrative = profile.narrative.strip()
        if len(narrative) > _MAX_NARRATIVE_CHARS:
            narrative = narrative[: _MAX_NARRATIVE_CHARS - 1].rstrip() + "…"

        lines = [
            "=== USER MEMORY CONTEXT (Tầng 3 — cross-session) ===",
            "[SECURITY NOTICE: Aggregated statistics only. Zero raw messages or raw telemetry attached.]",
            f"Sessions observed: {profile.sessions_observed}",
        ]
        if narrative:
            lines.append(f"Summary: {narrative}")

        return "\n".join(lines)


memory_context_provider = MemoryContextProvider()
