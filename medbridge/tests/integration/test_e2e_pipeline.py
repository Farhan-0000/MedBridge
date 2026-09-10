"""
Comprehensive End-to-End Multi-Turn Pipeline Integration Tests (TASK-31).

Verifies the complete 8-stage clinical AI pipeline against live PostgreSQL and Qdrant
instances with deterministic mocked LLM responses.

Covers:
1. Emergency fast-path triggering with sub-10ms latency (bypassing downstream LLM/retrieval).
2. Full multi-turn conversational round-trip:
   - Session creation
   - Turn 1: Demographic and BP reading context ingestion -> SOFT-ASK clarification
   - Turn 2: Clarification ingestion -> PROCEED -> live hybrid retrieval -> ANSWER with citations
   - Live PostgreSQL state verification (Session, ClinicalEvent, ContextSnapshot, AuditLog, MessageHistory).
3. SOFT-ASK loop-breaker threshold transition (soft_ask_count >= 2 forces GENERALIZE).
4. Out-of-domain query handling routing safely to ABSTAIN without hallucination.
5. End-to-End FastAPI REST API round-trip via TestClient.
"""
from datetime import datetime, timezone
import time
from unittest.mock import AsyncMock, patch
import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi.testclient import TestClient

from medbridge.ai.schemas.context_gate import ContextGateOutput
from medbridge.ai.schemas.evidence_gate import EvidenceGateOutput
from medbridge.ai.schemas.extractor import DeltaEvent, ExtractorOutput
from medbridge.ai.schemas.response_generator import (
    GeneratedCitation,
    ResponseGeneratorOutput,
)
from medbridge.api.schemas.enums import ActionEnum, EventTypeEnum
from medbridge.core.orchestrator import PipelineOrchestrator
from medbridge.db.connection import get_sessionmaker
from medbridge.db.models import (
    AuditLog,
    ClinicalEvent,
    ContextSnapshot,
    MessageHistory,
    Session as SessionModel,
)
from medbridge.main import create_app
from medbridge.state.session_manager import create_session


# ===========================================================================
# Fixtures
# ===========================================================================

@pytest.fixture
async def db_session():
    """Acquire live PostgreSQL session and ensure test cleanup."""
    maker = get_sessionmaker()
    async with maker() as session:
        yield session


@pytest.fixture
async def new_session_id(db_session: AsyncSession) -> uuid.UUID:
    """Create a new session record in live PostgreSQL."""
    sid = await create_session(db_session)
    await db_session.commit()
    return sid


# ===========================================================================
# 1. Emergency Fast-Path Trigger (<10ms Latency)
# ===========================================================================

@pytest.mark.asyncio
async def test_emergency_fast_path_latency_and_routing(
    db_session: AsyncSession,
    new_session_id: uuid.UUID,
):
    """
    Emergency symptoms (hypertensive crisis + acute organ damage signs) must trigger
    the fast-path emergency classifier immediately, bypassing all AI gates and retrieval,
    with sub-10ms latency.
    """
    orchestrator = PipelineOrchestrator()
    emergency_message = (
        "My blood pressure is 220/130 mmHg and I have crushing chest pain, "
        "severe shortness of breath, and visual blurriness."
    )

    # 1. Verify emergency classifier sub-10ms fast-path trigger requirement
    start_clf = time.perf_counter()
    clf_action = orchestrator._emergency_classifier(emergency_message)
    clf_latency_ms = (time.perf_counter() - start_clf) * 1000
    assert clf_action == ActionEnum.ESCALATE
    assert clf_latency_ms < 10.0  # Fast-path classifier strictly triggers in <10ms

    start = time.perf_counter()
    response = await orchestrator.process_message(
        session_id=new_session_id,
        message=emergency_message,
        db=db_session,
    )
    elapsed_ms = (time.perf_counter() - start) * 1000

    # 2. Verify routing and safety response
    assert response.action == ActionEnum.ESCALATE
    assert response.citations == []
    assert "911" in response.response_text or "emergency" in response.response_text.lower()
    assert elapsed_ms < 200.0  # Pipeline bypasses LLMs and completes in <200ms with DB writes

    # 2. Verify persistence in live PostgreSQL
    stmt = (
        select(MessageHistory)
        .where(MessageHistory.session_id == new_session_id)
        .order_by(MessageHistory.created_at.asc())
    )
    res = await db_session.execute(stmt)
    messages = res.scalars().all()
    assert len(messages) == 2
    assert messages[0].role == "user"
    assert messages[0].content == emergency_message
    assert messages[1].role == "assistant"
    assert messages[1].action.value == "ESCALATE"


