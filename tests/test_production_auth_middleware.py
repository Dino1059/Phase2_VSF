from fastapi import Request
from fastapi.testclient import TestClient

import backend.api.main as main_module
from backend.api.auth_routes import create_jwt_token


class _Cursor:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, _query, params):
        assert params == ("user-1", 7, "VIEWER")

    def fetchone(self):
        return ("viewer.alice",)


class _Connection:
    def cursor(self):
        return _Cursor()

    def close(self):
        pass


def test_bearer_identity_overrides_untrusted_legacy_headers(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("JWT_SECRET", "a" * 32)
    monkeypatch.setenv("DATATRUST_API_USER", "outer")
    monkeypatch.setenv("DATATRUST_API_PASSWORD", "outer-secret")
    monkeypatch.setattr(main_module, "auth_db_connection", lambda: _Connection())

    path = "/_middleware-test/verified-identity"

    @main_module.app.get(path)
    def verified_identity(request: Request):
        return {
            "user": request.headers.get("X-User"),
            "role": request.headers.get("X-User-Role"),
        }

    token = create_jwt_token({
        "sub": "user-1",
        "active_role": "VIEWER",
        "session_version": 7,
    })
    response = TestClient(main_module.app).get(
        path,
        headers={
            "Authorization": f"Bearer {token}",
            "X-User": "attacker",
            "X-User-Role": "ADMIN",
        },
    )

    assert response.status_code == 200
    assert response.json() == {"user": "viewer.alice", "role": "VIEWER"}
