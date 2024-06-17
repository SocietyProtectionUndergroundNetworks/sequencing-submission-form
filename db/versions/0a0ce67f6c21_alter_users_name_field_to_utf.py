"""Alter users name field to utf

Revision ID: 0a0ce67f6c21
Revises: f213796342df
Create Date: 2024-03-14 08:45:37.640058

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0a0ce67f6c21"
down_revision: Union[str, None] = "f213796342df"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        table_name="users",
        column_name="name",
        type_=sa.String(255, collation="utf8_general_ci"),
        existing_nullable=False,
        existing_type=sa.String(collation="utf8_general_ci"),
    )


def downgrade() -> None:
    pass
