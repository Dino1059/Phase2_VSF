"""
DataTrust OS x SoD Flow: Unified Authentication & Role Switcher Routes
Supports single unified session, token session_version validation, and Demo Multi-party Persona Context.
"""

import os
import datetime
from typing import Any, Dict, List, Optional
import jwt
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, Header, Request, status
from psycopg2.extras import RealDictCursor

from database.profiler_engine import get_db_connection

router = APIRouter()

_DEV_JWT_SECRET = "datatrust_os_sod_jwt_secret_phase2_dev"
JWT_ALGORITHM = "HS256"


def _jwt_secret() -> str:
    secret = os.getenv("JWT_SECRET")
    is_production = os.getenv("ENVIRONMENT", "").lower() == "production"
    if secret and (not is_production or (secret != _DEV_JWT_SECRET and len(secret.encode("utf-8")) >= 32)):
        return secret
    if is_production:
        raise RuntimeError("JWT_SECRET must be configured with at least 32 bytes in production")
    return _DEV_JWT_SECRET

# Danh sách quyền chi tiết cho từng vai trò (Fine-grained Authorization)
ROLE_PERMISSIONS: Dict[str, set] = {
    "ADMIN": {"read", "profile", "propose_rules", "review_rules", "start_run", "sod_access", "sod_create_ticket", "sod_approve_step", "sod_admin", "sod_propose_config", "sod_read_evidence"},
    "AUDITOR": {"read", "review_rules", "start_run", "sod_access", "sod_read_evidence", "sod_inspect"},
    "DPO": {"read", "review_rules", "sod_access", "sod_approve_step", "sod_dpo"},
    "SO": {"read", "sod_access", "sod_approve_step", "sod_owner"},
    "REQ": {"sod_access", "sod_create_ticket"},
    "LM": {"sod_access", "sod_approve_step"},
    "IAM": {"sod_access", "sod_approve_step", "sod_provision"},
    "DEV": {"sod_access", "sod_create_ticket"},
    "REL": {"sod_access", "sod_approve_step"},
    "OPS": {"sod_access", "sod_approve_step", "sod_deploy"},
    "CISO": {"sod_access", "sod_approve_step", "sod_decide_config"},
    "DATA_STEWARD": {"read", "profile", "propose_rules", "review_rules", "hitl_write", "start_run"},
    "ANALYST": {"read", "profile", "propose_rules"},
    "VIEWER": {"read"},
}

BOTH_ROLES = {"ADMIN", "AUDITOR", "DPO", "SO"}
SOD_ROLES = {"REQ", "LM", "IAM", "DEV", "REL", "OPS", "CISO"}
DATATRUST_ROLES = {"DATA_STEWARD", "ANALYST", "VIEWER"}


def get_system_access_for_role(role: str) -> str:
    r = role.upper()
    if r in BOTH_ROLES:
        return "both"
    if r in SOD_ROLES:
        return "sod_only"
    return "datatrust_only"


class UserContext(BaseModel):
    user_id: str
    username: str
    full_name: str
    active_role: str
    roles: List[str]
    system_access: str
    session_version: int


def create_jwt_token(payload: Dict[str, Any], expires_hours: int = 24) -> str:
    claims = dict(payload)
    claims["exp"] = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=expires_hours)
    claims["iat"] = datetime.datetime.now(datetime.timezone.utc)
    return jwt.encode(claims, _jwt_secret(), algorithm=JWT_ALGORITHM)


