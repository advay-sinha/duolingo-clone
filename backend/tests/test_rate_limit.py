"""Login rate limiting — the mechanism, and the endpoint that uses it.

**Nothing here sleeps.** The limiter takes its clock as a constructor argument
precisely so time can be moved by assignment, which is what keeps expiry testable
in microseconds instead of five real minutes. A test that sleeps to prove a
timeout is a test nobody runs.

Two halves:

* the pure ``RateLimiter``, tested with a fake clock and no HTTP;
* the login endpoint, tested through the real API to prove the limit is actually
  wired in, that a success clears it, that learners are independent, and — the
  security-relevant one — that being blocked reveals nothing about whether an
  email exists.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api.v1.routes.auth import client_ip, login_limiter
from app.core.config import get_settings
from app.core.rate_limit import RateLimiter, login_key

API = "/api/v1"


class FakeClock:
    """A clock that only moves when a test says so."""

    def __init__(self, now: float = 1000.0) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


@pytest.fixture
def limiter() -> RateLimiter:
    return RateLimiter(max_attempts=3, window_seconds=60, clock=FakeClock())


# The limiter is reset around every test by an autouse fixture in `conftest.py`,
# because the tests it would otherwise poison are in other files.


# --------------------------------------------------------------------------
# The mechanism
# --------------------------------------------------------------------------


def test_below_the_limit_is_not_blocked(limiter: RateLimiter) -> None:
    limiter.register_failure("k")
    limiter.register_failure("k")

    assert limiter.is_blocked("k") is False


def test_at_the_limit_is_blocked(limiter: RateLimiter) -> None:
    for _ in range(3):
        limiter.register_failure("k")

    assert limiter.is_blocked("k") is True


def test_above_the_limit_stays_blocked(limiter: RateLimiter) -> None:
    for _ in range(10):
        limiter.register_failure("k")

    assert limiter.is_blocked("k") is True


def test_an_untouched_key_is_never_blocked(limiter: RateLimiter) -> None:
    assert limiter.is_blocked("nobody") is False
    assert limiter.retry_after("nobody") == 0


def test_keys_are_counted_independently(limiter: RateLimiter) -> None:
    for _ in range(3):
        limiter.register_failure("alice")

    assert limiter.is_blocked("alice") is True
    assert limiter.is_blocked("bob") is False


def test_a_reset_clears_the_count(limiter: RateLimiter) -> None:
    for _ in range(3):
        limiter.register_failure("k")
    limiter.reset("k")

    assert limiter.is_blocked("k") is False


def test_the_window_expires(limiter: RateLimiter) -> None:
    clock: FakeClock = limiter.clock  # type: ignore[assignment]
    for _ in range(3):
        limiter.register_failure("k")
    assert limiter.is_blocked("k") is True

    clock.advance(60)

    assert limiter.is_blocked("k") is False


def test_the_window_does_not_expire_early(limiter: RateLimiter) -> None:
    clock: FakeClock = limiter.clock  # type: ignore[assignment]
    for _ in range(3):
        limiter.register_failure("k")

    clock.advance(59.9)

    assert limiter.is_blocked("k") is True


def test_the_window_starts_at_the_first_failure_not_the_last(
    limiter: RateLimiter,
) -> None:
    """A fixed window, not a sliding one — and the difference is observable.

    Under a sliding window the third failure would extend the block. Under a
    fixed window the clock started at the first failure, so the block ends 60
    seconds after *that*. This test exists so the choice is documented by
    something that fails if it silently changes.
    """
    clock: FakeClock = limiter.clock  # type: ignore[assignment]
    limiter.register_failure("k")
    clock.advance(30)
    limiter.register_failure("k")
    limiter.register_failure("k")
    assert limiter.is_blocked("k") is True

    clock.advance(30)

    assert limiter.is_blocked("k") is False


def test_a_fresh_window_opens_after_expiry(limiter: RateLimiter) -> None:
    clock: FakeClock = limiter.clock  # type: ignore[assignment]
    for _ in range(3):
        limiter.register_failure("k")
    clock.advance(61)

    limiter.register_failure("k")

    assert limiter.is_blocked("k") is False


def test_retry_after_counts_down(limiter: RateLimiter) -> None:
    clock: FakeClock = limiter.clock  # type: ignore[assignment]
    for _ in range(3):
        limiter.register_failure("k")
    assert limiter.retry_after("k") == 60

    clock.advance(20)

    assert limiter.retry_after("k") == 40


def test_retry_after_is_zero_below_the_limit(limiter: RateLimiter) -> None:
    limiter.register_failure("k")

    assert limiter.retry_after("k") == 0


def test_expired_windows_do_not_accumulate(limiter: RateLimiter) -> None:
    """The dictionary is pruned on read, so it cannot grow without bound.

    Same housekeeping as `resolve_session` deleting expired session rows on
    sight: no sweeper process, and the rule stays correct without one.
    """
    clock: FakeClock = limiter.clock  # type: ignore[assignment]
    for index in range(50):
        limiter.register_failure(f"key-{index}")
    clock.advance(61)

    for index in range(50):
        limiter.is_blocked(f"key-{index}")

    assert limiter._windows == {}


# --------------------------------------------------------------------------
# The key
# --------------------------------------------------------------------------


def test_the_key_combines_email_and_ip() -> None:
    """Neither alone is right, and the test names both failure modes.

    Email only lets anyone lock a known learner out of their own account. IP only
    makes one office share a single budget.
    """
    assert login_key("a@x.com", "1.1.1.1") != login_key("a@x.com", "2.2.2.2")
    assert login_key("a@x.com", "1.1.1.1") != login_key("b@x.com", "1.1.1.1")


def test_the_key_is_case_insensitive_like_the_account() -> None:
    assert login_key("Alex@X.com", "1.1.1.1") == login_key("alex@x.com", "1.1.1.1")


def test_a_missing_ip_still_produces_a_key() -> None:
    assert login_key("a@x.com", None)


# --------------------------------------------------------------------------
# The endpoint
# --------------------------------------------------------------------------


def bad_login(client: TestClient, email: str, password: str = "wrong-password"):
    return client.post(f"{API}/auth/login", json={"email": email, "password": password})


def test_a_wrong_password_below_the_limit_is_the_usual_401(
    anon_client: TestClient,
) -> None:
    settings = get_settings()
    response = bad_login(anon_client, settings.demo_email)

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthenticated"
    assert response.json()["error"]["message"] == "Email or password is incorrect."


def test_the_response_is_unchanged_right_up_to_the_limit(
    anon_client: TestClient,
) -> None:
    """Everything below the limit must look exactly as it did before Phase 10."""
    settings = get_settings()
    seen = set()
    for _ in range(settings.login_max_attempts):
        response = bad_login(anon_client, settings.demo_email)
        seen.add((response.status_code, response.text))

    assert len(seen) == 1
    assert next(iter(seen))[0] == 401


def test_the_next_attempt_after_the_limit_is_429(anon_client: TestClient) -> None:
    settings = get_settings()
    for _ in range(settings.login_max_attempts):
        bad_login(anon_client, settings.demo_email)

    response = bad_login(anon_client, settings.demo_email)

    assert response.status_code == 429
    assert response.json()["error"]["code"] == "rate_limited"
    assert int(response.headers["Retry-After"]) > 0


def test_being_blocked_does_not_reveal_whether_an_email_exists(
    anon_client: TestClient,
) -> None:
    """**The security property this endpoint is built around, under limiting.**

    An address that has an account and one that does not must be indistinguishable
    — before the limit (identical 401) and after it (identical 429). The limiter
    never consults the users table, which is what makes this true by construction
    rather than by coincidence.
    """
    settings = get_settings()
    known, unknown = settings.demo_email, "nobody@example.com"

    known_below = bad_login(anon_client, known)
    unknown_below = bad_login(anon_client, unknown)
    assert (known_below.status_code, known_below.text) == (
        unknown_below.status_code,
        unknown_below.text,
    )

    for email in (known, unknown):
        for _ in range(settings.login_max_attempts):
            bad_login(anon_client, email)

    known_blocked = bad_login(anon_client, known)
    unknown_blocked = bad_login(anon_client, unknown)

    assert known_blocked.status_code == unknown_blocked.status_code == 429
    assert known_blocked.json() == unknown_blocked.json()


def test_a_correct_password_still_works_when_others_are_blocked(
    anon_client: TestClient,
) -> None:
    """One learner's failures must not lock a different learner out."""
    settings = get_settings()
    for _ in range(settings.login_max_attempts + 2):
        bad_login(anon_client, "someone-else@example.com")

    response = anon_client.post(
        f"{API}/auth/login",
        json={"email": settings.demo_email, "password": settings.demo_user_password},
    )

    assert response.status_code == 200


