"""Add metadata file to process

Revision ID: 68a8ad337a77
Revises: 86a0cb13428a
Create Date: 2024-04-11 10:49:26.858055

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = '68a8ad337a77'
down_revision: Union[str, None] = '86a0cb13428a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('uploads', sa.Column('metadata_filename', sa.String(length=255), nullable=True))
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('uploads', 'metadata_filename')
    # ### end Alembic commands ###