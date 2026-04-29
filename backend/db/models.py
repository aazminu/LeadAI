# backend/db/models.py

from sqlalchemy import (
    Column, String, Integer, Float,
    Boolean, DateTime, Text, ForeignKey, Enum
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
import uuid

from db.database import Base

# ─── Enums ─────────────────────────────────────────────────────

class LeadStatus(str, enum.Enum):
    queued       = "queued"        # accepted, waiting for the single worker
    pending      = "pending"       # legacy alias for queued
    processing   = "processing"    # orchestrator is running
    complete     = "complete"      # all agents done, results ready
    failed       = "failed"        # something went wrong
    disqualified = "disqualified"  # invalid or not a fit


class LeadTier(str, enum.Enum):
    hot            = "hot"           # score 80-100
    warm           = "warm"          # score 50-79
    cold           = "cold"          # score 20-49
    disqualified   = "disqualified"  # score 0-19


# ─── Lead Table ────────────────────────────────────────────────

class Lead(Base):
    __tablename__ = "leads"

    # Identity
    id              = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name            = Column(String(255), nullable=False)
    email           = Column(String(255), nullable=False)
    company         = Column(String(255), nullable=False)

    # Property
    property_address = Column(String(500), nullable=False)
    city             = Column(String(255), nullable=False)
    state            = Column(String(100), nullable=False)
    country          = Column(String(100), default="US")

    # Pipeline status
    status          = Column(
                        Enum(LeadStatus),
                        default=LeadStatus.pending,
                        nullable=False
                      )

    # Timestamps
    created_at      = Column(DateTime(timezone=True), server_default=func.now())
    updated_at      = Column(DateTime(timezone=True), onupdate=func.now())
    completed_at    = Column(DateTime(timezone=True), nullable=True)
    attempt_count   = Column(Integer, default=0, nullable=False)
    last_error      = Column(Text, nullable=True)

    # Batch tracking (for CSV bulk uploads)
    batch_id        = Column(String, nullable=True)

    # Relationship to enrichment result
    enrichment      = relationship(
                        "EnrichmentResult",
                        back_populates="lead",
                        uselist=False,          # one-to-one
                        cascade="all, delete-orphan"
                      )

    def __repr__(self):
        return f"<Lead {self.name} @ {self.company} — {self.status}>"


# ─── Enrichment Result Table ───────────────────────────────────

class EnrichmentResult(Base):
    __tablename__ = "enrichment_results"

    id              = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    lead_id         = Column(String, ForeignKey("leads.id"), nullable=False, unique=True)

    # ── Per-agent outputs (JSONB = queryable JSON in PostgreSQL) ──
    identity_data   = Column(JSONB, nullable=True)   # Agent 1
    company_data    = Column(JSONB, nullable=True)   # Agent 2
    market_data     = Column(JSONB, nullable=True)   # Agent 3
    property_data   = Column(JSONB, nullable=True)   # Agent 4
    values_data     = Column(JSONB, nullable=True)   # Agent 5

    # ── Agent completion flags ─────────────────────────────────
    # Lets the frontend show which agents are done in real time
    identity_complete  = Column(Boolean, default=False)
    company_complete   = Column(Boolean, default=False)
    market_complete    = Column(Boolean, default=False)
    property_complete  = Column(Boolean, default=False)
    values_complete    = Column(Boolean, default=False)
    scoring_complete   = Column(Boolean, default=False)
    outreach_complete  = Column(Boolean, default=False)

    # ── Scoring Agent output ───────────────────────────────────
    score           = Column(Float, nullable=True)        # 0-100
    tier            = Column(Enum(LeadTier), nullable=True)
    score_reasoning = Column(JSONB, nullable=True)        # cited evidence
    insights        = Column(JSONB, nullable=True)        # 5 bullet points
    recommended_action = Column(Text, nullable=True)      # SDR next step

    # ── Outreach Agent output ──────────────────────────────────
    email_draft     = Column(Text, nullable=True)
    pitch_angle     = Column(String(255), nullable=True)  # e.g. "sustainability_and_tech"
    talking_points  = Column(JSONB, nullable=True)        # for the call

    # Add after existing outreach fields:
    score_breakdown    = Column(JSONB, nullable=True)
    email_subject      = Column(Text, nullable=True)
    reasoning_steps    = Column(JSONB, nullable=True)
    signal_used        = Column(String(100), nullable=True)
    completed_agents   = Column(JSONB, nullable=True)

    # ── Error tracking ─────────────────────────────────────────
    errors          = Column(JSONB, nullable=True)        # which agents failed + why

    # Timestamps
    created_at      = Column(DateTime(timezone=True), server_default=func.now())
    updated_at      = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationship back to lead
    lead            = relationship("Lead", back_populates="enrichment")

    def __repr__(self):
        return f"<EnrichmentResult lead={self.lead_id} score={self.score} tier={self.tier}>"


class PipelineEvent(Base):
    __tablename__ = "pipeline_events"

    id         = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    lead_id    = Column(String, ForeignKey("leads.id"), nullable=False, index=True)
    sequence   = Column(Integer, nullable=False)
    event_type = Column(String(50), nullable=False)
    agent      = Column(String(100), nullable=True)
    icon       = Column(String(20), nullable=True)
    message    = Column(Text, nullable=True)
    detail     = Column(Text, nullable=True)
    payload    = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<PipelineEvent lead={self.lead_id} seq={self.sequence} type={self.event_type}>"
