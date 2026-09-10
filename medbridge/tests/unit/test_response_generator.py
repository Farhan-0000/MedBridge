"""
Unit tests for TASK-22: Response Generator (LLM Call 4).

Tests XML prompt isolation, citation parsing, action bypassing (bypassed for ABSTAIN/ESCALATE,
invoked for ANSWER/GENERALIZE/SOFT-ASK), and temperature 0.3 configuration.
"""
from unittest.mock import AsyncMock, MagicMock
import pytest
from pydantic import ValidationError

from medbridge.ai.response_generator import (
    ALLOWED_ACTIONS,
    BYPASS_ACTIONS,
    ResponseGenerator,
    _build_system_prompt,
    _build_user_prompt,
    _format_chunks,
    build_full_prompt,
    get_response_generator,
)
from medbridge.ai.schemas.response_generator import (
    GeneratedCitation,
    ResponseGeneratorOutput,
)
from medbridge.api.schemas.enums import ActionEnum
from medbridge.retrieval.hybrid_retriever import RetrievedChunk


# ---------------------------------------------------------------------------
# Prompt formatting & XML isolation (ADL-018, ADL-025, Constitution §7.1)
# ---------------------------------------------------------------------------

class TestResponseGeneratorPromptConstruction:
    """Verify XML prompt construction across all 4 mandatory tags."""

    def test_all_xml_tags_present_in_full_prompt(self) -> None:
        query = "What is the recommended medication for high blood pressure?"
        snapshot = {"demographics": {"age": 55}, "diagnoses": ["Hypertension"]}
        chunks = [
            RetrievedChunk(
                chunk_id="chunk_101",
                chunk_text="First-line pharmacotherapy includes thiazide diuretics, CCBs, and ACE inhibitors.",
                guideline_id="AHA_ACC_2025",
                section_title="First-Line Therapy",
                page_number=18,
                source_url="https://guidelines.acc.org/htn2025",
                score=0.92,
            )
        ]

        full_prompt = build_full_prompt(ActionEnum.ANSWER, chunks, snapshot, query)

        # 1. <system_instructions>
        assert "<system_instructions>" in full_prompt
        assert "</system_instructions>" in full_prompt
        assert "Follow\nthe routing action: ANSWER." in full_prompt

        # 2. <patient_context>
        assert "<patient_context>" in full_prompt
        assert "</patient_context>" in full_prompt
        assert '"age": 55' in full_prompt
        assert '"Hypertension"' in full_prompt

        # 3. <clinical_evidence>
        assert "<clinical_evidence>" in full_prompt
        assert "</clinical_evidence>" in full_prompt
        assert '<chunk id="chunk_101" source="AHA_ACC_2025" section="First-Line Therapy">' in full_prompt
        assert "First-line pharmacotherapy includes thiazide diuretics" in full_prompt

        # 4. <user_query> with <untrusted_user_input>
        assert "<user_query>" in full_prompt
        assert "</user_query>" in full_prompt
        assert "<untrusted_user_input>" in full_prompt
        assert "</untrusted_user_input>" in full_prompt
        start_tag = full_prompt.find("<untrusted_user_input>")
        end_tag = full_prompt.find("</untrusted_user_input>")
        assert start_tag < full_prompt.find(query) < end_tag

    def test_system_prompt_action_interpolation(self) -> None:
        for action in ["ANSWER", "GENERALIZE", "SOFT-ASK"]:
            sys_prompt = _build_system_prompt(action)
            assert f"the routing action: {action}." in sys_prompt
            assert "<system_instructions>" in sys_prompt
            assert "</system_instructions>" in sys_prompt

    def test_top_5_chunk_truncation(self) -> None:
        chunks = [
            RetrievedChunk(
                chunk_id=f"c_{i}",
                chunk_text=f"Clinical text snippet {i}",
                guideline_id="AHA",
                section_title="Treatment",
                page_number=i,
                source_url="",
                score=1.0 - (i * 0.05),
            )
            for i in range(1, 8)  # 7 chunks
        ]
        prompt = _build_user_prompt(chunks, {}, "query")

        # Top 5 chunks must be in prompt
        for i in range(1, 6):
            assert f'chunk id="c_{i}"' in prompt
            assert f"Clinical text snippet {i}" in prompt

        # Chunks 6 and 7 must be omitted
        assert 'chunk id="c_6"' not in prompt
        assert 'chunk id="c_7"' not in prompt

    def test_empty_chunks_formatting(self) -> None:
        formatted = _format_chunks([])
        assert '<chunk id="0" source="None" section="None">' in formatted
        assert "No clinical evidence provided." in formatted

    def test_format_chunks_with_dicts_tuples_and_strings(self) -> None:
        chunks = [
            {"chunk_id": "dict_1", "guideline_id": "ACC", "section_title": "Sec1", "chunk_text": "Dict text"},
            ("Tuple text", 0.88),
            "Raw string text",
        ]
        formatted = _format_chunks(chunks)
        assert 'chunk id="dict_1" source="ACC" section="Sec1">' in formatted
        assert "Dict text" in formatted
        assert "Tuple text" in formatted
        assert "Raw string text" in formatted


