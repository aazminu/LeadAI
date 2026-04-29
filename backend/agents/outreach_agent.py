# backend/agents/outreach_agent.py

import json
import logging
import anthropic
from agents.base_agent import BaseAgent, EnrichmentState
from config import get_settings

logger = logging.getLogger(__name__)


OUTREACH_SYSTEM_PROMPT = """You are an expert SDR at EliseAI writing 
cold outreach emails to residential property managers.

ABOUT ELISEAI:
EliseAI automates leasing communication, maintenance requests, 
and resident operations for property managers.
- Backed by Andreessen Horowitz $250M Series E
- Customers: Greystar, AvalonBay, Equity Residential, 500+ operators
- Integrates natively with Yardi, Entrata, OneSite, RealPage
- Deploys in 30 days alongside existing systems

EMAIL STRUCTURE — follow this exactly:
1. SIGNAL    → open with ONE specific signal you found
               (hiring, tech gap, market pressure, growth)
2. INSIGHT   → interpret what that signal MEANS for them
               THIS IS YOUR EDGE — show operational understanding
3. SOFT PITCH → connect EliseAI naturally, don't hard sell
4. CTA       → one low-friction ask (15-min call, quick question)

TONE RULES:
- Semi-formal — "Hi Sarah" not "Dear Ms. Johnson"
- Conversational — write like a thoughtful human, not a template
- Specific — reference actual numbers, company names, tool names
- Short — under 120 words for first email
- Never say "I hope this email finds you well"
- Never use "synergies", "leverage", "cutting-edge", "game-changer"
- Never mention AI generically — say exactly what EliseAI does
- Never start with "I" — start with the signal

SIGNAL PRIORITY (use strongest available):
1. Hiring pressure    → hiring signal is strongest
2. Tech gap          → using PropTech without automation
3. Growth signal     → expanding, funded, new markets
4. Market pressure   → high leasing intensity in their city

INSIGHT RULES — this is your competitive edge:
The insight must show you understand property management operations.
Not generic business insight — specific to leasing/maintenance workflows.

Hiring signal insight examples:
BAD:  "You're hiring a lot of leasing agents"
GOOD: "4 leasing roles usually means your team spends 
       80% of their time on inquiry triage instead of tours — 
       the activity that actually drives revenue"
GOOD: "When you're filling 4 leasing roles simultaneously, 
       your best agents are answering the same 10 questions 
       over and over instead of closing leases"

Tech gap insight examples:
BAD:  "You don't have automation yet"
GOOD: "Yardi handles your back office beautifully but 
       prospect communication still hits a human inbox — 
       that's where 40% of leads go dark after hours"
GOOD: "Entrata gives you great resident management but 
       the prospect-to-lease journey still runs through 
       your leasing team's inbox and voicemail"

Market pressure insight examples:
BAD:  "Dallas is a competitive market"
GOOD: "Dallas leasing intensity means prospects are 
       shopping 3-4 properties simultaneously — 
       whoever responds first at 10pm wins the lease"
GOOD: "In a high-velocity market like Dallas, a 2-hour 
       response delay costs you the lead — 
       prospects have already toured somewhere else"

Growth insight examples:
BAD:  "You're expanding fast"
GOOD: "Adding properties without proportional headcount 
       is exactly where leasing velocity starts to slip — 
       more doors, same team, more after-hours inquiries"

PROOF POINTS TO USE:
- "AvalonBay runs EliseAI across 290+ properties alongside Yardi"
- "Equity Residential reduced leasing response time by 80%"
- "Backed by a16z — $250M Series E"
- "Deploys in 30 days, works alongside your existing Yardi/Entrata stack"
- "500+ operators, including the top 10 NMHC managers"

SUBJECT LINE RULES:
- Under 8 words
- Sound like a human wrote it, not a tool
- Reference something specific to their world
- Create curiosity — don't give away the whole point
- Never mention job counts or hiring numbers in subject
- Never use "question" as a standalone word
- Never use "+ 1" format

GOOD subject line examples:
  "Greystar's Dallas leasing ops"
  "Quick thought on Entrata + surge season"
  "How AvalonBay handles this at scale"
  "Re: 70 campuses, one leasing team"
  "Before your next leasing surge"

BAD subject line examples (never do these):
  "11 open roles + 1 CX question"   ← sounds automated
  "7 maintenance roles + question"  ← reveals data scraping
  "Leasing automation question"     ← too generic

CTA RULES:
- One ask only
- Low friction — "worth a 15-min call?" not "book a demo"
- Reference their specific situation
- Examples:
  "Worth 15 min to see how AvalonBay handles this?"
  "Happy to show you what this looks like in Yardi — 15 min?"
  "Quick call to walk through how this works with Entrata?"

SIGN-OFF RULES:
- Do NOT include any closing or sign-off (no "Best,", no "Thanks,", no "[Your name]", no signature block)
- End the email_draft at the CTA — the system appends the sender's signature automatically

RETURN ONLY VALID JSON — no markdown, no preamble:
{
  "subject":       "email subject line",
  "email_draft":   "full email body — ends at the CTA, NO sign-off, NO 'Best,', NO '[Your name]'",
  "signal_used":   "hiring/tech_gap/growth/market",
  "signal_detail": "exact signal referenced in email",
  "pitch_angle":   "one sentence describing angle used",
  "talking_points": [
    "point 1 for follow-up call",
    "point 2 for follow-up call", 
    "point 3 for follow-up call"
  ],
  "word_count": 0
}"""

