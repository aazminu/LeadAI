# backend/tools/base_tool.py

from dataclasses import dataclass
from typing import Any


@dataclass
class ToolDefinition:
    """
    Defines a tool for Anthropic's tool calling API.
    
    name:        must match function name Claude calls
    description: what Claude reads to decide when to use this tool
                 be specific — vague descriptions = wrong tool choices
    input_schema: JSON schema for parameters Claude passes
    """
    name:         str
    description:  str
    input_schema: dict

    def to_anthropic_format(self) -> dict:
        """Convert to Anthropic API tool format."""
        return {
            "name":         self.name,
            "description":  self.description,
            "input_schema": self.input_schema,
        }


class ToolResult:
    """
    Wraps tool execution results for return to Anthropic API.
    """
    def __init__(
        self,
        tool_use_id: str,
        content:     Any,
        is_error:    bool = False,
    ):
        self.tool_use_id = tool_use_id
        self.content     = content
        self.is_error    = is_error

    def to_anthropic_format(self) -> dict:
        """Convert to Anthropic API tool_result format."""
        import json
        return {
            "type":        "tool_result",
            "tool_use_id": self.tool_use_id,
            "content":     json.dumps(self.content)
                           if not isinstance(self.content, str)
                           else self.content,
        }