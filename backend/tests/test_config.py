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
