from typing import Optional
from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel
from src.middleware.auth import (
    check_user_role,
    create_access_token,
    decode_access_token,
    resolve_server_user_role,
    ROLE_PERMISSIONS,
    SERVER_USERS,
    UserRole,
)

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    user: str


@router.get("", summary="Auth status")
@router.get("/", summary="Auth status")
async def auth_status(request: Request):
    auth_header = request.headers.get("Authorization")
    raw_token = auth_header.replace("Bearer ", "").strip() if auth_header else None
    if raw_token:
        payload = decode_access_token(raw_token)
        if payload:
            role = payload.get("role", "Admin")
            return {
                "status": "ok",
                "service": "auth",
                "current_role": role,
            }
    x_user_role = request.headers.get("X-User-Role")
    if x_user_role:
        return {
            "status": "ok",
            "service": "auth",
            "current_role": x_user_role.capitalize(),
        }
    return {
        "status": "ok",
        "service": "auth",
        "current_role": "Viewer",
    }


@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest):
    if not request.username or not request.password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username and password required",
        )

    user_entry = SERVER_USERS.get(request.username.lower())
    if user_entry:
        user_id = user_entry["user_id"]
        username = user_entry["username"]
        role = user_entry["role"]
    else:
        user_id = f"usr_{request.username.lower()}"
        username = request.username
        role = resolve_server_user_role(request.username)

    token_data = {
        "sub": username,
        "user_id": user_id,
        "role": role.value,
    }
    access_token = create_access_token(token_data)

    return LoginResponse(
        access_token=access_token,
        token_type="bearer",
        role=role.value,
        user=username,
    )


@router.get("/me")
async def get_current_user(request: Request):
    auth_header = request.headers.get("Authorization")
    x_user_role = request.headers.get("X-User-Role")
    raw_token = auth_header.replace("Bearer ", "").strip() if auth_header else (x_user_role or None)

    if not raw_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized: Missing Authorization Bearer token",
        )

    payload = decode_access_token(raw_token)
    if not payload and x_user_role:
        role_str = x_user_role.strip().capitalize()
        try:
            user_role = UserRole(role_str)
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Forbidden: Unknown role {x_user_role}",
            )
        user_id = f"usr_{user_role.value.lower()}_01"
        sub = f"{user_role.value.lower()}@datatrust.os"
    elif not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized: Invalid or expired signed JWT token",
        )
    else:
        role_str = payload.get("role")
        sub = payload.get("sub", "user")
        user_id = payload.get("user_id", f"usr_{sub}")
        try:
            user_role = UserRole(role_str)
        except Exception:
            user_role = resolve_server_user_role(sub)

    permissions = list(ROLE_PERMISSIONS.get(user_role, set()))

    return {
        "user_id": user_id,
        "username": sub,
        "role": user_role.value,
        "permissions": sorted(permissions),
    }


@router.post("/logout")
async def logout():
    return {"status": "success", "message": "Successfully logged out"}
