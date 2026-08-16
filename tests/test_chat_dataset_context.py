from types import SimpleNamespace

import src.api.routes as routes
from src.main import app
from fastapi.testclient import TestClient


def test_chat_passes_selected_dataset_context_to_react_engine(monkeypatch):
    captured = {}

    class FakeEngine:
        def __init__(self, **kwargs):
            pass

        def run(self, task, context=None):
            captured["task"] = task
            captured["context"] = context
            return SimpleNamespace(steps=[], final_answer="ok", status="completed")

    monkeypatch.setattr(routes, "BoundedReActEngine", FakeEngine)
    client = TestClient(app, headers={"X-User-Role": "Admin"})

    response = client.post(
        "/api/v1/chat/send",
        json={
            "message": "Profile this dataset",
            "session_id": "dataset:uploaded_sample",
            "dataset_key": "uploaded_sample",
        },
    )

    assert response.status_code == 200
    assert captured["context"] == {"dataset_key": "uploaded_sample"}
    assert "dataset_key='uploaded_sample'" in captured["task"]

    history = client.get("/api/v1/chat/history", params={"session_id": "dataset:uploaded_sample"})
    assert history.status_code == 200
    user_messages = [m for m in history.json()["messages"] if m["type"] == "user"]
    assert user_messages[-1]["metadata"] == {"dataset_key": "uploaded_sample"}
