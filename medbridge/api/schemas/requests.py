"""
API Request Pydantic Models.

Defines validated request schemas for all inbound API endpoints.
Constitution §8.5: Input length constraints enforce max 2000 characters.
"""
from pydantic import BaseModel, Field


class MessageRequest(BaseModel):
    """Request body for POST /api/sessions/{session_id}/messages."""

    message: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="Patient's clinical question",
    )
