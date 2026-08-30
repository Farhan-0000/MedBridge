import os
import pytest
from alembic.config import Config
from alembic import command
from sqlalchemy import text
from medbridge.db.connection import get_engine

# Ensure required environment variables for Alembic/Settings
os.environ["POSTGRES_PASSWORD"] = "password"
os.environ["GROQ_API_KEY"] = "dummy"

def run_alembic(cmd, *args, **kwargs):
    alembic_cfg = Config("alembic.ini")
    getattr(command, cmd)(alembic_cfg, *args, **kwargs)

@pytest.fixture(scope="module")
def apply_migrations():
    # Attempt to downgrade just in case DB is already populated
    try:
        run_alembic("downgrade", "base")
    except Exception:
        pass
    
    # Run migrations up
    run_alembic("upgrade", "head")
    
    yield
    
    # Run migrations down
    run_alembic("downgrade", "base")

@pytest.mark.asyncio
async def test_migrations_and_immutability(apply_migrations):
    engine = get_engine()
    
    async with engine.begin() as conn:
        # 1. Insert dummy session
        res = await conn.execute(
            text("INSERT INTO sessions (session_id) VALUES (gen_random_uuid()) RETURNING session_id")
        )
        session_id = res.scalar()

        # 2. Insert clinical event
        res = await conn.execute(
            text("INSERT INTO clinical_events (event_id, session_id, event_type, payload) VALUES (gen_random_uuid(), :sid, 'BP_READING', '{}') RETURNING event_id"),
            {"sid": session_id}
        )
        event_id = res.scalar()

        # 3. Test UPDATE on clinical_events is a no-op
        await conn.execute(
            text("UPDATE clinical_events SET event_type = 'LAB_RESULT' WHERE event_id = :eid"),
            {"eid": event_id}
        )
        
        # Verify it didn't change
        res = await conn.execute(
            text("SELECT event_type FROM clinical_events WHERE event_id = :eid"),
            {"eid": event_id}
        )
        assert res.scalar() == "BP_READING"

        # 4. Test DELETE on clinical_events is a no-op
        await conn.execute(
            text("DELETE FROM clinical_events WHERE event_id = :eid"),
            {"eid": event_id}
        )
        
        # Verify it still exists
        res = await conn.execute(
            text("SELECT COUNT(*) FROM clinical_events WHERE event_id = :eid"),
            {"eid": event_id}
        )
        assert res.scalar() == 1
