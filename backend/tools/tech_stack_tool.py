# backend/tools/tech_stack_tool.py

import logging
from tools.base_tool import ToolDefinition, ToolResult
from services.techstack_service import techstack_service

logger = logging.getLogger(__name__)

TECH_STACK_TOOL = ToolDefinition(
    name="tech_stack",
    description=(
        "Detect technology stack from company job postings. "
        "Returns PropTech tools (Yardi, RealPage, Entrata, OneSite), "
        "CRM tools, EliseAI integration matches, "
        "and tech maturity level 1-4. "
        "Call this for ALL residential real estate companies. "
        "EliseAI integrates natively with Yardi, Entrata, OneSite."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "company_name": {
                "type":        "string",
                "description": "Company name to detect tech stack for"
            }
        },
        "required": ["company_name"]
    }
)


async def execute_tech_stack(
    tool_use_id:  str,
    company_name: str,
    emitter=None,
) -> ToolResult:
    try:
        result = await techstack_service.get_tech_stack(
            company_name,
            emitter=emitter,
        )

        clean = {
            "proptech_detected":     result.get("proptech_detected", []),
            "eliseai_integrations":  result.get("eliseai_integrations", []),
            "has_eliseai_integration": result.get(
                "has_eliseai_integration", False
            ),
            "crm_tools":             result.get("crm_tools", []),
            "cloud_tools":           result.get("cloud_tools", []),
            "ai_signals":            result.get("ai_signals", []),
            "tech_maturity_level":   result.get("tech_maturity_level", 1),
            "tech_maturity_label":   result.get("tech_maturity_label", "Manual"),
            "tech_maturity":         result.get("tech_maturity", {}),
            "is_tech_forward":       result.get("is_tech_forward", False),
            "talking_points":        result.get("talking_points", []),
            "careers_url":           result.get("careers_url"),
            "data_source":           "Exa job postings analysis",
        }

        return ToolResult(
            tool_use_id=tool_use_id,
            content=clean,
        )

    except Exception as e:
        logger.error(f"tech_stack tool failed: {e}")
        return ToolResult(
            tool_use_id=tool_use_id,
            content={"error": str(e)},
            is_error=True,
        )