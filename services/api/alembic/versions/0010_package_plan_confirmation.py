"""add package plan confirmation

Revision ID: 0010_package_plan_confirmation
Revises: 0009_material_assistant_slots
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0010_package_plan_confirmation"
down_revision: Union[str, None] = "0009_material_assistant_slots"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "application_packages" in inspector.get_table_names() and "plan_confirmed" not in {
        item["name"] for item in inspector.get_columns("application_packages")
    }:
        op.add_column("application_packages", sa.Column("plan_confirmed", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "plan_confirmed" in {item["name"] for item in inspector.get_columns("application_packages")}:
        op.drop_column("application_packages", "plan_confirmed")
