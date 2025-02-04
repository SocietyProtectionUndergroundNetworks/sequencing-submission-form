"""Create views for first and second file of each pair of files

Revision ID: 93d024d36b5f
Revises: 7806d577e603
Create Date: 2025-02-04 08:45:40.175540

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "93d024d36b5f"
down_revision: Union[str, None] = "7806d577e603"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE VIEW files_per_sequencer_first AS
        SELECT a.*
        FROM sequencing_files_uploaded a
        JOIN (
            SELECT sequencerId, MIN(original_filename) AS first_filename
            FROM sequencing_files_uploaded
            GROUP BY sequencerId
        ) b
        ON a.sequencerId = b.sequencerId
        AND a.original_filename = b.first_filename;
    """
    )

    op.execute(
        """
        CREATE VIEW files_per_sequencer_second AS
        SELECT a.*
        FROM sequencing_files_uploaded a
        JOIN (
            SELECT sequencerId, MIN(original_filename) AS first_filename
            FROM sequencing_files_uploaded
            GROUP BY sequencerId
        ) b ON a.sequencerId = b.sequencerId
        JOIN (
            SELECT sequencerId, MIN(original_filename) AS second_filename
            FROM sequencing_files_uploaded
            WHERE original_filename > (
                SELECT MIN(original_filename)
                FROM sequencing_files_uploaded t
                WHERE t.sequencerId = sequencing_files_uploaded.sequencerId
            )
            GROUP BY sequencerId
        ) c ON a.sequencerId = c.sequencerId
        AND a.original_filename = c.second_filename;
    """
    )


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS second_file_per_sequencer;")
    op.execute("DROP VIEW IF EXISTS first_file_per_sequencer;")
