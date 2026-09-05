"""Wave 2 Task 2.3 — structured workflow trace events without CoT product field."""
from __future__ import annotations

from src.api.traces import (
    WorkflowTraceEvent,
    normalize_trace_step,
    to_workflow_trace_event,
)


def _base_row(
    *,
    thought="legacy thought text",
    action="profile_dataset",
    tool_name="profile_dataset",
    tokens=42,
    duration_ms=100,
):
    # Matches _TRACE_BASE_COLS + extras layout used by normalize_trace_step
    return (
        1,  # step_index
        thought,
        action,
        tool_name,
        '{"dataset_key":"trips"}',
        '{"total_rows":10,"provider":"openrouter","model":"gpt-4o-mini","fallback_depth":1,"validation_status":"pass","context_items_included":3,"context_items_dropped":2,"input_tokens_estimated":80,"output_tokens":12}',
        "Sampled 10 rows",
        tokens,
        duration_ms,
        "2026-09-05T10:00:00",
        "canonical_react_engine",
        "done",
        "Profile dataset",
        "Profiles columns",
        None,  # safe_summary null → map from thought
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
    )


def test_workflow_trace_event_model_requires_safe_summary():
    ev = WorkflowTraceEvent(
        trace_id="tr_1",
        stage="profile",
        actor="PROFILER",
        action="profile_dataset",
        status="done",
        started_at="2026-09-05T10:00:00",
        safe_summary="Profiled 10 rows",
    )
    assert ev.safe_summary == "Profiled 10 rows"
    assert ev.fallback_depth == 0


def test_normalize_maps_legacy_thought_to_safe_summary():
    card = normalize_trace_step(_base_row())
    assert card["safe_summary"] == "legacy thought text"
    assert "thought" not in card
    assert card["provider"] == "openrouter"
    assert card["model"] == "gpt-4o-mini"
    assert card["fallback_depth"] == 1
    assert card["validation_status"] == "pass"
    assert card["context_items_included"] == 3
    assert card["context_items_dropped"] == 2
    assert card["stage"]


def test_normalize_prefers_safe_summary_column():
    row = list(_base_row())
    row[14] = "new safe summary"
    card = normalize_trace_step(tuple(row))
    assert card["safe_summary"] == "new safe summary"


def test_to_workflow_trace_event_no_thought_field():
    card = normalize_trace_step(_base_row())
    ev = to_workflow_trace_event(card, trace_id="tr_x", session_id="s1")
    dumped = ev.model_dump()
    assert "thought" not in dumped
    assert dumped["safe_summary"]
    assert dumped["provider"] == "openrouter"
