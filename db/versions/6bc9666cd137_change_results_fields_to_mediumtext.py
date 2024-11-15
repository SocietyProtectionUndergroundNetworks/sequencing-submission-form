"""Change results fields to mediumtext

Revision ID: 6bc9666cd137
Revises: 5d5d9afb7820
Create Date: 2024-11-15 11:21:15.075762

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = '6bc9666cd137'
down_revision: Union[str, None] = '5d5d9afb7820'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column('sequencing_analysis', 'lotus2_result',
               existing_type=mysql.TEXT(charset='utf8mb4', collation='utf8mb4_unicode_ci'),
               type_=mysql.MEDIUMTEXT(charset='utf8mb4', collation='utf8mb4_unicode_ci'),
               existing_nullable=True)
    op.alter_column('sequencing_analysis', 'rscripts_result',
               existing_type=mysql.TEXT(charset='utf8mb4', collation='utf8mb4_unicode_ci'),
               type_=mysql.MEDIUMTEXT(charset='utf8mb4', collation='utf8mb4_unicode_ci'),
               existing_nullable=True)
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column('sequencing_analysis', 'rscripts_result',
               existing_type=mysql.MEDIUMTEXT(charset='utf8mb4', collation='utf8mb4_unicode_ci'),
               type_=mysql.TEXT(charset='utf8mb4', collation='utf8mb4_unicode_ci'),
               existing_nullable=True)
    op.alter_column('sequencing_analysis', 'lotus2_result',
               existing_type=mysql.MEDIUMTEXT(charset='utf8mb4', collation='utf8mb4_unicode_ci'),
               type_=mysql.TEXT(charset='utf8mb4', collation='utf8mb4_unicode_ci'),
               existing_nullable=True)
    # ### end Alembic commands ###
