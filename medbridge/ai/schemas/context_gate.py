from pydantic import BaseModel
from typing import Literal

class ContextGateOutput(BaseModel):
    action: Literal["SOFT-ASK", "PROCEED"]
    missing_fields: list[str]
    rationale: str
