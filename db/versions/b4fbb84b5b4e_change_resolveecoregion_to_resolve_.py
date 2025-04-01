"""Change ResolveEcoregion to resolve_ecoregion_id

Revision ID: b4fbb84b5b4e
Revises: 4c598b1536be
Create Date: 2025-02-25 09:42:55.487121

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = "b4fbb84b5b4e"
down_revision = "4c598b1536be"
branch_labels = None
depends_on = None


def upgrade():
    # Add the new column first
    op.add_column(
        "sequencing_samples",
        sa.Column("resolve_ecoregion_id", sa.Integer(), nullable=True),
    )

    # Use raw SQL to copy data before dropping the old column
    connection = op.get_bind()

    connection.execute(
        sa.text(
            """
        UPDATE sequencing_samples ss
        JOIN resolve_ecoregions re ON ss.ResolveEcoregion = re.ecoregion_name
        SET ss.resolve_ecoregion_id = re.id
        """
        )
    )

    # Now, create the foreign key constraint
    op.create_foreign_key(
        "fk_sequencing_samples_ecoregion",
        "sequencing_samples",
        "resolve_ecoregions",
        ["resolve_ecoregion_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # Finally, drop the old column
    op.drop_column("sequencing_samples", "ResolveEcoregion")


def downgrade():
    # Re-add the old column
    op.add_column(
        "sequencing_samples",
        sa.Column("ResolveEcoregion", sa.String(length=255), nullable=True),
    )

    # Use raw SQL to restore data
    connection = op.get_bind()
    connection.execute(
        sa.text(
            """
        UPDATE sequencing_samples ss
        JOIN resolve_ecoregions re ON ss.resolve_ecoregion_id = re.id
        SET ss.ResolveEcoregion = re.ecoregion_name
        """
        )
    )

    # Drop the foreign key constraint
    op.drop_constraint(
        "fk_sequencing_samples_ecoregion",
        "sequencing_samples",
        type_="foreignkey",
    )

    # Drop the new column
    op.drop_column("sequencing_samples", "resolve_ecoregion_id")
