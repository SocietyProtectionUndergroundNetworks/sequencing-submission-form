"""Drop version from user groups

Revision ID: a373ae470bb5
Revises: 1f188679f26e
Create Date: 2026-08-05 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a373ae470bb5"
down_revision: Union[str, None] = "1f188679f26e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("user_groups", "version")


def downgrade() -> None:
    op.add_column(
        "user_groups", sa.Column("version", sa.Integer(), nullable=True)
    )
