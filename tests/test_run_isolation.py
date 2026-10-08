"""
Unit tests for Strict Run Isolation & Leakage Prevention in DataTrust OS.
Verifies that:
1. run_id is mandatory (400 MISSING_RUN_ID)
2. message cannot be empty (400 EMPTY_MESSAGE)
3. Nonexistent run_id returns 404 RUN_NOT_FOUND
4. Finding not belonging to the specified run_id returns 404 FINDING_NOT_FOUND_IN_RUN (no fallback)
5. Session bound to one run cannot be reused for a different run (400 SESSION_RUN_MISMATCH)
"""

import pytest
import uuid
from fastapi.testclient import TestClient
from backend.api.main import app
from backend.ai.services.chat_session_manager import session_manager

client = TestClient(app)


def test_missing_run_id_returns_400():
    res = client.post("/api/agent/chat", json={
        "run_id": "",
        "message": "Kiểm tra finding FND-001"
    })
    assert res.status_code == 400
    detail = res.json().get("detail", {})
    assert detail.get("code") == "MISSING_RUN_ID"


def test_whitespace_run_id_returns_400():
    res = client.post("/api/agent/chat", json={
        "run_id": "   ",
        "message": "Kiểm tra finding FND-001"
    })
    assert res.status_code == 400
    detail = res.json().get("detail", {})
    assert detail.get("code") == "MISSING_RUN_ID"


def test_empty_message_returns_400():
    res = client.post("/api/agent/chat", json={
        "run_id": "RUN-20261007-001",
        "message": "   "
    })
    assert res.status_code == 400
    detail = res.json().get("detail", {})
    assert detail.get("code") == "EMPTY_MESSAGE"


def test_nonexistent_run_id_returns_404():
    fake_run_id = f"NONEXISTENT-RUN-{uuid.uuid4().hex[:8]}"
    res = client.post("/api/agent/chat", json={
        "run_id": fake_run_id,
        "message": "Tình hình lần chạy này thế nào?"
    })
    assert res.status_code == 404
    detail = res.json().get("detail", {})
    assert detail.get("code") == "RUN_NOT_FOUND"


def test_finding_not_in_run_returns_404_no_fallback(monkeypatch):
    """
    Enforces that querying finding_id not belonging to run_id strictly errors with 404 FINDING_NOT_FOUND_IN_RUN.
    No cross-run fallback permitted.
    """
    target_run_id = "run-test-isolation-01"
    target_finding_id = "FND-RUN-ISOLATED-01"

    class MockCursor:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def execute(self, query, params=None):
            pass
        def fetchone(self):
            # Return finding row ONLY if both finding_id and run_id match
            return None

    class MockConn:
        def cursor(self, cursor_factory=None):
            return MockCursor()
        def close(self):
            pass

    monkeypatch.setattr("database.profiler_engine.get_db_connection", lambda: MockConn())

    res = client.post("/api/agent/chat", json={
        "run_id": target_run_id,
        "finding_id": target_finding_id,
        "message": f"Giải thích vi phạm {target_finding_id}"
    })
    assert res.status_code == 404
    detail = res.json().get("detail", {})
    assert detail.get("code") == "FINDING_NOT_FOUND_IN_RUN"


def test_session_run_mismatch_returns_400():
    """
    Ensures session_id bound to RUN-A cannot be reused with RUN-B.
    """
    session_id = f"sess_mismatch_test_{uuid.uuid4().hex[:8]}"
    run_a = "run-test-A"
    run_b = "run-test-B"

    # 1. Bind to run_a
    assert session_manager.verify_and_bind_session(session_id, run_a) is True

    # 2. Try to send with run_b
    res = client.post("/api/agent/chat", json={
        "run_id": run_b,
        "session_id": session_id,
        "message": "Xin chào AI"
    })
    assert res.status_code == 400
    detail = res.json().get("detail", {})
    assert detail.get("code") == "SESSION_RUN_MISMATCH"
