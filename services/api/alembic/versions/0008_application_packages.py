"""add per-program application packages

Revision ID: 0008_application_packages
Revises: 0007_material_draft_versions
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "0008_application_packages"
down_revision: Union[str, None] = "0007_material_draft_versions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if sa.inspect(op.get_bind()).has_table("application_packages"):
        return
    op.create_table(
        "application_packages",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("owner_id", sa.String(64), nullable=False),
        sa.Column("program_id", sa.String(36), sa.ForeignKey("programs.id"), nullable=False),
        sa.Column("shortlist_id", sa.String(36), sa.ForeignKey("shortlists.id"), nullable=True),
        sa.Column("official_verified", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("checklist", sa.JSON(), nullable=False),
        sa.Column("gaps", sa.JSON(), nullable=False),
        sa.Column("ready", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("owner_id", "program_id", name="uq_application_package_owner_program"),
    )
    for name in ["owner_id", "program_id", "shortlist_id", "ready"]:
        op.create_index(f"ix_application_packages_{name}", "application_packages", [name])


def downgrade() -> None:
    if sa.inspect(op.get_bind()).has_table("application_packages"):
        op.drop_table("application_packages")
