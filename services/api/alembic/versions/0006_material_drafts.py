"""add editable full CV and PS drafts

Revision ID: 0006_material_drafts
Revises: 0005_requirement_deadlines
"""

from datetime import datetime, timezone
from typing import Sequence, Union
from uuid import uuid4

import sqlalchemy as sa

from alembic import op

revision: str = "0006_material_drafts"
down_revision: Union[str, None] = "0005_requirement_deadlines"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if inspector.has_table("material_drafts"):
        return
    op.create_table(
        "material_drafts",
        sa.Column("id", sa.String(36), primary_key=True, default=lambda: str(uuid4())),
        sa.Column("owner_id", sa.String(64), nullable=False),
        sa.Column("program_id", sa.String(36), sa.ForeignKey("programs.id"), nullable=True),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("title", sa.String(240), nullable=False),
        sa.Column("language", sa.String(40), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("source_experience_ids", sa.JSON(), nullable=False, default=list),
        sa.Column("warnings", sa.JSON(), nullable=False, default=list),
        sa.Column("model_info", sa.JSON(), nullable=False, default=dict),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)),
    )
    op.create_index("ix_material_drafts_owner_id", "material_drafts", ["owner_id"])
    op.create_index("ix_material_drafts_program_id", "material_drafts", ["program_id"])
    op.create_index("ix_material_drafts_kind", "material_drafts", ["kind"])
    op.create_index("ix_material_drafts_status", "material_drafts", ["status"])


def downgrade() -> None:
    if sa.inspect(op.get_bind()).has_table("material_drafts"):
        op.drop_table("material_drafts")