def decode_jwt_token(token: str) -> Dict[str, Any]:
    try:
        return jwt.decode(token, _jwt_secret(), algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Phiên đăng nhập đã hết hạn")
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token không hợp lệ")


async def get_current_user(
    request: Request,
    authorization: Optional[str] = Header(None),
    x_actor_role: Optional[str] = Header(None),
    conn = Depends(get_db_connection)
) -> UserContext:
    """
    Xác thực token JWT và kiểm tra session_version trong CSDL.
    Nếu token mang session_version cũ hơn CSDL, từ chối với 401 Unauthorized.
    """
    token = None
    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:].strip()

    allow_demo = os.getenv("ALLOW_DEMO_LOGIN", "false").lower() in {"1", "true", "yes"}
    is_demo = os.getenv("ENVIRONMENT", "").lower() != "production" or allow_demo

    if token:
        payload = decode_jwt_token(token)
        user_id = payload.get("sub")
        token_ver = payload.get("session_version", 1)
        active_role = payload.get("active_role", "VIEWER")

        # So khớp session_version trong CSDL để chống Privilege Escalation
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT id, username, full_name, session_version FROM sod.users WHERE id = %s;", (user_id,))
                user_row = cur.fetchone()
                if not user_row:
                    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Người dùng không tồn tại")
                
                db_ver = user_row["session_version"]
                if token_ver != db_ver:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Phiên làm việc đã bị vô hiệu hóa do thay đổi vai trò. Vui lòng sử dụng token mới."
                    )
                
                cur.execute("""
                    SELECT role_code FROM sod.user_roles
                    WHERE user_id = %s AND valid_from <= now()
                      AND (valid_to IS NULL OR valid_to > now())
                      AND revoked_at IS NULL;
                """, (user_id,))
                roles = [r["role_code"] for r in cur.fetchall()]
                if active_role not in roles:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Vai trò đang hoạt động không còn được phân công cho tài khoản.",
                    )

                return UserContext(
                    user_id=str(user_row["id"]),
                    username=user_row["username"],
                    full_name=user_row["full_name"],
                    active_role=active_role,
                    roles=roles,
                    system_access=get_system_access_for_role(active_role),
                    session_version=db_ver
                )
        except HTTPException:
            raise
        except Exception:
            if not is_demo:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Không thể xác thực phiên làm việc.")

    # Fallback cho môi trường test/demo cục bộ khi chưa truyền token
    if is_demo:
        fallback_role = (x_actor_role or "ADMIN").upper()
        # Tìm Persona tương ứng trong DB hoặc tạo context mẫu
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT u.id, u.username, u.full_name, u.session_version
                    FROM sod.users u
                    JOIN sod.user_roles ur ON u.id = ur.user_id
                    WHERE ur.role_code = %s
                    LIMIT 1;
                """, (fallback_role,))
                row = cur.fetchone()
                if row:
                    return UserContext(
                        user_id=str(row["id"]),
                        username=row["username"],
                        full_name=row["full_name"],
                        active_role=fallback_role,
                        roles=[fallback_role],
                        system_access=get_system_access_for_role(fallback_role),
                        session_version=row["session_version"]
                    )
        except Exception:
            pass

        return UserContext(
            user_id="00000000-0000-0000-0000-000000000001",
            username="demo_user",
            full_name="Tài khoản Trải nghiệm",
            active_role=fallback_role,
            roles=[fallback_role],
            system_access=get_system_access_for_role(fallback_role),
            session_version=1
        )

    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Yêu cầu cung cấp token xác thực Bearer")


def require_permission(perm: str):
    """FastAPI Dependency kiểm tra quyền chi tiết ở từng API endpoint."""
    def dependency(user: UserContext = Depends(get_current_user)):
        perms = ROLE_PERMISSIONS.get(user.active_role, set())
        if perm not in perms and "ADMIN" != user.active_role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Vai trò '{user.active_role}' không có quyền thực hiện thao tác '{perm}'."
            )
        return user
    return dependency


class LoginRequest(BaseModel):
    username: str
    password: Optional[str] = None
    role: Optional[str] = None


class SwitchRoleRequest(BaseModel):
    role: str


@router.post("/login")
def login(payload: LoginRequest, conn = Depends(get_db_connection)):
    """Đăng nhập tài khoản hoặc nạp phiên demo, trả về JWT token."""
    username = payload.username.strip().lower()
    allow_demo = os.getenv("ALLOW_DEMO_LOGIN", "false").lower() in {"1", "true", "yes"}
    is_production = os.getenv("ENVIRONMENT", "").lower() == "production"
    requested_role = payload.role.upper() if payload.role else None

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT u.id, u.username, u.full_name, u.session_version, u.password_hash,
                   CASE WHEN u.password_hash IS NULL OR %s IS NULL THEN FALSE
                        ELSE u.password_hash = crypt(%s, u.password_hash)
                   END AS password_valid
            FROM sod.users u
            WHERE u.username = %s AND u.is_active = TRUE;
        """, (payload.password, payload.password, username))
        user_row = cur.fetchone()

        if user_row and is_production and not allow_demo:
            if user_row["password_hash"] is not None and not user_row["password_valid"]:
                raise HTTPException(status_code=401, detail="Tài khoản hoặc mật khẩu không chính xác.")
        elif user_row and is_production and allow_demo:
            if payload.password and user_row["password_hash"] is not None and not user_row["password_valid"]:
                raise HTTPException(status_code=401, detail="Tài khoản hoặc mật khẩu không chính xác.")

        if not user_row:
            # Nếu chưa có sẵn trong DB và đang ở Demo mode, tìm persona tương ứng
            if not is_production or allow_demo:
                cur.execute("""
                    SELECT u.id, u.username, u.full_name, u.session_version, u.password_hash, TRUE AS password_valid
                    FROM sod.users u
                    LEFT JOIN sod.user_roles ur ON ur.user_id = u.id
                    WHERE u.is_active = TRUE AND (
                        u.username = %s
                        OR (%s IS NOT NULL AND ur.role_code = %s AND (u.username LIKE 'demo_%%' OR u.username = 'demo_user'))
                        OR u.username LIKE 'demo_%%'
                    )
                    LIMIT 1;
                """, (f"demo_{username}", requested_role, requested_role))
                user_row = cur.fetchone()

        if not user_row:
            raise HTTPException(status_code=400, detail="Tài khoản hoặc mật khẩu không chính xác.")

        user_id = str(user_row["id"])
        # Lấy các vai trò được phân công
        cur.execute("""
            SELECT role_code FROM sod.user_roles
            WHERE user_id = %s AND valid_from <= now()
              AND (valid_to IS NULL OR valid_to > now())
              AND revoked_at IS NULL;
        """, (user_id,))
        roles = [r["role_code"] for r in cur.fetchall()]
        if not roles:
            raise HTTPException(status_code=403, detail="Tài khoản chưa được phân công vai trò hiệu lực.")
        if payload.role and payload.role.upper() not in roles:
            raise HTTPException(status_code=403, detail="Tài khoản không được phân công vai trò yêu cầu.")
        active_role = payload.role.upper() if payload.role else roles[0]

        system_access = get_system_access_for_role(active_role)
        token = create_jwt_token({
            "sub": user_id,
            "username": user_row["username"],
            "full_name": user_row["full_name"],
            "active_role": active_role,
            "system_access": system_access,
            "session_version": user_row["session_version"],
        })

        return {
            "token": token,
            "user": {
                "id": user_id,
                "username": user_row["username"],
                "full_name": user_row["full_name"],
                "active_role": active_role,
                "roles": roles,
                "system_access": system_access,
            },
            "redirect": "/sod" if system_access == "sod_only" else "/overview"
        }