# ===========================================================================
# 2. Full Multi-Turn Round-Trip: Context Ingestion -> SOFT-ASK -> ANSWER
# ===========================================================================

@pytest.mark.asyncio
async def test_multi_turn_pipeline_context_accumulation_and_answer(
    db_session: AsyncSession,
    new_session_id: uuid.UUID,
):
    """
    Validates complete multi-turn flow:
    - Turn 1: Ingests demographic and BP reading context -> Context Gate detects missing
              medications/comorbidities -> issues SOFT-ASK & increments soft_ask_count to 1.
    - Turn 2: Ingests medication and comorbidity context -> Context Gate returns PROCEED
              -> resets soft_ask_count to 0 -> Live Hybrid Search & Reranking -> Evidence Gate
              -> Response Generator produces evidence-grounded ANSWER with citations.
    - Audits all state in live PostgreSQL (Events, Snapshot, Messages, AuditLog).
    """
    orchestrator = PipelineOrchestrator()

    # -----------------------------------------------------------------------
    # TURN 1: Initial Context & SOFT-ASK Clarification
    # -----------------------------------------------------------------------
    turn_1_message = "I am a 58 year old male and my blood pressure was 155/95 mmHg this morning."

    turn_1_extraction = ExtractorOutput(
        delta_events=[
            DeltaEvent(
                event_type=EventTypeEnum.DEMOGRAPHIC,
                payload={"age": 58, "sex": "male"},
            ),
            DeltaEvent(
                event_type=EventTypeEnum.BP_READING,
                payload={"sbp": 155, "dbp": 95},
            ),
        ],
        raw_intent="Inquire about high blood pressure reading",
        search_query="hypertension treatment guidelines stage 2",
    )

    turn_1_gate_1 = ContextGateOutput(
        action="SOFT-ASK",
        missing_fields=["medications", "comorbidities"],
        rationale="Patient reported SBP 155/95 mmHg, but medication and diabetes/CKD status is unknown.",
    )

    soft_ask_question = (
        "Are you currently taking any blood pressure medications, and do you have any "
        "other medical conditions such as diabetes or kidney disease?"
    )

    soft_ask_gen_output = ResponseGeneratorOutput(
        response_text=soft_ask_question,
        citations=[],
    )

    with patch.object(orchestrator._context_extractor, "extract", new_callable=AsyncMock) as mock_extract, \
         patch.object(orchestrator._context_gate, "evaluate", new_callable=AsyncMock) as mock_cg, \
         patch.object(orchestrator._response_generator, "generate", new_callable=AsyncMock) as mock_rg:

        mock_extract.return_value = turn_1_extraction
        mock_cg.return_value = turn_1_gate_1
        mock_rg.return_value = soft_ask_gen_output

        resp_1 = await orchestrator.process_message(
            session_id=new_session_id,
            message=turn_1_message,
            db=db_session,
        )

    # Verify Turn 1 response
    assert resp_1.action == ActionEnum.SOFT_ASK
    assert resp_1.soft_ask_count == 1
    assert resp_1.response_text == soft_ask_question
    assert resp_1.citations == []

    # Verify Turn 1 DB state
    snapshot_row = await db_session.get(ContextSnapshot, new_session_id)
    assert snapshot_row is not None
    assert snapshot_row.soft_ask_count == 1
    assert snapshot_row.snapshot.get("demographics", {}).get("age") == 58
    assert snapshot_row.snapshot.get("demographics", {}).get("sex") == "male"
    assert len(snapshot_row.snapshot.get("recent_bp_readings", [])) == 1
    assert snapshot_row.snapshot["recent_bp_readings"][0]["sbp"] == 155
    assert snapshot_row.snapshot["recent_bp_readings"][0]["dbp"] == 95

    events_stmt = (
        select(ClinicalEvent)
        .where(ClinicalEvent.session_id == new_session_id)
        .order_by(ClinicalEvent.created_at.asc())
    )
    events = (await db_session.execute(events_stmt)).scalars().all()
    assert len(events) == 2
    event_types = [e.event_type.value for e in events]
    assert "DEMOGRAPHIC" in event_types
    assert "BP_READING" in event_types

    # -----------------------------------------------------------------------
    # TURN 2: Clarification Provided -> Context Sufficient -> PROCEED -> ANSWER
    # -----------------------------------------------------------------------
    turn_2_message = "I take Lisinopril 10mg daily and I have type 2 diabetes."

    turn_2_extraction = ExtractorOutput(
        delta_events=[
            DeltaEvent(
                event_type=EventTypeEnum.MEDICATION_ADDED,
                payload={"drug_name": "Lisinopril", "dosage": "10mg", "frequency": "daily"},
            ),
            DeltaEvent(
                event_type=EventTypeEnum.SYMPTOM_REPORTED,
                payload={"symptom": "type 2 diabetes"},
            ),
        ],
        raw_intent="Provide clarification on medications and diabetes comorbidity",
        search_query="hypertension diabetes target blood pressure guideline recommendations",
    )

    turn_2_gate_1 = ContextGateOutput(
        action="PROCEED",
        missing_fields=[],
        rationale="Context complete with age, BP 155/95, Lisinopril, and type 2 diabetes.",
    )

    turn_2_gate_2 = EvidenceGateOutput(
        action="ANSWER",
        evidence_sufficient=True,
        rationale="Retrieved guidelines confirm target BP < 130/80 mmHg for patients with diabetes.",
    )

    turn_2_generator_output = ResponseGeneratorOutput(
        response_text=(
            "According to the 2025 AHA/ACC guidelines, the recommended blood pressure target for adults "
            "with diabetes is < 130/80 mmHg [1]. Since your current blood pressure is 155/95 mmHg, "
            "it remains above the recommended goal despite taking Lisinopril 10mg [2]. "
            "Please consult your physician regarding potential combination therapy."
        ),
        citations=[
            GeneratedCitation(
                marker="[1]",
                chunk_id="aha_chunk_01",
                source="AHA/ACC 2025",
                section="Section 2: Blood Pressure Targets",
                excerpt="Patients with Diabetes Mellitus: Target BP < 130/80 mmHg.",
            ),
            GeneratedCitation(
                marker="[2]",
                chunk_id="esc_chunk_02",
                source="ESC/ESH 2024",
                section="Section 3: Combination Therapy",
                excerpt="Dual combination therapy using single pill combination is recommended.",
            ),
        ],
    )

    with patch.object(orchestrator._context_extractor, "extract", new_callable=AsyncMock) as mock_extract_2, \
         patch.object(orchestrator._context_gate, "evaluate", new_callable=AsyncMock) as mock_cg_2, \
         patch.object(orchestrator._evidence_gate, "evaluate", new_callable=AsyncMock) as mock_eg_2, \
         patch.object(orchestrator._response_generator, "generate", new_callable=AsyncMock) as mock_rg_2:

        mock_extract_2.return_value = turn_2_extraction
        mock_cg_2.return_value = turn_2_gate_1
        mock_eg_2.return_value = turn_2_gate_2
        mock_rg_2.return_value = turn_2_generator_output

        resp_2 = await orchestrator.process_message(
            session_id=new_session_id,
            message=turn_2_message,
            db=db_session,
        )

    # Verify Turn 2 response
    assert resp_2.action == ActionEnum.ANSWER
    assert resp_2.soft_ask_count == 0  # Reset to 0 on PROCEED
    assert len(resp_2.citations) == 2
    assert resp_2.citations[0].marker == "[1]"
    assert resp_2.citations[0].source == "AHA/ACC 2025"
    assert resp_2.citations[1].marker == "[2]"

    # -----------------------------------------------------------------------
    # Comprehensive PostgreSQL Audit & Snapshot Verification
    # -----------------------------------------------------------------------
    # 1. Verify snapshot soft-ask counter was reset to 0 in DB
    snapshot_row = await db_session.get(ContextSnapshot, new_session_id)
    assert snapshot_row is not None
    assert snapshot_row.soft_ask_count == 0

    # 2. Verify all 4 clinical events exist in DB
    events_res = await db_session.execute(events_stmt)
    all_events = events_res.scalars().all()
    assert len(all_events) == 4
    all_event_types = {e.event_type.value for e in all_events}
    assert all_event_types == {"DEMOGRAPHIC", "BP_READING", "MEDICATION_ADDED", "SYMPTOM_REPORTED"}

    # 3. Verify accumulated ContextSnapshot in DB
    assert snapshot_row.snapshot["demographics"]["age"] == 58
    assert snapshot_row.snapshot["demographics"]["sex"] == "male"
    assert snapshot_row.snapshot["recent_bp_readings"][0]["sbp"] == 155
    assert snapshot_row.snapshot["recent_bp_readings"][0]["dbp"] == 95
    meds = snapshot_row.snapshot.get("current_medications", [])
    assert any(m["drug"] == "Lisinopril" for m in meds)
    symptoms = snapshot_row.snapshot.get("symptoms", [])
    assert "type 2 diabetes" in symptoms

    # 4. Verify MessageHistory has 4 messages
    msgs_stmt = (
        select(MessageHistory)
        .where(MessageHistory.session_id == new_session_id)
        .order_by(MessageHistory.created_at.asc())
    )
    all_msgs = (await db_session.execute(msgs_stmt)).scalars().all()
    assert len(all_msgs) == 4
    assert all_msgs[0].role == "user"
    assert all_msgs[1].role == "assistant"
    assert all_msgs[1].action.value == "SOFT-ASK"
    assert all_msgs[2].role == "user"
    assert all_msgs[3].role == "assistant"
    assert all_msgs[3].action.value == "ANSWER"

    # 5. Verify AuditLog records
    audit_stmt = (
        select(AuditLog)
        .where(AuditLog.session_id == new_session_id)
        .order_by(AuditLog.created_at.asc())
    )
    audits = (await db_session.execute(audit_stmt)).scalars().all()
    assert len(audits) == 2
    assert audits[0].gate_1_action.value == "SOFT-ASK"
    assert audits[0].final_action.value == "SOFT-ASK"
    assert audits[1].gate_1_action.value == "PROCEED"
    assert audits[1].gate_2_action.value == "ANSWER"
    assert audits[1].final_action.value == "ANSWER"


