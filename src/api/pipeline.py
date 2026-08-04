import uuid
from fastapi import APIRouter, BackgroundTasks
from src.db.connection import get_db
from src.services.audit import AuditService

pipeline_router = APIRouter(prefix="/pipeline", tags=["Pipeline"])


@pipeline_router.post("/trigger")
async def trigger_pipeline(background_tasks: BackgroundTasks, table_name: str = "vgreen_telemetry"):
    """Trigger the analysis pipeline on a table."""
    run_id = str(uuid.uuid4())[:8]
    AuditService.log("PIPELINE_TRIGGER", "user", table_name, run_id, {"table": table_name})
    # In production, this would use BackgroundTasks to run the orchestrator
    return {"run_id": run_id, "status": "triggered", "table": table_name}


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
