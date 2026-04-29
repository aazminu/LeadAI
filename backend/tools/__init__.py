# backend/tools/__init__.py

from tools.base_tool import ToolDefinition, ToolResult
from tools.sec_edgar_tool import SEC_EDGAR_TOOL, execute_sec_edgar
from tools.private_research_tool import PRIVATE_RESEARCH_TOOL, execute_private_research
from tools.news_search_tool import NEWS_SEARCH_TOOL, execute_news_search
from tools.job_postings_tool import JOB_POSTINGS_TOOL, execute_job_postings
from tools.tech_stack_tool import TECH_STACK_TOOL, execute_tech_stack

# All tool definitions for Anthropic API
ALL_COMPANY_TOOLS = [
    SEC_EDGAR_TOOL,
    PRIVATE_RESEARCH_TOOL,
    NEWS_SEARCH_TOOL,
    JOB_POSTINGS_TOOL,
    TECH_STACK_TOOL,
]

# Tool executor map
TOOL_EXECUTORS = {
    "sec_edgar":         execute_sec_edgar,
    "private_research":  execute_private_research,
    "news_search":       execute_news_search,
    "job_postings":      execute_job_postings,
    "tech_stack":        execute_tech_stack,
}