from eval.eval_detectors import run_detector_evaluation, _safe_f1


def test_safe_f1_zero():
    assert _safe_f1(0.0, 0.0) == 0.0


def test_safe_f1_normal():
    assert _safe_f1(1.0, 1.0) == 1.0
    assert _safe_f1(0.8, 0.8) == 0.8


def test_run_detector_evaluation():
    results = run_detector_evaluation()

    assert "l1_evaluation" in results
    assert "l2_l4_evaluation" in results

    l1 = results["l1_evaluation"]
    assert 0.0 <= l1["precision"] <= 1.0
    assert 0.0 <= l1["recall"] <= 1.0
    assert 0.0 <= l1["f1_score"] <= 1.0
    assert l1["p95_latency_ms"] >= 0.0
    assert isinstance(l1["sla_target_passed"], bool)

    l2_l4 = results["l2_l4_evaluation"]
    assert 0.0 <= l2_l4["precision"] <= 1.0
    assert 0.0 <= l2_l4["recall"] <= 1.0
    assert 0.0 <= l2_l4["f1_score"] <= 1.0
    assert l2_l4["fp_per_entity_day"] >= 0.0
