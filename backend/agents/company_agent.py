# backend/agents/company_agent.py

import json
import logging
import asyncio
import anthropic
from typing import Optional
from agents.base_agent import BaseAgent, EnrichmentState
from tools import ALL_COMPANY_TOOLS, TOOL_EXECUTORS
from config import get_settings

logger = logging.getLogger(__name__)

# ── System Prompt ────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a company research agent for EliseAI — 
an AI leasing automation platform that serves residential 
property managers.

YOUR GOAL:
Research the given company and determine:
1. Is this company a residential real estate operator?
2. If yes — gather enrichment data for lead scoring

CRITICAL RULE — RESIDENTIAL GATE:
After calling sec_edgar (or private_research + extracting facts):
- If is_residential=False → STOP immediately
- Do NOT call any more tools
- Return your final JSON with disqualify=true

EliseAI ONLY serves:
✅ Multifamily apartment operators
✅ Student housing operators  
✅ Affordable housing operators
✅ Single-family rental operators

EliseAI does NOT serve:
❌ Restaurants (McDonald's, SIC 5812)
❌ Data center REITs (Equinix, SIC 6798 with no apartments)
❌ Office/retail/industrial REITs
❌ Healthcare facilities
❌ Any non-residential business

TOOL CALLING RULES:
1. ALWAYS call sec_edgar first
2. If is_public=False → call private_research
3. If is_residential=False → STOP, return disqualify=true
4. If is_residential=True → call news_search + job_postings + tech_stack in parallel
5. After all tools complete → return final JSON

PRIVATE COMPANY EXTRACTION RULES:
When you receive private_research results (combined_text),
you MUST extract structured facts from the raw text.
This is the most critical part of your job.

═══════════════════════════════════════════════════
RULE 1: units_managed — CURRENT UNITS ONLY
═══════════════════════════════════════════════════
You are looking for how many residential units
this company manages TODAY — not historically.

ACCEPT these patterns:
  "manages 1.1 million multifamily units"       → 1100000
  "over 700,000 apartment homes"                → 700000
  "100,000+ residences managed"                 → 100000
  "managing approximately 80,000 units"         → 80000
  "portfolio of 50,000 homes"                   → 50000
  "500 communities" (no unit count)             → null
    (communities ≠ units, don't estimate)

REJECT these patterns (historical milestones):
  "50,000 units under management (2002)"        → IGNORE
  "reached 100,000 units in 2013"               → IGNORE
  "started with 1,000 units"                    → IGNORE

REJECT these patterns (wrong metric):
  "serves 300,000 residents"                    → IGNORE
    (residents ≠ units they manage)
  "200 million sq ft managed"                   → IGNORE
    (square feet, not residential units)
  "$320 billion of real estate"                 → IGNORE
    (dollar value, not units)

If multiple numbers found, prefer the LARGEST
recent number — companies grow over time.

If genuinely uncertain → return null.
Never guess or estimate.

═══════════════════════════════════════════════════
RULE 2: annual_revenue — REVENUE ONLY, NOT AUM
═══════════════════════════════════════════════════
AUM (Assets Under Management) is the total value
of real estate they manage for investors.
Revenue is what the company actually earns.
AUM is always 10-100x larger than revenue.
DO NOT confuse them.

ACCEPT — these are revenue:
  "$2.1 billion in revenue"                     → 2100000000
  "$500 million annual revenue"                 → 500000000
  "$1.5B total revenue"                         → 1500000000
  "$300 million construction annual revenue"    → 300000000

REJECT — these are AUM, not revenue:
  "$320 billion of real estate"                 → NOT revenue
  "$79 billion assets under management"         → NOT revenue
  "$50 billion investment portfolio"            → NOT revenue
  "$35 billion in development assets"           → NOT revenue
  "manages $10 billion in property"             → NOT revenue

If only AUM found and no revenue → return null for revenue,
populate aum field instead.

═══════════════════════════════════════════════════
RULE 3: aum — ASSETS UNDER MANAGEMENT
═══════════════════════════════════════════════════
ACCEPT these patterns:
  "$79 billion assets under management"         → 79000000000
  "$320 billion of real estate"                 → 320000000000
  "$50B AUM"                                    → 50000000000
  "manages $10 billion in property"             → 10000000000

═══════════════════════════════════════════════════
RULE 4: valuation — COMPANY VALUATION
═══════════════════════════════════════════════════
ACCEPT these patterns:
  "raised $1B at $5B valuation"                 → 5000000000
  "valued at $3 billion"                        → 3000000000
  "Series C at $2B valuation"                   → 2000000000
  "$500M funding round" (no valuation stated)   → null
    (funding amount ≠ valuation)

═══════════════════════════════════════════════════
RULE 5: employee_count — CURRENT HEADCOUNT
═══════════════════════════════════════════════════
ACCEPT:
  "12,000+ team members"                        → 12000
  "over 20,000 employees"                       → 20000
  "3,000+ associates"                           → 3000
  "team of 500 professionals"                   → 500

REJECT:
  "hiring 50 leasing agents"                    → NOT headcount
  "500 job openings"                            → NOT headcount

═══════════════════════════════════════════════════
RULE 6: is_residential — RESIDENTIAL GATE
═══════════════════════════════════════════════════
This is the MOST IMPORTANT field.
EliseAI ONLY serves residential property managers.

Return TRUE for:
  "apartment communities"
  "multifamily housing"
  "residential properties"
  "student housing"
  "affordable housing"
  "single-family rentals"
  "BTR (build-to-rent)"
  "rental housing"

Return FALSE for:
  "office buildings"
  "retail centers / shopping malls"
  "industrial / warehouse"
  "data centers"
  "self-storage facilities"
  "hotel / hospitality"
  "senior care facilities"
  "restaurants / food service"

MIXED PORTFOLIO:
  "manages office AND residential" → TRUE
    (they have residential — EliseAI can serve that segment)
  "primarily office with some residential" → TRUE

═══════════════════════════════════════════════════
RULE 7: company_size — FROM UNITS MANAGED
═══════════════════════════════════════════════════
enterprise: units_managed > 50,000
large:      units_managed 10,000 - 50,000
medium:     units_managed 1,000 - 10,000
small:      units_managed < 1,000
unknown:    no units data available

If no units data, infer from other signals:
  "one of the largest" / "global" / "nationwide" → large/enterprise
  "regional operator" / "mid-size"               → medium
  No signals at all                              → unknown

═══════════════════════════════════════════════════
RULE 8: extraction_confidence
═══════════════════════════════════════════════════
high:   found explicit numbers with clear context
medium: found numbers but context slightly ambiguous
low:    inferred from vague signals or found nothing

Always include extraction_notes explaining:
  - What you found and where
  - What was ambiguous
  - Why you returned null for missing fields


FINAL OUTPUT FORMAT:
Return ONLY valid JSON matching this exact structure:
{
  "disqualify": false,
  "disqualify_reason": null,
  "is_public": true/false,
  "is_real_estate": true/false,
  "is_residential": true/false,
  "company_size": "enterprise/large/medium/small/unknown",
  "ticker": "AVB" or null,
  "exchange": "NYSE" or null,
  "sic_code": "6512" or null,
  "sic_description": "..." or null,
  "units_managed": 98694 or null,
  "annual_revenue": 3040725000 or null,
  "aum": null,
  "valuation": null,
  "net_income": null,
  "total_assets": null,
  "employee_count": null,
  "eliseai_integrations": ["yardi", "entrata"],
  "proptech_detected": ["yardi", "mri"],
  "crm_tools": ["salesforce"],
  "tech_maturity_level": 4,
  "tech_maturity_label": "Advanced",
  "tech_maturity": {},
  "talking_points": [],
  "leasing_jobs": 5,
  "maintenance_jobs": 6,
  "tech_jobs": 2,
  "leadership_jobs": 1,
  "total_jobs": 20,
  "automation_urgency": "high",
  "pain_points": [],
  "is_expanding": false,
  "funding_signals": [],
  "leadership_signals": [],
  "growth_signals": [],
  "top_headlines": [],
  "buying_signal_score": 40,
  "has_recent_material_event": false,
  "recent_8k_count": 0,
  "key_facts": ["fact1", "fact2"],
  "extraction_confidence": "high/medium/low",
  "extraction_notes": "brief explanation"
}"""


class CompanyAgent(BaseAgent):
    """
    Genuinely agentic company research agent.

    Uses Anthropic native tool calling:
    - Claude decides which tools to call
    - Tools execute and return results
    - Claude reasons about results
    - Loop until Claude has enough information
    - Claude returns structured JSON output

    One LLM call with tool use loop.
    Additional extraction happens inside the same conversation.
    """

    agent_name = "company"
    MAX_ITERATIONS = 6

    def __init__(self):
        get_settings.cache_clear()
        s = get_settings()
        self.client = anthropic.AsyncAnthropic(
            api_key=s.anthropic_api_key
        )
        self.tools = [
            t.to_anthropic_format()
            for t in ALL_COMPANY_TOOLS
        ]

    async def run(
        self,
        state: EnrichmentState,
        emitter=None,
    ) -> dict:
        try:
            company = state.get("company", "")
            city    = state.get("city", "")
            state_  = state.get("state", "")

            def emit(msg, detail=None, icon="🔍"):
                if emitter:
                    emitter.emit(msg, detail, icon)
                logger.info(f"{msg} {detail or ''}")

            emit(
                f"Starting agentic company research",
                f"{company} | {city}, {state_}",
                "🤖"
            )

            # ── Run Anthropic tool calling loop ──────────
            result = await self._agent_loop(
                company, city, state_,
                emit, emitter
            )

            emit(
                f"Company research complete",
                f"residential={result.get('is_residential')} | "
                f"size={result.get('company_size')} | "
                f"disqualify={result.get('disqualify')}",
                "✅"
            )

            return self._mark_complete(state, {
                "company_data": result
            })

        except Exception as e:
            logger.error(f"CompanyAgent failed: {e}")
            return self._mark_error(state, e)

    async def _agent_loop(
        self,
        company:  str,
        city:     str,
        state_:   str,
        emit,
        emitter,
    ) -> dict:

        messages = [
    {
        "role": "user",
        "content": (
            f"Research this company for EliseAI lead qualification:\n"
            f"Company: {company}\n"
            f"Location: {city}, {state_}\n\n"
            f"TOOL INSTRUCTIONS:\n"
            f"- sec_edgar: pass company_name only\n"
            f"- private_research: pass company_name only\n"
            f"- tech_stack: pass company_name only\n"
            f"- news_search: pass company_name, "
            f"city='{city}', state='{state_}'\n"
            f"- job_postings: pass company_name, "
            f"city='{city}', state='{state_}'\n\n"
            f"Follow your tool calling rules. "
            f"Return final JSON when done."
        )
    }
]

        iteration = 0

        while iteration < self.MAX_ITERATIONS:
            iteration += 1

            emit(f"Agent iteration {iteration}", "sending to Claude", "🧠")

            

            response = await self.client.messages.create(
                model="claude-sonnet-4-5",
                max_tokens=4096,
                system=[
                    {
                        "type":          "text",
                        "text":          SYSTEM_PROMPT,
                        "cache_control": {"type": "ephemeral"}
                    }
                ],
                tools=self.tools,
                messages=messages,
            )
            # Debug — single clean print
            print(f"\n--- Iteration {iteration} ---")
            print(f"stop_reason: {response.stop_reason}")
            for block in response.content:
                print(f"  block: {block.type}", end="")
                if hasattr(block, 'text'):
                    print(f" → {block.text[:80]}", end="")
                if block.type == 'tool_use':
                    print(f" → {block.name}({block.input})", end="")
                print()

            
            # Add assistant response to history
            messages.append({
                "role":    "assistant",
                "content": response.content,
            })

            # Claude finished
            if response.stop_reason == "end_turn":
                emit("Claude finished reasoning", None, "✅")
                return self._extract_final_output(response.content, emit)

            # Unexpected stop
            if response.stop_reason != "tool_use":
                logger.warning(f"Unexpected stop reason: {response.stop_reason}")
                return self._empty_response()["company_data"]

            # Execute tool calls
            tool_use_blocks = [
                block for block in response.content
                if block.type == "tool_use"
            ]

            emit(
                f"Claude calling {len(tool_use_blocks)} tool(s)",
                ", ".join(b.name for b in tool_use_blocks),
                "🔧"
            )

            tool_results = await self._execute_tools_parallel(
                tool_use_blocks,
                company, city, state_,
                emit, emitter
            )

            print(f"\n--- TOOL RESULTS BEING SENT ---")
            import json
            for tr in tool_results:
                print(json.dumps(tr, indent=2, default=str)[:300])
            print("--- END TOOL RESULTS ---\n")

            # Add tool results
            messages.append({
                "role":    "user",
                "content": tool_results,
            })

        logger.warning("Max iterations reached")
        return self._empty_response()["company_data"]

    async def _execute_tools_parallel(
        self,
        tool_use_blocks: list,
        company:  str,
        city:     str,
        state_:   str,
        emit,
        emitter,
    ) -> list:
        """
        Execute all tool calls in parallel.
        Returns list of tool_result blocks for Anthropic API.
        """

        async def execute_one(block) -> dict:
            tool_name = block.name
            tool_input = block.input

            emit(
                f"Executing: {tool_name}",
                json.dumps(tool_input)[:80],
                "⚙️"
            )

            executor = TOOL_EXECUTORS.get(tool_name)
            if not executor:
                return {
                    "type":        "tool_result",
                    "tool_use_id": block.id,
                    "content":     json.dumps({
                        "error": f"Unknown tool: {tool_name}"
                    }),
                    "is_error":    True,
                }

            # WRONG — injects city/state into ALL tools including sec_edgar
            TOOLS_NEEDING_LOCATION = {"news_search", "job_postings"}

            kwargs = {"tool_use_id": block.id, "emitter": emitter}
            kwargs.update(tool_input)

            if tool_name in TOOLS_NEEDING_LOCATION:
                if "city" not in kwargs:
                    kwargs["city"] = city
                if "state" not in kwargs:
                    kwargs["state"] = state_



            tool_result = await executor(**kwargs)

            emit(
                f"Tool {tool_name} complete",
                None,
                "✅" if not tool_result.is_error else "❌"
            )

            return tool_result.to_anthropic_format()

        # Run all tools concurrently
        results = await asyncio.gather(
            *[execute_one(block) for block in tool_use_blocks],
            return_exceptions=True
        )

        # Handle any exceptions
        clean_results = []
        for i, r in enumerate(results):
            if isinstance(r, Exception):
                clean_results.append({
                    "type":        "tool_result",
                    "tool_use_id": tool_use_blocks[i].id,
                    "content":     json.dumps({"error": str(r)}),
                    "is_error":    True,
                })
            else:
                clean_results.append(r)

        return clean_results

    def _extract_final_output(
        self,
        content: list,
        emit,
    ) -> dict:
        """
        Extract final JSON from Claude's response.
        Claude should return structured JSON as text.
        """
        for block in content:
            if hasattr(block, "text"):
                text = block.text.strip()

                # Strip markdown if present
                if "```json" in text:
                    text = text.split("```json")[1].split("```")[0].strip()
                elif "```" in text:
                    text = text.split("```")[1].split("```")[0].strip()

                try:
                    result = json.loads(text)
                    emit(
                        f"Final output extracted",
                        f"disqualify={result.get('disqualify')} | "
                        f"is_residential={result.get('is_residential')} | "
                        f"size={result.get('company_size')}",
                        "📊"
                    )
                    return result
                except json.JSONDecodeError as e:
                    logger.error(f"JSON parse failed: {e}")
                    logger.error(f"Raw text: {text[:200]}")

        # Fallback
        logger.error("Could not extract JSON from Claude response")
        return self._empty_response()["company_data"]

    def _empty_response(self) -> dict:
        return {
            "company_data": {
                "disqualify":            False,
                "disqualify_reason":     None,
                "is_public":             False,
                "is_real_estate":        False,
                "is_residential":        False,
                "company_size":          "unknown",
                "ticker":                None,
                "exchange":              None,
                "sic_code":              None,
                "sic_description":       None,
                "units_managed":         None,
                "annual_revenue":        None,
                "aum":                   None,
                "valuation":             None,
                "net_income":            None,
                "total_assets":          None,
                "employee_count":        None,
                "eliseai_integrations":  [],
                "proptech_detected":     [],
                "crm_tools":             [],
                "tech_maturity_level":   1,
                "tech_maturity_label":   "Manual",
                "tech_maturity":         {},
                "talking_points":        [],
                "leasing_jobs":          0,
                "maintenance_jobs":      0,
                "tech_jobs":             0,
                "leadership_jobs":       0,
                "total_jobs":            0,
                "automation_urgency":    "unknown",
                "pain_points":           [],
                "is_expanding":          False,
                "funding_signals":       [],
                "leadership_signals":    [],
                "growth_signals":        [],
                "top_headlines":         [],
                "buying_signal_score":   0,
                "has_recent_material_event": False,
                "recent_8k_count":       0,
                "key_facts":             [],
                "extraction_confidence": "low",
                "extraction_notes":      "agent failed",
            }
        }


# ─── Singleton ──────────────────────────────────────────────────
company_agent = CompanyAgent()
