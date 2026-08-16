from pydantic import BaseModel
from uuid import UUID
from datetime import datetime
from medbridge.api.schemas.enums import ActionEnum

class CitationResponse(BaseModel):
    marker: str
    chunk_id: str
    source: str
    section: str
    excerpt: str

class MessageResponse(BaseModel):
    session_id: UUID
    response_text: str
    action: ActionEnum
    citations: list[CitationResponse]
    soft_ask_count: int
    timestamp: datetime

class ErrorResponse(BaseModel):
    error_code: str
    message: str
    safe_fallback: str