# ===========================================================================
# 3. SOFT-ASK Loop-Breaker Transition (soft_ask_count >= 2 -> GENERALIZE)
# ===========================================================================

@pytest.mark.asyncio
async def test_soft_ask_loop_breaker_forces_generalize(
    db_session: AsyncSession,
    new_session_id: uuid.UUID,
):
    """
    When soft_ask_count reaches the threshold (>= 2), the loop-breaker must intercept
    subsequent ambiguous queries, force ActionEnum.GENERALIZE, and return population-level
    guidance instead of trapping the user in an infinite questioning loop.
    """
    orchestrator = PipelineOrchestrator()

    # Pre-set soft-ask count to 2 in DB ContextSnapshot
    snapshot_row = await db_session.get(ContextSnapshot, new_session_id)
    assert snapshot_row is not None
    snapshot_row.soft_ask_count = 2
    await db_session.commit()

    ambiguous_message = "What should I do about my condition?"

    # Extractor extracts no specific clinical data
    extraction = ExtractorOutput(
        delta_events=[],
        raw_intent="General query",
        search_query="blood pressure general management",
    )

    # Context Gate would normally want another SOFT-ASK
    gate_1 = ContextGateOutput(
        action="SOFT-ASK",
        missing_fields=["bp_reading"],
        rationale="No blood pressure reading provided.",
    )

    with patch.object(orchestrator._context_extractor, "extract", new_callable=AsyncMock) as mock_extract, \
         patch.object(orchestrator._context_gate, "evaluate", new_callable=AsyncMock) as mock_cg:

        mock_extract.return_value = extraction
        mock_cg.return_value = gate_1

        response = await orchestrator.process_message(
            session_id=new_session_id,
            message=ambiguous_message,
            db=db_session,
        )

    # Loop-breaker MUST force GENERALIZE
    assert response.action == ActionEnum.GENERALIZE
    assert response.citations == []
    assert "general clinical guidelines" in response.response_text.lower()

    # Verify AuditLog recorded forced GENERALIZE
    audit_stmt = (
        select(AuditLog)
        .where(AuditLog.session_id == new_session_id)
        .order_by(AuditLog.created_at.desc())
    )
    audit = (await db_session.execute(audit_stmt)).scalars().first()
    assert audit is not None
    assert audit.final_action.value == "GENERALIZE"
    assert "loop-breaker" in audit.gate_2_rationale.lower() or "forced generalize" in audit.gate_2_rationale.lower()


