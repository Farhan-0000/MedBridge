from pydantic import BaseModel
from typing import Any
from medbridge.api.schemas.enums import EventTypeEnum

class DeltaEvent(BaseModel):
    event_type: EventTypeEnum
    payload: dict[str, Any]

class ExtractorOutput(BaseModel):
    delta_events: list[DeltaEvent]
    search_query: str
    raw_intent: str
