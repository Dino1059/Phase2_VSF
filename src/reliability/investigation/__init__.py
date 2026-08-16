"""
Reliability Investigation Module.
"""

from src.reliability.investigation.c0 import C0DeterministicBaseline

__all__ = [
    "C0DeterministicBaseline",
]


def __getattr__(name: str):
    """Lazy import to avoid duckdb dependency at import time."""
    if name in ("ReliabilityOrchestrator", "InvestigationResult"):
        from src.reliability.investigation import reliability_orchestrator as _mod
        return getattr(_mod, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
