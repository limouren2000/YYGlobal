"""store all official application deadlines

Revision ID: 0005_requirement_deadlines
Revises: 0004_agent_structured_output
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "0005_requirement_deadlines"
down_revision: Union[str, None] = "0004_agent_structured_output"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("program_requirements")}
    if "deadlines" in columns:
        return
    op.add_column(
        "program_requirements",
        sa.Column("deadlines", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
    )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("program_requirements")}
    if "deadlines" in columns:
        op.drop_column("program_requirements", "deadlines")
