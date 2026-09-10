"""
Unit tests for TASK-21: Evidence Gate (LLM Call 3).

Tests 4-way routing decision classification (ANSWER, GENERALIZE, ABSTAIN, ESCALATE),
XML prompt isolation, Top-5 chunk truncation, schema validation, and deterministic zero-temperature parameters.
"""
from unittest.mock import AsyncMock, MagicMock
import pytest
from pydantic import ValidationError

from medbridge.ai.evidence_gate import (
    SYSTEM_PROMPT,
    EvidenceGate,
    _build_user_prompt,
    _format_chunks,
    get_evidence_gate,
)
from medbridge.ai.schemas.evidence_gate import EvidenceGateOutput
from medbridge.retrieval.hybrid_retriever import RetrievedChunk


# ---------------------------------------------------------------------------
# Prompt formatting & XML isolation (ADL-018, ADL-025, Constitution §7.1)
# ---------------------------------------------------------------------------

class TestEvidenceGatePromptFormatting:
    """Ensure patient input is strictly encapsulated within XML boundary tags and chunks are formatted."""

    def test_xml_isolation_tags_present(self) -> None:
        query = "Can I take ibuprofen with lisinopril?"
        snapshot = {"current_medications": [{"drug": "lisinopril", "dosage": "10mg"}]}
        chunks = [
            RetrievedChunk(
                chunk_id="chunk_1",
                chunk_text="NSAIDs like ibuprofen may attenuate the antihypertensive effect of ACE inhibitors.",
                guideline_id="AHA_ACC_2025",
                section_title="Drug Interactions",
                page_number=35,
                source_url="https://guidelines.acc.org/htn2025",
                score=0.9,
            )
        ]

        prompt = _build_user_prompt(chunks, snapshot, query)

        # Non-negotiable #5: Untrusted input tag wrapping
        assert "<untrusted_user_input>" in prompt
        assert "</untrusted_user_input>" in prompt
        start_tag = prompt.find("<untrusted_user_input>")
        end_tag = prompt.find("</untrusted_user_input>")
        assert start_tag < prompt.find(query) < end_tag

        # Patient context XML wrapper
        assert "<patient_context>" in prompt
        assert "</patient_context>" in prompt
        assert '"lisinopril"' in prompt

        # Clinical evidence XML wrapper
        assert "<clinical_evidence>" in prompt
        assert "</clinical_evidence>" in prompt
        assert '<chunk id="chunk_1" source="AHA_ACC_2025" section="Drug Interactions">' in prompt
        assert "NSAIDs like ibuprofen" in prompt

    def test_top_5_chunk_truncation(self) -> None:
        """Verify that at most Top-5 chunks are included even if more are passed."""
        chunks = [
            RetrievedChunk(
                chunk_id=f"chunk_{i}",
                chunk_text=f"Evidence text number {i}",
                guideline_id="GUIDELINE",
                section_title="Section",
                page_number=i,
                source_url="",
                score=1.0 - (i * 0.1),
            )
            for i in range(1, 9)  # 8 chunks
        ]
        prompt = _build_user_prompt(chunks, {}, "query")

        # Top-5 should be present
        for i in range(1, 6):
            assert f'chunk id="chunk_{i}"' in prompt
            assert f"Evidence text number {i}" in prompt

        # Chunks 6, 7, 8 must be omitted
        for i in range(6, 9):
            assert f'chunk id="chunk_{i}"' not in prompt
            assert f"Evidence text number {i}" not in prompt

    def test_empty_chunks_handling(self) -> None:
        prompt = _build_user_prompt([], {}, "query")
        assert "No clinical evidence available." in prompt

    def test_format_chunks_with_dicts_tuples_and_strings(self) -> None:
        chunks = [
            {"chunk_id": "c_dict", "guideline_id": "ACC", "section_title": "SecA", "chunk_text": "Dict chunk text"},
            ("Tuple chunk text", 0.85),
            "Raw string chunk text",
        ]
        formatted = _format_chunks(chunks)
        assert 'chunk id="c_dict"' in formatted
        assert "Dict chunk text" in formatted
        assert "Tuple chunk text" in formatted
        assert "Raw string chunk text" in formatted


# ---------------------------------------------------------------------------
# Schema validation
# ---------------------------------------------------------------------------

