"""Ngan GT pack must emit real scores for every required metric. LLM-judge off."""
from src.reliability.benchmark.ngan_gt_eval import evaluate_ngan_gt


def test_ngan_gt_metrics_are_real_scores():
    result = evaluate_ngan_gt()
    assert result["pack"]["llm_judge"] == "off"
    assert result["pack"]["incidents"] == 14
    for flow in ("batch", "realtime"):
        s = result[flow]
        assert s["implemented"] is True
        det = s["detection"]
        for key in ("precision", "recall", "f1"):
            assert isinstance(det[key], float)
            assert 0.0 <= det[key] <= 1.0
        assert isinstance(s["location"]["accuracy"], float)
        assert isinstance(s["time_window"]["accuracy"], float)
        assert s["time_window"]["unit"] == "day_idx"
        assert isinstance(s["rca"]["top1"], float)
        assert isinstance(s["rca"]["top3"], float)
        assert isinstance(s["hallucination"]["false_alarms"], int)
        assert s["hallucination"]["weather_inventions"] == 0
        assert "adapter TBD" not in str(s).lower()
    unans = result["unanswerable"]
    assert unans["llm_judge"] == "off"
    assert isinstance(unans["accuracy"], float)
    assert unans["total"] >= 1
    frozen = result["rca_frozen_cases"]
    assert frozen["available"] is True
    assert frozen["n"] == 13
    assert isinstance(frozen["top1"], float)
    # Realtime should catch day-gated L4 families; INC_010 F13 must match parquet SoT.
    assert result["blockers"] == []
    assert result["realtime"]["detection"]["tp"] >= 11
    assert result["realtime"]["detection"]["f1"] > 0


def test_evaluation_gt_endpoint():
    from fastapi.testclient import TestClient
    from src.main import app
    client = TestClient(app, headers={"X-User-Role": "Admin"})
    res = client.get("/api/v1/evaluation/gt")
    assert res.status_code == 200
    body = res.json()
    assert body["pack"]["llm_judge"] == "off"
    assert "precision" in body["batch"]["detection"]
    assert "top1" in body["batch"]["rca"]
    assert "accuracy" in body["unanswerable"]
    assert "adapter TBD" not in res.text.lower()
