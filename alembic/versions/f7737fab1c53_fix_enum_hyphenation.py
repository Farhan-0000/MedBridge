"""fix_enum_hyphenation

Revision ID: f7737fab1c53
Revises: 6a69a1c21f43
Create Date: 2026-09-10 14:13:45.518348

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f7737fab1c53'
down_revision: Union[str, Sequence[str], None] = '6a69a1c21f43'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Rename enum values from underscore to hyphen format (ADL-008)."""
    op.execute("""
    DO $$
    BEGIN
        IF EXISTS (
            SELECT 1 FROM pg_enum e
            JOIN pg_type t ON e.enumtypid = t.oid
            WHERE t.typname = 'gate_1_action_enum' AND e.enumlabel = 'SOFT_ASK'
        ) THEN
            ALTER TYPE gate_1_action_enum RENAME VALUE 'SOFT_ASK' TO 'SOFT-ASK';
        END IF;

        IF EXISTS (
            SELECT 1 FROM pg_enum e
            JOIN pg_type t ON e.enumtypid = t.oid
            WHERE t.typname = 'final_action_enum' AND e.enumlabel = 'SOFT_ASK'
        ) THEN
            ALTER TYPE final_action_enum RENAME VALUE 'SOFT_ASK' TO 'SOFT-ASK';
        END IF;
    END $$;
    """)


def downgrade() -> None:
    """Revert enum values back to underscore format."""
    op.execute("""
    DO $$
    BEGIN
        IF EXISTS (
            SELECT 1 FROM pg_enum e
            JOIN pg_type t ON e.enumtypid = t.oid
            WHERE t.typname = 'gate_1_action_enum' AND e.enumlabel = 'SOFT-ASK'
        ) THEN
            ALTER TYPE gate_1_action_enum RENAME VALUE 'SOFT-ASK' TO 'SOFT_ASK';
        END IF;

        IF EXISTS (
            SELECT 1 FROM pg_enum e
            JOIN pg_type t ON e.enumtypid = t.oid
            WHERE t.typname = 'final_action_enum' AND e.enumlabel = 'SOFT-ASK'
        ) THEN
            ALTER TYPE final_action_enum RENAME VALUE 'SOFT-ASK' TO 'SOFT_ASK';
        END IF;
    END $$;
    """)
