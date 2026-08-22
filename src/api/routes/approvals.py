from typing import List
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from src.api.middleware import check_user_role
from src.db.connection import get_db


router = APIRouter(prefix="/approvals", tags=["approvals"], dependencies=[Depends(check_user_role)])


class BatchApprovalRequest(BaseModel):
    rule_ids: List[str]
    action: str  # "approve" or "reject"


@router.get("", summary="List pending HITL rule approvals")
@router.get("/", summary="List pending HITL rule approvals")
async def list_pending_approvals():
    db = get_db()
    try:
        rows = db.execute(
            "SELECT id, rule_type, rule_name, status, rule_expression FROM quality_rules WHERE status IN ('pending', 'proposed')"
        )
        return [
            {
                "id": r[0],
                "rule_type": r[1],
                "rule_name": r[2],
                "status": r[3],
                "description": r[4],
            }
            for r in rows
        ]
    except Exception:
        return []


@router.post("/{rule_id}/approve")
async def approve_rule(rule_id: str):
    db = get_db()
    try:
        db.execute("UPDATE quality_rules SET status = 'approved', approved_at = CURRENT_TIMESTAMP WHERE id = ?", [rule_id])
        quarantined_count = 0
        try:
            from src.api.routes.rules import quarantine_violating_data_for_rule
            q_res = quarantine_violating_data_for_rule(rule_id, db=db)
            quarantined_count = q_res.get("quarantined_count", 0)
        except Exception as qe:
            print(f"[WARN] Error executing quarantine on approval: {qe}")
        return {"status": "approved", "rule_id": rule_id, "quarantined_count": quarantined_count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{rule_id}/reject")
async def reject_rule(rule_id: str):
    db = get_db()
    try:
        db.execute("UPDATE quality_rules SET status = 'rejected' WHERE id = ?", [rule_id])
        return {"status": "rejected", "rule_id": rule_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/batch")
async def batch_approval(request: BatchApprovalRequest):
    if request.action not in ("approve", "reject"):
        raise HTTPException(status_code=400, detail="Action must be 'approve' or 'reject'")
    target_status = "approved" if request.action == "approve" else "rejected"
    db = get_db()
    total_quarantined = 0
    try:
        for rid in request.rule_ids:
            db.execute("UPDATE quality_rules SET status = ?, approved_at = CURRENT_TIMESTAMP WHERE id = ?", [target_status, rid])
            if target_status == "approved":
                try:
                    from src.api.routes.rules import quarantine_violating_data_for_rule
                    q_res = quarantine_violating_data_for_rule(rid, db=db)
                    total_quarantined += q_res.get("quarantined_count", 0)
                except Exception:
                    pass
        return {
            "status": "success",
            "processed_count": len(request.rule_ids),
            "new_status": target_status,
            "total_quarantined": total_quarantined,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class AuthorizeRequest(BaseModel):
    dataset_key: str
    rule_ids: List[str]


@router.post("/authorize", summary="Authorize execution of approved rules for a dataset")
async def authorize_execution(request: AuthorizeRequest):
    import json
    import uuid
    import hashlib
    db = get_db()
    try:
        # Check that rules exist and are approved
        for rid in request.rule_ids:
            rows = db.execute("SELECT status FROM quality_rules WHERE id = ?", [rid])
            if not rows or rows[0][0] != "approved":
                raise HTTPException(
                    status_code=403,
                    detail=f"Rule '{rid}' is not approved by HITL. Execution authorization denied.",
                )

        auth_id = f"auth_{uuid.uuid4().hex[:12]}"
        payload_str = f"{request.dataset_key}:{sorted(request.rule_ids)}"
        payload_hash = hashlib.sha256(payload_str.encode("utf-8")).hexdigest()

        db.execute(
            """
            INSERT INTO execution_authorizations (id, dataset_key, rule_ids, actor, payload_hash)
            VALUES (?, ?, ?, ?, ?)
            """,
            [auth_id, request.dataset_key, json.dumps(request.rule_ids), "HITL_USER", payload_hash],
        )

        return {
            "authorization_id": auth_id,
            "dataset_key": request.dataset_key,
            "rule_ids": request.rule_ids,
            "status": "authorized",
            "payload_hash": payload_hash,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

