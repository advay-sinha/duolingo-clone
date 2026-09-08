"""Migrations — the tests that make Alembic safe to have adopted.

Every test here runs against a throwaway SQLite file in pytest's ``tmp_path``.
**The development database is never opened**, which matters more in this file
than anywhere else: these tests are about a tool whose entire job is to change
schemas in place.

The two properties worth stating up front, because they are what the whole file
is arranged around:

1. **The baseline must equal the models.** If ``alembic upgrade head`` and
   ``Base.metadata.create_all`` disagree, then a fresh database and a migrated
   one are different databases, and every later migration is written against a
   guess. ``test_the_baseline_matches_the_models`` is the guard.

2. **Adopting an existing database must not touch a row.** Stamping is a claim
   about what is already there, and the tests below check the claim is only made
   when it is true, and that nothing is lost when it is.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session

import app.models  # noqa: F401  -- registers models on Base.metadata
from app.db.base import Base
from app.db.migrate import BASELINE_REVISION, current_revision, migrate
from app.db.seed import seed


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------


def url_for(path) -> str:
    """A SQLAlchemy URL for a filesystem path, on any platform."""
    return f"sqlite:///{path.as_posix()}"


def run_migrate(path) -> None:
    """Migrate a database file, disposing the engine afterwards.

    The dispose matters on Windows: an open handle stops pytest from cleaning up
    ``tmp_path``, which turns a passing test into a confusing teardown error.
    """
    url = url_for(path)
    engine = create_engine(url)
    try:
        migrate(engine=engine, database_url=url)
    finally:
        engine.dispose()


def revision_of(path) -> str | None:
    engine = create_engine(url_for(path))
    try:
        return current_revision(engine)
    finally:
        engine.dispose()


def describe_schema(path) -> dict:
    """A semantic description of a schema, for comparing two databases.

    **Deliberately not a comparison of `CREATE TABLE` text.** SQLAlchemy's
    ``create_all`` and Alembic's ``op.create_table`` emit the same constraints in
    a different *order* within the statement, so comparing DDL strings reports
    thirteen differences that are not differences. What matters is what the
    database will enforce: columns and their types and nullability, primary keys,
    unique constraint column sets, foreign key targets with their ON DELETE
    behaviour, indexes, and the presence of each CHECK.
    """
    engine = create_engine(url_for(path))
    try:
        inspector = inspect(engine)
        schema: dict = {}
        for table in sorted(inspector.get_table_names()):
            if table == "alembic_version":
                continue
            schema[table] = {
                "columns": sorted(
                    (c["name"], str(c["type"]), bool(c["nullable"]))
                    for c in inspector.get_columns(table)
                ),
                "pk": sorted(
                    inspector.get_pk_constraint(table).get("constrained_columns") or []
                ),
                "unique": sorted(
                    tuple(sorted(u["column_names"]))
                    for u in inspector.get_unique_constraints(table)
                ),
                "indexes": sorted(
                    (i["name"], tuple(sorted(i["column_names"] or [])), bool(i["unique"]))
                    for i in inspector.get_indexes(table)
                ),
                "foreign_keys": sorted(
                    (
                        tuple(sorted(f["constrained_columns"])),
                        f["referred_table"],
                        tuple(sorted(f["referred_columns"])),
                        (f.get("options") or {}).get("ondelete"),
                    )
                    for f in inspector.get_foreign_keys(table)
                ),
                "checks": sorted(
                    c["name"] for c in inspector.get_check_constraints(table) if c["name"]
                ),
            }
        return schema
    finally:
        engine.dispose()


@pytest.fixture
def fresh_db(tmp_path):
    """An empty database file that has never been touched."""
    return tmp_path / "fresh.db"


@pytest.fixture
def legacy_db(tmp_path):
    """A database at the pre-Alembic schema, with data in it.

    Built with ``create_all`` and the real seed, then the version table is
    removed — which is exactly the state every database created before Phase 10
    is in: correct schema, no Alembic history.
    """
    path = tmp_path / "legacy.db"
    engine = create_engine(url_for(path))
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        seed(db)
    with engine.begin() as connection:
        connection.execute(text("DROP TABLE IF EXISTS alembic_version"))
    engine.dispose()
    return path


# --------------------------------------------------------------------------
# 1-3. A fresh database
# --------------------------------------------------------------------------


def test_an_empty_database_migrates_to_head(fresh_db) -> None:
    run_migrate(fresh_db)
    assert revision_of(fresh_db) == BASELINE_REVISION


def test_a_migrated_empty_database_has_every_table(fresh_db) -> None:
    run_migrate(fresh_db)
    engine = create_engine(url_for(fresh_db))
    try:
        tables = set(inspect(engine).get_table_names())
    finally:
        engine.dispose()

    assert set(Base.metadata.tables) <= tables
    assert "alembic_version" in tables


def test_the_baseline_matches_the_models(tmp_path, fresh_db) -> None:
    """**The most important test in this file.**

    A database built by running the migrations must be indistinguishable from one
    built by ``create_all`` from the models. If it is not, then a developer's
    fresh database and a migrated production database have different shapes, and
    every migration written after that point is written against a guess.

    Alembic's autogenerate is good but not infallible — it is known to miss
    server defaults and some constraint forms — so this asserts the outcome
    rather than trusting the generator.
    """
    run_migrate(fresh_db)

    from_models = tmp_path / "from_models.db"
    engine = create_engine(url_for(from_models))
    Base.metadata.create_all(engine)
    engine.dispose()

    assert describe_schema(fresh_db) == describe_schema(from_models)


def test_seeding_works_after_migrating(fresh_db) -> None:
    """The documented path for an evaluator: migrate, then seed."""
    run_migrate(fresh_db)

    engine = create_engine(url_for(fresh_db))
    try:
        with Session(engine) as db:
            seed(db)
            counts = {
                "courses": db.execute(text("SELECT COUNT(*) FROM courses")).scalar(),
                "skills": db.execute(text("SELECT COUNT(*) FROM skills")).scalar(),
                "exercises": db.execute(text("SELECT COUNT(*) FROM exercises")).scalar(),
                "users": db.execute(text("SELECT COUNT(*) FROM users")).scalar(),
            }
    finally:
        engine.dispose()

    assert counts == {"courses": 1, "skills": 9, "exercises": 90, "users": 1}


# --------------------------------------------------------------------------
# 4-6. An existing database
# --------------------------------------------------------------------------


def test_a_legacy_database_is_stamped_not_rebuilt(legacy_db) -> None:
    """Adoption records where the database is; it does not build it again."""
    assert revision_of(legacy_db) is None

    run_migrate(legacy_db)

    assert revision_of(legacy_db) == BASELINE_REVISION


def test_adopting_a_legacy_database_preserves_every_row(legacy_db) -> None:
    """The whole reason this phase did not simply delete and re-create."""
    before = _row_counts(legacy_db)

    run_migrate(legacy_db)

    assert _row_counts(legacy_db) == before


def test_adopting_preserves_learner_progress_exactly(legacy_db) -> None:
    """Counts can match while values are quietly rewritten. Check the values."""
    engine = create_engine(url_for(legacy_db))
    with Session(engine) as db:
        db.execute(
            text(
                "UPDATE user_stats SET total_xp = 140, current_streak = 3, hearts = 4"
            )
        )
        db.execute(
            text("UPDATE user_skill_progress SET crowns = 1, lessons_completed = 2 "
                 "WHERE skill_id = 1")
        )
        db.commit()
    engine.dispose()

    run_migrate(legacy_db)

    engine = create_engine(url_for(legacy_db))
    try:
        with Session(engine) as db:
            stats = db.execute(
                text("SELECT total_xp, current_streak, hearts FROM user_stats")
            ).one()
            progress = db.execute(
                text(
                    "SELECT crowns, lessons_completed FROM user_skill_progress "
                    "WHERE skill_id = 1"
                )
            ).one()
    finally:
        engine.dispose()

    assert tuple(stats) == (140, 3, 4)
    assert tuple(progress) == (1, 2)


def test_adopting_preserves_credentials_and_sessions(legacy_db) -> None:
    """A migration that invalidated every password or session would be a bug.

    Both are checked because they fail differently: a rewritten hash locks the
    learner out permanently, a dropped session only logs them out.
    """
    expires = datetime.now(timezone.utc) + timedelta(days=7)
    engine = create_engine(url_for(legacy_db))
    with Session(engine) as db:
        hash_before = db.execute(text("SELECT password_hash FROM users")).scalar()
        db.execute(
            text(
                "INSERT INTO sessions (id, user_id, created_at, expires_at) "
                "VALUES ('abc123', 1, :now, :exp)"
            ),
            {"now": datetime.now(timezone.utc), "exp": expires},
        )
        db.commit()
    engine.dispose()

    run_migrate(legacy_db)

    engine = create_engine(url_for(legacy_db))
    try:
        with Session(engine) as db:
            hash_after = db.execute(text("SELECT password_hash FROM users")).scalar()
            session_rows = db.execute(
                text("SELECT COUNT(*) FROM sessions WHERE id = 'abc123'")
            ).scalar()
    finally:
        engine.dispose()

    assert hash_after == hash_before
    assert hash_after.startswith("$2")
    assert session_rows == 1


def test_migrating_twice_changes_nothing(legacy_db) -> None:
    run_migrate(legacy_db)
    schema_once = describe_schema(legacy_db)
    counts_once = _row_counts(legacy_db)

    run_migrate(legacy_db)

    assert describe_schema(legacy_db) == schema_once
    assert _row_counts(legacy_db) == counts_once
    assert revision_of(legacy_db) == BASELINE_REVISION


# --------------------------------------------------------------------------
# 7-9. Integrity after migrating
# --------------------------------------------------------------------------


def test_integrity_and_foreign_keys_hold_after_migrating(legacy_db) -> None:
    run_migrate(legacy_db)

    engine = create_engine(url_for(legacy_db))
    try:
        with engine.connect() as connection:
            integrity = connection.execute(text("PRAGMA integrity_check")).scalar()
            orphans = connection.execute(text("PRAGMA foreign_key_check")).fetchall()
    finally:
        engine.dispose()

    assert integrity == "ok"
    assert orphans == []


def test_foreign_keys_are_still_enforced_after_migrating(legacy_db) -> None:
    """The pragma is per connection, so it has to be proved, not assumed."""
    from sqlalchemy.exc import IntegrityError

    run_migrate(legacy_db)

    from app.db.session import _enable_sqlite_foreign_keys  # noqa: F401

    engine = create_engine(url_for(legacy_db))
    try:
        with engine.connect() as connection:
            connection.execute(text("PRAGMA foreign_keys=ON"))
            with pytest.raises(IntegrityError):
                connection.execute(
                    text(
                        "INSERT INTO lessons (skill_id, title, order_index, xp_reward) "
                        "VALUES (99999, 'orphan', 0, 10)"
                    )
                )
                connection.commit()
    finally:
        engine.dispose()


def test_unique_constraints_survive_migrating(legacy_db) -> None:
    from sqlalchemy.exc import IntegrityError

    run_migrate(legacy_db)

    engine = create_engine(url_for(legacy_db))
    try:
        with engine.connect() as connection:
            existing = connection.execute(
                text("SELECT username, email, display_name FROM users LIMIT 1")
            ).one()
            with pytest.raises(IntegrityError):
                connection.execute(
                    text(
                        "INSERT INTO users (username, email, password_hash, "
                        "display_name, avatar_url, created_at) VALUES "
                        "(:u, 'other@example.com', 'x', 'Other', '', :now)"
                    ),
                    {"u": existing[0], "now": datetime.now(timezone.utc)},
                )
                connection.commit()
    finally:
        engine.dispose()


# --------------------------------------------------------------------------
# Refusing to lie
# --------------------------------------------------------------------------


def test_a_database_missing_tables_is_repaired_rather_than_refused(
    legacy_db,
) -> None:
    """A database at an older schema still adopts cleanly.

    Dropping the placement tables reproduces a Phase 9 database. The frozen
    legacy repair creates what is missing before the baseline check runs, so an
    older database is carried forward rather than rejected — which is the
    behaviour the pre-Phase-10 script had, and losing it would have been a
    regression.
    """
    engine = create_engine(url_for(legacy_db))
    with engine.begin() as connection:
        connection.execute(text("DROP TABLE placement_answers"))
        connection.execute(text("DROP TABLE placement_tests"))
        connection.execute(text("DROP TABLE user_onboarding"))
    engine.dispose()

    run_migrate(legacy_db)

    engine = create_engine(url_for(legacy_db))
    try:
        tables = set(inspect(engine).get_table_names())
    finally:
        engine.dispose()

    assert {"placement_answers", "placement_tests", "user_onboarding"} <= tables
    assert revision_of(legacy_db) == BASELINE_REVISION


def test_the_baseline_revision_is_the_only_head() -> None:
    """One linear history. A branch would make `upgrade head` ambiguous."""
    from alembic.script import ScriptDirectory

    from app.db.migrate import alembic_config

    heads = ScriptDirectory.from_config(alembic_config()).get_heads()
    assert len(heads) == 1


def test_every_revision_has_a_downgrade() -> None:
    """A migration you cannot reverse is a deployment you cannot roll back.

    Reads the source of each revision rather than running it: `downgrade()`
    existing but containing only `pass` is the failure this catches, and it is
    the one autogenerate produces when nobody looks.
    """
    from alembic.script import ScriptDirectory

    from app.db.migrate import alembic_config

    scripts = ScriptDirectory.from_config(alembic_config())
    for revision in scripts.walk_revisions():
        source = open(revision.path, encoding="utf-8").read()
        body = source.split("def downgrade()", 1)[1]
        assert "op." in body, f"revision {revision.revision} cannot be rolled back"


# --------------------------------------------------------------------------


def _row_counts(path) -> dict[str, int]:
    """Row counts for every model table, for before/after comparison."""
    engine = create_engine(url_for(path))
    try:
        with engine.connect() as connection:
            present = set(inspect(engine).get_table_names())
            return {
                table: connection.execute(
                    text(f"SELECT COUNT(*) FROM {table}")
                ).scalar()
                for table in sorted(set(Base.metadata.tables) & present)
            }
    finally:
        engine.dispose()
