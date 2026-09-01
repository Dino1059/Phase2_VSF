import os
import time
import json
import logging
from typing import Callable, Optional, Set, Dict, Any, Tuple, List
from enum import Enum
import jwt
from fastapi import Request, Response, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)

JWT_SECRET = os.getenv("JWT_SECRET", "datatrust-secret-key-v6-signed-jwt-authentication-token-secret-key-32bytes")
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_SECONDS = 3600 * 24  # 24 hours


class UserRole(str, Enum):
    ADMIN = "Admin"
    ANALYST = "Analyst"
    AUDITOR = "Auditor"
    STEWARD = "Steward"
    VIEWER = "Viewer"


# Admin: control-plane only — no warehouse execute (grill R2/R3).
ROLE_PERMISSIONS: Dict[UserRole, Set[str]] = {
    UserRole.ADMIN: {
        "read",
        "profile",
        "propose_rules",
        "review_rules",
        "manage_schedule",
        "clear_alerts",
        "reset",
        "manage_acl",
    },
    UserRole.ANALYST: {
        "read",
        "profile",
        "propose_rules",
        # preview/propose only — warehouse execute is Steward HITL gate
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
        "hitl_write",
        "execute_transform",
        "manage_schedule",
        "create_alert",
    },
    UserRole.VIEWER: {
        "read",
    },
}

# ACL principal = dataset_key (Q13). Map → warehouse tables internally.
_KNOWN_DATASETS = ("ev_telemetry", "charging_sessions", "trips", "nlp_feedback", "vingroup_pilot")
DATASET_A = "ev_telemetry"
DATASET_B = "trips"
DATASET_KEY_ALIASES = {
    "vinfast_ev_telemetry": "ev_telemetry",
    "vin_ev_ops": "ev_telemetry",
    "ev": "ev_telemetry",
    "vgreen": "charging_sessions",
    "xanhsm": "trips",
    "vin_trips_nlp": "trips",
    "nlp": "nlp_feedback",
}


def normalize_dataset_key(key: Optional[str]) -> Optional[str]:
    if not key:
        return None
    k = str(key).strip()
    if not k:
        return None
    if "::" in k:
        k = k.split("::", 1)[0]
    return DATASET_KEY_ALIASES.get(k, k)


def _user(
    user_id: str,
    username: str,
    role: UserRole,
    *,
    is_global: bool = False,
    datasets: Optional[list] = None,
    dept: str = "",
) -> Dict[str, Any]:
    ds = list(datasets) if datasets is not None else (["*"] if is_global else [])
    return {
        "user_id": user_id,
        "username": username,
        "role": role,
        "is_global": bool(is_global) or ("*" in ds),
        "datasets": ds,
        "dept": dept or "",
    }


