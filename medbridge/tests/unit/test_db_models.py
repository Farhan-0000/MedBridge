import pytest
from sqlalchemy import inspect
from medbridge.db.models import (
    Base,
    Session,
    ClinicalEvent,
    ContextSnapshot,
    AuditLog,
    MessageHistory,
)

def test_table_names():
    assert Session.__tablename__ == "sessions"
    assert ClinicalEvent.__tablename__ == "clinical_events"
    assert ContextSnapshot.__tablename__ == "context_snapshots"
    assert AuditLog.__tablename__ == "audit_logs"
    assert MessageHistory.__tablename__ == "message_history"

def test_session_relationships():
    mapper = inspect(Session)
    assert "clinical_events" in mapper.relationships
    assert "context_snapshot" in mapper.relationships
    assert "audit_logs" in mapper.relationships
    assert "message_history" in mapper.relationships

def test_foreign_keys():
    assert ClinicalEvent.session_id.property.columns[0].foreign_keys
    assert ContextSnapshot.session_id.property.columns[0].foreign_keys
    assert AuditLog.session_id.property.columns[0].foreign_keys
    assert MessageHistory.session_id.property.columns[0].foreign_keys


def test_enum_column_values():
    """Verify that Enum columns map to the canonical hyphenated string values (ADL-008)."""
    assert AuditLog.__table__.c.gate_1_action.type.enums == ["SOFT-ASK", "PROCEED"]
    assert AuditLog.__table__.c.gate_2_action.type.enums == ["ANSWER", "GENERALIZE", "ABSTAIN", "ESCALATE"]
    assert AuditLog.__table__.c.final_action.type.enums == ["SOFT-ASK", "ANSWER", "GENERALIZE", "ABSTAIN", "ESCALATE"]
    assert MessageHistory.__table__.c.action.type.enums == ["SOFT-ASK", "ANSWER", "GENERALIZE", "ABSTAIN", "ESCALATE"]


def test_enum_bind_and_result_processing():
    """Verify that SQLAlchemy binds and parses hyphenated enum values properly."""
    from sqlalchemy.dialects import postgresql
    from medbridge.db.models import FinalActionEnum, Gate1ActionEnum

    final_type = AuditLog.__table__.c.final_action.type
    bp = final_type.bind_processor(postgresql.dialect())
    rp = final_type.result_processor(postgresql.dialect(), None)

    # Bind param should be the hyphenated string
    assert bp(FinalActionEnum.SOFT_ASK) == "SOFT-ASK"
    # Result value should parse into the enum instance
    assert rp("SOFT-ASK") == FinalActionEnum.SOFT_ASK

    gate1_type = AuditLog.__table__.c.gate_1_action.type
    g1_bp = gate1_type.bind_processor(postgresql.dialect())
    g1_rp = gate1_type.result_processor(postgresql.dialect(), None)
    assert g1_bp(Gate1ActionEnum.SOFT_ASK) == "SOFT-ASK"
    assert g1_rp("SOFT-ASK") == Gate1ActionEnum.SOFT_ASK

