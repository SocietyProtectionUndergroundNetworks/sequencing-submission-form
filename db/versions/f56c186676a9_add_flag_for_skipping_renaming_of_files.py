"""Add flag for skipping renaming of files

Revision ID: f56c186676a9
Revises: 2ebf9ccc05cd
Create Date: 2024-05-01 09:25:33.067754

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = "f56c186676a9"
down_revision: Union[str, None] = "2ebf9ccc05cd"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column("uploads", sa.Column("renaming_skipped", sa.Boolean(), nullable=True))
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column("uploads", "renaming_skipped")
    # ### end Alembic commands ###
