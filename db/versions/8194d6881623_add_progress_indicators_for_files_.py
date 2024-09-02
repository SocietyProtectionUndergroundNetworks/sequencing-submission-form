"""Add progress indicators for files bucket uploads

Revision ID: 8194d6881623
Revises: 435c319f7b31
Create Date: 2024-08-27 09:49:47.325304

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "8194d6881623"
down_revision: Union[str, None] = "435c319f7b31"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column(
        "sequencing_files_uploaded",
        sa.Column("bucket_upload_progress", sa.Integer(), nullable=True),
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column("sequencing_files_uploaded", "bucket_upload_progress")
    # ### end Alembic commands ###