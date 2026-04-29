# backend/tools/news_search_tool.py

import logging
from tools.base_tool import ToolDefinition, ToolResult
from services.news_service import news_service

logger = logging.getLogger(__name__)

NEWS_SEARCH_TOOL = ToolDefinition(
    name="news_search",
    description=(
        "Search recent news articles about a company. "
        "Call this to get growth and timing signals. "
        "Returns expansion signals, funding news, "
        "leadership changes, pain signals, "
        "and a buying signal score 0-100. "
        "Call this for ALL residential real estate companies."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "company_name": {
                "type":        "string",
                "description": "Company name to search news for"
            },
            "city": {
                "type":        "string",
                "description": "City where company operates"
            },
            "state": {
                "type":        "string",
                "description": "State abbreviation e.g. TX"
            }
        },
        "required": ["company_name"]
    }
)


async def execute_news_search(
    tool_use_id:  str,
    company_name: str,
    city:         str = "",
    state:        str = "",
    emitter=None,
) -> ToolResult:
    try:
        result = await news_service.get_company_news(
            company_name, city, state,
            emitter=emitter,
        )

        clean = {
            "is_expanding":      result.get("is_expanding", False),
            "has_pain_signals":  result.get("has_pain_signals", False),
            "buying_signal":     result.get("buying_signal", "low"),
            "buying_signal_score": result.get("buying_signal_score", 0),
            "expansion_signals": result.get("expansion_signals", [])[:2],
            "funding_signals":   result.get("funding_signals", [])[:2],
            "leadership_signals": result.get("leadership_signals", [])[:2],
            "pain_signals":      result.get("pain_signals", [])[:2],
            "top_headlines":     result.get("top_headlines", [])[:3],
            "data_source":       "NewsAPI",
        }

        return ToolResult(
            tool_use_id=tool_use_id,
            content=clean,
        )

    except Exception as e:
        logger.error(f"news_search tool failed: {e}")
        return ToolResult(
            tool_use_id=tool_use_id,
            content={"error": str(e)},
            is_error=True,
        )