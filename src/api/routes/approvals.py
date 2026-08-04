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
            "SELECT id, rule_type, rule_name, status, rule_expression FROM quality_rules WHERE status = 'pending'"
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
        db.execute("UPDATE quality_rules SET status = 'approved' WHERE id = ?", [rule_id])
        return {"status": "approved", "rule_id": rule_id}
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
    try:
        for rid in request.rule_ids:
            db.execute("UPDATE quality_rules SET status = ? WHERE id = ?", [target_status, rid])
        return {
            "status": "success",
            "processed_count": len(request.rule_ids),
            "new_status": target_status,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
