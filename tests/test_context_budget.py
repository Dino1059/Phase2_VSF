from src.services.context_budget import select_evidence, estimate_tokens, compact_a1_messages


def test_xl_noise_stays_under_budget():
    items = [{"evidence_id": "ev_rel_1", "rank_bucket": 1, "text": "soc < 0 on VIN1", "contradictory": False}]
    items += [
        {"evidence_id": f"ev_noise_{i}", "rank_bucket": 7, "text": "weather " + ("z" * 80), "contradictory": False}
        for i in range(3000)
    ]
    env = select_evidence(items, task_type="rca_c1", hard_limit_tokens=3500)
    assert env.estimated_input_tokens <= 3500
    assert "ev_rel_1" in env.evidence_ids_included
    assert env.truncation_applied
    assert len(env.evidence_ids_dropped) >= 1000


def test_keeps_contradiction_slot():
    items = [
        {"evidence_id": "ev_a", "rank_bucket": 1, "text": "main", "contradictory": False},
        {"evidence_id": "ev_c", "rank_bucket": 5, "text": "contradicts main", "contradictory": True},
    ] + [{"evidence_id": f"ev_n{i}", "rank_bucket": 7, "text": "n" * 200, "contradictory": False} for i in range(200)]
    env = select_evidence(items, task_type="rca_c1", hard_limit_tokens=800)
    assert "ev_c" in env.evidence_ids_included


def test_estimate_tokens_not_char_count():
    assert estimate_tokens("abcd") == 1
    assert estimate_tokens("a" * 8) == 2
