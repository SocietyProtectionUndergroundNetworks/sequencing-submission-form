"""Change goodgrands_slug to allow null

Revision ID: 89ecfd9d28e7
Revises: bf5b2663a7f5
Create Date: 2024-09-25 06:29:33.725544

"""

from typing import Sequence, Union

from alembic import op
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = "89ecfd9d28e7"
down_revision: Union[str, None] = "bf5b2663a7f5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column(
        "users",
        "goodgrands_slug",
        existing_type=mysql.VARCHAR(length=50),
        nullable=True,
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column(
        "users",
        "goodgrands_slug",
        existing_type=mysql.VARCHAR(length=50),
        nullable=False,
    )
    # ### end Alembic commands ###