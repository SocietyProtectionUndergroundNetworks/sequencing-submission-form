"""Add mobile_app_staging_samples table

Revision ID: a1b2c3d4e5f6
Revises: 141b0c54705d
Create Date: 2026-05-14

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "141b0c54705d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "mobile_app_staging_samples",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("sample_id", sa.String(length=100), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("project_name", sa.String(length=255), nullable=True),
        sa.Column("submitter_id", sa.String(length=255), nullable=False),
        sa.Column("date_collected", sa.Date(), nullable=False),
        sa.Column(
            "latitude", sa.Numeric(precision=10, scale=6), nullable=True
        ),
        sa.Column(
            "longitude", sa.Numeric(precision=10, scale=6), nullable=True
        ),
        sa.Column(
            "elevation", sa.Numeric(precision=8, scale=2), nullable=True
        ),
        sa.Column("sample_type", sa.String(length=50), nullable=True),
        sa.Column(
            "sample_or_control",
            sa.String(length=20),
            nullable=False,
            server_default="True sample",
        ),
        sa.Column("transport", sa.String(length=100), nullable=True),
        sa.Column("drying", sa.String(length=100), nullable=True),
        sa.Column("soil_depth", sa.String(length=20), nullable=True),
        sa.Column("grid_size", sa.String(length=20), nullable=True),
        sa.Column("land_use", sa.String(length=50), nullable=True),
        sa.Column("agricultural", sa.String(length=10), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "dna_concentration_ng_ul", sa.String(length=50), nullable=True
        ),
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
        "idx_mss_project_id", "mobile_app_staging_samples", ["project_id"]
    )
    op.create_index(
        "idx_mss_submitter_id", "mobile_app_staging_samples", ["submitter_id"]
    )
    op.create_index(
        "idx_mss_date_collected",
        "mobile_app_staging_samples",
        ["date_collected"],
    )


def downgrade() -> None:
    op.drop_index(
        "idx_mss_date_collected", table_name="mobile_app_staging_samples"
    )
    op.drop_index(
        "idx_mss_submitter_id", table_name="mobile_app_staging_samples"
    )
    op.drop_index(
        "idx_mss_project_id", table_name="mobile_app_staging_samples"
    )
    op.drop_table("mobile_app_staging_samples")
