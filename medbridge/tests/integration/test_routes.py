"""
Integration Tests for REST Route Handlers (TASK-29, Module M-04).

Tests all 4 endpoints:
- POST /api/sessions: Create session (HTTP 201)
- GET /api/sessions/{session_id}/history: Retrieve message history (HTTP 200 / 404)
- POST /api/sessions/{session_id}/messages: Process clinical query (HTTP 200 / 404 / 422)
- GET /health: Health check (HTTP 200 / 503)
"""
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch
import uuid
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from medbridge.api.middleware.error_handler import register_error_handlers
from medbridge.api.routes import api_router, health_router
from medbridge.api.schemas.enums import ActionEnum
from medbridge.api.schemas.responses import (
    CitationResponse,
    HealthResponse,
    HistoryResponse,
    MessageResponse,
    SessionResponse,
)
from medbridge.core.orchestrator import PipelineOrchestrator, get_orchestrator
from medbridge.db.connection import get_session
from medbridge.db.models import MessageHistory, Session as SessionModel


@pytest.fixture
def mock_db_session():
    """Mock database session that handles Session and MessageHistory entities."""
    db = AsyncMock()
    sessions_store: dict[uuid.UUID, SessionModel] = {}
    messages_store: dict[uuid.UUID, list[MessageHistory]] = {}

    async def mock_get(entity_cls, entity_id):
        if entity_cls == SessionModel:
            return sessions_store.get(entity_id)
        return None

    def mock_add(entity):
        if isinstance(entity, SessionModel):
            sessions_store[entity.session_id] = entity
        elif isinstance(entity, MessageHistory):
            messages_store.setdefault(entity.session_id, []).append(entity)

    async def mock_execute(stmt):
        from unittest.mock import MagicMock
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        rows = []
        for sid, msgs in messages_store.items():
            rows.extend(msgs)
        mock_scalars.all.return_value = rows
        mock_result.scalars.return_value = mock_scalars
        return mock_result

    from unittest.mock import MagicMock
    db.get = AsyncMock(side_effect=mock_get)
    db.add = MagicMock(side_effect=mock_add)
    db.execute = AsyncMock(side_effect=mock_execute)
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    db.rollback = AsyncMock()

    db._sessions_store = sessions_store
    db._messages_store = messages_store
    return db


@pytest.fixture
def mock_orchestrator():
    """Mock PipelineOrchestrator returning valid MessageResponse."""
    orch = AsyncMock(spec=PipelineOrchestrator)

    async def mock_process(session_id, message, db=None):
        return MessageResponse(
            session_id=session_id,
            response_text="Based on ACC/AHA guidelines [1], your blood pressure target is <130/80 mmHg.",
            action=ActionEnum.ANSWER,
            citations=[
                CitationResponse(
                    marker="[1]",
                    chunk_id="aha_2025_s8_c1",
                    source="AHA/ACC 2025",
                    section="Section 8.1",
                    excerpt="Target BP is <130/80 mmHg for patients with hypertension.",
                )
            ],
            soft_ask_count=0,
            timestamp=datetime.now(timezone.utc),
        )

    orch.process_message.side_effect = mock_process
    return orch


@pytest.fixture
def test_client(mock_db_session, mock_orchestrator):
    """FastAPI TestClient with injected dependencies and mounted routes."""
    app = FastAPI()
    register_error_handlers(app)

    # Mount API routes
    app.include_router(api_router, prefix="/api")
    app.include_router(health_router)

    # Dependency overrides
    async def override_get_session():
        yield mock_db_session

    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_orchestrator] = lambda: mock_orchestrator

    return TestClient(app, raise_server_exceptions=False)


# ===========================================================================
# 1. POST /api/sessions
# ===========================================================================

def test_create_session_success(test_client: TestClient, mock_db_session) -> None:
    """POST /api/sessions should create session and return 201 with UUID."""
    response = test_client.post("/api/sessions")
    assert response.status_code == 201

    data = response.json()
    assert "session_id" in data
    assert "created_at" in data

    # Verify UUID format and model validation
    session_uuid = uuid.UUID(data["session_id"])
    parsed = SessionResponse.model_validate(data)
    assert parsed.session_id == session_uuid
    assert session_uuid in mock_db_session._sessions_store


# ===========================================================================
# 2. GET /api/sessions/{session_id}/history
# ===========================================================================

def test_get_history_empty_session(test_client: TestClient, mock_db_session) -> None:
    """GET /api/sessions/{id}/history for new session returns 200 with empty list."""
    sid = uuid.uuid4()
    mock_db_session._sessions_store[sid] = SessionModel(session_id=sid)

    response = test_client.get(f"/api/sessions/{sid}/history")
    assert response.status_code == 200

    data = response.json()
    parsed = HistoryResponse.model_validate(data)
    assert parsed.session_id == sid
    assert parsed.messages == []


def test_get_history_with_messages(test_client: TestClient, mock_db_session) -> None:
    """GET /api/sessions/{id}/history returns messages in chronological order."""
    sid = uuid.uuid4()
    mock_db_session._sessions_store[sid] = SessionModel(session_id=sid)

    now = datetime.now(timezone.utc)
    mock_db_session._messages_store[sid] = [
        MessageHistory(
            message_id=uuid.uuid4(),
            session_id=sid,
            role="user",
            content="What is my BP target?",
            action=None,
            citations=[],
            created_at=now,
        ),
        MessageHistory(
            message_id=uuid.uuid4(),
            session_id=sid,
            role="assistant",
            content="Target is <130/80.",
            action=ActionEnum.ANSWER,
            citations=[
                {
                    "marker": "[1]",
                    "chunk_id": "aha_c1",
                    "source": "AHA 2025",
                    "section": "S1",
                    "excerpt": "Guideline excerpt",
                }
            ],
            created_at=now,
        ),
    ]

    response = test_client.get(f"/api/sessions/{sid}/history")
    assert response.status_code == 200

    data = response.json()
    parsed = HistoryResponse.model_validate(data)
    assert len(parsed.messages) == 2
    assert parsed.messages[0].role == "user"
    assert parsed.messages[1].role == "assistant"
    assert parsed.messages[1].action == ActionEnum.ANSWER
    assert len(parsed.messages[1].citations) == 1


