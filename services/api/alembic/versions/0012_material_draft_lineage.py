"""add material draft lineage source

Revision ID: 0012_material_draft_lineage
Revises: 0011_conversation_pinning
"""

from typing import Sequence, Union
from collections import defaultdict

import sqlalchemy as sa
from alembic import op

revision: str = "0012_material_draft_lineage"
down_revision: Union[str, None] = "0011_conversation_pinning"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "material_drafts" in inspector.get_table_names() and "derived_from_id" not in {
        item["name"] for item in inspector.get_columns("material_drafts")
    }:
        op.add_column("material_drafts", sa.Column("derived_from_id", sa.String(36), nullable=True))
    drafts = sa.table(
        "material_drafts",
        sa.column("id", sa.String),
        sa.column("root_id", sa.String),
        sa.column("parent_id", sa.String),
        sa.column("version_number", sa.Integer),
        sa.column("revision_type", sa.String),
        sa.column("model_info", sa.JSON),
        sa.column("created_at", sa.DateTime),
    )
    rows = list(op.get_bind().execute(sa.select(drafts)).mappings())
    groups = defaultdict(list)
    for row in rows:
        model_info = row["model_info"] or {}
        conversation_id = model_info.get("conversation_id") if isinstance(model_info, dict) else None
        if conversation_id:
            groups[str(conversation_id)].append(row)
    for group in groups.values():
        if len(group) < 2:
            continue
        ordered = sorted(group, key=lambda row: (row["created_at"], row["id"]))
        root_id = ordered[0]["root_id"] or ordered[0]["id"]
        previous_id = None
        for index, row in enumerate(ordered, start=1):
            revision_type = row["revision_type"]
            if index > 1 and revision_type == "generated":
                revision_type = "ai_revision"
            op.get_bind().execute(
                drafts.update().where(drafts.c.id == row["id"]).values(
                    root_id=root_id,
                    parent_id=previous_id,
                    version_number=index,
                    revision_type=revision_type,
                )
            )
            previous_id = row["id"]


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "material_drafts" in inspector.get_table_names() and "derived_from_id" in {
        item["name"] for item in inspector.get_columns("material_drafts")
    }:
        op.drop_column("material_drafts", "derived_from_id")
