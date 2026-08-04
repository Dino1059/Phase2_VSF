from typing import Optional
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from src.api.middleware import check_user_role


router = APIRouter(prefix="/auth", tags=["auth"], dependencies=[Depends(check_user_role)])


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str = "Admin"
    user: str


@router.get("", summary="Auth status")
@router.get("/", summary="Auth status")
async def auth_status(x_user_role: Optional[str] = Header(None, alias="X-User-Role")):
    return {
        "status": "ok",
        "service": "auth",
        "current_role": x_user_role or "Admin",
    }


@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest):
    if not request.username or not request.password:
        raise HTTPException(status_code=400, detail="Username and password required")
    return LoginResponse(
        access_token="mock-jwt-token-datatrust-v3",
        token_type="bearer",
        role="Admin",
        user=request.username,
    )


@router.get("/me")
async def get_current_user(x_user_role: Optional[str] = Header(None, alias="X-User-Role")):
    role = x_user_role or "Admin"
    return {
        "user_id": "usr_admin_01",
        "username": "admin@datatrust.os",
        "role": role,
        "permissions": [
            "read",
            "profile",
            "propose_rules",
            "review_rules",
            "execute_transform",
            "manage_schedule",
            "clear_alerts",
            "reset",
        ],
    }


@router.post("/logout")
async def logout():
    return {"status": "success", "message": "Successfully logged out"}
