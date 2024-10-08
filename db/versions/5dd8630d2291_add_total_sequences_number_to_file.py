"""Add total sequences number to file

Revision ID: 5dd8630d2291
Revises: 37f6fa13f2eb
Create Date: 2024-10-07 13:05:37.175208

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "5dd8630d2291"
down_revision: Union[str, None] = "37f6fa13f2eb"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column(
        "sequencing_files_uploaded",
        sa.Column("total_sequences_number", sa.Integer(), nullable=True),
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column("sequencing_files_uploaded", "total_sequences_number")
    # ### end Alembic commands ###
