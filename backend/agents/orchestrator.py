# backend/agents/orchestrator.py

import logging
from langgraph.graph import StateGraph, START, END
from agents.base_agent import EnrichmentState

logger = logging.getLogger(__name__)


# ── Dummy Nodes ──────────────────────────────────────────────────

async def dummy_identity_node(state: EnrichmentState) -> dict:
    return {
        "identity_data":    {
            "status":           "dummy",
            "name":             state.get("name", ""),
            "email":            state.get("email", ""),
            "verified_title":   "Unknown",
            "seniority":        "unknown",
            "dm_probability":   0.5,
            "linkedin_url":     None,
        },
        "completed_agents": ["identity"],
    }

async def dummy_company_node(state: EnrichmentState) -> dict:
    return {
        "company_data": {
            "status":           "dummy",
            "company_name":     state.get("company", ""),
            "is_residential":   True,
            "is_real_estate":   True,
            "company_size":     "unknown",
            "disqualify":       False,
        },
        "completed_agents": ["company"],
    }

async def dummy_market_node(state: EnrichmentState) -> dict:
    return {
        "market_data":      {"status": "dummy"},
        "completed_agents": ["market"],
    }

async def dummy_property_node(state: EnrichmentState) -> dict:
    return {
        "property_data":    {"status": "dummy"},
        "completed_agents": ["property"],
    }

async def dummy_values_node(state: EnrichmentState) -> dict:
    return {
        "values_data":      {"status": "dummy"},
        "completed_agents": ["values"],
    }

async def dummy_scoring_node(state: EnrichmentState) -> dict:
    return {
        "score":            75.0,
        "tier":             "warm",
        "recommended_action": "Contact within 72 hours",
        "score_breakdown":  {},
        "insights":         {},
        "completed_agents": ["scoring"],
    }

async def dummy_outreach_node(state: EnrichmentState) -> dict:
    return {
        "email_draft":      "Hi there, this is a dummy email.",
        "email_subject":    "Quick question",
        "talking_points":   [],
        "completed_agents": ["outreach"],
    }

async def disqualified_node(state: EnrichmentState) -> dict:
    company_data = state.get("company_data", {}) or {}
    reason = company_data.get("disqualify_reason", "Not residential real estate")
    logger.info(f"Lead disqualified: {reason}")
    return {
        "status":           "disqualified",
        "score":            0,
        "tier":             "disqualified",
        "recommended_action": f"Do not contact — {reason}",
        "completed_agents": ["disqualified"],
    }
async def real_outreach_node(state: EnrichmentState) -> dict:
    from agents.outreach_agent import outreach_agent
    try:
        result = await outreach_agent.run(state)
        return result
    except Exception as e:
        print(f"OUTREACH ERROR: {e}")
        import traceback
        traceback.print_exc()
        return {
            "email_draft":      None,
            "completed_agents": ["outreach"],
        }

async def collector_node(state: EnrichmentState) -> dict:
    """
    Collects all enrichment outputs before routing.
    Prevents multiple simultaneous writes to scoring.
    """
    return {}  # just a gate — no writes

# ── Real Agent Wrappers ──────────────────────────────────────────
# Wrap real agents to pass emitter through state

async def real_identity_node(state: EnrichmentState) -> dict:
    from agents.identity_agent import identity_agent
    emitter = _make_emitter(state, "identity")
    result = await identity_agent.run(state, emitter=emitter)
    await _mark_agent_complete(state, "identity", result)
    return result

async def real_company_node(state: EnrichmentState) -> dict:
    from agents.company_agent import company_agent
    emitter = _make_emitter(state, "company")
    result = await company_agent.run(state, emitter=emitter)
    await _mark_agent_complete(state, "company", result)
    return result

async def real_market_node(state: EnrichmentState) -> dict:
    from agents.market_agent import market_agent
    emitter = _make_emitter(state, "market")
    result = await market_agent.run(state, emitter=emitter)
    await _mark_agent_complete(state, "market", result)
    return result

async def real_property_node(state: EnrichmentState) -> dict:
    from agents.property_agent import property_agent
    emitter = _make_emitter(state, "property")
    result = await property_agent.run(state, emitter=emitter)
    await _mark_agent_complete(state, "property", result)
    return result

async def real_values_node(state: EnrichmentState) -> dict:
    from agents.values_agent import values_agent
    emitter = _make_emitter(state, "values")
    result = await values_agent.run(state, emitter=emitter)
    await _mark_agent_complete(state, "values", result)
    return result

