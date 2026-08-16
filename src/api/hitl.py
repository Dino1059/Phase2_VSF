import uuid
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, HTTPException

from src.db.connection import get_db
from src.models.hitl import RuleProposalCard, ApproveRequest, RejectRequest, EditRequest
from src.services.audit import AuditService

hitl_router = APIRouter(prefix="/hitl", tags=["HITL"])


def check_rule_approved(rule_id: str):
    """Verify rule exists in DuckDB quality_rules table and status is approved or edited."""
    db = get_db()
    rules = db.execute("SELECT id, status FROM quality_rules WHERE id = ?", [rule_id])
    if not rules or rules[0][1] not in ("approved", "edited"):
        raise HTTPException(
            status_code=403,
            detail="Rule execution denied: Rule is not approved by HITL"
        )
    return rules[0]


@hitl_router.get("/queue")
async def get_queue():
    db = get_db()
    rows = db.execute("SELECT id, rule_name, rule_type, rule_expression, confidence, status, proposed_by, created_at FROM quality_rules WHERE status IN ('pending', 'proposed') ORDER BY created_at DESC")
    return {"proposals": [
        {"rule_id": r[0], "rule_name": r[1], "rule_type": r[2], "rule_expression": r[3],
         "confidence": r[4], "status": r[5], "proposed_by": r[6], "proposed_at": str(r[7]) if r[7] else None}
        for r in rows
    ]}


@hitl_router.post("/approve/{rule_id}")
async def approve_rule(rule_id: str, req: ApproveRequest = ApproveRequest()):
    db = get_db()
    rules = db.execute("SELECT id, status FROM quality_rules WHERE id = ?", [rule_id])
    if not rules:
        raise HTTPException(status_code=404, detail=f"Rule {rule_id} not found")
    if rules[0][1] not in ("proposed", "pending", "draft"):
        raise HTTPException(status_code=400, detail=f"Rule {rule_id} is '{rules[0][1]}', not 'proposed'")

    db.execute("UPDATE quality_rules SET status = 'approved', approved_by = ?, approved_at = ? WHERE id = ?",
               [req.approved_by, datetime.now().isoformat(), rule_id])

    AuditService.log("APPROVE_RULE", req.approved_by, "quality_rules", rule_id,
                     {"state_hash": AuditService.compute_state_hash(rule_id, "", "approved")})
    return {"status": "approved", "rule_id": rule_id}


@hitl_router.post("/reject/{rule_id}")
async def reject_rule(rule_id: str, req: RejectRequest = RejectRequest()):
    db = get_db()
    rules = db.execute("SELECT id, status FROM quality_rules WHERE id = ?", [rule_id])
    if not rules:
        raise HTTPException(status_code=404, detail=f"Rule {rule_id} not found")

    db.execute("UPDATE quality_rules SET status = 'rejected' WHERE id = ?", [rule_id])
    AuditService.log("REJECT_RULE", req.rejected_by, "quality_rules", rule_id,
                     {"reason": req.reason})
    return {"status": "rejected", "rule_id": rule_id}


@hitl_router.post("/edit/{rule_id}")
async def edit_rule(rule_id: str, req: EditRequest):
    db = get_db()
    rules = db.execute("SELECT id, status FROM quality_rules WHERE id = ?", [rule_id])
    if not rules:
        raise HTTPException(status_code=404, detail=f"Rule {rule_id} not found")

    db.execute("UPDATE quality_rules SET rule_expression = ?, status = 'edited' WHERE id = ?",
               [req.rule_expression, rule_id])
    AuditService.log("EDIT_RULE", req.edited_by, "quality_rules", rule_id,
                     {"new_expression": req.rule_expression})
    return {"status": "edited", "rule_id": rule_id}


@hitl_router.post("/execute/{rule_id}")
async def execute_hitl_rule(rule_id: str):
    check_rule_approved(rule_id)
    return {"status": "executed", "rule_id": rule_id}


@hitl_router.post("/execute")
async def execute_hitl_rules(payload: Optional[dict] = None):
    rule_id = payload.get("rule_id") if payload else None
    if not rule_id:
        raise HTTPException(
            status_code=403,
            detail="Rule execution denied: Rule is not approved by HITL"
        )
    check_rule_approved(rule_id)
    return {"status": "executed", "rule_id": rule_id}


@hitl_router.get("/history")
async def get_history():
    return {"history": AuditService.get_history(limit=100)}


@hitl_router.post("/reset")
async def reset_hitl_and_rules():
    db = get_db()
    deleted_counts = {}
    for tbl in ["quality_rules", "audit_log", "quarantine", "execution_authorizations", "decisions", "evidence"]:
        try:
            db.execute(f"DELETE FROM {tbl}")
            deleted_counts[tbl] = "cleared"
        except Exception as e:
            deleted_counts[tbl] = str(e)
    return {
        "status": "success",
        "message": "DB rule history and audit log reset successfully",
        "details": deleted_counts
    }

