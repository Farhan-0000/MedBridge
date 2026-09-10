"""
Forwarding shim for Adversarial & Security Test Suite (TASK-33).

Re-exports the test suite from tests.adversarial.test_security_adversarial.
"""
from tests.adversarial.test_security_adversarial import (  # noqa: F401
    TestBrandGenericDrugSubstitution,
    TestPromptInjectionResilience,
    TestSQLInjectionResistance,
    db_session,
    new_session_id,
)
