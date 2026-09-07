"""Database initialisation: turn the model definitions into real tables.

``create_all`` reads ``Base.metadata`` — populated as a side effect of importing
``app.models`` — and emits ``CREATE TABLE IF NOT EXISTS`` for anything missing.

**Why ``create_all`` rather than Alembic migrations.** This is a 24-hour
assignment with a schema that is designed once and seeded from scratch; there is
no production data to preserve, so there is nothing for a migration history to
protect. ``create_all`` is one function call with no extra tooling.

**KNOWN LIMITATION, and the honest caveat:** ``create_all`` creates missing
tables. It does **not** alter existing ones. If a column is added to a model
later, the existing ``duolingo.db`` will not gain it — the file must be deleted
and re-seeded. Alembic is the migration path the moment the database holds
anything worth keeping.
"""

from sqlalchemy import Engine

import app.models  # noqa: F401  -- registers every model on Base.metadata
from app.db.base import Base
from app.db.session import engine as default_engine


def create_tables(engine: Engine | None = None) -> None:
    """Create every table that does not already exist.

    Args:
        engine: Optional engine override, used by tests to build the schema in a
            throwaway database instead of the development one.
    """
    Base.metadata.create_all(bind=engine or default_engine)
