"""The one command that brings any database up to date.

    python -m app.db.migrate

**What changed in Phase 10.** Through Phase 9.5 this file *was* the migration
system: a hand-written script that re-inspected the schema on every run and
applied whatever it found missing. Phase 10 hands that job to Alembic and leaves
this module as the thing that knows how to get an *existing* database onto the
Alembic timeline without losing a row.

The three cases it handles, and why each exists:

1. **Empty database** — no tables at all. Run ``alembic upgrade head``. This is
   what a fresh clone gets.

2. **Legacy database** — tables, but no ``alembic_version``. Every database
   created before Phase 10 is in this state, including the developer's own
   ``duolingo.db`` with real practice progress in it. It is *repaired* to the
   Phase 9.5 shape by the frozen fixups below, *verified* against the models,
   and then **stamped** at the baseline revision — which writes a version row
   and executes no DDL. That is the whole trick of adopting a migration tool
   against data that already exists: you tell it where you are, rather than
   asking it to build what is already there.

3. **Managed database** — has ``alembic_version``. Run ``alembic upgrade head``.
   From here on this is the only case that will ever run.

**Nothing in this file drops, rewrites or deletes a row**, and the whole thing is
idempotent: run it twice and the second run reports "already up to date".

**The legacy fixups are frozen.** They exist to carry pre-Phase-10 databases onto
the timeline and will never grow another step. A schema change from now on is::

    alembic revision -m "what changed"      # then write upgrade() and downgrade()
    alembic upgrade head

See ADR-73 for why Alembic is justified now when it was deliberately deferred
before.
"""

from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

import app.models  # noqa: F401  -- registers every model on Base.metadata
from app.core.config import get_settings
from app.db.base import Base
from app.db.session import engine as default_engine

#: The revision that represents the complete Phase 9.5 schema. A legacy database
#: is stamped here, because that is exactly the shape it is already in.
BASELINE_REVISION = "0001"

# backend/app/db/migrate.py -> backend/
BACKEND_DIR = Path(__file__).resolve().parents[2]


def alembic_config(database_url: str | None = None) -> Config:
    """Build an Alembic config pointed at this project.

    The URL is handed over as a config *attribute* rather than written into
    ``alembic.ini``, for the reason spelled out in ``alembic/env.py``: one source
    of truth for which database is being touched. Left as ``None`` it resolves to
    the application's own ``Settings.database_url``.
    """
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    # Absolute, so `migrate()` works no matter which directory the process was
    # started from — the same reasoning as the absolute default DATABASE_URL.
    config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    if database_url:
        # `attributes` rather than `sqlalchemy.url`: env.py reads it explicitly,
        # and the ini stays free of a second place that names a database.
        config.attributes["url"] = database_url
    return config


def current_revision(engine: Engine) -> str | None:
    """The revision this database is stamped at, or ``None`` if unmanaged."""
    with engine.connect() as connection:
        return MigrationContext.configure(connection).get_current_revision()


def _table_names(engine: Engine) -> set[str]:
    return set(inspect(engine).get_table_names())


def _columns(connection, table: str) -> set[str]:
    return {row[1] for row in connection.execute(text(f"PRAGMA table_info({table})"))}


# --------------------------------------------------------------------------
# Legacy repair — frozen. Do not add to this.
# --------------------------------------------------------------------------


