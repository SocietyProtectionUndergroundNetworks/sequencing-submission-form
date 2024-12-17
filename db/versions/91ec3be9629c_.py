"""

Revision ID: 91ec3be9629c
Revises: f9d2b21522f8
Create Date: 2024-12-17 10:51:30.960094

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "91ec3be9629c"
down_revision: Union[str, None] = "f9d2b21522f8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column(
        "sequencing_samples",
        sa.Column("Sample_type", sa.String(length=255), nullable=True),
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column("sequencing_samples", "Sample_type")
    # ### end Alembic commands ###