def test_get_history_missing_session_returns_404(test_client: TestClient) -> None:
    """GET /api/sessions/{id}/history for non-existent session returns 404."""
    unknown_id = uuid.uuid4()
    response = test_client.get(f"/api/sessions/{unknown_id}/history")
    assert response.status_code == 404

    data = response.json()
    assert data["error_code"] == "SESSION_NOT_FOUND"
    assert str(unknown_id) in data["message"]


def test_get_history_invalid_uuid_returns_422(test_client: TestClient) -> None:
    """GET /api/sessions/{id}/history with invalid UUID string returns 422."""
    response = test_client.get("/api/sessions/not-a-valid-uuid/history")
    assert response.status_code == 422

    data = response.json()
    assert data["error_code"] == "VALIDATION_ERROR"


# ===========================================================================
# 3. POST /api/sessions/{session_id}/messages
# ===========================================================================

def test_send_message_success(test_client: TestClient, mock_db_session, mock_orchestrator) -> None:
    """POST /api/sessions/{id}/messages executes pipeline and returns 200 MessageResponse."""
    sid = uuid.uuid4()
    mock_db_session._sessions_store[sid] = SessionModel(session_id=sid)

    payload = {"message": "My BP is 145/92 mmHg this morning."}
    response = test_client.post(f"/api/sessions/{sid}/messages", json=payload)
    assert response.status_code == 200

    data = response.json()
    parsed = MessageResponse.model_validate(data)
    assert parsed.session_id == sid
    assert parsed.action == ActionEnum.ANSWER
    assert len(parsed.citations) == 1
    assert "ACC/AHA" in parsed.response_text


def test_send_message_missing_session_returns_404(test_client: TestClient) -> None:
    """POST /api/sessions/{id}/messages with non-existent session returns 404."""
    unknown_id = uuid.uuid4()
    payload = {"message": "Hello, is this working?"}
    response = test_client.post(f"/api/sessions/{unknown_id}/messages", json=payload)
    assert response.status_code == 404

    data = response.json()
    assert data["error_code"] == "SESSION_NOT_FOUND"


def test_send_message_empty_message_returns_422(test_client: TestClient, mock_db_session) -> None:
    """POST /api/sessions/{id}/messages with empty string fails Pydantic validation (422)."""
    sid = uuid.uuid4()
    mock_db_session._sessions_store[sid] = SessionModel(session_id=sid)

    response = test_client.post(f"/api/sessions/{sid}/messages", json={"message": ""})
    assert response.status_code == 422

    data = response.json()
    assert data["error_code"] == "VALIDATION_ERROR"


def test_send_message_exceeds_max_length_returns_422(test_client: TestClient, mock_db_session) -> None:
    """POST /api/sessions/{id}/messages exceeding 2000 chars returns 422."""
    sid = uuid.uuid4()
    mock_db_session._sessions_store[sid] = SessionModel(session_id=sid)

    response = test_client.post(f"/api/sessions/{sid}/messages", json={"message": "a" * 2001})
    assert response.status_code == 422

    data = response.json()
    assert data["error_code"] == "VALIDATION_ERROR"


# ===========================================================================
# 4. GET /health
# ===========================================================================

@patch("medbridge.api.routes.health.check_postgres_health", new_callable=AsyncMock)
@patch("medbridge.api.routes.health.check_qdrant_health", new_callable=AsyncMock)
def test_health_check_healthy(mock_qdrant, mock_pg, test_client: TestClient) -> None:
    """GET /health returns 200 and healthy status when both dependencies pass."""
    mock_pg.return_value = True
    mock_qdrant.return_value = True

    response = test_client.get("/health")
    assert response.status_code == 200

    data = response.json()
    parsed = HealthResponse.model_validate(data)
    assert parsed.status == "healthy"
    assert parsed.postgres_connected is True
    assert parsed.qdrant_connected is True


@patch("medbridge.api.routes.health.check_postgres_health", new_callable=AsyncMock)
@patch("medbridge.api.routes.health.check_qdrant_health", new_callable=AsyncMock)
def test_health_check_postgres_failure_returns_503(mock_qdrant, mock_pg, test_client: TestClient) -> None:
    """GET /health returns 503 and unhealthy status when Postgres fails."""
    mock_pg.return_value = False
    mock_qdrant.return_value = True

    response = test_client.get("/health")
    assert response.status_code == 503

    data = response.json()
    parsed = HealthResponse.model_validate(data)
    assert parsed.status == "unhealthy"
    assert parsed.postgres_connected is False
    assert parsed.qdrant_connected is True


@patch("medbridge.api.routes.health.check_postgres_health", new_callable=AsyncMock)
@patch("medbridge.api.routes.health.check_qdrant_health", new_callable=AsyncMock)
def test_health_check_qdrant_failure_returns_503(mock_qdrant, mock_pg, test_client: TestClient) -> None:
    """GET /health returns 503 and unhealthy status when Qdrant fails."""
    mock_pg.return_value = True
    mock_qdrant.return_value = False

    response = test_client.get("/health")
    assert response.status_code == 503

    data = response.json()
    parsed = HealthResponse.model_validate(data)
    assert parsed.status == "unhealthy"
    assert parsed.postgres_connected is True
    assert parsed.qdrant_connected is False
