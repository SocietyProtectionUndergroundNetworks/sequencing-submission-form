"""Add google related fields to users table

Revision ID: 538d8602afd3
Revises: ecac2e0feaf4
Create Date: 2023-12-14 13:45:41.197240

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = "538d8602afd3"
down_revision: Union[str, None] = "ecac2e0feaf4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column(
        "users", sa.Column("name", sa.String(length=255), nullable=False)
    )
    op.add_column(
        "users", sa.Column("email", sa.String(length=255), nullable=False)
    )
    op.add_column(
        "users",
        sa.Column("profile_pic", sa.String(length=255), nullable=False),
    )
    op.drop_column("users", "username")
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column(
        "users",
        sa.Column("username", mysql.VARCHAR(length=50), nullable=False),
    )
    op.drop_column("users", "profile_pic")
    op.drop_column("users", "email")
    op.drop_column("users", "name")
    # ### end Alembic commands ###
