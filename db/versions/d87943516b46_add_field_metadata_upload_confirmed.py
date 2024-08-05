"""Add field metadata_upload_confirmed

Revision ID: d87943516b46
Revises: 69d49ce491bd
Create Date: 2024-07-18 13:27:53.496393

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "d87943516b46"
down_revision: Union[str, None] = "69d49ce491bd"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column(
        "sequencing_uploads",
        sa.Column("metadata_upload_confirmed", sa.Boolean(), nullable=True),
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column("sequencing_uploads", "metadata_upload_confirmed")
    # ### end Alembic commands ###