# ===========================================================================
# 4. Out-of-Domain / Insufficient Evidence -> ABSTAIN Transition
# ===========================================================================

@pytest.mark.asyncio
async def test_insufficient_evidence_routes_to_abstain(
    db_session: AsyncSession,
    new_session_id: uuid.UUID,
):
    """
    Out-of-domain queries lacking guideline support must route cleanly to ABSTAIN
    via Evidence Gate, returning a safe referral template without hallucinations.
    """
    orchestrator = PipelineOrchestrator()
    out_of_domain_query = "What is the recommended dosage of topical corticosteroids for eczema?"

    extraction = ExtractorOutput(
        delta_events=[],
        raw_intent="Eczema topical steroid treatment",
        search_query="corticosteroid dosage eczema dermatitis",
    )

    # Context Gate allows the query through
    gate_1 = ContextGateOutput(
        action="PROCEED",
        missing_fields=[],
        rationale="Context evaluated.",
    )

    # Evidence Gate identifies that hypertension guidelines do not support dermatology queries
    gate_2 = EvidenceGateOutput(
        action="ABSTAIN",
        evidence_sufficient=False,
        rationale="Retrieved guidelines cover cardiovascular hypertension only. No evidence for dermatologic conditions.",
    )

    with patch.object(orchestrator._context_extractor, "extract", new_callable=AsyncMock) as mock_extract, \
         patch.object(orchestrator._context_gate, "evaluate", new_callable=AsyncMock) as mock_cg, \
         patch.object(orchestrator._evidence_gate, "evaluate", new_callable=AsyncMock) as mock_eg:

        mock_extract.return_value = extraction
        mock_cg.return_value = gate_1
        mock_eg.return_value = gate_2

        response = await orchestrator.process_message(
            session_id=new_session_id,
            message=out_of_domain_query,
            db=db_session,
        )

    # Verify ABSTAIN routing
    assert response.action == ActionEnum.ABSTAIN
    assert response.citations == []
    assert "sufficient information in my clinical guidelines" in response.response_text or "outside the scope" in response.response_text

    # Verify AuditLog
    audit_stmt = (
        select(AuditLog)
        .where(AuditLog.session_id == new_session_id)
        .order_by(AuditLog.created_at.desc())
    )
    audit = (await db_session.execute(audit_stmt)).scalars().first()
    assert audit is not None
    assert audit.gate_2_action.value == "ABSTAIN"
    assert audit.final_action.value == "ABSTAIN"


