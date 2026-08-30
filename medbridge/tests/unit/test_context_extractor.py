"""
Unit tests for TASK-18: Context Extractor (LLM Call 1).

Tests XML-tag isolation for prompt injection mitigation,
prompt formatting, and parsing of structured delta events.
"""
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from medbridge.ai.context_extractor import (
    SYSTEM_PROMPT,
    ContextExtractor,
    _build_user_prompt,
)
from medbridge.ai.schemas.extractor import ExtractorOutput


# ---------------------------------------------------------------------------
# Prompt formatting & XML isolation (ADL-018)
# ---------------------------------------------------------------------------

class TestPromptFormatting:
    """Ensure patient input is strictly encapsulated in XML tags."""

    def test_xml_isolation_tags_present(self) -> None:
        message = "I started taking lisinopril 10mg."
        snapshot = {"current_medications": []}

        prompt = _build_user_prompt(message, snapshot)

        # ADL-018: Untrusted user input must be isolated
        assert "<untrusted_user_input>" in prompt
        assert "</untrusted_user_input>" in prompt
        
        # Message must be between tags
        start_tag = prompt.find("<untrusted_user_input>")
        end_tag = prompt.find("</untrusted_user_input>")
        assert start_tag < prompt.find(message) < end_tag

    def test_snapshot_formatting(self) -> None:
        message = "test"
        snapshot = {"demographics": {"age": 55}}

        prompt = _build_user_prompt(message, snapshot)

        # Snapshot should be JSON formatted
        assert '"age": 55' in prompt


# ---------------------------------------------------------------------------
# Extraction logic
# ---------------------------------------------------------------------------

class TestContextExtractor:
    """Test extractor logic wrapping ResilientLLMWrapper."""

    @pytest.mark.asyncio
    async def test_extract_returns_parsed_output(self) -> None:
        mock_llm = MagicMock()
        
        expected_output = ExtractorOutput(
            delta_events=[],
            search_query="hypertension guidelines",
            raw_intent="patient wants to know about guidelines",
        )
        mock_llm.call = AsyncMock(return_value=expected_output)

        extractor = ContextExtractor(llm=mock_llm)
        result = await extractor.extract("hello", {})

        assert result == expected_output
        
        # Verify the wrapper was called with correct deterministic params
        mock_llm.call.assert_called_once()
        call_kwargs = mock_llm.call.call_args.kwargs
        assert call_kwargs["call_name"] == "context_extractor"
        assert call_kwargs["system_prompt"] == SYSTEM_PROMPT
        assert call_kwargs["output_schema"] == ExtractorOutput
        assert call_kwargs["temperature"] == 0.0

    @pytest.mark.asyncio
    async def test_extract_returns_none_on_failure(self) -> None:
        mock_llm = MagicMock()
        mock_llm.call = AsyncMock(return_value=None)

        extractor = ContextExtractor(llm=mock_llm)
        result = await extractor.extract("hello", {})

        assert result is None
