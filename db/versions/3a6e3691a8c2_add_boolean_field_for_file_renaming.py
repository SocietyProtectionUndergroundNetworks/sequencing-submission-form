"""Add boolean field for file renaming

Revision ID: 3a6e3691a8c2
Revises: b94ce0a40898
Create Date: 2023-12-20 07:17:25.593081

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "3a6e3691a8c2"
down_revision: Union[str, None] = "b94ce0a40898"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column("uploads", sa.Column("files_renamed", sa.Boolean(), nullable=True))
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column("uploads", "files_renamed")
    # ### end Alembic commands ###
