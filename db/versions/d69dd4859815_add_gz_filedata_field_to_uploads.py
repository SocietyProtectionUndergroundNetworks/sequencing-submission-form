"""Add gz_filedata field to uploads

Revision ID: d69dd4859815
Revises: 2e43da21f4cd
Create Date: 2024-01-29 06:38:44.712786

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = "d69dd4859815"
down_revision: Union[str, None] = "2e43da21f4cd"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column(
        "uploads",
        sa.Column("gz_filedata", mysql.JSON(none_as_null=True), nullable=True),
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column("uploads", "gz_filedata")
    # ### end Alembic commands ###
