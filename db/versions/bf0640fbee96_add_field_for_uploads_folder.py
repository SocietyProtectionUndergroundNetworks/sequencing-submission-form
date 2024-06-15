"""Add field for uploads folder

Revision ID: bf0640fbee96
Revises: 3e00792d90db
Create Date: 2023-12-18 08:19:48.089280

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "bf0640fbee96"
down_revision: Union[str, None] = "3e00792d90db"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column(
        "uploads",
        sa.Column("uploads_folder", sa.String(length=20), nullable=True),
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column("uploads", "uploads_folder")
    # ### end Alembic commands ###
