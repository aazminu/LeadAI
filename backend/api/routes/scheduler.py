from fastapi import APIRouter
from pydantic import BaseModel

from scheduler.jobs import get_scheduler_runtime_status, scheduled_queue_kick, set_scheduler_time
from services.pipeline_queue import scheduler_status, set_scheduler_enabled

router = APIRouter(prefix="/api/scheduler", tags=["scheduler"])


class SchedulerToggle(BaseModel):
    enabled: bool


class SchedulerScheduleUpdate(BaseModel):
    hour: int
    minute: int


@router.get("")
async def get_scheduler():
    return {
        **scheduler_status(),
        "schedule": get_scheduler_runtime_status(),
    }


@router.post("/toggle")
async def toggle_scheduler(payload: SchedulerToggle):
    return await set_scheduler_enabled(payload.enabled)


@router.post("/run-now")
async def run_scheduler_now():
    await scheduled_queue_kick()
    return {
        "accepted": True,
        **scheduler_status(),
        "schedule": get_scheduler_runtime_status(),
    }


@router.post("/schedule")
async def update_scheduler_schedule(payload: SchedulerScheduleUpdate):
    if payload.hour < 0 or payload.hour > 23:
        return {"accepted": False, "error": "hour must be between 0 and 23"}
    if payload.minute < 0 or payload.minute > 59:
        return {"accepted": False, "error": "minute must be between 0 and 59"}

    return {
        "accepted": True,
        **scheduler_status(),
        "schedule": set_scheduler_time(payload.hour, payload.minute),
    }
