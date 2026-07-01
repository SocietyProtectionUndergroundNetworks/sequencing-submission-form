"""Change project_id FK to integer in staging samples and photos

Revision ID: ec3d1ec91228
Revises: 084aaeb3501f
Create Date: 2026-07-01 07:01:17.107702

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = "ec3d1ec91228"
down_revision: Union[str, None] = "084aaeb3501f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- mobile_app_staging_samples ---
    op.add_column(
        "mobile_app_staging_samples",
        sa.Column("project_id_new", sa.Integer(), nullable=True),
    )
    op.execute(
        sa.text(
            "UPDATE mobile_app_staging_samples s "
            "JOIN mobile_app_projects p ON s.project_id = p.project_id "
            "SET s.project_id_new = p.id"
        )
    )
    op.drop_index(
        "idx_mss_project_id", table_name="mobile_app_staging_samples"
    )
    op.drop_column("mobile_app_staging_samples", "project_id")
    op.alter_column(
        "mobile_app_staging_samples",
        "project_id_new",
        new_column_name="project_id",
        existing_type=sa.Integer(),
        nullable=False,
    )
    op.create_index(
        "idx_mss_project_id", "mobile_app_staging_samples", ["project_id"]
    )
    op.create_foreign_key(
        "fk_mss_project_id",
        "mobile_app_staging_samples",
        "mobile_app_projects",
        ["project_id"],
        ["id"],
    )

    # --- mobile_app_staging_photos ---
    op.add_column(
        "mobile_app_staging_photos",
        sa.Column("project_id_new", sa.Integer(), nullable=True),
    )
    op.execute(
        sa.text(
            "UPDATE mobile_app_staging_photos ph "
            "JOIN mobile_app_projects p ON ph.project_id = p.project_id "
            "SET ph.project_id_new = p.id"
        )
    )
    op.drop_column("mobile_app_staging_photos", "project_id")
    op.alter_column(
        "mobile_app_staging_photos",
        "project_id_new",
        new_column_name="project_id",
        existing_type=sa.Integer(),
        nullable=True,
    )
    op.create_foreign_key(
        "fk_msph_project_id",
        "mobile_app_staging_photos",
        "mobile_app_projects",
        ["project_id"],
        ["id"],
    )


def downgrade() -> None:
    # --- mobile_app_staging_photos ---
    op.drop_constraint(
        "fk_msph_project_id", "mobile_app_staging_photos", type_="foreignkey"
    )
    op.add_column(
        "mobile_app_staging_photos",
        sa.Column("project_id_old", mysql.VARCHAR(length=36), nullable=True),
    )
    op.execute(
        sa.text(
            "UPDATE mobile_app_staging_photos ph "
            "JOIN mobile_app_projects p ON ph.project_id = p.id "
            "SET ph.project_id_old = p.project_id"
        )
    )
    op.drop_column("mobile_app_staging_photos", "project_id")
    op.alter_column(
        "mobile_app_staging_photos",
        "project_id_old",
        new_column_name="project_id",
        existing_type=mysql.VARCHAR(length=36),
        nullable=True,
    )

    # --- mobile_app_staging_samples ---
    op.drop_constraint(
        "fk_mss_project_id", "mobile_app_staging_samples", type_="foreignkey"
    )
    op.drop_index(
        "idx_mss_project_id", table_name="mobile_app_staging_samples"
    )
    op.add_column(
        "mobile_app_staging_samples",
        sa.Column("project_id_old", mysql.VARCHAR(length=36), nullable=True),
    )
    op.execute(
        sa.text(
            "UPDATE mobile_app_staging_samples s "
            "JOIN mobile_app_projects p ON s.project_id = p.id "
            "SET s.project_id_old = p.project_id"
        )
    )
    op.drop_column("mobile_app_staging_samples", "project_id")
    op.alter_column(
        "mobile_app_staging_samples",
        "project_id_old",
        new_column_name="project_id",
        existing_type=mysql.VARCHAR(length=36),
        nullable=False,
    )
    op.create_index(
        "idx_mss_project_id", "mobile_app_staging_samples", ["project_id"]
    )
