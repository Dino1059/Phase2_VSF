from typing import List
from fastapi import APIRouter, Depends, HTTPException

from src.api.middleware import check_user_role
from src.models.schemas import ScheduleCreate, ScheduleResponse
from src.services.scheduler import scheduler_service


router = APIRouter(prefix="/schedules", tags=["schedules"], dependencies=[Depends(check_user_role)])


@router.post("", response_model=ScheduleResponse)
@router.post("/", response_model=ScheduleResponse)
async def create_schedule_endpoint(request: ScheduleCreate) -> ScheduleResponse:
    try:
        sched = scheduler_service.add_schedule(
            name=request.name,
            dataset_name=request.dataset_name,
            schedule_type=request.schedule_type,
            interval_seconds=request.interval_seconds,
            cron_expression=request.cron_expression,
            action=request.action,
        )
        return ScheduleResponse(**sched)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("", response_model=List[ScheduleResponse])
@router.get("/", response_model=List[ScheduleResponse])
async def get_schedules_endpoint() -> List[ScheduleResponse]:
    schedules = scheduler_service.get_schedules()
    return [ScheduleResponse(**s) for s in schedules]


@router.get("/{id}", response_model=ScheduleResponse)
async def get_schedule_by_id(id: str) -> ScheduleResponse:
    schedules = scheduler_service.get_schedules()
    for s in schedules:
        if s.get("id") == id:
            return ScheduleResponse(**s)
    raise HTTPException(status_code=404, detail=f"Schedule '{id}' not found.")


@router.delete("/{id}")
async def delete_schedule_endpoint(id: str):
    success = scheduler_service.delete_schedule(id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Schedule '{id}' not found.")
    return {"status": "success", "message": f"Schedule '{id}' deleted successfully."}
