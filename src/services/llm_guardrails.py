"""Central LLM input/output guardrails (Wave 2 Task 2.2)."""
from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel


class GuardVerdict(BaseModel):
    allowed: bool
    reason: str | None = None
    original_chars: int
    estimated_tokens: int
    trimmed: bool = False
    trim_reason: str | None = None


_EV_ID_RE = re.compile(r"^ev[_-][A-Za-z0-9_-]+$", re.IGNORECASE)


def _estimate_tokens(text: str) -> int:
    # ~4 chars/token heuristic — good enough for gatekeeping
    return max(1, (len(text) + 3) // 4) if text else 0


def pre_llm_guard(
    payload: str,
    *,
    task_type: str,
    max_bytes: int = 120_000,
    max_tokens: int = 8000,
) -> GuardVerdict:
    """Reject absurd user bodies (4xx at API). For evidence, trim via context_budget — do not 4xx."""
    text = payload if isinstance(payload, str) else str(payload or "")
    original_chars = len(text)
    estimated = _estimate_tokens(text)
    task = (task_type or "").strip().lower()

    # Evidence / RCA context: trim, never hard-reject
    if task in ("evidence", "rca", "context", "rule_proposal"):
        if len(text.encode("utf-8")) > max_bytes or estimated > max_tokens:
            # Caller should use context_budget; we only flag trim needed
            return GuardVerdict(
                allowed=True,
                reason=None,
                original_chars=original_chars,
                estimated_tokens=estimated,
                trimmed=True,
                trim_reason="payload exceeds budget; trim via context_budget",
            )
        return GuardVerdict(
            allowed=True,
            original_chars=original_chars,
            estimated_tokens=estimated,
        )

    # Chat / generic user bodies: hard reject absurd sizes
    if len(text.encode("utf-8")) > max_bytes:
        return GuardVerdict(
            allowed=False,
            reason=f"payload exceeds max_bytes={max_bytes}",
            original_chars=original_chars,
            estimated_tokens=estimated,
        )
    if estimated > max_tokens * 4:  # absurd overshoot vs soft token cap
        return GuardVerdict(
            allowed=False,
            reason=f"estimated_tokens {estimated} far exceeds max_tokens={max_tokens}",
            original_chars=original_chars,
            estimated_tokens=estimated,
        )
    return GuardVerdict(
        allowed=True,
        original_chars=original_chars,
        estimated_tokens=estimated,
    )


def post_llm_guard(
    obj: dict,
    *,
    required_keys: list[str],
    allowed_classifications: list[str] | None = None,
) -> GuardVerdict:
    """Schema keys present; confidence in [0,1] if present; evidence IDs look like ev_*/ev-*."""
    payload = obj if isinstance(obj, dict) else {}
    blob = str(payload)
    original_chars = len(blob)
    estimated = _estimate_tokens(blob)
    missing = [k for k in (required_keys or []) if k not in payload]
    if missing:
        return GuardVerdict(
            allowed=False,
            reason=f"missing required keys: {', '.join(missing)}",
            original_chars=original_chars,
            estimated_tokens=estimated,
        )

    if "confidence" in payload:
        try:
            conf = float(payload["confidence"])
            if conf < 0.0 or conf > 1.0:
                return GuardVerdict(
                    allowed=False,
                    reason=f"confidence {conf} out of [0,1]",
                    original_chars=original_chars,
                    estimated_tokens=estimated,
                )
        except (TypeError, ValueError):
            return GuardVerdict(
                allowed=False,
                reason="confidence is not numeric",
                original_chars=original_chars,
                estimated_tokens=estimated,
            )

    if allowed_classifications is not None and "classification" in payload:
        cls = str(payload.get("classification") or "")
        if cls and cls not in allowed_classifications:
            return GuardVerdict(
                allowed=False,
                reason=f"classification '{cls}' not in allowed set",
                original_chars=original_chars,
                estimated_tokens=estimated,
            )

    evidence = payload.get("evidence_ids") or payload.get("evidence") or []
    if isinstance(evidence, list):
        for eid in evidence:
            s = str(eid)
            if s and not _EV_ID_RE.match(s):
                return GuardVerdict(
                    allowed=False,
                    reason=f"evidence id '{s}' does not look like ev_*/ev-*",
                    original_chars=original_chars,
                    estimated_tokens=estimated,
                )

    return GuardVerdict(
        allowed=True,
        original_chars=original_chars,
        estimated_tokens=estimated,
    )