async def real_scoring_node(state: EnrichmentState) -> dict:
    from agents.scoring_agent import scoring_agent
    emitter = _make_emitter(state, "scoring")
    result = await scoring_agent.run(state, emitter=emitter)
    await _mark_agent_complete(state, "scoring", result)
    return result

async def real_outreach_node(state: EnrichmentState) -> dict:
    from agents.outreach_agent import outreach_agent
    emitter = _make_emitter(state, "outreach")
    result = await outreach_agent.run(state, emitter=emitter)
    await _mark_agent_complete(state, "outreach", result)
    return result


def _make_emitter(state: EnrichmentState, agent_name: str):
    emitter_factory = state.get("emitter_factory")
    if not emitter_factory:
        return None
    return emitter_factory(agent_name)


async def _mark_agent_complete(state: EnrichmentState, agent_name: str, result: dict):
    completion_callback = state.get("completion_callback")
    if completion_callback:
        await completion_callback(agent_name, result)


# ── Routing Functions ────────────────────────────────────────────

def route_after_enrichment(state: EnrichmentState) -> str:
    """
    After enrichment agents complete check if residential.
    Company agent sets disqualify=True if not residential.
    """
    company_data = state.get("company_data", {}) or {}

    # Check explicit disqualify flag from company agent
    if company_data.get("disqualify", False):
        logger.info(
            f"Routing to disqualified: "
            f"{company_data.get('disqualify_reason', 'not residential')}"
        )
        return "disqualified"

    return "scoring"


def route_after_scoring(state: EnrichmentState) -> str:
    """Only explicit scoring disqualification stops outreach."""
    if state.get("tier") == "disqualified" or state.get("status") == "disqualified":
        logger.info("Scoring explicitly disqualified lead")
        return "disqualified"
    return "outreach"

async def collector_node(state: EnrichmentState) -> dict:
    """Gate node — waits for all 5 agents then routes."""
    return {}

# ── Build Graph ──────────────────────────────────────────────────

def build_graph(use_real_agents: bool = False):
    """
    Build LangGraph enrichment pipeline.
    use_real_agents=False → dummy nodes
    use_real_agents=True  → real agents
    """
    workflow = StateGraph(EnrichmentState)

    if use_real_agents:
        identity_node = real_identity_node
        company_node  = real_company_node
        market_node   = real_market_node
        property_node = real_property_node
        values_node   = real_values_node
        scoring_node  = real_scoring_node
        outreach_node = real_outreach_node
    else:
        identity_node = dummy_identity_node
        company_node  = dummy_company_node
        market_node   = dummy_market_node
        property_node = dummy_property_node
        values_node   = dummy_values_node
        scoring_node  = dummy_scoring_node
        outreach_node = dummy_outreach_node

    # Add nodes
    workflow.add_node("collector", collector_node)  # ← add this
    workflow.add_node("identity",     identity_node)
    workflow.add_node("company",      company_node)
    workflow.add_node("market",       market_node)
    workflow.add_node("property",     property_node)
    workflow.add_node("values",       values_node)
    workflow.add_node("scoring",      scoring_node)
    workflow.add_node("outreach",     outreach_node)
    workflow.add_node("disqualified", disqualified_node)

    # Remove individual conditional edges from each agent
    # Replace with:

    # Fan out from START
    workflow.add_edge(START, "identity")
    workflow.add_edge(START, "company")
    workflow.add_edge(START, "market")
    workflow.add_edge(START, "property")
    workflow.add_edge(START, "values")

    # All 5 → collector
    workflow.add_edge("identity", "collector")
    workflow.add_edge("company",  "collector")
    workflow.add_edge("market",   "collector")
    workflow.add_edge("property", "collector")
    workflow.add_edge("values",   "collector")

    # Collector → routing
    workflow.add_conditional_edges(
        "collector",
        route_after_enrichment,
        {"scoring": "scoring", "disqualified": "disqualified"}
    )

    # Scoring → outreach or disqualify
    workflow.add_conditional_edges(
        "scoring",
        route_after_scoring,
        {"outreach": "outreach", "disqualified": "disqualified"}
    )

    # Terminal
    workflow.add_edge("outreach",     END)
    workflow.add_edge("disqualified", END)

    return workflow.compile()


# ── Singleton instances ──────────────────────────────────────────
dummy_graph = build_graph(use_real_agents=False)

real_graph  = build_graph(use_real_agents=True)
