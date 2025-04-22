import asyncio
from logging.config import fileConfig

from sqlalchemy.ext.asyncio import create_async_engine
from alembic import context

from models import Base  # Import your Base from where models are defined

# Alembic config object
config = context.config

# Setup Python logging
fileConfig(config.config_file_name)

# Set your metadata for 'autogenerate'
target_metadata = Base.metadata


def run_migrations_offline():
    """Run migrations in offline mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online():
    connectable = create_async_engine(
        config.get_main_option("sqlalchemy.url"),
        future=True,
    )

    async with connectable.connect() as connection:
        # Run Alembic context inside a sync-compatible wrapper
        def do_migrations(sync_connection):
            context.configure(
                connection=sync_connection,
                target_metadata=target_metadata,
                compare_type=True,
                compare_server_default=True,
            )

            with context.begin_transaction():  # ❗️THIS is sync
                context.run_migrations()

        await connection.run_sync(do_migrations)  # Proper async->sync wrapping


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