def test_a_successful_login_clears_the_learners_failures(
    anon_client: TestClient,
) -> None:
    """Someone who mistypes twice and then succeeds starts from zero again."""
    settings = get_settings()
    for _ in range(settings.login_max_attempts - 1):
        bad_login(anon_client, settings.demo_email)

    ok = anon_client.post(
        f"{API}/auth/login",
        json={"email": settings.demo_email, "password": settings.demo_user_password},
    )
    assert ok.status_code == 200

    # A full fresh budget, none of which is refused.
    for _ in range(settings.login_max_attempts):
        assert bad_login(anon_client, settings.demo_email).status_code == 401


def test_successful_logins_are_never_limited(anon_client: TestClient) -> None:
    """Only failures count. Signing in repeatedly is a person, not an attack."""
    settings = get_settings()
    body = {"email": settings.demo_email, "password": settings.demo_user_password}

    for _ in range(settings.login_max_attempts * 3):
        assert anon_client.post(f"{API}/auth/login", json=body).status_code == 200


def test_registration_is_not_rate_limited(anon_client: TestClient) -> None:
    """The limiter is on failed *logins*. Registration has its own protections
    (a unique email, a unique display name) and blocking it would stop new
    learners for the sake of a threat that does not apply to it."""
    settings = get_settings()
    for _ in range(settings.login_max_attempts + 2):
        bad_login(anon_client, "fresh@example.com")

    response = anon_client.post(
        f"{API}/auth/register",
        json={
            "email": "fresh@example.com",
            "password": "password123",
            "display_name": "Fresh",
        },
    )

    assert response.status_code == 201


