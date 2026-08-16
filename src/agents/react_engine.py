"""Deprecated module. Redirecting exports to canonical orchestrator engine in src.orchestrator.engine."""

import warnings
from pydantic import BaseModel
from src.orchestrator.engine import DecisionRecord, ReActEngine, ReActResult, ReActStep

warnings.warn(
    "src.agents.react_engine is deprecated. Import ReActEngine from src.orchestrator.engine instead.",
    DeprecationWarning,
    stacklevel=2,
)


class StepLog(BaseModel):
    step_idx: int
    thought: str
    action: str
    observation: str


__all__ = ["ReActEngine", "ReActStep", "ReActResult", "DecisionRecord", "StepLog"]
