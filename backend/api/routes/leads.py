from typing import Any

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from agents.outreach_agent import outreach_agent
from db.database import get_db
from db.models import EnrichmentResult, Lead, LeadStatus
from services.pipeline_queue import (
    enqueue_lead,
    save_pipeline_result,
    stream_lead_events,
)

router = APIRouter(prefix="/api/leads", tags=["leads"])

class LeadCreate(BaseModel):
    name: str
    email: str
    company: str
    property_address: str
    city: str
    state: str
    country: str = "US"


class EmailRegenerateRequest(BaseModel):
    feedback: str = "Rewrite this email with a sharper, more concise SDR tone while preserving the strongest lead signal."


def serialize_enrichment(enrichment: EnrichmentResult | None) -> dict[str, Any] | None:
    if not enrichment:
        return None

    return {
        "id": enrichment.id,
        "lead_id": enrichment.lead_id,
        "identity_data": enrichment.identity_data,
        "company_data": enrichment.company_data,
        "market_data": enrichment.market_data,
        "property_data": enrichment.property_data,
        "values_data": enrichment.values_data,
        "identity_complete": enrichment.identity_complete,
        "company_complete": enrichment.company_complete,
        "market_complete": enrichment.market_complete,
        "property_complete": enrichment.property_complete,
        "values_complete": enrichment.values_complete,
        "scoring_complete": enrichment.scoring_complete,
        "outreach_complete": enrichment.outreach_complete,
        "score": enrichment.score,
        "tier": enrichment.tier.value if enrichment.tier else None,
        "score_reasoning": enrichment.score_reasoning,
        "score_breakdown": enrichment.score_breakdown,
        "insights": enrichment.insights,
        "recommended_action": enrichment.recommended_action,
        "email_subject": enrichment.email_subject,
        "email_draft": enrichment.email_draft,
        "pitch_angle": enrichment.pitch_angle,
        "talking_points": enrichment.talking_points,
        "reasoning_steps": enrichment.reasoning_steps,
        "signal_used": enrichment.signal_used,
        "completed_agents": enrichment.completed_agents,
        "errors": enrichment.errors,
        "created_at": enrichment.created_at.isoformat() if enrichment.created_at else None,
        "updated_at": enrichment.updated_at.isoformat() if enrichment.updated_at else None,
    }


def serialize_lead(lead: Lead, include_enrichment: bool = True) -> dict[str, Any]:
    status = lead.status.value if lead.status else None
    if (
        lead.enrichment
        and lead.status in {LeadStatus.queued, LeadStatus.pending, LeadStatus.processing}
        and lead.enrichment.outreach_complete
    ):
        status = (
            LeadStatus.disqualified.value
            if lead.enrichment.tier and lead.enrichment.tier.value == "disqualified"
            else LeadStatus.complete.value
        )

    data = {
        "id": lead.id,
        "name": lead.name,
        "email": lead.email,
        "company": lead.company,
        "property_address": lead.property_address,
        "city": lead.city,
        "state": lead.state,
        "country": lead.country,
        "status": status,
        "batch_id": lead.batch_id,
        "created_at": lead.created_at.isoformat() if lead.created_at else None,
        "updated_at": lead.updated_at.isoformat() if lead.updated_at else None,
        "completed_at": lead.completed_at.isoformat() if lead.completed_at else None,
    }

    if include_enrichment:
        data["enrichment"] = serialize_enrichment(lead.enrichment)
    elif lead.enrichment:
        data["score"] = lead.enrichment.score
        data["tier"] = lead.enrichment.tier.value if lead.enrichment.tier else None

    return data


@router.post("")
async def create_lead(payload: LeadCreate, db: AsyncSession = Depends(get_db)):
    lead = Lead(
        name=payload.name,
        email=payload.email,
        company=payload.company,
        property_address=payload.property_address,
        city=payload.city,
        state=payload.state,
        country=payload.country,
        status=LeadStatus.queued,
    )
    db.add(lead)
    await db.commit()
    await db.refresh(lead)

    await enqueue_lead(lead)

    return {
        "lead_id": lead.id,
        "id": lead.id,
        "status": lead.status.value,
        "company": lead.company,
        "name": lead.name,
        "city": lead.city,
        "state": lead.state,
        "created_at": lead.created_at.isoformat() if lead.created_at else None,
    }

