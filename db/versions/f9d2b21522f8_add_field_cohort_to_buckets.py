"""Add field cohort to buckets

Revision ID: f9d2b21522f8
Revises: 5155133ba4e4
Create Date: 2024-12-13 09:41:02.640966

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "f9d2b21522f8"
down_revision: Union[str, None] = "5155133ba4e4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column(
        "buckets", sa.Column("cohort", sa.String(length=255), nullable=True)
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column("buckets", "cohort")
    # ### end Alembic commands ###
