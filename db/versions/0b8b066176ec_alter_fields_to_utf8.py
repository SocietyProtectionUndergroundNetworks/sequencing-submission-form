"""Alter fields to UTF8

Revision ID: 0b8b066176ec
Revises: 5dd8630d2291
Create Date: 2024-10-11 07:13:29.143316

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0b8b066176ec"
down_revision: Union[str, None] = "5dd8630d2291"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE sequencing_uploads
        MODIFY COLUMN Expedition_lead VARCHAR(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
        MODIFY COLUMN Sequencing_facility VARCHAR(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
        MODIFY COLUMN Collaborators VARCHAR(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci, 
        MODIFY COLUMN region_1_lotus2_report_result TEXT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
        MODIFY COLUMN region_2_lotus2_report_result TEXT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
        ;
    """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE sequencing_uploads
        MODIFY COLUMN Expedition_lead VARCHAR(255) CHARACTER SET latin1 COLLATE latin1_swedish_ci,
        MODIFY COLUMN Sequencing_facility VARCHAR(255) CHARACTER SET latin1 COLLATE latin1_swedish_ci,
        MODIFY COLUMN Collaborators VARCHAR(255) CHARACTER SET latin1 COLLATE latin1_swedish_ci,
        MODIFY COLUMN region_1_lotus2_report_result TEXT CHARACTER SET latin1 COLLATE latin1_swedish_ci,
        MODIFY COLUMN region_2_lotus2_report_result TEXT CHARACTER SET latin1 COLLATE latin1_swedish_ci  
        ;
    """
    )
