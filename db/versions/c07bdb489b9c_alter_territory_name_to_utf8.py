"""Alter territory_name to utf8

Revision ID: c07bdb489b9c
Revises: 9921085efd3c
Create Date: 2026-07-14 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "c07bdb489b9c"
down_revision: Union[str, None] = "9921085efd3c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE sequencing_uploads
        MODIFY COLUMN territory_name
            VARCHAR(255) CHARACTER SET utf8mb4
            COLLATE utf8mb4_unicode_ci
        ;
    """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE sequencing_uploads
        MODIFY COLUMN territory_name
            VARCHAR(255) CHARACTER SET latin1
            COLLATE latin1_swedish_ci
        ;
    """
    )
