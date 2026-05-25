"""Add mobile_app_staging_photos table

Revision ID: c2d3e4f5a6b7
Revises: b2c3d4e5f6a7
Create Date: 2026-05-25

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c2d3e4f5a6b7"
down_revision: Union[str, None] = "b2c3d4e5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "mobile_app_staging_photos",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("sample_id", sa.String(length=100), nullable=False),
        sa.Column("submitter_id", sa.String(length=255), nullable=False),
        sa.Column("file_path", sa.String(length=500), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=True),
        sa.Column(
            "received_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.PrimaryKeyConstraint("id"),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )
    op.create_index(
        "idx_msph_sample_id", "mobile_app_staging_photos", ["sample_id"]
    )
    op.create_index(
        "idx_msph_submitter_id", "mobile_app_staging_photos", ["submitter_id"]
    )


def downgrade() -> None:
    op.drop_index(
        "idx_msph_submitter_id", table_name="mobile_app_staging_photos"
    )
    op.drop_index("idx_msph_sample_id", table_name="mobile_app_staging_photos")
    op.drop_table("mobile_app_staging_photos")