class TestEvidenceGateOutputSchema:
    """Test validation of EvidenceGateOutput Pydantic schema."""

    def test_valid_answer_schema(self) -> None:
        output = EvidenceGateOutput(
            action="ANSWER",
            evidence_sufficient=True,
            rationale="Retrieved guidelines directly address patient's medication inquiry.",
        )
        assert output.action == "ANSWER"
        assert output.evidence_sufficient is True

    def test_valid_generalize_schema(self) -> None:
        output = EvidenceGateOutput(
            action="GENERALIZE",
            evidence_sufficient=False,
            rationale="Evidence covers hypertension treatment generally but not this specific drug combination.",
        )
        assert output.action == "GENERALIZE"
        assert output.evidence_sufficient is False

    def test_valid_abstain_schema(self) -> None:
        output = EvidenceGateOutput(
            action="ABSTAIN",
            evidence_sufficient=False,
            rationale="Query regarding pediatric oncology is outside cardiovascular knowledge base domain.",
        )
        assert output.action == "ABSTAIN"
        assert output.evidence_sufficient is False

    def test_valid_escalate_schema(self) -> None:
        output = EvidenceGateOutput(
            action="ESCALATE",
            evidence_sufficient=False,
            rationale="Symptoms of acute chest pain and hypertensive emergency mandate emergency department care.",
        )
        assert output.action == "ESCALATE"

    def test_invalid_action_rejected(self) -> None:
        with pytest.raises(ValidationError):
            EvidenceGateOutput.model_validate({
                "action": "SOFT-ASK",  # SOFT-ASK is Context Gate only, not Evidence Gate
                "evidence_sufficient": True,
                "rationale": "Invalid action for evidence gate",
            })

        with pytest.raises(ValidationError):
            EvidenceGateOutput.model_validate({
                "action": "PROCEED",  # PROCEED is Context Gate only
                "evidence_sufficient": True,
                "rationale": "Invalid action for evidence gate",
            })


# ---------------------------------------------------------------------------
# Clinical Vignettes & Routing Evaluation (ADL-024)
# ---------------------------------------------------------------------------

