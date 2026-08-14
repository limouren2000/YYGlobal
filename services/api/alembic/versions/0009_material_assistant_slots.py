"""add material assistant slots

Revision ID: 0009_material_assistant_slots
Revises: 0008_application_packages
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0009_material_assistant_slots"
down_revision: Union[str, None] = "0008_application_packages"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _add_column(table: str, column: sa.Column) -> None:
    inspector = sa.inspect(op.get_bind())
    if table in inspector.get_table_names() and column.name not in {
        item["name"] for item in inspector.get_columns(table)
    }:
        op.add_column(table, column)


def upgrade() -> None:
    _add_column("material_drafts", sa.Column("slot_key", sa.String(120), nullable=False, server_default=""))
    _add_column("conversations", sa.Column("program_id", sa.String(36), nullable=True))
    _add_column("conversations", sa.Column("slot_key", sa.String(120), nullable=False, server_default=""))
    _add_column("conversations", sa.Column("material_kind", sa.String(40), nullable=False, server_default=""))
    _add_column("conversations", sa.Column("resource_ids", sa.JSON(), nullable=False, server_default="[]"))


def downgrade() -> None:
    for table, columns in (
        ("conversations", ["resource_ids", "material_kind", "slot_key", "program_id"]),
        ("material_drafts", ["slot_key"]),
    ):
        inspector = sa.inspect(op.get_bind())
        existing = {item["name"] for item in inspector.get_columns(table)}
        for name in columns:
            if name in existing:
                op.drop_column(table, name)