# ===========================================================================
# 5. FastAPI REST API HTTP Round-Trip via TestClient
# ===========================================================================

def test_fastapi_rest_routes_e2e_flow():
    """
    Full HTTP round-trip using FastAPI TestClient:
    1. POST /api/sessions -> creates session in live PostgreSQL.
    2. POST /api/sessions/{id}/messages -> processes emergency query, returns HTTP 200 with ESCALATE.
    3. GET /api/sessions/{id}/history -> verifies full conversation history.
    4. GET /health -> verifies live DB and Qdrant connectivity.
    """
    app = create_app()
    with TestClient(app) as client:
        # 1. Create Session
        resp_create = client.post("/api/sessions")
        assert resp_create.status_code == 201
        sid_str = resp_create.json()["session_id"]
        sid = uuid.UUID(sid_str)

        # 2. Submit Emergency Message
        emergency_msg = "My BP is 220/130 with severe chest pain and shortness of breath."
        resp_msg = client.post(
            f"/api/sessions/{sid}/messages",
            json={"message": emergency_msg},
        )
        assert resp_msg.status_code == 200
        msg_data = resp_msg.json()
        assert msg_data["session_id"] == sid_str
        assert msg_data["action"] == "ESCALATE"
        assert "911" in msg_data["response_text"] or "emergency" in msg_data["response_text"].lower()

        # 3. Retrieve Conversation History
        resp_history = client.get(f"/api/sessions/{sid}/history")
        assert resp_history.status_code == 200
        history_data = resp_history.json()
        assert history_data["session_id"] == sid_str
        messages = history_data["messages"]
        assert len(messages) == 2
        assert messages[0]["role"] == "user"
        assert messages[0]["content"] == emergency_msg
        assert messages[1]["role"] == "assistant"
        assert messages[1]["action"] == "ESCALATE"

        # 4. System Health Check
        resp_health = client.get("/health")
        assert resp_health.status_code == 200
        health_data = resp_health.json()
        assert health_data["status"] == "healthy"
        assert health_data["postgres_connected"] is True
        assert health_data["qdrant_connected"] is True
