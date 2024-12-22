"""Add richness data per sample per analysis

Revision ID: ae6dd10d2e8d
Revises: 91ec3be9629c
Create Date: 2024-12-20 08:11:19.392204

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "ae6dd10d2e8d"
down_revision: Union[str, None] = "91ec3be9629c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table(
        "sequencing_analysis_sample_richness",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("analysis_id", sa.Integer(), nullable=False),
        sa.Column("sample_id", sa.Integer(), nullable=False),
        sa.Column("observed", sa.Float(), nullable=True),
        sa.Column("estimator", sa.Float(), nullable=True),
        sa.Column("est_s_e", sa.Float(), nullable=True),
        sa.Column("x95_percent_lower", sa.Float(), nullable=True),
        sa.Column("x95_percent_upper", sa.Float(), nullable=True),
        sa.Column("seq_depth", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["analysis_id"], ["sequencing_analysis.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["sample_id"], ["sequencing_samples.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table("sequencing_analysis_sample_richness")
    # ### end Alembic commands ###