# backend/services/llm_service.py

import json
import logging
from typing import Any
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type
)
import litellm
from litellm import acompletion
from config import settings

logger = logging.getLogger(__name__)

# Tell LiteLLM which key to use
litellm.anthropic_key = settings.anthropic_api_key

# Suppress LiteLLM's verbose logging unless debugging
litellm.set_verbose = settings.debug


class LLMService:
    """
    Provider-agnostic LLM abstraction layer.
    
    All agents call this — never call litellm or anthropic directly.
    To swap providers: change LITELLM_MODEL in .env
    
    Examples:
        anthropic/claude-sonnet-4-5   ← current
        gpt-4o                         ← OpenAI swap
        gemini/gemini-pro              ← Google swap
        ollama/mistral                 ← local swap
    """

    def __init__(self):
        self.model = settings.litellm_model
        self.max_tokens = settings.llm_max_tokens
        self.temperature = settings.llm_temperature

    @retry(
        stop=stop_after_attempt(settings.agent_max_retries),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(Exception),
        reraise=True
    )
    async def complete(
        self,
        prompt: str,
        system: str,
        temperature: float | None = None,
    ) -> str:
        """
        Basic completion — returns raw text.
        Use for free-form outputs like email drafts.
        """
        try:
            response = await acompletion(
                model=self.model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=self.max_tokens,
                temperature=temperature or self.temperature,
            )

            result = response.choices[0].message.content
            logger.debug(f"LLM complete() — model={self.model} tokens={response.usage.total_tokens}")
            return result

        except Exception as e:
            logger.error(f"LLM complete() failed: {e}")
            raise

    @retry(
        stop=stop_after_attempt(settings.agent_max_retries),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(Exception),
        reraise=True
    )
    async def complete_json(
        self,
        prompt: str,
        system: str,
        temperature: float | None = None,
    ) -> dict[str, Any]:
        """
        Structured completion — returns parsed JSON dict.
        Use for scoring agent, values agent outputs.
        Forces the model to return valid JSON every time.
        """
        # Append JSON instruction to system prompt
        json_system = system + """

CRITICAL INSTRUCTION:
You must respond with ONLY valid JSON.
No markdown, no backticks, no explanation before or after.
Your entire response must be parseable by json.loads().
"""
        try:
            response = await acompletion(
                model=self.model,
                messages=[
                    {"role": "system", "content": json_system},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=self.max_tokens,
                temperature=temperature or self.temperature,
            )

            raw = response.choices[0].message.content.strip()

            # Strip markdown fences if model ignores instructions
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
                raw = raw.strip()

            parsed = json.loads(raw)
            logger.debug(f"LLM complete_json() — model={self.model} tokens={response.usage.total_tokens}")
            return parsed

        except json.JSONDecodeError as e:
            logger.error(f"LLM returned invalid JSON: {e}\nRaw: {raw}")
            raise
        except Exception as e:
            logger.error(f"LLM complete_json() failed: {e}")
            raise


# ─── Singleton ─────────────────────────────────────────────────
# One instance shared across the entire app.
# Import this anywhere you need LLM access.
llm_service = LLMService()