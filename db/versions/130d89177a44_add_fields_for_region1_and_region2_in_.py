"""Add fields for Region1 and Region2 in Sequencing_uploads

Revision ID: 130d89177a44
Revises: c1283df0e46a
Create Date: 2024-11-11 09:50:22.626223

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "130d89177a44"
down_revision: Union[str, None] = "c1283df0e46a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column(
        "sequencing_uploads",
        sa.Column("region_1", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "sequencing_uploads",
        sa.Column("region_2", sa.String(length=255), nullable=True),
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column("sequencing_uploads", "region_2")
    op.drop_column("sequencing_uploads", "region_1")
    # ### end Alembic commands ###
