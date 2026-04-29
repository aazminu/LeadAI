# backend/agents/property_agent.py

import logging
from agents.base_agent import BaseAgent, EnrichmentState

logger = logging.getLogger(__name__)


class PropertyAgent(BaseAgent):
    """
    Property-level enrichment using WalkScore API.
    Geocodes address via OpenStreetMap Nominatim (free).
    Then fetches Walk, Transit, Bike scores.
    """

    agent_name = "property"

    async def run(
        self,
        state: EnrichmentState,
        emitter=None,
    ) -> dict:
        try:
            from services.walkscore_service import walkscore_service

            address = state.get("property_address", "")
            city    = state.get("city", "")
            state_  = state.get("state", "")

            def emit(msg, detail=None, icon="🔍"):
                if emitter:
                    emitter.emit(msg, detail, icon)
                logger.info(f"{msg} {detail or ''}")

            emit(
                "Starting property enrichment",
                f"{address}, {city} {state_}",
                "🏠"
            )

            emit(
                "Geocoding address",
                "OpenStreetMap Nominatim → lat/lon",
                "📍"
            )

            scores = await walkscore_service.get_property_scores(
                address=address,
                city=city,
                state=state_,
            )

            walk    = scores.get("walk_score", 0)
            transit = scores.get("transit_score", 0)
            bike    = scores.get("bike_score", 0)
            urban   = scores.get("urban_classification", "unknown")

            if walk > 0:
                emit(
                    f"WalkScore: {walk}/100",
                    f"{scores.get('walk_description', '')} — {urban}",
                    "🚶"
                )
                emit(
                    f"TransitScore: {transit}/100",
                    scores.get("transit_description", ""),
                    "🚌"
                )
                emit(
                    f"BikeScore: {bike}/100",
                    scores.get("bike_description", ""),
                    "🚲"
                )
                emit(
                    f"Leasing velocity: {scores.get('leasing_velocity')}",
                    scores.get("automation_case", ""),
                    "✅"
                )
            else:
                emit(
                    "WalkScore unavailable",
                    "address not found or API limit reached",
                    "⚠️"
                )

            return self._mark_complete(state, {
                "property_data": scores
            })

        except Exception as e:
            logger.error(f"PropertyAgent failed: {e}")
            return self._mark_error(state, e)

    def _empty_response(self) -> dict:
        return {
            "property_data": {
                "status": "failed",
            }
        }


# ─── Singleton ──────────────────────────────────────────────────
property_agent = PropertyAgent()