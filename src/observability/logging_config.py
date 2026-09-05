from __future__ import annotations

import logging
import sys

from .formatters import DataTrustJsonFormatter

_HANDLER_MARKER = "datatrust_runtime_handler"


def configure_logging(level: str = "INFO") -> None:
    """Configure runtime logs once; output stays on stdout for container collection."""
    root = logging.getLogger()
    normalized = str(level or "INFO").upper()
    if normalized not in logging.getLevelNamesMapping():
        normalized = "INFO"
    root.setLevel(normalized)
    if any(getattr(handler, _HANDLER_MARKER, False) for handler in root.handlers):
        return

    handler = logging.StreamHandler(sys.stdout)
    setattr(handler, _HANDLER_MARKER, True)
    handler.setFormatter(DataTrustJsonFormatter())
    root.addHandler(handler)
