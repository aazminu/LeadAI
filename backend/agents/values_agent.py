# backend/agents/values_agent.py

import logging
from agents.base_agent import BaseAgent, EnrichmentState

logger = logging.getLogger(__name__)


class ValuesAgent(BaseAgent):
    """
    Company values enrichment using Exa AI.
    Searches for ESG, DEI, sustainability, 
    tech adoption signals from company website.
    """

    agent_name = "values"

    async def run(
        self,
        state: EnrichmentState,
        emitter=None,
    ) -> dict:
        try:
            from exa_py import Exa
            from config import get_settings
            get_settings.cache_clear()
            settings = get_settings()

            company = state.get("company", "")

            def emit(msg, detail=None, icon="🔍"):
                if emitter:
                    emitter.emit(msg, detail, icon)
                logger.info(f"{msg} {detail or ''}")

            emit(
                "Starting values enrichment",
                company,
                "⭐"
            )

            if not settings.exa_api_key:
                emit("Exa API key missing", None, "⚠️")
                return self._mark_complete(state, {
                    "values_data": self._empty_values(company)
                })

            exa = Exa(api_key=settings.exa_api_key)

            # Search 1: ESG + sustainability
            emit(
                "Searching ESG signals",
                f"{company} sustainability diversity",
                "🌱"
            )

            esg_results = exa.search_and_contents(
                f"{company} ESG sustainability diversity inclusion",
                num_results=3,
                text=True,
            )

            # Search 2: Company culture + values page
            emit(
                "Searching company values",
                f"{company} mission culture who we are",
                "💡"
            )

            values_results = exa.search_and_contents(
                f"{company} company values mission culture who we are",
                num_results=3,
                text=True,
            )

            # Search 3: Tech adoption signals
            emit(
                "Searching tech adoption signals",
                f"{company} technology innovation AI proptech",
                "🤖"
            )

            tech_results = exa.search_and_contents(
                f"{company} technology innovation AI proptech automation",
                num_results=2,
                text=True,
            )

            # Synthesize
            result = self._synthesize(
                company,
                esg_results,
                values_results,
                tech_results,
                emit,
            )

            return self._mark_complete(state, {
                "values_data": result
            })

        except Exception as e:
            logger.error(f"ValuesAgent failed: {e}")
            return self._mark_error(state, e)

    def _synthesize(
        self,
        company: str,
        esg_results,
        values_results,
        tech_results,
        emit,
    ) -> dict:

        # ESG signals
        has_esg_page    = False
        has_dei_page    = False
        sustainability  = None
        esg_signals     = []

        esg_keywords = [
            "sustainability", "esg", "environmental",
            "carbon", "net zero", "green"
        ]
        dei_keywords = [
            "diversity", "inclusion", "equity",
            "dei", "belonging", "eeo"
        ]

        for result in (esg_results.results or []):
            text = (result.text or "").lower()
            if any(k in text for k in esg_keywords):
                has_esg_page = True
                esg_signals.append("Sustainability/ESG content detected")
            if any(k in text for k in dei_keywords):
                has_dei_page = True
                esg_signals.append("DEI content detected")

        # Values signals
        mission_statement = None
        values_keywords   = []

        for result in (values_results.results or []):
            text  = (result.text or "").lower()
            title = (result.title or "")
            if any(k in text for k in ["mission", "vision", "values", "who we are"]):
                mission_statement = title
                values_keywords.append("Mission/values page found")

        # Tech signals
        tech_signals    = []
        ai_interest     = False
        innovation_flag = False

        ai_keywords = [
            "artificial intelligence", "machine learning",
            "ai", "automation", "proptech", "innovation"
        ]

        for result in (tech_results.results or []):
            text = (result.text or "").lower()
            if any(k in text for k in ai_keywords):
                ai_interest = True
                tech_signals.append("AI/automation interest detected")
            if "innovation" in text:
                innovation_flag = True
                tech_signals.append("Innovation culture signal")

        # Emit findings
        if has_esg_page:
            emit("ESG page detected", "sustainability content found", "🌱")
        if has_dei_page:
            emit("DEI signals found", "diversity + inclusion content", "🤝")
        if ai_interest:
            emit("AI interest detected", "tech-forward signals found", "🤖")
        if mission_statement:
            emit("Values page found", mission_statement, "💡")

        emit(
            "Values enrichment complete",
            f"ESG: {has_esg_page} | DEI: {has_dei_page} | AI: {ai_interest}",
            "✅"
        )

        return {
            "company":          company,
            "has_esg_page":     has_esg_page,
            "has_dei_page":     has_dei_page,
            "sustainability":   sustainability,
            "mission_statement": mission_statement,
            "esg_signals":      esg_signals,
            "values_keywords":  values_keywords,
            "tech_signals":     tech_signals,
            "ai_interest":      ai_interest,
            "innovation_flag":  innovation_flag,
            "data_source":      "Exa AI search",
        }

    def _empty_values(self, company: str) -> dict:
        return {
            "company":           company,
            "has_esg_page":      None,
            "has_dei_page":      None,
            "sustainability":    None,
            "mission_statement": None,
            "esg_signals":       [],
            "values_keywords":   [],
            "tech_signals":      [],
            "ai_interest":       None,
            "innovation_flag":   None,
            "data_source":       "unavailable",
        }

    def _empty_response(self) -> dict:
        return {
            "values_data": self._empty_values("")
        }


# ─── Singleton ──────────────────────────────────────────────────
values_agent = ValuesAgent()