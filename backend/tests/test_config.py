"""Configuration profiles, and the production checks that refuse to boot.

**Why these are worth testing.** Every check under test here guards a mistake
that is otherwise *silent*: a cookie without `Secure` still authenticates, SQL
echo still serves requests, the committed demo password still logs in. The
application looks healthy while being wrong, which is the class of failure that
survives longest in production — so the checks convert it into a crash at
startup, and these tests keep the checks honest.

The other half is just as important: **development must not be affected.**
A safety check that makes local work harder gets disabled, and then protects
nothing.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.core.config import Environment, Settings


def production(**overrides) -> Settings:
    """A production Settings that is safe apart from what a test overrides."""
    safe = {
        "environment": "production",
        "session_cookie_secure": True,
        "demo_user_password": "a-real-password",
        "cors_origins": [],
        "database_echo": False,
        # A hosted libSQL URL: the Phase 10.3 production database. Without this
        # the default (a file inside the app directory) would now be refused, and
        # every test in this file would fail for the wrong reason.
        "database_url": "sqlite+libsql://db-org.turso.io/?authToken=t&secure=true",
    }
    return Settings(**{**safe, **overrides})


def problems_from(exc: ValidationError) -> str:
    return str(exc.value if hasattr(exc, "value") else exc)


# --------------------------------------------------------------------------
# Defaults
# --------------------------------------------------------------------------


def test_the_default_environment_is_development() -> None:
    """Nobody has to set anything to work locally — only to deploy."""
    assert Settings().environment is Environment.DEVELOPMENT
    assert Settings().is_production is False


def test_development_tolerates_the_local_defaults() -> None:
    """The checks must not fire outside production, or they get switched off."""
    settings = Settings(
        session_cookie_secure=False,
        database_echo=True,
        cors_origins=["http://localhost:3000"],
    )

    assert settings.environment is Environment.DEVELOPMENT


def test_the_test_environment_is_also_unchecked() -> None:
    assert Settings(environment="test", session_cookie_secure=False)


def test_an_unknown_environment_is_rejected() -> None:
    """A typo must not fall back to development behaviour in a deployment."""
    with pytest.raises(ValidationError):
        Settings(environment="prod")


# --------------------------------------------------------------------------
# Production refusals
# --------------------------------------------------------------------------


def test_a_correctly_configured_production_boots() -> None:
    settings = production()

    assert settings.is_production is True
    assert settings.session_cookie_secure is True


def test_production_refuses_an_insecure_cookie() -> None:
    """Without `Secure` the session cookie travels in the clear."""
    with pytest.raises(ValidationError) as exc:
        production(session_cookie_secure=False)

    assert "SESSION_COOKIE_SECURE" in problems_from(exc)


def test_production_refuses_the_committed_demo_password() -> None:
    """It is published in this repository; it cannot also be a live credential."""
    with pytest.raises(ValidationError) as exc:
        production(demo_user_password="duolingo123")

    assert "DEMO_USER_PASSWORD" in problems_from(exc)


def test_production_refuses_sql_echo() -> None:
    """Echo writes every statement — parameters included — to the platform log."""
    with pytest.raises(ValidationError) as exc:
        production(database_echo=True)

    assert "DATABASE_ECHO" in problems_from(exc)


def test_production_refuses_localhost_in_the_cors_allowlist() -> None:
    with pytest.raises(ValidationError) as exc:
        production(cors_origins=["https://app.example.com", "http://localhost:3000"])

    assert "CORS_ORIGINS" in problems_from(exc)


def test_production_allows_an_empty_cors_allowlist() -> None:
    """The recommended topology proxies the API under the frontend's own origin,
    so there is no cross-origin request for CORS to govern at all."""
    assert production(cors_origins=[]).cors_origins == []


def test_every_problem_is_reported_at_once() -> None:
    """One deploy, one list. Reporting the first only would mean four attempts."""
    with pytest.raises(ValidationError) as exc:
        Settings(
            environment="production",
            session_cookie_secure=False,
            demo_user_password="duolingo123",
            database_echo=True,
            cors_origins=["http://localhost:3000"],
        )

    message = problems_from(exc)
    for key in (
        "SESSION_COOKIE_SECURE",
        "DEMO_USER_PASSWORD",
        "DATABASE_ECHO",
        "CORS_ORIGINS",
    ):
        assert key in message


# --------------------------------------------------------------------------
# CORS_ORIGINS parsing
#
# These exist because of a real production failure. `pydantic-settings` treats
# `list[str]` as JSON and calls `json.loads()` inside `EnvSettingsSource`, before
# any validator runs — so a Vercel dashboard value of
# `https://my-app.vercel.app`, or a comma-separated list, or an EMPTY value,
# all crashed the application at import with:
#
#     SettingsError: error parsing value for field "cors_origins"
#                    from source "EnvSettingsSource"
#
# The field is now annotated `NoDecode` and parsed by `_parse_cors_origins`.
# Every case below is a form that previously brought the app down.
# --------------------------------------------------------------------------


def from_env(monkeypatch, raw: str) -> Settings:
    """Build Settings from a raw CORS_ORIGINS environment value.

    Goes through the environment rather than the constructor on purpose: the bug
    lived in the *settings source*, so a test passing a Python list to
    `Settings(cors_origins=[...])` would not have caught it.
    """
    monkeypatch.setenv("CORS_ORIGINS", raw)
    return Settings()


def test_a_single_origin_needs_no_json(monkeypatch) -> None:
    """The exact value a deployment dashboard makes easiest to type."""
    settings = from_env(monkeypatch, "https://my-app.vercel.app")

    assert settings.cors_origins == ["https://my-app.vercel.app"]


def test_multiple_origins_can_be_comma_separated(monkeypatch) -> None:
    settings = from_env(
        monkeypatch, "http://localhost:3000,https://my-app.vercel.app"
    )

    assert settings.cors_origins == [
        "http://localhost:3000",
        "https://my-app.vercel.app",
    ]


def test_whitespace_and_trailing_commas_are_tolerated(monkeypatch) -> None:
    """A trailing comma is a typo, not a reason to refuse to boot."""
    settings = from_env(monkeypatch, " https://a.example.com , https://b.example.com ,")

    assert settings.cors_origins == ["https://a.example.com", "https://b.example.com"]


def test_json_is_still_accepted(monkeypatch) -> None:
    """Backwards compatible: `.env.example` shipped JSON for several phases."""
    settings = from_env(
        monkeypatch, '["http://localhost:3000","http://127.0.0.1:3000"]'
    )

    assert settings.cors_origins == [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]


def test_an_empty_value_means_no_origins(monkeypatch) -> None:
    """**The likeliest trigger of the production failure.**

    This project's own documentation recommends no origins for the recommended
    topology, and the obvious way to express that in a dashboard text box is to
    leave it blank. That used to crash the app.

    Empty means *no cross-origin access*, never "allow everything" — reading a
    blank box as a wildcard would turn a typo into an open API.
    """
    assert from_env(monkeypatch, "").cors_origins == []
    assert from_env(monkeypatch, "   ").cors_origins == []
    assert from_env(monkeypatch, "[]").cors_origins == []


def test_the_local_development_default_is_unchanged(monkeypatch) -> None:
    """Nothing has to be set to work locally."""
    monkeypatch.delenv("CORS_ORIGINS", raising=False)

    assert Settings().cors_origins == [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]


def test_a_trailing_slash_is_normalised_away(monkeypatch) -> None:
    """The failure this prevents is silent: the browser compares the Origin
    header as an exact string, so `https://app.dev/` matches nothing at all and
    looks like a broken application rather than a mistyped setting."""
    settings = from_env(monkeypatch, "https://app.example.com/")

    assert settings.cors_origins == ["https://app.example.com"]


def test_a_wildcard_is_refused(monkeypatch) -> None:
    """A wildcard origin and credentialed requests are incompatible by spec, and
    this API authenticates with a cookie."""
    with pytest.raises(ValidationError) as exc:
        from_env(monkeypatch, "*")

    assert "may not contain" in problems_from(exc)


def test_an_origin_without_a_scheme_is_refused(monkeypatch) -> None:
    with pytest.raises(ValidationError) as exc:
        from_env(monkeypatch, "my-app.vercel.app")

    assert "http:// or https://" in problems_from(exc)


def test_a_url_with_a_path_is_refused_and_says_what_to_use(monkeypatch) -> None:
    with pytest.raises(ValidationError) as exc:
        from_env(monkeypatch, "https://app.example.com/api/v1")

    message = problems_from(exc)
    assert "must be an origin, not a URL" in message
    assert "https://app.example.com" in message


def test_broken_json_explains_itself_instead_of_raising_JSONDecodeError(
    monkeypatch,
) -> None:
    """**The regression test for the original bug.**

    The old failure was a `SettingsError` wrapping a `JSONDecodeError`, raised
    inside the settings source — it named the field and nothing else. The value
    below still cannot be parsed, but now it is a validation error that says why
    and offers the simpler format.
    """
    with pytest.raises(ValidationError) as exc:
        from_env(monkeypatch, '["https://a.example.com"')

    message = problems_from(exc)
    assert "looks like JSON but could not be parsed" in message
    assert "comma-separated" in message


def test_json_that_is_not_a_list_is_refused(monkeypatch) -> None:
    with pytest.raises(ValidationError) as exc:
        from_env(monkeypatch, '{"origin": "https://a.example.com"}')

    assert "must be a list of origins" in problems_from(exc)


def test_the_production_localhost_check_still_works_from_the_environment(
    monkeypatch,
) -> None:
    """The Phase 10 production check reads the *parsed* list, so it must keep
    working now that the value arrives as a string."""
    monkeypatch.setenv("CORS_ORIGINS", "https://app.example.com,http://localhost:3000")

    with pytest.raises(ValidationError) as exc:
        Settings(
            environment="production",
            session_cookie_secure=True,
            demo_user_password="a-real-password",
        )

    assert "CORS_ORIGINS" in problems_from(exc)


# --------------------------------------------------------------------------
# The production database URL
#
# These exist because of the second real production outage: the deployed backend
# answered GET /health with 200 and then returned 500 from the first endpoint
# that touched the database --
#     sqlite3.OperationalError: unable to open database file
# -- because DATABASE_URL was still the built-in default, a file inside the
# deployed application directory, on a filesystem that is neither writable nor
# durable. Nothing objected until a learner tried to register.
#
# The check turns that into a refusal to start. See ADR-81.
# --------------------------------------------------------------------------


def test_production_refuses_a_database_inside_the_application_directory() -> None:
    """The exact configuration that failed in production."""
    from app.core.config import DEFAULT_SQLITE_URL

    with pytest.raises(ValidationError) as exc:
        production(database_url=DEFAULT_SQLITE_URL)

    message = problems_from(exc)
    assert "DATABASE_URL" in message
    assert "unable to open database file" in message


def test_production_refuses_a_relative_sqlite_path() -> None:
    """`sqlite:///./duolingo.db` resolves inside the app directory too."""
    with pytest.raises(ValidationError) as exc:
        production(database_url="sqlite:///./duolingo.db")

    assert "DATABASE_URL" in problems_from(exc)


def test_production_accepts_a_hosted_libsql_url() -> None:
    """`sqlite+libsql://` is a network dialect — nothing is stored on the host.

    This is the production configuration from Phase 10.3: SQLAlchemy still
    generates SQLite SQL, only the driver differs.
    """
    settings = production(
        database_url="sqlite+libsql://db-org.turso.io/?authToken=token&secure=true"
    )

    assert settings.database_url.startswith("sqlite+libsql://")


def test_production_accepts_a_file_on_a_persistent_volume() -> None:
    """A deliberate absolute path outside the app directory is an operator's
    decision, not a mistake. Refusing it would be a false positive, and false
    positives are how safety checks get switched off."""
    assert production(database_url="sqlite:////data/duolingo.db")


def test_development_is_unaffected_by_the_database_check() -> None:
    """The default local file must keep working with no configuration at all."""
    from app.core.config import DEFAULT_SQLITE_URL

    assert Settings().database_url == DEFAULT_SQLITE_URL
    assert Settings(database_url=DEFAULT_SQLITE_URL).is_production is False


def test_the_local_sqlite_default_is_still_a_plain_sqlite_file() -> None:
    """Guards the assignment requirement: local development is SQLite.

    Phase 10.3 changed the *production* database only. If this ever stops being
    a `sqlite://` file URL, the local development story has changed and that
    needs to be a deliberate decision.
    """
    from app.core.config import DEFAULT_SQLITE_URL

    assert DEFAULT_SQLITE_URL.startswith("sqlite:///")
    assert DEFAULT_SQLITE_URL.endswith("duolingo.db")


def test_an_unparseable_database_url_is_not_this_checks_problem() -> None:
    """It must not mask a different error with a confusing one of its own."""
    from app.core.config import _is_local_sqlite_file

    assert _is_local_sqlite_file("nonsense") is False
    assert _is_local_sqlite_file("postgresql://host/db") is False
    assert _is_local_sqlite_file("sqlite:///:memory:") is False


# --------------------------------------------------------------------------
# Rate limiting is configuration, not a literal
# --------------------------------------------------------------------------


def test_rate_limit_settings_have_sensible_defaults() -> None:
    settings = Settings()

    assert settings.login_max_attempts == 5
    assert settings.login_window_seconds == 300


def test_forwarded_headers_are_not_trusted_by_default() -> None:
    """**A security default, not a convenience one.**

    Trusting `X-Forwarded-For` with no proxy in front lets a caller invent a new
    address per request, which makes the login rate limiter decorative.
    """
    assert Settings().trust_proxy_headers is False


def test_no_secret_is_required_to_run() -> None:
    """There is deliberately no SESSION_SECRET, and its absence is the design.

    Session tokens are 32 bytes from `secrets.token_urlsafe` stored as a SHA-256
    digest — they are looked up, not verified, so there is no signing key to
    manage, rotate or leak. Adding one because production systems usually have
    one would be cargo cult.
    """
    assert not hasattr(Settings(), "session_secret")
