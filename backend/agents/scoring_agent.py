# backend/agents/scoring_agent.py

import json
import logging
import anthropic
from agents.base_agent import BaseAgent, EnrichmentState
from config import get_settings

logger = logging.getLogger(__name__)


# ── Scoring System Prompt ────────────────────────────────────────

SCORING_SYSTEM_PROMPT = """You are an expert sales intelligence 
analyst for EliseAI — an AI leasing automation platform that 
serves residential property managers.

Your job: analyze enriched lead data and produce:
1. A lead score 0-100
2. A tier classification
3. Sales insights for the SDR

ELISEAI CONTEXT:
EliseAI automates leasing communication, maintenance requests,
and resident operations. Customers include Greystar, AvalonBay,
Equity Residential, and 500+ operators.

Products:
- Conventional: AI-guided tours, 24/7 leasing, renewal automation
- Affordable: Fair housing compliance, 51-language support
- Student: Surge leasing, renewal campaigns
- Single-family: Maintenance automation, resident communication

SCORING FORMULA:
You will receive pre-computed sub-scores. Use them as your
starting point but apply judgment for edge cases.

SCORE BREAKDOWN RULES — REQUIRED:
You MUST populate every field in score_breakdown.
Never return null for sub-scores — compute them explicitly.

pain_score (0-30):
  leasing_jobs >= 5:    +15 pts
  leasing_jobs >= 2:    +8 pts
  maintenance_jobs >= 5: +8 pts
  maintenance_jobs >= 2: +4 pts
  no PropTech detected:  +7 pts
  has PropTech no EliseAI: +3 pts
  news pain signals:    +5 pts

fit_score (0-25):
  units > 50000:        +10 pts
  units > 10000:        +7 pts
  units > 1000:         +4 pts
  is_public=True:       +8 pts
  company enterprise:   +7 pts
  company large:        +4 pts
  eliseai_integrations: +7 pts
  proptech only:        +3 pts

timing_score (0-25):
  is_adopting_new_software: +12 pts
  has_recent_8k:            +8 pts
  is_expanding:             +7 pts
  funding_signals:          +5 pts
  total_jobs > 20:          +5 pts
  total_jobs > 10:          +3 pts

market_score (0-10):
  leasing_intensity=high:     +5 pts
  leasing_intensity=moderate: +3 pts
  market_health >= 75:        +3 pts
  market_health >= 50:        +2 pts
  population_trend=growing:   +2 pts
  population_trend=declining: -1 pt

contact_score (0-10):
  dm_probability >= 0.8: +5 pts
  dm_probability >= 0.5: +3 pts
  dm_probability < 0.5:  +1 pt
  seniority=c_suite:     +5 pts
  seniority=vp:          +4 pts
  seniority=director:    +3 pts
  seniority=manager:     +2 pts
  seniority=unknown:     +1 pt

Always populate pain_evidence, fit_evidence, timing_evidence,
market_evidence, contact_evidence with specific cited reasons.
Always populate confidence and confidence_notes.

Pain Score (0-30):      Do they NEED EliseAI right now?
Fit Score (0-25):       Are they the right type of company?
Timing Score (0-25):    Is NOW the right moment?
Market Score (0-10):    Does their city create urgency?
Contact Score (0-10):   Can we reach the right person?

TIER CLASSIFICATION:
80-100: hot      → Contact within 24 hours
60-79:  warm     → Contact within 72 hours
40-59:  nurture  → Add to nurture sequence
20-39:  low      → Monitor only
0-19:   pass     → Do not contact

CRITICAL RULES:
1. If is_residential=False → score=0, tier=disqualified
2. If company_size=small AND units<500 → cap score at 60
3. If contact score=0 AND no linkedin → note in action
4. Always cite specific data points in reasoning
5. Never make up data not provided

RETURN ONLY VALID JSON — no markdown, no explanation:
{
  "score": 0-100,
  "tier": "hot/warm/nurture/low/pass/disqualified",
  "recommended_action": "specific next step for SDR",
  "score_breakdown": {
    "pain_score": 0-30,
    "fit_score": 0-25,
    "timing_score": 0-25,
    "market_score": 0-10,
    "contact_score": 0-10,
    "pain_evidence": ["evidence1", "evidence2"],
    "fit_evidence": ["evidence1", "evidence2"],
    "timing_evidence": ["evidence1", "evidence2"],
    "market_evidence": ["evidence1", "evidence2"],
    "contact_evidence": ["evidence1", "evidence2"]
  },
  "insights": {
    "company_snapshot": ["3 most important facts"],
    "pain_points": ["what hurts them NOW"],
    "timing_signals": ["why contact NOW"],
    "pitch_angle": "what to lead with in outreach",
    "integration_hook": "EliseAI + their existing tools",
    "objection_prep": [
      {"objection": "...", "response": "..."},
      {"objection": "...", "response": "..."}
    ],
    "market_context": "one sentence on their city market"
  },
  "confidence": "high/medium/low",
  "confidence_notes": "what data was missing or uncertain"
}


CRITICAL: You MUST return the COMPLETE JSON structure.
The score_breakdown field is REQUIRED with all sub-scores.
Do not simplify or omit any fields.
Return null for fields you cannot determine — never omit them.
"""