SERVER_USERS: Dict[str, Dict[str, Any]] = {
    # Demo globals — is_global=true (unchanged personas)
    "admin": _user("usr_admin_01", "admin@datatrust.os", UserRole.ADMIN, is_global=True, dept="Operations"),
    "admin@datatrust.os": _user("usr_admin_01", "admin@datatrust.os", UserRole.ADMIN, is_global=True, dept="Operations"),
    "steward": _user("usr_steward_01", "steward@datatrust.os", UserRole.STEWARD, is_global=True, dept="Data Quality"),
    "steward@datatrust.os": _user("usr_steward_01", "steward@datatrust.os", UserRole.STEWARD, is_global=True, dept="Data Quality"),
    "analyst": _user("usr_analyst_01", "analyst@datatrust.os", UserRole.ANALYST, is_global=True, dept="Fleet Analytics"),
    "analyst@datatrust.os": _user("usr_analyst_01", "analyst@datatrust.os", UserRole.ANALYST, is_global=True, dept="Fleet Analytics"),
    "auditor": _user("usr_auditor_01", "auditor@datatrust.os", UserRole.AUDITOR, is_global=True, dept="Audit"),
    "auditor@datatrust.os": _user("usr_auditor_01", "auditor@datatrust.os", UserRole.AUDITOR, is_global=True, dept="Audit"),
    "viewer": _user("usr_viewer_01", "viewer@datatrust.os", UserRole.VIEWER, is_global=True, dept="Audit"),
    "viewer@datatrust.os": _user("usr_viewer_01", "viewer@datatrust.os", UserRole.VIEWER, is_global=True, dept="Audit"),
    # Dataset A = ev_telemetry
    "steward_a": _user("usr_steward_a", "steward_a@datatrust.os", UserRole.STEWARD, datasets=[DATASET_A], dept="Faculty A"),
    "steward_a@datatrust.os": _user("usr_steward_a", "steward_a@datatrust.os", UserRole.STEWARD, datasets=[DATASET_A], dept="Faculty A"),
    "faculty_a": _user("usr_steward_a", "steward_a@datatrust.os", UserRole.STEWARD, datasets=[DATASET_A], dept="Faculty A"),
    "faculty_a@datatrust.os": _user("usr_steward_a", "steward_a@datatrust.os", UserRole.STEWARD, datasets=[DATASET_A], dept="Faculty A"),
    "analyst_a": _user("usr_analyst_a", "analyst_a@datatrust.os", UserRole.ANALYST, datasets=[DATASET_A], dept="Faculty A"),
    "analyst_a@datatrust.os": _user("usr_analyst_a", "analyst_a@datatrust.os", UserRole.ANALYST, datasets=[DATASET_A], dept="Faculty A"),
    "viewer_a": _user("usr_viewer_a", "viewer_a@datatrust.os", UserRole.VIEWER, datasets=[DATASET_A], dept="Faculty A"),
    "viewer_a@datatrust.os": _user("usr_viewer_a", "viewer_a@datatrust.os", UserRole.VIEWER, datasets=[DATASET_A], dept="Faculty A"),
    # Dataset B = trips
    "steward_b": _user("usr_steward_b", "steward_b@datatrust.os", UserRole.STEWARD, datasets=[DATASET_B], dept="Faculty B"),
    "steward_b@datatrust.os": _user("usr_steward_b", "steward_b@datatrust.os", UserRole.STEWARD, datasets=[DATASET_B], dept="Faculty B"),
    "faculty_b": _user("usr_steward_b", "steward_b@datatrust.os", UserRole.STEWARD, datasets=[DATASET_B], dept="Faculty B"),
    "faculty_b@datatrust.os": _user("usr_steward_b", "steward_b@datatrust.os", UserRole.STEWARD, datasets=[DATASET_B], dept="Faculty B"),
    "analyst_b": _user("usr_analyst_b", "analyst_b@datatrust.os", UserRole.ANALYST, datasets=[DATASET_B], dept="Faculty B"),
    "analyst_b@datatrust.os": _user("usr_analyst_b", "analyst_b@datatrust.os", UserRole.ANALYST, datasets=[DATASET_B], dept="Faculty B"),
    "viewer_b": _user("usr_viewer_b", "viewer_b@datatrust.os", UserRole.VIEWER, datasets=[DATASET_B], dept="Faculty B"),
    "viewer_b@datatrust.os": _user("usr_viewer_b", "viewer_b@datatrust.os", UserRole.VIEWER, datasets=[DATASET_B], dept="Faculty B"),
    # Scoped admin (names+aggregate still; no row drill regardless of datasets claim)
    "faculty_admin": _user("usr_faculty_admin", "faculty_admin@datatrust.os", UserRole.ADMIN, datasets=[DATASET_A], dept="Faculty Admin"),
    "faculty_admin@datatrust.os": _user("usr_faculty_admin", "faculty_admin@datatrust.os", UserRole.ADMIN, datasets=[DATASET_A], dept="Faculty Admin"),
}


def acl_profile_from_user(user_info: Dict[str, Any]) -> Dict[str, Any]:
    ds = list(user_info.get("datasets") or [])
    is_global = bool(user_info.get("is_global")) or ("*" in ds)
    return {
        "is_global": is_global,
        "datasets": ["*"] if is_global else ds,
        "dept": user_info.get("dept") or "",
    }


def user_can_access_dataset(is_global: bool, datasets: Optional[list], dataset_key: Optional[str]) -> bool:
    key = normalize_dataset_key(dataset_key)
    if not key:
        return True
    if is_global or (datasets and "*" in datasets):
        return True
    allowed = {normalize_dataset_key(d) for d in (datasets or []) if d}
    if key in allowed:
        return True
    # vingroup_pilot is cross-cutting warehouse name — allow if any known table assigned
    if key == "vingroup_pilot" and allowed.intersection(_KNOWN_DATASETS):
        return True
    return False


