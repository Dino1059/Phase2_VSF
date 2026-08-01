from enum import Enum
from typing import Callable, List, Optional, Set
from fastapi import Header, HTTPException, Request, Response, status
from starlette.middleware.base import BaseHTTPMiddleware


class UserRole(str, Enum):
    ADMIN = "Admin"
    STEWARD = "Steward"
    VIEWER = "Viewer"


ROLE_PERMISSIONS: dict[UserRole, Set[str]] = {
    UserRole.ADMIN: {
        "read",
        "profile",
        "propose_rules",
        "review_rules",
        "execute_transform",
        "manage_schedule",
        "clear_alerts",
        "reset",
    },
    UserRole.STEWARD: {
        "read",
        "profile",
        "propose_rules",
        "review_rules",
        "execute_transform",
        "manage_schedule",
        "create_alert",
    },
    UserRole.VIEWER: {
        "read",
    },
}


def check_role_permission(role: UserRole, action: str) -> bool:
    """Check if given role has permission for a specific action."""
    allowed = ROLE_PERMISSIONS.get(role, set())
    return action in allowed


class RoleMiddleware(BaseHTTPMiddleware):
    """FastAPI Middleware enforcing role-based access control (Admin, Steward, Viewer)."""

    def __init__(self, app, default_role: UserRole = UserRole.ADMIN):
        super().__init__(app)
        self.default_role = default_role

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        role_header = (request.headers.get("X-User-Role", self.default_role.value) or "Admin").strip().capitalize()
        
        try:
            user_role = UserRole(role_header)
        except ValueError:
            user_role = UserRole.VIEWER

        request.state.user_role = user_role
        path = request.url.path
        method = request.method

        # Viewer role cannot execute mutating POST/PUT/DELETE operations (except health/status)
        if user_role == UserRole.VIEWER and method in ("POST", "PUT", "DELETE", "PATCH"):
            if not any(path.endswith(p) for p in ["/chat", "/health", "/status"]):
                return Response(
                    content='{"detail": "Forbidden: Viewer role has read-only access"}',
                    status_code=status.HTTP_403_FORBIDDEN,
                    media_type="application/json",
                )

        # Admin role required for system reset
        if path.endswith("/reset") and method == "POST" and user_role != UserRole.ADMIN:
            return Response(
                content='{"detail": "Forbidden: Admin role required for system reset"}',
                status_code=status.HTTP_403_FORBIDDEN,
                media_type="application/json",
            )

        response = await call_next(request)
        return response
