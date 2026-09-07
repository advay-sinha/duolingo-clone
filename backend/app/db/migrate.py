"""One hand-written migration, for the Phase 9 authentication columns.

**Why this file exists at all.** Every earlier phase created its tables with
``create_all``, which is honest about what it does: it creates tables that are
missing and never alters a table that exists. That was fine while every schema
change added a *new* table. Phase 9 adds columns to ``users``, so ``create_all``
would silently do nothing and the application would fail at runtime against an
old database.

**Why not Alembic.** Alembic is the right answer for a schema that keeps moving,
and it is what this project would adopt next. It is not the right answer for one
migration on a single-file local database: ``env.py``, a versions directory,
autogenerate configuration and a second command to learn is more machinery than
the change it would carry. The honest trade-off is recorded in ADR-62 — this
script is deliberately a stopgap, not a framework.

**What it guarantees.** It is idempotent (running it twice changes nothing the
second time) and non-destructive (it adds columns and backfills blanks; it never
drops, rewrites or deletes a row). The alternative — deleting ``duolingo.db`` and
re-seeding — also works and is documented in the README, but it throws away
whatever practice progress is in the local database, which is exactly the thing
the seed was carefully written not to do.

Run it with::

    python -m app.db.migrate
"""

from __future__ import annotations

from sqlalchemy import inspect, text

from app.core.config import get_settings
from app.db.init_db import create_tables
from app.db.session import SessionLocal, engine
from app.repositories import user_repo
from app.services import auth_service


def _columns(connection, table: str) -> set[str]:
    return {row[1] for row in connection.execute(text(f"PRAGMA table_info({table})"))}


def migrate() -> None:
    """Bring an existing database up to the Phase 9 schema."""
    settings = get_settings()

    # New *tables* (sessions, lesson_attempt_pairs) need nothing special —
    # create_all still does exactly the right thing for those.
    create_tables()

    inspector = inspect(engine)
    if "users" not in inspector.get_table_names():
        print("No users table yet; run `python -m app.db.seed` instead.")
        return

    with engine.begin() as connection:
        existing = _columns(connection, "users")

        # SQLite cannot add a NOT NULL column without a default, so these arrive
        # with an empty default and are backfilled below. The model declares them
        # NOT NULL, which is what matters for every database created from now on.
        if "email" not in existing:
            connection.execute(
                text("ALTER TABLE users ADD COLUMN email VARCHAR(255) NOT NULL DEFAULT ''")
            )
            print("users: added email")
        if "password_hash" not in existing:
            connection.execute(
                text(
                    "ALTER TABLE users ADD COLUMN password_hash VARCHAR(255) "
                    "NOT NULL DEFAULT ''"
                )
            )
            print("users: added password_hash")

        # Unique indexes are created after the backfill below, because empty
        # strings in more than one row would collide.

    with SessionLocal() as db:
        # Backfill only what is blank. A learner who has already set a password
        # must not have it reset by running a migration.
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
            print(f"users: backfilled {filled} blank credential field(s)")

    with engine.begin() as connection:
        # Created last, and IF NOT EXISTS so a re-run is a no-op. If a legacy
        # database somehow holds duplicates these will fail loudly, which is the
        # correct outcome: silently dropping a row to satisfy an index would be
        # the migration destroying data.
        connection.execute(
            text("CREATE UNIQUE INDEX IF NOT EXISTS uq_users_email ON users (email)")
        )
        connection.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_users_display_name "
                "ON users (display_name)"
            )
        )

    print("Migration complete.")


if __name__ == "__main__":
    migrate()
