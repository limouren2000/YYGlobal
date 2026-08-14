"""add conversation pinning

Revision ID: 0011_conversation_pinning
Revises: 0010_package_plan_confirmation
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0011_conversation_pinning"
down_revision: Union[str, None] = "0010_package_plan_confirmation"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "conversations" in inspector.get_table_names() and "pinned" not in {
        item["name"] for item in inspector.get_columns("conversations")
    }:
        op.add_column(
            "conversations",
            sa.Column("pinned", sa.Boolean(), nullable=False, server_default=sa.false()),
        )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "conversations" in inspector.get_table_names() and "pinned" in {
        item["name"] for item in inspector.get_columns("conversations")
    }:
        op.drop_column("conversations", "pinned")
