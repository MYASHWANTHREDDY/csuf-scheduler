import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Attempt to read DATABASE_URL from environment (or backend/.env) so
# developers can keep DB config out of alembic.ini. If present, set
# the sqlalchemy.url option used below.
try:
    # prefer dotenv if available (backend/.env)
    from dotenv import load_dotenv

    # load .env in backend/ (this file lives under backend/ so the
    # repository root is one level up)
    env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
    if os.path.exists(env_path):
        load_dotenv(env_path)
except Exception:
    pass

# If DATABASE_URL is in the environment, use it to configure Alembic
db_url = os.getenv("DATABASE_URL")
if db_url:
    config.set_main_option("sqlalchemy.url", db_url)

# add your model's MetaData object here for 'autogenerate' support
# Import the application DB object and use its metadata so Alembic can
# detect model changes.
try:
    from backend.app.database import db

    # Import models so their Table objects are registered on the metadata
    try:
        import backend.app.models  # noqa: F401
    except Exception:
        # if models cannot be imported here, autogenerate may not see tables
        pass

    target_metadata = db.metadata
except Exception:
    # fallback if imports fail (leave target_metadata as None)
    target_metadata = None

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
