from pydantic import BaseModel
from typing import Literal

class EvidenceGateOutput(BaseModel):
    action: Literal["ANSWER", "GENERALIZE", "ABSTAIN", "ESCALATE"]
    evidence_sufficient: bool
    rationale: str
