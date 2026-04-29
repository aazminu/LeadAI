# backend/tools/private_research_tool.py

import logging
from tools.base_tool import ToolDefinition, ToolResult
from config import get_settings

logger = logging.getLogger(__name__)

PRIVATE_RESEARCH_TOOL = ToolDefinition(
    name="private_research",
    description=(
        "Research a PRIVATE company using Exa AI web search. "
        "Call this ONLY when sec_edgar returns is_public=False. "
        "Finds about page, funding rounds, company size signals. "
        "Returns raw text from multiple sources — you will "
        "extract structured facts from this text. "
        "Returns: combined_text, source_urls, sources_found."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "company_name": {
                "type":        "string",
                "description": "Company name to research"
            }
        },
        "required": ["company_name"]
    }
)


async def execute_private_research(
    tool_use_id:  str,
    company_name: str,
    emitter=None,
) -> ToolResult:
    """
    Research private company via Exa AI.
    Returns raw text — LLM extracts facts from it.
    """
    def emit(msg, detail=None, icon="🔍"):
        if emitter:
            emitter.emit(msg, detail, icon)
        logger.info(f"{msg} {detail or ''}")

    try:
        get_settings.cache_clear()
        s = get_settings()

        from exa_py import Exa
        exa = Exa(api_key=s.exa_api_key)

        emit(
            f"Researching private company via Exa",
            company_name,
            "🔎"
        )

        # Search 1: About page
        about = exa.search_and_contents(
            f"{company_name} property management "
            f"about company overview",
            num_results=2,
            text=True,
        )

        # Search 2: Funding + size signals
        funding = exa.search_and_contents(
            f"{company_name} funding valuation employees "
            f"revenue apartments units managed",
            num_results=3,
            text=True,
        )

        # Combine all sources
        all_text = []
        all_urls = []

        for r in (about.results + funding.results):
            if r.text:
                all_text.append(
                    f"SOURCE: {r.url}\n"
                    f"{r.text[:2000]}"
                )
                all_urls.append(r.url)

        combined = "\n\n---\n\n".join(all_text)

        emit(
            f"Found {len(all_urls)} sources",
            f"{all_urls[0] if all_urls else 'none'}",
            "✅" if all_urls else "⚠️"
        )

        return ToolResult(
            tool_use_id=tool_use_id,
            content={
                "combined_text":  combined[:6000],
                "source_urls":    all_urls,
                "sources_found":  len(all_urls),
                "char_count":     len(combined),
            }
        )

    except Exception as e:
        logger.error(f"private_research tool failed: {e}")
        return ToolResult(
            tool_use_id=tool_use_id,
            content={
                "error":         str(e),
                "combined_text": "",
                "source_urls":   [],
                "sources_found": 0,
            },
            is_error=True,
        )