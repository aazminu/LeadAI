import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from config import settings
from services.pipeline_queue import ensure_worker_running, recover_stalled_leads

logger = logging.getLogger(__name__)

_scheduler = AsyncIOScheduler(timezone="America/New_York")
_started = False


async def scheduled_queue_kick():
    recovered = await recover_stalled_leads()
    logger.info("scheduled_queue_kick recovered=%s", recovered)
    ensure_worker_running()


def start_scheduler() -> AsyncIOScheduler:
    global _started
    if _started:
        return _scheduler

    _scheduler.add_job(
        scheduled_queue_kick,
        CronTrigger(hour=settings.scheduler_hour, minute=settings.scheduler_minute),
        id="daily_queue_kick",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    _scheduler.start()
    _started = True
    logger.info(
        "scheduler_started hour=%s minute=%s",
        settings.scheduler_hour,
        settings.scheduler_minute,
    )
    return _scheduler


def set_scheduler_time(hour: int, minute: int) -> dict:
    settings.scheduler_hour = hour
    settings.scheduler_minute = minute
    if _started:
        _scheduler.add_job(
            scheduled_queue_kick,
            CronTrigger(hour=hour, minute=minute),
            id="daily_queue_kick",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )
    logger.info("scheduler_rescheduled hour=%s minute=%s", hour, minute)
    return get_scheduler_runtime_status()


def stop_scheduler() -> None:
    global _started
    if _started:
        _scheduler.shutdown(wait=False)
        _started = False


def get_scheduler_runtime_status() -> dict:
    job = _scheduler.get_job("daily_queue_kick")
    next_run = job.next_run_time if job and job.next_run_time else None
    return {
        "running": _started and _scheduler.running,
        "job_id": job.id if job else None,
        "next_run": next_run.isoformat() if next_run else None,
        "next_run_display": next_run.strftime("%b %-d, %Y %-I:%M %p %Z") if next_run else None,
        "hour": settings.scheduler_hour,
        "minute": settings.scheduler_minute,
    }