# ---------------------------------------------------------------------------
# Action Bypassing (Acceptance Criteria: Bypassed for ABSTAIN / ESCALATE)
# ---------------------------------------------------------------------------

class TestResponseGeneratorActionBypassing:
    """Verify that ABSTAIN and ESCALATE actions bypass LLM Call 4 entirely."""

    @pytest.mark.asyncio
    async def test_bypasses_abstain_string_and_enum(self) -> None:
        mock_llm = MagicMock()
        generator = ResponseGenerator(llm=mock_llm)

        # String action
        res1 = await generator.generate(action="ABSTAIN", chunks=[], snapshot={}, query="query")
        assert res1 is None

        # Enum action
        res2 = await generator.generate(action=ActionEnum.ABSTAIN, chunks=[], snapshot={}, query="query")
        assert res2 is None

        # LLM must not have been called
        mock_llm.call.assert_not_called()

    @pytest.mark.asyncio
    async def test_bypasses_escalate_string_and_enum(self) -> None:
        mock_llm = MagicMock()
        generator = ResponseGenerator(llm=mock_llm)

        # String action
        res1 = await generator.generate(action="ESCALATE", chunks=[], snapshot={}, query="emergency")
        assert res1 is None

        # Enum action
        res2 = await generator.generate(action=ActionEnum.ESCALATE, chunks=[], snapshot={}, query="emergency")
        assert res2 is None

        mock_llm.call.assert_not_called()

    @pytest.mark.asyncio
    async def test_bypasses_invalid_action(self) -> None:
        mock_llm = MagicMock()
        generator = ResponseGenerator(llm=mock_llm)

        res = await generator.generate(action="INVALID_UNKNOWN_ACTION", chunks=[], snapshot={}, query="query")
        assert res is None
        mock_llm.call.assert_not_called()


# ---------------------------------------------------------------------------
# Invocation & Parameter Verification (ANSWER, GENERALIZE, SOFT-ASK, Temp 0.3)
# ---------------------------------------------------------------------------

