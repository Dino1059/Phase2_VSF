import pytest
from fastapi import HTTPException

from backend.api.auth_routes import LoginRequest, create_jwt_token, login
from backend.sod.service import SodService


class _CursorContext:
    def __init__(self, cursor):
        self.cursor = cursor

    def __enter__(self):
        return self.cursor

    def __exit__(self, *_args):
        return False


class _Connection:
    def __init__(self, cursor):
        self._cursor = cursor

    def cursor(self, **_kwargs):
        return _CursorContext(self._cursor)


def test_production_requires_explicit_jwt_secret(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.delenv("JWT_SECRET", raising=False)

    with pytest.raises(RuntimeError, match="JWT_SECRET"):
        create_jwt_token({"sub": "user-1"})


def test_production_login_rejects_invalid_password(monkeypatch):
    class Cursor:
        def execute(self, query, params):
            assert "crypt(%s, u.password_hash)" in query
            assert params == ("wrong", "wrong", "alice")

        def fetchone(self):
            return {
                "id": "user-1",
                "username": "alice",
                "full_name": "Alice",
                "session_version": 1,
                "password_hash": "stored-hash",
                "password_valid": False,
            }

    monkeypatch.setenv("ENVIRONMENT", "production")
    with pytest.raises(HTTPException) as exc_info:
        login(LoginRequest(username="Alice", password="wrong"), _Connection(Cursor()))

    assert exc_info.value.status_code == 401


def test_decision_step_must_belong_to_ticket():
    class Cursor:
        def execute(self, *_args):
            pass

        def fetchone(self):
            return {"id": "step-1", "ticket_id": "ticket-a", "status": "CURRENT"}

    with pytest.raises(HTTPException) as exc_info:
        SodService.decide_step(
            ticket_id="ticket-b",
            step_id="step-1",
            actor_id="user-1",
            outcome="APPROVE",
            comment="",
            conn=_Connection(Cursor()),
        )

    assert exc_info.value.status_code == 404
    assert "không thuộc" in exc_info.value.detail
