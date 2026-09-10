"""
Unit tests for TASK-19: Context Gate (LLM Call 2).

Tests binary sufficiency classification (SOFT-ASK vs PROCEED),
XML prompt isolation, schema validation, and deterministic zero-temperature parameters.
"""
from unittest.mock import AsyncMock, MagicMock
import pytest
from pydantic import ValidationError

from medbridge.ai.context_gate import (
    SYSTEM_PROMPT,
    ContextGate,
    _build_user_prompt,
)
from medbridge.ai.schemas.context_gate import ContextGateOutput


# ---------------------------------------------------------------------------
# Prompt formatting & XML isolation (ADL-018, Constitution §7.1)
# ---------------------------------------------------------------------------

class TestContextGatePromptFormatting:
    """Ensure patient input is strictly encapsulated within XML boundary tags."""

    def test_xml_isolation_tags_present(self) -> None:
        message = "Can I take ibuprofen for headache with my BP?"
        snapshot = {"current_medications": [{"drug": "amlodipine", "dosage": "5mg"}]}
        raw_intent = "drug interaction between ibuprofen and amlodipine"

        prompt = _build_user_prompt(snapshot, message, raw_intent)

        assert "<untrusted_user_input>" in prompt
        assert "</untrusted_user_input>" in prompt
        start_tag = prompt.find("<untrusted_user_input>")
        end_tag = prompt.find("</untrusted_user_input>")
        assert start_tag < prompt.find(message) < end_tag

    def test_snapshot_formatted_as_json(self) -> None:
        snapshot = {"demographics": {"age": 62, "sex": "female"}}
        prompt = _build_user_prompt(snapshot, "message", "intent")

        assert '"age": 62' in prompt
        assert '"sex": "female"' in prompt

    def test_question_intent_included(self) -> None:
        raw_intent = "evaluate if blood pressure of 145/92 is controlled"
        prompt = _build_user_prompt({}, "my bp is 145/92", raw_intent)

        assert raw_intent in prompt


# ---------------------------------------------------------------------------
# Schema validation
# ---------------------------------------------------------------------------

class TestContextGateOutputSchema:
    """Test validation of ContextGateOutput Pydantic schema."""

    def test_valid_proceed_schema(self) -> None:
        output = ContextGateOutput(
            action="PROCEED",
            missing_fields=[],
            rationale="All relevant clinical parameters present.",
        )
        assert output.action == "PROCEED"
        assert output.missing_fields == []
        assert "relevant clinical parameters" in output.rationale

    def test_valid_soft_ask_schema(self) -> None:
        output = ContextGateOutput(
            action="SOFT-ASK",
            missing_fields=["age", "current_medications"],
            rationale="Patient age and current medications required.",
        )
        assert output.action == "SOFT-ASK"
        assert len(output.missing_fields) == 2

    def test_default_missing_fields_empty(self) -> None:
        output = ContextGateOutput(
            action="PROCEED",
            rationale="Sufficient context.",
        )
        assert output.missing_fields == []

    def test_invalid_action_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ContextGateOutput.model_validate({
                "action": "ANSWER",  # Only SOFT-ASK or PROCEED allowed
                "missing_fields": [],
                "rationale": "Invalid action for gate 1",
            })


# ---------------------------------------------------------------------------
# Context Gate evaluation logic (TASK-19 Acceptance Criteria)
# ---------------------------------------------------------------------------

class TestContextGateEvaluation:
    """Test evaluation logic wrapping ResilientLLMWrapper."""

    @pytest.mark.asyncio
    async def test_evaluate_proceed_when_sufficient(self) -> None:
        mock_llm = MagicMock()
        expected = ContextGateOutput(
            action="PROCEED",
            missing_fields=[],
            rationale="Patient age, current medications, and recent BP readings are present.",
        )
        mock_llm.call = AsyncMock(return_value=expected)

        gate = ContextGate(llm=mock_llm)
        snapshot = {
            "demographics": {"age": 58},
            "current_medications": [{"drug": "amlodipine", "dosage": "5mg"}],
            "recent_bp_readings": [{"systolic": 138, "diastolic": 86}],
        }
        result = await gate.evaluate(
            snapshot=snapshot,
            message="Is 138/86 a safe reading on amlodipine?",
            raw_intent="blood pressure control evaluation",
        )

        assert result == expected
        assert result.action == "PROCEED"

        mock_llm.call.assert_called_once()
        call_kwargs = mock_llm.call.call_args.kwargs
        assert call_kwargs["call_name"] == "context_gate"
        assert call_kwargs["system_prompt"] == SYSTEM_PROMPT
        assert call_kwargs["output_schema"] == ContextGateOutput
        assert call_kwargs["temperature"] == 0.0  # NON-NEGOTIABLE #3

    @pytest.mark.asyncio
    async def test_evaluate_soft_ask_when_missing_context(self) -> None:
        mock_llm = MagicMock()
        expected = ContextGateOutput(
            action="SOFT-ASK",
            missing_fields=["age", "current_medications"],
            rationale="Cannot evaluate treatment goals without patient age and current medications.",
        )
        mock_llm.call = AsyncMock(return_value=expected)

        gate = ContextGate(llm=mock_llm)
        result = await gate.evaluate(
            snapshot={},
            message="What should my target BP be?",
            raw_intent="blood pressure target inquiry",
        )

        assert result == expected
        assert result.action == "SOFT-ASK"
        assert "age" in result.missing_fields

    @pytest.mark.asyncio
    async def test_evaluate_returns_none_on_permanent_failure(self) -> None:
        mock_llm = MagicMock()
        mock_llm.call = AsyncMock(return_value=None)

        gate = ContextGate(llm=mock_llm)
        result = await gate.evaluate(
            snapshot={},
            message="What is hypertension?",
            raw_intent="definition inquiry",
        )

        assert result is None
