"""widen_sequencing_samples_notes_to_unlimited

Revision ID: 229bfb353632
Revises: 58855b6043b1
Create Date: 2026-08-27 10:05:20.572781

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "229bfb353632"
down_revision: Union[str, None] = "58855b6043b1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE sequencing_samples
        MODIFY COLUMN Notes
            TEXT CHARACTER SET utf8mb4
            COLLATE utf8mb4_unicode_ci
        ;
    """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE sequencing_samples
        MODIFY COLUMN Notes
            VARCHAR(255) CHARACTER SET utf8mb4
            COLLATE utf8mb4_unicode_ci
        ;
    """
    )
