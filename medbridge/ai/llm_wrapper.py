"""
Resilient LLM Wrapper (ADL-004).

Wraps all LLM inference calls with:
- Async HTTP requests to Groq Cloud API (primary) with optional OpenAI failover
- Markdown code-block extraction (```json → raw JSON)
- Common malformed-JSON repair (trailing commas, unclosed brackets)
- Exponential-backoff retry (configurable, default 3 attempts)
- Pydantic schema validation — returns validated model or ``None``

Technical Specification Part III §3.9.
"""
import asyncio
import json
import logging
import re
from typing import Optional, TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from medbridge.config import get_settings

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

# Groq and OpenAI share the same chat-completions API shape
_GROQ_BASE_URL = "https://api.groq.com/openai/v1"
_OPENAI_BASE_URL = "https://api.openai.com/v1"


class ResilientLLMWrapper:
    """Wraps all LLM calls with retry, JSON repair, and deterministic fallback.

    On permanent failure (all retries exhausted across all providers),
    returns ``None``.  The orchestrator must then apply the deterministic
    fallback logic specified in §3.9.
    """

    def __init__(self) -> None:
        settings = get_settings()
        self.model: str = settings.LLM_MODEL
        self.max_retries: int = settings.LLM_MAX_RETRIES
        self.retry_base_delay: float = settings.LLM_RETRY_BASE_DELAY
        self.seed: int = settings.LLM_SEED

        # Build provider list: Groq primary, OpenAI fallback
        self._providers: list[dict[str, str]] = [
            {"name": "groq", "base_url": _GROQ_BASE_URL, "api_key": settings.GROQ_API_KEY},
        ]
        if settings.OPENAI_API_KEY:
            self._providers.append(
                {"name": "openai", "base_url": _OPENAI_BASE_URL, "api_key": settings.OPENAI_API_KEY}
            )

    async def call(
        self,
        call_name: str,
        system_prompt: str,
        user_prompt: str,
        output_schema: type[T],
        temperature: float = 0.0,
        max_tokens: int = 512,
    ) -> Optional[T]:
        """Execute an LLM call with retry, JSON repair, and provider failover.

        Args:
            call_name: Human-readable label for logging (e.g. "context_extractor").
            system_prompt: The system prompt for the LLM.
            user_prompt: The user prompt / input.
            output_schema: Pydantic model class to validate the response against.
            temperature: Sampling temperature (0.0 for deterministic gates).
            max_tokens: Maximum tokens in the response.

        Returns:
            A validated Pydantic model instance, or ``None`` on permanent failure.
        """
        for provider in self._providers:
            result = await self._call_provider(
                provider=provider,
                call_name=call_name,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                output_schema=output_schema,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            if result is not None:
                return result

            logger.warning(
                "Provider exhausted, trying next",
                extra={"call": call_name, "provider": provider["name"]},
            )

        # All providers exhausted
        logger.error(
            "LLM permanent failure — all providers exhausted",
            extra={"call": call_name},
        )
        return None

    # ------------------------------------------------------------------
    # Provider-level retry loop
    # ------------------------------------------------------------------

    async def _call_provider(
        self,
        provider: dict[str, str],
        call_name: str,
        system_prompt: str,
        user_prompt: str,
        output_schema: type[T],
        temperature: float,
        max_tokens: int,
    ) -> Optional[T]:
        """Attempt up to ``max_retries`` calls against a single provider."""
        for attempt in range(1, self.max_retries + 1):
            try:
                raw_response = await self._call_llm_api(
                    provider=provider,
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )

                json_str = self._extract_json(raw_response)

                # On retries, apply JSON repair before parsing
                if attempt > 1:
                    json_str = self._repair_json(json_str)

                parsed = output_schema.model_validate_json(json_str)
                return parsed

            except (json.JSONDecodeError, ValidationError) as e:
                logger.warning(
                    "LLM parse failure",
                    extra={
                        "call": call_name,
                        "provider": provider["name"],
                        "attempt": attempt,
                        "error": str(e),
                    },
                )
                if attempt < self.max_retries:
                    await asyncio.sleep(
                        self.retry_base_delay * (2 ** (attempt - 1))
                    )
                continue

            except httpx.TimeoutException:
                logger.error(
                    "LLM timeout",
                    extra={
                        "call": call_name,
                        "provider": provider["name"],
                        "attempt": attempt,
                    },
                )
                if attempt < self.max_retries:
                    await asyncio.sleep(
                        self.retry_base_delay * (2 ** (attempt - 1))
                    )
                continue

            except httpx.HTTPStatusError as e:
                status = e.response.status_code
                logger.error(
                    "LLM HTTP error",
                    extra={
                        "call": call_name,
                        "provider": provider["name"],
                        "attempt": attempt,
                        "status": status,
                    },
                )
                # 5xx → retry; 4xx (except 429) → don't retry
                if status == 429 or status >= 500:
                    if attempt < self.max_retries:
                        # Respect Retry-After header if present
                        retry_after = e.response.headers.get("Retry-After")
                        delay = (
                            float(retry_after)
                            if retry_after
                            else self.retry_base_delay * (2 ** (attempt - 1))
                        )
                        await asyncio.sleep(delay)
                    continue
                else:
                    # Non-retryable client error — break to next provider
                    break

        return None

    # ------------------------------------------------------------------
    # HTTP call
    # ------------------------------------------------------------------

    async def _call_llm_api(
        self,
        provider: dict[str, str],
        system_prompt: str,
        user_prompt: str,
        temperature: float,
        max_tokens: int,
    ) -> str:
        """Send a chat-completions request and return the raw content string."""
        payload: dict = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "response_format": {"type": "json_object"},
        }

        # Add seed for deterministic gates (temperature == 0.0)
        if temperature == 0.0:
            payload["seed"] = self.seed

        headers = {
            "Authorization": f"Bearer {provider['api_key']}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{provider['base_url']}/chat/completions",
                json=payload,
                headers=headers,
            )
            response.raise_for_status()

        data = response.json()
        return data["choices"][0]["message"]["content"]

    # ------------------------------------------------------------------
    # JSON extraction & repair
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_json(raw: str) -> str:
        """Extract JSON from markdown code blocks if present.

        Handles:
        - ```json ... ```
        - ``` ... ```
        - Raw JSON (no code block)
        """
        # Match ```json ... ``` or ``` ... ```
        match = re.search(
            r"```(?:json)?\s*\n?(.*?)\n?\s*```",
            raw,
            re.DOTALL,
        )
        if match:
            return match.group(1).strip()

        # No code block — return trimmed raw
        return raw.strip()

    @staticmethod
    def _repair_json(json_str: str) -> str:
        """Attempt to repair common malformed JSON patterns.

        Fixes:
        - Trailing commas before } or ]
        - Trailing comma at end of string
        - Unclosed brackets/braces (appends missing closers)
        - Single quotes → double quotes
        """
        # Replace single quotes with double quotes (common LLM mistake)
        repaired = json_str.replace("'", '"')

        # Remove trailing commas: ,} or ,]
        repaired = re.sub(r",\s*([}\]])", r"\1", repaired)

        # Remove trailing comma at end of string (before we add closers)
        repaired = re.sub(r",\s*$", "", repaired)

        # Count unmatched brackets and auto-close (inner-to-outer)
        open_brackets = repaired.count("[") - repaired.count("]")
        open_braces = repaired.count("{") - repaired.count("}")

        if open_brackets > 0:
            repaired += "]" * open_brackets
        if open_braces > 0:
            repaired += "}" * open_braces

        return repaired
