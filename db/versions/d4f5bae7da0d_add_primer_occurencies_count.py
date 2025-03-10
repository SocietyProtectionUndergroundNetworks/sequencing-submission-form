"""Add primer occurencies count

Revision ID: d4f5bae7da0d
Revises: 5fe4b35c88ff
Create Date: 2024-10-29 08:41:57.304303

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d4f5bae7da0d"
down_revision: Union[str, None] = "5fe4b35c88ff"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column(
        "sequencing_files_uploaded",
        sa.Column("primer_occurrences_count", sa.Integer(), nullable=True),
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column("sequencing_files_uploaded", "primer_occurrences_count")
    # ### end Alembic commands ###
