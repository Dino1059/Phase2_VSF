import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, Header
from pydantic import BaseModel

from src.middleware.auth import (
    UserRole,
    SERVER_USERS,
    create_access_token,
    decode_access_token,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: Optional[str] = None
    role: Optional[str] = None


class SwitchRoleRequest(BaseModel):
    role: str  # admin, steward, viewer, analyst, auditor


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

    # Check direct lookup by username/email
    if username in SERVER_USERS:
        user_info = SERVER_USERS[username]
    else:
        # Fallback to role matching
        target_role = (req.role or username).capitalize()
        for u, data in SERVER_USERS.items():
            if data["role"].value.lower() == target_role.lower():
                user_info = data
                break

    if not user_info:
        # Default to Viewer if unknown
        user_info = {
            "user_id": f"usr_{username}",
            "username": username,
            "role": UserRole.VIEWER,
        }

    token = create_access_token({
        "sub": user_info["username"],
        "user_id": user_info["user_id"],
        "role": user_info["role"].value,
    })

    return {
        "access_token": token,
        "token_type": "bearer",
        "user": user_info["username"],
        "role": user_info["role"].value,
        "user_profile": {
            "user_id": user_info["user_id"],
            "username": user_info["username"],
            "role": user_info["role"].value,
        },
    }


@router.post("/quick-switch")
async def quick_switch(req: SwitchRoleRequest):
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
        if data["role"] == matched_role:
            user_info = data
            break

    if not user_info:
        user_info = {
            "user_id": f"usr_{matched_role.value.lower()}_01",
            "username": f"{matched_role.value.lower()}@datatrust.os",
            "role": matched_role,
        }

    token = create_access_token({
        "sub": user_info["username"],
        "user_id": user_info["user_id"],
        "role": matched_role.value,
    })

    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "user_id": user_info["user_id"],
            "username": user_info["username"],
            "role": matched_role.value,
        },
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
            return {
                "user_id": payload.get("user_id", "usr_01"),
                "username": payload.get("sub", "user@datatrust.os"),
                "role": role,
                "permissions": ["all", "read", "write"] if role == "Admin" else ["read"],
            }

    role = x_user_role or "Admin"
    return {
        "user_id": f"usr_{role.lower()}_01",
        "username": f"{role.lower()}@datatrust.os",
        "role": role,
        "permissions": ["all", "read", "write"] if role == "Admin" else ["read"],
    }


@router.post("/logout")
async def logout():
    return {"status": "success", "message": "Logged out successfully"}