def _repair_legacy_schema(engine: Engine) -> None:
    """Bring a pre-Phase-10 database up to the Phase 9.5 shape.

    These are the two ``ALTER TABLE`` steps that used to live in this module as
    the whole migration story — Phase 9's credential columns and Phase 9.5's
    ``placed_out_at``. They are kept, unchanged in behaviour, because a database
    sitting at the Phase 8 schema still needs them before it can honestly be
    stamped at the Phase 9.5 baseline.

    Every step is guarded by a column check, so this is a no-op on any database
    that is already current — which is the common case, and why running it before
    stamping costs nothing.
    """
    settings = get_settings()

    # Missing *tables* first. A database left at the Phase 8 schema has no
    # `sessions`, `lesson_attempt_pairs`, `user_onboarding` or `placement_*`, and
    # `create_all` adds exactly those without touching anything that exists —
    # which is precisely what the pre-Phase-10 script did as its first step. It
    # is kept so adopting an older database still works, rather than being
    # refused by the baseline check below.
    Base.metadata.create_all(bind=engine)

    tables = _table_names(engine)

    if "user_skill_progress" in tables:
        with engine.begin() as connection:
            if "placed_out_at" not in _columns(connection, "user_skill_progress"):
                connection.execute(
                    text(
                        "ALTER TABLE user_skill_progress ADD COLUMN placed_out_at DATETIME"
                    )
                )
                print("  legacy repair: user_skill_progress.placed_out_at added")

    if "users" not in tables:
        return

    with engine.begin() as connection:
        existing = _columns(connection, "users")
        # SQLite cannot add a NOT NULL column without a default, so these arrive
        # with an empty default and are backfilled below.
        if "email" not in existing:
            connection.execute(
                text(
                    "ALTER TABLE users ADD COLUMN email VARCHAR(255) NOT NULL DEFAULT ''"
                )
            )
            print("  legacy repair: users.email added")
        if "password_hash" not in existing:
            connection.execute(
                text(
                    "ALTER TABLE users ADD COLUMN password_hash VARCHAR(255) "
                    "NOT NULL DEFAULT ''"
                )
            )
            print("  legacy repair: users.password_hash added")

    # Backfill only blanks. A learner who already has a password must not have it
    # reset by running a migration.
    from sqlalchemy.orm import Session as OrmSession

    from app.repositories import user_repo
    from app.services import auth_service

    with OrmSession(engine) as db:
        filled = 0
        for user in user_repo.all_users(db):
            if not user.email:
                user.email = auth_service.normalize_email(
                    settings.demo_email
                    if user.username == settings.demo_username
                    else f"{user.username}@example.invalid"
                )
                filled += 1
            if not user.password_hash:
                user.password_hash = auth_service.hash_password(
                    settings.demo_user_password
                )
                filled += 1
        if filled:
            db.commit()
            print(f"  legacy repair: backfilled {filled} blank credential field(s)")

    with engine.begin() as connection:
        # After the backfill, because empty strings in more than one row would
        # collide. `IF NOT EXISTS` so a re-run is a no-op. A legacy database with
        # genuine duplicates fails here, loudly — which is correct: silently
        # dropping a row to satisfy an index would be the migration destroying
        # data.
        connection.execute(
            text("CREATE UNIQUE INDEX IF NOT EXISTS uq_users_email ON users (email)")
        )
        connection.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_users_display_name "
                "ON users (display_name)"
            )
        )


def _verify_matches_baseline(engine: Engine) -> None:
    """Refuse to stamp a database that is not actually at the baseline.

    Stamping is a *claim*: "this database already has the schema revision 0001
    describes". Making that claim wrongly is the one genuinely dangerous thing
    this module can do — every later migration would then run against a shape it
    was not written for.

    So the claim is checked before it is made. Tables the models declare but the
    database lacks are a hard error with a message naming them.
    """
    missing = set(Base.metadata.tables) - _table_names(engine)
    if missing:
        raise RuntimeError(
            "This database cannot be stamped at the Alembic baseline: it is "
            f"missing {sorted(missing)}. It is neither empty nor at the Phase 9.5 "
            "schema, so migrating it automatically would be a guess. Inspect it, "
            "or start from a fresh database with `python -m app.db.seed`."
        )


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------


def migrate(engine: Engine | None = None, database_url: str | None = None) -> None:
    """Bring a database to the latest revision, whatever state it is in.

    Args:
        engine: Engine to inspect. Defaults to the application's.
        database_url: URL Alembic should migrate. Defaults to the application's.
            Tests pass both, pointed at a throwaway file.
    """
    engine = engine or default_engine
    config = alembic_config(database_url)

    tables = _table_names(engine)
    stamped = current_revision(engine)

    if not tables:
        print("Empty database. Creating the schema at the latest revision.")
        command.upgrade(config, "head")

    elif stamped is None:
        print("Existing database with no Alembic version. Adopting it.")
        _repair_legacy_schema(engine)
        _verify_matches_baseline(engine)
        # `stamp` writes the version row and runs NO DDL. The tables are already
        # there; this only records which revision they correspond to.
        command.stamp(config, BASELINE_REVISION)
        print(f"  stamped at revision {BASELINE_REVISION} (no tables were altered)")
        command.upgrade(config, "head")

    else:
        print(f"Database is at revision {stamped}.")
        command.upgrade(config, "head")

    print(f"Migration complete. Now at revision {current_revision(engine)}.")


if __name__ == "__main__":
    migrate()
