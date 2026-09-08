"""Database engine and session management.

One engine per process (it owns the connection pool), and a fresh Session per
unit of work. The ``get_db`` dependency is what FastAPI routes will use from
Phase 3 onwards; nothing consumes it yet.
"""

import logging
from collections.abc import Iterator

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

logger = logging.getLogger("app.db")

settings = get_settings()

# `check_same_thread=False` is required for SQLite under FastAPI: the framework
# runs synchronous endpoints in a threadpool, so a connection created on one
# thread may be used from another. SQLAlchemy's pool already serialises access,
# so lifting SQLite's own guard is safe here.
_connect_args = (
    {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
)

engine = create_engine(
    settings.database_url,
    echo=settings.database_echo,
    connect_args=_connect_args,
)


#: DBAPI modules that speak SQLite and therefore understand its pragmas.
#:
#: ``sqlite3`` is the standard library driver used locally and by the tests.
#: ``libsql_experimental`` is the driver behind the ``sqlite+libsql://`` dialect
#: used against Turso in production (ADR-81) — it is SQLite-compatible, so the
#: same pragma applies, but it is a *different module* and so would not have
#: matched a check for "sqlite3" alone.
_SQLITE_DBAPI_MODULES = ("sqlite3", "libsql")


@event.listens_for(Engine, "connect")
def _enable_sqlite_foreign_keys(dbapi_connection, connection_record) -> None:
    """Turn on foreign key enforcement for every new SQLite connection.

    SQLite ships with foreign keys **disabled**, per connection, for backwards
    compatibility. Without this hook every ``ForeignKey`` in the models would be
    documentation only: the database would happily accept an exercise pointing at
    a lesson that does not exist. This is the single most important line in the
    file.

    **Phase 10.3 widened the guard, and that was a real bug rather than a
    tidy-up.** It used to read ``startswith("sqlite3")``, which is the standard
    library driver's module name. The libSQL driver's connections come from
    ``libsql_experimental``, so against Turso the condition would have been false,
    the pragma would never have been sent, and **foreign keys would have been
    silently unenforced in production** — the worst possible shape for a bug:
    invisible, data-corrupting, and only in the environment that matters.

    The pragma is attempted rather than assumed. A driver that does not accept it
    must not stop the application from starting, and a backend that enforces
    foreign keys natively does not need it — so a failure here is logged at debug
    level and ignored.
    """
    module = dbapi_connection.__class__.__module__
    if not any(module.startswith(name) for name in _SQLITE_DBAPI_MODULES):
        return

    try:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
    except Exception:  # pragma: no cover - driver-specific, not reachable locally
        # **KNOWN LIMITATION.** Whether a hosted libSQL/Turso endpoint honours a
        # per-connection `PRAGMA foreign_keys` has not been verified against a
        # live Turso database from this repository — see §16.10. If it does not,
        # the constraints still exist in the schema but are not enforced at
        # write time, and that must be checked in production rather than assumed.
        logger.debug("Could not enable foreign keys on this connection", exc_info=True)


SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    """Yield a database session and guarantee it is closed.

    FastAPI dependency, unused until Phase 3. The ``finally`` block returns the
    connection to the pool even if the endpoint raises, which is what stops a
    long-running server from leaking connections.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
