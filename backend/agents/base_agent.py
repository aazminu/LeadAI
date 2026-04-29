# backend/agents/base_agent.py

from typing import Annotated, TypedDict, Optional, Any
from operator import add
import logging

logger = logging.getLogger(__name__)


# ── Reducer functions ───────────────────────────────────────────

def merge_dicts(a: dict, b: dict) -> dict:
    """Safely merge two dicts — used for errors field."""
    return {**a, **b}


# ── Shared State ────────────────────────────────────────────────

class EnrichmentState(TypedDict, total=False):
    """
    Shared state for the entire lead enrichment pipeline.

    Annotated reducers handle parallel writes safely:
    - completed_agents: list that grows as agents finish
    - errors: dict that merges agent errors
    
    All other fields are written by exactly one agent
    so no reducer needed.
    """

    # ── Lead Input ──────────────────────────────────────
    lead_id:            str
    name:               str
    email:              str
    company:            str
    property_address:   str
    city:               str
    state:              str
    country:            str

    # ── Enrichment Agent Outputs ────────────────────────
    # Each written by exactly one agent — no reducer needed
    identity_data:      Optional[dict]
    company_data:       Optional[dict]
    market_data:        Optional[dict]
    property_data:      Optional[dict]
    values_data:        Optional[dict]

    # ── AI Agent Outputs ────────────────────────────────
    score:              Optional[float]
    tier:               Optional[str]
    score_reasoning:    Optional[dict]
    score_breakdown:    Optional[dict]
    insights:           Optional[dict]
    recommended_action: Optional[str]
    email_draft:        Optional[str]
    email_subject:      Optional[str]
    talking_points:     Optional[list]
    pitch_angle:        Optional[str]
    signal_used:        Optional[str]

    # ── Pipeline Tracking ───────────────────────────────
    # Reducers handle parallel writes from multiple agents
    completed_agents:   Annotated[list[str], add]
    errors:             Annotated[dict, merge_dicts]
    status:             str
    emitter_factory:    Optional[Any]
    completion_callback: Optional[Any]


# ── Base Agent ──────────────────────────────────────────────────

class BaseAgent:
    """
    Base class for all LeadOS enrichment agents.

    Every agent:
    1. Implements run() — receives state, returns partial update
    2. Implements _empty_response() — graceful degradation
    3. Never raises exceptions — always returns something
    4. Returns ONLY its own fields + completed_agents
    """

    agent_name: str = "base"

    async def run(self, state: EnrichmentState) -> dict:
        raise NotImplementedError(
            f"{self.__class__.__name__} must implement run()"
        )

    def _empty_response(self) -> dict:
        raise NotImplementedError(
            f"{self.__class__.__name__} must implement _empty_response()"
        )

    def _mark_complete(
        self,
        state: EnrichmentState,
        result: dict
    ) -> dict:
        """
        Returns partial update for LangGraph.
        completed_agents reducer appends automatically.
        """
        return {
            **result,
            "completed_agents": [self.agent_name],
        }

    def _mark_error(
        self,
        state: EnrichmentState,
        error: Exception
    ) -> dict:
        """
        Records error gracefully.
        Pipeline continues with other agents.
        """
        logger.error(f"{self.agent_name} agent failed: {error}")
        return {
            **self._empty_response(),
            "errors":           {self.agent_name: str(error)},
            "completed_agents": [self.agent_name],
        }
