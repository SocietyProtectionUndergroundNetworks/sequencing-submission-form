"""Move sequencing_run to sequencer ids table

Revision ID: a72e6d642384
Revises: 493bbb939e03
Create Date: 2025-04-07 08:32:35.871368

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a72e6d642384"
down_revision: Union[str, None] = "493bbb939e03"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column(
        "sequencing_sequencer_ids",
        sa.Column("sequencing_run", sa.String(length=255), nullable=True),
    )
    # ### end Alembic commands ###

    # Use raw SQL to copy data before dropping the old column
    connection = op.get_bind()

    connection.execute(
        sa.text(
            """
        UPDATE sequencing_sequencer_ids AS ss, sequencing_samples AS sa
        SET ss.sequencing_run = sa.SequencingRun
        WHERE ss.sequencingSampleId = sa.id
        """
        )
    )


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column("sequencing_sequencer_ids", "sequencing_run")
    # ### end Alembic commands ###
