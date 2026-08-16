import uuid
from typing import Any, Dict, Optional
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse
import pandas as pd

from src.api.middleware import check_user_role
from src.api.state_machine import WorkflowState
from src.api.routes import state_machine, audit_store
from src.models.schemas import ProfileRequest, ProfileResponse
from src.tools.profiler import Profiler


router = APIRouter(prefix="/profile", tags=["profiling"], dependencies=[Depends(check_user_role)])
profiler = Profiler()

# In-memory background jobs registry
profiling_jobs: Dict[str, Dict[str, Any]] = {}


def _run_background_profiling(job_id: str, data: list):
    try:
        df = pd.DataFrame(data)
        report = profiler.profile(df)
        state_machine.row_count = report.row_count

        if state_machine.current_state == WorkflowState.INIT:
            state_machine.transition_to(WorkflowState.PROFILED)

        audit_store.record_event(
            "profile_async",
            {"row_count": report.row_count, "column_count": report.column_count, "job_id": job_id},
        )

        profiling_jobs[job_id] = {
            "job_id": job_id,
            "status": "completed",
            "result": {
                "snapshot_id": report.snapshot_id,
                "row_count": report.row_count,
                "column_count": report.column_count,
                "duplicate_count": report.duplicate_count,
                "columns": [c.model_dump() for c in report.columns],
            },
        }
    except Exception as e:
        profiling_jobs[job_id] = {"job_id": job_id, "status": "failed", "error": str(e)}


@router.post("", status_code=200)
@router.post("/", status_code=200)
async def profile_endpoint(
    request: ProfileRequest,
    background_tasks: BackgroundTasks,
    async_mode: bool = Query(False, alias="async"),
):
    """Profile data synchronously or asynchronously via HTTP 202 Accepted when async=true."""
    if async_mode:
        job_id = f"prof_job_{uuid.uuid4().hex[:8]}"
        profiling_jobs[job_id] = {"job_id": job_id, "status": "accepted", "result": None}
        background_tasks.add_task(_run_background_profiling, job_id, request.data)
        return JSONResponse(
            status_code=status.HTTP_202_ACCEPTED,
            content={
                "job_id": job_id,
                "status": "accepted",
                "message": "Profiling task queued for background execution",
            },
        )

    try:
        df = pd.DataFrame(request.data)
        report = profiler.profile(df)
        state_machine.row_count = report.row_count

        if state_machine.current_state == WorkflowState.INIT:
            state_machine.transition_to(WorkflowState.PROFILED)

        audit_store.record_event(
            "profile", {"row_count": report.row_count, "column_count": report.column_count}
        )

        return ProfileResponse(
            snapshot_id=report.snapshot_id,
            row_count=report.row_count,
            column_count=report.column_count,
            duplicate_count=report.duplicate_count,
            columns=[c.model_dump() for c in report.columns],
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/async", status_code=status.HTTP_202_ACCEPTED)
async def profile_async_endpoint(
    request: ProfileRequest,
    background_tasks: BackgroundTasks,
):
    """Trigger async dataset profiling background task returning HTTP 202 Accepted."""
    job_id = f"prof_job_{uuid.uuid4().hex[:8]}"
    profiling_jobs[job_id] = {"job_id": job_id, "status": "accepted", "result": None}
    background_tasks.add_task(_run_background_profiling, job_id, request.data)
    return JSONResponse(
        status_code=status.HTTP_202_ACCEPTED,
        content={
            "job_id": job_id,
            "status": "accepted",
            "message": "Profiling task queued for background execution",
        },
    )


@router.get("/jobs/{job_id}")
async def get_profiling_job_status(job_id: str):
    """Retrieve async profiling job status."""
    if job_id not in profiling_jobs:
        raise HTTPException(status_code=404, detail=f"Profiling job '{job_id}' not found.")
    return profiling_jobs[job_id]
