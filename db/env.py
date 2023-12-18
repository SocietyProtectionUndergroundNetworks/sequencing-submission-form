import os
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context

# Add your SQLAlchemy models' Base here
from models.db_model import Base  # Update the path as needed

# This is the Alembic Config object, which provides access to the values within the .ini file in use.
config = context.config
fileConfig(config.config_file_name)  # Interpret the config file for Python logging

# You can set the URL directly here using the environment variables
DB_USER = os.environ['MYSQL_USER']
DB_PASSWORD =os.environ['MYSQL_PASSWORD']
DB_HOST = os.environ['MYSQL_HOST']
DB_PORT = os.environ['MYSQL_PORT']
DB_NAME = os.environ['MYSQL_DATABASE']

SQLALCHEMY_DATABASE_URI = f'mysql+mysqldb://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}?charset=utf8mb4'

# Set the SQLAlchemy URL in the Alembic context
config.set_main_option('sqlalchemy.url', SQLALCHEMY_DATABASE_URI)

# Add your models' metadata here if needed for autogenerate support
target_metadata = Base.metadata


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix='sqlalchemy.',
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