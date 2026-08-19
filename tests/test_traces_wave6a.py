from src.api.traces import normalize_trace_step


def test_normalize_trace_step_aliases_and_honest_summary():
    row = (
        1,
        "Thought should not become Done",
        "profile_dataset",
        "profile_dataset",
        '{"dataset_key": "vingroup_pilot"}',
        '{"total_rows": 50000, "columns_count": 10, "status": "ok"}',
        "Sampled 50000 rows",
        120,
        640,
        "2026-08-19T10:00:00",
        "canonical_react_engine",
    )
    card = normalize_trace_step(row)
    assert card["tool"] == "profile_dataset"
    assert card["tokens"] == 120
    assert card["actor_kind"] == "C1_AI"
    assert "50000" in card["summary_done"] or "Sampled" in card["summary_done"]
    assert "12 anomalies" not in card["summary_done"]
    assert card.get("thought") in (None, "")


def test_normalize_empty_output_does_not_invent_counts():
    row = (2, None, "register_dataset", "register_dataset", None, None, None, None, None, None, None)
    card = normalize_trace_step(row)
    assert card["summary_done"] == "register_dataset completed"
    assert card["tokens"] is None
    assert "SHA-256" not in card["summary_done"]
