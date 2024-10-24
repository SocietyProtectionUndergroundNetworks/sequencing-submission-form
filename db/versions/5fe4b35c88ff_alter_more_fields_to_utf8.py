"""Alter more fields to utf8

Revision ID: 5fe4b35c88ff
Revises: 0b8b066176ec
Create Date: 2024-10-24 11:49:31.559385

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5fe4b35c88ff'
down_revision: Union[str, None] = '0b8b066176ec'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE sequencing_samples
        MODIFY COLUMN Site_name
            VARCHAR(255) CHARACTER SET utf8mb4
            COLLATE utf8mb4_unicode_ci,
        MODIFY COLUMN Notes
            VARCHAR(255) CHARACTER SET utf8mb4
            COLLATE utf8mb4_unicode_ci
        ;
    """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE sequencing_samples
        MODIFY COLUMN Site_name
            VARCHAR(255) CHARACTER SET utf8mb4
            COLLATE utf8mb4_unicode_ci,
        MODIFY COLUMN Notes
            VARCHAR(255) CHARACTER SET utf8mb4
            COLLATE utf8mb4_unicode_ci
        ;
    """
    )
