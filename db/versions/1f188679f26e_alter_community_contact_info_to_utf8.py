"""Alter community_contact_info to utf8

Revision ID: 1f188679f26e
Revises: c4976f64b5f3
Create Date: 2026-07-14 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "1f188679f26e"
down_revision: Union[str, None] = "c4976f64b5f3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE sequencing_uploads
        MODIFY COLUMN community_contact_info
            VARCHAR(255) CHARACTER SET utf8mb4
            COLLATE utf8mb4_unicode_ci
        ;
    """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE sequencing_uploads
        MODIFY COLUMN community_contact_info
            VARCHAR(255) CHARACTER SET latin1
            COLLATE latin1_swedish_ci
        ;
    """
    )
