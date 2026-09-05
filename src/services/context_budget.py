"""Token-bounded evidence selection and A1 message compaction."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

TaskType = Literal["rca_c1", "rca_a1", "rule_proposal", "chat"]

DEFAULT_LIMITS: dict[str, int] = {
    "rca_c1": 3500,
    "rca_a1": 6000,
    "rule_proposal": 2500,
    "chat": 2000,
}

_CATEGORY_CAPS: dict[int, int] = {
    1: 8,
    2: 8,
    3: 5,
    4: 3,
    5: 2,
    6: 3,
    7: 4,
}

_NAMED_CAPS = {
    "signals": 5,
    "recent_changes": 3,
    "violations": 5,
    "profile": 3,
    "historical": 4,
    "contradictory": 2,
}


class ContextEnvelope(BaseModel):
    task_type: TaskType
    rendered_context: str
    estimated_input_tokens: int
    hard_limit_tokens: int
    evidence_ids_included: list[str] = Field(default_factory=list)
    evidence_ids_dropped: list[str] = Field(default_factory=list)
    truncation_applied: bool = False
    truncation_reason: str | None = None


def estimate_tokens(text: str) -> int:
    """Deterministic: max(1, ceil(len(text) / 4)) for ASCII; do not call a tokenizer."""
    if not text:
        return 1
    return max(1, (len(text) + 3) // 4)


def _item_text(item: dict) -> str:
    return str(item.get("text") or item.get("summary") or "")


def _item_id(item: dict, idx: int) -> str:
    return str(item.get("evidence_id") or f"ev_anon_{idx}")


def _rank(item: dict) -> int:
    try:
        return int(item.get("rank_bucket") or 7)
    except (TypeError, ValueError):
        return 7


def select_evidence(
    items: list[dict],
    *,
    task_type: TaskType,
    hard_limit_tokens: int | None = None,
    must_keep_ids: list[str] | None = None,
) -> ContextEnvelope:
    """Rank evidence, apply category caps, then trim to token budget."""
    limit = hard_limit_tokens if hard_limit_tokens is not None else DEFAULT_LIMITS.get(task_type, 3500)
    must_keep = set(must_keep_ids or [])

    normalized: list[tuple[int, int, dict]] = []
    for i, raw in enumerate(items or []):
        if not isinstance(raw, dict):
            continue
        item = dict(raw)
        if item.get("contradictory") and not item.get("rank_bucket"):
            item["rank_bucket"] = 5
        normalized.append((_rank(item), i, item))
    normalized.sort(key=lambda t: (t[0], t[1]))

    bucket_counts: dict[int, int] = {k: 0 for k in range(1, 8)}
    selected: list[dict] = []
    dropped: list[dict] = []

    contra_selected = 0
    for rank, _i, item in normalized:
        eid = _item_id(item, _i)
        is_contra = bool(item.get("contradictory")) or rank == 5
        if eid in must_keep or (is_contra and contra_selected < _NAMED_CAPS["contradictory"]):
            selected.append(item)
            if is_contra:
                contra_selected += 1
            bucket_counts[rank] = bucket_counts.get(rank, 0) + 1

    selected_ids = {_item_id(it, j) for j, it in enumerate(selected)}

    for rank, _i, item in normalized:
        eid = _item_id(item, _i)
        if eid in selected_ids:
            continue
        is_contra = bool(item.get("contradictory")) or rank == 5
        if is_contra:
            dropped.append(item)
            continue
        if rank == 3:
            cap = _NAMED_CAPS["signals"]
        elif rank == 4:
            cap = _NAMED_CAPS["recent_changes"]
        elif rank == 6:
            cap = _NAMED_CAPS["profile"]
        elif rank == 7:
            cap = _NAMED_CAPS["historical"]
        elif rank in (1, 2):
            cap = max(_CATEGORY_CAPS.get(rank, 4), 5)
        else:
            cap = _CATEGORY_CAPS.get(rank, 4)

        if bucket_counts.get(rank, 0) >= cap:
            dropped.append(item)
            continue
        selected.append(item)
        selected_ids.add(eid)
        bucket_counts[rank] = bucket_counts.get(rank, 0) + 1

    def render(parts: list[dict]) -> str:
        lines = []
        for it in parts:
            eid = str(it.get("evidence_id") or "")
            lines.append(f"[{eid}] {_item_text(it)}")
        return "\n".join(lines)

    selected.sort(key=lambda it: (_rank(it), str(it.get("evidence_id") or "")))
    truncation_applied = bool(dropped)
    truncation_reason = "category_cap" if dropped else None

    while selected:
        rendered = render(selected)
        tokens = estimate_tokens(rendered)
        if tokens <= limit:
            break
        drop_idx = None
        for idx in range(len(selected) - 1, -1, -1):
            eid = str(selected[idx].get("evidence_id") or "")
            if eid in must_keep:
                continue
            if _rank(selected[idx]) >= 6:
                drop_idx = idx
                break
        if drop_idx is None:
            for idx in range(len(selected) - 1, -1, -1):
                eid = str(selected[idx].get("evidence_id") or "")
                if eid not in must_keep:
                    drop_idx = idx
                    break
        if drop_idx is None:
            break
        dropped.append(selected.pop(drop_idx))
        truncation_applied = True
        truncation_reason = "token_budget"

    rendered = render(selected)
    tokens = estimate_tokens(rendered)
    if tokens > limit and selected:
        trimmed_lines = []
        budget_chars = max(4, limit * 4)
        used = 0
        for it in selected:
            eid = str(it.get("evidence_id") or "")
            body = _item_text(it)
            line = f"[{eid}] {body}"
            if used + len(line) > budget_chars:
                remain = max(0, budget_chars - used - len(f"[{eid}] ") - 1)
                line = f"[{eid}] {body[:remain]}"
                trimmed_lines.append(line)
                truncation_applied = True
                truncation_reason = truncation_reason or "token_budget"
                break
            trimmed_lines.append(line)
            used += len(line) + 1
        rendered = "\n".join(trimmed_lines)
        tokens = estimate_tokens(rendered)

    if tokens > limit:
        rendered = rendered[: limit * 4]
        tokens = estimate_tokens(rendered)
        truncation_applied = True
        truncation_reason = truncation_reason or "token_budget"

    included_ids = [str(it.get("evidence_id")) for it in selected if it.get("evidence_id")]
    dropped_ids = [str(it.get("evidence_id")) for it in dropped if it.get("evidence_id")]
    dropped_ids = [d for d in dropped_ids if d not in set(included_ids)]

    return ContextEnvelope(
        task_type=task_type,
        rendered_context=rendered,
        estimated_input_tokens=min(tokens, limit) if truncation_applied else tokens,
        hard_limit_tokens=limit,
        evidence_ids_included=included_ids,
        evidence_ids_dropped=dropped_ids,
        truncation_applied=truncation_applied,
        truncation_reason=truncation_reason,
    )


def compact_a1_messages(
    messages: list[dict],
    *,
    incident_capsule: str,
    hypothesis_state: str,
    evidence_ids: list[str],
    hard_limit_tokens: int,
) -> ContextEnvelope:
    """Compact A1 chat messages under a hard token limit."""
    system_parts: list[str] = []
    observations: list[str] = []
    other: list[str] = []
    for msg in messages or []:
        if not isinstance(msg, dict):
            continue
        role = msg.get("role") or "user"
        content = str(msg.get("content") or "")
        if role == "system":
            system_parts.append(content)
        elif role == "user" and content.startswith("Observation:"):
            observations.append(content)
        else:
            other.append(f"{role}: {content}")

    older = observations[:-2]
    recent = observations[-2:]
    historical_ledger = ""
    if older:
        historical_ledger = (
            f"Historical observations summarized ({len(older)}): "
            + " | ".join(o[:80] for o in older)
        )

    evidence_ledger = "Evidence IDs: " + ", ".join(evidence_ids or [])
    parts = [
        "\n\n".join(system_parts),
        f"Incident capsule:\n{incident_capsule}",
        f"Hypothesis state:\n{hypothesis_state}",
        evidence_ledger,
    ]
    if historical_ledger:
        parts.append(historical_ledger)
    parts.extend(recent)
    if other:
        parts.append("\n".join(other[-2:]))

    rendered = "\n\n".join(p for p in parts if p)
    tokens = estimate_tokens(rendered)
    truncation_applied = False
    truncation_reason = None
    dropped: list[str] = []

    if tokens > hard_limit_tokens and historical_ledger:
        parts = [p for p in parts if p != historical_ledger]
        dropped.append("historical_ledger")
        rendered = "\n\n".join(p for p in parts if p)
        tokens = estimate_tokens(rendered)
        truncation_applied = True
        truncation_reason = "dropped_historical_ledger"

    if tokens > hard_limit_tokens:
        capsule_block = f"Incident capsule:\n{incident_capsule}"
        max_chars = hard_limit_tokens * 4
        head = (
            f"{capsule_block}\n\n{evidence_ledger}\n\n"
            f"Hypothesis state:\n{hypothesis_state}"
        )
        remain = max(0, max_chars - len(head) - 1)
        tail = "\n\n".join(recent)[:remain]
        rendered = head + ("\n\n" + tail if tail else "")
        tokens = estimate_tokens(rendered)
        truncation_applied = True
        truncation_reason = "insufficient_evidence_after_compaction"

    if tokens > hard_limit_tokens:
        rendered = rendered[: hard_limit_tokens * 4]
        tokens = estimate_tokens(rendered)
        truncation_applied = True
        truncation_reason = "insufficient_evidence_after_compaction"

    return ContextEnvelope(
        task_type="rca_a1",
        rendered_context=rendered,
        estimated_input_tokens=min(tokens, hard_limit_tokens),
        hard_limit_tokens=hard_limit_tokens,
        evidence_ids_included=list(evidence_ids or []),
        evidence_ids_dropped=dropped,
        truncation_applied=truncation_applied,
        truncation_reason=truncation_reason,
    )