REGENERATE_SYSTEM_PROMPT = """You are an expert SDR at EliseAI 
rewriting a cold outreach email based on SDR feedback.

ABOUT ELISEAI:
- Automates leasing communication and maintenance for property managers
- Backed by a16z $250M Series E
- Customers: Greystar, AvalonBay, Equity Residential, 500+ operators
- Native integrations: Yardi, Entrata, OneSite, RealPage

EMAIL STRUCTURE — always maintain:
1. SIGNAL    → specific signal (hiring/tech gap/growth/market)
2. INSIGHT   → operational interpretation showing expertise  
3. SOFT PITCH → natural EliseAI connection
4. CTA       → one low-friction ask

Apply the SDR feedback exactly as requested.
Keep under 120 words unless feedback says otherwise.
Never start with "I".
Never use generic AI language.
Do NOT include any closing or sign-off — end at the CTA.

RETURN ONLY VALID JSON:
{
  "subject":       "email subject line",
  "email_draft":   "full email body — ends at the CTA, NO sign-off, NO 'Best,', NO '[Your name]'",
  "signal_used":   "hiring/tech_gap/growth/market",
  "signal_detail": "exact signal referenced",
  "pitch_angle":   "one sentence on angle used",
  "talking_points": [
    "point 1",
    "point 2",
    "point 3"
  ],
  "word_count":    0,
  "changes_made":  "specific changes made based on feedback"
}"""

