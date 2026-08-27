"""
src/memory/routes.py

Purpose: Workstream C — give every user direct, self-service visibility and
control over their own memory (Tầng 2 session summaries + Tầng 3 consolidated
profile), instead of it being an opaque store only engineers can inspect.
This mirrors the transparency the rest of DataTrust OS already demands of
itself: every rule mutation goes through `AuditService` and an HITL trail
(`src/api/hitl.py`); memory mutations get the same treatment here.

Role in the business flow: mounted onto the FastAPI app in `src/main.py`
alongside the other routers (`hitl_router`, `traces_router`, ...). Every
endpoint reads the caller's identity from `request.state.user_id` /
`request.state.user_role`, the same fields `src/middleware/auth.py`'s
`RoleMiddleware` already attaches to every authenticated request — no new
auth mechanism is introduced. Handlers call the module-level singletons
(`memory_store`, `user_memory_consolidator`) directly, the same convention
`src/api/hitl.py` already uses for `get_db()` — a plain class instance cannot
be a bare function-parameter default in a FastAPI route (FastAPI would try to
treat it as a request field and fail at startup), so it is never declared in
a handler signature.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from src.memory.schemas import MemoryEditRequest, SessionSummaryRecord, UserMemoryProfile, utcnow_iso
from src.memory.store import memory_store
from src.memory.user_memory import user_memory_consolidator
from src.middleware.auth import UserRole
from src.services.audit import AuditService

memory_router = APIRouter(prefix="/memory", tags=["Memory"])

_ADMIN_ROLES = {UserRole.ADMIN.value, "Admin"}


def _require_self_or_admin(request: Request, target_user_id: str) -> str:
    """Purpose: shared authorization guard for every endpoint in this file.
    Input: the inbound `Request` (carrying `state.user_id`/`state.user_role`
    set by `RoleMiddleware`) and the `user_id` path segment being accessed.
    Output: the caller's own `user_id`, for logging as the `actor`.
    Raises: `HTTPException(403)` if the caller is neither the memory owner
    nor an Admin — a user's memory is private to them by default.
    """
    caller_id = getattr(request.state, "user_id", None)
    caller_role = getattr(request.state, "user_role", None)
    caller_role_value = getattr(caller_role, "value", caller_role)

    if not caller_id:
        raise HTTPException(status_code=401, detail="Unauthorized: no resolved user identity")
    if caller_id != target_user_id and caller_role_value not in _ADMIN_ROLES:
        raise HTTPException(
            status_code=403,
            detail="Forbidden: you may only view or modify your own memory",
        )
    return caller_id


@memory_router.get("/{user_id}/profile", response_model=UserMemoryProfile | None)
async def get_user_memory_profile(user_id: str, request: Request, refresh: bool = True):
    """Purpose: Workstream C "view" — return the caller's Tầng 3 consolidated
    memory. Output: `None` (HTTP 200 with `null` body) if no sessions have
    ever been summarized for this user yet — that is a valid, non-error state
    for a new user, not a 404.
    """
    _require_self_or_admin(request, user_id)
    if refresh:
        return user_memory_consolidator.consolidate(user_id)
    return memory_store.get_profile(user_id)


@memory_router.get("/{user_id}/sessions", response_model=list[SessionSummaryRecord])
async def list_user_session_summaries(user_id: str, request: Request, limit: int = 50):
    """Purpose: Workstream C "view" — return the caller's Tầng 2 episodic
    memory (one entry per past session), newest first, so a user can see
    exactly which sessions fed their consolidated profile.
    """
    _require_self_or_admin(request, user_id)
    return memory_store.list_summaries_for_user(user_id, limit=limit)


@memory_router.patch("/{user_id}/profile", response_model=UserMemoryProfile)
async def edit_user_memory_profile(user_id: str, payload: MemoryEditRequest, request: Request):
    """Purpose: Workstream C "edit" — let a user correct their own long-term
    memory (e.g. override a narrative that misreads their intent, or reset the
    rule-decision counters) without an engineer touching the database.
    Output: the updated `UserMemoryProfile`.
    Raises: `HTTPException(404)` if the user has no profile yet — there is
    nothing to edit until at least one session has been consolidated.
    """
    actor = _require_self_or_admin(request, user_id)
    profile = memory_store.get_profile(user_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="No memory profile exists for this user yet")

    if payload.narrative is not None:
        profile.narrative = payload.narrative
    if payload.reset_rule_decision_pattern:
        profile.rule_decision_pattern = {"approved": 0, "rejected": 0, "edited": 0}
        profile.approval_rate = None

    profile.updated_at = utcnow_iso()
    memory_store.upsert_profile(profile)

    AuditService.log(
        action="EDIT_USER_MEMORY",
        actor=payload.edited_by if payload.edited_by != "self" else actor,
        target_table="memory_user_profile",
        target_id=user_id,
        details={
            "narrative_changed": payload.narrative is not None,
            "rule_decision_pattern_reset": payload.reset_rule_decision_pattern,
        },
    )
    return profile


@memory_router.delete("/{user_id}/profile")
async def delete_user_memory_profile(user_id: str, request: Request):
    """Purpose: Workstream C "delete" — right-to-be-forgotten for Tầng 3.
    Removes the consolidated profile only; Tầng 2 session summaries are left
    intact unless the caller also calls the session-level delete endpoints, so
    a full erase is two explicit actions rather than one that could be fired
    by accident.
    """
    actor = _require_self_or_admin(request, user_id)
    deleted = memory_store.delete_profile(user_id)
    if deleted:
        AuditService.log(
            action="DELETE_USER_MEMORY",
            actor=actor,
            target_table="memory_user_profile",
            target_id=user_id,
        )
    return {"deleted": deleted, "user_id": user_id}


@memory_router.delete("/{user_id}/sessions/{summary_id}")
async def delete_session_summary(user_id: str, summary_id: str, request: Request):
    """Purpose: Workstream C "delete" — forget one specific past session
    ("quên chuyện đó đi") without wiping the entire consolidated profile.
    Note: deleting a summary after it has already been folded into the Tầng 3
    profile does not retroactively un-merge those counts — the profile only
    reflects summaries observed *up to* its last consolidation. This is
    documented behaviour, not a bug: full removal of a session's influence
    requires also editing/resetting the profile via the endpoints above.
    """
    actor = _require_self_or_admin(request, user_id)
    deleted = memory_store.delete_summary(summary_id, user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Session summary not found for this user")
    AuditService.log(
        action="DELETE_SESSION_SUMMARY",
        actor=actor,
        target_table="memory_session_summaries",
        target_id=summary_id,
    )
    return {"deleted": True, "summary_id": summary_id}


@memory_router.delete("/{user_id}")
async def delete_all_user_memory(user_id: str, request: Request):
    """Purpose: Workstream C "delete" — full erase of both memory tiers for
    one user (Tầng 2 summaries + Tầng 3 profile) in one explicit call.
    """
    actor = _require_self_or_admin(request, user_id)
    memory_store.delete_all_summaries_for_user(user_id)
    profile_deleted = memory_store.delete_profile(user_id)
    AuditService.log(
        action="DELETE_ALL_USER_MEMORY",
        actor=actor,
        target_table="memory_user_profile,memory_session_summaries",
        target_id=user_id,
    )
    return {"deleted": True, "profile_existed": profile_deleted, "user_id": user_id}
