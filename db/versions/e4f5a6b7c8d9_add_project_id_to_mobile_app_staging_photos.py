"""Add project_id to mobile_app_staging_photos

Revision ID: e4f5a6b7c8d9
Revises: d3e4f5a6b7c8
Create Date: 2026-05-25

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e4f5a6b7c8d9"
down_revision: Union[str, None] = "d3e4f5a6b7c8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "mobile_app_staging_photos",
        sa.Column("project_id", sa.String(length=36), nullable=True),
    )
    op.create_index(
        "idx_msph_project_id", "mobile_app_staging_photos", ["project_id"]
    )


def downgrade() -> None:
    op.drop_index("idx_msph_project_id", table_name="mobile_app_staging_photos")
    op.drop_column("mobile_app_staging_photos", "project_id")
