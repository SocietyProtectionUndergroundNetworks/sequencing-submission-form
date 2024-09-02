"""Remove combined primer_set fields

Revision ID: d5abe5bcee9a
Revises: 5a179c7c8604
Create Date: 2024-08-28 12:32:55.825892

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = "d5abe5bcee9a"
down_revision: Union[str, None] = "5a179c7c8604"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column("sequencing_uploads", "Primer_set_2")
    op.drop_column("sequencing_uploads", "Primer_set_1")
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column(
        "sequencing_uploads",
        sa.Column("Primer_set_1", mysql.VARCHAR(length=255), nullable=True),
    )
    op.add_column(
        "sequencing_uploads",
        sa.Column("Primer_set_2", mysql.VARCHAR(length=255), nullable=True),
    )
    # ### end Alembic commands ###