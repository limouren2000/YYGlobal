"""make material drafts immutable version chains

Revision ID: 0007_material_draft_versions
Revises: 0006_material_drafts
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "0007_material_draft_versions"
down_revision: Union[str, None] = "0006_material_drafts"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("material_drafts")}
    additions = {
        "parent_id": sa.Column("parent_id", sa.String(36), nullable=True),
        "root_id": sa.Column("root_id", sa.String(36), nullable=True),
        "version_number": sa.Column(
            "version_number", sa.Integer(), nullable=False, server_default="1"
        ),
        "revision_type": sa.Column(
            "revision_type", sa.String(30), nullable=False, server_default="generated"
        ),
        "change_summary": sa.Column(
            "change_summary", sa.Text(), nullable=False, server_default="首次生成"
        ),
    }
    for name, column in additions.items():
        if name not in columns:
            op.add_column("material_drafts", column)

    inspector = sa.inspect(bind)
    foreign_keys = inspector.get_foreign_keys("material_drafts")
    has_parent_fk = any(
        item.get("constrained_columns") == ["parent_id"]
        and item.get("referred_table") == "material_drafts"
        and item.get("referred_columns") == ["id"]
        for item in foreign_keys
    )
    if not has_parent_fk:
        op.create_foreign_key(
            "fk_material_drafts_parent",
            "material_drafts",
            "material_drafts",
            ["parent_id"],
            ["id"],
        )
    indexes = {item["name"] for item in inspector.get_indexes("material_drafts")}
    if "ix_material_drafts_parent_id" not in indexes:
        op.create_index("ix_material_drafts_parent_id", "material_drafts", ["parent_id"])
    if "ix_material_drafts_root_id" not in indexes:
        op.create_index("ix_material_drafts_root_id", "material_drafts", ["root_id"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    indexes = {item["name"] for item in inspector.get_indexes("material_drafts")}
    if "ix_material_drafts_root_id" in indexes:
        op.drop_index("ix_material_drafts_root_id", table_name="material_drafts")
    if "ix_material_drafts_parent_id" in indexes:
        op.drop_index("ix_material_drafts_parent_id", table_name="material_drafts")
    parent_fk = next(
        (
            item
            for item in inspector.get_foreign_keys("material_drafts")
            if item.get("constrained_columns") == ["parent_id"]
            and item.get("referred_table") == "material_drafts"
            and item.get("referred_columns") == ["id"]
        ),
        None,
    )
    if parent_fk and parent_fk.get("name"):
        op.drop_constraint(parent_fk["name"], "material_drafts", type_="foreignkey")
    columns = {column["name"] for column in sa.inspect(bind).get_columns("material_drafts")}
    for name in ["change_summary", "revision_type", "version_number", "root_id", "parent_id"]:
        if name in columns:
            op.drop_column("material_drafts", name)
