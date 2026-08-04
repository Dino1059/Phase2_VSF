import uuid
from typing import Optional
from fastapi import APIRouter, BackgroundTasks, HTTPException
from src.db.connection import get_db
from src.services.audit import AuditService

pipeline_router = APIRouter(prefix="/pipeline", tags=["Pipeline"])


def check_pipeline_rule_approved(rule_id: Optional[str] = None, table_name: str = "vgreen_telemetry"):
    db = get_db()
    if rule_id:
        rules = db.execute("SELECT id, status FROM quality_rules WHERE id = ?", [rule_id])
        if not rules or rules[0][1] not in ("approved", "edited"):
            raise HTTPException(
                status_code=403,
                detail="Rule execution denied: Rule is not approved by HITL"
            )
    else:
        unapproved = db.execute(
            "SELECT id FROM quality_rules WHERE (snapshot_id = ? OR rule_name LIKE ?) AND status NOT IN ('approved', 'edited')",
            [table_name, f"%{table_name}%"]
        )
        if unapproved:
            raise HTTPException(
                status_code=403,
                detail="Rule execution denied: Rule is not approved by HITL"
            )


@pipeline_router.post("/trigger")
async def trigger_pipeline(
    background_tasks: BackgroundTasks,
    table_name: str = "vgreen_telemetry",
    rule_id: Optional[str] = None,
):
    """Trigger the analysis pipeline on a table."""
    check_pipeline_rule_approved(rule_id, table_name)
    run_id = str(uuid.uuid4())[:8]
    AuditService.log("PIPELINE_TRIGGER", "user", table_name, run_id, {"table": table_name})
    return {"run_id": run_id, "status": "triggered", "table": table_name}


@pipeline_router.post("/execute")
async def execute_pipeline(
    rule_id: Optional[str] = None,
    table_name: str = "vgreen_telemetry",
):
    """Execute pipeline for table/rule."""
    check_pipeline_rule_approved(rule_id, table_name)
    run_id = str(uuid.uuid4())[:8]
    return {"run_id": run_id, "status": "executed", "table": table_name}


@pipeline_router.get("/status/{run_id}")
async def get_pipeline_status(run_id: str):
    db = get_db()
    traces = db.execute("SELECT agent_type, step_index, action, timestamp FROM agent_traces WHERE session_id = ? ORDER BY step_index", [run_id])
    if not traces:
        return {"run_id": run_id, "status": "not_found", "steps": []}
    return {
        "run_id": run_id,
        "status": "completed",
        "steps": [{"agent": t[0], "step": t[1], "action": t[2], "timestamp": str(t[3]) if t[3] else None} for t in traces]
    }
