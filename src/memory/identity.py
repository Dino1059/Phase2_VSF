"""
src/memory/identity.py

Purpose: Workstream A — bind a chat/investigation session to the authenticated
user that owns it. `messages`/`session_id` in `src/services/conversation_store.py`
never carried a `user_id` before this module; every other tier of the memory
system (Workstream B step tracking, Tầng 2/3 summarization and consolidation)
needs that link to know *whose* memory a session belongs to, so this is the
foundation the rest of `src/memory/` is built on.

Role in the business flow: the API layer (or the chat entrypoint that already
resolves `request.state.user_id`/`request.state.user_role` via
`src/middleware/auth.py`) calls `SessionIdentityRegistry.bind()` once per new
session_id. Everything downstream (`SessionStateTracker`, the Workstream C
transparency API) calls `resolve()` to recover the owner instead of trusting a
caller-supplied `user_id` on every call.
"""
from __future__ import annotations

from src.memory.store import MemoryStore, memory_store


class SessionIdentityRegistry:
    """Purpose: thin, single-responsibility wrapper around `MemoryStore`'s
    identity table. Kept as its own class (rather than folded into
    `SessionStateTracker`) so Workstream A stays independently testable and
    independently reusable by any future caller that only needs identity
    resolution, not full step tracking.
    """

    def __init__(self, store: MemoryStore | None = None) -> None:
        self._store = store or memory_store

    def bind(self, session_id: str, user_id: str, role: str | None = None) -> None:
        """Purpose: register (or re-register) which user owns a session.
        Input: `session_id` — the chat/workspace session id already used by
        `conversation_store`; `user_id`/`role` — resolved from the signed JWT
        by `src/middleware/auth.py` (`request.state.user_id`,
        `request.state.user_role`), never trusted from client-supplied body.
        Output: none. Idempotent — binding the same session_id again simply
        overwrites the previous owner, which only matters for the (rare and
        already-illegal-by-JWT) case of a session being reused across users.
        """
        if not session_id or not user_id:
            raise ValueError("session_id and user_id are required to bind session identity")
        self._store.bind_identity(session_id, user_id, role)

    def resolve(self, session_id: str) -> tuple[str, str | None] | None:
        """Purpose: recover `(user_id, role)` for a session_id.
        Output: `None` if the session was never bound (e.g. a session_id that
        predates this module, or one from an untracked flow) — callers must
        treat that as "no owner known", never guess a default user.
        """
        record = self._store.resolve_identity(session_id)
        if record is None:
            return None
        return record["user_id"], record.get("role")


session_identity_registry = SessionIdentityRegistry()
