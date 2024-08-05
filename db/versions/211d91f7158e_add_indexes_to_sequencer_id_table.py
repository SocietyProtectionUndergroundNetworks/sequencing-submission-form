"""Add indexes to sequencer_id table

Revision ID: 211d91f7158e
Revises: 6f8b52b20365
Create Date: 2024-07-24 13:52:37.630334

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "211d91f7158e"
down_revision: Union[str, None] = "6f8b52b20365"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column(
        "sequencing_sequencer_ids",
        sa.Column("Index_1", sa.String(length=100), nullable=True),
    )
    op.add_column(
        "sequencing_sequencer_ids",
        sa.Column("Index_2", sa.String(length=100), nullable=True),
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column("sequencing_sequencer_ids", "Index_2")
    op.drop_column("sequencing_sequencer_ids", "Index_1")
    # ### end Alembic commands ###
