"""Remove v1 uploads table and references

Revision ID: 7806d577e603
Revises: 5f782f8dda38
Create Date: 2025-01-23 15:17:14.084214

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = '7806d577e603'
down_revision: Union[str, None] = '5f782f8dda38'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index('ix_uploads_fastqc_process_id', table_name='uploads')
    op.drop_table('uploads')
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('uploads',
    sa.Column('id', mysql.INTEGER(display_width=11), autoincrement=True, nullable=False),
    sa.Column('user_id', mysql.VARCHAR(length=36), nullable=True),
    sa.Column('created_at', mysql.DATETIME(), nullable=True),
    sa.Column('updated_at', mysql.DATETIME(), nullable=True),
    sa.Column('csv_uploaded', mysql.TINYINT(display_width=1), autoincrement=False, nullable=True),
    sa.Column('csv_filename', mysql.VARCHAR(length=255), nullable=True),
    sa.Column('uploads_folder', mysql.VARCHAR(length=20), nullable=True),
    sa.Column('files_renamed', mysql.TINYINT(display_width=1), autoincrement=False, nullable=True),
    sa.Column('files_json', mysql.JSON(), nullable=True),
    sa.Column('fastqc_run', mysql.TINYINT(display_width=1), autoincrement=False, nullable=True),
    sa.Column('fastqc_process_id', mysql.VARCHAR(length=255), nullable=True),
    sa.Column('fastqc_sent_to_bucket', mysql.TINYINT(display_width=1), autoincrement=False, nullable=True),
    sa.Column('renamed_sent_to_bucket', mysql.TINYINT(display_width=1), autoincrement=False, nullable=True),
    sa.Column('renamed_sent_to_bucket_progress', mysql.INTEGER(display_width=11), autoincrement=False, nullable=True),
    sa.Column('fastqc_files_progress', mysql.VARCHAR(length=255), nullable=True),
    sa.Column('gz_filedata', mysql.JSON(), nullable=True),
    sa.Column('sequencing_method', mysql.INTEGER(display_width=11), autoincrement=False, nullable=True),
    sa.Column('metadata_filename', mysql.VARCHAR(length=255), nullable=True),
    sa.Column('renaming_skipped', mysql.TINYINT(display_width=1), autoincrement=False, nullable=True),
    sa.Column('reviewed_by_admin', mysql.TINYINT(display_width=1), autoincrement=False, nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name='uploads_ibfk_1', ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    mysql_default_charset='latin1',
    mysql_engine='InnoDB'
    )
    op.create_index('ix_uploads_fastqc_process_id', 'uploads', ['fastqc_process_id'], unique=False)
    # ### end Alembic commands ###
