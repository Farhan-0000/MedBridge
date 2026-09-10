"""
Message Processing REST Routes (TASK-29, Module M-04).

Endpoints:
- POST /api/sessions/{session_id}/messages: Process clinical query through the 8-stage AI pipeline (HTTP 200).

Technical Specification Part II §4.1.
"""
import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from medbridge.api.schemas.requests import MessageRequest
from medbridge.api.schemas.responses import MessageResponse
from medbridge.core.orchestrator import PipelineOrchestrator, get_orchestrator
from medbridge.db.connection import get_session
from medbridge.db.models import Session as SessionModel
from medbridge.state.session_manager import SessionNotFoundError

messages_router = APIRouter(prefix="/sessions", tags=["messages"])


@messages_router.post(
    "/{session_id}/messages",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Submit patient message to the 8-stage clinical pipeline",
)
async def handle_send_message(
    session_id: uuid.UUID,
    payload: MessageRequest,
    db: AsyncSession = Depends(get_session),
    orchestrator: PipelineOrchestrator = Depends(get_orchestrator),
) -> MessageResponse:
    """
    Process an incoming patient question through the full MedBridge pipeline.
    
    1. Validates that the session exists (raises 404 SESSION_NOT_FOUND if missing).
    2. Coordinates emergency classifier, extraction, gates, retrieval, and response generation.
    3. Persists events, snapshot, message history, and audit log.
    4. Returns grounded clinical guidance with inline citations (HTTP 200).
    """
    session = await db.get(SessionModel, session_id)
    if session is None:
        raise SessionNotFoundError(session_id)

    return await orchestrator.process_message(
        session_id=session_id,
        message=payload.message,
        db=db,
    )
