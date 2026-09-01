import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, Header
from pydantic import BaseModel

from src.middleware.auth import (
    UserRole,
    SERVER_USERS,
    ROLE_PERMISSIONS,
    create_access_token,
    decode_access_token,
    acl_profile_from_user,
    resolve_user_acl,
)

logger = logging.getLogger(__name__)

def _permissions_for_role(role: str) -> list[str]:
    try:
        role_enum = UserRole(role)
    except ValueError:
        role_enum = UserRole.VIEWER
    return sorted(ROLE_PERMISSIONS.get(role_enum, {"read"}))


def _token_claims(user_info: dict) -> dict:
    acl = acl_profile_from_user(user_info) if "is_global" in user_info or "datasets" in user_info else resolve_user_acl(
        user_info.get("user_id"), user_info.get("username")
    )
    return {
        "sub": user_info["username"],
        "user_id": user_info["user_id"],
        "role": user_info["role"].value if isinstance(user_info["role"], UserRole) else user_info["role"],
        "is_global": acl["is_global"],
        "datasets": acl["datasets"],
        "dept": acl.get("dept") or user_info.get("dept") or "",
    }


def _profile_payload(user_info: dict) -> dict:
    acl = acl_profile_from_user(user_info) if "datasets" in user_info else resolve_user_acl(
        user_info.get("user_id"), user_info.get("username")
    )
    role = user_info["role"].value if isinstance(user_info["role"], UserRole) else user_info["role"]
    return {
        "user_id": user_info["user_id"],
        "username": user_info["username"],
        "role": role,
        "is_global": acl["is_global"],
        "datasets": acl["datasets"],
        "dept": acl.get("dept") or user_info.get("dept") or "",
        "permissions": _permissions_for_role(role),
    }


router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: Optional[str] = None
    role: Optional[str] = None


class SwitchRoleRequest(BaseModel):
    role: str  # admin, steward, viewer, analyst, auditor, steward_a, …


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict


@router.get("")
@router.get("/")
async def auth_status():
    return {"status": "ok", "service": "auth"}


@router.post("/login")
async def login(req: LoginRequest):
    username = req.username.strip().lower()
    user_info = None

    if username in SERVER_USERS:
        user_info = SERVER_USERS[username]
    else:
        target_role = (req.role or username).capitalize()
        for u, data in SERVER_USERS.items():
            if data["role"].value.lower() == target_role.lower() and data.get("is_global"):
                user_info = data
                break

    if not user_info:
        user_info = {
            "user_id": f"usr_{username}",
            "username": username,
            "role": UserRole.VIEWER,
            "is_global": False,
            "datasets": [],
            "dept": "",
        }

    claims = _token_claims(user_info)
    token = create_access_token(claims)
    profile = _profile_payload(user_info)

    return {
        "access_token": token,
        "token_type": "bearer",
        "user": user_info["username"],
        "role": profile["role"],
        "is_global": profile["is_global"],
        "datasets": profile["datasets"],
        "user_profile": profile,
    }


@router.post("/quick-switch")
async def quick_switch(req: SwitchRoleRequest):
    raw = req.role.strip().lower()
    # Allow switching to scoped seed users by username alias
    if raw in SERVER_USERS:
        user_info = SERVER_USERS[raw]
        claims = _token_claims(user_info)
        token = create_access_token(claims)
        profile = _profile_payload(user_info)
        return {
            "access_token": token,
            "token_type": "bearer",
            "user": {
                "user_id": profile["user_id"],
                "username": profile["username"],
                "role": profile["role"],
                "is_global": profile["is_global"],
                "datasets": profile["datasets"],
                "dept": profile["dept"],
            },
            "user_profile": profile,
            "role": profile["role"],
            "is_global": profile["is_global"],
            "datasets": profile["datasets"],
        }

    target_role_str = req.role.strip().capitalize()
    matched_role = None
    for r in UserRole:
        if r.value.lower() == target_role_str.lower():
            matched_role = r
            break

    if not matched_role:
        raise HTTPException(status_code=400, detail=f"Invalid role: {req.role}")

    user_info = None
    for u, data in SERVER_USERS.items():
        if data["role"] == matched_role and data.get("is_global"):
            user_info = data
            break

    if not user_info:
        user_info = {
            "user_id": f"usr_{matched_role.value.lower()}_01",
            "username": f"{matched_role.value.lower()}@datatrust.os",
            "role": matched_role,
            "is_global": True,
            "datasets": ["*"],
            "dept": "",
        }

    claims = _token_claims(user_info)
    token = create_access_token(claims)
    profile = _profile_payload(user_info)

    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "user_id": profile["user_id"],
            "username": profile["username"],
            "role": matched_role.value,
            "is_global": profile["is_global"],
            "datasets": profile["datasets"],
            "dept": profile["dept"],
        },
        "user_profile": profile,
        "role": matched_role.value,
        "is_global": profile["is_global"],
        "datasets": profile["datasets"],
    }


@router.get("/me")
async def get_me(
    authorization: Optional[str] = Header(None),
    x_user_role: Optional[str] = Header("Admin"),
):
    if authorization:
        token = authorization
        if token.lower().startswith("bearer "):
            token = token[7:].strip()

        payload = decode_access_token(token)
        if payload:
            role = payload.get("role", "Viewer")
            acl = {
                "is_global": bool(payload.get("is_global")) or ("*" in (payload.get("datasets") or [])),
                "datasets": payload.get("datasets") or (["*"] if payload.get("is_global") else []),
                "dept": payload.get("dept") or "",
            }
            if "is_global" not in payload and "datasets" not in payload:
                acl = resolve_user_acl(payload.get("user_id"), payload.get("sub"))
            return {
                "user_id": payload.get("user_id", "usr_01"),
                "username": payload.get("sub", "user@datatrust.os"),
                "role": role,
                "is_global": acl["is_global"],
                "datasets": acl["datasets"],
                "dept": acl.get("dept") or "",
                "permissions": _permissions_for_role(role),
            }

    role = x_user_role or "Admin"
    acl = resolve_user_acl(f"usr_{role.lower()}_01", f"{role.lower()}@datatrust.os")
    return {
        "user_id": f"usr_{role.lower()}_01",
        "username": f"{role.lower()}@datatrust.os",
        "role": role,
        "is_global": acl["is_global"],
        "datasets": acl["datasets"],
        "dept": acl.get("dept") or "",
        "permissions": _permissions_for_role(role),
    }


@router.post("/logout")
async def logout():
    return {"status": "success", "message": "Logged out successfully"}
