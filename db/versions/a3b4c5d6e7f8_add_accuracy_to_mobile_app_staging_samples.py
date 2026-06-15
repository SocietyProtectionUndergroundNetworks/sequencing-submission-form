"""Add accuracy field to mobile_app_staging_samples

Revision ID: a3b4c5d6e7f8
Revises: 9ec3d957c178
Create Date: 2026-06-15 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a3b4c5d6e7f8"
down_revision: Union[str, None] = "9ec3d957c178"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "mobile_app_staging_samples",
        sa.Column(
            "accuracy", sa.Numeric(precision=10, scale=2), nullable=True
        ),
    )


def downgrade() -> None:
    op.drop_column("mobile_app_staging_samples", "accuracy")
