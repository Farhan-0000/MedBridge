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