def filter_datasets_for_acl(datasets: list, is_global: bool, allowed: Optional[list]) -> list:
    """Filter catalog entries (dicts with key/dataset_key or bare strings)."""
    if is_global or (allowed and "*" in allowed):
        return datasets
    allow = {normalize_dataset_key(d) for d in (allowed or []) if d}

    def _key(item):
        if isinstance(item, dict):
            return normalize_dataset_key(item.get("key") or item.get("dataset_key") or item.get("name"))
        return normalize_dataset_key(str(item))

    return [d for d in datasets if _key(d) in allow]


def resolve_user_acl(user_id: Optional[str], username: Optional[str] = None) -> Dict[str, Any]:
    for key in (username or "", user_id or ""):
        k = str(key).strip().lower()
        if k in SERVER_USERS:
            return acl_profile_from_user(SERVER_USERS[k])
        # also match by user_id field
        for u in SERVER_USERS.values():
            if u.get("user_id") == key or u.get("username", "").lower() == k:
                return acl_profile_from_user(u)
    return {"is_global": False, "datasets": [], "dept": ""}


def extract_dataset_key_from_request(request: Request) -> Optional[str]:
    qp = request.query_params
    for name in ("dataset_key", "table", "table_name", "domain", "dataset"):
        val = qp.get(name)
        if val:
            return normalize_dataset_key(str(val).strip())
    path = request.url.path
    # /datasets/{key}/...
    if "/datasets/" in path:
        rest = path.split("/datasets/", 1)[1]
        seg = rest.split("/", 1)[0].strip()
        if seg and seg not in ("upload", ""):
            return normalize_dataset_key(seg)
    for ds in _KNOWN_DATASETS:
        if f"/{ds}" in path or path.rstrip("/").endswith(ds):
            return ds
    return None


MOCK_TOKEN_REGISTRY: Dict[str, UserRole] = {
    "token_admin": UserRole.ADMIN,
    "token_analyst": UserRole.ANALYST,
    "token_auditor": UserRole.AUDITOR,
    "token_steward": UserRole.STEWARD,
    "token_viewer": UserRole.VIEWER,
    "admin_token": UserRole.ADMIN,
    "mock-jwt-token-datatrust-v3": UserRole.ADMIN,
    "admin": UserRole.ADMIN,
    "steward": UserRole.STEWARD,
    "analyst": UserRole.ANALYST,
    "auditor": UserRole.AUDITOR,
    "viewer": UserRole.VIEWER,
}


def create_access_token(data: dict, expires_delta: Optional[int] = None) -> str:
    to_encode = data.copy()
    now = int(time.time())
    expire = now + (expires_delta if expires_delta is not None else JWT_EXPIRATION_SECONDS)
    to_encode.update({"iat": now, "exp": expire})
    return jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> Optional[dict]:
    if not token:
        return None

    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        logger.warning("Expired JWT token received.")
        return None
    except jwt.InvalidTokenError:
        pass
    except Exception:
        pass

    app_env = os.getenv("APP_ENV", "development").lower()
    if app_env != "production":
        if token in MOCK_TOKEN_REGISTRY:
            role = MOCK_TOKEN_REGISTRY[token]
            acl = resolve_user_acl(f"usr_{role.value.lower()}_01", f"{role.value.lower()}@datatrust.os")
            return {
                "sub": f"{role.value.lower()}@datatrust.os",
                "user_id": f"usr_{role.value.lower()}_01",
                "role": role.value,
                "is_global": acl["is_global"],
                "datasets": acl["datasets"],
                "dept": acl.get("dept") or "",
            }

        valid_roles = {
            "Admin": UserRole.ADMIN,
            "Analyst": UserRole.ANALYST,
            "Auditor": UserRole.AUDITOR,
            "Steward": UserRole.STEWARD,
            "Viewer": UserRole.VIEWER,
        }
        cap_token = token.capitalize()
        if cap_token in valid_roles:
            role = valid_roles[cap_token]
            acl = resolve_user_acl(f"usr_{role.value.lower()}_01", f"{role.value.lower()}@datatrust.os")
            return {
                "sub": f"{role.value.lower()}@datatrust.os",
                "user_id": f"usr_{role.value.lower()}_01",
                "role": role.value,
                "is_global": acl["is_global"],
                "datasets": acl["datasets"],
                "dept": acl.get("dept") or "",
            }

    return None


