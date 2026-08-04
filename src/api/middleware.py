from enum import Enum
from typing import Callable, List, Optional, Set
from fastapi import Header, HTTPException, Request, Response, status
from starlette.middleware.base import BaseHTTPMiddleware


class UserRole(str, Enum):
    ADMIN = "Admin"
    ANALYST = "Analyst"
    AUDITOR = "Auditor"
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
    UserRole.ANALYST: {
        "read",
        "profile",
        "propose_rules",
        "execute_transform",
    },
    UserRole.AUDITOR: {
        "read",
        "review_rules",
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


PUBLIC_EXACT_PATHS = {
    "/health",
    "/v3",
    "/v3/",
    "/vite.svg",
    "/favicon.ico",
    "/favicon.svg",
    "/",
    "/ui",
}


def is_public_path(path: str) -> bool:
    """Determine if a request path is publicly accessible without authentication."""
    if path in PUBLIC_EXACT_PATHS:
        return True
    if (
        path.startswith("/v3/")
        or path.startswith("/static/")
        or path.startswith("/assets/")
    ):
        return True
    return False


async def check_user_role(request: Request):
    """Middleware dependency for X-User-Role role-based access control."""
    if request.scope.get("type") == "websocket":
        return "Admin"

    path = request.url.path

    x_user_role = request.headers.get("X-User-Role")
    auth_header = request.headers.get("Authorization")

    # Reject missing credentials on protected routes with HTTP 401
    if not x_user_role and not auth_header:
        if not is_public_path(path):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Unauthorized: Missing X-User-Role or Authorization header",
            )
        return "Viewer"

    raw_role = x_user_role or (auth_header.replace("Bearer ", "") if auth_header else "")
    role = raw_role.strip().capitalize() if raw_role else ""

    valid_roles = {"Admin", "Analyst", "Auditor", "Viewer", "Steward"}
    if role not in valid_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Forbidden: Unknown or invalid user role '{raw_role}'",
        )

    request.state.user_role = role
    method = request.method.upper()

    if role == "Viewer":
        if method not in ("GET", "HEAD", "OPTIONS"):
            if not any(path.endswith(p) for p in ["/chat", "/health", "/status"]):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Role 'Viewer' has read-only access. '{method}' operation is forbidden.",
                )

    if role in ("Steward", "Analyst", "Auditor"):
        if method == "DELETE" or path.rstrip("/").endswith("/reset"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{role}' does not have permission for administrative operation.",
            )

    return role


class RoleMiddleware(BaseHTTPMiddleware):
    """FastAPI Middleware enforcing role-based access control (Admin, Analyst, Auditor, Steward, Viewer)."""

    def __init__(self, app):
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if request.scope.get("type") == "websocket":
            return await call_next(request)

        path = request.url.path
        x_user_role = request.headers.get("X-User-Role")
        auth_header = request.headers.get("Authorization")

        if not x_user_role and not auth_header:
            if not is_public_path(path):
                return Response(
                    content='{"detail": "Unauthorized: Missing X-User-Role or Authorization header"}',
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    media_type="application/json",
                )
            return await call_next(request)

        raw_role = x_user_role or (auth_header.replace("Bearer ", "") if auth_header else "")
        role_str = raw_role.strip().capitalize() if raw_role else ""

        valid_roles = {"Admin", "Analyst", "Auditor", "Viewer", "Steward"}
        if role_str not in valid_roles:
            return Response(
                content=f'{{"detail": "Forbidden: Unknown or invalid role \'{raw_role}\'"}}',
                status_code=status.HTTP_403_FORBIDDEN,
                media_type="application/json",
            )

        try:
            user_role = UserRole(role_str)
        except ValueError:
            return Response(
                content=f'{{"detail": "Forbidden: Unknown or invalid role \'{raw_role}\'"}}',
                status_code=status.HTTP_403_FORBIDDEN,
                media_type="application/json",
            )

        request.state.user_role = user_role
        method = request.method.upper()

        if user_role == UserRole.VIEWER and method in ("POST", "PUT", "DELETE", "PATCH"):
            if not any(path.endswith(p) for p in ["/chat", "/health", "/status"]):
                return Response(
                    content='{"detail": "Forbidden: Viewer role has read-only access"}',
                    status_code=status.HTTP_403_FORBIDDEN,
                    media_type="application/json",
                )

        if path.rstrip("/").endswith("/reset") and method == "POST" and user_role != UserRole.ADMIN:
            return Response(
                content='{"detail": "Forbidden: Admin role required for system reset"}',
                status_code=status.HTTP_403_FORBIDDEN,
                media_type="application/json",
            )

        response = await call_next(request)
        return response