@router.get("")
async def list_leads(limit: int = 50, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Lead)
        .options(selectinload(Lead.enrichment))
        .order_by(Lead.created_at.desc())
        .limit(limit)
    )
    leads = result.scalars().all()
    return {"leads": [serialize_lead(lead, include_enrichment=True) for lead in leads]}


@router.get("/{lead_id}")
async def get_lead(lead_id: str, db: AsyncSession = Depends(get_db)):
    lead = (
        await db.execute(
            select(Lead)
            .options(selectinload(Lead.enrichment))
            .where(Lead.id == lead_id)
        )
    ).scalar_one_or_none()

    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    return serialize_lead(lead, include_enrichment=True)


@router.post("/{lead_id}/regenerate-email")
async def regenerate_email(
    lead_id: str,
    payload: EmailRegenerateRequest,
    db: AsyncSession = Depends(get_db),
):
    lead = (
        await db.execute(
            select(Lead)
            .options(selectinload(Lead.enrichment))
            .where(Lead.id == lead_id)
        )
    ).scalar_one_or_none()

    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    if not lead.enrichment or not lead.enrichment.email_draft:
        raise HTTPException(status_code=400, detail="No existing email draft to regenerate")

    enrichment = lead.enrichment
    state = {
        "lead_id": lead.id,
        "name": lead.name,
        "email": lead.email,
        "company": lead.company,
        "property_address": lead.property_address,
        "city": lead.city,
        "state": lead.state,
        "country": lead.country,
        "identity_data": enrichment.identity_data or {},
        "company_data": enrichment.company_data or {},
        "market_data": enrichment.market_data or {},
        "property_data": enrichment.property_data or {},
        "values_data": enrichment.values_data or {},
        "score": enrichment.score,
        "tier": enrichment.tier.value if enrichment.tier else None,
        "insights": enrichment.insights or {},
        "recommended_action": enrichment.recommended_action,
        "pitch_angle": enrichment.pitch_angle,
        "talking_points": enrichment.talking_points or [],
        "errors": enrichment.errors or {},
        "completed_agents": enrichment.completed_agents or [],
    }

    result = await outreach_agent.regenerate(
        state=state,
        previous_email=enrichment.email_draft,
        feedback=payload.feedback,
    )

    if result.get("error"):
        raise HTTPException(status_code=500, detail=result["error"])

    enrichment.email_draft = result.get("email_draft") or enrichment.email_draft
    enrichment.email_subject = result.get("email_subject") or enrichment.email_subject
    enrichment.signal_used = result.get("signal_used") or enrichment.signal_used
    enrichment.pitch_angle = result.get("pitch_angle") or enrichment.pitch_angle
    enrichment.talking_points = result.get("talking_points") or enrichment.talking_points
    enrichment.outreach_complete = True

    await db.commit()
    await db.refresh(lead)

    return serialize_lead(lead, include_enrichment=True)


@router.get("/{lead_id}/stream")
async def stream_lead(lead_id: str, db: AsyncSession = Depends(get_db)):
    lead = await db.get(Lead, lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    return StreamingResponse(
        stream_lead_events(lead_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/batch")
async def upload_batch(file: UploadFile = File(...), db: AsyncSession = Depends(get_db)):
    import csv
    import io
    import uuid

    content = (await file.read()).decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(content))
    batch_id = str(uuid.uuid4())
    created = []

    required = {"name", "email", "company", "property_address", "city", "state"}
    missing = required - set(reader.fieldnames or [])
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"CSV missing required columns: {', '.join(sorted(missing))}",
        )

    for row in reader:
        lead = Lead(
            name=row["name"],
            email=row["email"],
            company=row["company"],
            property_address=row["property_address"],
            city=row["city"],
            state=row["state"],
            country=row.get("country") or "US",
            status=LeadStatus.queued,
            batch_id=batch_id,
        )
        db.add(lead)
        created.append(lead)

    await db.commit()
    for lead in created:
        await db.refresh(lead)

    return {
        "accepted": True,
        "batch_id": batch_id,
        "count": len(created),
        "lead_ids": [lead.id for lead in created],
    }


__all__ = ["router", "save_pipeline_result"]