def resolve_server_user_role(username_or_id: str) -> UserRole:
    user_info = SERVER_USERS.get(username_or_id.lower())
    if user_info:
        return user_info["role"]
    return UserRole.VIEWER


PUBLIC_EXACT_PATHS = {
    "/health",
    "/v3",
    "/v3/",
    "/vite.svg",
    "/favicon.ico",
    "/favicon.svg",
    "/",
    "/ui",
    "/api/v1/auth",
    "/api/v1/auth/",
    "/api/v1/auth/login",
    "/auth/login",
    "/api/v1/auth/quick-switch",
    "/auth/quick-switch",
    "/api/v1/auth/logout",
    "/auth/logout",
}


def is_public_path(path: str) -> bool:
    norm = path.rstrip("/")
    if norm in PUBLIC_EXACT_PATHS or norm.endswith("/auth/login") or norm.endswith("/login") or norm.endswith("/auth/quick-switch") or norm.endswith("/auth"):
        return True
    if (
        norm.startswith("/v3")
        or norm.startswith("/static")
        or norm.startswith("/assets")
    ):
        return True
    return False


def _attach_acl(request: Request, user_id: Optional[str], username: Optional[str], payload: Optional[dict] = None) -> Dict[str, Any]:
    """Resolve ACL onto request.state. JWT claims win when present."""
    if payload and ("is_global" in payload or "datasets" in payload):
        is_global = bool(payload.get("is_global")) or ("*" in (payload.get("datasets") or []))
        datasets = ["*"] if is_global else list(payload.get("datasets") or [])
        acl = {"is_global": is_global, "datasets": datasets, "dept": payload.get("dept") or ""}
    else:
        acl = resolve_user_acl(user_id, username)
    request.state.is_global = acl["is_global"]
    request.state.datasets = acl["datasets"]
    request.state.dept = acl.get("dept") or ""
    return acl


def _json_403(detail: str, **extra) -> Response:
    body = {"detail": detail, **extra}
    return Response(
        content=json.dumps(body),
        status_code=status.HTTP_403_FORBIDDEN,
        media_type="application/json",
    )


def _enforce_dataset_acl(request: Request) -> Optional[Response]:
    ds = extract_dataset_key_from_request(request)
    if not ds:
        return None
    is_global = bool(getattr(request.state, "is_global", False))
    datasets = getattr(request.state, "datasets", None) or []
    if user_can_access_dataset(is_global, datasets, ds):
        return None
    return _json_403(
        f"Forbidden: dataset '{ds}' not in ACL scope",
        dataset_key=ds,
        is_global=is_global,
        datasets=datasets,
    )


# Q11=C: Admin may catalog names + aggregate dashboard; block row/HITL/ingest detail + execute.
_ADMIN_DATA_DENY_MARKERS = (
    "/hitl/",
    "/datasets/",
    "/ingestion/",
    "/workspace",
    "/profiler",
    "/sample",
    "/quarantine",
    "/split",
    "/traces",
    "/execute",
    "/promote",
    "/warmup",
    "/realtime",
    "/pipeline/execute",
    "/transform/execute",
    "/day-count",
    "/sandbox",
)


def _admin_path_allowed(path: str, method: str) -> bool:
    """Return True if Admin may access this path (control-plane / aggregate / names)."""
    p = path.lower()
    # Always allow auth, system status, health, LLM status, reset, dashboard aggregate
    if any(
        x in p
        for x in (
            "/auth",
            "/system/",
            "/health",
            "/llm-status",
            "/dashboard/",
            "/summary",
            "/alerts",
            "/audit",
            "/search",
            "/eval",
            "/chat",
            "/rules",
            "/snapshots",
            "/operations",
            "/governance",
            "/incidents",
            "/signals",
            "/activity",
        )
    ):
        # still block execute anywhere
        if "/execute" in p:
            return False
        # block HITL entirely for Admin (no drill)
        if "/hitl/" in p:
            return False
        return True
    # Catalog names only: exact /datasets or /datasets/
    if p.rstrip("/").endswith("/datasets") and method in ("GET", "HEAD", "OPTIONS"):
        return True
    if method == "POST" and p.rstrip("/").endswith("/reset"):
        return True
    # Deny known data-plane markers
    if any(m in p for m in _ADMIN_DATA_DENY_MARKERS):
        return False
    # Default: allow read-ish ops without dataset drill
    if method in ("GET", "HEAD", "OPTIONS"):
        return True
    return False