class TestEvidenceGateEvaluation:
    """Test evaluation logic across standard clinical routing vignettes."""

    @pytest.mark.asyncio
    async def test_evaluate_answer_vignette(self) -> None:
        """Vignette 1: Evidence directly matches patient clinical parameters -> ANSWER."""
        mock_llm = MagicMock()
        expected = EvidenceGateOutput(
            action="ANSWER",
            evidence_sufficient=True,
            rationale="AHA/ACC 2025 guidelines directly specify thiazide diuretics as first-line for Stage 1 HTN.",
        )
        mock_llm.call = AsyncMock(return_value=expected)

        gate = EvidenceGate(llm=mock_llm)
        snapshot = {
            "demographics": {"age": 58, "race_ethnicity": "non-black"},
            "diagnoses": ["Stage 1 Hypertension"],
            "recent_bp_readings": [{"systolic": 142, "diastolic": 92}],
        }
        chunks = [
            RetrievedChunk(
                chunk_id="aha_2025_s1",
                chunk_text="First-line therapy for Stage 1 hypertension in non-black patients includes thiazide diuretics, CCBs, and ACE inhibitors.",
                guideline_id="AHA_ACC_2025",
                section_title="First-Line Therapy",
                page_number=24,
                source_url="https://guidelines.acc.org/htn2025",
                score=0.95,
            )
        ]

        result = await gate.evaluate(
            chunks=chunks,
            snapshot=snapshot,
            query="What is the recommended first-line medication for my Stage 1 high blood pressure?",
        )

        assert result == expected
        assert result.action == "ANSWER"
        assert result.evidence_sufficient is True

        mock_llm.call.assert_called_once()
        call_kwargs = mock_llm.call.call_args.kwargs
        assert call_kwargs["call_name"] == "evidence_gate"
        assert call_kwargs["system_prompt"] == SYSTEM_PROMPT
        assert call_kwargs["output_schema"] == EvidenceGateOutput
        assert call_kwargs["temperature"] == 0.0  # Deterministic gate inference (ADL-026)
        assert call_kwargs["max_tokens"] == 512

    @pytest.mark.asyncio
    async def test_evaluate_generalize_vignette(self) -> None:
        """Vignette 2: Evidence covers general topic but lacks specific scenario detail -> GENERALIZE."""
        mock_llm = MagicMock()
        expected = EvidenceGateOutput(
            action="GENERALIZE",
            evidence_sufficient=False,
            rationale="Guideline covers amlodipine dosing generally, but contains no evidence on interactions with St. John's Wort.",
        )
        mock_llm.call = AsyncMock(return_value=expected)

        gate = EvidenceGate(llm=mock_llm)
        snapshot = {
            "current_medications": [{"drug": "amlodipine", "dosage": "5mg"}],
        }
        chunks = [
            RetrievedChunk(
                chunk_id="aha_2025_ccb",
                chunk_text="Amlodipine is a dihydropyridine calcium channel blocker administered 2.5mg to 10mg once daily.",
                guideline_id="AHA_ACC_2025",
                section_title="Dihydropyridine CCBs",
                page_number=30,
                source_url="https://guidelines.acc.org/htn2025",
                score=0.72,
            )
        ]

        result = await gate.evaluate(
            chunks=chunks,
            snapshot=snapshot,
            query="Can I safely take my amlodipine with St. John's Wort herbal supplement?",
        )

        assert result == expected
        assert result.action == "GENERALIZE"
        assert result.evidence_sufficient is False

    @pytest.mark.asyncio
    async def test_evaluate_abstain_vignette(self) -> None:
        """Vignette 3: Query is outside knowledge base domain (e.g. pediatric oncology) -> ABSTAIN."""
        mock_llm = MagicMock()
        expected = EvidenceGateOutput(
            action="ABSTAIN",
            evidence_sufficient=False,
            rationale="Query regarding pediatric oncology protocols is outside the adult cardiovascular guideline knowledge base.",
        )
        mock_llm.call = AsyncMock(return_value=expected)

        gate = EvidenceGate(llm=mock_llm)
        chunks = [
            RetrievedChunk(
                chunk_id="aha_2025_s1",
                chunk_text="Adult hypertension diagnostic thresholds and pharmacotherapy.",
                guideline_id="AHA_ACC_2025",
                section_title="Adult HTN",
                page_number=1,
                source_url="",
                score=0.2,
            )
        ]

        result = await gate.evaluate(
            chunks=chunks,
            snapshot={},
            query="What chemotherapy protocol is recommended for pediatric neuroblastoma?",
        )

        assert result == expected
        assert result.action == "ABSTAIN"
        assert result.evidence_sufficient is False

    @pytest.mark.asyncio
    async def test_evaluate_escalate_vignette(self) -> None:
        """Vignette 4: Patient exhibits acute clinical danger / hypertensive emergency -> ESCALATE."""
        mock_llm = MagicMock()
        expected = EvidenceGateOutput(
            action="ESCALATE",
            evidence_sufficient=False,
            rationale="Blood pressure 210/125 with acute severe chest pain and dyspnea represents a hypertensive emergency.",
        )
        mock_llm.call = AsyncMock(return_value=expected)

        gate = EvidenceGate(llm=mock_llm)
        snapshot = {
            "recent_bp_readings": [{"systolic": 210, "diastolic": 125}],
        }
        chunks = [
            RetrievedChunk(
                chunk_id="aha_2025_emergencies",
                chunk_text="Hypertensive emergencies are defined as severe elevations in BP (>180/120 mm Hg) associated with evidence of new or worsening target organ damage.",
                guideline_id="AHA_ACC_2025",
                section_title="Hypertensive Crises and Emergencies",
                page_number=55,
                source_url="https://guidelines.acc.org/htn2025",
                score=0.98,
            )
        ]

        result = await gate.evaluate(
            chunks=chunks,
            snapshot=snapshot,
            query="My BP is 210/125 and I have crushing chest pain radiating to my arm. What pill should I take?",
        )

        assert result == expected
        assert result.action == "ESCALATE"

    @pytest.mark.asyncio
    async def test_evaluate_returns_none_on_permanent_failure(self) -> None:
        """When LLM call permanently fails, evaluate() logs error and returns None."""
        mock_llm = MagicMock()
        mock_llm.call = AsyncMock(return_value=None)

        gate = EvidenceGate(llm=mock_llm)
        result = await gate.evaluate(
            chunks=[],
            snapshot={},
            query="General question",
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_message_alias_supported(self) -> None:
        """Verify keyword argument `message` works as an alias for `query`."""
        mock_llm = MagicMock()
        mock_llm.call = AsyncMock(return_value=EvidenceGateOutput(
            action="ANSWER",
            evidence_sufficient=True,
            rationale="Direct match",
        ))

        gate = EvidenceGate(llm=mock_llm)
        result = await gate.evaluate(
            chunks=[],
            snapshot={},
            message="Alternative kwarg parameter",
        )

        assert result is not None
        assert result.action == "ANSWER"

    def test_factory_function(self) -> None:
        gate = get_evidence_gate()
        assert isinstance(gate, EvidenceGate)
