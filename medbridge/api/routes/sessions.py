"""
Session Management REST Routes (TASK-29, Module M-04).

Endpoints:
- POST /api/sessions: Create new session (HTTP 201).
- GET /api/sessions/{session_id}/history: Retrieve message history (HTTP 200).

Technical Specification Part II §4.2, §4.3.
"""
from datetime import datetime, timezone
import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from medbridge.api.schemas.enums import ActionEnum
from medbridge.api.schemas.responses import (
    CitationResponse,
    HistoryMessage,
    HistoryResponse,
    SessionResponse,
)
from medbridge.db.connection import get_session
from medbridge.db.models import Session as SessionModel
from medbridge.state.session_manager import (
    SessionNotFoundError,
    create_session,
    get_message_history,
)

sessions_router = APIRouter(prefix="/sessions", tags=["sessions"])


@sessions_router.post(
    "",
    response_model=SessionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new clinical guidance session",
)
@sessions_router.post(
    "/",
    response_model=SessionResponse,
    status_code=status.HTTP_201_CREATED,
    include_in_schema=False,
)
async def handle_create_session(
    db: AsyncSession = Depends(get_session),
) -> SessionResponse:
    """
    Create a new conversation session and initialize its ContextSnapshot.
    Returns the created session UUID and timestamp (HTTP 201).
    """
    session_id = await create_session(db)
    return SessionResponse(
        session_id=session_id,
        created_at=datetime.now(timezone.utc),
    )


@sessions_router.get(
    "/{session_id}/history",
    response_model=HistoryResponse,
    status_code=status.HTTP_200_OK,
    summary="Get conversation message history for a session",
)
async def handle_get_session_history(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_session),
) -> HistoryResponse:
    """
    Retrieve chronological message history for an existing session.
    Raises SessionNotFoundError (HTTP 404) if session does not exist.
    """
    session = await db.get(SessionModel, session_id)
    if session is None:
        raise SessionNotFoundError(session_id)

    rows = await get_message_history(db, session_id)
    messages = [
        HistoryMessage(
            role=r["role"],
            content=r["content"],
            action=ActionEnum(r["action"]) if r.get("action") else None,
            citations=[
                CitationResponse(**c) if isinstance(c, dict) else c
                for c in (r.get("citations") or [])
            ],
            timestamp=r["created_at"],
        )
        for r in rows
    ]
    return HistoryResponse(session_id=session_id, messages=messages)