@router.post("/switch-role")
def switch_active_role(
    payload: SwitchRoleRequest,
    current_user: UserContext = Depends(get_current_user),
    conn = Depends(get_db_connection)
):
    """
    Chuyển đổi vai trò tức thì qua Topbar Role Switcher.
    Demo Mode: chuyển context sang Persona Identity tương ứng để hỗ trợ multi-party workflow.
    Production Mode: chỉ cho phép chọn vai trò thực tế được gán.
    Cập nhật session_version += 1 để vô hiệu hóa token cũ ngay lập tức.
    """
    target_role = payload.role.upper()
    allow_demo = os.getenv("ALLOW_DEMO_LOGIN", "false").lower() in {"1", "true", "yes"}
    is_demo = os.getenv("ENVIRONMENT", "").lower() != "production" or allow_demo

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        if is_demo:
            # Demo Mode: Tìm Persona Identity tương ứng với target_role (e.g. demo_req, demo_lm)
            cur.execute("""
                SELECT u.id, u.username, u.full_name, u.session_version
                FROM sod.users u
                JOIN sod.user_roles ur ON u.id = ur.user_id
                WHERE ur.role_code = %s AND u.username LIKE 'demo_%'
                LIMIT 1;
            """, (target_role,))
            row = cur.fetchone()
            if not row:
                # Nếu không tìm thấy demo_xxx, dùng user hiện tại
                cur.execute("SELECT id, username, full_name, session_version FROM sod.users WHERE id = %s;", (current_user.user_id,))
                row = cur.fetchone()

            if not row:
                raise HTTPException(status_code=400, detail=f"Không tìm thấy Persona mẫu cho vai trò {target_role}")

            user_id = str(row["id"])
            username = row["username"]
            full_name = row["full_name"]
            new_session_ver = row["session_version"] + 1
            cur.execute("UPDATE sod.users SET session_version = %s WHERE id = %s;", (new_session_ver, user_id))
        else:
            # Production Mode: Kiểm tra quyền gán thực tế
            cur.execute("""
                SELECT 1 FROM sod.user_roles
                WHERE user_id = %s AND role_code = %s
                  AND valid_from <= now() AND (valid_to IS NULL OR valid_to > now())
                  AND revoked_at IS NULL;
            """, (current_user.user_id, target_role))
            if not cur.fetchone():
                raise HTTPException(status_code=403, detail="Tài khoản không được phân công vai trò này")

            user_id = current_user.user_id
            username = current_user.username
            full_name = current_user.full_name
            new_session_ver = current_user.session_version + 1
            cur.execute("UPDATE sod.users SET session_version = %s WHERE id = %s;", (new_session_ver, user_id))

        conn.commit()

    system_access = get_system_access_for_role(target_role)
    new_token = create_jwt_token({
        "sub": user_id,
        "username": username,
        "full_name": full_name,
        "active_role": target_role,
        "system_access": system_access,
        "session_version": new_session_ver,
    })

    redirect_route = "/sod" if system_access == "sod_only" else "/overview"
    return {
        "token": new_token,
        "user": {
            "id": user_id,
            "username": username,
            "full_name": full_name,
            "active_role": target_role,
            "system_access": system_access,
        },
        "redirect": redirect_route
    }


@router.get("/me")
def get_me(current_user: UserContext = Depends(get_current_user)):
    """Trả về thông tin phiên người dùng và vai trò hiện tại."""
    return {
        "id": current_user.user_id,
        "username": current_user.username,
        "full_name": current_user.full_name,
        "active_role": current_user.active_role,
        "roles": current_user.roles,
        "system_access": current_user.system_access,
        "permissions": list(ROLE_PERMISSIONS.get(current_user.active_role, set())),
    }
