import os
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context
from db.db_conn import get_database_uri

# Add your SQLAlchemy models' Base here
from models.db_model import Base  # Update the path as needed

# This is the Alembic Config object, which provides access to the values within the .ini file in use.
config = context.config
fileConfig(
    config.config_file_name
)  # Interpret the config file for Python logging

SQLALCHEMY_DATABASE_URI = get_database_uri()

# Set the SQLAlchemy URL in the Alembic context
config.set_main_option("sqlalchemy.url", SQLALCHEMY_DATABASE_URI)

# Add your models' metadata here if needed for autogenerate support
target_metadata = Base.metadata


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
