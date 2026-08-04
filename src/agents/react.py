"""Deprecated module. Redirecting exports to canonical orchestrator engine in src.orchestrator.engine."""

import warnings
from src.orchestrator.engine import DecisionRecord, ReActEngine, ReActResult, ReActStep

warnings.warn(
    "src.agents.react is deprecated. Import ReActEngine from src.orchestrator.engine instead.",
    DeprecationWarning,
    stacklevel=2,
)

BoundedReActEngine = ReActEngine

__all__ = ["ReActEngine", "BoundedReActEngine", "ReActStep", "ReActResult", "DecisionRecord"]