def test_the_block_expires(anon_client: TestClient) -> None:
    """Proved by moving the limiter's clock, not by waiting five minutes."""
    settings = get_settings()
    clock = FakeClock()
    original = login_limiter.clock
    login_limiter.clock = clock
    try:
        for _ in range(settings.login_max_attempts):
            bad_login(anon_client, settings.demo_email)
        assert bad_login(anon_client, settings.demo_email).status_code == 429

        clock.advance(settings.login_window_seconds + 1)

        assert bad_login(anon_client, settings.demo_email).status_code == 401
    finally:
        login_limiter.clock = original


def test_a_blocked_request_never_reaches_the_password_hash(
    anon_client: TestClient, monkeypatch
) -> None:
    """The check runs *before* bcrypt, which is what stops the endpoint from
    being a cheap way to spend the server's CPU."""
    settings = get_settings()
    for _ in range(settings.login_max_attempts):
        bad_login(anon_client, settings.demo_email)

    from app.services import auth_service

    def explode(*args, **kwargs):
        raise AssertionError("verify_password must not run for a blocked request")

    monkeypatch.setattr(auth_service, "verify_password", explode)

    assert bad_login(anon_client, settings.demo_email).status_code == 429


# --------------------------------------------------------------------------
# Client identification
# --------------------------------------------------------------------------


def test_forwarded_headers_are_ignored_unless_trusted(monkeypatch) -> None:
    """**Trusting `X-Forwarded-For` with no proxy in front breaks the limiter.**

    An attacker sets a different value per request, every request looks like a
    new client, and nothing is ever limited. So the default is to ignore it, and
    this test is what keeps that default from being "improved" away.
    """

    class Req:
        headers = {"x-forwarded-for": "9.9.9.9"}
        client = type("C", (), {"host": "10.0.0.1"})()

    get_settings.cache_clear()
    monkeypatch.setenv("TRUST_PROXY_HEADERS", "false")
    assert client_ip(Req()) == "10.0.0.1"

    get_settings.cache_clear()
    monkeypatch.setenv("TRUST_PROXY_HEADERS", "true")
    assert client_ip(Req()) == "9.9.9.9"

    get_settings.cache_clear()


def test_the_leftmost_forwarded_address_is_used(monkeypatch) -> None:
    """A proxy chain appends, so the original client is first."""

    class Req:
        headers = {"x-forwarded-for": "1.2.3.4, 10.0.0.1, 10.0.0.2"}
        client = type("C", (), {"host": "10.0.0.2"})()

    get_settings.cache_clear()
    monkeypatch.setenv("TRUST_PROXY_HEADERS", "true")
    try:
        assert client_ip(Req()) == "1.2.3.4"
    finally:
        get_settings.cache_clear()
