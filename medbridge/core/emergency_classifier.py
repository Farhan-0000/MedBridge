"""
Deterministic Emergency Classifier (ADL-002).

Regex-based sub-5ms triage classifier that detects hypertensive crises,
red-flag symptoms, and acute danger in raw patient messages **before** any
LLM invocation.

Patterns are compiled at import time for maximum performance.
Technical Specification Part III §3.2.
"""
import re
from typing import Optional

from medbridge.api.schemas.enums import ActionEnum

# ------------------------------------------------------------------
# Compiled emergency patterns (import-time compilation)
# ------------------------------------------------------------------

_EMERGENCY_PATTERNS: list[re.Pattern[str]] = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in [
        # Hypertensive emergency: systolic ≥180 OR diastolic ≥120
        # Systolic ≥180 with any diastolic
        r"(?:bp|blood\s+pressure)\s*(?:is|was|of|:)?\s*(?:2[0-9]{2}|1[89][0-9])\s*/\s*\d+",
        # Any systolic with diastolic ≥120
        r"(?:bp|blood\s+pressure)\s*(?:is|was|of|:)?\s*\d+\s*/\s*(?:1[2-9][0-9]|[2-9][0-9]{2})",
        # Red-flag symptoms
        r"chest\s+pain",
        r"difficulty\s+breathing",
        r"sudden\s+(?:severe\s+)?headache",
        r"vision\s+(?:loss|changes|blurr)",
        r"numbness.*(?:face|arm|leg)",
        r"(?:slurr?ed\s+speech|speech\s+(?:is\s+)?slurr?ed)",
        r"(?:faint|pass(?:ed)?\s+out|unconscious|seizure)",
        r"blood\s+in\s+(?:urine|stool)",
        # Self-harm / suicidal ideation
        r"(?:suicid|self[- ]harm|kill\s+my)",
    ]
]


def classify(message: str) -> Optional[ActionEnum]:
    """Evaluate a raw patient message against emergency patterns.

    This function runs **before** any LLM invocation in the pipeline.
    It must complete in under 5ms.

    Args:
        message: The raw patient message text.

    Returns:
        ``ActionEnum.ESCALATE`` if any emergency pattern matches,
        ``None`` if the message is safe to continue through the pipeline.
    """
    for pattern in _EMERGENCY_PATTERNS:
        if pattern.search(message):
            return ActionEnum.ESCALATE
    return None
