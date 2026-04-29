# backend/tools/sec_edgar_tool.py

import logging
from tools.base_tool import ToolDefinition, ToolResult
from services.edgar_service import edgar_service

logger = logging.getLogger(__name__)

# ── Tool Definition ──────────────────────────────────────────────
# This is what Claude reads to decide when to call this tool

SEC_EDGAR_TOOL = ToolDefinition(
    name="sec_edgar",
    description=(
        "Search SEC EDGAR database for company information. "
        "ALWAYS call this tool first for any company. "
        "Returns structured financial data for PUBLIC companies. "
        "Returns is_public=False if company is private. "
        "Also returns is_real_estate and is_residential — "
        "if is_residential=False, stop all research immediately. "
        "EliseAI only serves residential property managers. "
        "Returns: is_public, is_real_estate, is_residential, "
        "revenue, units_managed, employees, ticker, "
        "company_size, recent_8k_events."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "company_name": {
                "type":        "string",
                "description": "Full company name to search in SEC EDGAR"
            }
        },
        "required": ["company_name"]
    }
)


# ── Tool Executor ────────────────────────────────────────────────

async def execute_sec_edgar(
    tool_use_id:  str,
    company_name: str,
    emitter=None,
) -> ToolResult:
    """
    Execute SEC EDGAR lookup.
    Thin wrapper over edgar_service.
    """
    try:
        result = await edgar_service.get_company_intelligence(
            company_name,
            emitter=emitter,
        )

        # Return clean subset — don't flood Claude with raw data
        # Keep only what Claude needs to make decisions
        clean = {
            # Gate check fields — Claude reads these first
            "is_public":       result.get("is_public", False),
            "is_real_estate":  result.get("is_real_estate", False),
            "is_residential":  result.get("is_residential", False),

            # Company facts
            "company_size":    result.get("company_size", "unknown"),
            "ticker":          result.get("ticker"),
            "exchange":        result.get("exchange"),
            "sic_code":        result.get("sic_code"),
            "sic_description": result.get("sic_description"),

            # Financial facts (public only)
            "annual_revenue":  result.get("annual_revenue"),
            "net_income":      result.get("net_income"),
            "total_assets":    result.get("total_assets"),
            "units_managed":   result.get("units_managed"),
            "properties_count": result.get("properties_count"),
            "employee_count":  result.get("employee_count"),

            # Growth signals
            "has_recent_material_event": result.get(
                "has_recent_material_event", False
            ),
            "recent_8k_count": result.get("recent_8k_count", 0),
            "growth_signals":  result.get("growth_signals", []),

            # Citations
            "citations":       result.get("citations", {}),
            "data_source":     result.get("data_source", "SEC EDGAR"),
        }

        return ToolResult(
            tool_use_id=tool_use_id,
            content=clean,
        )

    except Exception as e:
        logger.error(f"sec_edgar tool failed: {e}")
        return ToolResult(
            tool_use_id=tool_use_id,
            content={"error": str(e), "is_public": False},
            is_error=True,
        )