class ScoringAgent(BaseAgent):
    """
    Scores enriched leads using:
    1. Deterministic formula (pain/fit/timing/market/contact)
    2. One LLM call for insights generation

    Inputs:  identity_data, company_data, market_data
    Outputs: score, tier, insights, recommended_action
    """

    agent_name = "scoring"

    def __init__(self):
        get_settings.cache_clear()
        s = get_settings()
        self.client = anthropic.AsyncAnthropic(
            api_key=s.anthropic_api_key
        )

    async def run(
        self,
        state: EnrichmentState,
        emitter=None,
    ) -> dict:
        try:
            def emit(msg, detail=None, icon="🔍"):
                if emitter:
                    emitter.emit(msg, detail, icon)
                logger.info(f"{msg} {detail or ''}")

            company_data  = state.get("company_data", {}) or {}
            market_data   = state.get("market_data", {}) or {}
            identity_data = state.get("identity_data", {}) or {}

            company = company_data.get("company_name", "")
            emit(f"Scoring lead", company, "🎯")

            # Gate check. Only hard-disqualify when the company agent explicitly
            # says to disqualify; false/unknown residential flags can be noisy.
            if company_data.get("disqualify", False):
                emit("Disqualified — not residential", None, "❌")
                return self._mark_complete(state, {
                    "score":              0,
                    "tier":               "disqualified",
                    "recommended_action": company_data.get("disqualify_reason") or "Do not contact — not residential real estate",
                    "score_breakdown":    {},
                    "insights":           {},
                    "confidence":         "high",
                    "confidence_notes":   "Disqualified by explicit company gate",
                })

            # Step 1: Compute sub-scores deterministically
            emit("Computing sub-scores", None, "📊")

            pain_score,    pain_evidence,    pain_missing    = \
                self._compute_pain_score(company_data)
            fit_score,     fit_evidence                      = \
                self._compute_fit_score(company_data)
            timing_score,  timing_evidence,  timing_conf     = \
                self._compute_timing_score(company_data)
            market_score,  market_evidence                   = \
                self._compute_market_score(market_data)
            contact_score, contact_evidence, contact_conf    = \
                self._compute_contact_score(identity_data)

            total_score = min(
                pain_score + fit_score + timing_score +
                market_score + contact_score,
                100
            )

            emit(
                f"Sub-scores computed: {total_score}/100",
                f"pain={pain_score} fit={fit_score} "
                f"timing={timing_score} market={market_score} "
                f"contact={contact_score}",
                "📊"
            )

            # Step 2: LLM generates insights
            emit("Generating sales insights", "Claude Sonnet", "🧠")

            prompt = self._build_prompt(
                company_data, market_data, identity_data,
                pain_score,    pain_evidence,    pain_missing,
                fit_score,     fit_evidence,
                timing_score,  timing_evidence,
                market_score,  market_evidence,
                contact_score, contact_evidence,
                total_score,
            )

            response = await self.client.messages.create(
                model="claude-sonnet-4-5",
                max_tokens=4096,
                system=[
                    {
                        "type":          "text",
                        "text":          SCORING_SYSTEM_PROMPT,
                        "cache_control": {"type": "ephemeral"}
                    }
                ],
                messages=[{"role": "user", "content": prompt}],
            )

            raw = response.content[0].text.strip()

            # Strip markdown if present
            if "```json" in raw:
                raw = raw.split("```json")[1].split("```")[0].strip()
            elif "```" in raw:
                raw = raw.split("```")[1].split("```")[0].strip()

            result = json.loads(raw)

            emit(
                f"Score: {result['score']}/100 — {result['tier'].upper()}",
                result.get("recommended_action", ""),
                "🔴" if result["tier"] == "hot"
                else "🟡" if result["tier"] == "warm"
                else "🟢"
            )

            return self._mark_complete(state, result)

        except Exception as e:
            logger.error(f"ScoringAgent failed: {e}")
            return self._mark_error(state, e)

    # ── Sub-Score Computations ───────────────────────────────────

    def _compute_pain_score(
        self,
        company_data: dict,
    ) -> tuple[int, list, list]:

        score    = 0
        evidence = []
        missing  = []

        # Leasing understaffing
        leasing_jobs = company_data.get("leasing_jobs", 0)
        total_jobs   = company_data.get("total_jobs", 0)

        if total_jobs == 0:
            missing.append(
                "Job postings unavailable — "
                "Adzuna may not cover this company"
            )
        elif leasing_jobs >= 5:
            score += 15
            evidence.append(
                f"{leasing_jobs} leasing roles open — "
                f"critically understaffed"
            )
        elif leasing_jobs >= 2:
            score += 8
            evidence.append(
                f"{leasing_jobs} leasing roles — understaffed"
            )

        # Maintenance burden
        maintenance_jobs = company_data.get("maintenance_jobs", 0)
        if maintenance_jobs >= 5:
            score += 8
            evidence.append(
                f"{maintenance_jobs} maintenance roles — "
                f"automation opportunity"
            )
        elif maintenance_jobs >= 2:
            score += 4
            evidence.append(
                f"{maintenance_jobs} maintenance roles"
            )

        # Tech gap
        has_proptech = bool(
            company_data.get("proptech_detected", [])
        )
        has_eliseai = bool(
            company_data.get("eliseai_integrations", [])
        )

        if not has_proptech:
            if total_jobs > 0:
                score += 7
                evidence.append(
                    "No PropTech detected — "
                    "likely manual leasing operations"
                )
            else:
                missing.append("Tech stack unverified")
        elif not has_eliseai:
            score += 3
            evidence.append(
                "Has PropTech but no EliseAI — "
                "automation gap exists"
            )

        return min(score, 30), evidence, missing

    def _compute_fit_score(
        self,
        company_data: dict,
    ) -> tuple[int, list]:

        score    = 0
        evidence = []

        # Portfolio size
        units          = company_data.get("units_managed") or 0
        is_residential = company_data.get("is_residential", False)
        is_public      = company_data.get("is_public", False)

        if units > 50000:
            score += 10
            evidence.append(
                f"{units:,.0f} units — enterprise portfolio"
            )
        elif units > 10000:
            score += 7
            evidence.append(
                f"{units:,.0f} units — large portfolio"
            )
        elif units > 1000:
            score += 4
            evidence.append(
                f"{units:,.0f} units — medium portfolio"
            )
        elif units > 0:
            score += 1
            evidence.append(
                f"{units:,.0f} units — small portfolio"
            )
        else:
            if is_residential and is_public:
                score += 1
                evidence.append(
                    "Units unknown — public residential REIT"
                )
            elif is_residential:
                score += 2
                evidence.append(
                    "Units unknown but confirmed residential — "
                    "benefit of doubt"
                )

        # Company type
        company_size = company_data.get("company_size", "unknown")

        if is_public:
            ticker = company_data.get("ticker", "")
            score += 8
            evidence.append(
                f"Public company {ticker} — "
                f"enterprise budget cycle"
            )
        elif company_size == "enterprise":
            score += 7
            evidence.append("Enterprise private operator")
        elif company_size == "large":
            score += 4
            evidence.append("Large private operator")
        elif company_size == "medium":
            score += 2
            evidence.append("Medium private operator")
        else:
            score += 1

        # EliseAI integration match
        eliseai = company_data.get("eliseai_integrations", [])
        proptech = company_data.get("proptech_detected", [])

        if eliseai:
            score += 7
            evidence.append(
                f"Uses {eliseai} — "
                f"EliseAI integrates natively — easy implementation"
            )
        elif proptech:
            score += 3
            evidence.append(
                f"Uses {proptech} — PropTech mindset confirmed"
            )

        return min(score, 25), evidence

    def _compute_timing_score(
        self,
        company_data: dict,
    ) -> tuple[int, list, str]:

        score      = 0
        evidence   = []
        confidence = "high"

        # Systems adoption roles
        if company_data.get("is_adopting_new_software"):
            score += 12
            evidence.append(
                "Hiring systems implementation roles — "
                "actively buying software NOW"
            )

        # SEC 8-K material events (public only)
        if company_data.get("has_recent_material_event"):
            count = company_data.get("recent_8k_count", 0)
            score += 8
            evidence.append(
                f"{count} SEC 8-K filings — "
                f"material events occurring"
            )

        # Expansion signals (news + Exa)
        if company_data.get("is_expanding"):
            score += 7
            evidence.append("Active expansion detected")
            confidence = "medium"

        # Funding signals
        if company_data.get("funding_signals"):
            score += 5
            evidence.append(
                "Recent funding — budget available"
            )
            confidence = "medium"

        # High local hiring volume
        total_jobs = company_data.get("total_jobs", 0)
        if total_jobs > 20:
            score += 5
            evidence.append(
                f"Hiring {total_jobs} roles locally — "
                f"growth mode"
            )
        elif total_jobs > 10:
            score += 3
            evidence.append(
                f"Hiring {total_jobs} roles locally"
            )

        return min(score, 25), evidence, confidence

    def _compute_market_score(
        self,
        market_data: dict,
    ) -> tuple[int, list]:

        score    = 0
        evidence = []

        # Leasing intensity
        leasing_intensity = market_data.get(
            "leasing_intensity", "unknown"
        )
        leasing_score = market_data.get(
            "leasing_intensity_score", 0
        )

        if leasing_intensity == "high":
            score += 5
            evidence.append(
                f"High leasing intensity ({leasing_score}/100)"
            )
        elif leasing_intensity == "moderate":
            score += 3
            evidence.append(
                f"Moderate leasing intensity ({leasing_score}/100)"
            )

        # Market health
        market_health_score = market_data.get(
            "market_health_score", 0
        )
        if market_health_score >= 75:
            score += 3
            evidence.append(
                f"Strong market health ({market_health_score}/100)"
            )
        elif market_health_score >= 50:
            score += 2
            evidence.append(
                f"Moderate market ({market_health_score}/100)"
            )

        # Population growth
        pop_trend = market_data.get("population_trend", "unknown")
        if pop_trend == "growing":
            pop_change = market_data.get(
                "population_change_pct", 0
            )
            score += 2
            evidence.append(
                f"Growing population +{pop_change}% — "
                f"expanding renter pool"
            )
        elif pop_trend == "declining":
            score -= 1
            evidence.append("Declining population")

        return max(0, min(score, 10)), evidence

    def _compute_contact_score(
        self,
        identity_data: dict,
    ) -> tuple[int, list, str]:

        score      = 0
        evidence   = []
        confidence = "high"

        # DM probability
        dm_prob = identity_data.get("dm_probability", None)

        if dm_prob is None:
            score += 1
            confidence = "low"
            evidence.append(
                "Contact info unavailable — "
                "manual research needed"
            )
        elif dm_prob >= 0.8:
            score += 5
            evidence.append(
                f"High DM probability ({dm_prob:.0%})"
            )
        elif dm_prob >= 0.5:
            score += 3
            evidence.append(
                f"Moderate DM probability ({dm_prob:.0%})"
            )
        else:
            score += 1
            evidence.append(
                f"Low DM probability ({dm_prob:.0%}) — "
                f"find right contact"
            )

        # Seniority
        seniority = identity_data.get("seniority", "unknown")
        title     = identity_data.get(
            "verified_title", "unknown"
        )

        if seniority == "c_suite":
            score += 5
            evidence.append(f"C-suite: {title}")
        elif seniority == "vp":
            score += 4
            evidence.append(f"VP-level: {title}")
        elif seniority == "director":
            score += 3
            evidence.append(f"Director-level: {title}")
        elif seniority == "manager":
            score += 2
            evidence.append(f"Manager-level: {title}")
        elif seniority == "unknown":
            score += 1
            confidence = "medium"
            evidence.append("Seniority unknown")
        else:
            evidence.append(
                f"Individual contributor: {title} — "
                f"find decision maker"
            )

        return min(score, 10), evidence, confidence

    # ── Prompt Builder ───────────────────────────────────────────

    def _build_prompt(
        self,
        company_data:    dict,
        market_data:     dict,
        identity_data:   dict,
        pain_score:      int,
        pain_evidence:   list,
        pain_missing:    list,
        fit_score:       int,
        fit_evidence:    list,
        timing_score:    int,
        timing_evidence: list,
        market_score:    int,
        market_evidence: list,
        contact_score:   int,
        contact_evidence: list,
        total_score:     int,
    ) -> str:

        # Key facts from company research
        key_facts = company_data.get("key_facts", [])
        key_facts_str = "\n".join(
            f"- {f}" for f in key_facts
        ) if key_facts else "None found"

        return f"""
Score this lead for EliseAI sales qualification.

═══════════════════════════════════════
LEAD IDENTITY
═══════════════════════════════════════
Name:            {identity_data.get('name', 'unknown')}
Email:           {identity_data.get('email', 'unknown')}
Verified title:  {identity_data.get('verified_title', 'unknown')}
Seniority:       {identity_data.get('seniority', 'unknown')}
DM probability:  {identity_data.get('dm_probability', 'unknown')}
LinkedIn:        {identity_data.get('linkedin_url', 'not found')}

═══════════════════════════════════════
COMPANY DATA
═══════════════════════════════════════
Company:         {company_data.get('company_name')}
Is public:       {company_data.get('is_public')}
Is residential:  {company_data.get('is_residential')}
Company size:    {company_data.get('company_size')}
Ticker:          {company_data.get('ticker')}
Units managed:   {company_data.get('units_managed')}
Annual revenue:  {company_data.get('annual_revenue')}
AUM:             {company_data.get('aum')}

Tech maturity:   Level {company_data.get('tech_maturity_level')} — {company_data.get('tech_maturity_label')}
EliseAI integrations: {company_data.get('eliseai_integrations')}
PropTech detected:    {company_data.get('proptech_detected')}

Leasing jobs:    {company_data.get('leasing_jobs')}
Maintenance jobs:{company_data.get('maintenance_jobs')}
Total jobs:      {company_data.get('total_jobs')}
Automation urgency: {company_data.get('automation_urgency')}
Pain points:     {company_data.get('pain_points')}

Is expanding:    {company_data.get('is_expanding')}
Funding signals: {company_data.get('funding_signals')}
Growth signals:  {company_data.get('growth_signals')}
SEC 8-K count:   {company_data.get('recent_8k_count')}

KEY FACTS FROM RESEARCH:
{key_facts_str}

EXTRACTION NOTES:
{company_data.get('extraction_notes', 'none')}

═══════════════════════════════════════
MARKET DATA
═══════════════════════════════════════
City:                {market_data.get('city')}
State:               {market_data.get('state')}
Renter population:   {market_data.get('renter_population')}
Leasing intensity:   {market_data.get('leasing_intensity')} ({market_data.get('leasing_intensity_score')}/100)
Market health:       {market_data.get('market_health')} ({market_data.get('market_health_score')}/100)
Population trend:    {market_data.get('population_trend')} ({market_data.get('population_change_pct')}%)
EliseAI product line: {market_data.get('eliseai_product_line')}
Pitch focus:         {market_data.get('eliseai_pitch_focus')}

═══════════════════════════════════════
PRE-COMPUTED SUB-SCORES
═══════════════════════════════════════
Pain score:    {pain_score}/30   → {pain_evidence}
               Missing data: {pain_missing}

Fit score:     {fit_score}/25    → {fit_evidence}

Timing score:  {timing_score}/25 → {timing_evidence}

Market score:  {market_score}/10 → {market_evidence}

Contact score: {contact_score}/10 → {contact_evidence}

TOTAL:         {total_score}/100

═══════════════════════════════════════
YOUR TASK
═══════════════════════════════════════
1. Review sub-scores — adjust if you see edge cases
   the formula missed
2. Classify tier based on final score
3. Generate sales insights for the SDR
4. Return valid JSON matching the specified format

Focus insights on SPECIFIC data points — not generic advice.
Reference actual numbers, company names, tool names.
"""

    def _empty_response(self) -> dict:
        return {
            "score":              0,
            "tier":               "pass",
            "recommended_action": "Insufficient data",
            "score_breakdown":    {},
            "insights":           {},
            "confidence":         "low",
            "confidence_notes":   "Agent failed",
        }


# ─── Singleton ──────────────────────────────────────────────────
scoring_agent = ScoringAgent()