class OutreachAgent(BaseAgent):
    """
    Generates personalized cold outreach emails.
    
    Structure: Signal → Insight → Soft pitch → CTA
    
    Two modes:
    1. generate()    → first email from enrichment data
    2. regenerate()  → revised email based on SDR feedback
    """

    agent_name = "outreach"

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
        """Standard pipeline run — generates first email."""
        try:
            def emit(msg, detail=None, icon="🔍"):
                if emitter:
                    emitter.emit(msg, detail, icon)
                logger.info(f"{msg} {detail or ''}")

            company_data  = state.get("company_data", {}) or {}
            market_data   = state.get("market_data", {}) or {}
            identity_data = state.get("identity_data", {}) or {}
            score_data    = state.get("score", 0)
            insights      = state.get("insights", {}) or {}

            company = company_data.get("company_name", "")
            name    = identity_data.get("name", "")

            emit(
                f"Generating outreach email",
                f"{name} at {company}",
                "✉️"
            )

            prompt = self._build_prompt(
                company_data,
                market_data,
                identity_data,
                insights,
            )

            response = await self.client.messages.create(
                model="claude-sonnet-4-5",
                max_tokens=4096,
                system=[
                    {
                        "type":          "text",
                        "text":          OUTREACH_SYSTEM_PROMPT,
                        "cache_control": {"type": "ephemeral"}
                    }
                ],

                messages=[{"role": "user", "content": prompt}],

            )

            print(
      "Claude usage:",
      "input=", response.usage.input_tokens,
      "cache_create=", response.usage.cache_creation_input_tokens,
      "cache_read=", response.usage.cache_read_input_tokens,
      "output=", response.usage.output_tokens,
  )
            result = self._parse_response(response.content[0].text)

            emit(
                f"Email generated",
                f"Signal: {result.get('signal_used')} | "
                f"Words: {result.get('word_count')}",
                "✅"
            )
            emit(
                f"Subject: {result.get('subject')}",
                result.get("signal_detail", ""),
                "📌"
            )

            email_subject = result.get("email_subject") or result.get("subject")
            return self._mark_complete(state, {
                "email_draft":   result.get("email_draft"),
                "email_subject": email_subject,
                "signal_used":   result.get("signal_used"),
                "pitch_angle":   result.get("pitch_angle"),
                "talking_points": result.get("talking_points", []),
                "word_count":    result.get("word_count"),
            })

        except Exception as e:
            logger.error(f"OutreachAgent failed: {e}")
            return self._mark_error(state, e)

    async def regenerate(
        self,
        state:          EnrichmentState,
        previous_email: str,
        feedback:       str,
        emitter=None,
    ) -> dict:
        """
        Regenerate email based on SDR feedback.
        Called directly — not through LangGraph.
        
        Example:
            result = await outreach_agent.regenerate(
                state=state,
                previous_email=result["email_draft"],
                feedback="Example: Make it shorter and more casual"
            )
        """
        def emit(msg, detail=None, icon="🔍"):
            if emitter:
                emitter.emit(msg, detail, icon)
            logger.info(f"{msg} {detail or ''}")

        try:
            company_data  = state.get("company_data", {}) or {}
            market_data   = state.get("market_data", {}) or {}
            identity_data = state.get("identity_data", {}) or {}
            insights      = state.get("insights", {}) or {}

            emit(
                "Regenerating email with feedback",
                feedback,
                "🔄"
            )

            prompt = f"""
ORIGINAL EMAIL:
{previous_email}

SDR FEEDBACK:
{feedback}

ENRICHMENT CONTEXT (for reference):
{self._build_prompt(company_data, market_data, identity_data, insights)}

Rewrite the email applying the feedback exactly.
Keep Signal → Insight → Soft pitch → CTA structure.
"""

            response = await self.client.messages.create(
                model="claude-sonnet-4-5",
                max_tokens=4096,
                system=[
                    {
                        "type":          "text",
                        "text":          REGENERATE_SYSTEM_PROMPT,
                        "cache_control": {"type": "ephemeral"}
                    }
                ],

                messages=[{"role": "user", "content": prompt}],

            )
            
            result = self._parse_response(response.content[0].text)

            emit(
                "Email regenerated",
                f"Changes: {result.get('changes_made', '')}",
                "✅"
            )

            email_subject = result.get("email_subject") or result.get("subject")
            return {
                "email_draft":   result.get("email_draft"),
                "email_subject": email_subject,
                "signal_used":   result.get("signal_used"),
                "pitch_angle":   result.get("pitch_angle"),
                "talking_points": result.get("talking_points", []),
                "word_count":    result.get("word_count"),
                "changes_made":  result.get("changes_made"),
                "feedback_applied": feedback,
            }

        except Exception as e:
            logger.error(f"OutreachAgent regenerate failed: {e}")
            return {"error": str(e)}

    def _build_prompt(
        self,
        company_data:  dict,
        market_data:   dict,
        identity_data: dict,
        insights:      dict,
    ) -> str:

        # Determine strongest signal
        leasing_jobs     = company_data.get("leasing_jobs", 0)
        maintenance_jobs = company_data.get("maintenance_jobs", 0)
        eliseai_tools    = company_data.get("eliseai_integrations", [])
        proptech         = company_data.get("proptech_detected", [])
        is_expanding     = company_data.get("is_expanding", False)
        leasing_intensity = market_data.get("leasing_intensity", "")

        # Signal priority
        if leasing_jobs >= 2:
            primary_signal = f"HIRING: {leasing_jobs} leasing roles + {maintenance_jobs} maintenance roles open"
        elif not proptech:
            primary_signal = "TECH GAP: No PropTech detected — likely manual operations"
        elif eliseai_tools:
            primary_signal = f"TECH GAP: Uses {eliseai_tools} but no leasing automation yet"
        elif is_expanding:
            primary_signal = "GROWTH: Active expansion detected"
        elif leasing_intensity == "high":
            primary_signal = f"MARKET: High leasing intensity in {market_data.get('city')}"
        else:
            primary_signal = "FIT: Residential operator matching EliseAI ICP"

        return f"""
Write a cold outreach email using this enrichment data.

CONTACT:
Name:    {identity_data.get('name', 'there')}
Title:   {identity_data.get('verified_title', 'Property Manager')}
Company: {company_data.get('company_name')}
Email:   {identity_data.get('email', '')}

STRONGEST SIGNAL TO LEAD WITH:
{primary_signal}

COMPANY CONTEXT:
- Size: {company_data.get('company_size')} | Units: {company_data.get('units_managed')}
- EliseAI integrations: {eliseai_tools or 'none detected'}
- PropTech stack: {proptech or 'none detected'}
- Tech maturity: Level {company_data.get('tech_maturity_level')}
- Pain points: {company_data.get('pain_points', [])}
- Key facts: {company_data.get('key_facts', [])[:3]}

MARKET CONTEXT:
- City: {market_data.get('city')}, {market_data.get('state')}
- Leasing intensity: {leasing_intensity}
- Product line: {market_data.get('eliseai_product_line')}

SCORING INSIGHTS:
- Pitch angle: {insights.get('pitch_angle', '')}
- Integration hook: {insights.get('integration_hook', '')}

Follow Signal → Insight → Soft pitch → CTA structure.
Use the contact's first name.
Reference specific numbers and tool names.
"""

    def _parse_response(self, text: str) -> dict:
        text = text.strip()
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            logger.error(f"JSON parse failed: {e}")
            return {
                "subject":      "Following up",
                "email_draft":  text,
                "signal_used":  "unknown",
                "word_count":   len(text.split()),
            }

    def _empty_response(self) -> dict:
        return {
            "email_draft":    None,
            "email_subject":  None,
            "signal_used":    None,
            "pitch_angle":    None,
            "talking_points": [],
            "word_count":     0,
        }


# ─── Singleton ──────────────────────────────────────────────────
outreach_agent = OutreachAgent()
