"""
Database Session Manager (ADL-014).

Provides session CRUD operations, session state loading (snapshot +
soft_ask_count), message history logging, and loop-breaker counter
management.

All functions accept an ``AsyncSession`` and do **not** commit —
callers (or the FastAPI dependency) are responsible for committing.

Technical Specification Part IV §4.
"""
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from medbridge.api.schemas.enums import ActionEnum
from medbridge.db.models import (
    ContextSnapshot,
    FinalActionEnum,
    MessageHistory,
    Session,
)


class SessionNotFoundError(Exception):
    """Raised when a session does not exist in the database."""

    def __init__(self, session_id: uuid.UUID) -> None:
        self.session_id = session_id
        super().__init__(f"Session {session_id} not found")


# ------------------------------------------------------------------
# Session CRUD
# ------------------------------------------------------------------

async def create_session(db: AsyncSession) -> uuid.UUID:
    """Create a new session and return its UUID.

    Also initialises an empty ``ContextSnapshot`` row so that
    ``load_session_state`` always has a snapshot to return.
    """
    session_id = uuid.uuid4()
    session = Session(session_id=session_id)
    db.add(session)

    # Pre-create the snapshot row with defaults
    snapshot = ContextSnapshot(
        session_id=session_id,
        snapshot={},
        soft_ask_count=0,
    )
    db.add(snapshot)

    await db.flush()
    return session_id


async def load_session_state(
    db: AsyncSession,
    session_id: uuid.UUID,
) -> dict[str, Any]:
    """Load the snapshot and soft_ask_count for a session (ADL-014).

    Returns a dict with keys ``"snapshot"`` (dict) and
    ``"soft_ask_count"`` (int).

    Raises:
        SessionNotFoundError: if the session does not exist.
    """
    session = await db.get(Session, session_id)
    if session is None:
        raise SessionNotFoundError(session_id)

    snap = await db.get(ContextSnapshot, session_id)
    if snap is None:
        # Session exists but no snapshot yet — return empty defaults
        return {"snapshot": {}, "soft_ask_count": 0}

    return {
        "snapshot": snap.snapshot,
        "soft_ask_count": snap.soft_ask_count,
    }


# ------------------------------------------------------------------
# Message History
# ------------------------------------------------------------------

async def save_message(
    db: AsyncSession,
    session_id: uuid.UUID,
    role: str,
    content: str,
    action: Optional[ActionEnum] = None,
    citations: Optional[list[dict[str, Any]]] = None,
) -> uuid.UUID:
    """Append a message to message_history and return its UUID.

    Args:
        db: Active async database session.
        session_id: The session to append the message to.
        role: ``"user"`` or ``"assistant"``.
        content: Message text content.
        action: The final action taken (assistant messages only).
        citations: List of citation dicts (assistant messages only).
    """
    final_action = None
    if action is not None:
        final_action = FinalActionEnum(action.value)

    message = MessageHistory(
        message_id=uuid.uuid4(),
        session_id=session_id,
        role=role,
        content=content,
        action=final_action,
        citations=citations or [],
    )
    db.add(message)
    await db.flush()
    return message.message_id


async def get_message_history(
    db: AsyncSession,
    session_id: uuid.UUID,
) -> list[dict[str, Any]]:
    """Return chronological message list for a session.

    Each message is a dict with keys: ``message_id``, ``role``,
    ``content``, ``action``, ``citations``, ``created_at``.

    Ordered by ``created_at ASC``.
    """
    stmt = (
        select(MessageHistory)
        .where(MessageHistory.session_id == session_id)
        .order_by(MessageHistory.created_at.asc())
    )
    result = await db.execute(stmt)
    rows = result.scalars().all()

    return [
        {
            "message_id": row.message_id,
            "role": row.role,
            "content": row.content,
            "action": row.action.value if row.action else None,
            "citations": row.citations or [],
            "created_at": row.created_at,
        }
        for row in rows
    ]


# ------------------------------------------------------------------
# Soft-Ask Counter Management (Loop-Breaker — NON-NEGOTIABLE #4)
# ------------------------------------------------------------------

async def increment_soft_ask_count(
    db: AsyncSession,
    session_id: uuid.UUID,
) -> int:
    """Increment the soft_ask_count by 1 and return the new value.

    Raises:
        SessionNotFoundError: if the snapshot row does not exist.
    """
    snap = await db.get(ContextSnapshot, session_id)
    if snap is None:
        raise SessionNotFoundError(session_id)

    snap.soft_ask_count += 1
    await db.flush()
    return snap.soft_ask_count


async def reset_soft_ask_count(
    db: AsyncSession,
    session_id: uuid.UUID,
) -> None:
    """Reset the soft_ask_count to 0 (called when Context Gate returns PROCEED).

    Raises:
        SessionNotFoundError: if the snapshot row does not exist.
    """
    snap = await db.get(ContextSnapshot, session_id)
    if snap is None:
        raise SessionNotFoundError(session_id)

    snap.soft_ask_count = 0
    await db.flush()
