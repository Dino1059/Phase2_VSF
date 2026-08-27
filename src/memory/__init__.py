"""
src/memory/__init__.py

Purpose: public surface of the Multi-tier User Memory module. Other packages
(the agent orchestrator, chat entrypoints, `src/main.py`) should import from
`src.memory` rather than reaching into individual submodules, so the internal
file layout (`identity.py`, `state_tracker.py`, `session_summarizer.py`,
`user_memory.py`, `context_provider.py`, `store.py`, `routes.py`) can evolve
without breaking callers.

Layer map (matches the plan discussed and confirmed in
`implementation-notes.md`):
  Workstream A — session identity:      `identity.py`      (SessionIdentityRegistry)
  Workstream B — session state/steps:   `state_tracker.py`  (SessionStateTracker)
  Tầng 2        — session summaries:     `session_summarizer.py` (SessionSummarizer)
  Tầng 3        — user memory:           `user_memory.py`    (UserMemoryConsolidator)
                                          `context_provider.py` (MemoryContextProvider)
  Workstream C  — transparency & control: `routes.py`        (memory_router)
"""
from src.memory.context_provider import MemoryContextProvider, memory_context_provider
from src.memory.identity import SessionIdentityRegistry, session_identity_registry
from src.memory.routes import memory_router
from src.memory.schemas import (
    MemoryEditRequest,
    SessionStateRecord,
    SessionStatus,
    SessionStep,
    SessionSummaryRecord,
    UserMemoryProfile,
)
from src.memory.session_summarizer import SessionSummarizer, session_summarizer
from src.memory.state_tracker import SessionStateTracker, session_state_tracker
from src.memory.store import MemoryStore, memory_store
from src.memory.user_memory import UserMemoryConsolidator, user_memory_consolidator

__all__ = [
    "MemoryContextProvider",
    "memory_context_provider",
    "SessionIdentityRegistry",
    "session_identity_registry",
    "memory_router",
    "MemoryEditRequest",
    "SessionStateRecord",
    "SessionStatus",
    "SessionStep",
    "SessionSummaryRecord",
    "UserMemoryProfile",
    "SessionSummarizer",
    "session_summarizer",
    "SessionStateTracker",
    "session_state_tracker",
    "MemoryStore",
    "memory_store",
    "UserMemoryConsolidator",
    "user_memory_consolidator",
]
