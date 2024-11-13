"""Add tracking fields for rscripts analysis and rename lotus2 analysis fields

Revision ID: 5d5d9afb7820
Revises: bbd5fb21ff61
Create Date: 2024-11-13 14:24:29.681011

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "5d5d9afb7820"
down_revision: Union[str, None] = "bbd5fb21ff61"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Rename the existing columns with specified types and UTF-8 charset
    op.alter_column(
        "sequencing_analysis",
        "status",
        new_column_name="lotus2_status",
        type_=sa.String(length=255, collation="utf8mb4_unicode_ci"),
    )
    op.alter_column(
        "sequencing_analysis",
        "celery_task_id",
        new_column_name="lotus2_celery_task_id",
        type_=sa.String(length=255, collation="utf8mb4_unicode_ci"),
    )
    op.alter_column(
        "sequencing_analysis",
        "result",
        new_column_name="lotus2_result",
        type_=sa.Text(collation="utf8mb4_unicode_ci"),
    )

    # Add the new columns with UTF-8 charset where applicable
    op.add_column(
        "sequencing_analysis",
        sa.Column("lotus2_started_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "sequencing_analysis",
        sa.Column("lotus2_finished_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "sequencing_analysis",
        sa.Column("rscripts_started_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "sequencing_analysis",
        sa.Column("rscripts_finished_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "sequencing_analysis",
        sa.Column(
            "rscripts_celery_task_id",
            sa.String(length=255, collation="utf8mb4_unicode_ci"),
            nullable=True,
        ),
    )
    op.add_column(
        "sequencing_analysis",
        sa.Column(
            "rscripts_status",
            sa.String(length=255, collation="utf8mb4_unicode_ci"),
            nullable=True,
        ),
    )
    op.add_column(
        "sequencing_analysis",
        sa.Column(
            "rscripts_result",
            sa.Text(collation="utf8mb4_unicode_ci"),
            nullable=True,
        ),
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    # Downgrade: rename the columns back to their original
    # names with specified types and UTF-8 charset
    op.alter_column(
        "sequencing_analysis",
        "lotus2_status",
        new_column_name="status",
        type_=sa.String(length=255, collation="utf8mb4_unicode_ci"),
    )
    op.alter_column(
        "sequencing_analysis",
        "lotus2_celery_task_id",
        new_column_name="celery_task_id",
        type_=sa.String(length=255, collation="utf8mb4_unicode_ci"),
    )
    op.alter_column(
        "sequencing_analysis",
        "lotus2_result",
        new_column_name="result",
        type_=sa.Text(collation="utf8mb4_unicode_ci"),
    )

    # Downgrade: drop the columns that were added in the upgrade
    op.drop_column("sequencing_analysis", "lotus2_started_at")
    op.drop_column("sequencing_analysis", "lotus2_finished_at")
    op.drop_column("sequencing_analysis", "rscripts_started_at")
    op.drop_column("sequencing_analysis", "rscripts_finished_at")
    op.drop_column("sequencing_analysis", "rscripts_celery_task_id")
    op.drop_column("sequencing_analysis", "rscripts_status")
    op.drop_column("sequencing_analysis", "rscripts_result")
