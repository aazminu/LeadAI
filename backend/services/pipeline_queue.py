import asyncio
import json
import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, AsyncIterator

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from agents.orchestrator import real_graph
from db.database import AsyncSessionLocal
from db.models import EnrichmentResult, Lead, LeadStatus, LeadTier, PipelineEvent

logger = logging.getLogger(__name__)

MAX_PIPELINE_ATTEMPTS = 2
STALLED_AFTER_MINUTES = 30


class PipelineEventBus:
    def __init__(self):
        self._subscribers: dict[str, set[asyncio.Queue]] = defaultdict(set)
        self._sequence_lock = asyncio.Lock()

    async def subscribe(self, lead_id: str) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue()
        self._subscribers[lead_id].add(queue)
        return queue

    def unsubscribe(self, lead_id: str, queue: asyncio.Queue) -> None:
        self._subscribers[lead_id].discard(queue)
        if not self._subscribers[lead_id]:
            self._subscribers.pop(lead_id, None)

    async def emit(
        self,
        lead_id: str,
        event_type: str,
        agent: str | None = None,
        icon: str | None = None,
        message: str | None = None,
        detail: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        async with self._sequence_lock:
            async with AsyncSessionLocal() as session:
                next_sequence = await session.scalar(
                    select(func.coalesce(func.max(PipelineEvent.sequence), 0) + 1)
                    .where(PipelineEvent.lead_id == lead_id)
                )
                event = PipelineEvent(
                    lead_id=lead_id,
                    sequence=next_sequence,
                    event_type=event_type,
                    agent=agent,
                    icon=icon,
                    message=message,
                    detail=detail,
                    payload=payload or {},
                )
                session.add(event)
                await session.commit()

        data = {
            "id": event.id,
            "lead_id": lead_id,
            "sequence": event.sequence,
            "event": event.event_type,
            "agent": event.agent,
            "icon": event.icon,
            "message": event.message,
            "detail": event.detail,
            "payload": event.payload or {},
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        for queue in list(self._subscribers.get(lead_id, [])):
            await queue.put(data)

        return data

    async def replay(self, lead_id: str) -> list[dict[str, Any]]:
        async with AsyncSessionLocal() as session:
            rows = (
                await session.execute(
                    select(PipelineEvent)
                    .where(PipelineEvent.lead_id == lead_id)
                    .order_by(PipelineEvent.sequence)
                )
            ).scalars().all()

        return [
            {
                "id": row.id,
                "lead_id": row.lead_id,
                "sequence": row.sequence,
                "event": row.event_type,
                "agent": row.agent,
                "icon": row.icon,
                "message": row.message,
                "detail": row.detail,
                "payload": row.payload or {},
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
            for row in rows
        ]


event_bus = PipelineEventBus()
_worker_lock = asyncio.Lock()
_worker_task: asyncio.Task | None = None
_scheduler_enabled = True


class StreamingStepEmitter:
    def __init__(self, lead_id: str, agent_name: str):
        self.lead_id = lead_id
        self.agent_name = agent_name
        self.steps: list[dict[str, Any]] = []

    def emit(
        self,
        message: str,
        detail: str | None = None,
        icon: str = "🔍",
        status: str = "done",
    ) -> dict[str, Any]:
        step = {
            "agent": self.agent_name,
            "icon": icon,
            "message": message,
            "detail": detail,
            "status": status,
            "lead_id": self.lead_id,
        }
        self.steps.append(step)
        asyncio.create_task(
            event_bus.emit(
                self.lead_id,
                "step",
                agent=self.agent_name,
                icon=icon,
                message=message,
                detail=detail,
                payload={"status": status},
            )
        )
        return step

    def get_steps(self) -> list[dict[str, Any]]:
        return self.steps


def sse_format(event: dict[str, Any]) -> str:
    return f"event: {event.get('event', 'message')}\ndata: {json.dumps(event, default=str)}\n\n"


async def stream_lead_events(lead_id: str) -> AsyncIterator[str]:
    replayed = await event_bus.replay(lead_id)
    for event in replayed:
        yield sse_format(event)

    if replayed and replayed[-1].get("event") == "done":
        return

    queue = await event_bus.subscribe(lead_id)
    try:
        while True:
            event = await queue.get()
            yield sse_format(event)
            if event.get("event") in {"done"}:
                break
    finally:
        event_bus.unsubscribe(lead_id, queue)


async def enqueue_lead(lead: Lead) -> None:
    await event_bus.emit(
        lead.id,
        "queued",
        icon="⏳",
        message="Lead queued",
        detail=lead.company,
        payload={"status": LeadStatus.queued.value},
    )
    ensure_worker_running()


def ensure_worker_running() -> None:
    global _worker_task
    if _worker_task and not _worker_task.done():
        return
    _worker_task = asyncio.create_task(_worker_loop())


def scheduler_status() -> dict[str, Any]:
    return {
        "enabled": _scheduler_enabled,
        "worker_running": _worker_task is not None and not _worker_task.done(),
        "max_pipeline_attempts": MAX_PIPELINE_ATTEMPTS,
        "stalled_after_minutes": STALLED_AFTER_MINUTES,
    }


async def set_scheduler_enabled(enabled: bool) -> dict[str, Any]:
    global _scheduler_enabled
    _scheduler_enabled = enabled
    if enabled:
        ensure_worker_running()
    return scheduler_status()


async def _worker_loop() -> None:
    if _worker_lock.locked():
        return

    async with _worker_lock:
        await recover_stalled_leads()
        while _scheduler_enabled:
            lead = await _claim_next_queued_lead()
            if not lead:
                return
            await _run_pipeline_for_lead(lead)


async def _claim_next_queued_lead() -> Lead | None:
    async with AsyncSessionLocal() as session:
        while True:
            lead = (
                await session.execute(
                    select(Lead)
                    .options(selectinload(Lead.enrichment))
                    .where(Lead.status.in_([LeadStatus.queued, LeadStatus.pending]))
                    .order_by(Lead.created_at)
                    .limit(1)
                    .with_for_update(skip_locked=True)
                )
            ).scalar_one_or_none()

            if not lead:
                return None

            if lead.enrichment and lead.enrichment.outreach_complete:
                lead.status = (
                    LeadStatus.disqualified
                    if lead.enrichment.tier == LeadTier.disqualified
                    else LeadStatus.complete
                )
                lead.completed_at = lead.completed_at or datetime.now(timezone.utc)
                lead.updated_at = datetime.now(timezone.utc)
                await session.commit()
                continue

            lead.status = LeadStatus.processing
            lead.attempt_count = (lead.attempt_count or 0) + 1
            lead.last_error = None
            lead.updated_at = datetime.now(timezone.utc)
            await session.commit()
            await session.refresh(lead)
            return lead


async def recover_stalled_leads() -> int:
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=STALLED_AFTER_MINUTES)
    recovered = 0

    async with AsyncSessionLocal() as session:
        leads = (
            await session.execute(
                select(Lead)
                .where(Lead.status == LeadStatus.processing)
                .where(Lead.updated_at.is_not(None))
                .where(Lead.updated_at < cutoff)
                .with_for_update(skip_locked=True)
            )
        ).scalars().all()

        for lead in leads:
            if (lead.attempt_count or 0) < MAX_PIPELINE_ATTEMPTS:
                lead.status = LeadStatus.queued
                lead.last_error = "Recovered stalled processing lead and requeued"
                event_type = "pipeline_requeued"
                message = "Stalled pipeline requeued"
            else:
                lead.status = LeadStatus.failed
                lead.last_error = "Pipeline stalled after maximum retry attempts"
                event_type = "pipeline_failed"
                message = "Stalled pipeline failed"

            recovered += 1
            await event_bus.emit(
                lead.id,
                event_type,
                icon="↻" if lead.status == LeadStatus.queued else "⚠️",
                message=message,
                detail=lead.last_error,
                payload={
                    "status": lead.status.value,
                    "attempt_count": lead.attempt_count,
                },
            )

        await session.commit()

    return recovered


async def _run_pipeline_for_lead(lead: Lead) -> None:
    await event_bus.emit(
        lead.id,
        "pipeline_started",
        icon="▶️",
        message="Pipeline started",
        detail=lead.company,
        payload={"status": LeadStatus.processing.value},
    )

    async with AsyncSessionLocal() as session:
        existing = await session.execute(
            select(EnrichmentResult).where(
                EnrichmentResult.lead_id == lead.id
            )
        )
        if not existing.scalar_one_or_none():
            session.add(EnrichmentResult(lead_id=lead.id))
            await session.commit()

            
    state = {
        "lead_id": lead.id,
        "name": lead.name,
        "email": lead.email,
        "company": lead.company,
        "property_address": lead.property_address,
        "city": lead.city,
        "state": lead.state,
        "country": lead.country,
        "completed_agents": [],
        "errors": {},
        "status": LeadStatus.processing.value,
        "emitter_factory": lambda agent_name: StreamingStepEmitter(lead.id, agent_name),
        "completion_callback": lambda agent_name, output: persist_agent_completion(
            lead.id, agent_name, output
        ),
    }

    try:
        result = await real_graph.ainvoke(state)
        terminal_status = (
            LeadStatus.disqualified
            if result.get("tier") == "disqualified" or result.get("status") == "disqualified"
            else LeadStatus.complete
        )

        async with AsyncSessionLocal() as session:
            await save_pipeline_result(lead.id, result, session, commit=False)
            db_lead = await session.get(Lead, lead.id)
            if db_lead:
                db_lead.status = terminal_status
                db_lead.completed_at = datetime.now(timezone.utc)
            await session.commit()

        await event_bus.emit(
            lead.id,
            "pipeline_complete",
            icon="✅",
            message="Pipeline complete",
            detail=lead.company,
            payload={
                "status": terminal_status.value,
                "score": result.get("score"),
                "tier": result.get("tier"),
                "email_draft": result.get("email_draft"),
                "email_subject": result.get("email_subject"),
            },
        )
    except Exception as exc:
        logger.exception("Pipeline failed for lead %s", lead.id)
        should_retry = False
        attempt_count = 0
        async with AsyncSessionLocal() as session:
            db_lead = await session.get(Lead, lead.id)
            if db_lead:
                attempt_count = db_lead.attempt_count or 0
                db_lead.last_error = str(exc)
                if attempt_count < MAX_PIPELINE_ATTEMPTS:
                    db_lead.status = LeadStatus.queued
                    should_retry = True
                else:
                    db_lead.status = LeadStatus.failed
            await session.commit()

        if should_retry:
            await event_bus.emit(
                lead.id,
                "pipeline_retry_scheduled",
                icon="↻",
                message="Pipeline failed; retry queued",
                detail=str(exc),
                payload={
                    "status": LeadStatus.queued.value,
                    "attempt_count": attempt_count,
                    "max_attempts": MAX_PIPELINE_ATTEMPTS,
                },
            )
        else:
            await event_bus.emit(
                lead.id,
                "pipeline_failed",
                icon="⚠️",
                message="Pipeline failed",
                detail=str(exc),
                payload={
                    "status": LeadStatus.failed.value,
                    "attempt_count": attempt_count,
                    "max_attempts": MAX_PIPELINE_ATTEMPTS,
                },
            )
    finally:
        await event_bus.emit(lead.id, "done", message="Stream closed")


async def persist_agent_completion(
    lead_id: str,
    agent: str,
    output: dict[str, Any],
) -> None:
    async with AsyncSessionLocal() as session:
        stmt = select(EnrichmentResult).where(EnrichmentResult.lead_id == lead_id)
        existing = await session.execute(stmt)
        enrichment = existing.scalar_one_or_none()

        if not enrichment:
            enrichment = EnrichmentResult(lead_id=lead_id)
            session.add(enrichment)

        data = _agent_output_payload(agent, output)
        if agent == "identity":
            enrichment.identity_data = output.get("identity_data")
            enrichment.identity_complete = True
        elif agent == "company":
            enrichment.company_data = output.get("company_data")
            enrichment.company_complete = True
        elif agent == "market":
            enrichment.market_data = output.get("market_data")
            enrichment.market_complete = True
        elif agent == "property":
            enrichment.property_data = output.get("property_data")
            enrichment.property_complete = True
        elif agent == "values":
            enrichment.values_data = output.get("values_data")
            enrichment.values_complete = True
        elif agent == "scoring":
            enrichment.scoring_complete = True
            enrichment.score = output.get("score")
            enrichment.score_breakdown = output.get("score_breakdown")
            enrichment.score_reasoning = output.get("score_reasoning")
            enrichment.reasoning_steps = output.get("reasoning_steps")
            enrichment.insights = output.get("insights")
            enrichment.recommended_action = output.get("recommended_action")
            tier_str = output.get("tier")
            if tier_str:
                try:
                    enrichment.tier = LeadTier(tier_str)
                except ValueError:
                    enrichment.tier = None
        elif agent == "outreach":
            enrichment.outreach_complete = True
            enrichment.email_subject = output.get("email_subject")
            enrichment.email_draft = output.get("email_draft")
            enrichment.pitch_angle = output.get("pitch_angle")
            enrichment.talking_points = output.get("talking_points")
            enrichment.signal_used = output.get("signal_used")

        existing_agents = enrichment.completed_agents or []
        if agent not in existing_agents:
            enrichment.completed_agents = [*existing_agents, agent]

        if output.get("errors"):
            enrichment.errors = {**(enrichment.errors or {}), **output["errors"]}

        await session.commit()

    await event_bus.emit(
        lead_id,
        "agent_complete",
        agent=agent,
        icon="✅",
        message=f"{agent.title()} agent complete",
        payload={"agent": agent, "data": data},
    )


def _agent_output_payload(agent: str, output: dict[str, Any]) -> Any:
    agent_outputs = {
        "identity": output.get("identity_data"),
        "company": output.get("company_data"),
        "market": output.get("market_data"),
        "property": output.get("property_data"),
        "values": output.get("values_data"),
        "scoring": {
            "score": output.get("score"),
            "tier": output.get("tier"),
            "score_breakdown": output.get("score_breakdown"),
            "score_reasoning": output.get("score_reasoning"),
            "reasoning_steps": output.get("reasoning_steps"),
            "insights": output.get("insights"),
            "recommended_action": output.get("recommended_action"),
        },
        "outreach": {
            "email_subject": output.get("email_subject"),
            "email_draft": output.get("email_draft"),
            "pitch_angle": output.get("pitch_angle"),
            "talking_points": output.get("talking_points"),
            "signal_used": output.get("signal_used"),
        },
    }
    return agent_outputs.get(agent, output)


async def save_pipeline_result(
    lead_id: str,
    result: dict[str, Any],
    session,
    commit: bool = True,
) -> EnrichmentResult:
    stmt = select(EnrichmentResult).where(EnrichmentResult.lead_id == lead_id)
    existing = await session.execute(stmt)
    enrichment = existing.scalar_one_or_none()

    if not enrichment:
        enrichment = EnrichmentResult(lead_id=lead_id)
        session.add(enrichment)

    enrichment.identity_data = result.get("identity_data")
    enrichment.company_data = result.get("company_data")
    enrichment.market_data = result.get("market_data")
    enrichment.property_data = result.get("property_data")
    enrichment.values_data = result.get("values_data")

    completed = result.get("completed_agents", [])
    enrichment.identity_complete = "identity" in completed
    enrichment.company_complete = "company" in completed
    enrichment.market_complete = "market" in completed
    enrichment.property_complete = "property" in completed
    enrichment.values_complete = "values" in completed
    enrichment.scoring_complete = "scoring" in completed
    enrichment.outreach_complete = "outreach" in completed

    enrichment.score = result.get("score")
    enrichment.score_breakdown = result.get("score_breakdown")
    enrichment.score_reasoning = result.get("score_reasoning")
    enrichment.reasoning_steps = result.get("reasoning_steps")
    enrichment.insights = result.get("insights")
    enrichment.recommended_action = result.get("recommended_action")
    enrichment.completed_agents = result.get("completed_agents")

    tier_str = result.get("tier")
    if tier_str:
        try:
            enrichment.tier = LeadTier(tier_str)
        except ValueError:
            enrichment.tier = None

    enrichment.email_draft = result.get("email_draft")
    enrichment.email_subject = result.get("email_subject")
    enrichment.pitch_angle = result.get("pitch_angle")
    enrichment.talking_points = result.get("talking_points")
    enrichment.signal_used = result.get("signal_used")
    enrichment.errors = result.get("errors", {})

    if commit:
        await session.commit()

    return enrichment
