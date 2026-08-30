"""
Deterministic Response Templates (ADL-015).

Pre-vetted, immutable response templates for ESCALATE and ABSTAIN actions,
and the SOFT-ASK loop-breaker prefix used when ``soft_ask_count >= 2``.

These templates are returned **without LLM generation** and contain no
hallucinated clinical claims or dynamic placeholders.

Technical Specification Appendix B.
"""
from medbridge.api.schemas.enums import ActionEnum

# ------------------------------------------------------------------
# Template constants (Appendix B — immutable, pre-vetted text)
# ------------------------------------------------------------------

ESCALATE_TEMPLATE: str = (
    "⚠️ IMPORTANT: Based on what you've described, this situation may require "
    "immediate medical attention. Please contact your healthcare provider, "
    "visit your nearest emergency room, or call emergency services right away.\n\n"
    "This tool provides informational guidance only and cannot assess or manage "
    "medical emergencies.\n\n"
    "If you are in the United States, call 911 for emergencies."
)

ABSTAIN_TEMPLATE: str = (
    "I don't have sufficient information in my clinical guidelines to safely "
    "address this specific question. This may be outside the scope of "
    "hypertension management, or the topic may require specialized medical "
    "expertise.\n\n"
    "I recommend discussing this question directly with your healthcare provider, "
    "who can give you personalized guidance based on your complete medical history."
)

LOOP_BREAKER_PREFIX: str = (
    "I understand you may not have all your medical details handy. Here is some "
    "general guidance based on current hypertension guidelines that may be helpful:"
)

# Map of action → template for supported deterministic responses
_TEMPLATES: dict[ActionEnum, str] = {
    ActionEnum.ESCALATE: ESCALATE_TEMPLATE,
    ActionEnum.ABSTAIN: ABSTAIN_TEMPLATE,
}


# ------------------------------------------------------------------
# Public API
# ------------------------------------------------------------------

def get_template(action: ActionEnum) -> str:
    """Return the pre-vetted response template for the given action.

    Only ``ESCALATE`` and ``ABSTAIN`` have deterministic templates.
    Other actions (``ANSWER``, ``GENERALIZE``, ``SOFT_ASK``) are
    LLM-generated and do not have templates.

    Args:
        action: The pipeline action requiring a template.

    Returns:
        The immutable template string.

    Raises:
        ValueError: If the action does not have a deterministic template.
    """
    template = _TEMPLATES.get(action)
    if template is None:
        raise ValueError(
            f"No deterministic template exists for action '{action.value}'. "
            f"Only ESCALATE and ABSTAIN have pre-vetted templates."
        )
    return template


def get_loop_breaker_prefix() -> str:
    """Return the loop-breaker transition prefix (Appendix B.3).

    This prefix is prepended to the LLM-generated ``GENERALIZE`` response
    when ``soft_ask_count >= 2`` (NON-NEGOTIABLE #4).

    Returns:
        The standard non-blocking conversational transition string.
    """
    return LOOP_BREAKER_PREFIX
