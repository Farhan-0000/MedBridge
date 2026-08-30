"""
Unit tests for TASK-15: Deterministic Emergency Classifier.

Covers true positives (crisis BP, symptom keywords), true negatives
(routine queries), case insensitivity, whitespace variations, and
sub-5ms latency verification.
"""
import time

import pytest

from medbridge.api.schemas.enums import ActionEnum
from medbridge.core.emergency_classifier import classify


# ---------------------------------------------------------------------------
# True Positive Suite — Hypertensive Crisis BP Values
# ---------------------------------------------------------------------------

class TestHypertensiveCrisis:
    """BP systolic ≥180 OR diastolic ≥120 → ESCALATE."""

    @pytest.mark.parametrize("message", [
        "My bp is 200/130",
        "blood pressure 185/125",
        "BP 180/120 this morning",
        "My blood pressure was 195/110",    # systolic ≥180
        "bp 210/140 and I feel dizzy",
        "Blood Pressure: 190/130",
        "BP is 199/121",
    ])
    def test_crisis_bp_escalates(self, message: str) -> None:
        assert classify(message) == ActionEnum.ESCALATE

    @pytest.mark.parametrize("message", [
        "My bp is 180/125",
        "blood pressure 220/150",
        "BP 195/135",
    ])
    def test_extreme_crisis_values(self, message: str) -> None:
        assert classify(message) == ActionEnum.ESCALATE


# ---------------------------------------------------------------------------
# True Positive Suite — Red-Flag Symptoms
# ---------------------------------------------------------------------------

class TestRedFlagSymptoms:
    """Known emergency symptom keywords → ESCALATE."""

    @pytest.mark.parametrize("message", [
        "I'm having chest pain right now",
        "experiencing difficulty breathing since this morning",
        "I had a sudden severe headache an hour ago",
        "sudden headache with nausea",
        "having vision changes and dizziness",
        "vision loss in my left eye",
        "vision blurring since yesterday",
        "numbness in my face and arm",
        "numbness in my left leg",
        "I have slurred speech",
        "my speech is slured and I'm confused",
        "I fainted at work today",
        "I passed out twice",
        "my mother is unconscious",
        "had a seizure last night",
        "there's blood in urine",
        "noticed blood in stool yesterday",
    ])
    def test_symptom_escalates(self, message: str) -> None:
        assert classify(message) == ActionEnum.ESCALATE


# ---------------------------------------------------------------------------
# True Positive Suite — Self-Harm / Suicidal Ideation
# ---------------------------------------------------------------------------

class TestSelfHarm:
    """Self-harm and suicidal ideation keywords → ESCALATE."""

    @pytest.mark.parametrize("message", [
        "I'm thinking about suicide",
        "having suicidal thoughts",
        "I want to self-harm",
        "I want to self harm",
        "I want to kill myself",
    ])
    def test_self_harm_escalates(self, message: str) -> None:
        assert classify(message) == ActionEnum.ESCALATE


# ---------------------------------------------------------------------------
# True Negative Suite — Routine Messages
# ---------------------------------------------------------------------------

class TestTrueNegatives:
    """Routine clinical questions → None (safe to continue)."""

    @pytest.mark.parametrize("message", [
        "What is my blood pressure target?",
        "My bp is 140/90, is that high?",
        "Blood pressure 130/85 this morning",
        "I take amlodipine 5mg daily",
        "What are the side effects of lisinopril?",
        "Should I reduce my salt intake?",
        "I have a mild headache",                      # Not "sudden" headache
        "I've been feeling tired lately",
        "Can I exercise with hypertension?",
        "My doctor prescribed metoprolol",
        "How does ACE inhibitor work?",
        "I'm 55 years old, male, diabetic",
        "What foods should I avoid?",
        "My potassium level is 4.5 mEq/L",
        "Is 120/80 a normal blood pressure?",
        "BP 170/95 today",                             # Below crisis threshold
        "blood pressure 179/119",                      # Just below threshold
    ])
    def test_routine_returns_none(self, message: str) -> None:
        assert classify(message) is None

    def test_empty_message(self) -> None:
        assert classify("") is None

    def test_unrelated_numbers(self) -> None:
        assert classify("My phone number is 180/120") is None  # No "bp" prefix


# ---------------------------------------------------------------------------
# Case Insensitivity & Whitespace Variation
# ---------------------------------------------------------------------------

class TestCaseAndWhitespace:
    """Patterns must match regardless of casing or extra whitespace."""

    @pytest.mark.parametrize("message", [
        "CHEST PAIN",
        "Chest Pain",
        "CHEST  PAIN",
        "chest   pain",
        "DIFFICULTY BREATHING",
        "Difficulty  Breathing",
        "SUDDEN SEVERE HEADACHE",
        "VISION CHANGES",
        "BLOOD IN URINE",
        "SLURRED SPEECH",
    ])
    def test_case_insensitive_match(self, message: str) -> None:
        assert classify(message) == ActionEnum.ESCALATE

    def test_bp_with_extra_spaces(self) -> None:
        # Spaces around / are handled by \s* in the regex
        assert classify("bp  200  /  130") == ActionEnum.ESCALATE
        assert classify("bp 200/130") == ActionEnum.ESCALATE

    def test_bp_with_prefix_word(self) -> None:
        assert classify("my blood pressure is 190/125") == ActionEnum.ESCALATE


# ---------------------------------------------------------------------------
# Latency Verification
# ---------------------------------------------------------------------------

class TestLatency:
    """classify() must execute in under 5ms."""

    def test_under_5ms_on_match(self) -> None:
        msg = "I'm having chest pain and my bp is 200/130"
        start = time.perf_counter()
        for _ in range(100):
            classify(msg)
        elapsed_ms = (time.perf_counter() - start) / 100 * 1000
        assert elapsed_ms < 5, f"Average latency {elapsed_ms:.2f}ms exceeds 5ms"

    def test_under_5ms_on_no_match(self) -> None:
        msg = "What is my blood pressure target if I'm 55 years old, male, taking amlodipine?"
        start = time.perf_counter()
        for _ in range(100):
            classify(msg)
        elapsed_ms = (time.perf_counter() - start) / 100 * 1000
        assert elapsed_ms < 5, f"Average latency {elapsed_ms:.2f}ms exceeds 5ms"
