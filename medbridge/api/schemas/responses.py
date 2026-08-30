"""
API Response Pydantic Models.

Defines validated response schemas for all outbound API responses.
All schemas follow Technical Specification Part II §5.1.
"""
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

from medbridge.api.schemas.enums import ActionEnum


class CitationResponse(BaseModel):
    """A single inline citation referencing a clinical guideline chunk."""

    marker: str = Field(..., description="Citation marker, e.g. '[1]'")
    chunk_id: str = Field(..., description="Unique chunk identifier, e.g. 'aha_2025_s8_c3'")
    source: str = Field(..., description="Guideline source, e.g. 'AHA/ACC 2025'")
    section: str = Field(..., description="Section reference, e.g. 'Section 8.2'")
    excerpt: str = Field(..., description="Truncated evidence text excerpt")


class MessageResponse(BaseModel):
    """Response body for POST /api/sessions/{session_id}/messages."""

    session_id: UUID
    response_text: str
    action: ActionEnum
    citations: list[CitationResponse] = Field(default_factory=list)
    soft_ask_count: int = Field(default=0, ge=0)
    timestamp: datetime


class SessionResponse(BaseModel):
    """Response body for POST /api/sessions (session creation)."""

    session_id: UUID
    created_at: datetime


class HistoryMessage(BaseModel):
    """A single message entry in the conversation history."""

    role: str = Field(..., description="Message sender: 'user' or 'assistant'")
    content: str
    action: Optional[ActionEnum] = None
    citations: list[CitationResponse] = Field(default_factory=list)
    timestamp: datetime


class HistoryResponse(BaseModel):
    """Response body for GET /api/sessions/{session_id}/history."""

    session_id: UUID
    messages: list[HistoryMessage] = Field(default_factory=list)


class HealthResponse(BaseModel):
    """Response body for GET /health."""

    status: str = Field(..., description="'healthy' or 'unhealthy'")
    postgres_connected: bool
    qdrant_connected: bool
    timestamp: datetime


class ErrorResponse(BaseModel):
    """
    Standardised error response body.

    Constitution §9 (NON-NEGOTIABLE #7): The backend must never return
    raw 500 errors. This schema guarantees a structured, safe response.
    """

    error_code: str = Field(..., description="Machine-readable error code")
    message: str = Field(..., description="Human-readable error description")
    safe_fallback: str = Field(
        ...,
        description="Pre-vetted clinically safe fallback message for the patient",
    )
