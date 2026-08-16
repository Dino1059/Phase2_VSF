import asyncio

from fastapi.testclient import TestClient

import src.api.pipeline as pipeline
from src.main import app


def test_pipeline_trigger_persists_result_and_exposes_it(monkeypatch):
    async def fake_background(run_id, table_name):
        pipeline._update_pipeline_run(
            run_id,
            "completed",
            {
                "run_id": run_id,
                "dataset_key": table_name,
                "status": "completed",
                "rca": {"nodes": [], "edges": [], "incidents": []},
                "telemetry": {"series": []},
                "split": {"clean": [], "quarantine": []},
                "manifest": {"hash": "test-manifest", "algorithm": "SHA-256"},
            },
        )

    monkeypatch.setattr(pipeline, "_run_pipeline_async", fake_background)
    client = TestClient(app, headers={"X-User-Role": "Admin"})

    trigger = client.post("/api/v1/pipeline/trigger?table_name=pipeline_result_test")
    assert trigger.status_code == 200
    run_id = trigger.json()["run_id"]

    result = client.get(f"/api/v1/pipeline/result/{run_id}")
    for _ in range(10):
        if result.status_code == 200:
            break
        asyncio.run(asyncio.sleep(0.01))
        result = client.get(f"/api/v1/pipeline/result/{run_id}")
    assert result.status_code == 200
    payload = result.json()
    assert payload["status"] == "completed"
    assert payload["manifest"]["hash"] == "test-manifest"
    assert payload["dataset_key"] == "pipeline_result_test"