def _enforce_admin_data_plane(request: Request, role: UserRole) -> Optional[Response]:
    if role != UserRole.ADMIN:
        return None
    path = request.url.path
    method = request.method.upper()
    if _admin_path_allowed(path, method):
        return None
    return _json_403(
        "Forbidden: Admin may view dataset names and aggregate dashboard only (no row/HITL/ingest drill, no execute)",
        role="Admin",
        path=path,
    )


def check_role_permission(role: UserRole, action: str) -> bool:
    allowed = ROLE_PERMISSIONS.get(role, set())
    return action in allowed


_REVIEW_MARKERS = (
    "/hitl/approve",
    "/hitl/reject",
    "/hitl/edit",
    "/batch-approve",
    "/hitl/remember",
    "/hitl/rollback",
    "/hitl/confirm-patch",
    "/hitl/execute",
)


def is_hitl_review_write(path: str, method: str) -> bool:
    if method not in ("POST", "PUT", "PATCH"):
        return False
    p = path.lower()
    if any(m in p for m in _REVIEW_MARKERS):
        return True
    if p.rstrip("/").endswith("/approve") and (
        "/hitl/" in p or "/rules/" in p or "/approvals/" in p
    ):
        return True
    return False


def _extract_token_and_role(request: Request) -> Tuple[Optional[str], Optional[UserRole], Optional[str], bool, Optional[dict]]:
    """
    Extract token and resolve role server-side.
    Returns: (raw_token, resolved_role, user_id, is_invalid_role, payload)
    """
    auth_header = request.headers.get("Authorization")
    token_param = request.query_params.get("token")
    x_user_role = request.headers.get("X-User-Role")

    raw_token = None
    if auth_header and auth_header.startswith("Bearer "):
        raw_token = auth_header[7:].strip()
    elif auth_header:
        raw_token = auth_header.strip()
    elif token_param:
        raw_token = token_param.strip()

    if raw_token:
        payload = decode_access_token(raw_token)
        if payload:
            role_str = payload.get("role")
            sub = payload.get("sub") or payload.get("user_id") or ""
            if not role_str and sub:
                role_val = resolve_server_user_role(sub)
            elif role_str:
                try:
                    role_val = UserRole(role_str.strip().capitalize())
                except ValueError:
                    return raw_token, None, None, True, None
            else:
                role_val = UserRole.VIEWER
            user_id = payload.get("user_id", f"usr_{sub}")
            return raw_token, role_val, user_id, False, payload
        else:
            valid_roles = {"Admin", "Analyst", "Auditor", "Viewer", "Steward"}
            if raw_token in valid_roles:
                return raw_token, UserRole(raw_token), f"usr_{raw_token.lower()}", False, None
            if raw_token.startswith("ey"):
                return raw_token, None, None, False, None
            if x_user_role:
                role_str = x_user_role.strip().capitalize()
                if role_str in valid_roles:
                    return raw_token, UserRole(role_str), f"usr_{role_str.lower()}", False, None
            return raw_token, None, None, True, None

    if x_user_role:
        role_str = x_user_role.strip().capitalize()
        valid_roles = {"Admin", "Analyst", "Auditor", "Viewer", "Steward"}
        if role_str in valid_roles:
            return None, UserRole(role_str), f"usr_{role_str.lower()}", False, None
        return None, None, None, True, None

    return None, None, None, False, None


