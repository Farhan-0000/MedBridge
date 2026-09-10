from typing import Literal
from pydantic import BaseModel, Field


class EvidenceGateOutput(BaseModel):
    """Evidence Gate classification output (LLM Call 3, ADL-024)."""

    action: Literal["ANSWER", "GENERALIZE", "ABSTAIN", "ESCALATE"] = Field(
        ...,
        description="Routing action decision based on evidence sufficiency and clinical safety.",
    )
    evidence_sufficient: bool = Field(
        ...,
        description="Whether the retrieved evidence is clinically sufficient to answer the query.",
    )
    rationale: str = Field(
        default="",
        description="Clinical rationale explaining the routing action.",
    )
