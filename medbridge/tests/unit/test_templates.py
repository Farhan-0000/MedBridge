"""
Unit tests for TASK-16: Deterministic Response Templates.

Verifies non-empty strings, correct content, proper exceptions on
invalid actions, and immutability of template constants.
"""
import pytest

from medbridge.api.schemas.enums import ActionEnum
from medbridge.core.templates import (
    ABSTAIN_TEMPLATE,
    ESCALATE_TEMPLATE,
    LOOP_BREAKER_PREFIX,
    get_loop_breaker_prefix,
    get_template,
)


# ---------------------------------------------------------------------------
# get_template() — Valid Actions
# ---------------------------------------------------------------------------

class TestGetTemplateValid:
    """ESCALATE and ABSTAIN must return non-empty pre-vetted strings."""

    def test_escalate_returns_non_empty(self) -> None:
        result = get_template(ActionEnum.ESCALATE)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_abstain_returns_non_empty(self) -> None:
        result = get_template(ActionEnum.ABSTAIN)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_escalate_contains_emergency_referral(self) -> None:
        result = get_template(ActionEnum.ESCALATE)
        assert "emergency" in result.lower()
        assert "911" in result

    def test_escalate_contains_disclaimer(self) -> None:
        result = get_template(ActionEnum.ESCALATE)
        assert "informational guidance only" in result

    def test_abstain_contains_physician_referral(self) -> None:
        result = get_template(ActionEnum.ABSTAIN)
        assert "healthcare provider" in result

    def test_abstain_mentions_guideline_limitation(self) -> None:
        result = get_template(ActionEnum.ABSTAIN)
        assert "clinical guidelines" in result

    def test_escalate_matches_constant(self) -> None:
        assert get_template(ActionEnum.ESCALATE) == ESCALATE_TEMPLATE

    def test_abstain_matches_constant(self) -> None:
        assert get_template(ActionEnum.ABSTAIN) == ABSTAIN_TEMPLATE


# ---------------------------------------------------------------------------
# get_template() — Invalid Actions
# ---------------------------------------------------------------------------

class TestGetTemplateInvalid:
    """Actions without deterministic templates must raise ValueError."""

    def test_answer_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="ANSWER"):
            get_template(ActionEnum.ANSWER)

    def test_generalize_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="GENERALIZE"):
            get_template(ActionEnum.GENERALIZE)

    def test_soft_ask_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="SOFT-ASK"):
            get_template(ActionEnum.SOFT_ASK)


# ---------------------------------------------------------------------------
# get_loop_breaker_prefix()
# ---------------------------------------------------------------------------

class TestLoopBreakerPrefix:
    """Loop-breaker prefix for soft_ask_count >= 2 (NON-NEGOTIABLE #4)."""

    def test_returns_non_empty_string(self) -> None:
        result = get_loop_breaker_prefix()
        assert isinstance(result, str)
        assert len(result) > 0

    def test_matches_constant(self) -> None:
        assert get_loop_breaker_prefix() == LOOP_BREAKER_PREFIX

    def test_contains_empathetic_transition(self) -> None:
        result = get_loop_breaker_prefix()
        assert "medical details" in result.lower()

    def test_mentions_general_guidance(self) -> None:
        result = get_loop_breaker_prefix()
        assert "general guidance" in result


# ---------------------------------------------------------------------------
# Template Safety
# ---------------------------------------------------------------------------

class TestTemplateSafety:
    """Templates must not contain dynamic placeholders or clinical claims."""

    @pytest.mark.parametrize("template", [
        ESCALATE_TEMPLATE,
        ABSTAIN_TEMPLATE,
        LOOP_BREAKER_PREFIX,
    ])
    def test_no_format_placeholders(self, template: str) -> None:
        """No {curly_brace} placeholders that could inject content."""
        assert "{" not in template
        assert "}" not in template

    @pytest.mark.parametrize("template", [
        ESCALATE_TEMPLATE,
        ABSTAIN_TEMPLATE,
        LOOP_BREAKER_PREFIX,
    ])
    def test_no_dosage_or_drug_claims(self, template: str) -> None:
        """Templates must not contain specific drug names or dosages."""
        lower = template.lower()
        assert "mg" not in lower
        assert "amlodipine" not in lower
        assert "lisinopril" not in lower
        assert "metoprolol" not in lower