class TestResponseGeneratorInvocation:
    """Verify LLM invocation for allowed actions and temperature 0.3 parameter."""

    @pytest.mark.asyncio
    async def test_invokes_for_answer_action(self) -> None:
        mock_llm = MagicMock()
        expected = ResponseGeneratorOutput(
            response_text="First-line medications for high blood pressure include thiazide diuretics [1].",
            citations=[
                GeneratedCitation(
                    marker="[1]",
                    chunk_id="aha_c1",
                    source="AHA_ACC_2025",
                    section="First-Line Therapy",
                    excerpt="First-line therapy includes thiazide diuretics.",
                )
            ],
        )
        mock_llm.call = AsyncMock(return_value=expected)

        generator = ResponseGenerator(llm=mock_llm)
        result = await generator.generate(
            action=ActionEnum.ANSWER,
            chunks=[],
            snapshot={"demographics": {"age": 60}},
            query="What meds for BP?",
        )

        assert result == expected
        assert "[1]" in result.response_text
        assert len(result.citations) == 1

        mock_llm.call.assert_called_once()
        call_kwargs = mock_llm.call.call_args.kwargs
        assert call_kwargs["call_name"] == "response_generator"
        assert call_kwargs["output_schema"] == ResponseGeneratorOutput
        assert call_kwargs["temperature"] == 0.3  # Acceptance Criteria: Temperature 0.3 for fluency
        assert call_kwargs["max_tokens"] == 1024

    @pytest.mark.asyncio
    async def test_invokes_for_generalize_action(self) -> None:
        mock_llm = MagicMock()
        expected = ResponseGeneratorOutput(
            response_text="In general, calcium channel blockers relax blood vessels [1].",
            citations=[
                GeneratedCitation(
                    marker="[1]",
                    chunk_id="aha_c2",
                    source="AHA_ACC_2025",
                    section="CCBs",
                    excerpt="CCBs relax blood vessels.",
                )
            ],
        )
        mock_llm.call = AsyncMock(return_value=expected)

        generator = ResponseGenerator(llm=mock_llm)
        result = await generator.generate(
            action="GENERALIZE",
            chunks=[],
            snapshot={},
            query="How does amlodipine work?",
        )

        assert result == expected
        mock_llm.call.assert_called_once()

    @pytest.mark.asyncio
    async def test_invokes_for_soft_ask_action(self) -> None:
        mock_llm = MagicMock()
        expected = ResponseGeneratorOutput(
            response_text="To give you the most accurate information about your blood pressure medication, could you let me know your age?",
            citations=[],
        )
        mock_llm.call = AsyncMock(return_value=expected)

        generator = ResponseGenerator(llm=mock_llm)
        # Verify both hyphen and enum work
        result1 = await generator.generate(
            action="SOFT-ASK",
            chunks=[],
            snapshot={},
            query="What should my BP be?",
        )
        assert result1 == expected

        result2 = await generator.generate(
            action=ActionEnum.SOFT_ASK,
            chunks=[],
            snapshot={},
            query="What should my BP be?",
        )
        assert result2 == expected

    @pytest.mark.asyncio
    async def test_permanent_llm_failure_returns_none(self) -> None:
        mock_llm = MagicMock()
        mock_llm.call = AsyncMock(return_value=None)

        generator = ResponseGenerator(llm=mock_llm)
        result = await generator.generate(
            action="ANSWER",
            chunks=[],
            snapshot={},
            query="Any query",
        )
        assert result is None


# ---------------------------------------------------------------------------
# Citation Parsing & Schema Validation
# ---------------------------------------------------------------------------

class TestCitationParsingAndSchema:
    """Verify validation and parsing of ResponseGeneratorOutput and GeneratedCitation."""

    def test_citation_parsing_and_model_fields(self) -> None:
        data = {
            "response_text": "Lifestyle modifications lower systolic BP by 4-5 mmHg [1]. First-line agents include CCBs [2].",
            "citations": [
                {
                    "marker": "[1]",
                    "chunk_id": "aha_lifestyle_c1",
                    "source": "AHA_ACC_2025",
                    "section": "Nonpharmacological Interventions",
                    "excerpt": "Lifestyle modifications reduce systolic BP by approximately 4-5 mm Hg.",
                },
                {
                    "marker": "[2]",
                    "chunk_id": "aha_pharm_c2",
                    "source": "AHA_ACC_2025",
                    "section": "First-Line Pharmacotherapy",
                    "excerpt": "Dihydropyridine CCBs are recommended first-line agents.",
                },
            ],
        }
        output = ResponseGeneratorOutput.model_validate(data)
        assert len(output.citations) == 2
        assert output.citations[0].marker == "[1]"
        assert output.citations[0].source == "AHA_ACC_2025"
        assert output.citations[1].marker == "[2]"
        assert output.citations[1].chunk_id == "aha_pharm_c2"

    def test_citations_default_to_empty_list(self) -> None:
        output = ResponseGeneratorOutput(response_text="General greeting without citations.")
        assert output.response_text == "General greeting without citations."
        assert output.citations == []

    def test_citation_optional_fields_fallback(self) -> None:
        cit = GeneratedCitation(marker="[1]")
        assert cit.marker == "[1]"
        assert cit.chunk_id == ""
        assert cit.source == ""
        assert cit.section == ""
        assert cit.excerpt == ""


# ---------------------------------------------------------------------------
# Factory Function
# ---------------------------------------------------------------------------

def test_factory_function() -> None:
    generator = get_response_generator()
    assert isinstance(generator, ResponseGenerator)
