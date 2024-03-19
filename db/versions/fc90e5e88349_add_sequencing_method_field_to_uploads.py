"""Add sequencing method field to uploads

Revision ID: fc90e5e88349
Revises: 0a0ce67f6c21
Create Date: 2024-03-19 08:49:43.255505

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = 'fc90e5e88349'
down_revision: Union[str, None] = '0a0ce67f6c21'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('uploads', sa.Column('sequencing_method', sa.Integer(), nullable=True))
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('uploads', 'sequencing_method')
    # ### end Alembic commands ###