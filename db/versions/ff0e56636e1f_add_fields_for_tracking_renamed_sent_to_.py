"""Add fields for tracking renamed sent to bucket

Revision ID: ff0e56636e1f
Revises: c6545a0647e6
Create Date: 2024-01-17 14:54:51.320235

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ff0e56636e1f'
down_revision: Union[str, None] = 'c6545a0647e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('uploads', sa.Column('renamed_sent_to_bucket', sa.Boolean(), nullable=True))
    op.add_column('uploads', sa.Column('renamed_sent_to_bucket_progress', sa.Integer(), nullable=True))
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('uploads', 'renamed_sent_to_bucket_progress')
    op.drop_column('uploads', 'renamed_sent_to_bucket')
    # ### end Alembic commands ###