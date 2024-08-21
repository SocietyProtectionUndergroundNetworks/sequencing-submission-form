"""Add version to user groups

Revision ID: 252743430cc4
Revises: fad56b066c2b
Create Date: 2024-08-13 07:17:12.995732

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "252743430cc4"
down_revision: Union[str, None] = "fad56b066c2b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column(
        "user_groups", sa.Column("version", sa.Integer(), nullable=True)
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column("user_groups", "version")
    # ### end Alembic commands ###