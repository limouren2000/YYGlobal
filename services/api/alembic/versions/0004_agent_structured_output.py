"""Add validated structured output to Agent runs.

Revision ID: 0004_agent_structured_output
Revises: 0003_applications
"""

from typing import Optional, Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "0004_agent_structured_output"
down_revision: Optional[str] = "0003_applications"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("agent_runs")}
    if "structured_output" in columns:
        return
    op.add_column(
        "agent_runs",
        sa.Column("structured_output", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
    )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("agent_runs")}
    if "structured_output" in columns:
        op.drop_column("agent_runs", "structured_output")