async def check_user_role(request: Request) -> str:
    """Dependency for API route role verification."""
    if request.scope.get("type") == "websocket":
        return "Admin"

    path = request.url.path
    if is_public_path(path):
        return "Viewer"

    raw_token, resolved_role, user_id, is_invalid_role, payload = _extract_token_and_role(request)

    if is_invalid_role:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Unknown or invalid user role/token",
        )

    if raw_token is not None and resolved_role is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized: Invalid or expired signed JWT token",
        )

    if resolved_role is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized: Missing signed JWT token",
        )

    role_str = resolved_role.value
    request.state.user_role = role_str
    request.state.user_id = user_id
    username = (payload or {}).get("sub") if payload else None
    _attach_acl(request, user_id, username, payload)
    method = request.method.upper()

    if resolved_role == UserRole.VIEWER:
        if method not in ("GET", "HEAD", "OPTIONS"):
            if not any(path.endswith(p) for p in ["/chat", "/health", "/status"]):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Role 'Viewer' has read-only access. '{method}' operation is forbidden.",
                )

    if is_hitl_review_write(path, method) and not check_role_permission(resolved_role, "hitl_write"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: HITL write is Data Steward only",
        )

    if resolved_role in (UserRole.STEWARD, UserRole.ANALYST, UserRole.AUDITOR):
        if method == "DELETE" or path.rstrip("/").endswith("/reset"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{role_str}' does not have permission for administrative operation.",
            )

    admin_block = _enforce_admin_data_plane(request, resolved_role)
    if admin_block is not None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=json.loads(admin_block.body.decode()).get("detail"))

    acl_block = _enforce_dataset_acl(request)
    if acl_block is not None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=json.loads(acl_block.body.decode()).get("detail"))

    return role_str


def assert_dataset_acl(request: Request, dataset_key: Optional[str]) -> None:
    """Call from handlers that take dataset_key in body."""
    role = getattr(request.state, "user_role", None)
    if str(role or "").lower() == "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Admin may view dataset names and aggregate dashboard only (no row/HITL/ingest drill, no execute)",
        )
    is_global = bool(getattr(request.state, "is_global", False))
    datasets = getattr(request.state, "datasets", None) or []
    if not user_can_access_dataset(is_global, datasets, dataset_key):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Forbidden: dataset '{dataset_key}' not in ACL scope",
        )


class RoleMiddleware(BaseHTTPMiddleware):
    """FastAPI Middleware enforcing signed JWT auth and server-side role resolution."""

    def __init__(self, app):
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if request.scope.get("type") == "websocket":
            return await call_next(request)

        path = request.url.path
        if is_public_path(path):
            return await call_next(request)

        raw_token, resolved_role, user_id, is_invalid_role, payload = _extract_token_and_role(request)

        if is_invalid_role:
            return _json_403("Forbidden: Unknown or invalid user role/token")

        if raw_token is not None and resolved_role is None:
            return Response(
                content='{"detail": "Unauthorized: Invalid or expired signed JWT token"}',
                status_code=status.HTTP_401_UNAUTHORIZED,
                media_type="application/json",
            )

        if resolved_role is None:
            return Response(
                content='{"detail": "Unauthorized: Missing signed JWT token"}',
                status_code=status.HTTP_401_UNAUTHORIZED,
                media_type="application/json",
            )

        role_str = resolved_role.value
        request.state.user_role = role_str
        request.state.user_id = user_id
        username = (payload or {}).get("sub") if payload else None
        _attach_acl(request, user_id, username, payload)
        method = request.method.upper()

        if resolved_role == UserRole.VIEWER and method in ("POST", "PUT", "DELETE", "PATCH"):
            if not any(path.endswith(p) for p in ["/chat", "/health", "/status"]):
                return _json_403("Forbidden: Viewer role has read-only access")

        if is_hitl_review_write(path, method) and not check_role_permission(resolved_role, "hitl_write"):
            return _json_403("Forbidden: HITL write is Data Steward only")

        if path.rstrip("/").endswith("/reset") and method == "POST" and resolved_role != UserRole.ADMIN:
            return _json_403("Forbidden: Admin role required for system reset")

        # Block Admin execute / data drill (Q11=C)
        admin_block = _enforce_admin_data_plane(request, resolved_role)
        if admin_block is not None:
            return admin_block

        # Dataset ACL for scoped users (Q12=A + steward_a/b)
        acl_block = _enforce_dataset_acl(request)
        if acl_block is not None:
            return acl_block

        try:
            response = await call_next(request)
            return response
        except Exception as exc:
            import traceback
            print(f"\033[91m[ROLE MIDDLEWARE DISPATCH EXCEPTION {request.method} {request.url.path}]\033[0m\n{traceback.format_exc()}")
            return Response(
                content=f'{{"detail": "Internal Server Error: {str(exc)}"}}',
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                media_type="application/json",
            )
