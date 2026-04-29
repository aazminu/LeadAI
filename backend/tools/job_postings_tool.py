# backend/tools/job_postings_tool.py

import logging
from tools.base_tool import ToolDefinition, ToolResult
from services.adzuna_service import adzuna_service

logger = logging.getLogger(__name__)

JOB_POSTINGS_TOOL = ToolDefinition(
    name="job_postings",
    description=(
        "Search Adzuna for company job postings. "
        "Returns hiring volume by role type. "
        "High leasing job count = understaffed = pain signal. "
        "High maintenance jobs = automation opportunity. "
        "Systems adoption roles = actively implementing software NOW. "
        "Call this for ALL residential real estate companies."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "company_name": {
                "type":        "string",
                "description": "Company name to search jobs for"
            },
            "city": {
                "type":        "string",
                "description": "City to search jobs in"
            },
            "state": {
                "type":        "string",
                "description": "State abbreviation e.g. TX"
            }
        },
        "required": ["company_name"]
    }
)


async def execute_job_postings(
    tool_use_id:  str,
    company_name: str,
    city:         str = "",
    state:        str = "",
    emitter=None,
) -> ToolResult:
    try:
        result = await adzuna_service.get_hiring_signals(
            company_name, city, state,
            emitter=emitter,
        )

        clean = {
            "total_jobs_found":       result.get("total_jobs_found", 0),
            "leasing_jobs":           result.get("leasing_jobs", 0),
            "maintenance_jobs":       result.get("maintenance_jobs", 0),
            "tech_jobs":              result.get("tech_jobs", 0),
            "leadership_jobs":        result.get("leadership_jobs", 0),
            "automation_urgency":     result.get("automation_urgency", "unknown"),
            "pain_points":            result.get("pain_points", []),
            "is_adopting_new_software": result.get(
                "is_adopting_new_software", False
            ),
            "growth_signal":          result.get("growth_signal", False),
            "data_source":            "Adzuna Jobs API",
        }

        return ToolResult(
            tool_use_id=tool_use_id,
            content=clean,
        )

    except Exception as e:
        logger.error(f"job_postings tool failed: {e}")
        return ToolResult(
            tool_use_id=tool_use_id,
            content={"error": str(e)},
            is_error=True,
        )