"""Database engine and session management.

One engine per process (it owns the connection pool), and a fresh Session per
unit of work. The ``get_db`` dependency is what FastAPI routes will use from
Phase 3 onwards; nothing consumes it yet.
"""

from collections.abc import Iterator

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

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


@event.listens_for(Engine, "connect")
def _enable_sqlite_foreign_keys(dbapi_connection, connection_record) -> None:
    """Turn on foreign key enforcement for every new SQLite connection.

    SQLite ships with foreign keys **disabled**, per connection, for backwards
    compatibility. Without this hook every ``ForeignKey`` in the models would be
    documentation only: the database would happily accept an exercise pointing at
    a lesson that does not exist. This is the single most important line in the
    file.
    """
    # Only SQLite understands this pragma; other backends enforce FKs natively.
    if dbapi_connection.__class__.__module__.startswith("sqlite3"):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


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
