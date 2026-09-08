"""Alembic environment — how a migration finds the database and the models.

**The one idea in this file: there is exactly one source of truth for the
database URL, and it is not `alembic.ini`.**

The generated template reads `sqlalchemy.url` from the ini file. That would give
this project two places that name a database — `Settings.database_url` for the
application and the ini for migrations — and nothing keeping them in step. The
failure mode is quiet and nasty: `alembic upgrade head` reports success having
migrated a file the application never opens. So the URL is read from
`get_settings()` here, and the ini has no `sqlalchemy.url` key at all.

The same reasoning as `app/db/session.py` reading its URL from settings, applied
to the tool that changes the schema rather than the one that queries it.
"""

from __future__ import annotations

from logging.config import fileConfig

from sqlalchemy import create_engine, event, pool

from alembic import context

# Importing the models package is what populates `Base.metadata`. Without it
# autogenerate would compare the database against an empty metadata and
# cheerfully propose dropping all seventeen tables.
import app.models  # noqa: F401
from app.core.config import get_settings
from app.db.base import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

#: What `--autogenerate` compares the database against.
target_metadata = Base.metadata


def _database_url() -> str:
    """The database to migrate, in order of precedence.

    1. ``-x url=...`` on the command line — for an operator pointing one command
       at a specific file without exporting an environment variable and hoping it
       is picked up.
    2. ``config.attributes["url"]`` — the programmatic equivalent, used by
       ``app.db.migrate`` and by the migration tests, which run Alembic in-process
       against a throwaway database.
    3. ``Settings.database_url`` — what the application itself would open, and the
       answer in every ordinary run.

    Note what is *not* in this list: ``sqlalchemy.url`` from ``alembic.ini``. The
    ini deliberately has no such key, so there is no way to migrate one database
    while the app opens another.
    """
    overrides = context.get_x_argument(as_dictionary=True)
    if overrides.get("url"):
        return overrides["url"]
    return config.attributes.get("url") or get_settings().database_url


def _context_options() -> dict:
    """Options shared by offline and online runs.

    ``render_as_batch`` is the one that matters, and it is SQLite-specific.
    SQLite's ``ALTER TABLE`` can add a column and rename a table, and that is
    close to all — it cannot drop a column, change a type, or add or remove a
    constraint. Batch mode works around this the only way anyone can: create a
    new table with the desired shape, copy the rows across, drop the original
    and rename. Without it, any migration beyond "add a column" fails at runtime
    on the database this project actually uses.

    ``compare_type`` makes autogenerate notice a changed column type. It is off
    by default because it produces false positives on some backends; on SQLite,
    where types are advisory, a *missed* type change is the worse failure.
    """
    return {
        "target_metadata": target_metadata,
        "render_as_batch": True,
        "compare_type": True,
        # Alembic ignores this table when autogenerating, but naming it
        # explicitly documents where the version lives.
        "version_table": "alembic_version",
    }


def run_migrations_offline() -> None:
    """Emit SQL to stdout instead of running it.

    ``alembic upgrade head --sql`` produces a script a DBA can review before
    anything touches a real database. Not used in this project's workflow, and
    kept because it costs four lines and is the answer to "how would you run
    this against a database you are not allowed to connect to?".
    """
    context.configure(
        url=_database_url(),
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        **_context_options(),
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against a live connection."""
    url = _database_url()
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}

    # NullPool: a migration is a single short-lived connection, and pooling one
    # connection is pure overhead. It also means the file handle is released the
    # moment the migration finishes, which matters on Windows, where an open
    # handle stops a test from deleting its temporary database.
    connectable = create_engine(url, poolclass=pool.NullPool, connect_args=connect_args)

    @event.listens_for(connectable, "connect")
    def _enable_sqlite_foreign_keys(dbapi_connection, _record) -> None:
        """Enforce foreign keys during migrations too.

        SQLite disables them per connection. The application turns them on in
        `db/session.py`; a migration running without them could copy orphaned
        rows into a rebuilt table and call it a success.
        """
        if dbapi_connection.__class__.__module__.startswith("sqlite3"):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    with connectable.connect() as connection:
        context.configure(connection=connection, **_context_options())
        with context.begin_transaction():
            context.run_migrations()

    connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
