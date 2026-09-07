"""Shared test fixtures.

**Test database isolation — the strategy, and why this one.**

Every API test runs against a fresh SQLite *file* in pytest's ``tmp_path``, seeded
from scratch. The development database at ``backend/duolingo.db`` is never opened
by the suite, so running tests can never corrupt or wipe local progress.

The mechanism is FastAPI's ``dependency_overrides``: the app is built normally,
then ``get_db`` is replaced with one yielding a session bound to the temporary
engine. Routes are untouched and unaware — they still just declare
``db: DbSession``. That is the payoff for having put the session behind a
dependency in Phase 1 rather than importing ``SessionLocal`` inside each route.

Alternatives considered:

* **In-memory SQLite** (``sqlite:///:memory:``) is faster, but each connection
  gets its own private database unless pooling is carefully pinned — a subtle
  trap where the seed and the request see different data. A temp file behaves
  exactly like production for a few milliseconds more.
* **Transaction rollback per test** (open a transaction, roll back at teardown)
  avoids re-seeding, but the code under test also commits, which makes the
  nesting fragile. Re-seeding is slower and obviously correct.
* **Reusing the dev database** would be fastest and would destroy the developer's
  data. Not an option.
"""

from __future__ import annotations

import os

# Set before anything imports app config, because `get_settings` is cached on
# first call. bcrypt is deliberately slow -- that is its entire purpose -- and at
# the production cost factor the suite would spend roughly a quarter-second per
# test hashing, for no extra coverage. 4 is bcrypt's minimum and exercises
# identical code; the cost factor is recorded inside each hash string, so nothing
# about production hashes changes. Django ships the same knob for the same
# reason.
os.environ.setdefault("BCRYPT_ROUNDS", "4")

from collections.abc import Iterator  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

import app.models  # noqa: F401 -- registers models on Base.metadata
from app.api.v1.deps import get_db as get_db_dependency
from app.db.base import Base
from app.db.seed import seed
from app.core.config import get_settings
from app.db.session import get_db
from app.main import create_app


@pytest.fixture
def db_session(tmp_path) -> Iterator[Session]:
    """A seeded, isolated database session backed by a temporary file."""
    engine = create_engine(
        f"sqlite:///{(tmp_path / 'api-test.db').as_posix()}",
        connect_args={"check_same_thread": False},
    )

    # The application enables this per connection in app/db/session.py. The test
    # engine is a different engine, so it must do the same -- otherwise foreign
    # keys would go unenforced here and tests would pass for the wrong reason.
    @event.listens_for(engine, "connect")
    def _fk_on(dbapi_connection, _record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    # `autoflush=False` mirrors the application's own SessionLocal. Without it
    # the test session flushes pending changes before every query while
    # production does not -- a divergence that hid a real bug in Phase 7, where
    # achievement evaluation saw the completion in tests but not in the running
    # app. Test sessions must behave like the real one.
    TestSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    session = TestSession()
    seed(session)

    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture
def client(db_session: Session) -> Iterator[TestClient]:
    """A TestClient whose app talks to the isolated test database.

    Both spellings of the dependency are overridden — the original in
    ``app.db.session`` and the one re-exported through ``app.api.v1.deps`` —
    because FastAPI keys overrides on the exact function object a route depends
    on. Overriding only one would leave the other pointing at the real database,
    which is precisely the failure this fixture exists to prevent.
    """
    app = create_app()

    def override_get_db() -> Iterator[Session]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_db_dependency] = override_get_db

    with TestClient(app) as test_client:
        # Phase 9: identity comes from a session cookie, so a client that has
        # not logged in gets 401 from every learner endpoint. The suite logs in
        # as the seeded learner through the *real* login endpoint rather than
        # overriding `get_current_user`, so every test exercises the actual
        # authentication path. Tests that need an unauthenticated client use the
        # `anon_client` fixture below.
        response = test_client.post(
            "/api/v1/auth/login",
            json={
                "email": get_settings().demo_email,
                "password": get_settings().demo_user_password,
            },
        )
        assert response.status_code == 200, response.text
        yield test_client


@pytest.fixture
def anon_client(db_session: Session) -> Iterator[TestClient]:
    """A TestClient with no session, for testing the unauthenticated paths.

    Same wiring as `client`, minus the login. Kept separate rather than made a
    parameter so a test's intent is visible from the fixture it asks for.
    """
    app = create_app()

    def override_get_db() -> Iterator[Session]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_db_dependency] = override_get_db

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def register_user(db_session: Session):
    """Factory: register a learner and return a TestClient logged in as them.

    Registration goes through the API, so the returned client exercises exactly
    what a browser would — including the cookie. Multi-user tests use two of
    these and assert that nothing leaks between them.
    """

    def _register(
        email: str, password: str = "password123", display_name: str | None = None
    ) -> TestClient:
        app = create_app()

        def override_get_db() -> Iterator[Session]:
            yield db_session

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_db_dependency] = override_get_db

        test_client = TestClient(app)
        response = test_client.post(
            "/api/v1/auth/register",
            json={
                "email": email,
                "password": password,
                "display_name": display_name or email.split("@")[0].title(),
            },
        )
        assert response.status_code == 201, response.text
        return test_client

    return _register

    app.dependency_overrides.clear()


def make_user(*, username: str, display_name: str, password: str = "password123"):
    """Build a `User` with valid credentials, for tests that insert one directly.

    Since Phase 9 `email` and `password_hash` are NOT NULL, so a bare
    `User(username=..., display_name=...)` no longer inserts. Tests that only
    need "another learner to exist" say so through this helper rather than
    repeating credential boilerplate that is beside their point.
    """
    from app.models import User
    from app.services import auth_service

    return User(
        username=username,
        display_name=display_name,
        email=f"{username}@example.test",
        password_hash=auth_service.hash_password(password),
    )
